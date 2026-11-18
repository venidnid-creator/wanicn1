# -*- coding: utf-8 -*-
"""Design chain: roof → slabs → beams → columns → footings → piles.

Units inside: lengths m, loads kg, moments kg-m; section checks in cm and
ksc. Working stress design (วสท.); every result needs a licensed
engineer's check and signature before it is used.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .analysis import continuous_beam
from .building import LIVE_LOAD, ROOF_COVER_LOAD, WALL_LOAD, Building  # noqa: F401
from .materials import CONCRETE_KG_M3, FY, Concrete
from .sections import BAR_DIA, bar_area, load_c_sections, load_piles, pick_bars, pick_spacing

PURLIN_FB = 1400.0          # allowable bending stress of cold-formed C, ksc (QuickDesign purlin sheet)
MAX_BEAM_DEPTH = 1.00       # m, auto-sizing stops here
MAX_COLUMN = 0.60           # m
MAX_PILES = 5               # piles per footing (QuickDesign limit)
STIRRUP = "RB6"

#: Two-way slab moment coefficients, case 5 (discontinuous on four sides),
#: short-span ratio m = 1.0 … 0.5 — the table in the QuickDesign appendix.
CASE5_M = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]
CASE5_NEG = [0.033, 0.038, 0.043, 0.047, 0.053, 0.055]
CASE5_POS = [0.050, 0.057, 0.064, 0.072, 0.080, 0.083]
CASE5_LONG_NEG, CASE5_LONG_POS = 0.033, 0.050


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


@dataclass
class RoofResult:
    load_plan: float               # kg/m² of plan, to the roof beams
    plan_area: float
    slope_area: float
    ridge: float
    hips: float
    eave: float
    purlin: SteelMember
    rafter: SteelMember
    steel_kg: float


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


@dataclass
class ColumnResult:
    node: str
    segment: str                   # e.g. "ฐาน–GB", "GB–FL2"
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


@dataclass
class FootingResult:
    node: str
    load: float                    # column load, kg
    kind: str                      # pile / spread
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


# ---------------------------------------------------------------------------
# Roof
# ---------------------------------------------------------------------------

def _pick_c(mx: float, my: float, role: str, span: float) -> SteelMember:
    sx_req = mx * 100 / PURLIN_FB
    sy_req = my * 100 / PURLIN_FB
    table = load_c_sections()
    for s in table:                        # sorted lightest first
        if s["zx_cm3"] >= sx_req and s["zy_cm3"] >= sy_req:
            return SteelMember(role, span, mx, my, sx_req, sy_req, s["name"], s["zx_cm3"],
                               s["zy_cm3"], s["kg_m"], True, s["source"])
    s = table[-1]
    return SteelMember(role, span, mx, my, sx_req, sy_req, s["name"], s["zx_cm3"], s["zy_cm3"],
                       s["kg_m"], False, "ใหญ่สุดในตารางยังไม่พอ")


def design_roof(b: Building) -> RoofResult:
    r = b.roof
    th = math.radians(r.slope_deg)
    cos, sin = math.cos(th), math.sin(th)
    cover = ROOF_COVER_LOAD.get(r.cover, 50)
    load_plan = (cover + r.frame_load) / cos + r.live_load
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
    # Purlin (QuickDesign sheet): W = covering + live load per m² of slope,
    # spanning the rafter spacing, bent about both axes (no sag rods).
    w_p = (cover + r.live_load) * r.purlin_spacing
    L = r.rafter_spacing
    purlin = _pick_c(w_p * cos * L * L / 8, w_p * sin * L * L / 8, "แป", L)
    # Rafter: ridge to the outer roof beam along the slope, simply supported,
    # carrying covering + purlins + live load over the rafter spacing.
    span = (short / 2 - r.overhang) / cos if short / 2 > r.overhang else short / 2 / cos
    w_r = (cover + r.frame_load + r.live_load) * r.rafter_spacing
    rafter = _pick_c(w_r * cos * span * span / 8, 0.0, "จันทัน", span)
    steel = (slope_area / r.purlin_spacing) * purlin.kg_m + \
            (slope_area / r.rafter_spacing) * rafter.kg_m + \
            (ridge + hips) * 2 * rafter.kg_m
    return RoofResult(load_plan, plan_area, slope_area, ridge, hips, eave, purlin, rafter, steel)


# ---------------------------------------------------------------------------
# Slabs
# ---------------------------------------------------------------------------

def _panel_name(b: Building, i: int, j: int) -> str:
    return f"{b.x_name(i)}-{b.x_name(i + 1)}/{b.y_name(j)}-{b.y_name(j + 1)}"


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
    as_min = 0.0025 * 100 * t * 100           # cm²/m, SR24
    smax = min(3 * t * 100, 45.0)
    if lv.slab == "on_ground":
        bars = f"RB9@{pick_spacing(as_min, 'RB9', smax):.2f}"
        return SlabResult(lv.name, name, "", "on-ground", lx, ly, m, 0.0, 0, 0, 0, t, 0.0,
                          bars, bars, "-", True, "พื้นวางบนดิน ใช้เหล็กกันร้าว")
    W = CONCRETE_KG_M3 * t + lv.finish_load + lv.live_load
    if m < 0.5:
        kind = "one-way"
        m_pos = W * S * S / 8
        m_neg = W * S * S / 24
        m_long = 0.0
        t_min = S / 20
    else:
        kind = "two-way"
        m_pos = _interp(m, CASE5_M, CASE5_POS) * W * S * S
        m_neg = _interp(m, CASE5_M, CASE5_NEG) * W * S * S
        m_long = CASE5_LONG_POS * W * S * S
        t_min = max(0.08, 2 * (lx + ly) / 180)
    d_req = math.sqrt(max(m_pos, m_neg) * 100 / (R * 100))
    ok = d_req <= d and t + 1e-9 >= t_min
    note = "" if ok else (f"ความหนาน้อยกว่า {t_min:.3f} ม." if t < t_min else "ความลึกไม่พอ")

    def bars(mom):
        as_ = max(mom * 100 / (fs * jj * d), as_min) if d > 0 else as_min
        return f"RB9@{pick_spacing(as_, 'RB9', smax):.2f}"

    long_bars = bars(m_long) if kind == "two-way" else f"RB9@{pick_spacing(as_min, 'RB9', smax):.2f}"
    return SlabResult(lv.name, name, "", kind, lx, ly, m, W, m_pos, m_neg, m_long, t, d_req,
                      bars(m_pos), long_bars, bars(m_neg), ok, note)


# ---------------------------------------------------------------------------
# Beams
# ---------------------------------------------------------------------------

def _seg(a, b):
    return (a, b) if a <= b else (b, a)


def level_line_loads(b: Building, li: int, roof: RoofResult | None) -> dict:
    """Uniform load (kg/m) on every beam segment of level ``li``, without the
    beam's own weight: slab panels, walls standing on it, roof load."""
    lv = b.levels[li]
    loads: dict = {}

    def add(seg, w):
        loads[seg] = loads.get(seg, 0.0) + w

    if lv.slab == "suspended":
        W = CONCRETE_KG_M3 * lv.slab_thickness + lv.finish_load + lv.live_load
    elif lv.slab == "roof" and roof is not None:
        W = roof.load_plan
    else:
        W = 0.0
    if W:
        for i, j in b.panels():
            lx = b.xs[i + 1] - b.xs[i]
            ly = b.ys[j + 1] - b.ys[j]
            S, Lg = min(lx, ly), max(lx, ly)
            m = S / Lg
            x_edges = [_seg((i, j), (i + 1, j)), _seg((i, j + 1), (i + 1, j + 1))]
            y_edges = [_seg((i, j), (i, j + 1)), _seg((i + 1, j), (i + 1, j + 1))]
            if m < 0.5:
                long_edges = x_edges if lx >= ly else y_edges
                for e in long_edges:
                    add(e, W * S / 2)
            else:
                w_short = W * S / 3
                w_long = W * S / 3 * (3 - m * m) / 2
                for e in x_edges:
                    add(e, w_short if lx <= ly else w_long)
                for e in y_edges:
                    add(e, w_short if ly < lx else w_long)
    if lv.slab == "roof" and roof is not None:
        for _d, run in b.beam_lines():
            for a, c in zip(run, run[1:]):
                if b.is_perimeter(a, c):
                    add(_seg(a, c), roof.load_plan * b.roof.overhang)
    if li + 1 < len(b.levels) and lv.walls != "none":
        above = b.levels[li + 1]
        hgt = above.elevation - lv.elevation - above.beam_depth
        wl = WALL_LOAD.get(lv.wall_type, 180) * max(0.0, hgt)
        for _d, run in b.beam_lines():
            for a, c in zip(run, run[1:]):
                if lv.walls == "all" or b.is_perimeter(a, c):
                    add(_seg(a, c), wl)
    return loads


