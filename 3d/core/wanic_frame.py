# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""โครงข้อแข็ง: the building's frames under the lateral forces (ข12, from WanicnDesign).

Every grid line along the shaking is a plane frame — the columns fixed at
the base, the beams of each level joined rigidly to them — and the frames
of one direction are tied level by level by the floor (rigid diaphragm:
links stiff along their length only), so each takes the lateral force by
its own stiffness instead of every column an equal share [STATICS].

Stiffness by the direct stiffness method (Euler–Bernoulli members, three
degrees of freedom a node), the cracked sections of ACI 318 §6.6.3.1.1
for the lateral analysis: 0.70 Ig columns, 0.35 Ig beams; Ec = 15,100√f'c
(ksc). The storey drift for the earthquake (มยผ. 1301/1302-61 §6.4 =
ASCE 7 §12.8.6): Δ = Cd·δe/I ≤ Δa (0.020 / 0.015 / 0.010 hs by the
importance), and the stability coefficient θ = Px·Δ·I/(Vx·hs·Cd) ≤
min(0.25, 0.5/Cd), P-Δ to be counted when θ > 0.10.
"""
from __future__ import annotations

import math

COL_CRACK, BEAM_CRACK = 0.70, 0.35
#: Cd (deflection amplification) of the frame systems, มยผ. 1301/1302-61 ตาราง 6.2-1
CD = {"rc_omf": 2.5, "rc_imf": 4.5, "rc_smf": 5.5, "steel_omf": 3.0}


def drift_limit(I: float) -> float:
    """Δa / hs by the importance factor (risk category II / III / IV)."""
    return 0.020 if I < 1.2 else (0.015 if I < 1.4 else 0.010)


def _local_k(L, E, A, I):
    import numpy as np
    a, b = E * A / L, E * I / L ** 3
    return np.array([
        [a, 0, 0, -a, 0, 0],
        [0, 12 * b, 6 * b * L, 0, -12 * b, 6 * b * L],
        [0, 6 * b * L, 4 * b * L * L, 0, -6 * b * L, 2 * b * L * L],
        [-a, 0, 0, a, 0, 0],
        [0, -12 * b, -6 * b * L, 0, 12 * b, -6 * b * L],
        [0, 6 * b * L, 2 * b * L * L, 0, -6 * b * L, 4 * b * L * L]])


def _rot(c, s):
    import numpy as np
    t = np.zeros((6, 6))
    for k in (0, 3):
        t[k:k + 3, k:k + 3] = [[c, s, 0], [-s, c, 0], [0, 0, 1]]
    return t


def solve(nodes, members, fixed, loads):
    """``nodes`` [(x, z)], ``members`` [(i, j, E, A, I)], ``fixed`` node
    indices, ``loads`` {node: (Fx, Fz, M)} → ``(disp, forces)``: disp[n] =
    (u, w, θ); forces[m] = local end forces (N1, V1, M1, N2, V2, M2)."""
    import numpy as np
    n = len(nodes)
    K = np.zeros((3 * n, 3 * n))
    F = np.zeros(3 * n)
    geo = []
    for (i, j, E, A, I) in members:
        (x1, z1), (x2, z2) = nodes[i], nodes[j]
        L = math.hypot(x2 - x1, z2 - z1)
        T = _rot((x2 - x1) / L, (z2 - z1) / L)
        dofs = [3 * i, 3 * i + 1, 3 * i + 2, 3 * j, 3 * j + 1, 3 * j + 2]
        K[np.ix_(dofs, dofs)] += T.T @ _local_k(L, E, A, I) @ T
        geo.append((L, T, dofs, E, A, I))
    for node, f in loads.items():
        F[3 * node:3 * node + 3] += f
    free = [d for d in range(3 * n) if d // 3 not in fixed]
    U = np.zeros(3 * n)
    U[free] = np.linalg.solve(K[np.ix_(free, free)], F[free])
    forces = [_local_k(L, E, A, I) @ (T @ U[dofs]) for (L, T, dofs, E, A, I) in geo]
    return [tuple(U[3 * k:3 * k + 3]) for k in range(n)], forces


def Ec(fc_ksc: float) -> float:
    """kg/m²."""
    return 15100.0 * math.sqrt(max(fc_ksc, 1.0)) * 1e4


def frames(data, direction: str, forces: list, fc: float = 240.0) -> dict | None:
    """The frames along ``direction`` ("X"/"Y") under the level forces
    ``forces`` (kg, level 1 … n). Returns {"delta": [δe at level 1 … n] m,
    "cols": {(x, y, floor): (M kg·m, V kg)}, "lines": n} or None when the
    building has no columns."""
    from core import wanic_building as B
    E_ = B.elements(data or {})
    lib, H = E_["lib"], float(E_["H"])
    cols = [c for c in E_["columns"] if int(c.get("floor", 0)) >= 0]
    if not cols or not forces:
        return None
    nlev = len(forces)
    ax = 0 if direction == "X" else 1                 # the coordinate along the frame
    key = lambda p: round(p[1 - ax], 3)               # noqa: E731 — the line a point is on
    Ec_ = Ec(fc)
    nodes, idx = [], {}
    lines = sorted({key((c["x"], c["y"])) for c in cols})
    gap = 0.0
    for c in cols:
        gap = max(gap, abs((c["x"], c["y"])[ax]))
    offset = {ln: k * (gap * 2 + 20.0) for k, ln in enumerate(lines)}

    def node(line, pos, lev):
        k = (line, round(pos, 3), lev)
        if k not in idx:
            idx[k] = len(nodes)
            nodes.append((offset.get(line, 0.0) + pos, lev * H))
        return idx[k]

    members, col_ref = [], []
    for c in cols:
        f = int(c["floor"])
        if f >= nlev:
            continue
        sp = lib.get(c["mark"]) or {}
        b, h = float(sp.get("b", 0.2) or 0.2), float(sp.get("h", 0.2) or 0.2)
        dim, wid = min(b, h), max(b, h)            # the weak way (the drift on the safe side)
        ln, pos = key((c["x"], c["y"])), (c["x"], c["y"])[ax]
        i, j = node(ln, pos, f), node(ln, pos, f + 1)
        members.append((i, j, Ec_, b * h, COL_CRACK * wid * dim ** 3 / 12))
        col_ref.append((len(members) - 1, (round(c["x"], 3), round(c["y"], 3), f)))
    for bm in E_["beams"]:
        lev = int(bm.get("level", 0))
        if lev <= 0 or lev > nlev:
            continue                                # the ground beams: the base is fixed
        p0, p1 = bm["p0"], bm["p1"]
        if abs(p0[1 - ax] - p1[1 - ax]) > 1e-6:
            continue                                # across this direction
        ln = key(p0)
        if ln not in offset:
            continue
        a, z = sorted((p0[ax], p1[ax]))
        sp = lib.get(bm["mark"]) or {}
        b, h = float(sp.get("b", 0.2) or 0.2), float(sp.get("h", 0.4) or 0.4)
        # split the beam at every column under it on this line
        stops = sorted({a, z} | {k[1] for k in idx if k[0] == ln and k[2] == lev and a < k[1] < z})
        for s0, s1 in zip(stops, stops[1:]):
            if s1 - s0 > 1e-6:
                members.append((node(ln, s0, lev), node(ln, s1, lev), Ec_, b * h,
                                BEAM_CRACK * b * h ** 3 / 12))
    # the floor ties the frames level by level (stiff along, no bending)
    lead = {}
    for lev in range(1, nlev + 1):
        heads = []
        for ln in lines:
            at = sorted(k[1] for k in idx if k[0] == ln and k[2] == lev)
            if at:
                heads.append(idx[(ln, at[0], lev)])
        for i, j in zip(heads, heads[1:]):
            members.append((i, j, Ec_, 10.0, 1e-9))
        if heads:
            lead[lev] = heads[0]
    fixed = {i for k, i in idx.items() if k[2] == 0}
    loads = {lead[lev]: (forces[lev - 1], 0.0, 0.0) for lev in lead}
    disp, fr = solve(nodes, members, fixed, loads)
    delta = [disp[lead[lev]][0] if lev in lead else 0.0 for lev in range(1, nlev + 1)]
    out = {}
    for m, k in col_ref:
        f = fr[m]
        out[k] = (max(abs(float(f[2])), abs(float(f[5]))), abs(float(f[1])))
    return {"delta": delta, "cols": out, "lines": len(lines)}


def drifts(delta: list, H: float, Cd: float, I: float, V: list, P_above: list) -> list:
    """[{"storey", "de", "D", "limit", "theta", "ok", "note"}] for the
    elastic level displacements ``delta`` (level 1 … n), storey shears V and
    the weight above each storey P_above (kg)."""
    out, prev = [], 0.0
    lim = drift_limit(I)
    tmax = min(0.25, 0.5 / Cd)
    for k, d in enumerate(delta):
        de = abs(d - prev)
        prev = d
        D = Cd * de / I
        th = (P_above[k] * D * I / (V[k] * H * Cd)) if V[k] > 0 else 0.0
        ok = D <= lim * H + 1e-12 and th <= tmax
        note = ("θ เกินค่าสูงสุด — โครงสร้างอาจไม่มีเสถียรภาพ" if th > tmax else
                "θ > 0.10 ต้องคิดผล P-Δ" if th > 0.10 else "")
        out.append({"storey": k + 1, "de": de, "D": D, "limit": lim * H, "theta": th,
                    "theta_max": tmax, "ok": ok, "note": note})
    return out
