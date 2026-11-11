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
}


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


def solve_beam(spans: list, fixed_ends=(False, False), n=24) -> BeamResult:
    """A continuous beam over len(spans)+1 supports: stiffness method on the
    rotations (supports do not settle); uniform and point loads per span.
    Returns the shear and moment along it and the support reactions."""
    k = len(spans)
    # fixed-end moments (clockwise +) for each span: left, right
    fem = []
    for sp in spans:
        L = sp.L
        fl = sp.w * L * L / 12.0
        fr = -fl
        for a, P in sp.P:
            b = L - a
            fl += P * a * b * b / (L * L)
            fr -= P * a * a * b / (L * L)
        fem.append((fl, fr))
    ndof = k + 1
    K = [[0.0] * ndof for _ in range(ndof)]
    F = [0.0] * ndof
    EI = 1.0
    for i, sp in enumerate(spans):
        L = sp.L
        kk = [[4 * EI / L, 2 * EI / L], [2 * EI / L, 4 * EI / L]]
        for a in range(2):
            for b in range(2):
                K[i + a][i + b] += kk[a][b]
        F[i] -= fem[i][0]
        F[i + 1] -= fem[i][1]
    free = [j for j in range(ndof)
            if not ((j == 0 and fixed_ends[0]) or (j == ndof - 1 and fixed_ends[1]))]
    # solve K_ff θ = F_f (Gauss)
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
    for i, sp in enumerate(spans):
        L = sp.L
        ml = fem[i][0] + 4 * EI / L * th[i] + 2 * EI / L * th[i + 1]     # end moments (clockwise +)
        mr = fem[i][1] + 2 * EI / L * th[i] + 4 * EI / L * th[i + 1]
        tot = sp.w * L + sum(P for _a, P in sp.P)
        mom_r = sp.w * L * L / 2 + sum(P * a for a, P in sp.P)
        Rr = (mom_r - ml - mr) / L                                       # sum of moments about left
        Rl = tot - Rr
        reactions[i] += Rl
        reactions[i + 1] += Rr
        for s in range(n + 1):
            x = L * s / n
            v = Rl - sp.w * x - sum(P for a, P in sp.P if a < x - 1e-9)
            mm = -ml + Rl * x - sp.w * x * x / 2 - sum(P * (x - a) for a, P in sp.P if a < x)
            xs.append(x0 + x)
            V.append(v)
            M.append(mm)
        x0 += L
    return BeamResult(spans, xs, V, M, reactions, max(M) if M else 0.0, min(M) if M else 0.0,
                      max((abs(v) for v in V), default=0.0))


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
        fy = bar.fy
        if b_["method"] == "SDM":
            a = As * fy / (0.85 * fc * bw * 100)    # cm
            Mn = As * fy * (d * 100 - a / 2) / 100  # kg·m
            out[key] = 0.90 * Mn
        else:                                       # WSD: fs = 0.5 fy, j ≈ 0.875
            out[key] = As * 0.5 * fy * 0.875 * d * 100 / 100
    st = R.parse_bar(spec.get("stir"))
    vc = (0.53 if b_["method"] == "SDM" else 0.29) * math.sqrt(fc) * bw * 100 * d * 100
    vs = 0.0
    if st and st.s:
        vs = 2 * st.area * (st.fy if b_["method"] == "SDM" else 0.5 * st.fy) * d * 100 / (st.s * 100)
    out["V"] = (0.85 if b_["method"] == "SDM" else 1.0) * (vc + vs)
    out["d"] = d
    return out


def column_capacity(spec: dict, b_: dict, fc: float) -> float:
    """φPn (kg) of a tied column, axial only (the usual check of a house column)."""
    b, h = float(spec["b"]), float(spec["h"])
    Ag = b * h * 1e4
    bar = R.parse_bar(spec.get("main"))
    Ast = bar.n * bar.area if bar and bar.n else 0.0
    fy = bar.fy if bar else 4000.0
    if b_["method"] == "SDM":
        return 0.80 * 0.70 * (0.85 * fc * (Ag - Ast) + fy * Ast)
    return 0.85 * (0.25 * fc * Ag + 0.40 * fy * Ast)


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

    @property
    def ok(self) -> bool:
        return self.ratio <= 1.0 + 1e-9


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
        out.append(Member("roof", f"{th} {s[key]}",
                          f"M = {M:,.1f} กก.-ม. · แอ่น {defl * 1000:.1f} มม. (ช่วง {span:.2f} ม.)",
                          f"Ma = {cap:,.1f} กก.-ม. · ยอมให้ {lim * 1000:.1f} มม. (L/{b_['defl']:g})",
                          r, f"น้ำหนัก {w:,.1f} กก./ม. (ASD)", res))
    # ridge and wall plate: they carry the rafters between the trusses
    sec = section(s["ridge"])
    truss = 4.0
    # the rafters of both slopes hand it (q × the quarter span each side) per metre
    w = q_slope / cosp * (half / 2) * 2 / 2 + sec["kg_m"]
    res = _simple(truss, w)
    cap = (b_["fb_timber"] if sec["timber"] else 0.6 * b_["fy_steel"]) * 1e4 * sec["S"]
    out.append(Member("roof", f"อกไก่ {s['ridge']}", f"M = {res.Mmax:,.1f} กก.-ม. (ช่วงโครงถัก {truss:.2f} ม.)",
                      f"Ma = {cap:,.1f} กก.-ม.", res.Mmax / cap if cap else 9.9, "", res))
    return q_slope / cosp                                      # kg/m² of plan, service


