# -*- coding: utf-8 -*-
"""Continuous beam on simple supports, solved by the stiffness method.

Spans carry a uniform load each (kg/m). Every support is a pin, so the
unknowns are the support rotations; the beam is prismatic (one EI). Signs:
sagging moments are positive, reactions upward are positive.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SpanResult:
    length: float
    w: float
    m_left: float      # kg-m (negative = hogging)
    m_right: float
    m_pos: float       # largest sagging moment in the span
    v_left: float      # shear at the left end, kg
    v_right: float     # shear at the right end (magnitude)


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting (small dense systems)."""
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


def continuous_beam(lengths: list[float], loads: list[float]):
    """Return ``(spans, reactions)`` for spans of ``lengths`` (m) with
    uniform ``loads`` (kg/m). ``reactions`` has one entry per support."""
    n = len(lengths)
    if n == 0:
        return [], []
    dof = n + 1
    k = [[0.0] * dof for _ in range(dof)]
    f = [0.0] * dof
    for s, (L, w) in enumerate(zip(lengths, loads)):
        c = 1.0 / L                       # EI = 1 (prismatic)
        k[s][s] += 4 * c
        k[s][s + 1] += 2 * c
        k[s + 1][s] += 2 * c
        k[s + 1][s + 1] += 4 * c
        fem = w * L * L / 12.0            # counter-clockwise end moments
        f[s] += fem
        f[s + 1] -= fem
    theta = _solve(k, [-v for v in f])
    spans, reactions = [], [0.0] * dof
    for s, (L, w) in enumerate(zip(lengths, loads)):
        c = 1.0 / L
        fem = w * L * L / 12.0
        m_ab = fem + c * (4 * theta[s] + 2 * theta[s + 1])
        m_ba = -fem + c * (2 * theta[s] + 4 * theta[s + 1])
        m0, m1 = -m_ab, m_ba              # sagging-positive at the ends
        v0 = w * L / 2 + (m1 - m0) / L
        v1 = w * L - v0
        x = min(max(v0 / w, 0.0), L) if w else 0.0
        m_pos = max(m0, m1, m0 + v0 * x - w * x * x / 2)
        spans.append(SpanResult(L, w, m0, m1, max(0.0, m_pos), v0, v1))
        reactions[s] += v0
        reactions[s + 1] += v1
    return spans, reactions
