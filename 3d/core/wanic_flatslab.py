# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""พื้นไร้คาน (Flat Slab / Flat Plate) with or without drop panels — the
Direct Design Method (ACI 318 / วสท. 011008):

- the least thickness: ln/33 (interior) / ln/30 (exterior) without drop
  panels, ln/36 / ln/33 with them;
- the total static moment of each span Mo = wu·l2·ln²/8 (ln clear, ≥ 0.65 l1);
- shared out along the span: interior span −0.65 / +0.35; the end span of a
  flat plate without edge beams −0.26 (exterior) / +0.52 / −0.70 (interior);
- across: the column strip (half the shorter span wide) takes 75 % of the
  interior negative, 60 % of the positive and 100 % of the exterior
  negative; the middle strip the rest;
- the bars: As from Mu/(φ fy (d − a/2)) (SDM) or M/(fs·j·d) (WSD), not less
  than 0.0018 b h, spaced ≤ 2h and ≤ 45 cm;
- punching shear round each column (d/2 off its face) and round the drop
  panel (d/2 off its edge, through the thinner slab): interior 4 sides,
  edge 3, corner 2 — Vc = 1.06 √fc′ b0 d (SDM, φ 0.85) or 0.53 √fc′ (WSD).

Units: m, kg, cm for sections, ksc."""
from __future__ import annotations

import math

DEFAULTS = {"t": 0.0, "drop": True, "drop_t": 0.10, "col": 0.0, "finish": 0.0, "ll": 0.0, "bar": 12,
            "cover": 0.025, "x": [], "y": []}


def spans_of(data) -> tuple:
    """The grid spacings (m): data["grid"] or the plan's column lines."""
    g = (data or {}).get("grid") or {}
    if g.get("x") and g.get("y"):
        return list(map(float, g["x"])), list(map(float, g["y"]))
    from core import wanic_building as B
    from core import wanic_rc as R
    xs, ys = R.grid_axes(B.elements(data or {}))
    sx = [b - a for a, b in zip(xs, xs[1:])]
    sy = [b - a for a, b in zip(ys, ys[1:])]
    return (sx or [5.0, 5.0]), (sy or [5.0, 5.0])


def params_of(data) -> dict:
    from core import wanic_building as B
    from core import wanic_calc as C
    p = {**DEFAULTS, **((data or {}).get("flatslab") or {})}
    b_ = C.basis(data or {})
    sx, sy = spans_of(data)
    if not p["x"]:
        p["x"] = sx
    if not p["y"]:
        p["y"] = sy
    if not p["col"]:
        p["col"] = max(0.30, float(B.library_of(data or {})["C1"]["b"]))
    if not p["ll"]:
        p["ll"] = float(b_["ll_floor"])
    if not p["finish"]:
        p["finish"] = float(b_["finish"])
    if not p["t"]:
        p["t"] = min_thickness(p)["need"]
    return p


def min_thickness(p) -> dict:
    """The least slab thickness (m), rounded up to 1 cm, at least 12 cm
    (flat plate) / 10 cm (with drop panels)."""
    ln = max(max(p["x"]), max(p["y"])) - p["col"]
    drop = bool(p["drop"])
    ext = ln / (33 if drop else 30)
    inn = ln / (36 if drop else 33)
    need = math.ceil(max(ext, inn, 0.10 if drop else 0.12) * 100) / 100
    return {"ln": ln, "exterior": ext, "interior": inn, "need": need}


def _as(M, b, h, d, fc, fy, method):
    """Steel area (cm²) for M (kg·m) on a strip b (m), h, d (m)."""
    bc, dc = b * 100, d * 100
    Mc = abs(M) * 100
    if method == "SDM":
        phi = 0.90
        Rn = Mc / (phi * bc * dc * dc)
        disc = 1 - 2 * Rn / (0.85 * fc)
        if disc < 0:
            return float("inf")                                    # the section is too thin
        rho = 0.85 * fc / fy * (1 - math.sqrt(disc))
        As = rho * bc * dc
    else:
        fs = min(0.5 * fy, 1700.0)
        As = Mc / (fs * 0.875 * dc)
    return max(As, 0.0018 * bc * h * 100)


def _bars(As, b, h, bar):
    """'DB12 @ 0.20' for As (cm²) over the strip b (m)."""
    a1 = math.pi * (bar / 10) ** 2 / 4
    if not math.isfinite(As):
        return "หนาไม่พอ", 0.0, 0.0
    n = max(1, math.ceil(As / a1))
    s = b / n
    s = min(s, 2 * h, 0.45)
    s = math.floor(s * 40) / 40                                    # down to 2.5 cm
    txt = f"{s:.3f}"
    if txt.endswith("0"):
        txt = txt[:-1]
    return f"DB{bar} @ {txt}", a1 * b / s if s else 0.0, s


