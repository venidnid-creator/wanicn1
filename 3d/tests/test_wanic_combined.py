# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ข12: ฐานรากร่วม — two columns on one footing when single ones overlap."""
from __future__ import annotations

import math

from core import wanic_autodesign as AD
from core import wanic_building as B
from core import wanic_calc as C
from core import wanic_combined as CF
from core import wanic_rc as R


def test_the_resultant_is_the_centre_and_the_soil_holds():
    r = CF.design((0.0, 0.0), (1.2, 0.0), 14000.0, 28000.0, 1.4, 0.2, 0.2, 5.0,
                  s1=(1.6, 1.6), s2=(2.0, 2.0))
    P1, P2 = 10000.0, 20000.0
    assert math.isclose(r["cx"], round(P2 * 1.2 / (P1 + P2), 3)) and r["cy"] == 0.0
    assert r["along_x"] and r["w"] >= 1.2 + 0.8 + 1.0 - 1e-9           # each keeps its own projection
    assert r["q"] <= 5.0 + 1e-6 and r["ok"]
    assert r["bars"].startswith("DB12@") and r["t"] >= 0.30


def test_pairs_only_two_on_a_line():
    sq = {(0.0, 0.0): (1.5, 1.5), (1.2, 0.0): (1.5, 1.5), (5.0, 0.0): (1.5, 1.5)}
    found, notes = CF.pairs(sq)
    assert found == [((0.0, 0.0), (1.2, 0.0))] and not notes
    sq[(2.4, 0.0)] = (1.5, 1.5)                                        # a chain of three: the engineer's
    found, notes = CF.pairs(sq)
    assert ((0.0, 0.0), (1.2, 0.0)) not in found and notes


def _close_columns():
    d = B.default_data()
    R.apply_grid(d, [4.0, 1.2, 4.0], [4.0], 2)
    return d


def test_auto_design_makes_the_combined_footing_and_the_model_follows():
    d = _close_columns()
    lines = AD.design_footings(d, C.analyse(d))
    assert any(ln.startswith("CF1") for ln in lines)
    assert len(d["combined_footings"]) == 2
    E = B.elements(d)
    cf = [f for f in E["footings"] if f.get("nodes")]
    assert len(cf) == 2 and all(f["mark"] == "CF1" for f in cf)
    assert len(E["footings"]) == 6 and len(E["stumps"]) == 8           # 8 columns, 6 footings
    # the grid stays on the columns, not on the footing's centre
    assert B.Grid(E).xs == [0.0, 4.0, 5.2, 9.2]
    # the calculation carries both columns on it
    res = C.analyse(d)
    m = [x for x in res["members"] if x.group == "footing" and x.name.startswith("CF1")]
    assert m and all(x.ratio <= 1.0 + 1e-6 for x in m)
    assert not [x for x in res["members"] if "ซ้อนกัน" in x.name]


def test_overlapping_singles_fail_until_combined():
    d = _close_columns()
    lib = dict(d.get("library") or {})
    lib["F1"] = dict(B.library_of(d)["F1"], w=1.6, l=1.6)
    d["library"] = lib
    res = C.analyse(d)
    bad = [x for x in res["members"] if "ซ้อนกัน" in x.name]
    assert bad and all(x.ratio > 1 for x in bad)
