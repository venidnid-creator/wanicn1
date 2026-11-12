# SPDX-License-Identifier: GPL-3.0-or-later
"""แรงด้านข้าง: site factors, base shear, distribution, wind, old formulas."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from core import wanic_building as B
from core import wanic_lateral as L
from core import wanic_rc as R


def _bldg(n=3):
    return R.apply_grid(B.default_data(), [4, 4, 4], [4, 4], n)


def test_site_factors_interpolate():
    assert L.site_factors("D", 0.25, 0.1) == (1.6, 2.4)
    Fa, Fv = L.site_factors("D", 0.375, 0.15)
    assert Fa == pytest.approx(1.5) and Fv == pytest.approx(2.2)


def test_weights_and_seismic_distribution():
    d = _bldg(3)
    lv = L.level_weights(d)
    assert len(lv) == 3 and all(w > 0 for *_x, w in lv)
    p = {**L.DEFAULTS, "eq_on": True}
    eq = L.seismic(p, lv, 8.0)
    assert sum(eq["F"]) == pytest.approx(eq["V"])
    assert eq["V"] == pytest.approx(eq["C"] * eq["W"])
    # T ≤ 0.5 s: k = 1 → forces in proportion to w·h
    k = [f / (w * h) for f, (_j, h, w) in zip(eq["F"], lv)]
    assert max(k) == pytest.approx(min(k))


def test_seismic_off_by_default_and_old_formula():
    d = _bldg(2)
    lv = L.level_weights(d)
    assert L.seismic(dict(L.DEFAULTS), lv, 8.0)["V"] == 0.0
    p = {**L.DEFAULTS, "eq_on": True, "standard": "old", "zone": "2", "S_old": 1.2}
    eq = L.seismic(p, lv, 8.0)
    assert eq["C"] == pytest.approx(0.375 * 1.0 * 1.0 * 0.12 * 1.2 if 0.12 * 1.2 <= 0.14 else 0.375 * 0.14)


def test_wind_new_and_old():
    lv = [(1, 3.0, 1.0), (2, 6.0, 1.0)]
    old = L.wind({**L.DEFAULTS, "wind_std": "old"}, lv, 10.0)
    assert old["p"] == [50.0, 50.0] and old["V"] == pytest.approx(50 * 4.5 * 10)   # to mid-storey above
    new = L.wind(dict(L.DEFAULTS), lv, 10.0)
    assert new["p"][0] > 50


def test_full_analysis_has_column_checks():
    d = _bldg(2)
    d["lateral"] = {"eq_on": True}
    res = L.analyse(d)
    acts = {c["action"] for c in res["checks"]}
    assert acts == {"แผ่นดินไหว", "ลม"}
    assert all(c["ratio"] >= 0 for c in res["checks"])
