# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeCAD contributors.
"""The ground along an axis and across it, and the earthworks between the
ground and a design: profile, grade line, cross sections, template with
side slopes to daylight, cut and fill areas, prismoidal volumes. Pure.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .alignment import Station, point_at, stations
from .tin import Tin

Point = tuple[float, float]


# -- the longitudinal profile ----------------------------------------------------------

@dataclass
class ProfilePoint:
    s: float
    z: Optional[float]           # None where the axis leaves the surface
    x: float
    y: float
    vertex: bool = False


def ground_profile(tin: Tin, axis: list[Point], step: float) -> list[ProfilePoint]:
    out = []
    for st in stations(axis, step):
        out.append(ProfilePoint(st.s, tin.z_at(st.x, st.y), st.x, st.y, st.vertex))
    return out


def grade_at(grade: list[Point], s: float) -> Optional[float]:
    """The design elevation at chainage ``s`` on a grade line of (s, z)
    vertices, or None outside its span."""
    if len(grade) < 2:
        return None
    # a micrometre of slack: the stations are rounded to 1e-6 and the
    # grade comes back from drawing coordinates, so the last station
    # used to fall just past the grade's end and lose its design section
    if s < grade[0][0] - 1e-6 or s > grade[-1][0] + 1e-6:
        return None
    for (s0, z0), (s1, z1) in zip(grade, grade[1:]):
        if s0 - 1e-6 <= s <= s1 + 1e-6:
            if s1 - s0 < 1e-12:
                return z1
            t = (s - s0) / (s1 - s0)
            return z0 + t * (z1 - z0)
    return grade[-1][1]


def grade_slopes(grade: list[Point]) -> list[float]:
    """Slope of each segment of the grade line, in percent."""
    out = []
    for (s0, z0), (s1, z1) in zip(grade, grade[1:]):
        out.append(0.0 if s1 - s0 < 1e-12 else (z1 - z0) / (s1 - s0) * 100.0)
    return out


# -- vertical curves ---------------------------------------------------------------------

@dataclass
class VerticalCurve:
    """A symmetric parabola at a PVI of the grade line, the way a road
    profile is labelled: PVI station and elevation, curve length (VC),
    grades in and out (percent) and the middle ordinate (MO, + for a sag,
    - for a crest)."""

    s: float                      # PVI station
    z: float                      # PVI elevation
    length: float                 # VC, horizontal
    g1: float                     # grade in, percent
    g2: float                     # grade out, percent

    @property
    def bvc(self) -> float:
        return self.s - self.length / 2.0

    @property
    def evc(self) -> float:
        return self.s + self.length / 2.0

    @property
    def middle_ordinate(self) -> float:
        return (self.g2 - self.g1) * self.length / 800.0

    def z_at(self, s: float) -> float:
        x = s - self.bvc
        z_bvc = self.z - self.g1 / 100.0 * self.length / 2.0
        return z_bvc + self.g1 / 100.0 * x + (self.g2 - self.g1) / 100.0 / (2.0 * self.length) * x * x


def vertical_curves(pvis: list[Point], lengths) -> list[VerticalCurve]:
    """The curves at the interior PVIs of ``pvis`` with a positive length.

    ``lengths`` is one length for every interior PVI or one per vertex
    (the ends are ignored). A curve longer than the tangents allow is cut
    down so it never reaches past the middle of either adjacent segment
    -- two curves then meet but never overlap.
    """
    n = len(pvis)
    if n < 3:
        return []
    if isinstance(lengths, (int, float)):
        lengths = [0.0] + [float(lengths)] * (n - 2) + [0.0]
    lengths = list(lengths) + [0.0] * max(0, n - len(lengths))
    slopes = grade_slopes(pvis)
    out = []
    for i in range(1, n - 1):
        length = float(lengths[i] or 0.0)
        if length <= 0:
            continue
        room = min(pvis[i][0] - pvis[i - 1][0], pvis[i + 1][0] - pvis[i][0])
        length = min(length, room)
        if length <= 1e-9 or abs(slopes[i] - slopes[i - 1]) < 1e-12:
            continue
        out.append(VerticalCurve(pvis[i][0], pvis[i][1], length, slopes[i - 1], slopes[i]))
    return out


def grade_with_curves(pvis: list[Point], lengths, step: float = 1.0) -> list[Point]:
    """The grade line as (s, z) with each vertical curve sampled every
    ``step`` metres (and at its BVC and EVC), tangents kept as they are --
    so grade_at, the sections and the earthworks follow the curves."""
    curves = vertical_curves(pvis, lengths)
    if not curves:
        return list(pvis)
    by_s = {round(c.s, 9): c for c in curves}
    out: list[Point] = []
    for s, z in pvis:
        curve = by_s.get(round(s, 9))
        if curve is None:
            out.append((s, z))
            continue
        k = max(2, int(math.ceil(curve.length / max(step, 1e-3))))
        for j in range(k + 1):
            sj = curve.bvc + curve.length * j / k
            out.append((sj, curve.z_at(sj)))
    return out


# -- cross sections -------------------------------------------------------------------------

def cross_section(tin: Tin, station: Station, half_width: float,
                  step: float = 0.5) -> list[Point]:
    """The ground across the axis at ``station``: (offset, z) from
    -half_width (left) to +half_width (right); gaps off the surface are
    dropped."""
    out = []
    n = max(1, int(round(2 * half_width / step)))
    for k in range(n + 1):
        offset = -half_width + k * (2 * half_width / n)
        x, y = station.offset_point(offset)
        z = tin.z_at(x, y)
        if z is not None:
            out.append((offset, z))
    return out


def _z_on(line: list[Point], o: float) -> Optional[float]:
    """Linear interpolation of a piecewise-linear (offset, z) line."""
    if not line or o < line[0][0] - 1e-9 or o > line[-1][0] + 1e-9:
        return None
    for (o0, z0), (o1, z1) in zip(line, line[1:]):
        if o0 - 1e-9 <= o <= o1 + 1e-9:
            return z1 if o1 - o0 < 1e-12 else z0 + (o - o0) / (o1 - o0) * (z1 - z0)
    return line[-1][1]


def _daylight(ground: list[Point], start: Point, slope_hv: float, direction: int,
              rising: bool) -> Optional[Point]:
    """Where a side slope from ``start`` meets the ground.

    ``direction`` is +1 to the right, -1 to the left; ``slope_hv`` is the
    horizontal run per unit of rise (2.0 = 2H:1V); ``rising`` for a cut
    slope going up, else a fill slope going down. Returns None when the
    ground ends first.
    """
    o0, z0 = start
    grade = (1.0 if rising else -1.0) / max(slope_hv, 1e-9)     # dz per do
    last_o, last_diff = o0, None
    span = [p for p in ground if (p[0] - o0) * direction >= -1e-9]
    if direction < 0:
        span = list(reversed(span))
    zg0 = _z_on(ground, o0)
    if zg0 is None:
        return None
    last_diff = z0 - zg0                                        # design minus ground
    if abs(last_diff) < 1e-9:
        return (o0, z0)                                         # at grade: daylight is the edge
    for og, zg in span:
        zd = z0 + grade * abs(og - o0)
        diff = zd - zg
        if abs(og - o0) < 1e-12:
            continue
        if last_diff is not None and (diff == 0 or (diff > 0) != (last_diff > 0)):
            # the sign changed between last_o and og: solve linearly
            t = last_diff / (last_diff - diff) if last_diff != diff else 0.0
            o = last_o + t * (og - last_o)
            return (o, z0 + grade * abs(o - o0))
        last_o, last_diff = og, diff
    return None


@dataclass
class Template:
    width: float = 6.0            # platform, total
    cut_hv: float = 1.0           # cut slope H:V (1.0 = 1:1)
    fill_hv: float = 1.5          # fill slope H:V
    crown: float = 0.0            # cross slope of the platform, percent, down from the axis
    shoulder: float = 0.0         # shoulder width each side
    shoulder_slope: float = 4.0   # shoulder cross slope, percent, down and outwards

    def top(self, z_design: float) -> list[Point]:
        """The finished surface across the axis, edge to edge: shoulder,
        platform edge, the axis (when crowned), and back out."""
        half = self.width / 2.0
        z_edge = z_design - self.crown / 100.0 * half
        right = [(half, z_edge)]
        if self.shoulder > 0:
            right.append((half + self.shoulder, z_edge - self.shoulder_slope / 100.0 * self.shoulder))
        left = [(-o, z) for o, z in reversed(right)]
        middle = [(0.0, z_design)] if abs(self.crown) > 1e-12 else []
        return left + middle + right


def design_section(ground: list[Point], z_design: float, template: Template) -> list[Point]:
    """The design across the axis: the platform at ``z_design`` on the
    axis (crowned and with shoulders when the template says so) and a side
    slope each way to daylight (cut up, fill down); where the ground ends
    before daylight the slope is stopped at the ground's end."""
    out = template.top(z_design)
    left, right = out[0], out[-1]
    for edge, direction in ((right, 1), (left, -1)):
        zg = _z_on(ground, edge[0])
        if zg is None:
            continue
        rising = zg > edge[1]                                   # ground above: cut
        hv = template.cut_hv if rising else template.fill_hv
        day = _daylight(ground, edge, hv, direction, rising)
        if day is None:
            end = ground[-1] if direction > 0 else ground[0]
            day = (end[0], edge[1] + (1.0 if rising else -1.0) / max(hv, 1e-9) * abs(end[0] - edge[0]))
        if direction > 0:
            out.append(day)
        else:
            out.insert(0, day)
    return out


