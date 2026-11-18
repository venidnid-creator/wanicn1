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

from ..standards import NO_REDUCTION, cite, ll_reduction
from .analysis import continuous_beam
from .building import ROOF_COVER_LOAD, WALL_LOAD, Building
from .materials import CONCRETE_KG_M3, ES, FY, Concrete
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
    live_reduced: float = 0.0      # kg of live load taken off [MR6-16]
    refs: str = ""


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

    @property
    def ok(self) -> bool:
        groups = [self.slabs, self.beams, self.columns, self.footings]
        return all(x.ok for g in groups for x in g) and \
            (self.roof is None or (self.roof.purlin.ok and self.roof.rafter.ok))

    def total_piles(self) -> int:
        return sum(f.piles for f in self.footings)

    def all_refs(self) -> list[str]:
        out = []
        items = [self.roof] if self.roof else []
        if self.roof:
            items += [self.roof.purlin, self.roof.rafter]
        for x in items + self.slabs + self.beams + self.columns + self.footings:
            for c in (x.refs or "").split(","):
                c = c.strip()
                if c and c not in out:
                    out.append(c)
        return out


# ---------------------------------------------------------------------------
# Roof
# ---------------------------------------------------------------------------

def _pick_c(mx: float, my: float, role: str, span: float, w_perp: float | None = None) -> SteelMember:
    """Lightest C section with Sx, Sy ≥ M/Fb [QD-PURLIN] and, when the load
    ``w_perp`` (kg/m, normal to the slope) is given, deflection ≤ L/240."""
    sx_req = mx * 100 / PURLIN_FB
    sy_req = my * 100 / PURLIN_FB
    limit = span * 100 / PURLIN_DEFL
    table = load_c_sections()
    refs = cite("QD-PURLIN", "AISC-ASD", "STEEL-TABLE")

    def defl(s):
        if not w_perp or not s.get("ix_cm4"):
            return 0.0
        L = span * 100
        return 5 * (w_perp / 100) * L ** 4 / (384 * ES * s["ix_cm4"])

    for s in table:                        # sorted lightest first
        d = defl(s)
        if s["zx_cm3"] >= sx_req and s["zy_cm3"] >= sy_req and d <= limit:
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
    load_plan = (cover + r.frame_load) / cos + r.live_load       # live per plan [MR6-15]
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
    w_p = (cover + r.live_load) * r.purlin_spacing
    L = r.rafter_spacing
    purlin = _pick_c(w_p * cos * L * L / 8, w_p * sin * L * L / 8, "แป", L, w_p * cos)
    span = (short / 2 - r.overhang) / cos if short / 2 > r.overhang else short / 2 / cos
    w_r = (cover + r.frame_load + r.live_load) * r.rafter_spacing
    rafter = _pick_c(w_r * cos * span * span / 8, 0.0, "จันทัน", span, w_r * cos)
    steel = (slope_area / r.purlin_spacing) * purlin.kg_m + \
            (slope_area / r.rafter_spacing) * rafter.kg_m + \
            (ridge + hips) * 2 * rafter.kg_m
    return RoofResult(load_plan, r.live_load, plan_area, slope_area, ridge, hips, eave, purlin, rafter,
                      steel, cite("QD-ROOF", "MR6-15", "QD-PURLIN"))


# ---------------------------------------------------------------------------
# Slabs
# ---------------------------------------------------------------------------

def _panel_name(b: Building, i: int, j: int) -> str:
    return f"{b.x_name(i)}-{b.x_name(i + 1)}/{b.y_name(j)}-{b.y_name(j + 1)}"


def _slab_load(lv) -> tuple[float, float]:
    """(total, live) kg/m² of a suspended slab: self weight [UNIT-WT],
    finishes, live load [MR6-15]."""
    return CONCRETE_KG_M3 * lv.slab_thickness + lv.finish_load + lv.live_load, lv.live_load


