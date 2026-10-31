# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeCAD contributors.
"""An alignment (an axis drawn as a polyline) as chainage: stations every
N metres plus every vertex, each with its point and its normal. Pure.

Chainage is horizontal length along the axis, written the Peruvian way,
``0+020.00`` (kilometres + metres).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

Point = tuple[float, float]


@dataclass(frozen=True)
class Station:
    s: float                 # chainage, metres from the start
    x: float
    y: float
    angle: float             # tangent direction, degrees CCW from east
    vertex: bool = False     # a vertex of the axis, not a regular station

    @property
    def normal(self) -> Point:
        """Unit vector to the LEFT of the axis (the negative offset side)."""
        rad = math.radians(self.angle)
        return (-math.sin(rad), math.cos(rad))

    def offset_point(self, offset: float) -> Point:
        """The point ``offset`` metres to the right (+) or left (-)."""
        nx, ny = self.normal
        return (self.x - nx * offset, self.y - ny * offset)


def format_station(s: float, decimals: int = 2) -> str:
    km, m = divmod(round(s, decimals), 1000.0)
    if decimals <= 0:
        return f"{int(km)}+{int(round(m)):03d}"
    return f"{int(km)}+{m:0{4 + decimals}.{decimals}f}"


def polyline_length(points: list[Point]) -> float:
    return sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(points, points[1:]))


def point_at(points: list[Point], s: float) -> Station:
    """The station ``s`` along the polyline (clamped to its ends)."""
    if len(points) < 2:
        raise ValueError("an alignment needs at least two points")
    run = 0.0
    for p, q in zip(points, points[1:]):
        length = math.hypot(q[0] - p[0], q[1] - p[1])
        if length <= 0:
            continue
        if run + length >= s - 1e-9:
            t = max(0.0, min(1.0, (s - run) / length))
            return Station(s, p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]),
                           math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])))
        run += length
    p, q = points[-2], points[-1]
    return Station(run, q[0], q[1], math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])))


def stations(points: list[Point], step: float, start: float = 0.0) -> list[Station]:
    """Every ``step`` from ``start``, plus every vertex and the end, in
    chainage order without duplicates."""
    total = polyline_length(points)
    if step <= 0:
        raise ValueError("the station step must be positive")
    wanted: dict[float, bool] = {}
    s = start
    while s <= total + 1e-9:
        wanted[round(s, 6)] = False
        s += step
    run = 0.0
    for p, q in zip(points, points[1:]):
        wanted[round(run, 6)] = True
        run += math.hypot(q[0] - p[0], q[1] - p[1])
    wanted[round(total, 6)] = True
    out = []
    for key in sorted(wanted):
        st = point_at(points, key)
        out.append(Station(key, st.x, st.y, st.angle, wanted[key]))
    return out


def station_of(points: list[Point], q: Point) -> float:
    """The chainage of the point of the axis nearest to ``q``."""
    best, best_d, run = 0.0, math.inf, 0.0
    for p, r in zip(points, points[1:]):
        dx, dy = r[0] - p[0], r[1] - p[1]
        length2 = dx * dx + dy * dy
        length = math.sqrt(length2)
        t = 0.0 if length2 < 1e-18 else max(0.0, min(1.0, ((q[0] - p[0]) * dx + (q[1] - p[1]) * dy) / length2))
        x, y = p[0] + t * dx, p[1] + t * dy
        d = math.hypot(q[0] - x, q[1] - y)
        if d < best_d:
            best_d, best = d, run + t * length
        run += length
    return best


# -- horizontal curves ---------------------------------------------------------------------

@dataclass(frozen=True)
class HorizontalCurve:
    """A circular curve of the axis with its textbook data: PI, Δ (the
    deflection, + to the right), R, and from them T, L, E, M and the long
    chord; the stations of PC, PI and PT. R = 0 is an angle point (the
    axis turns at the PI without a curve)."""

    number: int
    pi: Point
    delta: float             # degrees, + right (clockwise), - left
    radius: float
    s_pc: float
    s_pt: float
    pc: Point
    pt: Point

    @property
    def side(self) -> str:
        return "RT" if self.delta > 0 else "LT"

    @property
    def _half(self) -> float:
        return math.radians(abs(self.delta)) / 2.0

    @property
    def tangent(self) -> float:
        return self.radius * math.tan(self._half)

    @property
    def length(self) -> float:
        return self.radius * math.radians(abs(self.delta))

    @property
    def external(self) -> float:
        return self.radius * (1.0 / math.cos(self._half) - 1.0)

    @property
    def middle_ordinate(self) -> float:
        return self.radius * (1.0 - math.cos(self._half))

    @property
    def chord(self) -> float:
        return 2.0 * self.radius * math.sin(self._half)

    @property
    def s_pi(self) -> float:
        return self.s_pc + self.tangent


def format_dms(degrees: float) -> str:
    """57°17'45" -- an angle the way a curve table writes it."""
    total = round(abs(degrees) * 3600.0)
    d, rest = divmod(total, 3600)
    m, sec = divmod(rest, 60)
    return f"{int(d)}°{int(m):02d}'{int(sec):02d}\""


