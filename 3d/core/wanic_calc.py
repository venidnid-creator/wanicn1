# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""คำนวณโครงสร้าง: the building's loads taken down from the roof to the
piles, with the forces in every member, its shear and moment diagrams, and
a capacity check.

The path of the loads, top down::

    roof covering → purlins (แป) → rafters (จันทัน) → ridge / wall plate
    (อกไก่ / อะเส) and the trusses' posts (ดั้ง) → ring beams → columns
    slabs (two-way / one-way) + walls + self weight → beams → columns
    columns, floor by floor → stumps → footings → soil or piles

Methods (the defaults agreed with the developer; all can be changed):

- reinforced concrete: strength design (SDM, วสท. 011008), U = 1.4D + 1.7L,
  φ = 0.90 bending, 0.85 shear, 0.70 tied columns; working stress (WSD) as
  an option (n = 1 on the loads, the WSD allowables);
- steel and timber roof members: allowable stress (ASD) — Fb = 0.60 Fy for
  steel (SS400, Fy 2 450 ksc), Fb = 120 ksc for hardwood, deflection L/180;
- continuous beams: stiffness method on the column lines (pinned at the
  ends, continuous over the inner columns), uniform loads per span;
- footings: allowable soil pressure, or piles at a safe load each.

This is an engineering aid: every result must be checked and signed by a
licensed civil engineer (วิศวกรโยธา) before it is built.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from core import wanic_building as B
from core import wanic_rc as R

#: The design basis (หน่วย: kg, m, ksc = kg/cm²).
DEFAULTS = {
    "method": "SDM",                 # or "WSD"
    "fc": 240.0,                     # fc' cylinder, ksc
    "fy_db": 4000.0, "fy_rb": 2400.0,
    "fy_steel": 2450.0,              # SS400
    "fb_timber": 120.0, "e_timber": 100000.0,
    "e_steel": 2.04e6,
    "concrete": 2400.0,              # kg/m³
    "ll_floor": 150.0,               # residential, kg/m²
    "ll_roof": 30.0,
    "wind": 50.0,                    # kg/m² on the roof (uplift / pressure, informative)
    "finish": 50.0,                  # floor finish + ceiling, kg/m²
    "wall_kg_m2": 180.0,             # half-brick wall plastered both sides
    "soil": 10.0,                    # allowable soil pressure, t/m²
    "pile_cap": 8.0,                 # safe load per pile, t
    "defl": 180.0,                   # roof member deflection limit L/…
    # the booklet's signature (editable in «ค่าที่ใช้ออกแบบ…»)
    "engineer": "นายเวนิช ธัมมะวงษ์", "qualification": "วิศวกรสำรวจ",
    "project": "", "owner": "", "place": "",
}


#: ชุดค่ามาตรฐาน (preset) of the design basis
PRESETS = {
    "sdm": ("วสท. 011008 วิธีกำลัง (SDM) — fc′ 240 · SD40 · U = 1.4D + 1.7L",
            {"method": "SDM", "fc": 240.0, "fy_db": 4000.0, "fy_rb": 2400.0}),
    "wsd": ("ข้อบัญญัติ กทม. 2522 หน่วยแรงใช้งาน (WSD) — fc′ 173 · SD30 · fs ≤ 1,500",
            {"method": "WSD", "fc": 173.0, "fy_db": 3000.0, "fy_rb": 2400.0}),
}
#: กฎกระทรวง ฉบับที่ 6 (2527) ข้อ 15 — live load by use (kg/m²)
LIVE_LOADS = [("ที่พักอาศัย โรงเรียนอนุบาล ห้องน้ำ-ห้องส้วม", 150.0),
              ("ห้องแถว ตึกแถวพักอาศัย อาคารชุด หอพัก โรงแรม", 200.0),
              ("สำนักงาน ธนาคาร", 250.0),
              ("อาคารพาณิชย์ โรงเรียน มหาวิทยาลัย โรงพยาบาล / ห้องโถง บันได ทางเดิน (อาคารชุด สำนักงาน)", 300.0),
              ("ตลาด ห้างสรรพสินค้า หอประชุม ภัตตาคาร ห้องประชุม ที่จอดรถยนต์นั่ง", 400.0),
              ("คลังสินค้า โรงกีฬา พิพิธภัณฑ์ โรงงาน โรงพิมพ์ / ห้องโถง บันได ทางเดิน (ตลาด ห้าง)", 500.0),
              ("ห้องเก็บหนังสือของห้องสมุด", 600.0),
              ("ที่จอดรถหรือเก็บรถยนต์บรรทุกเปล่า", 800.0)]


def fy_of(bar, b_) -> float:
    """The bar's yield strength from the design basis (SD30 / SD40, SR24)."""
    if bar is None:
        return float(b_.get("fy_db", 4000.0))
    return float(b_.get("fy_rb" if bar.kind == "RB" else "fy_db", bar.fy))


def fs_of(bar, b_) -> float:
    """WSD allowable steel stress: 0.5 fy, not over 1,700 ksc."""
    return min(0.5 * fy_of(bar, b_), 1700.0)


def basis(data) -> dict:
    return {**DEFAULTS, **((data or {}).get("calc") or {})}


def factors(b) -> tuple:
    return (1.4, 1.7) if b["method"] == "SDM" else (1.0, 1.0)


# ---- section properties ------------------------------------------------------------

def section(label: str) -> dict:
    """{"A" m², "I" m⁴ (strong axis), "S" m³, "kg_m", "timber"} of a roof member."""
    from core import wanic_profiles as P
    fam, prm = B.steel_lookup(label)
    outer, holes = P.profile_outline(fam, prm)

    def props(poly):
        a = cx = cy = ixx = 0.0
        n = len(poly)
        for i in range(n):
            x0, y0 = poly[i]
            x1, y1 = poly[(i + 1) % n]
            cr = x0 * y1 - x1 * y0
            a += cr
            cy += (y0 + y1) * cr
            ixx += (y0 * y0 + y0 * y1 + y1 * y1) * cr
        a /= 2.0
        return a, cy / 6.0, ixx / 12.0
    A = Sy = Ixx = 0.0
    for poly, sg in [(outer, 1)] + [(h, 1) for h in holes]:
        a, sy, ix = props(poly)
        A += a
        Sy += sy
        Ixx += ix
    A = abs(A)
    yc = Sy / A if A else 0.0
    Ixx = abs(Ixx) - A * yc * yc
    ys = [y for _, y in outer]
    c = max(max(ys) - yc, yc - min(ys)) or 1e-6
    timber = B.is_timber(label)
    return {"A": A, "I": abs(Ixx), "S": abs(Ixx) / c, "kg_m": A * (800.0 if timber else 7850.0),
            "timber": timber, "label": label}


