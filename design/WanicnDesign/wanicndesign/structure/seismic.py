# -*- coding: utf-8 -*-
"""Earthquake design: equivalent static force procedure.

Follows มยผ. 1301/1302-61 [DPT1301] (whose loads, factors and tables
follow ASCE 7-05 [ASCE7]):

1. Site coefficients Fa, Fv from the site class; SDS = ⅔·Fa·Ss,
   SD1 = ⅔·Fv·S1 — or SDS, SD1 (and, for the Bangkok basin, Sa itself)
   entered from the standard's tables for the site.
2. Seismic design category from SDS, SD1 and the risk category.
3. T = 0.02·H (reinforced concrete moment frame); Sa = SDS for T ≤ Ts,
   SD1/T beyond; Cs = Sa·Ie/R ≥ max(0.01, 0.044·SDS·Ie); V = Cs·W.
4. Fx = Cvx·V with Cvx = wx·hx^k / Σ wi·hi^k.
5. Rigid floors: each floor force goes to the frame lines by their lateral
   stiffness, with the actual eccentricity plus 5% accidental torsion.
6. Each frame line is analysed as a plane frame with cracked stiffness
   (0.70 Ig columns, 0.35 Ig beams) [ACI318-STIFF]: storey drift
   Δ = Cd·δe/Ie ≤ Δa, stability coefficient θ.
7. Strength checks with the load combinations of the standard:
   (1.2 + 0.2 SDS) D + 1.0 L + E and (0.9 − 0.2 SDS) D + E for beams and
   columns (strength design, วสท. 1008 / ACI 318 [EIT1008]); allowable
   stress combinations D + 0.7E, D + 0.75L + 0.525E, 0.6D + 0.7E for
   piles and soil.

Gravity design stays by working stress (วสท. 1007); the earthquake check is
a separate strength check that may add bars, enlarge columns and add piles.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..standards import cite
from .frame2d import Member, solve_frame
from .materials import ES, FY
from .sections import BAR_DIA, bar_area, load_piles, pick_bars

# --- tables [DPT1301], [ASCE7] ---------------------------------------------------
SS_STEPS = [0.25, 0.50, 0.75, 1.00, 1.25]
S1_STEPS = [0.10, 0.20, 0.30, 0.40, 0.50]
FA = {"A": [0.8] * 5, "B": [1.0] * 5, "C": [1.2, 1.2, 1.1, 1.0, 1.0],
      "D": [1.6, 1.4, 1.2, 1.1, 1.0], "E": [2.5, 1.7, 1.2, 0.9, 0.9]}
FV = {"A": [0.8] * 5, "B": [1.0] * 5, "C": [1.7, 1.6, 1.5, 1.4, 1.3],
      "D": [2.4, 2.0, 1.8, 1.6, 1.5], "E": [3.5, 3.2, 2.8, 2.4, 2.4]}
SITE_CLASSES = [("A", "A หินแข็ง"), ("B", "B หิน"), ("C", "C ดินแข็งมาก/หินอ่อน"),
                ("D", "D ดินแข็ง"), ("E", "E ดินอ่อน")]
#: Importance factor by risk category.
IMPORTANCE = {"I": 1.0, "II": 1.0, "III": 1.25, "IV": 1.5}
RISK_CATEGORIES = [("I", "I อาคารที่มีความเสี่ยงต่ำต่อชีวิต (โรงเก็บของ)"),
                   ("II", "II อาคารทั่วไป (บ้าน อาคารพาณิชย์ สำนักงาน)"),
                   ("III", "III อาคารที่มีคนจำนวนมาก (โรงเรียน หอประชุม)"),
                   ("IV", "IV อาคารที่จำเป็นต่อความเป็นอยู่ (โรงพยาบาล สถานีดับเพลิง)")]
#: Reinforced concrete moment frames: (name, R, Ω0, Cd, design categories allowed).
SYSTEMS = {
    "OMF": ("โครงต้านแรงดัดคอนกรีตเสริมเหล็กแบบธรรมดา", 3.0, 3.0, 2.5, "AB"),
    "IMF": ("โครงต้านแรงดัดคอนกรีตเสริมเหล็กที่มีความเหนียวปานกลาง", 5.0, 3.0, 4.5, "ABC"),
}
#: Allowable storey drift / storey height by risk category.
DRIFT_LIMIT = {"I": 0.020, "II": 0.020, "III": 0.015, "IV": 0.010}
ACCIDENTAL = 0.05
CRACKED_COLUMN, CRACKED_BEAM = 0.70, 0.35          # [ACI318-STIFF]
STORAGE_USES = {"industrial", "archive"}            # 25% of live load in W
PHI_SHEAR = 0.75
COVER = 4.0                                          # cm to the ties
TIE = "RB6"
FY_TIE = 2400.0

REFS = cite("DPT1301", "ASCE7", "EIT1008", "ACI318-STIFF", "STATICS")


def _step(v: float, steps: list[float], vals: list[float]) -> float:
    if v <= steps[0]:
        return vals[0]
    for (x0, y0), (x1, y1) in zip(zip(steps, vals), zip(steps[1:], vals[1:])):
        if v <= x1:
            return y0 + (y1 - y0) * (v - x0) / (x1 - x0)
    return vals[-1]


def site_coefficients(ss: float, s1: float, site: str) -> tuple[float, float]:
    return _step(ss, SS_STEPS, FA[site]), _step(s1, S1_STEPS, FV[site])


def design_category(sds: float, sd1: float, risk: str) -> str:
    iv = risk == "IV"
    a = "A" if sds < 0.167 else ("C" if iv else "B") if sds < 0.33 else \
        ("D" if iv else "C") if sds < 0.50 else "D"
    b = "A" if sd1 < 0.067 else ("C" if iv else "B") if sd1 < 0.133 else \
        ("D" if iv else "C") if sd1 < 0.20 else "D"
    return max(a, b)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@dataclass
class StoreyResult:
    level: str
    hx: float           # m above the base
    wx: float           # kg
    fx: float           # kg
    vx: float           # storey shear, kg
    drift_x: float      # design storey drift Δ, m
    drift_y: float
    limit: float        # Δa, m
    theta: float        # stability coefficient (larger direction)
    ok: bool = True
    note: str = ""


@dataclass
class MemberCheck:
    kind: str           # "column", "beam", "footing"
    where: str
    direction: str
    demand: str
    capacity: str
    ratio: float
    detail: str
    ok: bool = True
    note: str = ""


@dataclass
class SeismicResult:
    sds: float
    sd1: float
    fa: float
    fv: float
    category: str       # seismic design category A–D
    system: str
    R: float
    cd: float
    ie: float
    period: float
    sa: float
    cs: float
    weight: float
    base_shear: float
    k: float
    storeys: list = field(default_factory=list)
    checks: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    refs: str = REFS

    @property
    def ok(self) -> bool:
        return all(s.ok for s in self.storeys) and all(c.ok for c in self.checks) and \
            not any(w.startswith("NG") for w in self.warnings)


# ---------------------------------------------------------------------------
# Section strength (strength design) [EIT1008]
# ---------------------------------------------------------------------------

def _beta1(fc: float) -> float:
    return max(0.65, min(0.85, 0.85 - 0.05 * (fc - 280.0) / 70.0))


def _phi(eps_t: float, fy: float) -> float:
    ey = fy / ES
    if eps_t <= ey:
        return 0.65
    if eps_t >= 0.005:
        return 0.90
    return 0.65 + 0.25 * (eps_t - ey) / (0.005 - ey)


def parse_bars(text: str) -> tuple[int, str]:
    n, size = text.split("-", 1)
    return int(n), size.strip()


def column_bars(n: int, size: str, depth: float, width: float):
    """Bars as (distance from the compression face, area), cm. Corners,
    then equal extra bars on every face; any two left over go on the side
    faces at mid depth (the less favourable place)."""
    a = bar_area(size)
    cv = COVER + BAR_DIA[TIE] + BAR_DIA[size] / 2
    extra = max(0, n - 4)
    per_face, left = extra // 4, extra % 4
    layers = {cv: 2 + per_face, depth - cv: 2 + per_face}
    side = 2 * per_face + left
    if side:
        k = per_face + (1 if left else 0)
        for t in range(1, k + 1):
            y = cv + (depth - 2 * cv) * t / (k + 1)
            layers[y] = layers.get(y, 0) + (2 if t <= per_face or left >= 2 else 1)
    return [(y, cnt * a) for y, cnt in sorted(layers.items())]


def pm_curve(depth: float, width: float, bars, fc: float, fy: float):
    """φPn, φMn points (kg, kg-cm) from pure tension to the compression cap."""
    b1 = _beta1(fc)
    ast = sum(a for _y, a in bars)
    ag = depth * width
    p_max = 0.80 * 0.65 * (0.85 * fc * (ag - ast) + fy * ast)
    dt = max(y for y, _a in bars)
    pts = [(-0.9 * ast * fy, 0.0)]
    for t in range(1, 121):
        c = depth * 3.0 * t / 120
        a = min(b1 * c, depth)
        cc = 0.85 * fc * a * width
        P, M = cc, cc * (depth / 2 - a / 2)
        for y, area in bars:
            fs = max(-fy, min(fy, ES * 0.003 * (c - y) / c))
            if y < a:
                fs -= 0.85 * fc
            P += area * fs
            M += area * fs * (depth / 2 - y)
        phi = _phi(0.003 * (dt - c) / c, fy)
        pts.append((min(phi * P, p_max), phi * M))
    pts.sort()
    return pts, p_max


def phi_mn_at(curve, pu: float) -> float:
    pts, p_max = curve
    if pu > p_max:
        return 0.0
    best = 0.0
    for (p0, m0), (p1, m1) in zip(pts, pts[1:]):
        if p0 <= pu <= p1:
            m = m0 if p1 == p0 else m0 + (m1 - m0) * (pu - p0) / (p1 - p0)
            best = max(best, m)
    return best


def phi_mn_beam(as_: float, b: float, d: float, fc: float, fy: float) -> float:
    a = as_ * fy / (0.85 * fc * b)
    return 0.9 * as_ * fy * (d - a / 2)


def as_for(mu: float, b: float, d: float, fc: float, fy: float) -> float | None:
    """Tension steel for φMn ≥ Mu (kg-cm); None when the section is too small."""
    rn = mu / (0.9 * b * d * d)
    x = 1 - 2 * rn / (0.85 * fc)
    if x < 0:
        return None
    return 0.85 * fc * b * d / fy * (1 - math.sqrt(x))


def rho_max(fc: float, fy: float) -> float:
    """0.75 ρb [EIT1008]."""
    rb = 0.85 * _beta1(fc) * fc / fy * 6120 / (6120 + fy)
    return 0.75 * rb


def tie_spacing(vu: float, b: float, d: float, fc: float, nu: float = 0.0, ag: float = 0.0):
    """Two-leg RB6 tie spacing (cm) for φ(Vc + Vs) ≥ Vu, or None."""
    vc = 0.53 * math.sqrt(fc) * b * d * (1 + (nu / (140 * ag) if ag and nu > 0 else 0.0))
    vs = vu / PHI_SHEAR - vc
    if vs <= 0:
        return 999.0
    if vs > 2.1 * math.sqrt(fc) * b * d:
        return None
    return 2 * bar_area(TIE) * FY_TIE * d / vs


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def _ec(fc: float) -> float:
    return 15100 * math.sqrt(fc) * 1e4          # kg/m²


class _Frame:
    def __init__(self, direction, coord, name):
        self.direction, self.coord, self.name = direction, coord, name
        self.nodes, self.members, self.fixed = [], [], set()
        self.index = {}
        self.columns = []        # (member index, node name, level index)
        self.beams = []          # (member index, BeamResult)
        self.level_nodes = {}    # li -> [node indices]
        self.k = 0.0

    def node(self, pos, z, li):
        key = (round(pos, 6), li)
        if key not in self.index:
            self.index[key] = len(self.nodes)
            self.nodes.append((pos, z))
            if li >= 0:
                self.level_nodes.setdefault(li, []).append(self.index[key])
        return self.index[key]

    def solve(self, floor_forces: dict):
        loads = {}
        for li, F in floor_forces.items():
            ids = self.level_nodes.get(li, [])
            for n in ids:
                loads[n] = (F / len(ids), 0.0, 0.0)
        return solve_frame(self.nodes, self.members, self.fixed, loads)

    def level_disp(self, disp, li):
        ids = self.level_nodes.get(li, [])
        return max((abs(disp[n][0]) for n in ids), default=0.0)


def build_frames(b, res, col_at, z_base):
    E = _ec(b.fc_prime)
    xs, ys = b.xs, b.ys
    n_lv = len(b.levels)
    frames = []
    for direction in ("x", "y"):
        lines = range(len(ys)) if direction == "x" else range(len(xs))
        for t in lines:
            name = b.y_name(t) if direction == "x" else b.x_name(t)
            fr = _Frame(direction, ys[t] if direction == "x" else xs[t], name)
            for (i, j) in b.nodes():
                if (j if direction == "x" else i) != t:
                    continue
                pos = xs[i] if direction == "x" else ys[j]
                prev = fr.node(pos, z_base, -1)
                fr.fixed.add(prev)
                for li in range(n_lv):
                    c = col_at[(i, j, li)]
                    top = fr.node(pos, b.levels[li].elevation, li)
                    depth, width = (c.b, c.h) if direction == "x" else (c.h, c.b)
                    fr.members.append(Member(prev, top, E, depth * width,
                                             CRACKED_COLUMN * width * depth ** 3 / 12))
                    fr.columns.append((len(fr.members) - 1, b.node_name(i, j), li))
                    prev = top
            li_of = {lv.name: k for k, lv in enumerate(b.levels)}
            for x in res.beams:
                if x.kind != "beam" or not x.line_xy:
                    continue
                x0, y0, x1, y1 = x.line_xy
                along_x = abs(y1 - y0) < 1e-9
                if (direction == "x") != along_x:
                    continue
                if abs((y0 if along_x else x0) - fr.coord) > 1e-6:
                    continue
                li = li_of[x.level]
                z = b.levels[li].elevation
                p0, p1 = (x0, x1) if along_x else (y0, y1)
                n0, n1 = fr.node(min(p0, p1), z, li), fr.node(max(p0, p1), z, li)
                fr.members.append(Member(n0, n1, E, x.b * x.h, CRACKED_BEAM * x.b * x.h ** 3 / 12))
                fr.beams.append((len(fr.members) - 1, x))
            if fr.columns:
                frames.append(fr)
    return frames


def analyse(b, res, node_dead, node_live, col_at, z_base):
    """Seismic forces, drifts and member forces. Returns
    ``(SeismicResult, column_forces, beam_forces)``."""
    s = b.seismic
    if s.mode == "direct":
        sds, sd1, fa, fv = s.sds, s.sd1, 0.0, 0.0
    else:
        fa, fv = site_coefficients(s.ss, s.s1, s.site_class)
        sds, sd1 = 2 / 3 * fa * s.ss, 2 / 3 * fv * s.s1
    sdc = design_category(sds, sd1, s.category)
    sys_name, R, _om, cd, allowed = SYSTEMS[s.system]
    ie = IMPORTANCE[s.category]
    lv = b.levels
    n_lv = len(lv)
    base = lv[0].elevation
    H = lv[-1].elevation - base
    T = 0.02 * H
    ts = sd1 / sds if sds > 0 else 0.0
    sa = s.sa if (s.mode == "direct" and s.sa > 0) else (sds if T <= ts else sd1 / T)
    cs = max(sa * ie / R, 0.01, 0.044 * sds * ie)
    # seismic weight per level (dead load; 25% of live in storage uses)
    w_lvl = [0.0] * n_lv
    cm = [(0.0, 0.0)] * n_lv
    store = 0.25 if b.occupancy in STORAGE_USES else 0.0
    for li in range(1, n_lv):
        tot = mx = my = 0.0
        for (i, j) in b.nodes():
            w = node_dead[li].get((i, j), 0.0) + store * node_live[li].get((i, j), 0.0)
            c = col_at[(i, j, li)]
            w += 2400 * c.b * c.h * c.height / 2
            if li + 1 < n_lv:
                c2 = col_at[(i, j, li + 1)]
                w += 2400 * c2.b * c2.h * c2.height / 2
            tot += w
            mx += w * b.xs[i]
            my += w * b.ys[j]
        w_lvl[li] = tot
        cm[li] = (mx / tot, my / tot) if tot else (b.xs[-1] / 2, b.ys[-1] / 2)
    W = sum(w_lvl)
    V = cs * W
    k = 1.0 if T <= 0.5 else 2.0 if T >= 2.5 else 1.0 + (T - 0.5) / 2.0
    hx = [l.elevation - base for l in lv]
    denom = sum(w_lvl[li] * hx[li] ** k for li in range(1, n_lv)) or 1.0
    F = [0.0] + [V * w_lvl[li] * hx[li] ** k / denom for li in range(1, n_lv)]
    out = SeismicResult(sds, sd1, fa, fv, sdc, s.system, R, cd, ie, T, sa, cs, W, V, k)
    if sdc not in allowed:
        out.warnings.append(f"NG ประเภทการออกแบบ {sdc} ไม่อนุญาตให้ใช้{sys_name} "
                            + ("ต้องใช้โครงต้านแรงดัดแบบพิเศษ ซึ่งโปรแกรมยังไม่รองรับ" if sdc == "D"
                               else "ให้เลือกระบบที่มีความเหนียวมากขึ้น"))

    frames = build_frames(b, res, col_at, z_base)
    pattern = {li: F[li] for li in range(1, n_lv)}
    for fr in frames:
        disp, _f = fr.solve(pattern)
        top = fr.level_disp(disp, n_lv - 1)
        fr.k = float(V / top) if top > 0 else 0.0
    kx = [f for f in frames if f.direction == "x"]
    ky = [f for f in frames if f.direction == "y"]
    sum_k = {"x": sum(f.k for f in kx) or 1.0, "y": sum(f.k for f in ky) or 1.0}
    cr = {"x": sum(f.k * f.coord for f in kx) / sum_k["x"],      # y of the centre (x loading)
          "y": sum(f.k * f.coord for f in ky) / sum_k["y"]}
    J = sum(f.k * (f.coord - cr[f.direction]) ** 2 for f in frames) or 1.0
    dims = {"x": b.ys[-1], "y": b.xs[-1]}

    col_forces, beam_forces = {}, {}
    drift = {"x": [0.0] * n_lv, "y": [0.0] * n_lv}
    for fr in frames:
        d = fr.direction
        forces = {}
        for li in range(1, n_lv):
            e0 = (cm[li][1] if d == "x" else cm[li][0]) - cr[d]
            arm = fr.coord - cr[d]
            share = max(fr.k / sum_k[d] + fr.k * arm * (e0 + sg * ACCIDENTAL * dims[d]) / J
                        for sg in (1, -1))
            forces[li] = F[li] * max(share, fr.k / sum_k[d])
        disp, mf = fr.solve(forces)
        for m, _node, li in fr.columns:
            if li >= 1:
                mem = fr.members[m]
                rel = abs(float(disp[mem.j][0] - disp[mem.i][0]))
                drift[d][li] = max(drift[d][li], cd * rel / ie)
        for m, node, li in fr.columns:
            N1, V1, M1, _N2, _V2, M2 = mf[m]
            key = (node, li, d)
            col_forces[key] = (float(max(abs(M1), abs(M2))), float(abs(N1)), float(abs(V1)), float(abs(M1)))
        for m, x in fr.beams:
            _N1, V1, M1, _N2, _V2, M2 = mf[m]
            beam_forces[id(x)] = (float(max(abs(M1), abs(M2))), float(abs(V1)))

    # storeys
    lim = DRIFT_LIMIT[s.category]
    vx = 0.0
    above = [0.0] * n_lv
    for li in reversed(range(1, n_lv)):
        above[li] = sum(node_dead[li].values()) + sum(node_live[li].values()) + \
            (above[li + 1] if li + 1 < n_lv else 0.0)
    for li in reversed(range(1, n_lv)):
        vx += F[li]
        hs = lv[li].elevation - lv[li - 1].elevation
        dmax = max(drift["x"][li], drift["y"][li])
        theta = float(above[li]) * dmax * ie / (vx * hs * cd) if vx and hs else 0.0
        theta_max = min(0.25, 0.5 / cd)
        notes, ok = [], True
        if dmax > lim * hs:
            ok = False
            notes.append("การเคลื่อนตัวระหว่างชั้นเกินกำหนด ต้องเพิ่มขนาดเสา/คาน")
        if theta > theta_max:
            ok = False
            notes.append("θ เกินค่าสูงสุด โครงสร้างอาจไม่มีเสถียรภาพ")
        elif theta > 0.10:
            notes.append("θ > 0.10 ต้องคิดผล P-Δ")
        out.storeys.append(StoreyResult(lv[li].name, hx[li], w_lvl[li], F[li], vx, drift["x"][li],
                                        drift["y"][li], lim * hs, theta, ok, " ; ".join(notes)))
    out.storeys.reverse()
    return out, col_forces, beam_forces


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

BAR_OPTIONS = [(n, s) for s in ("DB12", "DB16", "DB20", "DB25") for n in range(4, 17, 2)]


def check_columns(b, res, out, col_forces, col_at, mat):
    """Strength check of every column segment; adds bars or enlarges the
    section when needed. Returns True when a section size changed."""
    fc, fy = b.fc_prime, FY[mat.main_grade]
    sds = out.sds
    imf = b.seismic.system == "IMF"
    changed = False
    for (i, j, li), c in col_at.items():
        name = b.node_name(i, j)
        D, L = c.load - c.live, c.live
        worst = None
        for d in ("x", "y"):
            M, N, Vsh, _mb = col_forces.get((name, li, d), (0.0, 0.0, 0.0, 0.0))
            combos = [((1.2 + 0.2 * sds) * D + L + N, M), ((0.9 - 0.2 * sds) * D - N, M)]
            while True:
                n, size = parse_bars(c.bars)
                depth, width = (c.b * 100, c.h * 100) if d == "x" else (c.h * 100, c.b * 100)
                curve = pm_curve(depth, width, column_bars(n, size, depth, width), fc, fy)
                ratios = []
                for pu, mu in combos:
                    cap = phi_mn_at(curve, pu)
                    ratios.append((mu * 100 / cap if cap > 0 else 99.0, pu, mu, cap))
                r = max(ratios)
                if r[0] <= 1.0:
                    break
                ag = depth * width
                for nn, ss in BAR_OPTIONS:
                    if nn * bar_area(ss) > n * bar_area(size) + 1e-9 and nn * bar_area(ss) <= 0.04 * ag \
                            and _bars_fit(nn, ss, min(c.b, c.h) * 100):
                        c.bars = f"{nn}-{ss}"
                        c.pg = nn * bar_area(ss) / ag
                        c.note = _add(c.note, "เพิ่มเหล็กรับแผ่นดินไหว")
                        break
                else:
                    if max(c.b, c.h) >= 0.60:
                        break
                    c.b, c.h = round(c.b + 0.05, 2), round(c.h + 0.05, 2)
                    c.note = _add(c.note, "ขยายหน้าตัดรับแผ่นดินไหว")
                    changed = True
            if worst is None or r[0] > worst[0][0]:
                worst = (r, d, Vsh)
        r, d, Vsh = worst
        ok = r[0] <= 1.0
        n, size = parse_bars(c.bars)
        bmin = min(c.b, c.h) * 100
        detail = ""
        dd = max(c.b, c.h) * 100 - COVER - 1.0
        s_v = tie_spacing((2.0 if imf else 1.0) * Vsh, bmin, dd, fc, (0.9 - 0.2 * sds) * D, c.b * c.h * 1e4)
        if imf:
            so = min(8 * BAR_DIA[size], 24 * BAR_DIA[TIE], bmin / 2, 30.0)
            lo = max((c.height - 0.5) / 6, max(c.b, c.h), 0.45)
            if s_v is not None:
                so = min(so, s_v)
            detail = f"ปลอกปลายเสา {TIE}@{_sp(so)} ยาว {lo:.2f} ม. จากหน้าคาน/ฐาน"
        elif s_v is not None and s_v < 999:
            detail = f"ปลอกรับแรงเฉือน {TIE}@{_sp(min(s_v, 30.0))}"
        if s_v is None:
            ok = False
            detail = "แรงเฉือนเกินกำลังหน้าตัด ต้องเพิ่มขนาดเสา"
        if not ok:
            c.ok = False
            c.note = _add(c.note, "ไม่ผ่านการตรวจแผ่นดินไหว")
        c.refs = _add_refs(c.refs)
        out.checks.append(MemberCheck("column", f"{name} {c.segment}", d,
                                      f"Pu {r[1]:,.0f} กก. Mu {r[2]:,.0f} กก.-ม.",
                                      f"φMn {r[3] / 100:,.0f} กก.-ม.", round(float(r[0]), 3), detail, bool(ok),
                                      f"{c.b:.2f}×{c.h:.2f} {c.bars}"))
    return changed


def _bars_fit(n: int, size: str, side_cm: float) -> bool:
    """Clear spacing between column bars ≥ max(1.5 db, 4 cm) [EIT1008]."""
    db = BAR_DIA[size]
    cv = COVER + BAR_DIA[TIE] + db / 2
    per_face = 2 + (n - 4) // 4 + (1 if (n - 4) % 4 else 0)
    gap = (side_cm - 2 * cv) / (per_face - 1) - db
    return gap >= max(1.5 * db, 4.0) - 1e-9


def enlarge_for_drift(b, out, col_at) -> bool:
    """Enlarge every column of a storey whose drift exceeds Δa by 5 cm."""
    li_of = {lv.name: k for k, lv in enumerate(b.levels)}
    grew = False
    for st in out.storeys:
        if max(st.drift_x, st.drift_y) <= st.limit:
            continue
        li = li_of[st.level]
        for (i, j, l2), c in col_at.items():
            if l2 == li and max(c.b, c.h) < 0.60:
                c.b, c.h = round(c.b + 0.05, 2), round(c.h + 0.05, 2)
                n, size = parse_bars(c.bars)
                c.pg = n * bar_area(size) / (c.b * c.h * 1e4)
                c.note = _add(c.note, "ขยายหน้าตัดเพื่อจำกัดการเคลื่อนตัวระหว่างชั้น")
                grew = True
    return grew


def check_beams(b, res, out, beam_forces, mat):
    fc, fy = b.fc_prime, FY[mat.main_grade]
    sds = out.sds
    imf = b.seismic.system == "IMF"
    for x in res.beams:
        if id(x) not in beam_forces:
            continue
        ME, VE = beam_forces[id(x)]
        bw, d = x.b * 100, x.h * 100 - 5.0
        MD = max(0.0, x.m_neg - x.m_neg_live)
        mu_neg = (1.2 + 0.2 * sds) * MD + 1.0 * x.m_neg_live + ME
        mu_pos = max(0.0, ME - (0.9 - 0.2 * sds) * MD)
        notes, ok = [], True
        nt, st = parse_bars(x.top)
        nb, sb = parse_bars(x.bottom)
        as_t, as_b = nt * bar_area(st), nb * bar_area(sb)
        need_t = as_for(mu_neg * 100, bw, d, fc, fy)
        need_b = as_for(mu_pos * 100, bw, d, fc, fy)
        if need_t is None or need_b is None:
            ok = False
            notes.append("หน้าตัดคานเล็กเกินไปสำหรับแรงแผ่นดินไหว")
        else:
            if imf:
                need_b = max(need_b, max(as_t, need_t) / 3)          # positive ≥ ⅓ negative at the face
            if need_t > as_t + 1e-9:
                n, s = pick_bars(need_t, bw)
                x.top = f"{n}-{s}"
                as_t = n * bar_area(s)
                notes.append("เพิ่มเหล็กบนรับแผ่นดินไหว")
            if need_b > as_b + 1e-9:
                n, s = pick_bars(need_b, bw)
                x.bottom = f"{n}-{s}"
                as_b = n * bar_area(s)
                notes.append("เพิ่มเหล็กล่างรับแผ่นดินไหว")
            if max(as_t, as_b) / (bw * d) > rho_max(fc, fy):
                ok = False
                notes.append("เหล็กเกิน 0.75ρb ต้องเพิ่มขนาดคาน")
        vu = (1.2 + 0.2 * sds) * x.v + (2.0 if imf else 1.0) * VE
        s_v = tie_spacing(vu, bw, d, fc)
        if s_v is None:
            ok = False
            notes.append("แรงเฉือนเกินกำลังหน้าตัด")
            s_v = 5.0
        db = min(BAR_DIA[parse_bars(x.top)[1]], BAR_DIA[parse_bars(x.bottom)[1]])
        if imf:
            s_end = min(d / 4, 8 * db, 24 * BAR_DIA[TIE], 30.0, s_v)
            detail = f"ปลอกปลายคาน {TIE}@{_sp(s_end)} ยาว {2 * x.h:.2f} ม."
        else:
            s_end = min(d / 2, s_v)
            detail = f"ปลอกปลายคาน {TIE}@{_sp(s_end)}"
        cap_t = phi_mn_beam(as_t, bw, d, fc, fy) / 100
        cap_b = phi_mn_beam(as_b, bw, d, fc, fy) / 100
        ratio = max(mu_neg / cap_t if cap_t else 99, mu_pos / cap_b if cap_b else 99)
        if ratio > 1.0 + 1e-6:
            ok = False
        if notes:
            x.note = _add(x.note, " ; ".join(notes))
        if not ok:
            x.ok = False
        x.refs = _add_refs(x.refs)
        out.checks.append(MemberCheck("beam", f"{x.level} {x.span}", "",
                                      f"Mu- {mu_neg:,.0f} Mu+ {mu_pos:,.0f} Vu {vu:,.0f}",
                                      f"φMn- {cap_t:,.0f} φMn+ {cap_b:,.0f}", round(ratio, 3), detail, ok,
                                      f"บน {x.top} ล่าง {x.bottom}" + (" ; " + " ; ".join(notes) if notes else "")))


def _pile_points(n: int, size: float):
    from .design import _pile_layout
    return _pile_layout(n, max(3 * size, 0.60))


def check_footings(b, res, out, col_forces, col_at, mat):
    """Pile loads (or soil pressure) under the allowable stress combinations
    with earthquake; adds piles or enlarges the footing when needed."""
    from .design import design_footing
    sds = out.sds
    piles = load_piles()
    for k, f in enumerate(res.footings):
        i, j = b.parse_node(f.node)
        c = col_at[(i, j, 0)]
        D, L = c.load - c.live, c.live
        P_design = f.load
        new = f
        for _it in range(8):
            Wf = new.weight
            worst = (-1.0, None)
            low = math.inf
            for d in ("x", "y"):
                _M, N, _V, Mb = col_forces.get((f.node, 0, d), (0.0, 0.0, 0.0, 0.0))
                combos = [((1 + 0.14 * sds) * D + 0.7 * N, 0.7 * Mb),
                          ((1 + 0.105 * sds) * D + 0.75 * L + 0.525 * N, 0.525 * Mb),
                          ((0.6 - 0.14 * sds) * D - 0.7 * N, 0.7 * Mb)]
                for P, M in combos:
                    if new.kind == "pile":
                        pts = _pile_points(new.piles, piles[new.pile]["size_m"])
                        arm = [(p[0] if d == "x" else p[1]) for p in pts]
                        s2 = sum(a * a for a in arm)
                        rmax = (P + Wf) / len(pts) + (M * max(abs(a) for a in arm) / s2 if s2 else 0.0)
                        rmin = (P + Wf) / len(pts) - (M * max(abs(a) for a in arm) / s2 if s2 else 0.0)
                        cap = new.pile_capacity
                    else:
                        A, S = new.width * new.length, new.width * new.length ** 2 / 6
                        rmax, rmin = (P + Wf) / A + M / S, (P + Wf) / A - M / S
                        cap = new.pile_capacity           # soil qa
                    if rmax / cap > worst[0]:
                        worst = (rmax / cap, (P, M, rmax, cap, d))
                    low = min(low, rmin)
            if worst[0] <= 1.0 or not new.ok:
                break
            P_design *= worst[0] * 1.02
            new = design_footing(b, mat, f.node, P_design, c.b, c.h)
        ratio, (P, M, rmax, cap, d) = worst
        notes = []
        if new is not f:
            new.load = f.load
            new.note = _add(new.note, "เพิ่มเสาเข็ม/ขยายฐานรับแผ่นดินไหว")
            res.footings[k] = new
        if new.kind == "pile" and new.piles == 1:
            notes.append("เข็มต้นเดียว: โมเมนต์ที่โคนเสาต้องให้คานคอดินรับ")
        if low < 0:
            notes.append(f"มีแรงถอน {abs(low):,.0f} {'กก./ต้น' if new.kind == 'pile' else 'กก./ตร.ม.'} ต้องตรวจ")
        ok = ratio <= 1.0
        if not ok:
            new.ok = False
            new.note = _add(new.note, "ไม่ผ่านการตรวจแผ่นดินไหว")
        new.refs = _add_refs(new.refs)
        unit = "กก./ต้น" if new.kind == "pile" else "กก./ตร.ม."
        out.checks.append(MemberCheck("footing", f.node, d, f"P {P:,.0f} กก. M {M:,.0f} กก.-ม.",
                                      f"{rmax:,.0f} ≤ {cap:,.0f} {unit}", round(ratio, 3),
                                      f"{new.piles} ต้น {new.width:.2f}×{new.length:.2f}" if new.kind == "pile"
                                      else f"{new.width:.2f}×{new.length:.2f}", ok, " ; ".join(notes)))


def _sp(s_cm: float) -> str:
    """Spacing in metres, rounded down to 2.5 cm, at least 5 cm."""
    s = max(5.0, math.floor(s_cm / 2.5 + 1e-9) * 2.5)
    return f"{s / 100:.3f}".rstrip("0").rstrip(".")


def _add(note: str, text: str) -> str:
    if not note:
        return text
    return note if text in note else f"{note} ; {text}"


def _add_refs(refs: str) -> str:
    parts = [p.strip() for p in (refs or "").split(",") if p.strip()]
    for c in ("DPT1301", "EIT1008"):
        if c not in parts:
            parts.append(c)
    return ", ".join(parts)


def run(b, res, mat, node_dead, node_live, col_at, z_base) -> SeismicResult:
    for _ in range(8):
        out, cf, bf = analyse(b, res, node_dead, node_live, col_at, z_base)
        changed = check_columns(b, res, out, cf, col_at, mat)
        changed = enlarge_for_drift(b, out, col_at) or changed
        if not changed:
            break
    check_beams(b, res, out, bf, mat)
    check_footings(b, res, out, cf, col_at, mat)
    return out