def stacked_floors(data):
    fl, _sk = B.stacked(data)
    return fl


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
    # -- slabs: one-way / two-way (Marcus strips), and what they give their beams
    slab_q = {}
    for sl in E["slabs"]:
        spc = lib.get(sl["mark"], {})
        rm = sl["room"]
        t = float(spc.get("t", 0.10))
        a, b2 = sorted((float(rm["w"]), float(rm["d"])))
        dead = t * conc + b_["finish"]
        wu = D_ * dead + L_ * b_["ll_floor"]
        if b2 / a > 2.0:
            Mu = wu * a * a / 8.0
            kind = "พื้นทางเดียว"
        else:
            ws = wu * b2 ** 4 / (a ** 4 + b2 ** 4)
            Mu = ws * a * a / 8.0
            kind = "พื้นสองทาง"
        bar = R.parse_bar(spc.get("bars"))
        d = t - R.COVER["slab"] - (bar.d / 2000.0 if bar else 0.005)
        if bar and bar.s:
            As = bar.area / bar.s                                  # cm²/m
            if b_["method"] == "SDM":
                aa = As * bar.fy / (0.85 * fc * 100)
                cap = 0.90 * As * bar.fy * (d * 100 - aa / 2) / 100
            else:
                cap = As * 0.5 * bar.fy * 0.875 * d * 100 / 100
        else:
            cap = 0.0
        if not sl.get("ground") and not spc.get("ground"):
            out.append(Member("slab", f"{sl['mark']} {rm.get('name', '')} {a:.2f}×{b2:.2f} ม.",
                              f"Mu = {Mu:,.1f} กก.-ม./ม. ({kind})", f"φMn = {cap:,.1f} กก.-ม./ม.",
                              Mu / cap if cap else 9.9, f"wu = {wu:,.0f} กก./ตร.ม."))
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
    col_load: dict = {}
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
            spans.append(Span(L, w))
        if not spans:
            continue
        res = solve_beam(spans)
        cap = beam_capacity(spec, b_, fc)
        r = max(res.Mmax / cap["bot"] if cap["bot"] else 9.9,
                -res.Mmin / cap["top"] if cap["top"] and res.Mmin < 0 else 0.0,
                res.Vmax / cap["V"] if cap["V"] else 9.9)
        name = (f"{mark} ชั้น {level + 1 if not segs[0].get('ground') else 'ดิน'} · "
                f"แนว{'นอน' if axis == 'x' else 'ตั้ง'} {'y' if axis == 'x' else 'x'} = {c:.2f} · "
                f"{len(spans)} ช่วง")
        out.append(Member("beam", name,
                          f"Mu+ {res.Mmax:,.0f} · Mu− {max(0.0, -res.Mmin):,.0f} กก.-ม. · Vu {res.Vmax:,.0f} กก.",
                          f"φMn ล่าง {cap['bot']:,.0f} · บน {cap['top']:,.0f} · φVn {cap['V']:,.0f}",
                          r, f"w = {', '.join(f'{sp.w:,.0f}' for sp in spans)} กก./ม.", res))
        beams_out[name] = res
        # reactions to the columns at the supports
        x = 0.0
        pts = [segs[0]["p0"] if (segs[0]["p0"][0] if axis == "x" else segs[0]["p0"][1]) <=
               (segs[0]["p1"][0] if axis == "x" else segs[0]["p1"][1]) else segs[0]["p1"]]
        for e in segs:
            far = max((e["p0"], e["p1"]), key=lambda p: p[0] if axis == "x" else p[1])
            pts.append(far)
        for p, Rv in zip(pts, res.reactions):
            k_ = (round(p[0], 3), round(p[1], 3))
            col_load[k_] = col_load.get(k_, 0.0) + Rv
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
        out.append(Member("column", f"{c_['mark']} ที่ ({c_['x']:.2f}, {c_['y']:.2f})",
                          f"Pu = {Pu / 1000:,.2f} ตัน", f"φPn = {cap / 1000:,.2f} ตัน", Pu / cap if cap else 9.9))
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
            cap = piles * b_["pile_cap"] * 1000
            out.append(Member("footing", f"{f['mark']} ที่ ({f['x']:.2f}, {f['y']:.2f}) · เข็ม {piles} ต้น",
                              f"P = {P / 1000:,.2f} ตัน (ใช้งาน)",
                              f"เข็ม {piles} × {b_['pile_cap']:g} = {cap / 1000:,.2f} ตัน", P / cap if cap else 9.9,
                              f"ต้องใช้เข็มอย่างน้อย {max(1, math.ceil(P / (b_['pile_cap'] * 1000)))} ต้น"))
        else:
            q = P / (w_ * l_) / 1000 if w_ * l_ else 99.0
            out.append(Member("footing", f"{f['mark']} ที่ ({f['x']:.2f}, {f['y']:.2f}) · ฐานแผ่ {w_:.2f}×{l_:.2f} ม.",
                              f"q = {q:,.2f} ตัน/ตร.ม.", f"ดินรับได้ {b_['soil']:g} ตัน/ตร.ม.", q / b_["soil"],
                              f"ต้องใช้ฐานอย่างน้อย {math.sqrt(P / 1000 / b_['soil']):.2f} × "
                              f"{math.sqrt(P / 1000 / b_['soil']):.2f} ม."))
    return {"members": out, "basis": b_, "beams": beams_out, "columns": cols_out}


def summary(res) -> dict:
    groups = {}
    for m in res["members"]:
        g = groups.setdefault(m.group, [0, 0, 0.0])
        g[0] += 1
        g[1] += 0 if m.ok else 1
        g[2] = max(g[2], m.ratio)
    return groups