def tile_weight(s) -> float:
    """kg/m² of the covering (on the slope), from its name."""
    from core import wanic_catalog as CAT
    name = (CAT.ROOF_TILES.get(s.get("tile", ""), {}) or {}).get("name", "")
    if "เมทัลชีท" in name or "เหล็ก" in name:
        return 6.0
    if "ดินเผา" in name or "เซรามิก" in name:
        return 55.0
    if "คอนกรีต" in name:
        return 50.0
    return 20.0                                   # fibre cement and the like


# ---- beams: the continuous-beam solver ---------------------------------------------------

@dataclass
class Span:
    L: float
    w: float                       # uniform load, kg/m (factored)
    P: list = field(default_factory=list)   # point loads (a, kg)
    U: list = field(default_factory=list)   # part-length uniform loads (a, b, kg/m)
    cant: str = ""                 # "L" / "R": a cantilever (free at the outer end)


@dataclass
class BeamResult:
    spans: list
    xs: list                       # stations along the whole beam (m)
    V: list                        # shear, kg
    M: list                        # moment, kg·m (sagging +)
    reactions: list                # at each support, kg
    Mmax: float = 0.0
    Mmin: float = 0.0
    Vmax: float = 0.0
    supports: list = field(default_factory=list)   # x of each support (m)


def _span_loads(sp):
    """(total, moment about the left end) of a span's loads."""
    tot = sp.w * sp.L + sum(P for _a, P in sp.P) + sum(w * (b - a) for a, b, w in sp.U)
    mom = sp.w * sp.L ** 2 / 2 + sum(P * a for a, P in sp.P) + sum(w * (b - a) * (a + b) / 2 for a, b, w in sp.U)
    return tot, mom


def _fem(sp):
    """Fixed-end moments (left, right) of a span under all its loads; the
    part-length loads by integrating the point-load formula."""
    L = sp.L
    fl = sp.w * L * L / 12.0
    fr = -fl
    pts = list(sp.P)
    for a, b, w in sp.U:
        k = 40
        h = (b - a) / k
        pts += [(a + h * (i + 0.5), w * h) for i in range(k)]
    for a, P in pts:
        b = L - a
        fl += P * a * b * b / (L * L)
        fr -= P * a * a * b / (L * L)
    return fl, fr


def _shear_moment(sp, x, Rl, ml):
    """V and M at x along a span from its left reaction and end moment."""
    v = Rl - sp.w * x - sum(P for a, P in sp.P if a < x - 1e-9)
    mm = -ml + Rl * x - sp.w * x * x / 2 - sum(P * (x - a) for a, P in sp.P if a < x)
    for a, b, w in sp.U:
        e = min(max(x, a), b)
        if e > a:
            v -= w * (e - a)
            mm -= w * (e - a) * (x - (a + e) / 2)
    return v, mm


def _stations(sp, n) -> list:
    """n+1 stations along a span; two of them meet at each point load so
    the shear diagram steps there (the count stays n+1)."""
    st = [sp.L * k / n for k in range(n + 1)]
    used = set()
    for a, _P in sorted(sp.P):
        if not (0 < a < sp.L) or n < 4:
            continue
        k = min(max(round(a / sp.L * n), 1), n - 2)
        if k in used or k + 1 in used or k - 1 in used:
            continue
        st[k], st[k + 1] = a, a + 1e-6
        used |= {k, k + 1}
    return st


def solve_beam(spans: list, fixed_ends=(False, False), n=24) -> BeamResult:
    """A continuous beam over its supports: stiffness method on the
    rotations (supports do not settle); uniform, part-length uniform and
    point loads per span; a first span marked cant "L" or a last one
    marked "R" is a cantilever (its moment is known, it adds no support).
    Returns the shear and moment along it and the support reactions."""
    lc = spans[0] if spans and spans[0].cant == "L" else None
    rc = spans[-1] if len(spans) > (1 if lc else 0) and spans[-1].cant == "R" else None
    inner = spans[(1 if lc else 0):(len(spans) - (1 if rc else 0))]
    k = len(inner)
    fem = [_fem(sp) for sp in inner]
    ndof = k + 1
    K = [[0.0] * ndof for _ in range(ndof)]
    F = [0.0] * ndof
    EI = 1.0
    for i, sp in enumerate(inner):
        L = sp.L
        kk = [[4 * EI / L, 2 * EI / L], [2 * EI / L, 4 * EI / L]]
        for a in range(2):
            for b in range(2):
                K[i + a][i + b] += kk[a][b]
        F[i] -= fem[i][0]
        F[i + 1] -= fem[i][1]
    # a cantilever hands its support a known moment (hogging Mc)
    Mc_l = Mc_r = 0.0
    if lc is not None:
        tot, mom = _span_loads(lc)
        Mc_l = tot * lc.L - mom                      # about its right (built-in) end
        F[0] += Mc_l
    if rc is not None:
        _tot, mom = _span_loads(rc)
        Mc_r = mom                                   # about its left (built-in) end
        F[ndof - 1] -= Mc_r
    free = [j for j in range(ndof)
            if k and not ((j == 0 and fixed_ends[0] and lc is None) or
                          (j == ndof - 1 and fixed_ends[1] and rc is None))]
    A = [[K[r][c] for c in free] + [F[r]] for r in free]
    m = len(free)
    for c in range(m):
        piv = max(range(c, m), key=lambda r: abs(A[r][c]))
        A[c], A[piv] = A[piv], A[c]
        for r in range(m):
            if r != c and A[c][c]:
                f = A[r][c] / A[c][c]
                A[r] = [A[r][j] - f * A[c][j] for j in range(m + 1)]
    th = [0.0] * ndof
    for idx, j in enumerate(free):
        th[j] = A[idx][m] / A[idx][idx] if A[idx][idx] else 0.0
    xs, V, M = [], [], []
    reactions = [0.0] * ndof
    x0 = 0.0
    supports = []
    if lc is not None:
        tot, _mom = _span_loads(lc)
        for x in _stations(lc, n):
            v, mm = _shear_moment(lc, x, 0.0, 0.0)
            xs.append(x)
            V.append(v)
            M.append(mm)
        reactions[0] += tot
        x0 = lc.L
    for i, sp in enumerate(inner):
        L = sp.L
        ml = fem[i][0] + 4 * EI / L * th[i] + 2 * EI / L * th[i + 1]     # end moments
        mr = fem[i][1] + 2 * EI / L * th[i] + 4 * EI / L * th[i + 1]
        tot, mom_r = _span_loads(sp)
        Rr = (mom_r - ml - mr) / L
        Rl = tot - Rr
        reactions[i] += Rl
        reactions[i + 1] += Rr
        supports.append(x0)
        for x in _stations(sp, n):
            v, mm = _shear_moment(sp, x, Rl, ml)
            xs.append(x0 + x)
            V.append(v)
            M.append(mm)
        x0 += L
    supports.append(x0)
    if rc is not None:
        tot, _mom = _span_loads(rc)
        reactions[-1] += tot
        for x in _stations(rc, n):
            v, mm = _shear_moment(rc, x, tot, Mc_r)
            xs.append(x0 + x)
            V.append(v)
            M.append(mm)
    return BeamResult(spans, xs, V, M, reactions, max(M) if M else 0.0, min(M) if M else 0.0,
                      max((abs(v) for v in V), default=0.0), supports)