def _beam_design(mat: Concrete, bw: float, h: float, m_neg: float, m_pos: float, v: float):
    fs = mat.fs("DB")
    R, j = mat.R(fs), mat.j(fs)
    b_cm, d = bw * 100, h * 100 - 5.0
    d_req = math.sqrt(max(m_neg, m_pos, 1.0) * 100 / (R * b_cm))
    rho_min = 14.0 / FY[mat.main_grade]

    def as_of(mom):
        req = mom * 100 / (fs * j * d)
        return max(req, min(rho_min * b_cm * d, 4 / 3 * req))

    as_top, as_bot = as_of(m_neg), as_of(m_pos)
    nt, st = pick_bars(as_top, b_cm)
    nb, sb = pick_bars(as_bot, b_cm)
    vv = v / (b_cm * d)
    vc = mat.vc_beam
    av = 2 * bar_area(STIRRUP)
    fv = mat.fs(STIRRUP)
    s = av * fv / ((vv - vc) * b_cm) if vv > vc else d / 2
    s = max(5.0, _round_down(min(s, d / 2, 20.0), 2.5))
    ok = d_req <= d and vv <= 1.32 * math.sqrt(mat.fc_prime) + vc
    return d_req, as_top, as_bot, f"{nt}-{st}", f"{nb}-{sb}", f"{STIRRUP}@{s / 100:.3f}".rstrip("0"), ok


