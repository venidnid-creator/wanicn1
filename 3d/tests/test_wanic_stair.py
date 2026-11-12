# SPDX-License-Identifier: GPL-3.0-or-later
"""บันได คสล. — straight / L / two-flight."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import wanic_building as B  # noqa: E402
from core import wanic_calc as C  # noqa: E402
from core import wanic_rc as R  # noqa: E402
from core import wanic_stair as ST  # noqa: E402


def _house(typ="U", **kw):
    d = B.default_data()
    R.apply_grid(d, [4.9, 4.9], [4.9, 2.0], 2)
    d["floors"][0].setdefault("stairs", []).append(dict({"id": "s1", "x": 7.35, "y": 2.45, "dir": 1,
                                                          "type": typ, "turn": "left"}, **kw))
    return d


@pytest.mark.parametrize("typ,nf,nl", [("straight", 1, 0), ("L", 2, 1), ("U", 2, 1)])
def test_layout(typ, nf, nl):
    s = B.settings_of(B.default_data())
    lay = B.stair_layout({"x": 5, "y": 5, "dir": 0, "type": typ}, s)
    assert len(lay["flights"]) == nf and len(lay["landings"]) == nl
    assert sum(f["n"] for f in lay["flights"]) == lay["n"]
    xs = [q[0] for q in lay["rect"]]
    ys = [q[1] for q in lay["rect"]]
    assert abs((min(xs) + max(xs)) / 2 - 5) < 1e-9 and abs((min(ys) + max(ys)) / 2 - 5) < 1e-9
    if nl:
        assert abs(lay["landings"][0]["z"] - lay["flights"][1]["z0"]) < 1e-9


def test_turn_side():
    s = B.settings_of(B.default_data())
    left = B.stair_layout({"x": 0, "y": 0, "dir": 0, "type": "L", "turn": "left"}, s)
    right = B.stair_layout({"x": 0, "y": 0, "dir": 0, "type": "L", "turn": "right"}, s)
    assert left["flights"][1]["d"] == (0.0, 1.0) and right["flights"][1]["d"] == (0.0, -1.0)
    u = B.stair_layout({"x": 0, "y": 0, "dir": 0, "type": "U"}, s)
    assert u["flights"][1]["d"][0] == -1.0


def test_plan_model_and_boq():
    s = B.settings_of(B.default_data())
    pl = B.stair_plan({"x": 0, "y": 0, "dir": 1, "type": "U"}, s)
    assert len(pl["polys"]) == 3 and len(pl["walk"]) == 4 and len(pl["treads"]) == 17 - 2
    from core import wanic_quantities as Q
    vols = {}
    for typ in ("straight", "U"):
        d = _house(typ)
        g = B.stair_members(d["floors"][0]["stairs"][0], B.settings_of(d), 0.0)
        assert len(g) == (1 if typ == "straight" else 3)
        vols[typ] = sum(ln["net"] for ln in Q.compute(d)["lines"]
                        if ln["group"] == "stair" and ln["unit"] == "ลบ.ม.")
    assert vols["U"] > vols["straight"] > 0          # the landing adds concrete


def test_design_and_checks():
    d = _house("U")
    dz = ST.designs(d)[0]
    assert dz["geo"][0][3] and len(dz["flights"]) == 2 and dz["beam"]
    assert dz["wu_inc"] > dz["wu_land"]
    # a riser over 20 cm fails the law check
    d2 = _house("straight")
    d2["settings"]["riser_max"] = 0.25
    d2["settings"]["floor_h"] = 2.0
    dz2 = ST.designs(d2)[0]
    assert not dz2["members"][0].ok or dz2["layout"]["R"] <= 0.20


def test_suggest_makes_it_pass():
    d = _house("straight")
    stp = d["floors"][0]["stairs"][0]
    b_ = C.basis(d)
    s = B.settings_of(d)
    assert not all(m.ok for m in ST.design(stp, s, b_)["members"])
    ch, _beam, tips = ST.suggest(stp, s, b_)
    assert ch and tips
    assert all(m.ok for m in ST.design(dict(stp, **ch), s, b_)["members"])
    done = ST.apply_all(d)
    assert done and all(m.ok for dz in ST.designs(d) for m in dz["members"])


def test_in_the_calculation_and_advice():
    from core import wanic_advice as AD
    d = _house("straight")
    res = C.analyse(d)
    st = [m for m in res["members"] if m.group == "stair"]
    assert st and res["stairs"]
    bad = next(m for m in st if not m.ok)
    tips = AD.advice_by_member(res, d)
    assert bad.name in tips
    fix = AD.member_fix(res, d, bad)
    assert fix["target"] == "stair" and fix["changes"]
    from core.wanic_fix_view import apply
    apply(d, fix, {k: v for k, v in fix["changes"].items()})
    assert all(m.ok for m in C.analyse(d)["members"] if m.group == "stair")