# ---- RC section design (SDM / WSD) ---------------------------------------------------------

def beam_capacity(spec: dict, b_: dict, fc: float) -> dict:
    """φMn for the bottom and top bars, φVn with the stirrups, kg·m / kg."""
    bw, h = float(spec["b"]), float(spec["h"])
    d = h - R.COVER["beam"] - 0.006 - 0.006
    out = {}
    for key in ("bot", "top"):
        bar = R.parse_bar(spec.get(key))
        if not bar or not bar.n:
            out[key] = 0.0
            continue
        As = bar.n * bar.area                       # cm²
        fy = fy_of(bar, b_)
        if b_["method"] == "SDM":
            a = As * fy / (0.85 * fc * bw * 100)    # cm
            Mn = As * fy * (d * 100 - a / 2) / 100  # kg·m
            out[key] = 0.90 * Mn
        else:                                       # WSD: fs = 0.5 fy ≤ 1,700 ksc, j ≈ 0.875
            out[key] = As * fs_of(bar, b_) * 0.875 * d * 100 / 100
    st = R.parse_bar(spec.get("stir"))
    vc = (0.53 if b_["method"] == "SDM" else 0.29) * math.sqrt(fc) * bw * 100 * d * 100
    vs = 0.0
    if st and st.s:
        vs = 2 * st.area * (fy_of(st, b_) if b_["method"] == "SDM" else fs_of(st, b_)) * d * 100 / (st.s * 100)
    out["V"] = (0.85 if b_["method"] == "SDM" else 1.0) * (vc + vs)
    out["Vc"] = (0.85 if b_["method"] == "SDM" else 1.0) * vc
    out["d"] = d
    return out


def column_capacity(spec: dict, b_: dict, fc: float) -> float:
    """φPn (kg) of a tied column, axial only (the usual check of a house column)."""
    b, h = float(spec["b"]), float(spec["h"])
    Ag = b * h * 1e4
    bar = R.parse_bar(spec.get("main"))
    Ast = bar.n * bar.area if bar and bar.n else 0.0
    fy = fy_of(bar, b_)
    if b_["method"] == "SDM":
        return 0.80 * 0.70 * (0.85 * fc * (Ag - Ast) + fy * Ast)
    return 0.85 * (0.25 * fc * Ag + 0.40 * fy * Ast)


# ---- slabs: the coefficient method ---------------------------------------------------------

#: วสท./ACI 318-63 Method 2 — the largest short-span coefficient (negative at a
#: continuous edge, positive at mid-span, negative at a discontinuous edge) for
#: m = S/L of 1.0 0.9 0.8 0.7 0.6 0.5, by the number of discontinuous edges.
SLAB_COEF = {
    0: [(0.033, 0.025, 0.0), (0.040, 0.030, 0.0), (0.048, 0.036, 0.0), (0.055, 0.041, 0.0),
        (0.063, 0.047, 0.0), (0.083, 0.062, 0.0)],
    1: [(0.041, 0.031, 0.021), (0.048, 0.036, 0.024), (0.055, 0.041, 0.027), (0.062, 0.047, 0.031),
        (0.069, 0.052, 0.035), (0.085, 0.064, 0.042)],
    2: [(0.049, 0.037, 0.025), (0.057, 0.043, 0.028), (0.064, 0.048, 0.032), (0.071, 0.054, 0.036),
        (0.078, 0.059, 0.039), (0.090, 0.068, 0.045)],
    3: [(0.058, 0.044, 0.029), (0.066, 0.050, 0.033), (0.074, 0.056, 0.037), (0.082, 0.062, 0.041),
        (0.090, 0.068, 0.045), (0.098, 0.074, 0.049)],
    4: [(0.0, 0.050, 0.033), (0.0, 0.057, 0.038), (0.0, 0.064, 0.043), (0.0, 0.072, 0.047),
        (0.0, 0.080, 0.053), (0.0, 0.083, 0.055)],
}


def slab_moment(m: float, disc: int) -> float:
    """The governing coefficient C (M = C w S²) for m = S/L, interpolated."""
    rows = SLAB_COEF[max(0, min(4, disc))]
    ms = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]
    m = max(0.5, min(1.0, m))
    for i in range(5):
        if ms[i + 1] - 1e-9 <= m <= ms[i] + 1e-9:
            f = (ms[i] - m) / 0.1
            return max(a + (b - a) * f for a, b in zip(rows[i], rows[i + 1]))
    return max(rows[-1])


def discontinuous_edges(rm, rooms) -> int:
    """How many of a room's four edges have no room on the other side."""
    x0, y0, x1, y1 = rm["x"], rm["y"], rm["x"] + rm["w"], rm["y"] + rm["d"]
    n = 0
    for side in ("l", "r", "b", "t"):
        cont = False
        for o in rooms:
            if o is rm:
                continue
            ox0, oy0, ox1, oy1 = o["x"], o["y"], o["x"] + o["w"], o["y"] + o["d"]
            if side in ("l", "r"):
                edge = x0 if side == "l" else x1
                other = ox1 if side == "l" else ox0
                if abs(edge - other) < 1e-6 and min(y1, oy1) - max(y0, oy0) > 0.5 * (y1 - y0):
                    cont = True
            else:
                edge = y0 if side == "b" else y1
                other = oy1 if side == "b" else oy0
                if abs(edge - other) < 1e-6 and min(x1, ox1) - max(x0, ox0) > 0.5 * (x1 - x0):
                    cont = True
        n += 0 if cont else 1
    return n


# ---- columns: axial load and moment (P-M) ---------------------------------------------------