def design(p: dict, basis: dict) -> dict:
    method = basis["method"]
    fc, fy = float(basis["fc"]), float(basis.get("fy_db", 4000.0))
    D_, L_ = (1.4, 1.7) if method == "SDM" else (1.0, 1.0)
    h = float(p["t"])
    dead = 2400 * h + float(p["finish"])
    wu = D_ * dead + L_ * float(p["ll"])
    bar = int(p["bar"])
    d = h - float(p["cover"]) - bar / 1000 / 2 - bar / 1000 / 2      # the inner layer, on average
    c = float(p["col"])
    out = {"wu": wu, "dead": dead, "h": h, "d": d, "dirs": [], "punch": [], "method": method,
           "thick": min_thickness(p)}
    for name, l1s, l2s in (("แนวแกนตัวเลข (X)", p["x"], p["y"]), ("แนวแกนตัวอักษร (Y)", p["y"], p["x"])):
        l2 = max(l2s)                                             # the widest frame (the design strip)
        cs = min(min(l1s), l2) / 2                               # column strip width
        ms = l2 - cs
        rows = []
        n = len(l1s)
        for i, l1 in enumerate(l1s):
            ln = max(l1 - c, 0.65 * l1)
            Mo = wu * l2 * ln * ln / 8
            end = n == 1 or i in (0, n - 1)
            if n == 1:
                coef = {"ลบซ้าย": 0.26, "บวก": 0.52, "ลบขวา": 0.26}
            elif end:
                coef = {"ลบซ้าย": 0.26, "บวก": 0.52, "ลบขวา": 0.70} if i == 0 else \
                    {"ลบซ้าย": 0.70, "บวก": 0.52, "ลบขวา": 0.26}
            else:
                coef = {"ลบซ้าย": 0.65, "บวก": 0.35, "ลบขวา": 0.65}
            for loc, k in coef.items():
                M = k * Mo
                ext_neg = loc != "บวก" and k == 0.26
                share = 1.0 if ext_neg else (0.60 if loc == "บวก" else 0.75)
                for strip, frac, width in (("แถบเสา", share, cs), ("แถบกลาง", 1 - share, ms)):
                    Ms = M * frac
                    # the drop panel thickens the column strip's negative section
                    hh = h + (float(p["drop_t"]) if (p["drop"] and strip == "แถบเสา" and loc != "บวก") else 0.0)
                    dd = d + (hh - h)
                    As = _as(Ms, width, hh, dd, fc, fy, method)
                    txt, As_used, s = _bars(As, width, hh, bar)
                    rows.append({"span": i + 1, "l1": l1, "Mo": Mo, "loc": loc, "strip": strip, "k": k * frac,
                                 "M": Ms, "b": width, "As": As, "bars": txt, "As_used": As_used,
                                 "h": hh, "ok": math.isfinite(As) and As_used >= As - 1e-6})
        out["dirs"].append({"name": name, "l2": l2, "cs": cs, "ms": ms, "rows": rows})
    # punching shear at an interior, an edge and a corner column
    lx, ly = max(p["x"]), max(p["y"])
    vfac = 1.06 if method == "SDM" else 0.53
    phi = 0.85 if method == "SDM" else 1.0
    drop_w = (lx / 3, ly / 3) if p["drop"] else None
    for kind, sides, frac in (("เสาใน", 4, 1.0), ("เสาขอบ", 3, 0.5), ("เสามุม", 2, 0.25)):
        A = lx * ly * frac
        cases = []
        dd = d + (float(p["drop_t"]) if p["drop"] else 0.0)
        cases.append(("รอบเสา", c, dd))
        if drop_w:
            cases.append(("รอบแผ่นหนา (Drop)", min(drop_w), d))
        for where, size, depth in cases:
            side = size + depth
            b0 = {4: 4 * side, 3: 2 * (size + depth / 2) + side, 2: 2 * (size + depth / 2)}[sides]
            crit = side * side if sides == 4 else (side * (size + depth / 2) if sides == 3 else (size + depth / 2) ** 2)
            Vu = wu * max(A - crit, 0.0)
            Vc = phi * vfac * math.sqrt(fc) * b0 * 100 * depth * 100
            out["punch"].append({"col": kind, "where": where, "b0": b0, "d": depth, "Vu": Vu, "Vc": Vc,
                                 "ratio": Vu / Vc if Vc else 9.9})
    out["drop_w"] = drop_w
    return out


def design_of(data):
    from core import wanic_calc as C
    p = params_of(data)
    return p, design(p, C.basis(data or {}))
