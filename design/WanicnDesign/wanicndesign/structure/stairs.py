# -*- coding: utf-8 -*-
"""Reinforced concrete stairs in a grid bay.

Two layouts, as in the QuickDesign stair menus [QD-STAIR]:

* ``straight`` — one flight from the start edge (bottom level) to the far
  edge (top level); the waist slab spans the bay from the bottom-level beam
  to the top-level beam.
* ``landing`` — two flights side by side, each half the bay wide, turning
  on a landing at the far edge. The landing and both flights rest on a
  stair beam BT along the far edge at landing height, carried by the two
  corner columns. Flight 1 starts on the bottom-level beam of the start
  edge, flight 2 arrives at the top-level beam of the start edge.

Each flight is a one-way slab strip, simply supported over the bay length
[STATICS], with the inclined part loaded by the waist t/cosθ plus half a
riser of concrete and the landing by t [UNIT-WT]; finishes and the stair
live load of กฎกระทรวง ฉบับที่ 6 ข้อ 15 [MR6-15]. Geometry is checked against
กฎกระทรวง ฉบับที่ 55 ข้อ 23–24 [MR55-STAIR]; thickness against the
one-way slab minimum [EIT1007-SLABMIN].
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..standards import cite
from .analysis import continuous_beam, partial_udl
from .materials import CONCRETE_KG_M3, FY
from .sections import bar_area, pick_spacing

#: Stair live load, kg/m², by building use — กฎกระทรวง ฉบับที่ 6 ข้อ 15:
#: halls, stairs and corridors 300 (apartments, hotels, offices, banks),
#: 400 (commercial buildings, schools, hospitals), 500 (markets,
#: department stores, assembly halls). Houses are not listed separately;
#: 300 is used (the lowest stair value in the table, on the safe side).
STAIR_LIVE = {"house": 300, "apartment": 300, "office": 300, "commercial": 400,
              "assembly": 500, "industrial": 500, "archive": 500}

#: Geometry limits — กฎกระทรวง ฉบับที่ 55 ข้อ 23 (residential buildings)
#: and ข้อ 24 (other buildings): riser max, tread min, clear width min,
#: rise of one flight max (m).
RULES = {"residential": {"riser": 0.20, "tread": 0.22, "width": 0.80, "rise": 3.00},
         "other": {"riser": 0.18, "tread": 0.25, "width": 1.20, "rise": 4.00}}
RESIDENTIAL = {"house"}
PIECES = 24
MAIN_BAR, TEMP_BAR = "DB12", "RB9"


@dataclass
class Flight:
    risers: int
    going: float          # horizontal length of the treads, m
    width: float
    offset: tuple         # (from, to) along the start edge, m from its lower end
    z_from: float
    z_to: float


@dataclass
class StairGeom:
    i: int
    j: int
    axis: str             # "x" or "y"
    sign: int             # +1 travels towards the larger coordinate
    length: float         # bay length along the travel (the span), m
    width: float          # bay width across, m
    li0: int
    li1: int
    z0: float
    z1: float
    risers: int
    riser: float
    tread: float
    start: tuple          # nodes of the start edge
    far: tuple            # nodes of the far edge
    flights: list = field(default_factory=list)
    landing_z: float | None = None


@dataclass
class StairResult:
    name: str
    level: str            # bottom level
    panel: str
    kind: str
    risers: int
    riser: float
    tread: float
    span: float
    width: float          # one flight
    thickness: float
    load: float           # kg/m² on the inclined part (plan)
    moment: float         # kg-m per m width
    d_req: float
    bars_main: str
    bars_top: str
    bars_temp: str
    ok: bool
    note: str = ""
    mark: str = ""
    refs: str = ""
    geom: StairGeom | None = None


def rules_for(b) -> dict:
    return RULES["residential" if b.occupancy in RESIDENTIAL else "other"]


def live_load(b, st) -> float:
    return st.live_load or STAIR_LIVE.get(b.occupancy, 300)


def geometry(b, st) -> StairGeom | None:
    names = [lv.name for lv in b.levels]
    if st.level not in names or names.index(st.level) + 1 >= len(names):
        return None
    li0 = names.index(st.level)
    li1 = li0 + 1
    i, j = b.stair_ij(st)
    if not (0 <= i < len(b.xs) - 1 and 0 <= j < len(b.ys) - 1):
        return None
    axis, sign = st.direction[-1], (-1 if st.direction.startswith("-") else 1)
    xs, ys = b.xs, b.ys
    if axis == "y":
        length, width = ys[j + 1] - ys[j], xs[i + 1] - xs[i]
        js, jf = (j, j + 1) if sign > 0 else (j + 1, j)
        start, far = ((i, js), (i + 1, js)), ((i, jf), (i + 1, jf))
    else:
        length, width = xs[i + 1] - xs[i], ys[j + 1] - ys[j]
        is_, if_ = (i, i + 1) if sign > 0 else (i + 1, i)
        start, far = ((is_, j), (is_, j + 1)), ((if_, j), (if_, j + 1))
    z0, z1 = b.levels[li0].elevation, b.levels[li1].elevation
    H = z1 - z0
    rule = rules_for(b)
    n = max(2, math.ceil(H / rule["riser"] - 1e-9))
    riser = H / n
    g = StairGeom(i, j, axis, sign, length, width, li0, li1, z0, z1, n, riser, st.tread, start, far)
    if st.kind == "straight":
        g.flights = [Flight(n, (n - 1) * st.tread, width, (0.0, width), z0, z1)]
    else:
        r1 = math.ceil(n / 2)
        r2 = n - r1
        half = width / 2
        g.landing_z = z0 + r1 * riser
        g.flights = [Flight(r1, (r1 - 1) * st.tread, half, (0.0, half), z0, g.landing_z),
                     Flight(r2, (r2 - 1) * st.tread, half, (half, width), g.landing_z, z1)]
    return g


def strip(g: StairGeom, f: Flight, t: float, finish: float, live: float, part: str = "total"):
    """One metre of flight: ``(M, R_start, R_far, w_inclined, w_flat)``."""
    cos = g.tread / math.hypot(g.tread, g.riser)
    inc = CONCRETE_KG_M3 * (t / cos + g.riser / 2) + finish
    flat = CONCRETE_KG_M3 * t + finish
    if part == "live":
        inc = flat = live
    else:
        inc, flat = inc + live, flat + live
    going = min(f.going, g.length)
    pts = partial_udl(inc, 0.0, going, PIECES) + partial_udl(flat, going, g.length, PIECES)
    (sp,), (r0, r1) = continuous_beam([g.length], [0.0], [pts])
    return sp.m_pos, r0, r1, inc, flat


def min_thickness(span: float, fy: float) -> float:
    """Simply supported one-way slab: L/20 × (0.4 + fy/7000) [EIT1007-SLABMIN]."""
    return span / 20 * (0.4 + fy / 7000)


def design_stair(b, mat, st) -> StairResult:
    g = geometry(b, st)
    refs = cite(mat.ref, "STATICS", "UNIT-WT", "MR6-15", "MR55-STAIR", "EIT1007-SLABMIN", "EIT1007-TEMP",
                "EIT1007-SHEAR", "QD-STAIR")
    if g is None:
        return StairResult(st.name, st.level, st.panel, st.kind, 0, 0, st.tread, 0, 0, st.thickness, 0, 0, 0,
                           "-", "-", "-", False, "ตำแหน่งหรือชั้นของบันไดไม่ถูกต้อง", refs=refs)
    rule = rules_for(b)
    notes, ok = [], True
    fy = FY[mat.main_grade]
    t_min = min_thickness(g.length, fy)
    t = st.thickness
    if t + 1e-9 < t_min:
        t = math.ceil(t_min / 0.01 - 1e-9) * 0.01
        notes.append(f"เพิ่มความหนาจาก {st.thickness:.2f} เป็น {t:.2f} ม. (≥ L/20)")
    live = live_load(b, st)
    m = max(strip(g, f, t, st.finish_load, live)[0] for f in g.flights)
    v = max(max(strip(g, f, t, st.finish_load, live)[1:3]) for f in g.flights)
    w_inc = strip(g, g.flights[0], t, st.finish_load, live)[3]
    fs = mat.fs(MAIN_BAR)
    R, jj = mat.R(fs), mat.j(fs)
    d = t * 100 - 2.5 - 0.6
    d_req = math.sqrt(m * 100 / (R * 100))
    if d_req > d:
        ok = False
        notes.append("ความลึกไม่พอ ต้องเพิ่มความหนา")
    as_min = 0.0025 * 100 * t * 100                                   # [EIT1007-TEMP]
    smax = min(3 * t * 100, 45.0)
    as_main = max(m * 100 / (fs * jj * d), as_min)
    main = f"{MAIN_BAR}@{pick_spacing(as_main, MAIN_BAR, smax):.2f}"
    top = f"{MAIN_BAR}@{pick_spacing(max(as_main / 2, as_min), MAIN_BAR, smax):.2f}"
    temp = f"{TEMP_BAR}@{pick_spacing(as_min, TEMP_BAR, smax):.2f}"
    if v / (100 * d) > mat.vc_beam:                                     # [EIT1007-SHEAR]
        ok = False
        notes.append("แรงเฉือนเกิน ต้องเพิ่มความหนา")
    # geometry — กฎกระทรวง ฉบับที่ 55
    width = g.flights[0].width
    if g.riser > rule["riser"] + 1e-9:
        ok = False
        notes.append(f"ลูกตั้ง {g.riser * 100:.1f} ซม. เกิน {rule['riser'] * 100:.0f} ซม.")
    if st.tread + 1e-9 < rule["tread"]:
        ok = False
        notes.append(f"ลูกนอน {st.tread * 100:.0f} ซม. น้อยกว่า {rule['tread'] * 100:.0f} ซม.")
    if width + 1e-9 < rule["width"]:
        ok = False
        notes.append(f"กว้าง {width:.2f} ม. น้อยกว่า {rule['width']:.2f} ม.")
    if max(f.z_to - f.z_from for f in g.flights) > rule["rise"] + 1e-9:
        ok = False
        notes.append(f"ช่วงบันไดสูงเกิน {rule['rise']:.1f} ม. ต้องมีชานพัก")
    for f in g.flights:
        need = f.going + (width if st.kind == "landing" else 0.0)
        if need > g.length + 1e-9:
            ok = False
            notes.append(f"ช่องกริดยาว {g.length:.2f} ม. ไม่พอ (ต้องการ {need:.2f} ม. รวมชานพัก)")
            break
    blondel = 2 * g.riser + st.tread
    if not 0.60 <= blondel <= 0.65:
        notes.append(f"2R+T = {blondel * 100:.0f} ซม. (แนะนำ 60–65 ซม.)")
    for a, c, lvl in ((g.start[0], g.start[1], b.levels[g.li0].name),
                      ((g.start if st.kind == "landing" else g.far) + (b.levels[g.li1].name,))):
        if not b.has_beam(lvl, a, c):
            ok = False
            notes.append(f"ไม่มีคานรองรับบันไดที่ {lvl} {b.node_name(*a)}-{b.node_name(*c)}")
    return StairResult(st.name, st.level, st.panel, st.kind, g.risers, g.riser, st.tread, g.length, width, t,
                       w_inc, m, d_req, main, top, temp, ok, " ; ".join(notes), refs=refs, geom=g)


def beam_loads(b, li: int, part: str = "total"):
    """Stair reactions on the beams of level ``li``:
    ``{(a, c): [(position, P)]}``, positions from the lower node."""
    out: dict = {}
    for st in b.stairs:
        g = geometry(b, st)
        if g is None or li not in (g.li0, g.li1):
            continue
        res = design_stair_thickness(b, st, g)
        live = live_load(b, st)
        for k, f in enumerate(g.flights):
            _m, r0, r1, _wi, _wf = strip(g, f, res, st.finish_load, live, part)
            targets = []
            if st.kind == "straight":
                targets = [(g.li0, g.start, r0), (g.li1, g.far, r1)]
            else:
                targets = [((g.li0 if k == 0 else g.li1), g.start, r0)]
            for lvl, (a, c), r in targets:
                if lvl != li:
                    continue
                key = (a, c) if a <= c else (c, a)
                out.setdefault(key, []).extend(partial_udl(r, f.offset[0], f.offset[1], PIECES))
    return out


def design_stair_thickness(b, st, g) -> float:
    from .materials import Concrete
    fy = FY[Concrete().main_grade]
    t_min = min_thickness(g.length, fy)
    return st.thickness if st.thickness + 1e-9 >= t_min else math.ceil(t_min / 0.01 - 1e-9) * 0.01


def landing_line(b, st, part: str = "total"):
    """Loads on the stair beam BT of a ``landing`` stair:
    ``(geometry, length, [(a, P)])``, positions from the far edge's lower node."""
    g = geometry(b, st)
    if g is None or st.kind != "landing":
        return None
    t = design_stair_thickness(b, st, g)
    live = live_load(b, st)
    pts = []
    for f in g.flights:
        r1 = strip(g, f, t, st.finish_load, live, part)[2]
        pts += partial_udl(r1, f.offset[0], f.offset[1], PIECES)
    return g, g.width, pts