def pm_curve(spec: dict, b_: dict, steps: int = 40) -> list:
    """The column's design interaction curve [(φMn kg·m, φPn kg)…] about
    its stronger axis: strain compatibility, the bars half on each face."""
    b, h = float(spec["b"]), float(spec["h"])
    bar = R.parse_bar(spec.get("main"))
    fc = b_["fc"]
    n_ = bar.n if bar and bar.n else 4
    As1 = (n_ / 2) * (bar.area if bar else 1.13)          # cm², each face
    fy = fy_of(bar, b_)
    Es = 2.04e6
    B_, H_ = b * 100, h * 100
    dp = (R.COVER["column"] + 0.006 + (bar.d if bar else 12) / 2000.0) * 100
    d = H_ - dp
    beta = 0.85 if fc <= 280 else max(0.65, 0.85 - 0.05 * (fc - 280) / 70)
    Ag, Ast = B_ * H_, 2 * As1
    P0 = 0.85 * fc * (Ag - Ast) + fy * Ast
    pts = [(0.0, 0.80 * 0.70 * P0)]
    for i in range(1, steps + 1):
        c = H_ * 1.5 * (1 - i / (steps + 1))
        a = min(beta * c, H_)
        Cc = 0.85 * fc * a * B_
        es1 = 0.003 * (c - dp) / c
        es2 = 0.003 * (c - d) / c
        fs1 = max(-fy, min(fy, es1 * Es))
        fs2 = max(-fy, min(fy, es2 * Es))
        Fs1 = As1 * (fs1 - (0.85 * fc if a > dp else 0.0))
        Fs2 = As1 * fs2
        Pn = Cc + Fs1 + Fs2
        Mn = Cc * (H_ / 2 - a / 2) + Fs1 * (H_ / 2 - dp) - Fs2 * (d - H_ / 2)
        et = -es2
        phi = 0.70 if et <= 0.002 else (0.90 if et >= 0.005 else 0.70 + 0.20 * (et - 0.002) / 0.003)
        q = (phi * Mn / 100.0, min(phi * Pn, 0.80 * 0.70 * P0))
        if q[1] < 0:                              # into tension: end on the M axis
            m0, p0 = pts[-1]
            f = p0 / (p0 - q[1]) if p0 != q[1] else 0.0
            pts.append((m0 + (q[0] - m0) * f, 0.0))
            break
        pts.append(q)
    if pts[-1][1] > 0:
        pts.append((pts[-1][0], 0.0))
    return pts


def pm_ratio(curve, Mu, Pu) -> float:
    """How far out the point (Mu, Pu) lies along its ray from the origin:
    ≤ 1.0 inside the curve."""
    Mu, Pu = abs(Mu), max(Pu, 0.0)
    if Mu < 1e-9 and Pu < 1e-9:
        return 0.0
    ang = math.atan2(Pu, Mu)
    best = None
    for (m0, p0), (m1, p1) in zip(curve, curve[1:]):
        a0, a1 = math.atan2(p0, m0), math.atan2(p1, m1)
        lo, hi = min(a0, a1), max(a0, a1)
        if lo - 1e-9 <= ang <= hi + 1e-9:
            f = 0.0 if abs(a1 - a0) < 1e-12 else (ang - a0) / (a1 - a0)
            rm, rp = m0 + (m1 - m0) * f, p0 + (p1 - p0) * f
            r = math.hypot(rm, rp)
            best = r if best is None else max(best, r)
    if not best:
        return 9.9
    return math.hypot(Mu, Pu) / best


@dataclass
class PMResult:
    curve: list
    Mu: float
    Pu: float

# ---- the whole building ------------------------------------------------------------------

@dataclass
class Member:
    group: str                    # "roof" / "slab" / "beam" / "column" / "footing"
    name: str
    demand: str
    capacity: str
    ratio: float                  # demand / capacity (≤ 1.0 passes)
    note: str = ""
    diagram: object = None        # BeamResult for beams and roof members
    #: the load it carries now in plain units (service), the unit, and the
    #: load factor of an added load — for «รับเพิ่มได้อีก» (reserve)
    qty: float = 0.0
    qty_unit: str = ""
    qty_factor: float = 1.0

    @property
    def ok(self) -> bool:
        return self.ratio <= 1.0 + 1e-9

    @property
    def reserve(self) -> float:
        """How much more load (service, in ``qty_unit``) before the member is
        at its capacity; negative = how much it is over. Loads scale linearly
        with the member's forces, so the extra is qty·(1/ratio − 1); a factored
        increment is turned back to service by ``qty_factor``."""
        if not self.qty or self.ratio <= 0:
            return 0.0
        return self.qty * (1.0 / self.ratio - 1.0) / max(self.qty_factor, 1e-9)

    def reserve_text(self) -> str:
        """In plain words, for someone who does not build."""
        if not self.qty_unit or not self.qty:
            return ""
        r = self.reserve
        unit = self.qty_unit
        nd = 1 if unit.startswith("ตัน") else 0
        pct = (1.0 / self.ratio - 1.0) * 100 if self.ratio > 0 else 0.0
        if r >= 0:
            if pct > 500:
                return f"รับเพิ่มได้อีกมาก — มากกว่า 5 เท่าของน้ำหนักที่ลงตอนนี้ ({unit})"
            return f"รับเพิ่มได้อีก ≈ {r:,.{nd}f} {unit} (เผื่ออีก {pct:,.0f}%)"
        return f"เกินกำลังอยู่ ≈ {-r:,.{nd}f} {unit} — ต้องแก้ก่อนก่อสร้าง"


#: plain names of the groups, for the owner's summary
GROUP_PLAIN = {"slab": "พื้น", "beam": "คาน", "column": "เสา", "footing": "ฐานราก", "roof": "โครงหลังคา",
               "stair": "บันได"}


def reserve_summary(members) -> list:
    """For each kind of member, the weakest one in plain words:
    [(group, text, ok)] — what the building can still take."""
    out = []
    for g in ("slab", "beam", "column", "footing", "roof", "stair"):
        ms = [m for m in members if m.group == g and m.qty and m.qty_unit]
        if not ms:
            continue
        weak = max(ms, key=lambda m: m.ratio)
        r = weak.reserve
        nd = 1 if weak.qty_unit.startswith("ตัน") else 0
        if weak.ok:
            txt = (f"{GROUP_PLAIN[g]}: ตัวที่รับน้ำหนักมากที่สุด ({weak.name.split(' ·')[0]}) ยังรับเพิ่มได้อีก "
                   f"≈ {r:,.{nd}f} {weak.qty_unit}")
        else:
            bad = sum(1 for m in ms if not m.ok)
            txt = (f"{GROUP_PLAIN[g]}: ไม่ผ่าน {bad} ชิ้น — ตัวที่หนักที่สุด ({weak.name.split(' ·')[0]}) "
                   f"เกินกำลังอยู่ ≈ {-r:,.{nd}f} {weak.qty_unit}")
        out.append((g, txt, weak.ok))
    return out


