# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
# WANICNSURVEY 3D — ตัดโครงหลังคาและแผ่นหลังคาที่ซ้อนกัน (หลังคาตัว L / T)
"""An L- or T-shaped plan is roofed with overlapping rectangles, one hip or
gable roof each. Where two of them overlap, the roof you see is the
higher of the two at every point (the upper envelope), and the creases
where they meet are the valleys (ตะเข้ราง).

This module trims every roof member and every piece of covering of one
rectangle that lies UNDER another rectangle's roof surface, so no steel
pokes through and nothing is counted twice, and measures the valleys.

A rectangle's roof is the lowest of its facet planes inside its eave box
(``z = a·x + b·y + c``) — hip and gable roofs are both that shape.
Pure Python, no Qt.
"""
from __future__ import annotations

import math

TOL = 0.004          # metres: a point this close to another roof is on it


def plane_of(poly):
    """``(a, b, c)`` with ``z = a x + b y + c`` through a planar polygon."""
    (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = poly[0], poly[1], poly[2]
    ux, uy, uz = x2 - x1, y2 - y1, z2 - z1
    vx, vy, vz = x3 - x1, y3 - y1, z3 - z1
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    if abs(nz) < 1e-12:
        return None
    a, b = -nx / nz, -ny / nz
    return a, b, z1 - a * x1 - b * y1


class Roof:
    """One rectangle's roof: its eave box and facet planes."""

    def __init__(self, box, skin):
        self.box = box
        self.planes = [p for p in (plane_of(q) for q in skin) if p]

    def inside(self, x, y, strict=False) -> bool:
        x0, y0, x1, y1 = self.box
        e = 1e-6 if strict else -1e-6
        return x0 + e < x < x1 - e and y0 + e < y < y1 - e

    def height(self, x, y):
        if not self.inside(x, y) or not self.planes:
            return None
        return min(a * x + b * y + c for a, b, c in self.planes)


def hidden(pt, i, roofs, tol=TOL) -> bool:
    """Whether a point of roof ``i`` lies under another roof's surface."""
    x, y, z = pt
    for j, r in enumerate(roofs):
        if j == i:
            continue
        h = r.height(x, y)
        if h is None:
            continue
        # Where two roofs share a plane the earlier one keeps it.
        if h > z + tol or (j < i and abs(h - z) <= tol):
            return True
    return False


def _lerp(a, b, t):
    return tuple(a[k] + (b[k] - a[k]) * t for k in range(3))


def clip_segment(a, b, i, roofs, step=0.05, min_len=0.03):
    """The visible parts of the straight member a→b of roof ``i``."""
    L = math.dist(a, b)
    if L < 1e-9:
        return []
    n = max(2, int(math.ceil(L / step)))
    ts = [k / n for k in range(n + 1)]
    vis = [not hidden(_lerp(a, b, t), i, roofs) for t in ts]
    if all(vis):
        return [[a, b]]

    def edge(t0, t1):           # vis(t0) != vis(t1): bisect the change
        v0 = not hidden(_lerp(a, b, t0), i, roofs)
        for _ in range(30):
            tm = (t0 + t1) / 2
            if (not hidden(_lerp(a, b, tm), i, roofs)) == v0:
                t0 = tm
            else:
                t1 = tm
        return (t0 + t1) / 2

    out, start = [], (0.0 if vis[0] else None)
    for k in range(1, len(ts)):
        if vis[k] != vis[k - 1]:
            t = edge(ts[k - 1], ts[k])
            if vis[k]:
                start = t
            else:
                if start is not None:
                    out.append((start, t))
                start = None
    if start is not None:
        out.append((start, 1.0))
    return [[_lerp(a, b, t0), _lerp(a, b, t1)] for t0, t1 in out
            if (t1 - t0) * L >= min_len]


def clip_path(path, i, roofs, closed=False):
    pts = list(path) + ([path[0]] if closed else [])
    out = []
    for a, b in zip(pts, pts[1:]):
        out += clip_segment(a, b, i, roofs)
    return out


# ---------------------------------------------------------------------------
# Covering: convex facets split by lines, hidden pieces dropped
# ---------------------------------------------------------------------------

def _split(poly, line):
    """Split a convex 3D polygon by the plan line ``A x + B y + C = 0``:
    (the part where it is ≥ 0, the part where it is < 0)."""
    A, B, C = line
    pos, neg = [], []
    n = len(poly)
    for k in range(n):
        p, q = poly[k], poly[(k + 1) % n]
        fp = A * p[0] + B * p[1] + C
        fq = A * q[0] + B * q[1] + C
        eps = 1e-9
        if fp >= -eps:
            pos.append(p)
        if fp <= eps:
            neg.append(p)
        if (fp > eps and fq < -eps) or (fp < -eps and fq > eps):
            x = _lerp(p, q, fp / (fp - fq))
            pos.append(x)
            neg.append(x)
    return (pos if len(pos) >= 3 else None), (neg if len(neg) >= 3 else None)


def _centroid(poly):
    n = len(poly)
    return tuple(sum(p[k] for p in poly) / n for k in range(3))


def _area(poly) -> float:
    nx = ny = nz = 0.0
    for k, a in enumerate(poly):
        b = poly[(k + 1) % len(poly)]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)


