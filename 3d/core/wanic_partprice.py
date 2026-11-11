# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""What one generated part costs, for the Properties panel: its main
quantity (ลบ.ม. of concrete, ตร.ม. of wall or plaster, กก. of steel, ม. of
board, ชุด of a door…), the material price per unit (the BOQ's price list —
the province's, หลักเกณฑ์ 2569 recipes), the labour per unit (ว480) and the
amounts. The rows are added to the part's info (``ext["wanic_building"]
["info"]``), so the panel shows them with the rest of the part's data.

Only the part's main work item is priced here; formwork, rebar, paint and
the like are in the full BOQ (ปร.4 / ปร.5).
"""
from __future__ import annotations

from core import wanic_building as B
from core import wanic_quantities as Q
from core import wanic_std2569 as S

STEEL_KG_M3 = 7850.0
CONCRETE_KINDS = ("footing", "stump", "column", "beam", "slab", "stair", "band")
STEEL_KINDS = ("ridge", "hip", "rafter", "purlin", "post", "valley",
               "wallplate", "tiebeam", "rbeam", "strut", "brace")


def _det3(m) -> float:
    """The volume scale of a matrix's linear part."""
    d = m.data()                                        # column-major 4x4
    a, b, c = d[0], d[4], d[8]
    e, f, g_ = d[1], d[5], d[9]
    h, i, j = d[2], d[6], d[10]
    return a * (f * j - g_ * i) - b * (e * j - g_ * h) + c * (e * i - f * h)


def _vol(g) -> float:
    """The part's volume AS IT STANDS in the model: a copy that was
    stretched shares its definition's mesh and carries the stretch in its
    ``xform``, so the definition's volume alone read the same for every
    copy, however tall."""
    from core import bim
    try:
        if getattr(g, "children", None):
            from core.group import world_mesh
            return abs(float(bim.face_set_volume(list(world_mesh(g).faces)) or 0.0))
        v = abs(float(bim.face_set_volume(list(g.mesh.faces)) or 0.0))
        m = getattr(g, "xform", None)
        return v * abs(_det3(m)) if m is not None else v
    except Exception:                                   # noqa: BLE001
        return 0.0


def extents(g) -> tuple:
    """(dx, dy, dz) of the part in the world, after any stretch."""
    m = getattr(g, "xform", None)
    pts = []
    for v in g.mesh.vertices:
        p = v.position
        if m is not None:
            p = m.map(p)
        pts.append((p.x(), p.y(), p.z()))
    for kid in getattr(g, "children", None) or []:
        from core.group import world_mesh
        for v in world_mesh(kid).vertices:
            p = v.position
            if m is not None:
                p = m.map(p)
            pts.append((p.x(), p.y(), p.z()))
    if not pts:
        return 0.0, 0.0, 0.0
    xs, ys, zs = zip(*pts)
    return max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)


def _money(text):
    try:
        return float(str(text).replace(",", "").split()[0])
    except (ValueError, IndexError):
        return None


_LIVE: dict = {}


def live_rows(g) -> list:
    """Cached :func:`_live_rows` (a click must stay instant): the key is
    what a stretch or an edit changes — the matrix, the mesh and its size,
    the stored rows."""
    m = getattr(g, "xform", None)
    rec = ((g.ext or {}).get(B.EXT_KEY)) or {}
    key = (id(g.mesh), len(g.mesh.faces), len(g.mesh.vertices),
           tuple(round(x, 9) for x in m.data()) if m is not None else None,
           repr(rec.get("info")))
    hit = _LIVE.get(id(g))
    if hit is not None and hit[0] == key:
        return hit[1]
    if g.mesh.faces and len(g.mesh.faces) > 3000:
        return [list(r) for r in (rec.get("info") or []) if r and len(r) > 1]
    rows = _live_rows(g)
    if len(_LIVE) > 4000:
        _LIVE.clear()
    _LIVE[id(g)] = (key, rows)
    return rows


