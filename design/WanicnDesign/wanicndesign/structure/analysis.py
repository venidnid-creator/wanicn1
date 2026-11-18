# -*- coding: utf-8 -*-
"""Continuous beam on simple supports, solved by the stiffness method
[STATICS].

Each span carries a uniform load ``w`` (kg/m) and any number of point loads
``(a, P)`` — ``a`` metres from the span's left end. A load over part of a
span is passed in as several point loads (see :func:`partial_udl`). Every
support is a pin; the unknowns are the support rotations; one EI. Signs:
sagging moments positive, reactions upward positive.

Fixed-end moments (counter-clockwise positive):
    uniform w:  +wL²/12, −wL²/12
    point P at a (b = L − a):  +P·a·b²/L², −P·a²·b/L²
"""
from __future__ import annotations

from dataclasses import dataclass

SAMPLES = 200          # points per span when searching the largest sagging moment


@dataclass
class SpanResult:
    length: float
    w: float           # equivalent uniform load, kg/m (total load / length)
    m_left: float      # kg-m (negative = hogging)
    m_right: float
    m_pos: float       # largest sagging moment in the span
    v_left: float      # shear at the left end, kg
    v_right: float     # shear at the right end (magnitude)


def partial_udl(w: float, a0: float, a1: float, pieces: int = 20) -> list[tuple[float, float]]:
    """A uniform load ``w`` from ``a0`` to ``a1`` as equal point loads."""
    if a1 <= a0 or w == 0:
        return []
    step = (a1 - a0) / pieces
    return [(a0 + step * (k + 0.5), w * step) for k in range(pieces)]


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        piv = m[c][c]
        if abs(piv) < 1e-12:
            raise ValueError("singular stiffness matrix")
        for r in range(c + 1, n):
            f = m[r][c] / piv
            for k in range(c, n + 1):
                m[r][k] -= f * m[c][k]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (m[r][n] - sum(m[r][k] * x[k] for k in range(r + 1, n))) / m[r][r]
    return x


def _fem(L: float, w: float, pts) -> tuple[float, float]:
    fa = w * L * L / 12.0
    fb = -fa
    for a, P in pts:
        b = L - a
        fa += P * a * b * b / (L * L)
        fb -= P * a * a * b / (L * L)
    return fa, fb


def continuous_beam(lengths: list[float], loads: list[float], points: list | None = None):
    """Return ``(spans, reactions)``; ``points[k]`` lists ``(a, P)`` on span k."""
    n = len(lengths)
    if n == 0:
        return [], []
    points = points or [[] for _ in lengths]
    dof = n + 1
    k = [[0.0] * dof for _ in range(dof)]
    f = [0.0] * dof
    fems = []
    for s, (L, w) in enumerate(zip(lengths, loads)):
        c = 1.0 / L                       # EI = 1 (prismatic)
        k[s][s] += 4 * c
        k[s][s + 1] += 2 * c
        k[s + 1][s] += 2 * c
        k[s + 1][s + 1] += 4 * c
        fa, fb = _fem(L, w, points[s])
        fems.append((fa, fb))
        f[s] += fa
        f[s + 1] += fb
    theta = _solve(k, [-v for v in f])
    spans, reactions = [], [0.0] * dof
    for s, (L, w) in enumerate(zip(lengths, loads)):
        c = 1.0 / L
        fa, fb = fems[s]
        m_ab = fa + c * (4 * theta[s] + 2 * theta[s + 1])
        m_ba = fb + c * (2 * theta[s] + 4 * theta[s + 1])
        m0, m1 = -m_ab, m_ba              # sagging-positive at the ends
        pts = sorted(points[s])
        total = w * L + sum(P for _a, P in pts)
        about_right = w * L * L / 2 + sum(P * (L - a) for a, P in pts)
        v0 = about_right / L + (m1 - m0) / L
        v1 = total - v0

        def moment(x):
            return m0 + v0 * x - w * x * x / 2 - sum(P * (x - a) for a, P in pts if a < x)

        xs = [L * t / SAMPLES for t in range(SAMPLES + 1)] + [a for a, _P in pts]
        m_pos = max(moment(x) for x in xs)
        spans.append(SpanResult(L, total / L, m0, m1, max(0.0, m_pos), v0, v1))
        reactions[s] += v0
        reactions[s + 1] += v1
    return spans, reactions
