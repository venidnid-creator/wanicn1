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
REFS = cite("MI2567-27", "AISC-ASD", "MI2567-8", "STATICS", "QD-PURLIN")


@dataclass
class Tube:
    side: float                  # mm
    t: float

    @property
    def name(self) -> str:
        return f"□{self.side:g}x{self.side:g}x{self.t:g}"

    @property
    def area(self) -> float:     # cm²
        b, h = self.side / 10, (self.side - 2 * self.t) / 10
        return b * b - h * h

    @property
    def inertia(self) -> float:  # cm⁴
        b, h = self.side / 10, (self.side - 2 * self.t) / 10
        return (b ** 4 - h ** 4) / 12

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
    force: float = 0.0           # kg, + tension


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


def geometry(span: float, slope_deg: float, depth: float, panels: int):
    """Nodes (x, z) and members of a pitched Pratt truss: bottom nodes 0…n,
    top nodes n+1…2n+1 above them; diagonals fall towards midspan."""
    n = panels
    t = math.tan(math.radians(slope_deg))
    xs = [span * k / n for k in range(n + 1)]
    nodes = [(x, 0.0) for x in xs] + [(x, depth + min(x, span - x) * t) for x in xs]
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


def _check(group, members, tube, w_chord):
    """Worst ratio of a member group with this tube: (ratio, text)."""
    worst = (0.0, "")
    A, r = tube.area, tube.r
    for m in members:
        L = m.length * 100
        lam = L / r
        if m.force >= 0:
            ratio = m.force / A / (0.60 * FY_STEEL)
            if lam > 300:
                ratio = max(ratio, 1.01)
            text = f"ดึง {m.force:,.0f} กก. L/r {lam:.0f}"
        else:
            fa = -m.force / A
            Fa = fa_allow(lam)
            ratio = fa / Fa
            if group == "top" and w_chord:
                M = w_chord * m.length ** 2 / 10 * 100           # kg-cm
                fb, Fb = M / tube.s, 0.60 * FY_STEEL
                if fa / Fa <= 0.15:
                    ratio = fa / Fa + fb / Fb
                else:
                    Fe = 12 * math.pi ** 2 * E_STEEL / (23 * lam ** 2)
                    ratio = fa / Fa + 0.85 * fb / ((1 - fa / Fe) * Fb) if fa < Fe else 9.9
            if lam > 200:
                ratio = max(ratio, 1.01)
            text = f"อัด {-m.force:,.0f} กก. KL/r {lam:.0f}"
        if ratio > worst[0]:
            worst = (ratio, text)
    return worst


def design_truss(b, roof_res, line: str, span: float, spacing: float, supports=()) -> TrussResult:
    r = b.roof
    depth = max(0.30, span / 20)                         # QuickDesign default D = L/20
    panels = max(4, 2 * math.ceil(span / 2 / 1.5))       # panels about 1.5 m, even
    nodes, mem = geometry(span, r.slope_deg, depth, panels)
    n = panels
    top = lambda k: n + 1 + k
    cos = math.cos(math.radians(r.slope_deg))
    out = TrussResult(line, span, nodes[top(n // 2)][1] - depth, depth, panels, spacing, supports=supports)
    tubes = [Tube(*t) for t in TUBES]
    sec = {"top": tubes[0], "bottom": tubes[0], "web": tubes[0]}
    for _round in range(4):
        sw = sum(sec[m.group].kg_m * m.length for m in mem)
        for part in ("total", "live"):
            w_plan = roof_res.live_plan if part == "live" else roof_res.load_plan + sw / (span + 2 * r.overhang) / spacing
            loads = {}
            for k in range(n + 1):
                trib = span / n * (0.5 if k in (0, n) else 1.0) + (r.overhang if k in (0, n) else 0.0)
                loads[top(k)] = (0.0, -w_plan * spacing * trib)
            areas = [sec[m.group].area for m in mem]
            U, forces = solve_truss(nodes, mem, areas, loads, {0: (True, True), n: (False, True)})
            if part == "total":
                for m, f in zip(mem, forces):
                    m.force = f
                out.reaction = sum(-fz for _fx, fz in loads.values()) / 2
                d_total = abs(U[2 * (n // 2) + 1]) * 100
            else:
                out.reaction_live = sum(-fz for _fx, fz in loads.values()) / 2
                d_live = abs(U[2 * (n // 2) + 1]) * 100
        w_chord = roof_res.load_plan * spacing * cos                   # purlins between the joints
        changed = False
        for g in ("top", "bottom", "web"):
            group = [m for m in mem if m.group == g]
            for tube in tubes:
                ratio, text = _check(g, group, tube, w_chord if g == "top" else 0.0)
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
    if any(v[0] > 1.0 for v in out.ratios.values()):
        out.ok = False
        notes.append("ท่อเหล็กใหญ่สุดในตารางยังไม่พอ")
    if d_live > out.deflection[2] or d_total > out.deflection[3]:
        out.ok = False
        notes.append("ระยะแอ่นตัวเกินเกณฑ์ตาราง 1")
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
        t = design_truss(b, roof_res, name, span, spacing, (a, c))
        out.append(t)
        for node in (a, c):
            tot, live = reac.get(node, (0.0, 0.0))
            reac[node] = (tot + t.reaction, live + t.reaction_live)
    groups: dict = {}
    for t in out:
        key = tuple(t.sections[g].name for g in ("top", "bottom", "web")) + (round(t.span, 2),)
        groups.setdefault(key, []).append(t)
    for k, (_key, ts) in enumerate(sorted(groups.items(), key=lambda kv: -max(t.reaction for t in kv[1])), 1):
        for t in ts:
            t.mark = f"T{k}"
    return out, reac