def clip_facet(poly, i, roofs):
    """The visible pieces of one covering facet of roof ``i``."""
    own = plane_of(poly)
    pieces = [poly]
    for j, r in enumerate(roofs):
        if j == i or own is None:
            continue
        x0, y0, x1, y1 = r.box
        lines = [(1, 0, -x0), (-1, 0, x1), (0, 1, -y0), (0, -1, y1)]
        for a, b, c in r.planes:
            # own − other = 0: where the two surfaces meet.
            lines.append((own[0] - a, own[1] - b, own[2] - c))
        nxt = []
        for pc in pieces:
            cells = [pc]
            for ln in lines:
                if abs(ln[0]) < 1e-12 and abs(ln[1]) < 1e-12:
                    continue
                cut = []
                for cell in cells:
                    p, q = _split(cell, ln)
                    cut += [x for x in (p, q) if x is not None]
                cells = cut
            for cell in cells:
                if _area(cell) < 1e-6:
                    continue
                cx, cy, cz = _centroid(cell)
                h = r.height(cx, cy)
                if h is not None and (h > cz + 1e-6 or
                                      (j < i and abs(h - cz) <= 1e-6)):
                    continue
                nxt.append(cell)
        pieces = nxt
    return pieces


def valley_length(pieces_by_roof, roofs, eps=0.01) -> float:
    """Total length of the creases where two roofs meet: the edges of the
    kept covering that border a dropped part (counted once)."""
    total = 0.0
    for i, pieces in pieces_by_roof.items():
        for poly in pieces:
            n = len(poly)
            cx, cy, _cz = _centroid(poly)
            for k in range(n):
                p, q = poly[k], poly[(k + 1) % n]
                L = math.dist(p, q)
                if L < 0.02:
                    continue
                mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
                dx, dy = q[0] - p[0], q[1] - p[1]
                h = math.hypot(dx, dy) or 1.0
                ox, oy = dy / h, -dx / h                    # a plan normal
                if (mx - cx) * ox + (my - cy) * oy < 0:
                    ox, oy = -ox, -oy                       # pointing out
                for j, r in enumerate(roofs):
                    if j == i or not r.inside(mx, my, strict=True):
                        continue
                    own = r.height(mx, my)
                    pl = plane_of(poly)
                    z = pl[0] * mx + pl[1] * my + pl[2]
                    if own is None or abs(own - z) > 0.01:
                        continue
                    xo, yo = mx + ox * eps, my + oy * eps
                    zo = pl[0] * xo + pl[1] * yo + pl[2]
                    ho = r.height(xo, yo)
                    if ho is not None and ho > zo + 1e-6:
                        total += L
                        break
    return total / 2.0


# ---------------------------------------------------------------------------
# Roof accessories (special cap pieces) from the trimmed lines
# ---------------------------------------------------------------------------

def accessories(lines, tol=0.05) -> dict:
    """Count the special cap pieces a covering needs, from where ridges,
    hips and verges meet:

    * ``four_way`` — four hips at one apex (a pyramid);
    * ``three_way`` — a ridge end with two hips (every hip roof);
    * ``gable_end`` — a ridge end at a gable (verge tops);
    * ``two_way`` — ridges that meet with no hip (a T or L crossing);
    * ``hip_end`` — the foot of a hip at the eave;
    * ``verge_end`` — the foot of a verge at the eave.
    """
    pts = []                         # (x, y, z, kind)
    for a, b in lines.get("ridge", []):
        pts += [(*a, "r"), (*b, "r")]
    for a, b in lines.get("hip", []):
        lo, hi = (a, b) if a[2] <= b[2] else (b, a)
        pts.append((*hi, "h"))
    for a, b in lines.get("barge", []):
        lo, hi = (a, b) if a[2] <= b[2] else (b, a)
        pts.append((*hi, "b"))
    clusters = []
    for x, y, z, k in pts:
        for c in clusters:
            if math.dist((x, y, z), c["p"]) <= tol:
                c[k] = c.get(k, 0) + 1
                break
        else:
            clusters.append({"p": (x, y, z), k: 1})
    out = {k: 0 for k in ("four_way", "three_way", "gable_end", "two_way",
                          "hip_end", "verge_end")}
    for c in clusters:
        r, h, b = c.get("r", 0), c.get("h", 0), c.get("b", 0)
        if h >= 4 and r == 0:
            out["four_way"] += 1
        elif h >= 2 and r >= 1:
            out["three_way"] += 1
        elif b >= 1:
            out["gable_end"] += 1
        elif r >= 2:
            out["two_way"] += 1
    eave_z = None
    for a, b in lines.get("eave", []):
        eave_z = a[2] if eave_z is None else min(eave_z, a[2])
    if eave_z is not None:
        for key, src in (("hip_end", "hip"), ("verge_end", "barge")):
            for a, b in lines.get(src, []):
                if abs(min(a[2], b[2]) - eave_z) < 0.02:
                    out[key] += 1
    return out
