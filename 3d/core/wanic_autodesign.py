# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ออกแบบอัตโนมัติจนผ่านทุกชิ้นส่วน (หลังคา → เสาเข็ม).

The rules the owner set:

* ฐานรากไม่จำเป็นต้องเท่ากันทุกฐาน — every footing is sized for its own
  load on the allowable soil pressure (or its piles), then the sizes are
  grouped into a few marks F1, F2, … (smallest first) so the site builds a
  handful of types, never one oversized type everywhere.
* คานคอดิน ตอม่อ และเสาชั้น 1 มีหน้าตัดเท่ากัน — one section for the
  ground-floor columns and the stumps (the ground beams as wide as they
  are); the steel differs with the load: the points are grouped into
  marks C1, C2 … / PC1, PC2 … by the bars they need.
* Nothing is reported as passing until a fresh analysis says so: the
  changes are applied, the building analysed again, and repeated until no
  member fails (or nothing more can be changed — then what still fails is
  reported, never hidden).
"""
from __future__ import annotations

import copy
import math

from core import wanic_calc as C
from core import wanic_rc as R

SIDE_STEP = 0.10                     # footing sides in 10 cm steps
MIN_SIDE = 0.80
MAX_GROUPS = 4                       # a few footing / column types, not one per point
BARS = [(n, d) for d in (12, 16, 20, 25) for n in (4, 6, 8, 10, 12)]
RHO_MAX = 0.04                       # ACI 10.9.1 (ρ ≤ 8 %, ≤ 4 % for laps — the economical limit)
SECTION_STEP = 0.05


def _node(x, y):
    from core import wanic_building as B
    return B.node_key(x, y)


def _assign(data, x, y, role, mark):
    a = data.setdefault("assign", {})
    rec = dict(a.get(_node(x, y)) or {})
    rec[role] = mark
    a[_node(x, y)] = rec


def _groups(values: list, limit: int = MAX_GROUPS) -> list:
    """Distinct values, merged upward until at most ``limit`` remain."""
    vals = sorted(set(values))
    while len(vals) > limit:
        gaps = [(vals[i + 1] - vals[i], i) for i in range(len(vals) - 1)]
        _g, i = min(gaps)
        del vals[i]                                     # the smaller one joins the larger
    return vals


# -- footings ----------------------------------------------------------------------------------

def footing_side(P_service: float, qa_t: float, depth: float, conc: float = 2400.0) -> tuple:
    """(side, thickness) of a square footing that carries ``P_service`` kg on
    ``qa_t`` t/m² with its own weight and the soil on it (1.8 t/m³)."""
    side = MIN_SIDE
    for _ in range(60):
        t = max(0.30, math.ceil(max(0.25, side / 5) * 20) / 20)
        q = (P_service + side * side * t * conc) / (side * side)       # as wanic_calc.analyse (net)
        if q <= qa_t * 1000.0 + 1e-6:
            return round(side, 2), t
        side = round(side + SIDE_STEP, 2)
    return round(side, 2), t


def design_footings(data, res) -> list:
    """Size every spread footing for its load and group them into F1.. ;
    returns the lines that say what changed."""
    from core import wanic_building as B
    had_cf = bool(data.get("combined_footings"))
    data["combined_footings"] = []                         # re-decided below from the single sizes
    E = B.elements(data)
    lib = B.library_of(data)
    b_ = res["basis"]
    D_, _L = C.factors(b_)
    loads = dict(res["columns"])
    base = dict(lib.get("F1") or {})
    if int(base.get("piles") or 0):                       # piles: the pile count rule (advice) handles them
        if had_cf:
            data["combined_footings"] = []
        return []
    need = {}
    for f in E["footings"]:
        k = (round(f["x"], 3), round(f["y"], 3))
        P = loads.get(k, 0.0) / D_
        sp = lib.get(f["mark"], base)
        need[(f["x"], f["y"])] = footing_side(P, b_["soil"], float(sp.get("depth") or base.get("depth") or 1.5),
                                              b_["concrete"])
    if not need:
        return []
    sizes = _groups([s for s, _t in need.values()])
    new_lib = dict(data.get("library") or {})
    for old in [m for m, v in lib.items() if v.get("kind") == "footing" and m != "F1"]:
        new_lib.pop(old, None)                            # regrouped from scratch
    marks = {}
    for i, side in enumerate(sizes, 1):
        t = max(t for s, t in need.values() if s <= side + 1e-9 and
                (i == 1 or s > sizes[i - 2] + 1e-9)) if any(s <= side for s, _ in need.values()) else 0.3
        mark = f"F{i}"
        new_lib[mark] = {**base, **(new_lib.get(mark) or {}), "kind": "footing", "w": side, "l": side,
                         "t": max(t, float((new_lib.get(mark) or {}).get("t", 0) if mark != "F1" else 0))}
        marks[side] = mark
    data["library"] = new_lib
    for (x, y), (s, _t) in need.items():
        side = next(v for v in sizes if v >= s - 1e-9)
        _assign(data, x, y, "F", marks[side])
    counts = {}
    for (x, y), (s, _t) in need.items():
        m = marks[next(v for v in sizes if v >= s - 1e-9)]
        counts[m] = counts.get(m, 0) + 1
    cf_lines = _combine(data, need, sizes, marks, loads, D_, b_, base, counts)
    return [f"{m} (ขั้น 2 ฐานราก): กว้าง {side:.2f} × ยาว {side:.2f} ม. หนา {new_lib[m]['t']:.2f} ม. · {counts.get(m, 0)} ฐาน "
            f"(ดินรับ {b_['soil']:g} ตัน/ตร.ม.)" for side, m in sorted((s, m) for s, m in marks.items())
            if counts.get(m)] + cf_lines


def _combine(data, need, sizes, marks, loads, D_, b_, base, counts) -> list:
    """ฐานรากร่วม (ข12): the single footings that would overlap become one
    footing under both columns (CF1 …, alike ones share a mark)."""
    from core import wanic_building as B
    from core import wanic_combined as CF
    side_of = {k: next(v for v in sizes if v >= s - 1e-9) for k, (s, _t) in need.items()}
    sq = {(round(x, 3), round(y, 3)): (sd, sd) for (x, y), sd in side_of.items()}
    found, notes = CF.pairs(sq)
    lib = B.library_of(data)
    new_lib = dict(data.get("library") or {})
    for old in [m for m in new_lib if m.startswith("CF") and m[2:].isdigit()]:
        new_lib.pop(old)
    kinds, out = {}, []
    for a, b2 in found:
        cs = []
        for p_ in (a, b2):
            st = lib.get(B.node_mark(data, lib, p_[0], p_[1], "PC")) or {}
            cs.append(max(float(st.get("b", 0.2) or 0.2), float(st.get("h", 0.2) or 0.2)))
        r = CF.design(a, b2, loads.get(a, 0.0), loads.get(b2, 0.0), D_, cs[0], cs[1], b_["soil"],
                      b_["concrete"], float(b_.get("fc", 240) or 240), float(b_.get("fy_db", 4000) or 4000),
                      sq[a], sq[b2], max([t_ for k_, (_s, t_) in need.items()
                                            if (round(k_[0], 3), round(k_[1], 3)) in (a, b2)] + [0.30]))
        key = (r["w"], r["l"], r["t"], r["bars"], r["bars_y"], r["top"]) if r["along_x"] else \
            (r["l"], r["w"], r["t"], r["bars_y"], r["bars"], r["top"])
        mark = kinds.setdefault(key, f"CF{len(kinds) + 1}")
        new_lib[mark] = dict(base, kind="footing", w=r["w"], l=r["l"], t=r["t"], bars=r["bars"],
                             bars_y=r["bars_y"], top=r["top"], combined=True, piles=0)
        data.setdefault("combined_footings", []).append(
            {"mark": mark, "nodes": [list(a), list(b2)], "cx": r["cx"], "cy": r["cy"]})
        for p_ in (a, b2):
            m_ = marks[side_of[next(k for k in side_of if (round(k[0], 3), round(k[1], 3)) == p_)]]
            counts[m_] = counts.get(m_, 0) - 1
        out.append(f"{mark} (ขั้น 2 ฐานรากร่วม): เสา ({a[0]:.2f}, {a[1]:.2f}) + ({b2[0]:.2f}, {b2[1]:.2f}) · "
                   f"{r['w']:.2f} × {r['l']:.2f} × {r['t']:.2f} ม. · " + " · ".join(r["notes"]))
    data["library"] = new_lib
    return out + notes


# -- columns and stumps: one section, the steel by load ------------------------------------------

def _ratio(m, spec, b_) -> float:
    dia = m.diagram
    if dia is None:
        return m.ratio
    mu = dia.Mu
    if hasattr(dia, "M0"):
        _sl, dl = C.column_magnifier(spec, b_, dia.Pu, dia.Lu)
        if dl >= 9.9:
            return 9.9
        mu = dia.M0 * dl
    return C.pm_ratio(C.pm_curve(spec, b_), mu, dia.Pu)


def design_columns(data, res) -> list:
    """The ground-floor columns and the stumps share one section (and the
    ground beams its width); every column point gets the least bars that
    pass, the points grouped into C1.. / PC1.. by those bars."""
    from core import wanic_building as B
    lib = B.library_of(data)
    b_ = res["basis"]
    E = B.elements(data)
    col0 = {(round(c["x"], 3), round(c["y"], 3)): c for c in E["columns"] if c.get("floor", 0) == 0}
    by_point = {}                                          # (x, y, role) → [members]
    for m in res["members"]:
        if m.group != "column" or m.diagram is None:
            continue
        try:
            xy = m.name.split("(")[1].split(")")[0]
            x, y = (round(float(v), 3) for v in xy.split(","))
        except (IndexError, ValueError):
            continue
        role = "PC" if "ตอม่อ" in m.name else "C"
        by_point.setdefault((x, y, role), []).append(m)
    if not by_point:
        return []
    cmark = next((c["mark"] for c in col0.values()), "C1")
    base_c = dict(lib.get(cmark) or lib.get("C1") or {})
    base_p = dict(lib.get("PC1") or {})
    b = max(float(base_c.get("b", 0.2)), float(base_p.get("b", 0.2)))
    for _grow in range(10):
        bars, ok = {}, True
        for (x, y, role), ms in by_point.items():
            spec0 = dict(base_p if role == "PC" else base_c, b=b, h=b)
            pick = None
            for n, d in BARS:
                As_ = n * math.pi * (d / 10) ** 2 / 4
                if As_ > RHO_MAX * b * b * 1e4 or As_ < 0.01 * b * b * 1e4:     # 1 % ≤ ρ ≤ 4 % (ACI 10.9)
                    continue
                if 4 * math.pi * (d / 10) ** 2 / 4 > 0 and (b * 100 - 2 * 4.0) < (n / 4 + 1) * (d / 10 + 2.5):
                    continue                               # the bars must fit with 2.5 cm gaps
                sp = dict(spec0, main=f"{n}-DB{d}")
                if all(_ratio(m, sp, b_) <= 0.98 for m in ms):  # 2 % margin: never on the edge
                    pick = (n * (d ** 2), n, d)
                    break
            if pick is None:
                ok = False
                break
            bars[(x, y, role)] = pick
        if ok:
            break
        b = round(b + SECTION_STEP, 2)
    else:
        return [f"เสา/ตอม่อ: แก้อัตโนมัติไม่ได้ (หน้าตัดเกิน {b * 100:.0f} ซม.) — ให้วิศวกรออกแบบเฉพาะ"]
    new_lib = dict(data.get("library") or {})
    lines = []
    for role, base, prefix in (("C", base_c, "C"), ("PC", base_p, "PC")):
        picks = sorted({v for k, v in bars.items() if k[2] == role})
        for old in [mk for mk, v in lib.items() if v.get("kind") == ("column" if role == "C" else "stump")
                    and mk not in (f"{prefix}1",)]:
            new_lib.pop(old, None)
        names = {}
        for i, (_a, n, d) in enumerate(picks, 1):
            mk = f"{prefix}{i}"
            new_lib[mk] = dict(base, **{k: v for k, v in (new_lib.get(mk) or {}).items()},
                               kind="column" if role == "C" else "stump", b=b, h=b, main=f"{n}-DB{d}")
            names[(n, d)] = mk
        cnt = {}
        for (x, y, r_), (_a, n, d) in bars.items():
            if r_ != role:
                continue
            _assign(data, x, y, role, names[(n, d)])
            cnt[names[(n, d)]] = cnt.get(names[(n, d)], 0) + 1
        for (n, d), mk in sorted(names.items(), key=lambda t: t[1]):
            lines.append(f"{mk} ({'ขั้น 3 ตอม่อ' if role == 'PC' else 'ขั้น 6 เสา'}): {b * 100:.0f}×{b * 100:.0f} ซม. "
                         f"เหล็กยืน {n}-DB{d} · {cnt.get(mk, 0)} ต้น")
    gb = [mk for mk, v in lib.items() if v.get("kind") == "beam" and mk.startswith("GB")]
    for mk in gb:                                          # the ground beams as wide as the columns
        if abs(float(lib[mk].get("b", 0.2)) - b) > 1e-6:
            new_lib[mk] = dict(new_lib.get(mk) or lib[mk], b=b)
            lines.append(f"{mk} (ขั้น 4 คานคอดิน): กว้าง {b * 100:.0f} ซม. เท่าเสา/ตอม่อ")
    data["library"] = new_lib
    return lines


# -- the whole loop ---------------------------------------------------------------------------

def failing(res) -> list:
    return sorted((m for m in res["members"] if not m.ok), key=lambda m: -m.ratio)


def design(data, rounds: int = 8) -> dict:
    """Change ``data`` until every member passes. Returns {"lines": what
    changed (last word per mark), "failing": what still fails, "rounds"}."""
    from core import wanic_advice as AD
    from core import wanic_building as B
    before = copy.deepcopy(B.library_of(data))
    words = {}
    res = C.analyse(data)
    n = 0
    for n in range(1, rounds + 1):
        for line in design_footings(data, res) + design_columns(data, C.analyse(data)):
            words[line.split(" ", 1)[0]] = line
        for line in AD.apply_mark_fixes(data, rounds=3):
            mk = line.split(" ", 1)[0]
            if mk not in words or not mk.startswith(("F", "C", "PC")):
                words[mk] = line
        res = C.analyse(data)
        if not failing(res):
            break
    after = B.library_of(data)
    changed = [mk for mk in after if before.get(mk) != after[mk]]
    lines = [words[mk] for mk in sorted(words) if mk in after and (mk in changed or mk not in before)]
    lines += [w for mk, w in words.items() if mk not in after]          # the stairs, and words for no mark
    return {"lines": lines, "failing": failing(res), "rounds": n, "res": res}
