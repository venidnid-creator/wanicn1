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


def test_standards_2566_seismic_provinces_and_phi():
    """ข5: the 43 provinces of กฎกระทรวงแผ่นดินไหว 2564 (ประกาศ มท. 2567
    ผนวก ข) switch the earthquake on; φ falls to the lower set without
    quality control (กฎกระทรวง 2566 ข้อ 8)."""
    from core import wanic_calc as C
    from core import wanic_lateral as LT
    assert LT.seismic_area("เชียงใหม่") == 3 and LT.seismic_area("จังหวัดกรุงเทพมหานคร") == 2
    assert LT.seismic_area("กระบี่") == 1 and LT.seismic_area("ขอนแก่น") == 0
    assert sum(len(v) for v in LT.SEISMIC_AREAS.values()) == 43
    p = LT.params_of({"province": "เชียงราย"})
    assert p["eq_on"] and p["area"] == 3
    assert not LT.params_of({"province": "เชียงราย", "lateral": {"eq_on": False}})["eq_on"]
    assert not LT.params_of({"province": "ขอนแก่น"})["eq_on"]
    assert C.phi({}, "flex") == 0.90 and C.phi({"qc": False}, "flex") == 0.75
    assert C.phi({"qc": False}, "tied") == 0.60 and C.phi({}, "shear") == 0.85
    spec = {"b": 0.25, "h": 0.25, "main": "6-DB16"}
    assert C.column_capacity(spec, {**C.DEFAULTS, "qc": False}, 240.0) < C.column_capacity(spec, C.DEFAULTS, 240.0)
