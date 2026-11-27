# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""วัตถุที่คัดลอกในโมเดล — the owner (27 พ.ย. 69): «เมื่อคัดลอกวัตถุใดๆ ออกมาแล้ว ให้มีราคา มีวัสดุเพิ่ม
หากมีการยืดหรือหด ก็ยังให้มีราคาและวัสดุเพิ่มทุกอย่าง เหมือนเป็นวัสดุที่สร้างขึ้นใหม่ และนำไปคิดเพิ่มใน BOQ».

Every group a build makes carries a ``uid`` (``wanic_building._tag``). A copy of it carries the same
``ext`` and so the same uid: the first group of a uid in the scene is the built one, the others are
copies — they get ``copy = True`` and a uid of their own (a copy of a copy is a copy too). A rebuild
replaces the built groups and keeps the copies.

``records(scene)`` measures each copy as it now is in the model (moved, turned, stretched or shrunk):
its volume, its length (the longest side of its box) and what it is (kind, mark, key). The building
panel writes them into ``data["copies"]``; ``wanic_quantities.compute`` adds their lines to the BOQ
with the unit prices of the lines of the member they were copied from (``copy_lines``).
"""
from __future__ import annotations

import secrets

EXT_KEY = "wanic_building"

#: the BOQ line suffix («… — คานหลังคา») of a concrete member, by kind
CONCRETE_KINDS = {"footing": "ฐานราก", "stump": "เสาตอม่อ", "column": "เสา", "stair": "บันได"}


def new_uid() -> str:
    return secrets.token_hex(6)


def _rec(g) -> dict:
    return ((getattr(g, "ext", None) or {}).get(EXT_KEY)) or {}


def mark_copies(scene) -> list:
    """Flag the copies among the top-level built groups; returns them."""
    seen, out = set(), []
    for g in list(getattr(scene, "groups", []) or []):
        rec = _rec(g)
        if not rec:
            continue
        uid = rec.get("uid")
        if rec.get("copy"):
            if uid in seen or not uid:                 # a copy of this copy
                rec = dict(rec, uid=new_uid())
                g.ext = dict(g.ext, **{EXT_KEY: rec})
            seen.add(rec["uid"])
            out.append(g)
            continue
        if not uid:
            continue                                   # built before uids: cannot tell
        if uid in seen:
            rec = dict(rec, copy=True, uid=new_uid())
            g.ext = dict(g.ext, **{EXT_KEY: rec})
            seen.add(rec["uid"])
            out.append(g)
        else:
            seen.add(uid)
    return out


def is_copy(g) -> bool:
    return bool(_rec(g).get("copy"))


def measure(g) -> tuple:
    """(volume m³, length m) of a group as it stands in the model."""
    vol = None
    try:
        from core.solids import solid_volume
        vol = solid_volume(g)
    except Exception:                                  # noqa: BLE001 - not a solid
        vol = None
    pts = []
    try:
        from core.group import world_mesh
        pts = [v.position for v in world_mesh(g).vertices]
    except Exception:                                  # noqa: BLE001
        try:
            pts = [v.position for v in g.mesh.vertices]
        except Exception:                              # noqa: BLE001
            pts = []
    if pts:
        dx = max(p.x() for p in pts) - min(p.x() for p in pts)
        dy = max(p.y() for p in pts) - min(p.y() for p in pts)
        dz = max(p.z() for p in pts) - min(p.z() for p in pts)
        length = max(dx, dy, dz)
        if vol is None:
            vol = dx * dy * dz                         # an open shell: its box
    else:
        length = 0.0
    return abs(float(vol or 0.0)), float(length)


def records(scene) -> list:
    """[{kind, mark, key, part, volume, length}] of every copy in the model, in scene order."""
    out = []
    for g in mark_copies(scene):
        rec = _rec(g)
        vol, length = measure(g)
        out.append({"kind": str(rec.get("kind") or ""), "mark": str(rec.get("mark") or ""),
                    "key": str(rec.get("key") or rec.get("mark") or ""), "part": str(rec.get("part") or ""),
                    "volume": round(vol, 4), "length": round(length, 3)})
    return out


# ---------------------------------------------------------------------------
# The BOQ lines of the copies
# ---------------------------------------------------------------------------

CONC = "คอนกรีตโครงสร้าง"


def _suffix(r: dict, base: list) -> str:
    """The «— …» of the concrete lines the copy belongs to, '' when none."""
    kind, mark = r["kind"], r["mark"].upper()
    if kind in CONCRETE_KINDS:
        return CONCRETE_KINDS[kind]
    conc = [ln["desc"].split(" — ", 1)[1] for ln in base
            if ln["desc"].startswith(CONC) and " — " in ln["desc"]]
    if kind == "beam":
        want = "คานคอดิน" if mark.startswith("GB") else "คานหลังคา" if mark.startswith("RB") else ""
        if want and want in conc:
            return want
        return next((c for c in conc if c.startswith("คาน") and c not in ("คานคอดิน", "คานหลังคา")),
                    next((c for c in conc if c.startswith("คาน")), ""))
    if kind == "slab":
        return next((c for c in conc if c.startswith("พื้น")), "")
    return ""


def copy_lines(records_: list, base: list, add) -> int:
    """Add the lines of the copies through ``add(group, desc, net, unit, **kw)`` (the bill's add);
    ``base``: the lines of the model as built. Returns how many copies were billed."""
    if not records_:
        return 0
    conc_all = sum(ln["net"] for ln in base if ln["desc"].startswith(CONC))
    rebar = [ln for ln in base if ln["group"] == "rebar"]
    rebar_r = 0.0
    by_line: dict = {}                              # (group, desc, unit) -> [net, base line, names]
    n = 0

    def put(ln, net, name):
        k = (ln["group"], ln["desc"], ln["unit"])
        e = by_line.setdefault(k, [0.0, ln, []])
        e[0] += net
        e[2].append(name)

    for r in records_:
        name = r["key"] or r["mark"] or r["kind"]
        suf = _suffix(r, base)
        if suf and r["volume"] > 0:
            sib = [ln for ln in base if ln["desc"].endswith(" — " + suf)]
            conc = next((ln for ln in sib if ln["desc"].startswith(CONC)), None)
            if conc and conc["net"] > 0:
                ratio = r["volume"] / conc["net"]
                for ln in sib:
                    put(ln, ln["net"] * ratio, name)
                if conc_all > 0:
                    rebar_r += r["volume"] / conc_all
                n += 1
                continue
        line = next((ln for ln in base if ln["desc"] == f"โครงหลังคาเหล็ก {name.split(' ', 1)[-1]}"), None)
        if line is not None and r["length"] > 0:
            try:
                from core import wanic_building as B
                from core import wanic_profiles as P
                fam, params = B.steel_lookup(name.split(" ", 1)[-1])
                kgm = P.weight_per_m(fam, params)
            except Exception:                           # noqa: BLE001
                kgm = 0.0
            if kgm > 0:
                put(line, r["length"] * kgm * 1.03, name)
                n += 1
                continue
        # anything else: one piece, priced by the user (orange until typed in)
        add("misc", f"วัตถุคัดลอกในโมเดล — {name}", 1.0, "ชิ้น", mat_key=f"วัตถุคัดลอก {name}",
            basis=f"คัดลอกในโมเดล · ยาว {r['length']:.2f} ม. · ปริมาตร {r['volume']:.3f} ลบ.ม.",
            note="วัตถุที่คัดลอกเพิ่ม — กรอกราคาในแท็บฐานข้อมูลราคา")
        n += 1
    if rebar_r > 0:
        for ln in rebar:
            put(ln, ln["net"] * rebar_r, "เหล็กเสริมตามสัดส่วนปริมาตรคอนกรีต")
    for (group, desc, unit), (net, ln, names) in by_line.items():
        uniq = sorted(set(names))
        add(group, f"{desc} (วัตถุคัดลอกเพิ่ม)", net, unit, waste=ln.get("waste", 0.0),
            mat=ln.get("mat") or None, mat_key=ln.get("mat_key", ""), lab_code=ln.get("lab_code", ""),
            lab=ln.get("lab") if ln.get("lab") else None,
            basis=f"วัตถุที่คัดลอกในโมเดล {len(names)} ชิ้น ({', '.join(uniq[:4])}"
                  + (" …" if len(uniq) > 4 else "") + ") — ตามขนาดจริงในโมเดล ราคาต่อหน่วยเท่ารายการเดิม",
            ref=ln.get("ref", ""), note="วัตถุที่คัดลอกเพิ่มในโมเดล")
    return n
