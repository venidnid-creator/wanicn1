# -*- coding: utf-8 -*-
"""Plane frame by the direct stiffness method [STATICS].

Units: m, kg, kg/m². Each node has three degrees of freedom (u, w, θ).
Members are prismatic Euler–Bernoulli beams with axial stiffness EA and
bending stiffness EI. Used for the lateral (earthquake) analysis of each
frame line of the building.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class Member:
    i: int
    j: int
    E: float
    A: float
    I: float


def _local_k(L: float, E: float, A: float, I: float) -> np.ndarray:
    a, b = E * A / L, E * I / L ** 3
    return np.array([
        [a, 0, 0, -a, 0, 0],
        [0, 12 * b, 6 * b * L, 0, -12 * b, 6 * b * L],
        [0, 6 * b * L, 4 * b * L * L, 0, -6 * b * L, 2 * b * L * L],
        [-a, 0, 0, a, 0, 0],
        [0, -12 * b, -6 * b * L, 0, 12 * b, -6 * b * L],
        [0, 6 * b * L, 2 * b * L * L, 0, -6 * b * L, 4 * b * L * L]])


def _rot(c: float, s: float) -> np.ndarray:
    t = np.zeros((6, 6))
    for k in (0, 3):
        t[k:k + 3, k:k + 3] = [[c, s, 0], [-s, c, 0], [0, 0, 1]]
    return t


def solve_frame(nodes, members, fixed, loads):
    """``nodes`` [(x, z)], ``members`` [Member], ``fixed`` node indices
    (fully fixed), ``loads`` {node: (Fx, Fz, M)}.

    Returns ``(disp, forces)``: ``disp[n] = (u, w, θ)``; ``forces[m]`` are
    the member end forces in local axes (N1, V1, M1, N2, V2, M2), from
    end i to end j (end moments counter-clockwise positive).
    """
    n = len(nodes)
    K = np.zeros((3 * n, 3 * n))
    F = np.zeros(3 * n)
    geo = []
    for m in members:
        (x1, z1), (x2, z2) = nodes[m.i], nodes[m.j]
        L = math.hypot(x2 - x1, z2 - z1)
        c, s = (x2 - x1) / L, (z2 - z1) / L
        T = _rot(c, s)
        kg = T.T @ _local_k(L, m.E, m.A, m.I) @ T
        dofs = [3 * m.i, 3 * m.i + 1, 3 * m.i + 2, 3 * m.j, 3 * m.j + 1, 3 * m.j + 2]
        K[np.ix_(dofs, dofs)] += kg
        geo.append((L, T, dofs))
    for node, f in loads.items():
        F[3 * node:3 * node + 3] += f
    free = [d for d in range(3 * n) if d // 3 not in fixed]
    U = np.zeros(3 * n)
    U[free] = np.linalg.solve(K[np.ix_(free, free)], F[free])
    forces = []
    for m, (L, T, dofs) in zip(members, geo):
        forces.append(_local_k(L, m.E, m.A, m.I) @ (T @ U[dofs]))
    disp = [tuple(U[3 * k:3 * k + 3]) for k in range(n)]
    return disp, forces