def concrete_volume(res: StairResult) -> float:
    """Waist, steps and landing concrete of one stair, m³."""
    g = res.geom
    if g is None:
        return 0.0
    vol = 0.0
    for f in g.flights:
        incl = math.hypot(f.going, f.z_to - f.z_from)
        vol += f.width * (incl * res.thickness + (f.risers - 1) * g.riser * g.tread / 2)
        vol += f.width * max(0.0, g.length - f.going) * res.thickness
    return vol


def plan_point(b, g: StairGeom, u: float, v: float) -> tuple[float, float]:
    """Plan (x, y) of a point ``u`` along the travel from the start edge and
    ``v`` across from the start edge's lower node."""
    a = g.start[0] if g.start[0] <= g.start[1] else g.start[1]
    x0, y0 = b.xs[a[0]], b.ys[a[1]]
    if g.axis == "y":
        return x0 + v, y0 + g.sign * u
    return x0 + g.sign * u, y0 + v


def flight_surfaces(b, g: StairGeom, kind: str):
    """Top surfaces of the flights and landings as 3D quads."""
    out = []
    for k, f in enumerate(g.flights):
        v0, v1 = f.offset
        going = min(f.going, g.length)
        if kind == "landing" and k == 1:
            za, zb = f.z_to, f.z_from              # flight 2 rises towards the start edge
        else:
            za, zb = f.z_from, f.z_to
        for u0, u1, z0, z1 in ((0.0, going, za, zb), (going, g.length, zb, zb)):
            if u1 - u0 < 1e-6:
                continue
            p = [plan_point(b, g, u0, v0), plan_point(b, g, u1, v0), plan_point(b, g, u1, v1),
                 plan_point(b, g, u0, v1)]
            out.append([(p[0][0], p[0][1], z0), (p[1][0], p[1][1], z1), (p[2][0], p[2][1], z1),
                        (p[3][0], p[3][1], z0)])
    return out


def tread_lines(b, g: StairGeom):
    """Plan lines of the tread nosings, per flight."""
    out = []
    for f in g.flights:
        v0, v1 = f.offset
        for t in range(f.risers):
            u = t * g.tread
            if u > g.length + 1e-9:
                break
            out.append((plan_point(b, g, u, v0), plan_point(b, g, u, v1)))
    return out
