# -*- coding: utf-8 -*-
"""Design chain: roof → slabs → beams → columns → footings → piles.

Units inside: lengths m, loads kg, moments kg-m; section checks in cm and
ksc. Working stress design. Every value and formula carries a reference
code from :mod:`wanicndesign.standards` (the ``refs`` of each result).
Every result needs a licensed engineer's check and signature before use.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..standards import LL_REDUCTION_MR6, NO_REDUCTION, NO_REDUCTION_ABOVE, cite, ll_reduction
from .analysis import continuous_beam, partial_udl
from .building import ROOF_COVER_LOAD, WALL_LOAD, Building
from .materials import CONCRETE_KG_M3, ES, FY, Concrete
from .rules import (SLAB_MIN_THICKNESS, beam_deflection, beam_offset, beam_rho_min, footing_offset, slab_max_spacing,
                    slab_min_ratio, slab_offset, stirrup_max_spacing, tie_bar, tie_spacing_max)
from .sections import BAR_DIA, bar_area, load_c_sections, load_piles, pick_bars, pick_spacing

PURLIN_FB = 1400.0          # ksc [QD-PURLIN]; ≈ 0.6 Fy of SS400 [AISC-ASD]
PURLIN_DEFL = 240           # L/240 [QD-PURLIN]
MAX_BEAM_DEPTH = 1.00       # m, auto-sizing stops here
MAX_COLUMN = 0.60           # m
MAX_PILES = 5               # piles per footing (QuickDesign limit)
STIRRUP = "RB6"

# ---------------------------------------------------------------------------
# Two-way slab coefficients [EIT1007-SLAB], ACI 318-63 method 2.
# Short span: m = 1.0 … 0.5; per case (number of discontinuous edges):
#   (negative at continuous edge, negative at discontinuous edge, positive)
# Long span (all m): (neg continuous, neg discontinuous, positive).
# Case 5 is also printed in the QuickDesign appendix [QD-SLAB5] and matches.
# ---------------------------------------------------------------------------
SLAB_M = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]
SLAB_CASES = {
    1: ([0.033, 0.040, 0.048, 0.055, 0.063, 0.083], [0, 0, 0, 0, 0, 0],
        [0.025, 0.030, 0.036, 0.041, 0.047, 0.062], (0.033, 0.0, 0.025)),
    2: ([0.041, 0.048, 0.055, 0.062, 0.069, 0.085], [0.021, 0.024, 0.027, 0.031, 0.035, 0.042],
        [0.031, 0.036, 0.041, 0.047, 0.052, 0.064], (0.041, 0.021, 0.031)),
    3: ([0.049, 0.057, 0.064, 0.071, 0.078, 0.090], [0.025, 0.028, 0.032, 0.036, 0.039, 0.045],
        [0.037, 0.043, 0.048, 0.054, 0.059, 0.068], (0.049, 0.025, 0.037)),
    4: ([0.058, 0.066, 0.074, 0.082, 0.090, 0.098], [0.029, 0.033, 0.037, 0.041, 0.045, 0.049],
        [0.044, 0.050, 0.056, 0.062, 0.068, 0.074], (0.058, 0.029, 0.044)),
    5: ([0, 0, 0, 0, 0, 0], [0.033, 0.038, 0.043, 0.047, 0.053, 0.055],
        [0.050, 0.057, 0.064, 0.072, 0.080, 0.083], (0.0, 0.033, 0.050)),
}
# kept for older callers
CASE5_M, CASE5_NEG, CASE5_POS = SLAB_M, SLAB_CASES[5][1], SLAB_CASES[5][2]


def _interp(m: float, xs: list[float], ys: list[float]) -> float:
    m = min(max(m, xs[-1]), xs[0])
    for k in range(len(xs) - 1):
        a, b = xs[k], xs[k + 1]
        if b <= m <= a:
            t = (a - m) / (a - b)
            return ys[k] + t * (ys[k + 1] - ys[k])
    return ys[-1]


def _round_up(v: float, step: float) -> float:
    return math.ceil(v / step - 1e-9) * step


def _round_down(v: float, step: float) -> float:
    return math.floor(v / step + 1e-9) * step


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@dataclass
class SteelMember:
    role: str
    span: float
    mx: float
    my: float
    sx_req: float
    sy_req: float
    section: str
    zx: float
    zy: float
    kg_m: float
    ok: bool
    source: str = ""
    deflection: float = 0.0        # cm
    defl_limit: float = 0.0        # cm
    refs: str = ""


@dataclass
class RoofResult:
    load_plan: float               # kg/m² of plan, to the roof beams
    live_plan: float               # of which live load
    plan_area: float
    slope_area: float
    ridge: float
    hips: float
    eave: float
    purlin: SteelMember
    rafter: SteelMember
    steel_kg: float
    refs: str = ""


@dataclass
class SlabResult:
    level: str
    panel: str
    mark: str
    kind: str                      # one-way, two-way, on-ground
    lx: float
    ly: float
    m: float
    load: float                    # kg/m²
    m_pos: float                   # kg-m per m, short direction
    m_neg: float
    m_long: float
    thickness: float
    d_req: float                   # cm
    bars_short: str
    bars_long: str
    bars_top: str
    ok: bool
    note: str = ""
    case: int = 0                  # two-way case 1–5
    refs: str = ""
    rect: tuple = ()               # (x0, y0, x1, y1) in plan, m


@dataclass
class BeamResult:
    level: str
    line: str
    span: str
    mark: str
    b: float
    h: float
    length: float
    w: float                       # kg/m total
    m_neg: float
    m_pos: float
    v: float
    d_req: float                   # cm
    as_top: float
    as_bot: float
    top: str
    bottom: str
    stirrup: str
    ok: bool
    note: str = ""
    h_min: float = 0.0             # depth needing no deflection check
    refs: str = ""
    line_xy: tuple = ()            # (x0, y0, x1, y1) in plan, m
    kind: str = "beam"             # beam, secondary
    d_off: float = 5.0             # top of beam to the main bars, cm
    deflection: float = 0.0        # long-term total deflection, cm (ประกาศ มท. 2567 ตาราง 1)
    m_neg_live: float = 0.0        # live-load share of m_neg (earthquake combinations)
    z_top: float | None = None     # top of beam when not at its level (stair beam BT)
    load_w: float = 0.0            # gravity loads on a frame beam (total; self weight included), kg/m
    load_pts: list = field(default_factory=list)       # [(a from the lower node, P)]
    load_w_live: float = 0.0
    load_pts_live: list = field(default_factory=list)


@dataclass
class ColumnResult:
    node: str
    segment: str
    height: float
    load: float                    # kg at the bottom of the segment
    b: float
    h: float
    pg: float
    bars: str
    ties: str
    mark: str = ""
    ok: bool = True
    note: str = ""
    live_reduced: float = 0.0      # kg of live load taken off [MR2566-13]
    refs: str = ""
    live: float = 0.0              # live-load share of ``load`` (after reduction), kg
    m_dx: float = 0.0              # gravity end moments from the frame analysis, kg-m (dead / live,
    m_lx: float = 0.0              # bending in the X frame / in the Y frame)
    m_dy: float = 0.0
    m_ly: float = 0.0
    slender: str = ""              # slenderness and moment magnifier summary


@dataclass
class FootingResult:
    node: str
    load: float                    # column load, kg
    kind: str
    piles: int
    pile: str
    pile_capacity: float
    width: float
    length: float
    thickness: float
    bars_x: str
    bars_y: str
    weight: float
    mark: str = ""
    ok: bool = True
    note: str = ""
    refs: str = ""
    nodes: list = field(default_factory=list)   # columns on a combined footing
    cx: float | None = None                     # centre of a combined footing, m
    cy: float | None = None

    def center(self, b) -> tuple[float, float]:
        if self.cx is not None:
            return self.cx, self.cy
        i, j = b.parse_node(self.node)
        return b.xs[i], b.ys[j]


@dataclass
class DesignResult:
    building: Building
    concrete: Concrete
    roof: RoofResult | None = None
    slabs: list = field(default_factory=list)
    beams: list = field(default_factory=list)
    columns: list = field(default_factory=list)
    footings: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    stairs: list = field(default_factory=list)
    seismic: object = None
    wind: object = None            # wind.WindResult
    fire: object = None            # fire.FireResult (กฎกระทรวง พ.ศ. 2566 ข้อ 21–24)
    frames: object = None          # columns.GravityFrameResult         # seismic.SeismicResult when the earthquake check ran

    @property
    def ok(self) -> bool:
        groups = [self.slabs, self.beams, self.columns, self.footings, self.stairs]
        return all(x.ok for g in groups for x in g) and \
            (self.roof is None or (self.roof.purlin.ok and self.roof.rafter.ok)) and \
            (self.seismic is None or self.seismic.ok) and (self.wind is None or self.wind.ok)

    def total_piles(self) -> int:
        return sum(f.piles for f in self.footings)

    def all_refs(self) -> list[str]:
        out = []
        items = [self.roof] if self.roof else []
        if self.roof:
            items += [self.roof.purlin, self.roof.rafter]
        for x in items + self.slabs + self.stairs + self.beams + self.columns + self.footings:
            for c in (x.refs or "").split(","):
                c = c.strip()
                if c and c not in out:
                    out.append(c)
        extra = (self.frames.refs.split(",") if self.frames else []) + \
            (self.wind.refs.split(",") if self.wind else []) + \
            (["MR2566-23", "MI2567-32"] if self.fire and self.fire.applies else
             ["MR2566-23"] if self.fire and self.fire.notes else []) + \
            (["MI2567-3", "MI2567-29", "MI2567-29C", "MI2567-29D", "EIT1008-DEV", "EIT1008-HOOK"]) + \
            (self.seismic.refs.split(",") + ["MR-EQ2564"] if self.seismic else [])
        if extra:
            for c in extra:
                c = c.strip()
                if c and c not in out:
                    out.append(c)
        return out


# ---------------------------------------------------------------------------
# Roof
# ---------------------------------------------------------------------------

#: Deflection limits of roof structures (live / dead + live) by ceiling — ประกาศ มท. 2567 ตาราง 1.
ROOF_DEFL = {"plaster": (360, 240), "board": (240, 180), "none": (180, 120)}


def _pick_c(mx: float, my: float, role: str, span: float, w_perp: float | None = None,
            w_live: float | None = None, limits: tuple = (PURLIN_DEFL, PURLIN_DEFL)) -> SteelMember:
    """Lightest C section with Sx, Sy ≥ M/Fb (Fb = 1,400 ksc ≤ 0.6 Fy [MI2567-27]) whose
    deflection under ``w_perp`` (total, kg/m normal to the slope) is within
    L/limits[1] and under ``w_live`` within L/limits[0] [MI2567-8]."""
    sx_req = mx * 100 / PURLIN_FB
    sy_req = my * 100 / PURLIN_FB
    limit = span * 100 / limits[1]
    limit_live = span * 100 / limits[0]
    table = load_c_sections()
    refs = cite("QD-PURLIN", "MI2567-27", "MI2567-8", "AISC-ASD", "STEEL-TABLE")

    def defl(s, w=None):
        w = w_perp if w is None else w
        if not w or not s.get("ix_cm4"):
            return 0.0
        L = span * 100
        return 5 * (w / 100) * L ** 4 / (384 * ES * s["ix_cm4"])

    for s in table:                        # sorted lightest first
        d = defl(s)
        if s["zx_cm3"] >= sx_req and s["zy_cm3"] >= sy_req and d <= limit and \
                (not w_live or defl(s, w_live) <= limit_live):
            return SteelMember(role, span, mx, my, sx_req, sy_req, s["name"], s["zx_cm3"],
                               s["zy_cm3"], s["kg_m"], True, s["source"], d, limit, refs)
    s = table[-1]
    return SteelMember(role, span, mx, my, sx_req, sy_req, s["name"], s["zx_cm3"], s["zy_cm3"],
                       s["kg_m"], False, "ใหญ่สุดในตารางยังไม่พอ", defl(s), limit, refs)


def design_roof(b: Building) -> RoofResult:
    r = b.roof
    th = math.radians(r.slope_deg)
    cos, sin = math.cos(th), math.sin(th)
    cover = ROOF_COVER_LOAD.get(r.cover, 50)                     # [QD-ROOF]
    load_plan = (cover + r.frame_load + r.solar_load) / cos + r.live_load   # live per plan [MR2566-11]
    X, Y = b.plan_size()
    a, c = X + 2 * r.overhang, Y + 2 * r.overhang
    long_, short = max(a, c), min(a, c)
    plan_area = a * c
    slope_area = plan_area / cos
    rise = short / 2 * math.tan(th)
    if r.shape == "gable":
        ridge, hips = long_, 0.0
        eave = 2 * long_ + 4 * (short / 2) / cos
    else:
        ridge = long_ - short
        hips = 4 * math.sqrt(2 * (short / 2) ** 2 + rise ** 2)
        eave = 2 * (a + c)
    w_p = (cover + r.solar_load + r.live_load) * r.purlin_spacing
    L = r.rafter_spacing
    # purlins carry no ceiling; rafters take the limits of the ceiling hung from the roof [MI2567-8]
    purlin = _pick_c(w_p * cos * L * L / 8, w_p * sin * L * L / 8, "แป", L, w_p * cos,
                     r.live_load * r.purlin_spacing * cos, ROOF_DEFL["none"])
    span = (short / 2 - r.overhang) / cos if short / 2 > r.overhang else short / 2 / cos
    w_r = (cover + r.frame_load + r.solar_load + r.live_load) * r.rafter_spacing
    rafter = _pick_c(w_r * cos * span * span / 8, 0.0, "จันทัน", span, w_r * cos,
                     r.live_load * r.rafter_spacing * cos, ROOF_DEFL.get(r.ceiling, ROOF_DEFL["board"]))
    steel = (slope_area / r.purlin_spacing) * purlin.kg_m + \
            (slope_area / r.rafter_spacing) * rafter.kg_m + \
            (ridge + hips) * 2 * rafter.kg_m
    return RoofResult(load_plan, r.live_load, plan_area, slope_area, ridge, hips, eave, purlin, rafter,
                      steel, cite("QD-ROOF", "MR2566-11", "QD-PURLIN", "MI2567-11" if r.solar_load else "",
                                  "MR72" if r.solar_load else ""))


# ---------------------------------------------------------------------------
# Slabs
# ---------------------------------------------------------------------------

def _panel_name(b: Building, i: int, j: int) -> str:
    return f"{b.x_name(i)}-{b.x_name(i + 1)}/{b.y_name(j)}-{b.y_name(j + 1)}"


def _slab_load(lv) -> tuple[float, float]:
    """(total, live) kg/m² of a suspended slab: self weight [UNIT-WT],
    finishes, live load [MR2566-11]."""
    return CONCRETE_KG_M3 * lv.slab_thickness + lv.finish_load + lv.live_load, lv.live_load


def _panel_slab(mat: Concrete, lv, name: str, lx: float, ly: float, discontinuous: int,
                rect: tuple) -> SlabResult:
    """One slab panel ``lx`` × ``ly`` with ``discontinuous`` free edges."""
    S, Lg = min(lx, ly), max(lx, ly)
    m = S / Lg
    t = lv.slab_thickness
    fs = mat.fs("RB9")
    R, jj = mat.R(fs), mat.j(fs)
    d = t * 100 - slab_offset(mat)                                     # cover, ตาราง 13 [MI2567-29C]
    on_ground = lv.slab == "on_ground"
    as_min = slab_min_ratio(mat.tie_grade, on_ground) * 100 * t * 100  # cm²/m [MI2567-29D]
    smax = slab_max_spacing(t, False)                                  # ≤ 3t ≤ 30 cm
    if on_ground:
        bars = f"RB9@{pick_spacing(as_min, 'RB9', smax):.2f}"
        return SlabResult(lv.name, name, "", "on-ground", lx, ly, m, 0.0, 0, 0, 0, t, 0.0,
                          bars, bars, "-", True, "พื้นวางบนดิน ใช้เหล็กกันร้าว 0.0015",
                          refs=cite("MI2567-29D"), rect=rect)
    W, _live = _slab_load(lv)
    refs = [mat.ref, "UNIT-WT", "MR2566-11", "MI2567-29D", "MI2567-29C"]
    if m < 0.5:
        kind, case = "one-way", 0
        m_pos = W * S * S / 8
        m_neg = W * S * S / 24
        m_long = 0.0
        t_min = max(SLAB_MIN_THICKNESS, S / 20)
        refs.append("QD-SLAB5")
    else:
        case = discontinuous + 1          # case 1 = all four edges continuous
        kind = "two-way"
        neg_c, neg_d, pos, (l_nc, l_nd, l_pos) = SLAB_CASES[case]
        m_pos = _interp(m, SLAB_M, pos) * W * S * S
        m_neg = max(_interp(m, SLAB_M, neg_c), _interp(m, SLAB_M, neg_d)) * W * S * S
        m_long = l_pos * W * S * S
        t_min = max(SLAB_MIN_THICKNESS, 2 * (lx + ly) / 180)
        smax = slab_max_spacing(t, True)                               # ≤ 2t at critical sections
        refs.append("EIT1007-SLAB")
        if case == 5:
            refs.append("QD-SLAB5")
    d_req = math.sqrt(max(m_pos, m_neg) * 100 / (R * 100))
    ok = d_req <= d and t + 1e-9 >= t_min
    note = "" if ok else (f"ความหนาน้อยกว่า {t_min:.3f} ม." if t < t_min else "ความลึกไม่พอ")

    def bars(mom):
        as_ = max(mom * 100 / (fs * jj * d), as_min) if d > 0 else as_min
        return f"RB9@{pick_spacing(as_, 'RB9', smax):.2f}"

    long_bars = bars(m_long) if kind == "two-way" else f"RB9@{pick_spacing(as_min, 'RB9', smax):.2f}"
    return SlabResult(lv.name, name, "", kind, lx, ly, m, W, m_pos, m_neg, m_long, t, d_req,
                      bars(m_pos), long_bars, bars(m_neg), ok, note, case, cite(*refs), rect)


def _free_edges(b: Building, lv, i: int, j: int) -> dict:
    """Which edges of panel (i, j) have no slab beyond them."""
    panels = set(b.panels(lv.name))
    return {"left": (i - 1, j) not in panels, "right": (i + 1, j) not in panels,
            "bottom": (i, j - 1) not in panels, "top": (i, j + 1) not in panels}


def slab_parts(b: Building, lv, i: int, j: int):
    """The slab pieces of panel (i, j): one, or two when a secondary beam
    splits it. Each: (name, x0, y0, x1, y1, free-edge count)."""
    x0, x1, y0, y1 = b.xs[i], b.xs[i + 1], b.ys[j], b.ys[j + 1]
    name = _panel_name(b, i, j)
    free = _free_edges(b, lv, i, j)
    sub = b.sub_beam(lv, i, j)
    if not sub:
        return [(name, x0, y0, x1, y1, sum(free.values()))]
    d, f = sub
    if d == "x":
        ym = y0 + f * (y1 - y0)
        return [(name + "·1", x0, y0, x1, ym, free["left"] + free["right"] + free["bottom"]),
                (name + "·2", x0, ym, x1, y1, free["left"] + free["right"] + free["top"])]
    xm = x0 + f * (x1 - x0)
    return [(name + "·1", x0, y0, xm, y1, free["bottom"] + free["top"] + free["left"]),
            (name + "·2", xm, y0, x1, y1, free["bottom"] + free["top"] + free["right"])]


def design_slab(b: Building, mat: Concrete, lv, i: int, j: int) -> SlabResult:
    """The first slab piece of panel (i, j) (kept for single-piece callers)."""
    return design_slabs(b, mat, lv, i, j)[0]


def design_slabs(b: Building, mat: Concrete, lv, i: int, j: int) -> list[SlabResult]:
    out = []
    for name, x0, y0, x1, y1, free in slab_parts(b, lv, i, j):
        out.append(_panel_slab(mat, lv, name, x1 - x0, y1 - y0, free, (x0, y0, x1, y1)))
    return out


def design_cantilever_slab(mat: Concrete, lv, name: str, length: float, width: float,
                           rect: tuple) -> SlabResult:
    """Cantilever slab: M = W·L²/2 at the support, top steel [STATICS];
    thickness at least L/10 [EIT1007-SLABMIN]."""
    t = lv.slab_thickness
    fs = mat.fs("RB9")
    R, jj = mat.R(fs), mat.j(fs)
    d = t * 100 - slab_offset(mat)
    W, _live = _slab_load(lv)
    mom = W * length * length / 2
    d_req = math.sqrt(mom * 100 / (R * 100))
    as_min = slab_min_ratio(mat.tie_grade) * 100 * t * 100
    smax = slab_max_spacing(t, False)
    as_ = max(mom * 100 / (fs * jj * d), as_min)
    t_min = max(SLAB_MIN_THICKNESS, length / 10)
    ok = d_req <= d and t + 1e-9 >= t_min
    note = "ไม่รวมแรงบิดในคานขอบ" if ok else (f"ความหนาน้อยกว่า {t_min:.2f} ม." if t < t_min
                                            else "ความลึกไม่พอ")
    temp = f"RB9@{pick_spacing(as_min, 'RB9', smax):.2f}"
    return SlabResult(lv.name, name, "", "cantilever", length, width, 0.0, W, 0.0, mom, 0.0, t, d_req,
                      temp, temp, f"RB9@{pick_spacing(as_, 'RB9', smax):.2f}", ok, note, 0,
                      cite(mat.ref, "STATICS", "EIT1007-SLABMIN", "UNIT-WT", "MR2566-11", "MI2567-29D",
                           "MI2567-29C"),
                      rect)


# ---------------------------------------------------------------------------
# Beams
# ---------------------------------------------------------------------------

def _seg(a, b):
    return (a, b) if a <= b else (b, a)


TRIB_PIECES = 24


def _tributary(W: float, sx: float, sy: float):
    """Load on the edges of an ``sx`` × ``sy`` slab piece from the areas cut
    by 45° lines (triangles on the short edges, trapezoids on the long ones)
    [EIT1007-SLAB]. Returns point loads ``(a, P)`` for ONE edge parallel to X
    and ONE edge parallel to Y. One-way pieces (m < 0.5) send W·S/2 to each
    long edge. The four edges together carry exactly W·sx·sy."""
    S, Lg = min(sx, sy), max(sx, sy)
    if S <= 0:
        return [], []
    if S / Lg < 0.5:
        long_pts = partial_udl(W * S / 2, 0.0, Lg, TRIB_PIECES)
        return (long_pts, []) if sx >= sy else ([], long_pts)
    q, h = W * S / 2, S / 2

    def area(x, L):
        """∫₀ˣ min(t, L − t, h) dt, exact."""
        if x <= h:
            return x * x / 2
        if x <= L - h:
            return h * h / 2 + h * (x - h)
        u = x - (L - h)
        return h * h / 2 + h * (L - 2 * h) + h * u - u * u / 2

    def profile(L):
        dx = L / TRIB_PIECES
        return [((k + 0.5) * dx, q / h * (area((k + 1) * dx, L) - area(k * dx, L)))
                for k in range(TRIB_PIECES)]

    return profile(sx), profile(sy)


def _shift(pts, offset: float):
    return [(a + offset, P) for a, P in pts]


def balconies(b: Building, lv):
    """Cantilever slabs of a level as ``(a, c, length, outward, supported)``.
    ``supported`` when cantilever beams leave both ends of the edge in the
    outward direction at least as far as the slab: the slab then rests on
    four beams (edge beam, two cantilever beams, an edge beam at the tip)."""
    cbs = {(node, d): L for node, d, L, _p, _w in b.cant_beams(lv)}
    out = []
    for a, c, length, outward in b.cantilevers(lv):
        ok = all(cbs.get((n, outward), 0.0) + 1e-6 >= length for n in (a, c))
        out.append((a, c, length, outward, ok))
    return out


@dataclass
class SubBeam:
    level: str
    name: str
    length: float
    w: float                      # average kg/m from the slabs (no self weight)
    w_live: float
    line_xy: tuple
    pts: list = field(default_factory=list)   # (a, P) slab load along the beam


def level_line_loads(b: Building, li: int, roof: RoofResult | None, part: str = "total"):
    """Loads on the beam segments of level ``li`` without the beams' own
    weight: ``({segment: {"w": kg/m, "p": [(a, P)]}}, [SubBeam])``.
    ``part="live"`` gives the live load share only."""
    lv = b.levels[li]
    loads: dict = {}
    subs: list[SubBeam] = []

    def seg(a, c):
        k = _seg(a, c)
        return loads.setdefault(k, {"w": 0.0, "p": []})

    def add_w(a, c, w):
        seg(a, c)["w"] += w

    def add_p(a, c, pts):
        seg(a, c)["p"].extend(pts)

    if lv.slab == "suspended":
        total, live = _slab_load(lv)
    elif lv.slab == "roof" and roof is not None:
        total, live = roof.load_plan, roof.live_plan
    else:
        total = live = 0.0
    W = live if part == "live" else total
    sw_sub = CONCRETE_KG_M3 * lv.beam_width * lv.beam_depth if part != "live" else 0.0
    for i, j in (b.panels(lv.name) if W else []):
        lx = b.xs[i + 1] - b.xs[i]
        ly = b.ys[j + 1] - b.ys[j]
        bl, br, bb, bt = (i, j), (i + 1, j), (i, j + 1), (i + 1, j + 1)
        sub = b.sub_beam(lv, i, j)
        if not sub:
            px, py = _tributary(W, lx, ly)
            add_p(bl, br, px)
            add_p(bb, bt, px)
            add_p(bl, bb, py)
            add_p(br, bt, py)
            continue
        d, f = sub
        name = f"{_panel_name(b, i, j)}:{d}"
        if d == "x":                      # secondary beam parallel to X at y = f·ly
            h1 = f * ly
            px1, py1 = _tributary(W, lx, h1)
            px2, py2 = _tributary(W, lx, ly - h1)
            add_p(bl, br, px1)
            add_p(bb, bt, px2)
            sub_pts = px1 + px2
            length = lx
            line = (b.xs[i], b.ys[j] + h1, b.xs[i + 1], b.ys[j] + h1)
            supports = ((bl, bb), (br, bt))
            edge_pts = py1 + _shift(py2, h1)
        else:                             # parallel to Y at x = f·lx
            w1 = f * lx
            px1, py1 = _tributary(W, w1, ly)
            px2, py2 = _tributary(W, lx - w1, ly)
            add_p(bl, bb, py1)
            add_p(br, bt, py2)
            sub_pts = py1 + py2
            length = ly
            line = (b.xs[i] + w1, b.ys[j], b.xs[i] + w1, b.ys[j + 1])
            supports = ((bl, br), (bb, bt))
            edge_pts = px1 + _shift(px2, w1)
            h1 = w1
        _spans, (r0, r1) = continuous_beam([length], [sw_sub], [sub_pts])
        for (a, c), r in zip(supports, (r0, r1)):
            add_p(a, c, edge_pts)
            add_p(a, c, [(h1, r)])
            seg(a, c)["sub"] = True
        subs.append(SubBeam(lv.name, name, length, sum(P for _a, P in sub_pts) / length, 0.0, line))
        subs[-1].pts = sub_pts
    if lv.slab == "roof" and roof is not None:
        per_m = (roof.live_plan if part == "live" else roof.load_plan) * b.roof.overhang
        for _d, run in b.beam_lines(lv.name):
            for a, c in zip(run, run[1:]):
                if b.is_perimeter(a, c, lv.name):
                    add_w(a, c, per_m)
    from .stairs import beam_loads as stair_beam_loads
    for (a, c), pts in stair_beam_loads(b, li, part).items():
        if b.has_beam(lv.name, a, c):
            add_p(a, c, pts)
            seg(a, c)["stair"] = True
    if lv.slab == "suspended":
        for a, c, length, (dx, dy), supported in balconies(b, lv):
            if not supported:
                add_w(a, c, W * length)                # [STATICS], torsion not included
                continue
            E = abs(b.xs[c[0]] - b.xs[a[0]]) + abs(b.ys[c[1]] - b.ys[a[1]])
            if a[1] == c[1]:                           # edge along X, slab out in ±Y
                along, side = _tributary(W, E, length)
            else:
                side, along = _tributary(W, length, E)
            add_p(a, c, along)                         # 45° areas [EIT1007-SLAB]
            (x0, y0), (x1, y1) = (b.xs[a[0]], b.ys[a[1]]), (b.xs[c[0]], b.ys[c[1]])
            lo, hi = _seg(a, c)
            loads[("tip", lo, hi)] = {"p": along, "len": E, "nodes": (lo, hi),
                                      "xy": (min(x0, x1) + dx * length, min(y0, y1) + dy * length,
                                             max(x0, x1) + dx * length, max(y0, y1) + dy * length)}
            for n in (a, c):
                loads.setdefault(("cb", n, (dx, dy)), []).extend(side)
    if part != "live" and li + 1 < len(b.levels) and lv.walls != "none":
        above = b.levels[li + 1]
        hgt = above.elevation - lv.elevation - above.beam_depth
        wl = WALL_LOAD.get(lv.wall_type, 180) * max(0.0, hgt)           # [QD-WALL]
        for _d, run in b.beam_lines(lv.name):
            for a, c in zip(run, run[1:]):
                if lv.walls == "all" or b.is_perimeter(a, c, lv.name):
                    add_w(a, c, wl)
    return loads, subs


def _beam_design(mat: Concrete, bw: float, h: float, m_neg: float, m_pos: float, v: float,
                 off: float | None = None):
    """``off``: top of beam to the main bars, cm (ตาราง 13 cover + stirrup + ½ bar)."""
    fs = mat.fs("DB")
    R, j = mat.R(fs), mat.j(fs)
    off = beam_offset(mat, False) if off is None else off
    b_cm, d = bw * 100, h * 100 - off
    d_req = math.sqrt(max(m_neg, m_pos, 1.0) * 100 / (R * b_cm))
    rho_min = beam_rho_min(mat.fc_prime, FY[mat.main_grade])          # [MI2567-29D] (ญ) 1)

    def as_of(mom):
        req = mom * 100 / (fs * j * d)
        return max(req, min(rho_min * b_cm * d, 4 / 3 * req))

    as_top, as_bot = as_of(m_neg), as_of(m_pos)
    nt, st = pick_bars(as_top, b_cm)
    nb, sb = pick_bars(as_bot, b_cm)
    vv = v / (b_cm * d)
    vc = mat.vc_beam                                                   # [EIT1007-SHEAR]
    av = 2 * bar_area(STIRRUP)
    fv = mat.fs(STIRRUP)
    s = av * fv / ((vv - vc) * b_cm) if vv > vc else d / 2
    s_max = stirrup_max_spacing(av, FY[mat.tie_grade], b_cm, d, mat.fc_prime)   # (ญ) 3) minimum stirrups
    s = max(5.0, _round_down(min(s, s_max, 20.0), 2.5))
    ok = d_req <= d and vv <= 1.32 * math.sqrt(mat.fc_prime) + vc
    stir = f"{STIRRUP}@{s / 100:.3f}".rstrip("0")
    return d_req, as_top, as_bot, f"{nt}-{st}", f"{nb}-{sb}", stir, ok


def _min_depth(mat: Concrete, length: float, n_spans: int, k: int) -> float:
    """Depth that needs no deflection check [EIT1007-DEFL]."""
    if n_spans == 0:
        ratio = 8.0                      # cantilever
    elif n_spans == 1:
        ratio = 16.0
    elif k in (0, n_spans - 1):
        ratio = 18.5
    else:
        ratio = 21.0
    return length / ratio * (0.4 + FY[mat.main_grade] / 7000.0)


def _local(load, flip: bool, L: float):
    return [(L - a if flip else a, P) for a, P in load["p"]]


def design_level_beams(b: Building, mat: Concrete, li: int, roof):
    lv = b.levels[li]
    ext, subs = level_line_loads(b, li, roof)
    ext_live, subs_live = level_line_loads(b, li, roof, "live")
    empty = {"w": 0.0, "p": []}
    off = beam_offset(mat, lv.slab == "on_ground")          # ground beams: exposed to earth [MI2567-29C]
    results, reactions, live_reac = [], {}, {}
    refs = cite(mat.ref, "EIT1007-SHEAR", "EIT1007-MIN", "EIT1007-DEFL", "UNIT-WT", "QD-WALL",
                "EIT1007-SLAB", "STATICS")
    # secondary beams first: simply supported on the edge beams
    for sb, sbl in zip(subs, subs_live):
        bw, h = lv.beam_width, lv.beam_depth
        w = sb.w + CONCRETE_KG_M3 * bw * h
        L = sb.length
        (sp,), _r = continuous_beam([L], [CONCRETE_KG_M3 * bw * h], [sb.pts])
        d_req, at, ab, top, bot, stir, ok = _beam_design(mat, bw, h, 0.0, sp.m_pos,
                                                         max(sp.v_left, sp.v_right), off)
        hmin = _min_depth(mat, L, 1, 0)
        notes = ["คานซอยวางบนคานหลัก (ช่วงเดียว)"]
        if not ok:
            notes.append("หน้าตัดไม่พอ ต้องเพิ่มขนาด")
        if h + 1e-9 < hmin:
            notes.append(f"ลึกน้อยกว่า {hmin:.2f} ม. ต้องตรวจการแอ่นตัว")
        results.append(BeamResult(lv.name, "คานซอย", sb.name, "", bw, h, L, w, 0.0, sp.m_pos,
                                  max(sp.v_left, sp.v_right), d_req, at, ab, top, bot, stir, ok, " ; ".join(notes), hmin,
                                  refs, sb.line_xy, "secondary"))
    # edge beams at the tip of supported cantilever slabs: simply supported on the cantilever beams
    tip_p, tip_live = {}, {}
    for key, tl in ext.items():
        if not (isinstance(key, tuple) and key and key[0] == "tip"):
            continue
        lo, hi = tl["nodes"]
        bw, h = lv.beam_width, lv.beam_depth
        L = tl["len"]
        for _it in range(4):
            (sp,), (r0, r1) = continuous_beam([L], [CONCRETE_KG_M3 * bw * h], [tl["p"]])
            d_req, at, ab, top, bot, stir, ok = _beam_design(mat, bw, h, 0.0, sp.m_pos,
                                                             max(sp.v_left, sp.v_right), off)
            need = _round_up((d_req + off) / 100, 0.05)
            if need <= h + 1e-9 or need > MAX_BEAM_DEPTH:
                break
            h = need
        live_tl = ext_live.get(key, {"p": []})
        (_s,), (l0, l1) = continuous_beam([L], [0.0], [live_tl["p"]])
        hmin = _min_depth(mat, L, 1, 0)
        notes = ["คานขอบปลายพื้นยื่น วางบนคานยื่น"]
        if not ok:
            notes.append("หน้าตัดไม่พอ ต้องเพิ่มขนาด")
        results.append(BeamResult(lv.name, "คานขอบ", f"{b.node_name(*lo)}-{b.node_name(*hi)} ปลาย", "", bw, h, L,
                                  sp.w, 0.0, sp.m_pos, max(sp.v_left, sp.v_right), d_req, at, ab, top, bot, stir,
                                  ok, " ; ".join(notes), hmin, refs, tl["xy"], "secondary"))
        for n, r, lr in ((lo, r0, l0), (hi, r1, l1)):
            tip_p[n] = tip_p.get(n, 0.0) + r
            tip_live[n] = tip_live.get(n, 0.0) + lr
    # cantilever beams: designed alone, their support moment and shear go to the line
    over = {}                                    # (node, direction sign) -> (M, V, axis, V_live)
    cb_refs = cite(mat.ref, "STATICS", "EIT1007-SHEAR", "EIT1007-MIN", "EIT1007-DEFL", "UNIT-WT")
    for node, (dx, dy), L, P, wall in b.cant_beams(lv):
        bw, h = lv.beam_width, lv.beam_depth
        wl = 0.0
        if wall and li + 1 < len(b.levels):
            above = b.levels[li + 1]
            wl = WALL_LOAD.get(lv.wall_type, 180) * max(0.0, above.elevation - lv.elevation - above.beam_depth)
        hmin = _min_depth(mat, L, 0, 0)
        notes = []
        if h + 1e-9 < hmin:
            h = _round_up(hmin, 0.05)
            notes.append(f"เพิ่มความลึกเป็น {h:.2f} ม. (คานยื่น L/8)")
        side = ext.get(("cb", node, (dx, dy)), [])
        side_live = ext_live.get(("cb", node, (dx, dy)), [])
        pt = tip_p.get(node, 0.0)
        slab_len = max((a for a, _P in side), default=0.0) * 2 if side else 0.0
        pts = side + ([(min(L, slab_len or L), pt)] if pt else [])
        lpts = side_live + ([(min(L, slab_len or L), tip_live.get(node, 0.0))] if pt else [])
        for _it in range(6):
            w = CONCRETE_KG_M3 * bw * h + wl
            M = w * L * L / 2 + P * L + sum(Pi * a for a, Pi in pts)      # [STATICS]
            V = w * L + P + sum(Pi for _a, Pi in pts)
            d_req, at, ab, top, bot, stir, ok = _beam_design(mat, bw, h, M, 0.0, V, off)
            need = _round_up((d_req + off) / 100, 0.05)
            if need <= h + 1e-9 or need > MAX_BEAM_DEPTH:
                break
            h = need
            notes = [f"เพิ่มความลึกเป็น {h:.2f} ม."]
        if wl:
            notes.append(f"รับผนัง {wl:,.0f} กก./ม.")
        if P:
            notes.append(f"แรงจุดปลาย {P:,.0f} กก.")
        if side or pt:
            notes.append("รับพื้นยื่นและคานขอบปลาย")
        if not ok:
            notes.append("หน้าตัดไม่พอ ต้องเพิ่มขนาด")
        x0, y0 = b.xs[node[0]], b.ys[node[1]]
        d_name = {(1, 0): "x", (-1, 0): "-x", (0, 1): "y", (0, -1): "-y"}[(dx, dy)]
        results.append(BeamResult(lv.name, "คานยื่น", f"{b.node_name(*node)}{d_name}", "", bw, h, L, w, M, 0.0, V,
                                  d_req, at, ab, top, bot, stir, ok, " ; ".join(notes), hmin, cb_refs,
                                  (x0, y0, x0 + dx * L, y0 + dy * L), "cantilever"))
        m_live = sum(Pi * a for a, Pi in lpts)
        results[-1].m_neg_live = m_live
        over[(node, dx + dy)] = (M, V, "x" if dx else "y", sum(Pi for _a, Pi in lpts), m_live)
    used = set()
    for direction, run in b.beam_lines(lv.name):
        lengths = [abs((b.xs[c[0]] - b.xs[a[0]]) if direction == "x" else (b.ys[c[1]] - b.ys[a[1]]))
                   for a, c in zip(run, run[1:])]
        segs = [ext.get(_seg(a, c), empty) for a, c in zip(run, run[1:])]
        lsegs = [ext_live.get(_seg(a, c), empty) for a, c in zip(run, run[1:])]
        flips = [_seg(a, c)[0] != a for a, c in zip(run, run[1:])]
        pts = [_local(sg, fl, L) for sg, fl, L in zip(segs, flips, lengths)]
        line = b.y_name(run[0][1]) if direction == "x" else b.x_name(run[0][0])
        h, bw = lv.beam_depth, lv.beam_width
        left, right = over.get((run[0], -1)), over.get((run[-1], 1))
        left = left if left and left[2] == direction else None
        right = right if right and right[2] == direction else None
        ends = ((left[0] if left else 0.0), (right[0] if right else 0.0))
        for node, ov, sg in ((run[0], left, -1), (run[-1], right, 1)):
            if ov:
                used.add((node, sg))
                reactions[node] = reactions.get(node, 0.0) + ov[1]
                live_reac[node] = live_reac.get(node, 0.0) + ov[3]
        for _it in range(4):                     # re-run when the depth grows
            sw = CONCRETE_KG_M3 * bw * h
            spans, reac = continuous_beam(lengths, [sg["w"] + sw for sg in segs], pts, ends)
            need = h
            for sp in spans:
                m_neg = max(0.0, -sp.m_left, -sp.m_right)
                d_req = _beam_design(mat, bw, h, m_neg, sp.m_pos, max(sp.v_left, sp.v_right), off)[0]
                need = max(need, _round_up((d_req + off) / 100, 0.05))
            if need <= h + 1e-9 or need > MAX_BEAM_DEPTH:
                break
            h = need
        lspans, lreac = continuous_beam(lengths, [sg["w"] for sg in lsegs],
                                        [_local(sg, fl, L) for sg, fl, L in zip(lsegs, flips, lengths)],
                                        ((left[4] if left else 0.0), (right[4] if right else 0.0)))
        for k, ((a, c), sp) in enumerate(zip(zip(run, run[1:]), spans)):
            m_neg = max(0.0, -sp.m_left, -sp.m_right)
            d_req, at, ab, top, bot, stir, ok = _beam_design(mat, bw, h, m_neg, sp.m_pos,
                                                             max(sp.v_left, sp.v_right), off)
            notes = []
            if h != lv.beam_depth:
                notes.append(f"เพิ่มความลึกจาก {lv.beam_depth:.2f} เป็น {h:.2f} ม.")
            if segs[k].get("sub"):
                notes.append("รับแรงจุดจากคานซอย")
            if segs[k].get("stair"):
                notes.append("รับน้ำหนักบันได")
            if (k == 0 and left) or (k == len(spans) - 1 and right):
                notes.append("รับโมเมนต์จากคานยื่น")
            if not ok:
                notes.append("หน้าตัดไม่พอ ต้องเพิ่มขนาด")
            hmin = _min_depth(mat, sp.length, len(spans), k)
            if h + 1e-9 < hmin:
                notes.append(f"ลึกน้อยกว่า {hmin:.2f} ม. ต้องตรวจการแอ่นตัว")
            xy = (b.xs[a[0]], b.ys[a[1]], b.xs[c[0]], b.ys[c[1]])
            results.append(BeamResult(lv.name, line, f"{b.node_name(*a)}-{b.node_name(*c)}", "", bw, h,
                                      sp.length, sp.w, m_neg, sp.m_pos, max(sp.v_left, sp.v_right), d_req,
                                      at, ab, top, bot, stir, ok, " ; ".join(notes), hmin, refs, xy,
                                      m_neg_live=max(0.0, -lspans[k].m_left, -lspans[k].m_right),
                                      load_w=segs[k]["w"] + CONCRETE_KG_M3 * bw * h, load_pts=pts[k],
                                      load_w_live=lsegs[k]["w"],
                                      load_pts_live=_local(lsegs[k], flips[k], sp.length)))
        for node, rx, lx in zip(run, reac, lreac):
            reactions[node] = reactions.get(node, 0.0) + rx
            live_reac[node] = live_reac.get(node, 0.0) + lx
    for (node, sg), (M, V, d, V_live, _ml) in over.items():
        if (node, sg) not in used:               # no beam line behind it: straight into the column
            reactions[node] = reactions.get(node, 0.0) + V
            live_reac[node] = live_reac.get(node, 0.0) + V_live
            for x in results:
                if x.kind == "cantilever" and x.span.startswith(b.node_name(*node)):
                    x.note = (x.note + " ; " if x.note else "") + "ไม่มีคานต่อเนื่องด้านใน โมเมนต์ลงเสา"
    for x in results:
        x.d_off = off
    return results, reactions, live_reac


def _bars_area(text: str) -> float:
    n, size = text.split("-", 1)
    return int(n) * bar_area(size.strip())


def check_deflections(res, mat):
    """Deflection of every beam against ประกาศ มท. 2567 ตาราง 1 [MI2567-8];
    a beam that deflects too much is deepened by 5 cm at a time (its
    bars are then re-chosen for the same moments)."""
    for x in res.beams:
        L = x.length
        cant = x.kind == "cantilever"
        m = x.m_neg if cant else x.m_pos
        if L <= 0 or m <= 0:
            continue
        total_w = x.load_w * L + sum(P for _a, P in x.load_pts)
        live_w = x.load_w_live * L + sum(P for _a, P in x.load_pts_live)
        share = min(1.0, live_w / total_w) if total_w > 0 and x.kind == "beam" else \
            (min(1.0, x.m_neg_live / x.m_neg) if cant and x.m_neg else 0.3)
        grown = False
        for _ in range(8):
            d = x.h * 100 - x.d_off
            As_t = _bars_area(x.top if cant else x.bottom)
            As_c = _bars_area(x.bottom if cant else x.top)
            dl, dt, ll, lt = beam_deflection(mat, x.b, x.h, d, As_t, As_c, L, m, share, cant)
            if (dl <= ll and dt <= lt) or x.h >= MAX_BEAM_DEPTH:
                break
            x.h = round(x.h + 0.05, 2)
            grown = True
            d_req, at, ab, top, bot, stir, ok = _beam_design(mat, x.b, x.h, x.m_neg, x.m_pos, x.v, x.d_off)
            x.as_top, x.as_bot, x.top, x.bottom, x.stirrup = at, ab, top, bot, stir
        x.note = " ; ".join(p for p in (x.note or "").split(" ; ") if "ตรวจการแอ่นตัว" not in p)
        text = f"แอ่น {dt * 10:.1f}/{lt * 10:.1f} มม. (จร {dl * 10:.1f}/{ll * 10:.1f})"
        if grown:
            text = f"เพิ่มความลึกเป็น {x.h:.2f} ม. ตามระยะแอ่นตัว ; " + text
        if dl > ll or dt > lt:
            x.ok = False
            text += " เกินเกณฑ์"
        x.note = (x.note + " ; " if x.note else "") + text
        x.deflection = dt
        if "MI2567-8" not in x.refs:
            x.refs += ", MI2567-8"


# ---------------------------------------------------------------------------
# Stairs and the stair beam BT
# ---------------------------------------------------------------------------

def design_stairs(b: Building, mat: Concrete, res, node_reac, node_live):
    """Design every stair; a ``landing`` stair also gets its beam BT,
    simply supported on the two far-edge columns at landing height, whose
    reactions go into those columns [STATICS], [QD-STAIR]."""
    from .stairs import design_stair, landing_line
    refs = cite(mat.ref, "STATICS", "EIT1007-SHEAR", "EIT1007-MIN", "EIT1007-DEFL", "UNIT-WT", "QD-STAIR")
    for st in b.stairs:
        r = design_stair(b, mat, st)
        res.stairs.append(r)
        line = landing_line(b, st)
        if line is None or r.geom is None:
            continue
        g, L, pts = line
        _g, _L, lpts = landing_line(b, st, "live")
        a, c = g.far
        lv0 = b.levels[g.li0]
        bw, h = lv0.beam_width, lv0.beam_depth
        notes = [f"คานบันได {st.name} ระดับชานพัก +{g.landing_z:.2f}"]
        hmin = _min_depth(mat, L, 1, 0)
        for _it in range(6):
            sw = CONCRETE_KG_M3 * bw * h
            (sp,), (r0, r1) = continuous_beam([L], [sw], [pts])
            d_req, at, ab, top, bot, stir, ok = _beam_design(mat, bw, h, 0.0, sp.m_pos,
                                                             max(sp.v_left, sp.v_right))
            need = max(_round_up((d_req + beam_offset(mat, False)) / 100, 0.05), _round_up(hmin, 0.05))
            if need <= h + 1e-9 or need > MAX_BEAM_DEPTH:
                break
            h = need
        if h != lv0.beam_depth:
            notes.append(f"ความลึก {h:.2f} ม.")
        if not ok:
            notes.append("หน้าตัดไม่พอ ต้องเพิ่มขนาด")
        (_lsp,), (l0, l1) = continuous_beam([L], [0.0], [lpts])
        xy = (b.xs[a[0]], b.ys[a[1]], b.xs[c[0]], b.ys[c[1]])
        res.beams.append(BeamResult(lv0.name, "คานบันได", f"{b.node_name(*a)}-{b.node_name(*c)} BT", "", bw, h, L,
                                    sp.w, 0.0, sp.m_pos, max(sp.v_left, sp.v_right), d_req, at, ab, top, bot,
                                    stir, ok, " ; ".join(notes), hmin, refs, xy, "stair", z_top=g.landing_z,
                                    d_off=beam_offset(mat, False)))
        lower, upper = (a, c) if a <= c else (c, a)
        for node, rx, lx in ((lower, r0, l0), (upper, r1, l1)):
            node_reac[g.li1][node] = node_reac[g.li1].get(node, 0.0) + rx
            node_live[g.li1][node] = node_live[g.li1].get(node, 0.0) + lx


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------

def _column_design(mat: Concrete, P: float, bw: float, h: float):
    """Short tied column under axial load [EIT1007-COL]."""
    fs = mat.fs_column
    note = ""
    while True:
        ag = bw * 100 * h * 100
        pg = (P / (0.85 * ag) - 0.25 * mat.fc_prime) / fs
        pg = max(0.01, pg)
        if pg <= 0.04 or max(bw, h) >= MAX_COLUMN:
            break
        bw, h = round(bw + 0.05, 2), round(h + 0.05, 2)
        note = "ขยายหน้าตัดอัตโนมัติ"
    as_ = pg * ag
    for size in ("DB12", "DB16", "DB20", "DB25"):
        n = max(4, math.ceil(as_ / bar_area(size) - 1e-9))
        n += n % 2
        if n <= 12:
            break
    return bw, h, pg, f"{n}-{size}", column_ties(f"{n}-{size}", bw, h), pg <= 0.08, \
        (note if pg <= 0.08 else "ปริมาณเหล็กเกิน 8% ต้องเพิ่มหน้าตัด")


def column_ties(bars: str, b: float, h: float) -> str:
    """Tie size by the main bar and spacing ≤ 16db, 48dt, least side — ประกาศ มท. 2567
    ข้อ 29 (11) (จ) 3) [MI2567-29D], [EIT1007-TIE]."""
    size = bars.split("-", 1)[1]
    tie = tie_bar(size)
    s = _round_down(tie_spacing_max(size, tie, min(b, h) * 100), 2.5)
    return f"{tie}@{s / 100:.3f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# Footings
# ---------------------------------------------------------------------------

def _pile_layout(n: int, s: float):
    if n == 1:
        pts = [(0, 0)]
    elif n == 2:
        pts = [(-s / 2, 0), (s / 2, 0)]
    elif n == 3:
        r = s / math.sqrt(3)
        pts = [(0, r), (-s / 2, -r / 2), (s / 2, -r / 2)]
    elif n == 4:
        pts = [(x, y) for x in (-s / 2, s / 2) for y in (-s / 2, s / 2)]
    else:
        a = s / math.sqrt(2)
        pts = [(0, 0)] + [(x, y) for x in (-a, a) for y in (-a, a)]
    return pts


def _footing_bars(mat: Concrete, moment: float, width: float, t: float, d: float) -> str:
    fs = mat.fs("DB")
    j = mat.j(fs)
    as_req = moment * 100 / (fs * j * d) if d > 0 else 0.0
    as_min = 0.0018 * width * 100 * t * 100
    as_ = max(as_req, as_min)
    for size in ("DB12", "DB16", "DB20"):
        n = max(2, math.ceil(as_ / bar_area(size) - 1e-9))
        n = max(n, math.ceil((width - 0.15) / 0.30) + 1)
        if (width - 0.15) / max(n - 1, 1) >= 0.10:
            return f"{n}-{size}"
    return f"{n}-DB20"


def _one_way_ok(mat, pts, R, c_m, d_cm, width, axis) -> bool:
    """One-way shear at d from the column face [EIT1007-FOOT]."""
    edge = c_m / 2 + d_cm / 100
    V = sum(R for p in pts if abs(p[axis]) > edge)
    return V <= mat.vc_beam * width * 100 * d_cm


def design_footing(b: Building, mat: Concrete, node: str, P: float, col_b: float, col_h: float):
    f = b.foundation
    c = (col_b + col_h) / 2 * 100              # cm
    vp = mat.vc_punch                          # [EIT1007-FOOT]
    if f.kind == "spread":
        W = 0.0
        for _ in range(5):
            side = _round_up(math.sqrt((P + W) / f.soil_qa), 0.05)
            d = (-c + math.sqrt(c * c + P / vp)) / 2
            t = max(0.30, _round_up((d + footing_offset(mat)) / 100, 0.05))
            q = P / (side * side)
            while t < 1.5:                      # one-way shear
                d = t * 100 - footing_offset(mat)
                V = q * side * max(0.0, (side - c / 100) / 2 - d / 100)
                if V <= mat.vc_beam * side * 100 * d:
                    break
                t += 0.05
            W = CONCRETE_KG_M3 * side * side * t
        arm = max(0.0, (side - c / 100) / 2)
        mom = q * side * arm * arm / 2
        d = t * 100 - footing_offset(mat)
        bars = _footing_bars(mat, mom, side, t, d)
        return FootingResult(node, P, "spread", 0, "-", f.soil_qa, round(side, 2), round(side, 2),
                             round(t, 2), bars, bars, W, refs=cite("EIT1007-FOOT", mat.ref, "SOIL", "MI2567-29D", "MI2567-29C"))
    piles = load_piles()
    family = f.pile[0]
    order = sorted((k for k in piles if k[0] == family), key=lambda k: piles[k]["capacity_kg"])
    pile = f.pile
    note = ""
    while True:
        p = piles[pile]
        size, cap = p["size_m"], p["capacity_kg"]
        s = max(3 * size, 0.60)
        e = max(size, 0.25)
        W = 0.0
        for _ in range(5):
            n = max(1, math.ceil((P + W) / cap - 1e-9))
            pts = _pile_layout(min(n, MAX_PILES), s)
            xs = [x for x, _y in pts]
            ys = [y for _x, y in pts]
            B = _round_up(max(xs) - min(xs) + 2 * e, 0.05)
            L = _round_up(max(ys) - min(ys) + 2 * e, 0.05)
            d = (-c + math.sqrt(c * c + P / vp)) / 2
            t = max(0.40, _round_up((d + footing_offset(mat)) / 100, 0.05))
            R = P / len(pts)
            while t < 1.5 and not (_one_way_ok(mat, pts, R, c / 100, t * 100 - footing_offset(mat), L, 0) and
                                   _one_way_ok(mat, pts, R, c / 100, t * 100 - footing_offset(mat), B, 1)):
                t = round(t + 0.05, 2)
            W = CONCRETE_KG_M3 * B * L * t
        if n <= MAX_PILES:
            break
        bigger = order.index(pile) + 1
        if bigger >= len(order):
            note = f"เสาเข็ม {pile} ต้องใช้ {n} ต้น เกิน {MAX_PILES}"
            break
        pile = order[bigger]
        note = f"เปลี่ยนเสาเข็มเป็น {pile} เพื่อไม่ให้เกิน {MAX_PILES} ต้น"
    R = P / len(pts)
    d = t * 100 - footing_offset(mat)
    mx = sum(R * (x - c / 200) for x, _y in pts if x - c / 200 > 0)
    my = sum(R * (y - c / 200) for _x, y in pts if y - c / 200 > 0)
    bars_x = _footing_bars(mat, mx, L, t, d)
    bars_y = _footing_bars(mat, my, B, t, d)
    ok = n <= MAX_PILES
    return FootingResult(node, P, "pile", len(pts) if ok else n, pile, cap, round(B, 2), round(L, 2),
                         round(t, 2), bars_x, bars_y, W, ok=ok, note=note,
                         refs=cite("EIT1007-FOOT", mat.ref, "QD-PILE", "SOIL", "UNIT-WT", "MI2567-29D", "MI2567-29C"))


# ---------------------------------------------------------------------------
# Marks
# ---------------------------------------------------------------------------

def _assign_marks(items, key, prefix, load):
    groups: dict = {}
    for it in items:
        groups.setdefault(key(it), []).append(it)
    ordered = sorted(groups.values(), key=lambda g: max(load(x) for x in g))
    for k, g in enumerate(ordered, 1):
        for it in g:
            it.mark = f"{prefix}{k}"


# ---------------------------------------------------------------------------
# The chain
# ---------------------------------------------------------------------------

def design(b: Building) -> DesignResult:
    from .seismic import use_quality_control
    use_quality_control(b.quality_control)            # φ of กฎกระทรวง พ.ศ. 2566 ข้อ 8
    mat = Concrete(fc_prime=b.fc_prime, code=b.design_code, qc=b.quality_control)
    from . import seismic as _seismic
    from .rules import column_cover, site_notes
    _seismic.COVER = column_cover(mat)               # ties' cover, ประกาศ มท. 2567 ตาราง 13
    res = DesignResult(b, mat)
    from .fire import requirements as fire_requirements
    res.fire = fire_requirements(b)
    if any(lv.slab == "roof" for lv in b.levels):
        res.roof = design_roof(b)
    n_lv = len(b.levels)
    node_reac: list[dict] = [dict() for _ in b.levels]
    node_live: list[dict] = [dict() for _ in b.levels]
    for li in reversed(range(n_lv)):
        lv = b.levels[li]
        if lv.slab in ("suspended", "on_ground"):
            for i, j in b.panels(lv.name):
                res.slabs.extend(design_slabs(b, mat, lv, i, j))
        if lv.slab == "suspended":
            bal = balconies(b, lv)
            ends = {}
            for a, c, _l, out, sup in bal:
                if sup:
                    for n in (a, c):
                        ends[(n, out)] = ends.get((n, out), 0) + 1
            for a, c, length, (dx, dy), supported in bal:
                (x0, y0), (x1, y1) = (b.xs[a[0]], b.ys[a[1]]), (b.xs[c[0]], b.ys[c[1]])
                rect = (min(x0, x1, x0 + dx * length), min(y0, y1, y0 + dy * length),
                        max(x0, x1, x0 + dx * length), max(y0, y1, y0 + dy * length))
                width = abs(x1 - x0) + abs(y1 - y0)
                name = f"{b.node_name(*a)}-{b.node_name(*c)} ยื่น"
                if supported:
                    # resting on four beams: edge beam (continuous with the floor), tip beam (free),
                    # cantilever beams (continuous when the next balcony shares them) [EIT1007-SLAB]
                    free = 1 + sum(1 for n in (a, c) if ends[(n, (dx, dy))] < 2)
                    sl = _panel_slab(mat, lv, name, rect[2] - rect[0], rect[3] - rect[1], free, rect)
                    sl.note = (sl.note + " ; " if sl.note else "") + "พื้นยื่นวางบนคานยื่นและคานขอบปลาย"
                    res.slabs.append(sl)
                else:
                    res.slabs.append(design_cantilever_slab(mat, lv, name, length, width, rect))
        beams, reac, live = design_level_beams(b, mat, li, res.roof)
        res.beams.extend(beams)
        node_reac[li], node_live[li] = reac, live
    design_stairs(b, mat, res, node_reac, node_live)
    reduce = b.ll_reduction and b.occupancy not in NO_REDUCTION
    elev = [lv.elevation for lv in b.levels]
    stub = b.foundation.depth - 0.40 + elev[0]
    old_law = b.design_code == "MR6"                     # transitional clause, ข้อ 25
    col_refs = cite(mat.ref, "EIT1007-COL", "EIT1007-TIE", "UNIT-WT",
                    ("MR6-16" if old_law else "MR2566-13") if reduce else "", "MR2566-25" if old_law else "")
    col_at = {}
    for i, j in b.nodes():
        name = b.node_name(i, j)
        above = reduced = live = 0.0
        bw, h = b.column_width, b.column_depth
        segs = []
        for li in reversed(range(n_lv)):
            r = ll_reduction(n_lv - 1 - li, LL_REDUCTION_MR6 if old_law else None) if reduce else 0.0
            if b.levels[li].live_load > NO_REDUCTION_ABOVE:          # ข้อ 14 (2)
                r = 0.0
            cut = node_live[li].get((i, j), 0.0) * r
            above += node_reac[li].get((i, j), 0.0) - cut
            live += node_live[li].get((i, j), 0.0) - cut
            reduced += cut
            if li == 0:
                hgt, seg = stub, f"ฐานราก–{b.levels[0].name}"
            else:
                hgt, seg = elev[li] - elev[li - 1], f"{b.levels[li - 1].name}–{b.levels[li].name}"
            above += CONCRETE_KG_M3 * bw * h * hgt
            cb, ch, pg, bars, ties, ok, note = _column_design(mat, above, bw, h)
            bw, h = max(bw, cb), max(h, ch)
            if reduced:
                note = (note + " ; " if note else "") + f"ลดน้ำหนักจร {reduced:,.0f} กก."
            segs.append(ColumnResult(name, seg, hgt, above, cb, ch, pg, bars, ties, ok=ok, note=note,
                                     live_reduced=reduced, refs=col_refs, live=live))
            col_at[(i, j, li)] = segs[-1]
        res.columns.extend(reversed(segs))
        res.footings.append(design_footing(b, mat, name, above, bw, h))
    if n_lv > 1:
        from .columns import check_footing_moments, design_columns
        res.frames = design_columns(b, res, mat, col_at, elev[0] - stub)
        for st in res.frames.stability:
            if st.sway:
                res.warnings.append(f"เสาช่วง {st.level} ทิศ {st.direction}: Q = {st.q:.3f} > 0.05 เป็นโครงแบบเซ"
                                    + (f" ขยายโมเมนต์จากแรงด้านข้าง δs = {st.delta_s:.2f}"
                                       if b.seismic.enabled else ""))
        check_footing_moments(b, res, mat, col_at)
    if b.wind.enabled and n_lv > 1:
        from .wind import run as wind_run
        res.wind = wind_run(b, res, mat, col_at, elev[0] - stub)
        res.warnings += [w[3:] if w.startswith("NG ") else w for w in res.wind.warnings]
    if b.seismic.enabled and n_lv > 1:
        from .seismic import run as seismic_run
        node_dead = [{n: node_reac[li][n] - node_live[li].get(n, 0.0) for n in node_reac[li]}
                     for li in range(n_lv)]
        res.seismic = seismic_run(b, res, mat, node_dead, node_live, col_at, elev[0] - stub)
        res.warnings += [w[3:] if w.startswith("NG ") else w for w in res.seismic.warnings]
        for s in res.seismic.storeys:
            if not s.ok:
                res.warnings.append(f"แผ่นดินไหว ชั้น {s.level}: {s.note}")
    if n_lv > 0:
        from .footings import combine_footings
        base = {b.node_name(i, j): c for (i, j, li), c in col_at.items() if li == 0}
        before = len(res.footings)
        res.warnings += combine_footings(b, res, mat, base)
        if res.seismic and len(res.footings) < before:
            res.warnings.append("ฐานรากร่วมออกแบบด้วยน้ำหนักแนวดิ่ง ยังไม่ได้ตรวจแรงแผ่นดินไหว")
    for c in res.columns:                             # bars may have changed in the later checks
        c.ties = column_ties(c.bars, c.b, c.h)
        if "MI2567-29D" not in c.refs:
            c.refs += ", MI2567-29D"
    res.warnings += site_notes(b)
    from .fire import check_members as fire_check
    fire_check(res)
    _assign_marks(res.columns, lambda c: (c.b, c.h, c.bars, c.ties), "C", lambda c: c.load)
    _assign_marks([f for f in res.footings if f.kind != "combined"],
                  lambda f: (f.piles, f.pile, f.width, f.length, f.thickness, f.bars_x, f.bars_y), "F",
                  lambda f: f.load)
    _assign_marks([f for f in res.footings if f.kind == "combined"],
                  lambda f: (f.piles, f.pile, f.width, f.length, f.thickness, f.bars_x, f.bars_y), "CF",
                  lambda f: f.load)
    check_deflections(res, mat)
    _assign_marks([x for x in res.beams if x.kind == "stair"],
                  lambda x: (x.b, x.h, x.top, x.bottom, x.stirrup), "BT", lambda x: x.m_pos)
    for st in res.stairs:
        st.mark = st.name
    for lv in b.levels:
        _assign_marks([x for x in res.beams if x.level == lv.name and x.kind == "cantilever"],
                      lambda x: (x.b, x.h, x.top, x.bottom, x.stirrup), lv.beam_mark + "C", lambda x: x.m_neg)
        _assign_marks([x for x in res.beams if x.level == lv.name and x.kind == "beam"],
                      lambda x: (x.b, x.h, x.top, x.bottom, x.stirrup), lv.beam_mark, lambda x: x.m_pos)
        _assign_marks([x for x in res.beams if x.level == lv.name and x.kind == "secondary"],
                      lambda x: (x.b, x.h, x.top, x.bottom, x.stirrup), lv.beam_mark + "S", lambda x: x.m_pos)
        _assign_marks([x for x in res.slabs if x.level == lv.name and x.kind != "cantilever"],
                      lambda x: (x.kind, x.case, x.thickness, x.bars_short, x.bars_long, x.bars_top),
                      "GS" if lv.slab == "on_ground" else "S", lambda x: x.m_pos)
        _assign_marks([x for x in res.slabs if x.level == lv.name and x.kind == "cantilever"],
                      lambda x: (x.lx, x.thickness, x.bars_top), "CS", lambda x: x.m_neg)
    for group in (res.slabs, res.stairs, res.beams, res.columns, res.footings):
        for x in group:
            if not x.ok:
                where = getattr(x, "span", "") or getattr(x, "panel", "") or x.node
                res.warnings.append(f"{type(x).__name__[:-6]} {where} ({x.mark}): {x.note}")
    for x in res.beams:
        if x.ok and "แอ่นตัว" in x.note:
            res.warnings.append(f"คาน {x.level} {x.span} ({x.mark}): {x.note}")
    if res.roof and not (res.roof.purlin.ok and res.roof.rafter.ok):
        res.warnings.append("หลังคา: เหล็กแปหรือจันทันในตารางไม่พอ")
    return res
