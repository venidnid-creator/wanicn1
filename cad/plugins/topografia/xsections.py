# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 WANICNSURVEY contributors.
"""Cross sections straight from the imported points: a centreline found in
the point cloud (or a drawn one), stations every N metres, the design
elevation at each one, the cut and fill areas and the volumes between
stations, and the regions to hatch. Pure: no ezdxf, no Qt.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from .alignment import Station, point_at, polyline_length
from .profile import Template, _z_on, areas, cross_section, design_section, prismoidal
from .tin import Tin

Point = tuple[float, float]


# -- the centreline -----------------------------------------------------------------------

def auto_axis(points: list[Point], bins: int = 30) -> list[Point]:
    """A centreline through a corridor of survey points.

    The points are projected on their main direction (the larger axis of
    their spread), cut into ``bins`` slices along it, and each slice gives
    its centroid; three-point smoothing irons out the zig-zag of points
    shot left and right of the road. The line runs the whole length.
    """
    pts = [(float(x), float(y)) for x, y in points]
    if len(pts) < 2:
        raise ValueError("a centreline needs at least two points")
    n = len(pts)
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - cx) ** 2 for p in pts)
    syy = sum((p[1] - cy) ** 2 for p in pts)
    sxy = sum((p[0] - cx) * (p[1] - cy) for p in pts)
    angle = 0.5 * math.atan2(2.0 * sxy, sxx - syy)
    ux, uy = math.cos(angle), math.sin(angle)
    along = [((p[0] - cx) * ux + (p[1] - cy) * uy, p) for p in pts]
    t0 = min(t for t, _p in along)
    t1 = max(t for t, _p in along)
    if t1 - t0 < 1e-9:
        raise ValueError("the points have no length to follow")
    bins = max(2, min(bins, n // 2 or 1))
    width = (t1 - t0) / bins
    slices: list[list[Point]] = [[] for _ in range(bins)]
    for t, p in along:
        slices[min(bins - 1, int((t - t0) / width))].append(p)
    centres = [(sum(p[0] for p in s) / len(s), sum(p[1] for p in s) / len(s))
               for s in slices if s]
    if len(centres) >= 3:
        smooth = [centres[0]]
        for a, b, c in zip(centres, centres[1:], centres[2:]):
            smooth.append(((a[0] + b[0] + c[0]) / 3.0, (a[1] + b[1] + c[1]) / 3.0))
        smooth.append(centres[-1])
        centres = smooth

    # the ends reach the first and last points, along the main direction
    def at(t, ref):
        off = (ref[0] - cx) * -uy + (ref[1] - cy) * ux
        return (cx + ux * t - uy * off, cy + uy * t + ux * off)
    line = [at(t0, centres[0])] + centres + [at(t1, centres[-1])]
    out = [line[0]]
    for p in line[1:]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-6:
            out.append(p)
    return out


def trim_to_surface(axis: list[Point], tin: Tin, tolerance: float = 0.01) -> list[Point]:
    """The axis cut where it first and last stands on the surface, so a
    centreline found in the points does not start off the survey."""
    length = polyline_length(axis)

    def on(s: float) -> bool:
        st = point_at(axis, s)
        return tin.z_at(st.x, st.y) is not None

    probe = [k * length / 200.0 for k in range(201)]
    inside = [s for s in probe if on(s)]
    if not inside:
        return axis

    def edge(out_s: float, in_s: float) -> float:
        while abs(in_s - out_s) > tolerance:
            mid = (in_s + out_s) / 2.0
            if on(mid):
                in_s = mid
            else:
                out_s = mid
        return in_s
    s0 = inside[0] if inside[0] == 0.0 else edge(probe[probe.index(inside[0]) - 1], inside[0])
    s1 = inside[-1] if inside[-1] == probe[-1] else edge(probe[probe.index(inside[-1]) + 1], inside[-1])
    if s0 <= 0.0 and s1 >= length:
        return axis
    out = [point_at(axis, s0)]
    run_ = 0.0
    for p, q in zip(axis, axis[1:]):
        run_ += math.hypot(q[0] - p[0], q[1] - p[1])
        if s0 < run_ < s1:
            out.append(q)
    out.append(point_at(axis, s1))
    return [(st.x, st.y) if isinstance(st, Station) else st for st in out]


def half_width_of(points: list[Point], axis: list[Point]) -> float:
    """How far the points reach from the axis: the section half width."""
    best = 0.0
    for q in points:
        d = math.inf
        for p, r in zip(axis, axis[1:]):
            dx, dy = r[0] - p[0], r[1] - p[1]
            l2 = dx * dx + dy * dy
            t = 0.0 if l2 < 1e-18 else max(0.0, min(1.0, ((q[0] - p[0]) * dx + (q[1] - p[1]) * dy) / l2))
            d = min(d, math.hypot(q[0] - p[0] - t * dx, q[1] - p[1] - t * dy))
        best = max(best, d)
    return best


def station_list(axis: list[Point], interval: float, first: float = 0.0) -> list[Station]:
    """Stations every ``interval`` metres along the axis, and the end."""
    if interval <= 0:
        raise ValueError("the station interval must be positive")
    total = polyline_length(axis)
    out, s = [], max(0.0, first)
    while s < total - 1e-6:
        out.append(point_at(axis, s))
        s += interval
    out.append(point_at(axis, total))
    return out


# -- the design elevation -----------------------------------------------------------------

LEVEL, SLOPE, FIT = "level", "slope", "fit"


@dataclass
class Design:
    """How the design elevation runs along the axis: a constant level
    (MSL), a start level with a slope in percent, or the straight line
    that best fits the ground (cut and fill near balanced)."""

    mode: str = FIT
    level: float = 0.0          # LEVEL: the elevation; SLOPE: at chainage 0
    slope: float = 0.0          # SLOPE: percent, + rising along the axis
    offset: float = 0.0         # FIT: raise (+) or lower (-) the fitted line

    def grade(self, ground: list[tuple[float, Optional[float]]], length: float) -> list[Point]:
        """The grade line as (s, z) vertices over [0, length]."""
        if self.mode == LEVEL:
            return [(0.0, self.level), (length, self.level)]
        if self.mode == SLOPE:
            return [(0.0, self.level), (length, self.level + self.slope / 100.0 * length)]
        known = [(s, z) for s, z in ground if z is not None]
        if not known:
            raise ValueError("the axis does not cross the surface")
        if len(known) == 1:
            z = known[0][1] + self.offset
            return [(0.0, z), (length, z)]
        n = len(known)
        ms = sum(s for s, _z in known) / n
        mz = sum(z for _s, z in known) / n
        sss = sum((s - ms) ** 2 for s, _z in known)
        b = 0.0 if sss < 1e-12 else sum((s - ms) * (z - mz) for s, z in known) / sss
        a = mz - b * ms + self.offset
        return [(0.0, a), (length, a + b * length)]


# -- one section and the run of them ------------------------------------------------------

@dataclass
class Section:
    station: Station
    chainage: float                     # station label: start chainage + s
    ground: list[Point]                 # (offset, z)
    design: list[Point]
    z_ground: Optional[float]           # on the centreline
    z_design: float
    cut_area: float
    fill_area: float
    cut_volume: float = 0.0             # from the previous section
    fill_volume: float = 0.0
    cut_total: float = 0.0
    fill_total: float = 0.0

    @property
    def mass(self) -> float:
        return self.cut_total - self.fill_total


@dataclass
class Settings:
    interval: float = 25.0              # metres between stations
    start_chainage: float = 0.0         # the label of the first station
    half_width: float = 0.0             # 0: as far as the points reach
    sample: float = 0.5                 # ground sampled across, metres
    design: Design = field(default_factory=Design)
    template: Template = field(default_factory=Template)
    method: str = "end-area"            # or "prismoidal"
    # how the sheet is laid out, and what else comes with it
    pick_axis: bool = False             # a drawn centreline, else auto_axis
    grid: float = 1.0                   # elevation grid (MSL) in the sections
    vscale: float = 1.0                 # vertical exaggeration
    text_height: float = 0.0            # 0: from the section width
    columns: int = 3
    contour_interval: float = 1.0       # contours on the plan, 0: none
    table: bool = True                  # the earthworks table beside them
    max_edge: float = 0.0               # longest TIN edge when one is built

    def text_height_for(self, half_width: float) -> float:
        if self.text_height > 0:
            return self.text_height
        return max(0.2, round(2.0 * half_width / 50.0, 2))


def run(tin: Tin, axis: list[Point], settings: Settings, half_width: float) -> list[Section]:
    """Every station's ground, design, areas and the volumes between them."""
    stations = station_list(axis, settings.interval)
    length = polyline_length(axis)
    grade = settings.design.grade([(st.s, tin.z_at(st.x, st.y)) for st in stations], length)
    out: list[Section] = []

    def design_z(s: float) -> float:
        (s0, z0), (s1, z1) = grade[0], grade[-1]
        return z0 if s1 - s0 < 1e-12 else z0 + (s - s0) / (s1 - s0) * (z1 - z0)

    def measure(st: Station):
        ground = cross_section(tin, st, half_width, settings.sample)
        if len(ground) < 2:
            return None
        zd = design_z(st.s)
        design = design_section(ground, zd, settings.template)
        return ground, design, zd, areas(ground, design)

    cut_total = fill_total = 0.0
    previous: Optional[Section] = None
    for st in stations:
        found = measure(st)
        if found is None:
            previous = None
            continue
        ground, design, zd, (cut_a, fill_a) = found
        section = Section(st, settings.start_chainage + st.s, ground, design,
                          tin.z_at(st.x, st.y), zd, cut_a, fill_a)
        if previous is not None:
            length_ = st.s - previous.station.s
            if settings.method == "prismoidal":
                mid = measure(point_at(axis, (previous.station.s + st.s) / 2.0))
                cm, fm = (mid[3] if mid else ((previous.cut_area + cut_a) / 2.0,
                                               (previous.fill_area + fill_a) / 2.0))
                section.cut_volume = prismoidal(previous.cut_area, cm, cut_a, length_)
                section.fill_volume = prismoidal(previous.fill_area, fm, fill_a, length_)
            else:
                section.cut_volume = length_ * (previous.cut_area + cut_a) / 2.0
                section.fill_volume = length_ * (previous.fill_area + fill_a) / 2.0
        cut_total += section.cut_volume
        fill_total += section.fill_volume
        section.cut_total, section.fill_total = cut_total, fill_total
        out.append(section)
        previous = section
    return out