def design_slab(b: Building, mat: Concrete, lv, i: int, j: int) -> SlabResult:
    lx = b.xs[i + 1] - b.xs[i]
    ly = b.ys[j + 1] - b.ys[j]
    S, Lg = min(lx, ly), max(lx, ly)
    m = S / Lg
    name = _panel_name(b, i, j)
    t = lv.slab_thickness
    fs = mat.fs("RB9")
    R, jj = mat.R(fs), mat.j(fs)
    d = t * 100 - 2.5
    as_min = 0.0025 * 100 * t * 100           # cm²/m [EIT1007-TEMP]
    smax = min(3 * t * 100, 45.0)
    if lv.slab == "on_ground":
        bars = f"RB9@{pick_spacing(as_min, 'RB9', smax):.2f}"
        return SlabResult(lv.name, name, "", "on-ground", lx, ly, m, 0.0, 0, 0, 0, t, 0.0,
                          bars, bars, "-", True, "พื้นวางบนดิน ใช้เหล็กกันร้าว",
                          refs=cite("EIT1007-TEMP"))
    W, _live = _slab_load(lv)
    panels = set(b.panels(lv.name))
    neighbours = [(i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)]
    discontinuous = sum(1 for p in neighbours if p not in panels)
    refs = [mat.ref, "UNIT-WT", "MR6-15", "EIT1007-TEMP"]
    if m < 0.5:
        kind, case = "one-way", 0
        m_pos = W * S * S / 8
        m_neg = W * S * S / 24
        m_long = 0.0
        t_min = S / 20
        refs.append("QD-SLAB5")
    else:
        case = discontinuous + 1          # case 1 = all four edges continuous
        kind = "two-way"
        neg_c, neg_d, pos, (l_nc, l_nd, l_pos) = SLAB_CASES[case]
        m_pos = _interp(m, SLAB_M, pos) * W * S * S
        m_neg = max(_interp(m, SLAB_M, neg_c), _interp(m, SLAB_M, neg_d)) * W * S * S
        m_long = l_pos * W * S * S
        t_min = max(0.08, 2 * (lx + ly) / 180)
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
                      bars(m_pos), long_bars, bars(m_neg), ok, note, case, cite(*refs))


# ---------------------------------------------------------------------------
# Beams
# ---------------------------------------------------------------------------

def _seg(a, b):
    return (a, b) if a <= b else (b, a)


def level_line_loads(b: Building, li: int, roof: RoofResult | None, part: str = "total") -> dict:
    """Uniform load (kg/m) on every beam segment of level ``li`` without the
    beam's own weight. ``part="live"`` gives the live load share only."""
    lv = b.levels[li]
    loads: dict = {}

    def add(seg, w):
        loads[seg] = loads.get(seg, 0.0) + w

    if lv.slab == "suspended":
        total, live = _slab_load(lv)
    elif lv.slab == "roof" and roof is not None:
        total, live = roof.load_plan, roof.live_plan
    else:
        total = live = 0.0
    W = live if part == "live" else total
    if W:
        for i, j in b.panels(lv.name):
            lx = b.xs[i + 1] - b.xs[i]
            ly = b.ys[j + 1] - b.ys[j]
            S, Lg = min(lx, ly), max(lx, ly)
            m = S / Lg
            x_edges = [_seg((i, j), (i + 1, j)), _seg((i, j + 1), (i + 1, j + 1))]
            y_edges = [_seg((i, j), (i, j + 1)), _seg((i + 1, j), (i + 1, j + 1))]
            if m < 0.5:
                for e in (x_edges if lx >= ly else y_edges):
                    add(e, W * S / 2)
            else:                                            # [EIT1007-SLAB]
                w_short = W * S / 3
                w_long = W * S / 3 * (3 - m * m) / 2
                for e in x_edges:
                    add(e, w_short if lx <= ly else w_long)
                for e in y_edges:
                    add(e, w_short if ly < lx else w_long)
    if lv.slab == "roof" and roof is not None:
        per_m = (roof.live_plan if part == "live" else roof.load_plan) * b.roof.overhang
        for _d, run in b.beam_lines(lv.name):
            for a, c in zip(run, run[1:]):
                if b.is_perimeter(a, c, lv.name):
                    add(_seg(a, c), per_m)
    if part != "live" and li + 1 < len(b.levels) and lv.walls != "none":
        above = b.levels[li + 1]
        hgt = above.elevation - lv.elevation - above.beam_depth
        wl = WALL_LOAD.get(lv.wall_type, 180) * max(0.0, hgt)           # [QD-WALL]
        for _d, run in b.beam_lines(lv.name):
            for a, c in zip(run, run[1:]):
                if lv.walls == "all" or b.is_perimeter(a, c, lv.name):
                    add(_seg(a, c), wl)
    return loads