def design_level_beams(b: Building, mat: Concrete, li: int, roof):
    lv = b.levels[li]
    ext = level_line_loads(b, li, roof)
    results, reactions = [], {}
    for direction, run in b.beam_lines():
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
        for (a, c), sp in zip(zip(run, run[1:]), spans):
            m_neg = max(0.0, -sp.m_left, -sp.m_right)
            d_req, at, ab, top, bot, stir, ok = _beam_design(mat, bw, h, m_neg, sp.m_pos,
                                                             max(sp.v_left, sp.v_right))
            note = "" if h == lv.beam_depth else f"เพิ่มความลึกจาก {lv.beam_depth:.2f} เป็น {h:.2f} ม."
            if not ok:
                note = (note + " ; " if note else "") + "หน้าตัดไม่พอ ต้องเพิ่มขนาด"
            span_name = f"{b.node_name(*a)}-{b.node_name(*c)}"
            results.append(BeamResult(lv.name, line, span_name, "", bw, h, sp.length, sp.w,
                                      m_neg, sp.m_pos, max(sp.v_left, sp.v_right), d_req, at, ab,
                                      top, bot, stir, ok, note))
        for node, rx in zip(run, reac):
            reactions[node] = reactions.get(node, 0.0) + rx
    return results, reactions


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------

def _column_design(mat: Concrete, P: float, bw: float, h: float):
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
    ties = _round_down(min(16 * BAR_DIA[size], 48 * BAR_DIA["RB6"], min(bw, h) * 100), 5.0)
    ok = pg <= 0.08
    if not ok:
        note = "ปริมาณเหล็กเกิน 8% ต้องเพิ่มหน้าตัด"
    return bw, h, pg, f"{n}-{size}", f"RB6@{ties / 100:.2f}", ok, note


# ---------------------------------------------------------------------------
# Footings
# ---------------------------------------------------------------------------

def _pile_layout(n: int, s: float):
    """Pile coordinates (m) about the footing centre, and the extent."""
    if n == 1:
        pts = [(0, 0)]
    elif n == 2:
        pts = [(-s / 2, 0), (s / 2, 0)]
    elif n == 3:
        r = s / math.sqrt(3)
        pts = [(0, r), (-s / 2, -r / 2), (s / 2, -r / 2)]
    elif n == 4:
        pts = [(x, y) for x in (-s / 2, s / 2) for y in (-s / 2, s / 2)]
    else:  # 5: four corners and the centre
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
        n = max(n, math.ceil((width - 0.15) / 0.30) + 1)      # spacing ≤ 0.30 m
        if (width - 0.15) / max(n - 1, 1) >= 0.10:
            return f"{n}-{size}"
    return f"{n}-DB20"