# -- the regions to hatch -----------------------------------------------------------------

def regions(ground: list[Point], design: list[Point]) -> list[tuple[str, list[Point]]]:
    """The cut ("cut", ground above design) and fill ("fill") regions
    between the two lines, each a closed (offset, z) polygon."""
    if len(ground) < 2 or len(design) < 2:
        return []
    lo = max(ground[0][0], design[0][0])
    hi = min(ground[-1][0], design[-1][0])
    if hi <= lo:
        return []
    breaks = sorted({o for o, _ in ground if lo <= o <= hi}
                    | {o for o, _ in design if lo <= o <= hi} | {lo, hi})
    samples = [(o, _z_on(ground, o), _z_on(design, o)) for o in breaks]
    # split at every crossing so each stretch has one sign
    split = [samples[0]]
    for (o0, g0, d0), (o1, g1, d1) in zip(samples, samples[1:]):
        a, b = g0 - d0, g1 - d1
        if a * b < 0:
            t = a / (a - b)
            o = o0 + t * (o1 - o0)
            z = g0 + t * (g1 - g0)
            split.append((o, z, z))
        split.append((o1, g1, d1))
    out: list[tuple[str, list[Point]]] = []
    run_: list[tuple[float, float, float]] = []
    kind = None
    eps = 1e-6

    def close():
        if len(run_) >= 2 and kind is not None:
            top = [(o, g) for o, g, _d in run_]
            bottom = [(o, d) for o, _g, d in reversed(run_)]
            poly = top + bottom
            area = 0.5 * abs(sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(poly, poly[1:] + poly[:1])))
            if area > 1e-6:
                out.append((kind, poly))

    for o, g, d in split:
        here = "cut" if g - d > eps else "fill" if d - g > eps else None
        if here is None:                    # on the design: closes and opens
            run_.append((o, g, d))
            close()
            run_, kind = [(o, g, d)], None
            continue
        if kind is None or here == kind:
            kind = here
            run_.append((o, g, d))
        else:
            close()
            run_, kind = [run_[-1], (o, g, d)], here
    close()
    return out