def _live_rows(g) -> list:
    """The part's info rows measured again from its geometry now: size,
    concrete, quantity, length and the amounts follow a part that was
    stretched, shortened or scaled after it was made (the unit prices stay
    those it was priced with)."""
    rec = ((g.ext or {}).get(B.EXT_KEY)) or {}
    rows = [list(r) for r in (rec.get("info") or []) if r and len(r) > 1]
    if not rows:
        return rows
    kind = rec.get("kind", "")
    dx, dy, dz = extents(g)
    v = _vol(g)
    have = {r[0] for r in rows}
    new = {}
    qty = None
    if kind in CONCRETE_KINDS:
        a, b = sorted((dx, dy))
        if kind in ("column", "stump"):
            new["ขนาด"] = f"{a:.2f} × {b:.2f} ม. สูง {dz:.2f} ม."
        elif kind == "footing":
            new["ขนาด"] = f"{a:.2f} × {b:.2f} × {dz:.2f} ม."
        elif kind == "beam":
            new["ขนาด"] = f"{a:.2f} × {dz:.2f} ม."
            if "ความยาวสุทธิ (ระหว่างหน้าเสา)" in have:
                new["ความยาวสุทธิ (ระหว่างหน้าเสา)"] = f"{b:.2f} ม."
        elif kind == "slab" and "ขนาดห้อง" in have:
            new["ขนาดห้อง"] = f"{a:.2f} × {b:.2f} ม. หนา {dz:.2f} ม."
        new["คอนกรีต"] = f"{v:.3f} ลบ.ม."
        qty, unit = v, "ลบ.ม."
    elif kind in STEEL_KINDS:
        kg = v * STEEL_KG_M3
        L = max(dx, dy, dz)
        if "ความยาว" in have:
            new["ความยาว"] = f"{L:.2f} ม."
        qty, unit = kg, "กก."
    if qty is not None:
        old_q = next((r[1] for r in rows if r[0] == "ปริมาณ"), "")
        if old_q and "·" in old_q and kind in STEEL_KINDS:
            new["ปริมาณ"] = f"{max(dx, dy, dz):,.2f} ม. · {qty:,.2f} {unit}"
        elif old_q:
            new["ปริมาณ"] = f"{qty:,.3f} {unit}"
        mat = _money(next((r[1] for r in rows if r[0] == "ราคาวัสดุ/หน่วย"), "")) or 0.0
        lab = _money(next((r[1] for r in rows if r[0] == "ค่าแรง/หน่วย"), "")) or 0.0
        if "ค่าวัสดุ" in have:
            new["ค่าวัสดุ"] = f"{qty * mat:,.2f} บาท"
        if "ค่าแรง" in have:
            new["ค่าแรง"] = f"{qty * lab:,.2f} บาท"
        if "รวม" in have:
            new["รวม"] = f"{qty * (mat + lab):,.2f} บาท (ยังไม่คูณ Factor F)"
    return [[k, new.get(k, val)] for k, val in rows]


def refresh(g) -> bool:
    """Write :func:`live_rows` back to the part (after a stretch), so the
    BOQ lines that read the rows agree with the model. True when changed."""
    rec = ((g.ext or {}).get(B.EXT_KEY)) or {}
    if not rec.get("info"):
        return False
    rows = _live_rows(g)
    if rows == [list(r) for r in rec["info"] if r and len(r) > 1]:
        return False
    ext = dict(g.ext)
    ext[B.EXT_KEY] = dict(rec, info=rows)
    g.ext = ext
    return True