def design_footing(b: Building, mat: Concrete, node: str, P: float, col_b: float, col_h: float):
    f = b.foundation
    c = (col_b + col_h) / 2 * 100              # cm
    vp = mat.vc_punch
    if f.kind == "spread":
        W = 0.0
        for _ in range(5):
            side = _round_up(math.sqrt((P + W) / f.soil_qa), 0.05)
            d = (-c + math.sqrt(c * c + P / vp)) / 2
            t = max(0.30, _round_up((d + 7.5 + 1.6) / 100, 0.05))
            W = CONCRETE_KG_M3 * side * side * t
        q = P / (side * side)
        arm = max(0.0, (side - c / 100) / 2)
        mom = q * side * arm * arm / 2
        d = t * 100 - 7.5 - 1.6
        bars = _footing_bars(mat, mom, side, t, d)
        return FootingResult(node, P, "spread", 0, "-", f.soil_qa, round(side, 2), round(side, 2),
                             round(t, 2), bars, bars, W)
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
                         round(t, 2), bars_x, bars_y, W, ok=ok, note=note)


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
    mat = Concrete(fc_prime=b.fc_prime)
    res = DesignResult(b, mat)
    if any(lv.slab == "roof" for lv in b.levels):
        res.roof = design_roof(b)
    # Slabs and beams, top level first (the order the loads travel).
    node_reac: list[dict] = [dict() for _ in b.levels]
    for li in reversed(range(len(b.levels))):
        lv = b.levels[li]
        if lv.slab in ("suspended", "on_ground"):
            for i, j in b.panels():
                res.slabs.append(design_slab(b, mat, lv, i, j))
        beams, reac = design_level_beams(b, mat, li, res.roof)
        res.beams.extend(beams)
        node_reac[li] = reac
    # Columns: accumulate down from the top level.
    elev = [lv.elevation for lv in b.levels]
    stub = b.foundation.depth - 0.40 + elev[0]
    for i, j in b.nodes():
        name = b.node_name(i, j)
        above = 0.0
        bw, h = b.column_width, b.column_depth
        segs = []
        for li in reversed(range(len(b.levels))):
            # segment just below level li carries every level from li up
            above += node_reac[li].get((i, j), 0.0)
            if li == 0:
                hgt, seg = stub, f"ฐานราก–{b.levels[0].name}"
            else:
                hgt, seg = elev[li] - elev[li - 1], f"{b.levels[li - 1].name}–{b.levels[li].name}"
            above += CONCRETE_KG_M3 * bw * h * hgt
            cb, ch, pg, bars, ties, ok, note = _column_design(res.concrete, above, bw, h)
            bw, h = max(bw, cb), max(h, ch)      # a column never gets smaller going down
            segs.append(ColumnResult(name, seg, hgt, above, cb, ch, pg, bars, ties, ok=ok, note=note))
        res.columns.extend(reversed(segs))
        res.footings.append(design_footing(b, mat, name, above, bw, h))
    _assign_marks(res.columns, lambda c: (c.b, c.h, c.bars, c.ties), "C", lambda c: c.load)
    _assign_marks(res.footings, lambda f: (f.piles, f.pile, f.width, f.length, f.thickness,
                                           f.bars_x, f.bars_y), "F", lambda f: f.load)
    for lv in b.levels:
        prefix = lv.beam_mark
        _assign_marks([x for x in res.beams if x.level == lv.name],
                      lambda x: (x.b, x.h, x.top, x.bottom, x.stirrup), prefix, lambda x: x.m_pos)
        _assign_marks([x for x in res.slabs if x.level == lv.name],
                      lambda x: (x.kind, x.thickness, x.bars_short, x.bars_long, x.bars_top),
                      "GS" if lv.slab == "on_ground" else "S", lambda x: x.m_pos)
    for group in (res.slabs, res.beams, res.columns, res.footings):
        for x in group:
            if not x.ok:
                res.warnings.append(f"{type(x).__name__[:-6]} {getattr(x, 'span', '') or getattr(x, 'panel', '') or x.node}"
                                    f" ({x.mark}): {x.note}")
    if res.roof and not (res.roof.purlin.ok and res.roof.rafter.ok):
        res.warnings.append("หลังคา: เหล็กแปหรือจันทันในตารางไม่พอ")
    return res
