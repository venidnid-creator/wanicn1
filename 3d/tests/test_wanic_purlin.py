# SPDX-License-Identifier: GPL-3.0-or-later
"""แป · Sag Rod · Tie Rod · แปผนัง."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from core import wanic_purlin as P


def test_lip_channel_close_to_the_tables():
    s = P.lipc("C 100×50×20×2.3")            # JIS: A 5.17, Ix 80.7, Iy 19.0, Sx 16.1
    assert s.A == pytest.approx(5.17, rel=0.05)
    assert s.Ix == pytest.approx(80.7, rel=0.06)
    assert s.Iy == pytest.approx(19.0, rel=0.06)
    assert s.Sx == pytest.approx(16.1, rel=0.06)


def test_sag_rods_cut_the_weak_axis_moment():
    s = P.lipc("C 100×50×20×2.3")
    r0, *_x = P.purlin_check(s, 4.0, 1.0, 30, 50, 30, 0, 0)
    r1, *_x = P.purlin_check(s, 4.0, 1.0, 30, 50, 30, 0, 1)
    assert r1 < r0


def test_design_passes_and_rods_are_sized():
    p, d = P.design_of({"truss": {"spacing": 4.0}, "purlin": {"wall_sheet": True}})
    assert all(r.ok for r in d["rows"])
    assert d["rod"] and d["tie"] and d["girt"]
    assert len(d["rows"]) == 4


def test_rod_sizes_grow_with_force():
    assert P.rod_for(500)[0] == "RB9"
    assert P.rod_for(1000)[0] == "RB12" and P.rod_for(3000)[0] == "RB19"