def areas(ground: list[Point], design: list[Point]) -> tuple[float, float]:
    """(cut, fill) between the ground and the design, over the design's
    span: cut where the ground is above the design, fill below."""
    if len(ground) < 2 or len(design) < 2:
        return 0.0, 0.0
    lo = max(ground[0][0], design[0][0])
    hi = min(ground[-1][0], design[-1][0])
    if hi <= lo:
        return 0.0, 0.0
    breaks = sorted({o for o, _ in ground if lo <= o <= hi}
                    | {o for o, _ in design if lo <= o <= hi} | {lo, hi})
    cut = fill = 0.0
    for o0, o1 in zip(breaks, breaks[1:]):
        d0 = _z_on(ground, o0) - _z_on(design, o0)              # + means ground above: cut
        d1 = _z_on(ground, o1) - _z_on(design, o1)
        w = o1 - o0
        if d0 >= 0 and d1 >= 0:
            cut += w * (d0 + d1) / 2.0
        elif d0 <= 0 and d1 <= 0:
            fill += w * (-d0 - d1) / 2.0
        else:                                                   # a crossing inside
            t = d0 / (d0 - d1)
            if d0 > 0:
                cut += w * t * d0 / 2.0
                fill += w * (1 - t) * (-d1) / 2.0
            else:
                fill += w * t * (-d0) / 2.0
                cut += w * (1 - t) * d1 / 2.0
    return cut, fill