def unit_rates(data) -> dict:
    """{what: (material/unit, labour/unit, unit, labour code, note)}."""
    s = B.settings_of(data)
    o = Q.options_of(data)
    prices, labour = Q.prices_of(data), Q.labour_of(data)
    n = max(B.elements(data)["n"], 1)
    conc_lab = ("1.7b" if n > 1 else "1.7a") if o["ready_mix"] else \
        ("1.6.2b" if n > 1 else "1.6.2a")
    conc_mat = prices.get(Q.CONCRETE, 0.0) if o["ready_mix"] else \
        Q.recipe_price("2.2", prices)[0]
    r = {"concrete": (conc_mat, labour.get(conc_lab, 0.0), "ลบ.ม.", conc_lab,
                      "คอนกรีต (ไม่รวมไม้แบบ เหล็กเสริม)")}
    r["timber"] = (prices.get("ไม้เนื้อแข็ง (โครงหลังคา)", 0.0), 0.0, "ลบ.ฟ.", "",
                   "ไม้โครงหลังคา (ไม่รวมน้ำยากันปลวก)")
    steel = prices.get("เหล็กรูปพรรณ (ทั่วไป)", 0.0)
    r["steel"] = (steel, labour.get("1.11.1", 0.0), "กก.", "1.11.1",
                  "เหล็กรูปพรรณ (ไม่รวมสีกันสนิม)")
    for ext in (True, False):
        sp = B.wall_spec(s, ext)
        mat, _n = Q.recipe_price(sp["recipe"], prices)
        code = S.wall_labour_code(sp["recipe"])
        r[f"wall:{'ext' if ext else 'int'}"] = (mat, labour.get(code, 0.0),
                                                "ตร.ม.", code, sp["name"])
    pmat, _n = Q.recipe_price(o["plaster_recipe"], prices)
    r["plaster:ext"] = (pmat * (s.get("ext_plaster_t", 0.015) / 0.015),
                        labour.get("2.3.1.2b", 0.0), "ตร.ม.", "2.3.1.2b",
                        "ฉาบปูนผนังภายนอก")
    r["plaster:int"] = (pmat * (s.get("plaster_t", 0.015) / 0.015),
                        labour.get("2.3.1.2a", 0.0), "ตร.ม.", "2.3.1.2a",
                        "ฉาบปูนผนังภายใน")
    fk = "เชิงชายไม้สำเร็จรูป 1\"×8\" + ทับเชิงชาย 1\"×6\""
    r["board"] = (prices.get(fk, 0.0), labour.get("2.1.10a", 0.0), "ม.",
                  "2.1.10a", "เชิงชาย/ปั้นลม + ทับ ไม้สำเร็จรูป")
    for ct, (cname, clab, *_r) in B.CEILING_TYPES.items():
        from core import wanic_w480 as W
        r[f"ceiling:{cname}"] = (prices.get(f"{cname} (วัสดุครบชุด)", 0.0),
                                 float(W.rate(clab)), "ตร.ม.", clab, cname)
    sname, slab, _h, _t, srate = B.SKIRTING_TYPES.get(
        s.get("skirting_type", "ceramic"), B.SKIRTING_TYPES["ceramic"])
    r["skirting"] = (prices.get(f"{sname} (วัสดุ)", 0.0), float(srate), "ม.", slab, sname)
    smat, _n = Q.recipe_price("5.41", prices)
    r["soffit"] = (smat, labour.get("2.2.1c", 0.0), "ตร.ม.", "2.2.1c",
                   "ฝ้าชายคาระแนงไม้เทียม")
    return r