def _ok_text(r):
    return "ผ่าน" if r <= 1.0 + 1e-9 else "ไม่ผ่าน"


def _simple(L, w, n=24):
    return solve_beam([Span(L, w)], n=n)


def roof_checks(data, b_, out):
    """Purlins, rafters, the ridge and the wall plate, the posts."""
    s = B.settings_of(data)
    if s.get("roof") not in B.ROOF_TYPES:
        return 0.0
    pitch = math.radians(float(s["pitch"]))
    cosp = math.cos(pitch)
    tile = tile_weight(s)
    sp_r = float(s["rafter_sp"])
    sp_p = float(s["purlin_sp"])
    D_, L_ = factors(b_)
    E = b_["e_steel"]
    # the roof load per m² of slope, and the half span (wall to ridge)
    q_slope = tile + b_["ll_roof"] * cosp
    fl = stacked_floors(data)
    rooms = fl[-1]["rooms"] if fl else []
    if not rooms:
        return 0.0
    half = min(max(r["x"] + r["w"] for r in rooms) - min(r["x"] for r in rooms),
               max(r["y"] + r["d"] for r in rooms) - min(r["y"] for r in rooms)) / 2
    for key, th, span, trib, extra in (
            ("purlin", "แป", sp_r, sp_p, 0.0),
            ("rafter", "จันทัน", None, sp_r, 0.0)):
        sec = section(s[key])
        if key == "rafter":
            # wall plate → strut (half way) → ridge: the longer of the two bays
            span = (half / 2) / cosp if s.get("struts", True) else half / cosp
        w = q_slope * trib + sec["kg_m"]                       # kg/m along the member (service)
        res = _simple(span, w)
        M = res.Mmax
        fb = b_["fb_timber"] if sec["timber"] else 0.60 * b_["fy_steel"]
        cap = fb * 1e4 * sec["S"]                              # kg·m
        Ei = b_["e_timber"] if sec["timber"] else E
        defl = 5 * w * span ** 4 / (384 * Ei * 1e4 * sec["I"]) if sec["I"] else 1e9
        lim = span / b_["defl"]
        r = max(M / cap if cap else 9.9, defl / lim if lim else 0.0)
        res.caps = {"M+": cap, "M-": cap, "lab_M": "Ma = Fb·S", "defl": (defl, lim)}
        out.append(Member("roof", f"{th} {s[key]}",
                          f"M = {M:,.1f} กก.-ม. · แอ่น {defl * 1000:.1f} มม. (ช่วง {span:.2f} ม.)",
                          f"Ma = {cap:,.1f} กก.-ม. · ยอมให้ {lim * 1000:.1f} มม. (L/{b_['defl']:g})",
                          r, f"น้ำหนัก {w:,.1f} กก./ม. (ASD)", res,
                          qty=w / trib if trib else 0.0, qty_unit="กก./ตร.ม. ของหลังคา"))
        # D + W: the wind's suction on the slope (Cp 0.7) less the covering's
        # weight; ASD with the one-third increase for wind
        up = 0.7 * b_["wind"] - (tile + 0.0) * cosp
        if up > 0:
            ww = up * trib - sec["kg_m"] * cosp
            resw = _simple(span, max(ww, 0.0))
            capw = cap * 4.0 / 3.0
            resw.caps = {"M+": capw, "M-": capw, "lab_M": "Ma × 4/3"}
            rw = resw.Mmax / capw if capw else 9.9
            out.append(Member("roof", f"{th} {s[key]} — แรงลม (แรงยก)",
                              f"M = {resw.Mmax:,.1f} กก.-ม. (แรงยกสุทธิ {up:,.1f} กก./ตร.ม.)",
                              f"Ma × 4/3 = {capw:,.1f} กก.-ม.", rw,
                              f"ลม {b_['wind']:g} กก./ตร.ม. × Cp 0.7 − น้ำหนักวัสดุมุง", resw))
            if key == "rafter":
                lift = up * trib * (half / cosp) / 2
                out.append(Member("roof", "จุดยึดจันทันกับอะเส — แรงยก",
                                  f"แรงยก {lift:,.0f} กก./จุด", "ต้องยึดด้วยเพลท/สลักให้รับได้", 0.0,
                                  "ตรวจขนาดเพลทและรอยเชื่อม/สลักตามรายละเอียดแบบ"))
    # ridge and wall plate: they carry the rafters between the trusses
    sec = section(s["ridge"])
    truss = 4.0
    # the rafters of both slopes hand it (q × the quarter span each side) per metre
    w = q_slope / cosp * (half / 2) * 2 / 2 + sec["kg_m"]
    res = _simple(truss, w)
    cap = (b_["fb_timber"] if sec["timber"] else 0.6 * b_["fy_steel"]) * 1e4 * sec["S"]
    res.caps = {"M+": cap, "M-": cap, "lab_M": "Ma = Fb·S"}
    out.append(Member("roof", f"อกไก่ {s['ridge']}", f"M = {res.Mmax:,.1f} กก.-ม. (ช่วงโครงถัก {truss:.2f} ม.)",
                      f"Ma = {cap:,.1f} กก.-ม.", res.Mmax / cap if cap else 9.9, "", res,
                      qty=w, qty_unit="กก. ต่อเมตรของอกไก่"))
    return q_slope / cosp                                      # kg/m² of plan, service


def stacked_floors(data):
    fl, _sk = B.stacked(data)
    return fl


def _along(e, axis) -> tuple:
    """A beam segment's (low, high) coordinate along its axis."""
    a, b = (e["p0"][0], e["p1"][0]) if axis == "x" else (e["p0"][1], e["p1"][1])
    return min(a, b), max(a, b)