def prismoidal(a1: float, am: float, a2: float, length: float) -> float:
    return length / 6.0 * (a1 + 4.0 * am + a2)


def end_area(a1: float, a2: float, length: float) -> float:
    return length * (a1 + a2) / 2.0


@dataclass
class EarthworksRow:
    s: float
    z_ground: Optional[float]
    z_design: Optional[float]
    cut_area: float
    fill_area: float
    cut_volume: float             # from the previous station to this one
    fill_volume: float
    cut_total: float              # cumulative
    fill_total: float

    @property
    def mass(self) -> float:
        return self.cut_total - self.fill_total


def earthworks(tin: Tin, axis: list[Point], grade: list[Point], step: float,
               template: Template, half_width: float = 20.0,
               section_step: float = 0.5, method: str = "prismoidal") -> list[EarthworksRow]:
    """Cut and fill at every station where both the ground and the grade
    exist, volumes between consecutive stations (prismoidal by default,
    with the mid-section measured, not averaged; or end-area)."""
    rows: list[EarthworksRow] = []
    cut_total = fill_total = 0.0
    previous: Optional[tuple[float, float, float]] = None       # (s, cut, fill)

    def section_areas(st: Station) -> Optional[tuple[float, float]]:
        zd = grade_at(grade, st.s)
        ground = cross_section(tin, st, half_width, section_step)
        if zd is None or len(ground) < 2:
            return None
        return areas(ground, design_section(ground, zd, template))

    for st in stations(axis, step):
        zg = tin.z_at(st.x, st.y)
        zd = grade_at(grade, st.s)
        result = section_areas(st)
        if result is None:
            rows.append(EarthworksRow(st.s, zg, zd, 0.0, 0.0, 0.0, 0.0, cut_total, fill_total))
            previous = None
            continue
        cut_a, fill_a = result
        cut_v = fill_v = 0.0
        if previous is not None:
            s0, c0, f0 = previous
            length = st.s - s0
            if method == "prismoidal":
                mid = point_at(axis, (s0 + st.s) / 2.0)
                mid_result = section_areas(mid) or ((c0 + cut_a) / 2.0, (f0 + fill_a) / 2.0)
                cut_v = prismoidal(c0, mid_result[0], cut_a, length)
                fill_v = prismoidal(f0, mid_result[1], fill_a, length)
            else:
                cut_v = end_area(c0, cut_a, length)
                fill_v = end_area(f0, fill_a, length)
        cut_total += cut_v
        fill_total += fill_v
        rows.append(EarthworksRow(st.s, zg, zd, cut_a, fill_a, cut_v, fill_v, cut_total, fill_total))
        previous = (st.s, cut_a, fill_a)
    return rows
