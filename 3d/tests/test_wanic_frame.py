# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ข12: the frames take the lateral force by their stiffness; storey drift."""
from __future__ import annotations

import math

from core import wanic_building as B
from core import wanic_frame as FR
from core import wanic_lateral as L
from core import wanic_rc as R


def test_a_fixed_column_by_hand():
    # a cantilever column 3 m, EI known: δ = PL³/3EI, M = PL at the base
    E, I, P, Lh = 2.0e9, 1.0e-4, 1000.0, 3.0
    disp, f = FR.solve([(0, 0), (0, Lh)], [(0, 1, E, 0.04, I)], {0}, {1: (P, 0, 0)})
    assert math.isclose(disp[1][0], P * Lh ** 3 / (3 * E * I), rel_tol=1e-9)
    assert math.isclose(max(abs(f[0][2]), abs(f[0][5])), P * Lh, rel_tol=1e-9)
    # a portal with a rigid beam: each column fixed–fixed, δ = (P/2)L³/12EI
    disp, f = FR.solve([(0, 0), (0, Lh), (4, Lh), (4, 0)],
                       [(0, 1, E, 100.0, I), (1, 2, E, 100.0, I * 1e6), (3, 2, E, 100.0, I)],
                       {0, 3}, {1: (P, 0, 0)})
    assert math.isclose(disp[1][0], P / 2 * Lh ** 3 / (12 * E * I), rel_tol=1e-3)


def _house(n=2):
    d = B.default_data()
    R.apply_grid(d, [4.0, 4.0], [4.0, 3.0], n)
    d["province"] = "เชียงใหม่"
    return d


def test_the_storey_shear_is_carried_by_its_columns():
    d = _house()
    F = [6000.0, 3000.0]
    for dir_ in ("X", "Y"):
        r = FR.frames(d, dir_, F)
        assert r["lines"] == 3
        for f in range(2):
            Vs = sum(v for (x, y, fl), (_m, v) in r["cols"].items() if fl == f)
            assert math.isclose(Vs, sum(F[f:]), rel_tol=1e-6)
        # the floor moves as one, the top more than the first
        assert 0 < r["delta"][0] < r["delta"][1]


def test_frame_shares_in_the_lateral_check_and_drift():
    d = _house()
    res = L.analyse(d)
    assert res["method"] == "frame"
    # columns of one storey no longer all carry the same shear
    eq0 = [c for c in res["checks"] if c["floor"] == 0 and c["action"] == "แผ่นดินไหว"]
    assert eq0 and all(c["Vc"] > c["V"] / c["n"] for c in eq0)       # the critical one carries more
    dr = res["drift"]["X"]
    assert [x["storey"] for x in dr] == [1, 2]
    Cd, I = FR.CD[res["params"]["system"]], res["params"]["I"]
    x = dr[0]
    assert math.isclose(x["D"], Cd * x["de"] / I) and math.isclose(x["limit"], 0.020 * res["H"])
    assert x["theta"] > 0 and x["theta_max"] == min(0.25, 0.5 / Cd)


def test_no_drift_check_without_the_earthquake():
    d = _house()
    d["province"] = "ขอนแก่น"                  # not in the seismic law
    res = L.analyse(d)
    assert res["drift"] == {} and res["method"] == "frame"
    assert FR.drift_limit(1.0) == 0.020 and FR.drift_limit(1.25) == 0.015 \
        and FR.drift_limit(1.5) == 0.010
