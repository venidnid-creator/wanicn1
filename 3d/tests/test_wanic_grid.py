# SPDX-License-Identifier: GPL-3.0-or-later
"""โหมดกริด: spacings, the bays, the columns on the intersections."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from core import wanic_building as B
from core import wanic_calc as C
from core import wanic_rc as R


def test_parse_spacings():
    assert R.parse_spacings("3@4, 3.5") == [4.0, 4.0, 4.0, 3.5]
    assert R.parse_spacings("4 4") == [4.0, 4.0]
    with pytest.raises(ValueError):
        R.parse_spacings("4, -1")


def test_grid_builds_the_plan_with_columns_on_every_node():
    d = R.apply_grid(B.default_data(), [4, 4, 4], [5, 5], 2, omit=[(2, 1)])
    assert len(d["floors"]) == 2 and len(d["floors"][0]["rooms"]) == 5
    ids = [r["id"] for f in d["floors"] for r in f["rooms"]]
    assert len(ids) == len(set(ids))
    E = B.elements(d)
    assert R.grid_axes(E) == ([0.0, 4.0, 8.0, 12.0], [0.0, 5.0, 10.0])
    assert len(E["stumps"]) == 4 * 3 - 1                             # the corner of the omitted bay
    res = C.analyse(d)
    assert res["beams"] and res["cards"]
    assert d["grid"]["omit"] == [[2, 1]]
