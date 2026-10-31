# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeCAD contributors.
"""The one polygon test the TIN needs, from IngeCAD's topography plugin
(``cad/plugins/topografia/geometry.py``), so ``tin.py`` is copied as is."""
from __future__ import annotations

import math

Point = tuple[float, float]
_EPS = 1e-9


def contains(pts: list[Point], q: Point) -> bool:
    """Ray casting; a point on the boundary counts as inside."""
    x, y = q
    inside = False
    n = len(pts)
    for i in range(n):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % n]
        if _on_segment(q, (x1, y1), (x2, y2)):
            return True
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xi > x:
                inside = not inside
    return inside


def _on_segment(q: Point, a: Point, b: Point) -> bool:
    cross = (b[0] - a[0]) * (q[1] - a[1]) - (b[1] - a[1]) * (q[0] - a[0])
    if abs(cross) > 1e-7 * max(1.0, math.hypot(b[0] - a[0], b[1] - a[1])):
        return False
    return (min(a[0], b[0]) - _EPS <= q[0] <= max(a[0], b[0]) + _EPS
            and min(a[1], b[1]) - _EPS <= q[1] <= max(a[1], b[1]) + _EPS)
