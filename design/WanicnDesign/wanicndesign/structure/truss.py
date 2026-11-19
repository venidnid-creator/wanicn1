# -*- coding: utf-8 -*-
"""Steel roof trusses — allowable strength design.

A pitched Pratt truss stands on the two end columns of every grid line
across the building (the ridge runs along the long side). Purlins span from
truss to truss. The truss is analysed pin-jointed by the stiffness method
[STATICS] under the roof load brought by the purlins to the top chord
joints, plus its own weight.

Members are square steel tubes (มอก. 107). Their properties are computed
from the dimensions (square corners, slightly on the high side of the
catalogue values). Steel of unspecified standard: Fy ≤ 235 MPa
(2,400 ksc), E = 200,000 MPa — ประกาศ มท. 2567 ข้อ 27 (1) (ข), (3)
[MI2567-27]:

* tension: Ft = 0.60 Fy; slenderness L/r ≤ 300 (ข้อ 27 (6) (ข));
* compression: AISC ASD Fa = [1 − (KL/r)²/2Cc²] Fy / FS, FS = 5/3 + 3λ/8Cc −
  λ³/8Cc³, or 12π²E/23(KL/r)² beyond Cc; KL/r ≤ 200 (ข้อ 27 (7) (ข)), K = 1
  [AISC-ASD];
* the top chord also bends under the purlins between joints, M = wa²/10:
  fa/Fa + fb/Fb ≤ 1 when fa/Fa ≤ 0.15, otherwise
  fa/Fa + Cm fb / ((1 − fa/F'e) Fb) ≤ 1 with Cm = 0.85, Fb = 0.60 Fy;
* deflection of the bottom chord against ตาราง 1 for roofs by the ceiling
  type (live and dead + live) [MI2567-8].
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..standards import cite

FY_STEEL = 2400.0                # ksc, ข้อ 27 (1) (ข)
E_STEEL = 2.04e6                 # ksc (200,000 MPa)
STEEL_KG_M3 = 7850.0
CC = math.sqrt(2 * math.pi ** 2 * E_STEEL / FY_STEEL)

#: Square tubes (มอก. 107): side × thickness, mm.
TUBES = [(38, 1.6), (38, 2.3), (50, 1.6), (50, 2.3), (50, 3.2), (75, 2.3), (75, 3.2), (75, 4.5), (100, 2.3),
         (100, 3.2), (100, 4.5), (125, 3.2), (125, 4.5), (150, 4.5), (150, 6.0)]
REFS = cite("MI2567-27", "AISC-ASD", "MI2567-8", "STATICS", "QD-PURLIN", "STEEL-TUBE", "MI2567-22", "WIND-ROOF",
            "MR2566-6", "MI2567-27C")


def _rounded_square(side: float, r: float, n: int = 24):
    """Polygon of a square of ``side`` with corner radius ``r`` centred on 0, anticlockwise."""
    h = side / 2
    pts = []
    for cx, cy, a0 in ((h - r, h - r, 0), (-h + r, h - r, 90), (-h + r, -h + r, 180), (h - r, -h + r, 270)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)) if r > 0 else (cx, cy))
    return pts


def _poly_props(pts):
    """Area and second moment about the x axis through 0 of a closed polygon."""
    A = Ix = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        c = x0 * y1 - x1 * y0
        A += c
        Ix += c * (y0 * y0 + y0 * y1 + y1 * y1)
    return A / 2, Ix / 12


@dataclass
class Tube:
    """Cold-formed square hollow section with the corner radii of EN 10219-2
    (outside 2t, inside t) [STEEL-TUBE]."""
    side: float                  # mm
    t: float

    @property
    def name(self) -> str:
        return f"□{self.side:g}x{self.side:g}x{self.t:g}"

    def _props(self):
        b, t = self.side / 10, self.t / 10
        Ao, Io = _poly_props(_rounded_square(b, 2 * t))
        Ai, Ii = _poly_props(_rounded_square(b - 2 * t, t))
        return Ao - Ai, Io - Ii

    @property
    def area(self) -> float:     # cm²
        return self._props()[0]

    @property
    def inertia(self) -> float:  # cm⁴
        return self._props()[1]

    @property
    def r(self) -> float:
        return math.sqrt(self.inertia / self.area)

    @property
    def s(self) -> float:        # section modulus, cm³
        return self.inertia / (self.side / 20)

    @property
    def kg_m(self) -> float:
        return self.area * 1e-4 * STEEL_KG_M3


def fa_allow(kl_r: float) -> float:
    """AISC ASD allowable compressive stress, ksc."""
    if kl_r <= CC:
        fs = 5 / 3 + 3 * kl_r / (8 * CC) - kl_r ** 3 / (8 * CC ** 3)
        return (1 - kl_r ** 2 / (2 * CC ** 2)) * FY_STEEL / fs
    return 12 * math.pi ** 2 * E_STEEL / (23 * kl_r ** 2)


@dataclass
class TrussMember:
    group: str                   # "top", "bottom", "web"
    i: int
    j: int
    length: float                # m
    force: float = 0.0           # kg, + tension (dead + live)
    force_up: float = 0.0        # kg under 0.6D + W (uplift), 0 when the roof is not lifted


@dataclass
class TrussResult:
    line: str                    # grid line the truss stands on
    span: float
    rise: float
    depth: float                 # at the supports
    panels: int
    spacing: float               # tributary width, m
    sections: dict = field(default_factory=dict)      # group -> Tube
    ratios: dict = field(default_factory=dict)        # group -> (ratio, text)
    reaction: float = 0.0        # kg per support, total
    reaction_live: float = 0.0
    deflection: tuple = (0.0, 0.0, 0.0, 0.0)          # live, total, limit live, limit total (cm)
    weight: float = 0.0          # kg
    nodes: list = field(default_factory=list)
    members: list = field(default_factory=list)
    supports: tuple = ()         # grid nodes (a, c)
    ok: bool = True
    note: str = ""
    mark: str = ""
    refs: str = REFS
    hip_cut: float | None = None # step-down hip truss: distance from the hip end, m
    uplift: float = 0.0          # net upward roof load under 0.6D + W, kg/m² of plan (0 = none)
    reaction_up: float = 0.0     # support reaction under 0.6D + W (negative = pulls up), kg
    welds: dict = field(default_factory=dict)   # group -> (force, capacity)
    seat: dict = field(default_factory=dict)    # base plate and anchor bolts


def geometry(span: float, slope_deg: float, depth: float, panels: int, hip_cut: float | None = None,
             mono: bool = False):
    """Nodes (x, z) and members of a pitched Pratt truss: bottom nodes 0…n,
    top nodes n+1…2n+1 above them; diagonals fall towards midspan. A
    step-down hip truss (``hip_cut`` = its distance from the hip end, m)
    has its top chord flat where the hip plane passes below the ridge."""
    n = panels
    t = math.tan(math.radians(slope_deg))
    xs = [span * k / n for k in range(n + 1)]
    cap = span if hip_cut is None else hip_cut
    if mono:                                            # shed roof: one slope from the low side (x = 0)
        nodes = [(x, 0.0) for x in xs] + [(x, depth + x * t) for x in xs]
    else:
        nodes = [(x, 0.0) for x in xs] + [(x, depth + min(x, span - x, cap) * t) for x in xs]
    top = lambda k: n + 1 + k
    mem = []
    for k in range(n):
        mem.append(TrussMember("bottom", k, k + 1, 0.0))
        mem.append(TrussMember("top", top(k), top(k + 1), 0.0))
        if k < n / 2:
            mem.append(TrussMember("web", top(k), k + 1, 0.0))
        else:
            mem.append(TrussMember("web", k, top(k + 1), 0.0))
    for k in range(n + 1):
        mem.append(TrussMember("web", k, top(k), 0.0))
    for m in mem:
        (x0, z0), (x1, z1) = nodes[m.i], nodes[m.j]
        m.length = math.hypot(x1 - x0, z1 - z0)
    return nodes, mem


def solve_truss(nodes, members, areas, loads, supports):
    """Pin-jointed plane truss: ``loads`` {node: (Fx, Fz)}, ``supports``
    {node: (fix_x, fix_z)}. Returns (displacements, member forces)."""
    n = len(nodes)
    K = np.zeros((2 * n, 2 * n))
    F = np.zeros(2 * n)
    E = E_STEEL * 1e4                                   # kg/m²
    geo = []
    for m, A in zip(members, areas):
        (x0, z0), (x1, z1) = nodes[m.i], nodes[m.j]
        L = math.hypot(x1 - x0, z1 - z0)
        c, s = (x1 - x0) / L, (z1 - z0) / L
        k = E * A * 1e-4 / L
        t = np.array([-c, -s, c, s])
        d = [2 * m.i, 2 * m.i + 1, 2 * m.j, 2 * m.j + 1]
        K[np.ix_(d, d)] += k * np.outer(t, t)
        geo.append((k, t, d))
    for node, (fx, fz) in loads.items():
        F[2 * node] += fx
        F[2 * node + 1] += fz
    fixed = [2 * nd + a for nd, (fx, fz) in supports.items() for a, on in ((0, fx), (1, fz)) if on]
    free = [d for d in range(2 * n) if d not in fixed]
    U = np.zeros(2 * n)
    U[free] = np.linalg.solve(K[np.ix_(free, free)], F[free])
    forces = [float(k * (t @ U[d])) for k, t, d in geo]
    return U, forces


# ---------------------------------------------------------------------------
# Wind uplift on the roof — ประกาศ มท. 2567 ข้อ 22 (roofs by มยผ. 1311), ผนวก ก
# ---------------------------------------------------------------------------
IW = {"low": 0.8, "normal": 1.0, "high": 1.15, "very_high": 1.15}     # importance factor (มยผ. 1311)
RHO_AIR = 1.25                                                        # kg/m³


def roof_uplift(b) -> tuple[float, str]:
    """Net upward wind pressure on the roof (kg/m² of plan) and how it was found:
    p = Iw · q · Ce · (CpCg external + CpiCgi internal), q = ½ρV̄², V̄ = V50 of the
    province group (× TF for buildings of very high importance) [MI2567-22],
    Ce = (h/10)^0.2 ≥ 0.9 open or 0.7 (h/12)^0.3 ≥ 0.7 rough terrain, net
    coefficient from the roof (default 1.6 = −1.3 outside − 0.3 inside, the
    severest low-rise roof value, safe for every slope) [WIND-ROOF]."""
    from ..standards import provinces
    data = provinces()
    grp = data["provinces"].get(b.province, {}).get("wind_group", "1")
    g = data["wind_groups"][grp]
    v = g["v50"] * (g["tf"] if b.wind.importance == "very_high" else 1.0)
    q = 0.5 * RHO_AIR * v * v / 9.81
    lv = b.levels
    from .roofs import geometry as roof_geometry
    rise = roof_geometry(b).rise if any(x.slab == "roof" for x in lv) else 0.0
    h = max(1.0, lv[-1].elevation - lv[0].elevation + rise / 2)
    ce = max(0.9, (h / 10) ** 0.2) if b.wind.terrain == "open" else max(0.7, 0.7 * (h / 12) ** 0.3)
    iw = IW.get(b.wind.importance, 1.0)
    p = iw * q * ce * b.roof.uplift_coef
    where = b.province or "ไม่ระบุจังหวัด (ใช้กลุ่ม 1)"
    return p, (f"{where} กลุ่ม {grp} V̄ = {v:.1f} ม./วินาที, q = {q:.1f}, Ce = {ce:.2f}, Iw = {iw:g}, "
               f"สัมประสิทธิ์สุทธิ {b.roof.uplift_coef:g} → แรงยก {p:.1f} กก./ตร.ม.")


# ---------------------------------------------------------------------------
# Welds, base plate, anchor bolts — ประกาศ มท. 2567 ข้อ 27 (4) (จ), (ฉ)
# ---------------------------------------------------------------------------
FEXX = 4220.0                    # ksc, E60XX electrode (E6013 in common use)
OMEGA_WELD = 2.00                # fillet weld, ข้อ 27 (4) (ฉ)
OMEGA_BOLT = 2.00                # bolts in bearing connections, ข้อ 27 (4) (จ)
FU_BOLT = 4080.0                 # ksc, grade 4.6 bolts / anchor rods (400 MPa)
BOLTS = [("M12", 1.2), ("M16", 1.6), ("M20", 2.0), ("M24", 2.4)]


def weld_capacity(tube: Tube) -> float:
    """All-round fillet weld of a tube end: leg = tube wall (≥ 3 mm),
    Rn = 0.6 FEXX × throat × length, allowable Rn / 2.00 (kg)."""
    leg = max(0.3, tube.t / 10)
    return 0.6 * FEXX * 0.707 * leg * 4 * tube.side / 10 / OMEGA_WELD


def base_plate(reaction: float, uplift: float, col_b: float, col_h: float, tube: Tube, fc: float) -> dict:
    """Seat of a truss on a concrete column: bearing fp ≤ 0.35 fc' (AISC ASD
    J9), plate t = 2m√(fp/Fy) and for the bolt pull t = √(4T/Fy), two
    anchor bolts for the uplift with Rn = 0.75 Fu Ab, allowable Rn/2.00."""
    N = max(tube.side / 10 + 8.0, min(col_b, col_h) * 100 - 4.0)        # cm, 2 cm inside the column edge
    A1 = N * N
    fp = reaction / A1
    Fp = 0.35 * fc
    m = (N - 0.95 * tube.side / 10) / 2
    t_bear = 2 * m * math.sqrt(fp / FY_STEEL)
    tension = max(0.0, -uplift)
    for name, d in BOLTS:
        cap = 0.75 * FU_BOLT * math.pi * d * d / 4 / OMEGA_BOLT
        if 2 * cap >= tension:
            break
    t_pull = math.sqrt(4 * (tension / 2) / FY_STEEL) if tension else 0.0
    t = max(0.6, t_bear, t_pull)
    t = math.ceil(t * 10 / 3 - 1e-9) * 3 / 10                         # 6, 9, 12 … mm
    return {"plate": f"PL {N * 10:.0f}x{N * 10:.0f}x{t * 10:.0f} มม.", "fp": fp, "Fp": Fp, "bolts": f"2-{name}",
            "bolt_cap": 2 * cap, "tension": tension, "ok": fp <= Fp and 2 * cap >= tension, "bolt_d": d}


def _check(group, members, tube, w_chord, brace=0.0):
    """Worst ratio of a member group with this tube over the gravity and the
    uplift forces: (ratio, text). ``brace``: unbraced length (m) of the bottom
    chord out of plane when the uplift puts it in compression."""
    worst = (0.0, "")
    A, r = tube.area, tube.r
    cases = []
    for m in members:
        cases.append((m, m.force, m.length, w_chord))
        if m.force_up:
            cases.append((m, m.force_up, max(m.length, brace) if group == "bottom" else m.length, 0.0))
    for m, force, length, wc in cases:
        L = length * 100
        lam = L / r
        if force >= 0:
            ratio = force / A / (0.60 * FY_STEEL)
            if lam > 300:
                ratio = max(ratio, 1.01)
            text = f"ดึง {force:,.0f} กก. L/r {lam:.0f}"
        else:
            fa = -force / A
            Fa = fa_allow(lam)
            ratio = fa / Fa
            if group == "top" and wc:
                M = wc * m.length ** 2 / 10 * 100                # kg-cm
                fb, Fb = M / tube.s, 0.60 * FY_STEEL
                if fa / Fa <= 0.15:
                    ratio = fa / Fa + fb / Fb
                else:
                    Fe = 12 * math.pi ** 2 * E_STEEL / (23 * lam ** 2)
                    ratio = fa / Fa + 0.85 * fb / ((1 - fa / Fe) * Fb) if fa < Fe else 9.9
            if lam > 200:
                ratio = max(ratio, 1.01)
            text = f"อัด {-force:,.0f} กก. KL/r {lam:.0f}" + (" (แรงยก)" if force is m.force_up else "")
        if ratio > worst[0]:
            worst = (ratio, text)
    return worst


def design_truss(b, roof_res, line: str, span: float, spacing: float, supports=(), hip_cut=None,
                 col=(0.2, 0.2)) -> TrussResult:
    r = b.roof
    depth = max(0.30, span / 20)                         # QuickDesign default D = L/20
    panels = max(4, 2 * math.ceil(span / 2 / 1.5))       # panels about 1.5 m, even
    nodes, mem = geometry(span, r.slope_deg, depth, panels, hip_cut, r.shape == "shed")
    n = panels
    top = lambda k: n + 1 + k
    cos = math.cos(math.radians(r.slope_deg))
    rise = max(z for _x, z in nodes) - depth
    out = TrussResult(line, span, rise, depth, panels, spacing, supports=supports, hip_cut=hip_cut)
    p_up, _info = roof_uplift(b)
    dead_plan = roof_res.load_plan - roof_res.live_plan
    tubes = [Tube(*t) for t in TUBES]
    sec = {"top": tubes[0], "bottom": tubes[0], "web": tubes[0]}
    brace = r.chord_brace or 2 * span / n
    for _round in range(5):
        sw = sum(sec[m.group].kg_m * m.length for m in mem)
        sw_plan = sw / (span + 2 * r.overhang) / spacing
        cases = {"total": roof_res.load_plan + sw_plan, "live": roof_res.live_plan,
                 "uplift": 0.6 * (dead_plan + sw_plan) - p_up}             # กฎกระทรวง 2566 ข้อ 6 (2)
        for part, w_plan in cases.items():
            loads = {}
            for k in range(n + 1):
                trib = span / n * (0.5 if k in (0, n) else 1.0) + (r.overhang if k in (0, n) else 0.0)
                loads[top(k)] = (0.0, -w_plan * spacing * trib)
            areas = [sec[m.group].area for m in mem]
            U, forces = solve_truss(nodes, mem, areas, loads, {0: (True, True), n: (False, True)})
            R = sum(-fz for _fx, fz in loads.values()) / 2
            mid = abs(U[2 * (n // 2) + 1]) * 100
            if part == "total":
                for m, f in zip(mem, forces):
                    m.force = f
                out.reaction, d_total = R, mid
            elif part == "live":
                out.reaction_live, d_live = R, mid
            else:
                out.uplift = max(0.0, -w_plan)
                out.reaction_up = R
                for m, f in zip(mem, forces):
                    m.force_up = f if w_plan < 0 else 0.0
        w_chord = roof_res.load_plan * spacing * cos                   # purlins between the joints
        changed = False
        for g in ("top", "bottom", "web"):
            group = [m for m in mem if m.group == g]
            for tube in tubes:
                ratio, text = _check(g, group, tube, w_chord if g == "top" else 0.0, brace)
                if ratio <= 1.0:
                    break
            if tube.name != sec[g].name:
                changed = True
            sec[g] = tube
            out.ratios[g] = (ratio, text)
        if not changed:
            break
    from .design import ROOF_DEFL
    n_live, n_total = ROOF_DEFL.get(r.ceiling, ROOF_DEFL["board"])
    out.deflection = (d_live, d_total, span * 100 / n_live, span * 100 / n_total)
    out.sections = sec
    out.weight = sum(sec[m.group].kg_m * m.length for m in mem)
    out.nodes, out.members = nodes, mem
    notes = []
    for g in ("top", "bottom", "web"):
        F = max(max(abs(m.force), abs(m.force_up)) for m in mem if m.group == g)
        out.welds[g] = (F, weld_capacity(sec[g]))
    out.seat = base_plate(out.reaction, out.reaction_up, col[0], col[1], sec["bottom"], b.fc_prime)
    if any(v[0] > 1.0 for v in out.ratios.values()):
        out.ok = False
        notes.append("ท่อเหล็กใหญ่สุดในตารางยังไม่พอ")
    if any(F > cap for F, cap in out.welds.values()):
        out.ok = False
        notes.append("รอยเชื่อมรอบท่อไม่พอ ต้องใช้แผ่นประกับ")
    if not out.seat["ok"]:
        out.ok = False
        notes.append("แผ่นรองฐานหรือสลักยึดไม่พอ")
    if d_live > out.deflection[2] or d_total > out.deflection[3]:
        out.ok = False
        notes.append("ระยะแอ่นตัวเกินเกณฑ์ตาราง 1")
    if out.uplift:
        notes.append(f"แรงยกสุทธิ {out.uplift:.0f} กก./ตร.ม. (0.6D + W) ค้ำยันจันทันล่างทุก {brace:.2f} ม.")
    if hip_cut is not None:
        notes.append(f"โครงถักขั้นบันไดของหลังคาปั้นหยา ห่างปลาย {hip_cut:.2f} ม.")
    notes.append(f"แอ่น {d_total * 10:.1f}/{out.deflection[3] * 10:.1f} มม. (จร {d_live * 10:.1f}/{out.deflection[2] * 10:.1f})")
    out.note = " ; ".join(notes)
    return out


def design_trusses(b, roof_res):
    """One truss per grid line across the building; returns (trusses,
    {node: (total, live)} reactions at the roof level)."""
    along_x = b.xs[-1] >= b.ys[-1]                      # ridge along the long side
    lines = range(len(b.xs)) if along_x else range(len(b.ys))
    coords = b.xs if along_x else b.ys
    span = b.ys[-1] if along_x else b.xs[-1]
    out, reac = [], {}
    for k in lines:
        lo = coords[k] - coords[k - 1] if k > 0 else 0.0
        hi = coords[k + 1] - coords[k] if k + 1 < len(coords) else 0.0
        spacing = (lo + hi) / 2
        a = (k, 0) if along_x else (0, k)
        c = (k, len(b.ys) - 1) if along_x else (len(b.xs) - 1, k)
        if not (b.has_node(*a) and b.has_node(*c)):
            continue
        name = b.x_name(k) if along_x else b.y_name(k)
        hip = None
        if b.roof.shape in ("hip", "manila"):           # step-down trusses near the hip ends
            dist = min(coords[k], coords[-1] - coords[k]) + b.roof.overhang
            f = 1.0 if b.roof.shape == "hip" else min(max(b.roof.manila_ratio, 0.1), 0.9)
            if dist < f * (span / 2 + b.roof.overhang) - 1e-6:
                hip = dist
        col = (b.column_width, b.column_depth)
        t = design_truss(b, roof_res, name, span, spacing, (a, c), hip, col)
        out.append(t)
        for node in (a, c):
            tot, live = reac.get(node, (0.0, 0.0))
            reac[node] = (tot + t.reaction, live + t.reaction_live)
    groups: dict = {}
    for t in out:
        key = tuple(t.sections[g].name for g in ("top", "bottom", "web")) + (round(t.span, 2),
                                                                           round(t.hip_cut or 0, 2))
        groups.setdefault(key, []).append(t)
    for k, (_key, ts) in enumerate(sorted(groups.items(), key=lambda kv: -max(t.reaction for t in kv[1])), 1):
        for t in ts:
            t.mark = f"T{k}"
    return out, reac