def _qty(g, kind, info) -> tuple:
    """(rate key, quantity) of a part."""
    v = _vol(g)
    if kind in CONCRETE_KINDS:
        return "concrete", v
    rows = dict(info)
    if kind in STEEL_KINDS:
        if "ไม้" in str(rows.get("ขนาด", "")) or "ไม้" in str(rows.get("หน้าตัด", "")):
            return "timber", v * 35.3147                 # ลบ.ฟ. of timber
        return "steel", v * STEEL_KG_M3
    if kind == "wall":
        t = B.wall_spec({**B.DEFAULT_SETTINGS}, True)["t"]
        try:
            t = float(rows.get("ความหนาเนื้อผนัง", "").split()[0]) / 100.0
        except (ValueError, IndexError):
            pass
        ext = "ภายนอก" in rows.get("ชนิด", "")
        return ("wall:ext" if ext else "wall:int"), (v / t if t else 0.0)
    if kind == "plaster":
        try:
            t = float(rows.get("ความหนา", "").split()[0]) / 100.0
        except (ValueError, IndexError):
            t = 0.015
        ext = "ภายนอก" in rows.get("ชนิด", "")
        return ("plaster:ext" if ext else "plaster:int"), (v / t if t else 0.0)
    if kind == "ceiling":
        try:
            return f"ceiling:{rows.get('ชนิด', '')}", float(rows.get("พื้นที่", "").split()[0])
        except (ValueError, IndexError):
            return "", 0.0
    if kind == "skirting":
        try:
            return "skirting", float(rows.get("ความยาว", "").split()[0])
        except (ValueError, IndexError):
            return "", 0.0
    if kind in ("fascia", "barge"):
        try:
            return "board", float(rows.get("ความยาว", "").split()[0])
        except (ValueError, IndexError):
            return "board", 0.0
    return "", 0.0


def price_rows(g, rates) -> list:
    rec = ((g.ext or {}).get(B.EXT_KEY)) or {}
    kind = rec.get("kind", "")
    key, qty = _qty(g, kind, rec.get("info") or [])
    if not key or qty <= 0 or key not in rates:
        return []
    mat, lab, unit, code, what = rates[key]
    rows = [("— ราคา —", what),
            ("ปริมาณ", f"{qty:,.3f} {unit}"),
            ("ราคาวัสดุ/หน่วย", f"{mat:,.2f} บาท/{unit}" if mat else
             "ยังไม่มีราคา (เลือกจังหวัด/ใส่ราคาใน BOQ)"),
            ("ค่าแรง/หน่วย", f"{lab:,.2f} บาท/{unit} (ว480 {S.w480_code(code)})"),
            ("ค่าวัสดุ", f"{qty * mat:,.2f} บาท"),
            ("ค่าแรง", f"{qty * lab:,.2f} บาท"),
            ("รวม", f"{qty * (mat + lab):,.2f} บาท (ยังไม่คูณ Factor F)")]
    return rows


def annotate(groups, data) -> int:
    """Add the price rows to every part that has a main work item."""
    rates = unit_rates(data)
    n = 0
    for g in groups:
        rows = price_rows(g, rates)
        if not rows:
            continue
        ext = dict(g.ext or {})
        rec = dict(ext.get(B.EXT_KEY) or {})
        rec["info"] = [r for r in (rec.get("info") or []) if r and r[0] != "— ราคา —"
                       and r[0] not in ("ปริมาณ", "ราคาวัสดุ/หน่วย", "ค่าแรง/หน่วย",
                                        "ค่าวัสดุ", "ค่าแรง", "รวม")]
        rec["info"] += [[k, v] for k, v in rows]
        ext[B.EXT_KEY] = rec
        g.ext = ext
        n += 1
    return n


#: what a part is counted in when it has no price row of its own
COUNT_UNIT = {"door": "บาน", "window": "บาน", "fixture": "ชุด", "light": "ชุด", "light_out": "ชุด",
              "outlet": "ชุด", "panel": "ชุด", "ac": "ชุด", "ac_out": "ชุด",
              "ac_bracket": "ชุด", "fan": "ชุด", "septic": "ถัง", "grease": "ถัง",
              "meter": "ชุด", "tap": "จุด", "manhole": "บ่อ", "ground_rod": "ต้น",
              "sign": "ป้าย", "headplate": "แผ่น", "pile": "ต้น", "cap": "แผ่น"}
LENGTH_KINDS = ("pipe_supply", "pipe_drain", "drain_pipe", "gutter", "eave_gutter", "downspout",
                "fascia", "barge", "skirting", "cornice", "ceiling_frame", "soffit_frame")