def _line_cross(p, d, q, e) -> Point | None:
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-12:
        return None
    t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den
    return (p[0] + t * d[0], p[1] + t * d[1])


def horizontal_curves(points: list[Point], tol_deg: float = 0.5) -> list[HorizontalCurve]:
    """The curves of an axis surveyed as a polyline (shots on the centre
    line every few metres): runs of vertices that turn the same way by
    more than ``tol_deg`` are one curve between two tangents. The PI is
    where the tangents meet, Δ the change of direction, R from the
    tangent length PI-PC and PI-PT (the curve's first and last shots), so
    a survey with a shot at PC and PT gives the designed radius. A single
    turning vertex is an angle point (R = 0)."""
    pts = [p for k, p in enumerate(points)
           if k == 0 or math.hypot(p[0] - points[k - 1][0], p[1] - points[k - 1][1]) > 1e-9]
    if len(pts) < 3:
        return []
    heads = [math.atan2(q[1] - p[1], q[0] - p[0]) for p, q in zip(pts, pts[1:])]
    turns = [0.0]
    for h0, h1 in zip(heads, heads[1:]):
        turns.append(-math.degrees((h1 - h0 + math.pi) % (2 * math.pi) - math.pi))  # + right
    turns.append(0.0)
    chain = [0.0]
    for p, q in zip(pts, pts[1:]):
        chain.append(chain[-1] + math.hypot(q[0] - p[0], q[1] - p[1]))
    out: list[HorizontalCurve] = []
    k = 1
    while k < len(pts) - 1:
        if abs(turns[k]) <= tol_deg:
            k += 1
            continue
        a = k
        while k + 1 < len(pts) - 1 and abs(turns[k + 1]) > tol_deg \
                and (turns[k + 1] > 0) == (turns[a] > 0):
            k += 1
        b = k
        k += 1
        delta = sum(turns[a:b + 1])
        din = (pts[a][0] - pts[a - 1][0], pts[a][1] - pts[a - 1][1])
        dout = (pts[b + 1][0] - pts[b][0], pts[b + 1][1] - pts[b][1])
        pi = _line_cross(pts[a], din, pts[b], dout)
        if pi is None:
            continue
        if a == b:
            out.append(HorizontalCurve(len(out) + 1, pi, delta, 0.0, chain[a], chain[a], pi, pi))
            continue
        half = math.radians(abs(delta)) / 2.0
        t = (math.hypot(pi[0] - pts[a][0], pi[1] - pts[a][1])
             + math.hypot(pi[0] - pts[b][0], pi[1] - pts[b][1])) / 2.0
        radius = t / math.tan(half) if half > 1e-9 else 0.0
        nin, nout = math.hypot(*din), math.hypot(*dout)
        pc = (pi[0] - din[0] / nin * t, pi[1] - din[1] / nin * t)
        pt = (pi[0] + dout[0] / nout * t, pi[1] + dout[1] / nout * t)
        out.append(HorizontalCurve(len(out) + 1, pi, delta, radius, station_of(pts, pc),
                                   station_of(pts, pt), pc, pt))
    return out
