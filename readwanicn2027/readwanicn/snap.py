# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ — ReadWanicn2027
"""ยึดจุด (object snap) on the lines of a PDF drawing: end points, mid
points, intersections, centres of circles, and the nearest point on a
line, the way a CAD program does.

The page's vector paths (``page.get_drawings()``) become straight
segments in the displayed (rotated) page's coordinates, kept in a grid of
cells so a lookup only looks at the segments near the cursor."""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

import pymupdf

KINDS = {"end": "จุดปลาย", "mid": "จุดกึ่งกลาง", "int": "จุดตัด", "cen": "จุดศูนย์กลาง",
         "near": "บนเส้น"}
#: Preference when two candidates are about as close: a corner beats a point on a line.
_RANK = {"end": 0, "int": 1, "cen": 2, "mid": 3, "near": 4}
CELL = 24.0                                 # PDF points
MAX_SEGMENTS = 400_000


@dataclass
class Hit:
    x: float
    y: float
    kind: str

    @property
    def pt(self):
        return (self.x, self.y)


def _bezier(p0, p1, p2, p3, n=8):
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
        out.append((a * p0.x + b * p1.x + c * p2.x + d * p3.x, a * p0.y + b * p1.y + c * p2.y + d * p3.y))
    return out


class Snapper:
    def __init__(self, page: pymupdf.Page):
        m = page.rotation_matrix
        self.segs: list[tuple[float, float, float, float]] = []
        self.straight: list[bool] = []                 # False for the pieces of curves
        #: closed shapes of the drawing for «อ่านรูปทรง»: ("circle", (cx, cy, r)) or ("poly", [pts])
        self.shapes: list = []
        self.ends: list[tuple[float, float]] = []     # true end points (not the inner points of curves)
        self.centres: list[tuple[float, float]] = []

        def P(p):
            q = pymupdf.Point(p) * m
            return (q.x, q.y)
        try:
            paths = page.get_drawings()
        except Exception:                           # a damaged page: no snapping, no crash
            paths = []
        for path in paths:
            if path.get("type") == "f" and path.get("rect") is not None and \
                    pymupdf.Rect(path["rect"]).height < 40:
                continue                         # filled shapes this small are letters, not lines
            self._closed_shape(path, P, m)
            for item in path["items"]:
                op = item[0]
                if op == "l":
                    a, b = P(item[1]), P(item[2])
                    self._add(a, b, True)
                elif op == "re":
                    r = item[1]
                    pts = [P(r.tl), P(r.tr), P(r.br), P(r.bl)]
                    for a, b in zip(pts, pts[1:] + pts[:1]):
                        self._add(a, b, True)
                elif op == "qu":
                    q = item[1]
                    pts = [P(q.ul), P(q.ur), P(q.lr), P(q.ll)]
                    for a, b in zip(pts, pts[1:] + pts[:1]):
                        self._add(a, b, True)
                elif op == "c":
                    pts = [P(p) for p in _bezier(*item[1:5])]
                    for a, b in zip(pts, pts[1:]):
                        self._add(a, b, False, straight=False)
                    self.ends += [pts[0], pts[-1]]
                if len(self.segs) > MAX_SEGMENTS:
                    break
            # a closed path of curves only is a circle or an ellipse: its centre snaps
            if path["items"] and all(it[0] == "c" for it in path["items"]) and path.get("rect") is not None:
                r = pymupdf.Rect(path["rect"]) * m
                if r.width > 1 and abs(r.width - r.height) < 0.2 * max(r.width, r.height):
                    self.centres.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2))
        self.grid = defaultdict(list)
        for i, (x0, y0, x1, y1) in enumerate(self.segs):
            for cx in range(int(min(x0, x1) // CELL), int(max(x0, x1) // CELL) + 1):
                for cy in range(int(min(y0, y1) // CELL), int(max(y0, y1) // CELL) + 1):
                    self.grid[(cx, cy)].append(i)
                    if len(self.grid[(cx, cy)]) > 5000:
                        break
        self.points = defaultdict(list)
        for kind, pts in (("end", self.ends), ("cen", self.centres)):
            for p in pts:
                self.points[(int(p[0] // CELL), int(p[1] // CELL))].append((p, kind))

    def _closed_shape(self, path, P, m):
        items = path.get("items") or []
        if not items:
            return
        if all(it[0] == "c" for it in items) and path.get("rect") is not None:
            r = pymupdf.Rect(path["rect"]) * m
            if r.width > 1 and abs(r.width - r.height) < 0.08 * max(r.width, r.height):
                self.shapes.append(("circle", ((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2, (r.width + r.height) / 4)))
            return
        for it in items:
            if it[0] == "re":
                rr = it[1]
                self.shapes.append(("poly", [P(rr.tl), P(rr.tr), P(rr.br), P(rr.bl)]))
            elif it[0] == "qu":
                q = it[1]
                self.shapes.append(("poly", [P(q.ul), P(q.ur), P(q.lr), P(q.ll)]))
        lines = [it for it in items if it[0] == "l"]
        if len(lines) >= 3 and len(lines) == len(items):
            pts = [P(lines[0][1])] + [P(it[2]) for it in lines]
            closed = path.get("closePath") or math.dist(pts[0], pts[-1]) < 0.5
            joined = all(math.dist(P(a[2]), P(b[1])) < 0.5 for a, b in zip(lines, lines[1:]))
            if closed and joined:
                if math.dist(pts[0], pts[-1]) < 0.5:
                    pts = pts[:-1]
                self.shapes.append(("poly", pts))

    def shape_at(self, pt):
        """The smallest closed shape of the drawing around ``pt``: ("circle", [centre, edge]) or
        ("rect"/"tri"/"poly", [corners]). Without a closed path, the rectangle bounded by the
        nearest horizontal and vertical lines around the point (separate lines drawn by CAD)."""
        x, y = pt
        best = None
        for kind, data in self.shapes:
            if kind == "circle":
                cx, cy, r = data
                if math.hypot(x - cx, y - cy) <= r:
                    area = math.pi * r * r
                    cand = ("circle", [(cx, cy), (cx + r, cy)], area)
                else:
                    continue
            else:
                if not _inside(data, x, y):
                    continue
                area = abs(_area(data))
                cand = (_name(data), list(data), area)
            if area > 0.5 and (best is None or area < best[2]):
                best = cand
        ray = self._ray_rect(x, y)
        if ray and (best is None or ray[2] < best[2] * 0.98):
            best = ray
        return (best[0], best[1]) if best else None

    def _ray_rect(self, x, y, reach=4000.0):
        """Nearest vertical line left and right, horizontal line above and below (diagonal hatching
        and the pieces of circles are ignored)."""
        left = right = up = down = None
        for i, (x0, y0, x1, y1) in enumerate(self.segs):
            if not self.straight[i]:
                continue
            if abs(x0 - x1) < 0.3 and min(y0, y1) - 0.3 <= y <= max(y0, y1) + 0.3:
                d = x0 - x
                if 0.3 < d < reach and (right is None or d < right):
                    right = d
                elif -reach < d < -0.3 and (left is None or -d < left):
                    left = -d
            elif abs(y0 - y1) < 0.3 and min(x0, x1) - 0.3 <= x <= max(x0, x1) + 0.3:
                d = y0 - y
                if 0.3 < d < reach and (down is None or d < down):
                    down = d
                elif -reach < d < -0.3 and (up is None or -d < up):
                    up = -d
        if None in (left, right, up, down):
            return None
        x0, x1, y0, y1 = x - left, x + right, y - up, y + down
        return ("rect", [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], (x1 - x0) * (y1 - y0))

    def _add(self, a, b, ends, straight=True):
        if a == b:
            return
        self.segs.append((a[0], a[1], b[0], b[1]))
        self.straight.append(straight)
        if ends:
            self.ends += [a, b]

    def _near_cells(self, x, y, tol):
        r = int(tol // CELL) + 1
        cx, cy = int(x // CELL), int(y // CELL)
        for i in range(cx - r, cx + r + 1):
            for j in range(cy - r, cy + r + 1):
                yield (i, j)

    def find(self, pt, tol: float, kinds=("end", "mid", "int", "cen", "near")) -> Hit | None:
        """The best snap within ``tol`` PDF points of ``pt``, or None."""
        x, y = pt
        cands: list[tuple[int, float, Hit]] = []

        def offer(px, py, kind):
            d = math.hypot(px - x, py - y)
            if d <= tol and kind in kinds:
                cands.append((_RANK[kind], d, Hit(px, py, kind)))
        seen = set()
        near = []
        for cell in self._near_cells(x, y, tol):
            for p, kind in self.points.get(cell, ()):
                offer(p[0], p[1], kind)
            for i in self.grid.get(cell, ()):
                if i in seen:
                    continue
                seen.add(i)
                x0, y0, x1, y1 = self.segs[i]
                dx, dy = x1 - x0, y1 - y0
                L2 = dx * dx + dy * dy
                t = max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / L2))
                px, py = x0 + t * dx, y0 + t * dy
                if math.hypot(px - x, py - y) <= tol:
                    near.append(i)
                    offer((x0 + x1) / 2, (y0 + y1) / 2, "mid")
                    cands.append((_RANK["near"], math.hypot(px - x, py - y), Hit(px, py, "near")))
        if "int" in kinds:
            near = near[:60]
            for a in range(len(near)):
                for b in range(a + 1, len(near)):
                    p = _cross(self.segs[near[a]], self.segs[near[b]])
                    if p:
                        offer(p[0], p[1], "int")
        if "near" not in kinds:
            cands = [c for c in cands if c[2].kind != "near"]
        if not cands:
            return None
        # points (not "near") within the tolerance win over the line itself
        best_pt = [c for c in cands if c[2].kind != "near"]
        pool = best_pt or cands
        pool.sort(key=lambda c: (c[1] > tol * 0.6, c[0], c[1]))
        return pool[0][2]


def _area(pts) -> float:
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1])) / 2.0


def _inside(pts, x, y) -> bool:
    inside = False
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def _name(pts) -> str:
    if len(pts) == 3:
        return "tri"
    if len(pts) == 4:
        (ax, ay), (bx, by), (cx, cy), (dx, dy) = pts
        v = [(bx - ax, by - ay), (cx - bx, cy - by), (dx - cx, dy - cy), (ax - dx, ay - dy)]
        if all(abs(v[i][0] * v[i + 1][0] + v[i][1] * v[i + 1][1]) < 1e-3 *
               (math.hypot(*v[i]) * math.hypot(*v[i + 1]) or 1) for i in range(3)):
            return "rect"
    return "poly"


def _cross(s, t):
    x1, y1, x2, y2 = s
    x3, y3, x4, y4 = t
    d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(d) < 1e-9:
        return None
    u = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / d
    v = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / d
    if -1e-6 <= u <= 1 + 1e-6 and -1e-6 <= v <= 1 + 1e-6:
        return (x1 + u * (x2 - x1), y1 + u * (y2 - y1))
    return None
