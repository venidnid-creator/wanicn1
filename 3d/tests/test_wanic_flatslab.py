# SPDX-License-Identifier: GPL-3.0-or-later
"""พื้นไร้คาน DDM."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from core import wanic_calc as C
from core import wanic_flatslab as F


def test_min_thickness():
    t = F.min_thickness({"x": [6, 6], "y": [6], "col": 0.3, "drop": False})
    assert t["need"] == pytest.approx(0.19)                  # 5.70/30 = 0.19
    t = F.min_thickness({"x": [6, 6], "y": [6], "col": 0.3, "drop": True})
    assert t["need"] == pytest.approx(0.18)                  # 5.70/33 = 0.173


def test_static_moment_and_shares():
    p, r = F.design_of({"grid": {"x": [6, 6, 6], "y": [6, 6]}})
    d = r["dirs"][0]
    Mo = r["wu"] * d["l2"] * (6 - p["col"]) ** 2 / 8
    end_neg = [x for x in d["rows"] if x["span"] == 1 and x["loc"] == "ลบซ้าย"]
    assert sum(x["M"] for x in end_neg) == pytest.approx(0.26 * Mo)
    mid_pos = [x for x in d["rows"] if x["span"] == 2 and x["loc"] == "บวก"]
    assert sum(x["M"] for x in mid_pos) == pytest.approx(0.35 * Mo)
    cs = [x for x in mid_pos if x["strip"] == "แถบเสา"][0]
    assert cs["M"] == pytest.approx(0.60 * 0.35 * Mo)
    assert all(x["ok"] for x in d["rows"])
    assert max(q["ratio"] for q in r["punch"]) < 1


def test_thin_plate_fails_punching():
    p, _ = F.design_of({"grid": {"x": [6, 6], "y": [6, 6]}})
    p.update(t=0.10, drop=False)
    r = F.design(p, C.basis({}))
    assert max(q["ratio"] for q in r["punch"]) > 1
