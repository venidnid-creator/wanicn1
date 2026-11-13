# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""เขียนแบบอิสระ — columns, beams and walls from lines drawn in the model:
any straight, sloping (inclined) or curved chain of edges becomes a beam,
a vertical edge a column, a chain at floor level a wall (straight or
curved). They live in ``data["free"]``:

    {"beams":   [{"pts": [[x, y, z], …], "mark": "B1", "curved": bool, "w": kg/m}],
     "columns": [{"x", "y", "z0", "z1", "mark": "C1"}],
     "walls":   [{"pts": [[x, y], …], "z", "h", "t", "curved", "exterior"}]}

(metres, the building's own coordinates) and the model, the BOQ, the plans
and the calculation all read them from here."""
from __future__ import annotations

import math

TOL = 0.05                                   # m: a beam end on a column


# ---- from the selected edges ---------------------------------------------------------------

def chains_from_edges(edges) -> list:
    """The selected edges as separate chains, split where three or more
    meet: [{"pts": [(x, y, z), …], "closed", "curved"}]."""
    edges = [e for e in edges if hasattr(e, "v0") and hasattr(e, "v1")]
    adj: dict = {}
    for e in edges:
        adj.setdefault(e.v0, []).append(e)
        adj.setdefault(e.v1, []).append(e)
    used: set = set()

    def other(e, v):
        return e.v1 if e.v0 is v else e.v0

    def walk(v, e):
        verts, es = [v], []
        while True:
            used.add(e)
            es.append(e)
            v = other(e, v)
            verts.append(v)
            nxt = [x for x in adj[v] if x not in used]
            if len(adj[v]) != 2 or not nxt:
                return verts, es
            e = nxt[0]

    out = []
    starts = [v for v, es in adj.items() if len(es) != 2]
    for v in starts:
        for e in adj[v]:
            if e not in used:
                out.append(walk(v, e))
    for e in edges:                                   # closed loops
        if e not in used:
            out.append(walk(e.v0, e))
    res = []
    for verts, es in out:
        pts = [(round(p.position.x(), 4), round(p.position.y(), 4), round(p.position.z(), 4)) for p in verts]
        closed = len(pts) > 2 and math.dist(pts[0], pts[-1]) < 1e-6
        if closed:
            pts = pts[:-1]
        curved = any(getattr(e, "curve", None) is not None or getattr(e, "soft", False) for e in es)
        res.append({"pts": pts, "closed": closed, "curved": curved})
    return res


def is_vertical(p, q) -> bool:
    return abs(q[2] - p[2]) > 0.05 and math.hypot(q[0] - p[0], q[1] - p[1]) < 0.02


def add_from_chains(data, chains, kind="auto", mark=None, t=0.10, h=None, w_extra=0.0) -> dict:
    """Put the chains into ``data["free"]`` as ``kind`` (beam / column /
    wall; ``auto``: vertical → column, the rest → beam). Returns the counts."""
    free = dict(data.get("free") or {})
    beams, cols, walls = (list(free.get(k) or []) for k in ("beams", "columns", "walls"))
    n = {"beams": 0, "columns": 0, "walls": 0}
    if kind == "auto":                                # vertical pieces out of a chain → columns
        split = []
        for ch in chains:
            run = [ch["pts"][0]]
            for p, q in zip(ch["pts"], ch["pts"][1:]):
                if is_vertical(p, q):
                    if len(run) > 1:
                        split.append({"pts": run, "closed": False, "curved": ch["curved"]})
                    split.append({"pts": [p, q], "closed": False, "curved": False})
                    run = [q]
                else:
                    run.append(q)
            if len(run) > 1:
                split.append({"pts": run, "closed": ch["closed"] and len(run) == len(ch["pts"]),
                              "curved": ch["curved"]})
        chains = split
    for ch in chains:
        pts = ch["pts"]
        if len(pts) < 2:
            continue
        segs = list(zip(pts, pts[1:]))
        if kind == "column" or (kind == "auto" and all(is_vertical(p, q) for p, q in segs)):
            for p, q in segs:
                if is_vertical(p, q):
                    cols.append({"x": p[0], "y": p[1], "z0": min(p[2], q[2]), "z1": max(p[2], q[2]),
                                 "mark": mark or "C1"})
                    n["columns"] += 1
        elif kind == "wall":
            z = min(p[2] for p in pts)
            walls.append({"pts": [[p[0], p[1]] for p in pts] + ([[pts[0][0], pts[0][1]]] if ch["closed"] else []),
                          "z": z, "h": float(h or 0.0), "t": float(t), "curved": bool(ch["curved"]),
                          "exterior": False})
            n["walls"] += 1
        else:
            beams.append({"pts": [list(p) for p in pts] + ([list(pts[0])] if ch["closed"] else []),
                          "mark": mark or "B1", "curved": bool(ch["curved"]), "w": float(w_extra)})
            n["beams"] += 1
    data["free"] = {"beams": beams, "columns": cols, "walls": walls}
    return n


def free_of(data) -> dict:
    f = (data or {}).get("free") or {}
    return {"beams": [b for b in f.get("beams") or [] if len(b.get("pts") or []) >= 2],
            "columns": [c for c in f.get("columns") or [] if "x" in c],
            "walls": [w for w in f.get("walls") or [] if len(w.get("pts") or []) >= 2]}


# ---- geometry ------------------------------------------------------------------------------

def length3(pts) -> float:
    return sum(math.dist(p, q) for p, q in zip(pts, pts[1:]))


def length2(pts) -> float:
    return sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(pts, pts[1:]))


def describe_beam(b) -> str:
    pts = b["pts"]
    rise = abs(pts[-1][2] - pts[0][2]) if len(pts[0]) > 2 else 0.0
    kind = "คานโค้ง" if b.get("curved") else ("คานเอียง" if rise > 0.02 else "คาน")
    return kind


def column_points(data) -> list:
    """(x, y) of every column the building has — grid and free."""
    from core import wanic_building as B
    E = B.elements(data)
    pts = {(round(c["x"], 3), round(c["y"], 3)) for c in E["columns"]}
    pts |= {(round(float(c["x"]), 3), round(float(c["y"]), 3)) for c in free_of(data)["columns"]}
    return sorted(pts)


def supports_of(b, cols) -> list:
    """Indices of the beam's points that rest on a column; the two ends
    always count (on a column, a wall or another beam)."""
    pts = b["pts"]
    idx = {0, len(pts) - 1}
    for i, p in enumerate(pts):
        if any(math.hypot(p[0] - x, p[1] - y) <= TOL for x, y in cols):
            idx.add(i)
    return sorted(idx)


# ---- the model -----------------------------------------------------------------------------

def members(data) -> list:
    """[(group, kind)] for the 3D model."""
    from core import wanic_building as B
    lib = B.library_of(data)
    s = B.settings_of(data)
    f = free_of(data)
    out = []
    for i, b in enumerate(f["beams"]):
        spec = lib.get(b.get("mark"), lib["B1"])
        bw, bh = float(spec.get("b", 0.2)), float(spec.get("h", 0.4))
        name = f"{describe_beam(b)} (เขียนอิสระ) {b.get('mark')} {bw * 100:g}×{bh * 100:g} ซม. ยาว {length3(b['pts']):.2f} ม."
        g = B._member("structure", "beam", b.get("mark") or "B1", "rect", dict(b=B._mm(bw), h=B._mm(bh)),
                      [tuple(p) for p in b["pts"]], anchor="tc", ifc="IfcBeam", name=name,
                      info=[("ชนิด", f"{describe_beam(b)} ค.ส.ล. (เขียนอิสระ)"), ("เบอร์", b.get("mark")),
                            ("ขนาด", f"{bw * 100:g}×{bh * 100:g} ซม."), ("ยาว", f"{length3(b['pts']):.2f} ม."),
                            ("คอนกรีต", f"{bw * bh * length3(b['pts']):.3f} ลบ.ม."),
                            ("รายการ BOQ", "งานคอนกรีตโครงสร้าง (คาน)")])
        if g is not None:
            out.append((g, "beam"))
    for c in f["columns"]:
        spec = lib.get(c.get("mark"), lib["C1"])
        cb, ch = float(spec.get("b", 0.2)), float(spec.get("h", 0.2))
        z0, z1 = float(c["z0"]), float(c["z1"])
        g = B._member("structure", "column", c.get("mark") or "C1", "rect", dict(b=B._mm(cb), h=B._mm(ch)),
                      [(float(c["x"]), float(c["y"]), z0), (float(c["x"]), float(c["y"]), z1)], ifc="IfcColumn",
                      name=f"เสา (เขียนอิสระ) {c.get('mark')} {cb * 100:g}×{ch * 100:g} ซม. สูง {z1 - z0:.2f} ม.",
                      info=[("ชนิด", "เสา ค.ส.ล. (เขียนอิสระ)"), ("เบอร์", c.get("mark")),
                            ("ตำแหน่ง", f"({float(c['x']):.2f}, {float(c['y']):.2f})"),
                            ("คอนกรีต", f"{cb * ch * (z1 - z0):.3f} ลบ.ม.")])
        if g is not None:
            out.append((g, "column"))
    for wl in f["walls"]:
        t = float(wl.get("t") or 0.10)
        h = float(wl.get("h") or 0.0) or float(s["floor_h"]) - float(lib["B1"].get("h", 0.4))
        z = float(wl.get("z") or 0.0)
        L = length2(wl["pts"])
        kind = "ผนังโค้ง" if wl.get("curved") else "ผนัง"
        g = B._member("structure", "wall", f"{kind} (เขียนอิสระ)", "rect", dict(b=B._mm(t), h=B._mm(h)),
                      [(p[0], p[1], z) for p in wl["pts"]], anchor="bc", ifc="IfcWall",
                      name=f"{kind} (เขียนอิสระ) หนา {t * 100:g} ซม. สูง {h:.2f} ม. ยาว {L:.2f} ม.",
                      info=[("ชนิด", f"{kind} ก่ออิฐฉาบปูน (เขียนอิสระ)"), ("ยาว", f"{L:.2f} ม."),
                            ("สูง", f"{h:.2f} ม."), ("พื้นที่", f"{L * h:.2f} ตร.ม."),
                            ("รายการ BOQ", "หมวด 6 งานผนัง/ฉาบ")])
        if g is not None:
            out.append((g, "wall"))
    return out


# ---- the calculation ------------------------------------------------------------------------

def analyse_free(data, b_, out, col_load, col_lv) -> list:
    """Free beams and columns into the calculation: each beam continuous
    over its supports, the load per horizontal metre (its own weight ÷ cos
    on a slope, the extra load, a free wall standing on it), the reactions
    to the columns below; free columns checked for axial load + minimum
    eccentricity. Returns the free-column loads [((x, y), Pu)]."""
    from core import wanic_building as B
    from core import wanic_calc as C
    lib = B.library_of(data)
    s = B.settings_of(data)
    D_, L_ = C.factors(b_)
    conc = b_["concrete"]
    f = free_of(data)
    cols = column_points(data)
    free_load: dict = {}
    for i, b in enumerate(f["beams"]):
        mark = b.get("mark") or "B1"
        spec = lib.get(mark, lib["B1"])
        bw, bh = float(spec.get("b", 0.2)), float(spec.get("h", 0.4))
        pts = b["pts"]
        sup = supports_of(b, cols)
        spans = []
        for a, c in zip(sup, sup[1:]):
            seg = pts[a:c + 1]
            Lh = length2(seg) or 1e-3
            L3 = length3(seg)
            w = D_ * bw * bh * conc * L3 / Lh + (D_ * float(b.get("w") or 0.0))
            for wl in f["walls"]:                      # a free wall standing on this beam
                if all(any(math.hypot(p[0] - q[0], p[1] - q[1]) < TOL for q in seg) for p in wl["pts"][:2]):
                    hh = float(wl.get("h") or 0.0) or float(s["floor_h"]) - bh
                    w += D_ * b_["wall_kg_m2"] * hh
            spans.append(C.Span(Lh, w))
        res = C.solve_beam(spans)
        cap = C.beam_capacity(spec, b_, b_["fc"])
        sdm = b_["method"] == "SDM"
        res.caps = {"M+": cap["bot"], "M-": cap["top"], "V": cap["V"], "Vc": cap["Vc"],
                    "lab_M": "φMn" if sdm else "Ma", "lab_V": "φVn" if sdm else "Va",
                    "lab_Vc": "φVc" if sdm else "vc·bd"}
        res.mark, res.spec, res.level, res.axis, res.line = mark, spec, 1, "x", 0.0
        res.ground, res.z, res.free = False, float(pts[0][2]), True
        r = max(res.Mmax / cap["bot"] if cap["bot"] else 9.9,
                -res.Mmin / cap["top"] if cap["top"] and res.Mmin < 0 else 0.0,
                res.Vmax / cap["V"] if cap["V"] else 9.9)
        kind = describe_beam(b)
        note = f"w = {', '.join(f'{sp.w:,.0f}' for sp in spans)} กก./ม. (ต่อเมตรแนวราบ)"
        if b.get("curved"):
            note += " · คานโค้งมีแรงบิด — ให้วิศวกรตรวจแรงบิดและเหล็กปลอกปิด"
        out.append(C.Member("beam", f"{kind}อิสระ {mark} #{i + 1} · ยาว {length3(pts):.2f} ม. · {len(spans)} ช่วง",
                            f"Mu+ {res.Mmax:,.0f} · Mu− {max(0.0, -res.Mmin):,.0f} กก.-ม. · Vu {res.Vmax:,.0f} กก.",
                            f"φMn ล่าง {cap['bot']:,.0f} · บน {cap['top']:,.0f} · φVn {cap['V']:,.0f}",
                            r, note, res, qty=max(sp.w for sp in spans) / ((D_ + L_) / 2.0),
                            qty_unit="กก. ต่อเมตรของคาน"))
        for idx, R_ in zip(sup, res.reactions):
            p = pts[idx]
            k_ = next(((x, y) for x, y in cols if math.hypot(p[0] - x, p[1] - y) <= TOL), None)
            if k_ is None:
                continue
            free_load[k_] = free_load.get(k_, 0.0) + R_
            col_load[k_] = col_load.get(k_, 0.0) + R_
            col_lv[(k_, 1)] = col_lv.get((k_, 1), 0.0) + R_
    loads = []
    for c in f["columns"]:
        spec = lib.get(c.get("mark"), lib["C1"])
        k_ = (round(float(c["x"]), 3), round(float(c["y"]), 3))
        Hc = float(c["z1"]) - float(c["z0"])
        Pu = free_load.get(k_, 0.0) + D_ * float(spec.get("b", 0.2)) * float(spec.get("h", 0.2)) * conc * Hc
        hh = max(float(spec.get("b", 0.2)), float(spec.get("h", 0.2)))
        Mu = Pu * (0.015 + 0.03 * hh)
        if b_["method"] == "SDM":
            curve = C.pm_curve(spec, b_)
            r = C.pm_ratio(curve, Mu, Pu)
            dia = C.PMResult(curve, Mu, Pu)
            capt = "ตรวจด้วยแผนภาพ P-M"
        else:
            cap = C.column_capacity(spec, b_, b_["fc"])
            r, dia, capt = Pu / cap if cap else 9.9, None, f"P ยอมให้ {cap / 1000:,.2f} ตัน"
        out.append(C.Member("column", f"{c.get('mark') or 'C1'} อิสระ ที่ ({k_[0]:.2f}, {k_[1]:.2f}) สูง {Hc:.2f} ม.",
                            f"Pu = {Pu / 1000:,.2f} ตัน · Mu = {Mu:,.0f} กก.-ม.", capt, r,
                            "รับแรงจากคานอิสระ — ฐานรากใต้เสาใช้เบอร์ F1 (ตรวจในตารางฐานราก)", dia,
                            qty=Pu / ((D_ + L_) / 2.0) / 1000.0, qty_unit="ตัน ต่อเสา 1 ต้น"))
        loads.append((k_, Pu))
    return loads