def analyse(data) -> dict:
    """Every member's demand and capacity, the beam diagrams, the column
    loads and the footings: {"members": [Member…], "basis", "columns",
    "beams": {name: BeamResult}}."""
    b_ = basis(data)
    E = B.elements(data)
    lib = E["lib"]
    s = E["settings"]
    D_, L_ = factors(b_)
    fc = b_["fc"]
    conc = b_["concrete"]
    out: list = []
    roof_q = roof_checks(data, b_, out)                        # kg/m² of plan (service)
    floors = E["floors"]
    n = E["n"]
    # -- slabs: the วสท. coefficient method (ACI 318-63 Method 2) by how many
    # of the panel's edges are continuous; one-way slabs by wL²/8 or /10
    slab_q = {}
    level_rooms = {}
    for sl in E["slabs"]:
        level_rooms.setdefault(sl.get("floor", 0), []).append(sl["room"])
    for sl in E["slabs"]:
        spc = lib.get(sl["mark"], {})
        rm = sl["room"]
        t = float(spc.get("t", 0.10))
        a, b2 = sorted((float(rm["w"]), float(rm["d"])))
        dead = t * conc + b_["finish"]
        wu = D_ * dead + L_ * b_["ll_floor"]
        disc = discontinuous_edges(rm, level_rooms.get(sl.get("floor", 0), []))
        m_ = a / b2
        if m_ < 0.5:
            Mu = wu * a * a / (10.0 if disc <= 2 else 8.0)
            kind = "พื้นทางเดียว"
        else:
            Mu = slab_moment(m_, disc) * wu * a * a
            kind = f"พื้นสองทาง กรณี {disc + 1} (ขอบไม่ต่อเนื่อง {disc} ด้าน, m = {m_:.2f})"
        bar = R.parse_bar(spc.get("bars"))
        d = t - R.COVER["slab"] - (bar.d / 2000.0 if bar else 0.005)
        if bar and bar.s:
            As = bar.area / bar.s                                  # cm²/m
            if b_["method"] == "SDM":
                aa = As * fy_of(bar, b_) / (0.85 * fc * 100)
                cap = 0.90 * As * fy_of(bar, b_) * (d * 100 - aa / 2) / 100
            else:
                cap = As * fs_of(bar, b_) * 0.875 * d * 100 / 100
        else:
            cap = 0.0
        if not sl.get("ground") and not spc.get("ground"):
            out.append(Member("slab", f"{sl['mark']} {rm.get('name', '')} {a:.2f}×{b2:.2f} ม.",
                              f"Mu = {Mu:,.1f} กก.-ม./ม. ({kind})", f"φMn = {cap:,.1f} กก.-ม./ม.",
                              Mu / cap if cap else 9.9, f"wu = {wu:,.0f} กก./ตร.ม.",
                              qty=wu, qty_unit="กก./ตร.ม. (คน/ของวางเพิ่ม)", qty_factor=L_))
        slab_q[id(rm)] = (D_ * dead + L_ * b_["ll_floor"], dead, b_["ll_floor"])
    # -- beams: collinear runs on the same level, continuous over the columns
    runs: dict = {}
    for e in E["beams"]:
        (x0, y0), (x1, y1) = e["p0"], e["p1"]
        horiz = abs(y1 - y0) < 1e-6
        key = (e["level"], e["mark"], "x" if horiz else "y", round(y0 if horiz else x0, 3))
        runs.setdefault(key, []).append(e)
    rooms_by_level = {i: (f.get("rooms") or []) for i, f in enumerate(floors)}
    walls = E["walls"]
    beams_out = {}
    user_loads = B.beam_loads(data)
    col_load: dict = {}
    col_mom: dict = {}
    col_lv: dict = {}
    for key, segs in runs.items():
        level, mark, axis, c = key
        segs.sort(key=lambda e: min(e["p0"][0], e["p1"][0]) if axis == "x" else min(e["p0"][1], e["p1"][1]))
        spec = lib.get(mark, {})
        bw, h = float(spec.get("b", 0.2)), float(spec.get("h", 0.4))
        spans = []
        for e in segs:
            L = math.dist(e["p0"], e["p1"])
            w = D_ * bw * h * conc
            # slabs either side (the floor this beam carries: the floor above its level)
            fl = level
            for rm in rooms_by_level.get(fl, []) if not e.get("roof") else []:
                rx0, ry0, rx1, ry1 = rm["x"], rm["y"], rm["x"] + rm["w"], rm["y"] + rm["d"]
                on = (axis == "x" and abs(ry0 - c) < 1e-6 or abs(ry1 - c) < 1e-6) if axis == "x" else \
                    (abs(rx0 - c) < 1e-6 or abs(rx1 - c) < 1e-6)
                lo = min(e["p0"][0], e["p1"][0]) if axis == "x" else min(e["p0"][1], e["p1"][1])
                hi = max(e["p0"][0], e["p1"][0]) if axis == "x" else max(e["p0"][1], e["p1"][1])
                along = (rx0 - 1e-6 <= lo and hi <= rx1 + 1e-6) if axis == "x" else \
                    (ry0 - 1e-6 <= lo and hi <= ry1 + 1e-6)
                if not (on and along):
                    continue
                q = slab_q.get(id(rm), (D_ * (0.10 * conc + b_["finish"]) + L_ * b_["ll_floor"], 0, 0))[0]
                S_ = min(rm["w"], rm["d"])
                Lr = max(rm["w"], rm["d"])
                m_ = S_ / Lr
                parallel_long = (axis == "x" and rm["w"] >= rm["d"]) or (axis == "y" and rm["d"] > rm["w"])
                w += q * S_ / 3.0 if not parallel_long else q * S_ / 6.0 * (3 - m_ * m_)
            # the wall standing on it
            for wl in walls:
                if wl["floor"] != level:
                    continue
                if {tuple(map(lambda v: round(v, 3), wl["p0"])), tuple(map(lambda v: round(v, 3), wl["p1"]))} \
                        == {tuple(map(lambda v: round(v, 3), e["p0"])), tuple(map(lambda v: round(v, 3), e["p1"]))}:
                    w += D_ * b_["wall_kg_m2"] * (float(s["floor_h"]) - h)
            # the roof on the top ring beams
            if e.get("roof") and roof_q:
                # an eave-side ring beam takes the roof from its wall half way up
                # to the struts plus the overhang
                fl_ = floors[-1]["rooms"] if floors else []
                half_ = min(max(r["x"] + r["w"] for r in fl_) - min(r["x"] for r in fl_),
                            max(r["y"] + r["d"] for r in fl_) - min(r["y"] for r in fl_)) / 2 if fl_ else 2.0
                w += (D_ * tile_weight(s) + L_ * b_["ll_roof"]) / math.cos(math.radians(
                    float(s["pitch"]))) * (half_ / 2 + float(s["overhang"]))
            lo_, hi_ = _along(e, axis)
            sp_ = Span(L, w)
            if e.get("cant"):
                free = e["p1"][0] if axis == "x" else e["p1"][1]
                sp_.cant = "L" if abs(free - lo_) < 1e-6 else "R"
            for q in user_loads:
                if q.get("level", 1) != level or q.get("axis") != axis or abs(float(q.get("line", 0)) - c) > 1e-3:
                    continue
                fac = D_ if q.get("type", "D") == "D" else L_
                a_, b2_ = sorted((float(q.get("a", 0)), float(q.get("b", q.get("a", 0)))))
                if "P" in q and b2_ - a_ < 1e-9:
                    if lo_ - 1e-9 <= a_ < hi_ - 1e-9 or (abs(a_ - hi_) < 1e-9 and e is segs[-1]):
                        sp_.P.append((a_ - lo_, fac * float(q["P"])))
                elif "w" in q:
                    ca, cb_ = max(a_, lo_), min(b2_, hi_)
                    if cb_ - ca > 1e-6:
                        sp_.U.append((ca - lo_, cb_ - lo_, fac * float(q["w"])))
            spans.append(sp_)
        if not spans:
            continue
        # a cantilever only at the ends of a run
        for j, sp_ in enumerate(spans):
            if sp_.cant == "L" and j != 0 or sp_.cant == "R" and j != len(spans) - 1:
                sp_.cant = ""
        res = solve_beam(spans)
        res.mark, res.spec, res.level, res.axis, res.line = mark, spec, level, axis, c
        res.ground = bool(segs[0].get("ground"))
        res.z = float(segs[0].get("z", 0.0))
        cap = beam_capacity(spec, b_, fc)
        sdm = b_["method"] == "SDM"
        res.caps = {"M+": cap["bot"], "M-": cap["top"], "V": cap["V"], "Vc": cap["Vc"],
                    "lab_M": "φMn" if sdm else "Ma", "lab_V": "φVn" if sdm else "Va",
                    "lab_Vc": "φVc" if sdm else "vc·bd"}
        r = max(res.Mmax / cap["bot"] if cap["bot"] else 9.9,
                -res.Mmin / cap["top"] if cap["top"] and res.Mmin < 0 else 0.0,
                res.Vmax / cap["V"] if cap["V"] else 9.9)
        name = (f"{mark} ชั้น {level + 1 if not segs[0].get('ground') else 'ดิน'} · "
                f"แนว{'นอน' if axis == 'x' else 'ตั้ง'} {'y' if axis == 'x' else 'x'} = {c:.2f} · "
                f"{len(spans) - sum(1 for sp_ in spans if sp_.cant)} ช่วง"
                + (" + คานยื่น" if any(sp_.cant for sp_ in spans) else "")
                + (" + น้ำหนักเพิ่ม" if any(sp_.P or sp_.U for sp_ in spans) else ""))
        out.append(Member("beam", name,
                          f"Mu+ {res.Mmax:,.0f} · Mu− {max(0.0, -res.Mmin):,.0f} กก.-ม. · Vu {res.Vmax:,.0f} กก.",
                          f"φMn ล่าง {cap['bot']:,.0f} · บน {cap['top']:,.0f} · φVn {cap['V']:,.0f}",
                          r, f"w = {', '.join(f'{sp.w:,.0f}' for sp in spans)} กก./ม.", res,
                          qty=max(sp.w for sp in spans) / ((D_ + L_) / 2.0),
                          qty_unit="กก. ต่อเมตรของคาน"))
        beams_out[name] = res
        # reactions to the columns at the supports
        x = 0.0
        ends = []
        for e, sp_ in zip(segs, spans):
            lo_, hi_ = _along(e, axis)
            if sp_.cant == "L":
                ends.append(hi_)
            elif sp_.cant == "R":
                if not ends:
                    ends.append(lo_)
            else:
                if not ends:
                    ends.append(lo_)
                ends.append(hi_)
        pts = [((v, c) if axis == "x" else (c, v)) for v in ends]
        for p, Rv in zip(pts, res.reactions):
            k_ = (round(p[0], 3), round(p[1], 3))
            col_load[k_] = col_load.get(k_, 0.0) + Rv
            col_lv[(k_, level)] = col_lv.get((k_, level), 0.0) + Rv
        # the moment a beam end hands its column (ACI coefficient wL²/16 at an
        # end built into a column, shared by the columns above and below)
        for p, sp_ in ((pts[0], spans[0]), (pts[-1], spans[-1])):
            k_ = (round(p[0], 3), round(p[1], 3))
            if sp_.cant:                     # the whole cantilever moment, shared above and below
                tot_, mom_ = _span_loads(sp_)
                mc_ = tot_ * sp_.L - mom_ if sp_.cant == "L" else mom_
                col_mom[k_] = max(col_mom.get(k_, 0.0), mc_ / 2.0)
            else:
                col_mom[k_] = max(col_mom.get(k_, 0.0), sp_.w * sp_.L ** 2 / 16.0 / 2.0)
    # -- columns: everything above, per column line (the ground floor's carries it all)
    cols_out = []
    for c_ in E["columns"]:
        if c_.get("floor", 0) != 0:
            continue
        k_ = (round(c_["x"], 3), round(c_["y"], 3))
        spec = lib.get(c_["mark"], {})
        Pu = col_load.get(k_, 0.0) + D_ * float(spec.get("b", 0.2)) * float(spec.get("h", 0.2)) * \
            conc * float(s["floor_h"]) * n
        cap = column_capacity(spec, b_, fc)
        hh = max(float(spec.get("b", 0.2)), float(spec.get("h", 0.2)))
        Mu = max(Pu * (0.015 + 0.03 * hh), col_mom.get(k_, 0.0))      # e_min = 15 mm + 0.03 h
        if b_["method"] == "SDM":
            curve = pm_curve(spec, b_)
            r = pm_ratio(curve, Mu, Pu)
            dia = PMResult(curve, Mu, Pu)
            capt = f"φPn {cap / 1000:,.2f} ตัน (แรงอัดล้วน) · ตรวจด้วยแผนภาพ P-M"
        else:
            r, dia, capt = Pu / cap if cap else 9.9, None, f"P ยอมให้ {cap / 1000:,.2f} ตัน"
        out.append(Member("column", f"{c_['mark']} ที่ ({c_['x']:.2f}, {c_['y']:.2f})",
                          f"Pu = {Pu / 1000:,.2f} ตัน · Mu = {Mu:,.0f} กก.-ม.", capt, r,
                          "Mu = ค่ามากกว่าของ Pu·emin และโมเมนต์จากปลายคาน (wL²/16 แบ่งเสาบน-ล่าง)", dia,
                          qty=Pu / ((D_ + L_) / 2.0) / 1000.0, qty_unit="ตัน ต่อเสา 1 ต้น"))
        cols_out.append((k_, Pu))
    # -- footings: the service load on the soil or the piles
    avg = (D_ + L_) / 2.0
    for f in E["footings"]:
        k_ = (round(f["x"], 3), round(f["y"], 3))
        spec = lib.get(f["mark"], {})
        Pu = next((p for kk, p in cols_out if kk == k_), 0.0)
        P = Pu / avg                                                # back to service
        w_, l_, t_ = (float(spec.get(k, 0)) for k in ("w", "l", "t"))
        P += w_ * l_ * t_ * conc
        piles = int(spec.get("piles") or 0)
        if piles:
            from core import wanic_pile as PL
            pc = PL.cap_of(spec, data, b_)
            pt = PL.type_of_spec(spec)
            cap = piles * pc * 1000
            out.append(Member("footing", f"{f['mark']} ที่ ({f['x']:.2f}, {f['y']:.2f}) · เข็ม {piles} ต้น ({pt})",
                              f"P = {P / 1000:,.2f} ตัน (ใช้งาน)",
                              f"เข็ม {pt} {piles} × {pc:,.2f} = {cap / 1000:,.2f} ตัน", P / cap if cap else 9.9,
                              f"ต้องใช้เข็มอย่างน้อย {max(1, math.ceil(P / (pc * 1000))) if pc else '-'} ต้น",
                              qty=P / 1000.0, qty_unit="ตัน ต่อฐาน 1 ฐาน"))
        else:
            q = P / (w_ * l_) / 1000 if w_ * l_ else 99.0
            out.append(Member("footing", f"{f['mark']} ที่ ({f['x']:.2f}, {f['y']:.2f}) · ฐานแผ่ {w_:.2f}×{l_:.2f} ม.",
                              f"q = {q:,.2f} ตัน/ตร.ม.", f"ดินรับได้ {b_['soil']:g} ตัน/ตร.ม.", q / b_["soil"],
                              f"ต้องใช้ฐานอย่างน้อย {math.sqrt(P / 1000 / b_['soil']):.2f} × "
                              f"{math.sqrt(P / 1000 / b_['soil']):.2f} ม.",
                              qty=P / 1000.0, qty_unit="ตัน ต่อฐาน 1 ฐาน"))
    # column loads floor by floor (for the booklet's column cards): a column
    # of floor f carries the beams of the levels above it; the stump all
    cards = []
    levels = sorted({lv for (_k, lv) in col_lv})
    for c_ in E["stumps"] + E["columns"]:
        k_ = (round(c_["x"], 3), round(c_["y"], 3))
        spec = lib.get(c_["mark"], {})
        f = -1 if c_ in E["stumps"] else int(c_.get("floor", 0))
        P = sum(v for (kk, lv), v in col_lv.items() if kk == k_ and lv >= f + 1)
        P += float(spec.get("b", 0.2)) * float(spec.get("h", 0.2)) * conc * float(s["floor_h"]) * \
            max(1, n - max(f, 0)) * D_
        cards.append({"mark": c_["mark"], "x": c_["x"], "y": c_["y"], "floor": f, "P": P, "spec": spec,
                      "H": abs(float(c_["z1"]) - float(c_["z0"]))})
    stairs = []
    try:
        from core import wanic_stair as ST
        stairs = ST.designs(data, b_)
    except Exception:                                # noqa: BLE001 - the stairs never stop the rest
        stairs = []
    for dz in stairs:
        out.extend(dz["members"])
    for m in out:
        if m.diagram is not None and m.qty:
            try:
                m.diagram.reserve = m.reserve_text()
            except (AttributeError, TypeError):
                pass
    return {"members": out, "basis": b_, "beams": beams_out, "columns": cols_out, "cards": cards,
            "stairs": stairs,
            "levels": levels}


