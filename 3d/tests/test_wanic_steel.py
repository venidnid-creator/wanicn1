# SPDX-License-Identifier: GPL-3.0-or-later
"""เหล็กรูปพรรณ: section properties, the ASD checks, the building's design."""
import copy
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from core import wanic_building as B
from core import wanic_steel as S


def test_section_properties_close_to_the_tables():
    s = S.lookup("H 200×200×8×12")
    assert s.A == pytest.approx(63.5, rel=0.03)          # JIS: 63.53 cm² (with fillets)
    assert s.Ix == pytest.approx(4720, rel=0.05)
    assert s.ry == pytest.approx(5.02, rel=0.03)
    w = S.lookup("WF 300×150×6.5×9")
    assert w.Sx == pytest.approx(481, rel=0.05)


def test_fb_and_fa():
    s = S.lookup("WF 300×150×6.5×9")
    assert S.Fb_of(s, 50, 2450) == pytest.approx(0.66 * 2450)       # braced: compact
    assert S.Fb_of(s, 600, 2450) < 0.66 * 2450
    assert S.Fa_of(0, 2450) == pytest.approx(0.6 * 2450)             # stub: Fy/(5/3)
    assert S.Fa_of(150, 2450) < S.Fa_of(80, 2450)


def test_pick_lightest_passing_beam():
    chk = S.pick(S.BEAMS, lambda s: S.beam_check(s, 6.0, 6000.0, 4000.0, 3.0, 2450, 360, 1333))
    assert chk.ok
    lighter = [s for s in S.BEAMS if s.kg_m < chk.sec.kg_m]
    assert all(not S.beam_check(s, 6.0, 6000.0, 4000.0, 3.0, 2450, 360, 1333).ok for s in lighter)


def test_building_in_steel_groups_and_base_plates():
    d = B.default_data()
    d["floors"][0]["rooms"] = [dict(x=0, y=0, w=4, d=4), dict(x=4, y=0, w=4, d=4)]
    d["settings"]["roof"] = "gable"
    d["floors"].append(copy.deepcopy(d["floors"][0]))
    res = S.design_building(d)
    assert res["beams"] and res["columns"] and res["weight"] > 0
    assert all(r["check"].ok for r in res["beams"] + res["columns"])
    first = [r for r in res["columns"] if r["floor"] == 0]
    assert len({r["check"].sec.label for r in first}) == 1          # grouped: one size per mark/floor
    assert all(r["plate"]["fp"] <= r["plate"]["fp_all"] for r in first)
    d["steel"] = {"group": False}
    ung = S.design_building(d)
    assert ung["weight"] <= res["weight"] + 1e-6