def _beam_design(mat: Concrete, bw: float, h: float, m_neg: float, m_pos: float, v: float):
    fs = mat.fs("DB")
    R, j = mat.R(fs), mat.j(fs)
    b_cm, d = bw * 100, h * 100 - 5.0
    d_req = math.sqrt(max(m_neg, m_pos, 1.0) * 100 / (R * b_cm))
    rho_min = 14.0 / FY[mat.main_grade]                               # [EIT1007-MIN]

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
    s = max(5.0, _round_down(min(s, d / 2, 20.0), 2.5))
    ok = d_req <= d and vv <= 1.32 * math.sqrt(mat.fc_prime) + vc
    stir = f"{STIRRUP}@{s / 100:.3f}".rstrip("0")
    return d_req, as_top, as_bot, f"{nt}-{st}", f"{nb}-{sb}", stir, ok


def _min_depth(mat: Concrete, length: float, n_spans: int, k: int) -> float:
    """Depth that needs no deflection check [EIT1007-DEFL]."""
    if n_spans == 1:
        ratio = 16.0
    elif k in (0, n_spans - 1):
        ratio = 18.5
    else:
        ratio = 21.0
    return length / ratio * (0.4 + FY[mat.main_grade] / 7000.0)


def design_level_beams(b: Building, mat: Concrete, li: int, roof):
    lv = b.levels[li]
    ext = level_line_loads(b, li, roof)
    ext_live = level_line_loads(b, li, roof, "live")
    results, reactions, live_reac = [], {}, {}
    refs = cite(mat.ref, "EIT1007-SHEAR", "EIT1007-MIN", "EIT1007-DEFL", "UNIT-WT", "QD-WALL",
                "EIT1007-SLAB")
    for direction, run in b.beam_lines(lv.name):
        lengths = [abs((b.xs[c[0]] - b.xs[a[0]]) if direction == "x" else (b.ys[c[1]] - b.ys[a[1]]))
                   for a, c in zip(run, run[1:])]
        line = b.y_name(run[0][1]) if direction == "x" else b.x_name(run[0][0])
        h, bw = lv.beam_depth, lv.beam_width
        for _it in range(4):                     # re-run when the depth grows
            sw = CONCRETE_KG_M3 * bw * h
            loads = [ext.get(_seg(a, c), 0.0) + sw for a, c in zip(run, run[1:])]
            spans, reac = continuous_beam(lengths, loads)
            need = h
            for sp in spans:
                m_neg = max(0.0, -sp.m_left, -sp.m_right)
                d_req = _beam_design(mat, bw, h, m_neg, sp.m_pos, max(sp.v_left, sp.v_right))[0]
                need = max(need, _round_up((d_req + 5.0) / 100, 0.05))
            if need <= h + 1e-9 or need > MAX_BEAM_DEPTH:
                break
            h = need
        _sp, lreac = continuous_beam(lengths, [ext_live.get(_seg(a, c), 0.0) for a, c in zip(run, run[1:])])
        for k, ((a, c), sp) in enumerate(zip(zip(run, run[1:]), spans)):
            m_neg = max(0.0, -sp.m_left, -sp.m_right)
            d_req, at, ab, top, bot, stir, ok = _beam_design(mat, bw, h, m_neg, sp.m_pos,
                                                             max(sp.v_left, sp.v_right))
            notes = []
            if h != lv.beam_depth:
                notes.append(f"เพิ่มความลึกจาก {lv.beam_depth:.2f} เป็น {h:.2f} ม.")
            if not ok:
                notes.append("หน้าตัดไม่พอ ต้องเพิ่มขนาด")
            hmin = _min_depth(mat, sp.length, len(spans), k)
            if h + 1e-9 < hmin:
                notes.append(f"ลึกน้อยกว่า {hmin:.2f} ม. ต้องตรวจการแอ่นตัว")
            results.append(BeamResult(lv.name, line, f"{b.node_name(*a)}-{b.node_name(*c)}", "", bw, h,
                                      sp.length, sp.w, m_neg, sp.m_pos, max(sp.v_left, sp.v_right), d_req,
                                      at, ab, top, bot, stir, ok, " ; ".join(notes), hmin, refs))
        for node, rx, lx in zip(run, reac, lreac):
            reactions[node] = reactions.get(node, 0.0) + rx
            live_reac[node] = live_reac.get(node, 0.0) + lx
    return results, reactions, live_reac


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
    ties = _round_down(min(16 * BAR_DIA[size], 48 * BAR_DIA["RB6"], min(bw, h) * 100), 5.0)  # [EIT1007-TIE]
    ok = pg <= 0.08
    if not ok:
        note = "ปริมาณเหล็กเกิน 8% ต้องเพิ่มหน้าตัด"
    return bw, h, pg, f"{n}-{size}", f"RB6@{ties / 100:.2f}", ok, note


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
            t = max(0.30, _round_up((d + 7.5 + 1.6) / 100, 0.05))
            q = P / (side * side)
            while t < 1.5:                      # one-way shear
                d = t * 100 - 9.1
                V = q * side * max(0.0, (side - c / 100) / 2 - d / 100)
                if V <= mat.vc_beam * side * 100 * d:
                    break
                t += 0.05
            W = CONCRETE_KG_M3 * side * side * t
        arm = max(0.0, (side - c / 100) / 2)
        mom = q * side * arm * arm / 2
        d = t * 100 - 7.5 - 1.6
        bars = _footing_bars(mat, mom, side, t, d)
        return FootingResult(node, P, "spread", 0, "-", f.soil_qa, round(side, 2), round(side, 2),
                             round(t, 2), bars, bars, W, refs=cite("EIT1007-FOOT", mat.ref, "SOIL"))
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
            t = max(0.40, _round_up((d + 7.5 + 1.6) / 100, 0.05))
            R = P / len(pts)
            while t < 1.5 and not (_one_way_ok(mat, pts, R, c / 100, t * 100 - 9.1, L, 0) and
                                   _one_way_ok(mat, pts, R, c / 100, t * 100 - 9.1, B, 1)):
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
    d = t * 100 - 7.5 - 1.6
    mx = sum(R * (x - c / 200) for x, _y in pts if x - c / 200 > 0)
    my = sum(R * (y - c / 200) for _x, y in pts if y - c / 200 > 0)
    bars_x = _footing_bars(mat, mx, L, t, d)
    bars_y = _footing_bars(mat, my, B, t, d)
    ok = n <= MAX_PILES
    return FootingResult(node, P, "pile", len(pts) if ok else n, pile, cap, round(B, 2), round(L, 2),
                         round(t, 2), bars_x, bars_y, W, ok=ok, note=note,
                         refs=cite("EIT1007-FOOT", mat.ref, "QD-PILE", "SOIL", "UNIT-WT"))


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
    mat = Concrete(fc_prime=b.fc_prime, code=b.design_code)
    res = DesignResult(b, mat)
    if any(lv.slab == "roof" for lv in b.levels):
        res.roof = design_roof(b)
    n_lv = len(b.levels)
    node_reac: list[dict] = [dict() for _ in b.levels]
    node_live: list[dict] = [dict() for _ in b.levels]
    for li in reversed(range(n_lv)):
        lv = b.levels[li]
        if lv.slab in ("suspended", "on_ground"):
            for i, j in b.panels(lv.name):
                res.slabs.append(design_slab(b, mat, lv, i, j))
        beams, reac, live = design_level_beams(b, mat, li, res.roof)
        res.beams.extend(beams)
        node_reac[li], node_live[li] = reac, live
    reduce = b.ll_reduction and b.occupancy not in NO_REDUCTION
    elev = [lv.elevation for lv in b.levels]
    stub = b.foundation.depth - 0.40 + elev[0]
    col_refs = cite(mat.ref, "EIT1007-COL", "EIT1007-TIE", "UNIT-WT", "MR6-16" if reduce else "")
    for i, j in b.nodes():
        name = b.node_name(i, j)
        above = reduced = 0.0
        bw, h = b.column_width, b.column_depth
        segs = []
        for li in reversed(range(n_lv)):
            r = ll_reduction(n_lv - 1 - li) if reduce else 0.0           # [MR6-16]
            cut = node_live[li].get((i, j), 0.0) * r
            above += node_reac[li].get((i, j), 0.0) - cut
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
                                     live_reduced=reduced, refs=col_refs))
        res.columns.extend(reversed(segs))
        res.footings.append(design_footing(b, mat, name, above, bw, h))
    _assign_marks(res.columns, lambda c: (c.b, c.h, c.bars, c.ties), "C", lambda c: c.load)
    _assign_marks(res.footings, lambda f: (f.piles, f.pile, f.width, f.length, f.thickness,
                                           f.bars_x, f.bars_y), "F", lambda f: f.load)
    for lv in b.levels:
        _assign_marks([x for x in res.beams if x.level == lv.name],
                      lambda x: (x.b, x.h, x.top, x.bottom, x.stirrup), lv.beam_mark, lambda x: x.m_pos)
        _assign_marks([x for x in res.slabs if x.level == lv.name],
                      lambda x: (x.kind, x.case, x.thickness, x.bars_short, x.bars_long, x.bars_top),
                      "GS" if lv.slab == "on_ground" else "S", lambda x: x.m_pos)
    for group in (res.slabs, res.beams, res.columns, res.footings):
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