def summary(res) -> dict:
    groups = {}
    for m in res["members"]:
        g = groups.setdefault(m.group, [0, 0, 0.0])
        g[0] += 1
        g[1] += 0 if m.ok else 1
        g[2] = max(g[2], m.ratio)
    return groups


#: the usual service load of a Thai RC house per m² of floor (all floors and
#: the roof counted), for the Checkload sanity check
WFLOOR_RANGE = (450.0, 1600.0)


def checkload(data, res) -> dict:
    """Checkload — the load on each ground-floor column three ways:
    Wcol (from the beam reactions, service, tonnes), its tributary area
    over every floor it carries and the roof (m²), Wfloor = Wcol / area
    (kg/m²) and Wcol-Area = area × the building's average Wfloor; a column
    far from the average (or Wfloor outside the usual range) is flagged."""
    E = B.elements(data)
    b_ = res["basis"]
    D_, L_ = factors(b_)
    avg = (D_ + L_) / 2.0
    floors = E["floors"]
    carried = [sl["room"] for sl in E["slabs"]
               if not (sl.get("floor", 0) == 0 and (E["lib"].get(sl["mark"], {}).get("ground")
                                                    or sl["mark"] == "S1"))]
    roof = floors[-1]["rooms"] if floors else []
    area: dict = {}
    for group in (carried, roof):
        for rm in group:
            pts = [p for p in B.nodes([rm]) if B._on_edge(rm, *p)]
            if not pts:
                continue
            share = float(rm["w"]) * float(rm["d"]) / len(pts)
            for p in pts:
                k_ = (round(p[0], 3), round(p[1], 3))
                area[k_] = area.get(k_, 0.0) + share
    rows = []
    for k_, Pu in res["columns"]:
        W = Pu / avg
        A = area.get(k_, 0.0)
        rows.append({"x": k_[0], "y": k_[1], "W": W, "A": A, "Wf": W / A if A else 0.0})
    tot_A = sum(r["A"] for r in rows)
    mean = sum(r["W"] for r in rows) / tot_A if tot_A else 0.0
    marks = {(round(c["x"], 3), round(c["y"], 3)): c["mark"] for c in E["columns"] if c.get("floor", 0) == 0}
    lo, hi = WFLOOR_RANGE
    for r in rows:
        r["mark"] = marks.get((r["x"], r["y"]), "C")
        r["WA"] = r["A"] * mean
        r["diff"] = (r["W"] - r["WA"]) / r["WA"] * 100 if r["WA"] else 0.0
        if not r["A"]:
            r["ok"], r["note"] = False, "ไม่มีพื้นที่รับน้ำหนัก — ตรวจผัง/คานยื่น"
        elif r["Wf"] < lo or r["Wf"] > hi:
            r["ok"], r["note"] = False, (f"Wfloor {'สูง' if r['Wf'] > hi else 'ต่ำ'}กว่าปกติ "
                                         f"({lo:,.0f}–{hi:,.0f}) — ตรวจน้ำหนักที่ใส่")
        elif abs(r["diff"]) > 40:
            r["ok"], r["note"] = True, f"ต่างจากค่าเฉลี่ย {r['diff']:+.0f}% (มีผนัง/คานยื่น/น้ำหนักเพิ่ม)"
        else:
            r["ok"], r["note"] = True, "ปกติ"
    return {"rows": rows, "mean": mean, "area": tot_A, "range": WFLOOR_RANGE,
            "total": sum(r["W"] for r in rows)}