AREA_KINDS = ("skin", "tiles", "gable", "infill", "soffit", "walkway", "ceiling")


def _area(g, up_only=False) -> float:
    """The plan of a plate: the area of its faces facing the most common
    way (one side of a wall, the top of a slab, the roof faces up)."""
    import math
    best: dict = {}
    for f in g.mesh.faces:
        for a, b, c in f.triangulate():
            ux, uy, uz = b.x() - a.x(), b.y() - a.y(), b.z() - a.z()
            vx, vy, vz = c.x() - a.x(), c.y() - a.y(), c.z() - a.z()
            nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
            ar = 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)
            if ar < 1e-12:
                continue
            n = (nx / (2 * ar), ny / (2 * ar), nz / (2 * ar))
            if up_only:
                if n[2] > 0.1:
                    best[0] = best.get(0, 0.0) + ar
                continue
            key = (round(n[0], 1), round(n[1], 1), round(n[2], 1))
            best[key] = best.get(key, 0.0) + ar
    return max(best.values()) if best else 0.0


def _num(text):
    try:
        return float(str(text).replace(",", "").split()[0])
    except (ValueError, IndexError):
        return None


def annotate_units(groups) -> int:
    """A «ปริมาณ» row on every part that has none yet, in the unit it is
    counted in: ลบ.ม. for concrete, ตร.ม. for walls, roofs and ceilings,
    ม. for pipes and boards, กก. for steel, ชุด/บาน/บ่อ/จุด for things."""
    import re
    n = 0
    for g in groups:
        ext = dict(g.ext or {})
        rec = dict(ext.get(B.EXT_KEY) or {})
        info = [list(r) for r in (rec.get("info") or []) if r]
        if any(r[0] == "ปริมาณ" for r in info):
            continue
        rows = {r[0]: r[1] for r in info if len(r) > 1}
        kind = rec.get("kind", "")
        q = None
        if kind in CONCRETE_KINDS:
            q = f"{_vol(g):,.3f} ลบ.ม."
        elif kind in STEEL_KINDS:
            L = _num(rows.get("ความยาว"))
            kg = _vol(g) * STEEL_KG_M3
            q = (f"{L:,.2f} ม. · " if L else "") + f"{kg:,.2f} กก."
        elif kind in LENGTH_KINDS:
            L = _num(rows.get("ความยาวรวม") or rows.get("ความยาว"))
            if L is None:
                m = re.search(r"ยาว(?:รวม)?\s*([\d,.]+)\s*ม", getattr(g, "name", "") or "")
                L = _num(m.group(1)) if m else None
            if L is not None:
                q = f"{L:,.2f} ม."
            else:
                A = _num(rows.get("พื้นที่"))
                q = f"{A:,.2f} ตร.ม." if A is not None else f"{_area(g, True):,.2f} ตร.ม. (ตามแปลน)"
        elif kind in AREA_KINDS:
            A = _num(rows.get("พื้นที่"))
            if A is None:
                A = _area(g, up_only=kind in ("skin", "tiles", "ceiling", "soffit", "walkway"))
            q = f"{A:,.2f} ตร.ม."
        elif kind in ("wall", "plaster"):
            q = f"{_area(g):,.2f} ตร.ม."
        else:
            unit = COUNT_UNIT.get(kind)
            m = re.search(r"([\d,]+)\s*(ชุด|บ่อ|จุด|บาน|แผ่น|ต้น|ตัว)", getattr(g, "name", "") or "")
            if m:
                q = f"{m.group(1)} {m.group(2)}"
            elif unit:
                q = f"1 {unit}"
            else:
                v = _vol(g)
                q = f"{v:,.3f} ลบ.ม." if v > 1e-6 else "1 ชิ้น"
        if q:
            info.append(["ปริมาณ", q])
            rec["info"] = info
            ext[B.EXT_KEY] = rec
            g.ext = ext
            n += 1
    return n
