# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""DR (ทถ-5) and TS (ทถ-3) sheets drawn from the road."""
import math

import pytest

from core import wanic_drawings as D
from core import wanic_road as R
from core import wanic_road_furniture as RF
from core import wanic_road_sheets as RS
from core.road import alignment as A

E0, N0 = 700000.0, 1400000.0


def _road():
    stakes = [R.PiStake("1", E0, N0, "POT"), R.PiStake("2", E0 + 120, N0 + 600, "PI", radius=120.0),
              R.PiStake("3", E0 - 60, N0 + 1300, "PI", radius=400.0),
              R.PiStake("4", E0 + 40, N0 + 2100, "POT")]
    al = R.alignment_from_pis(stakes, step=2.0)
    rows, num = [], 1
    for st in A.stations(al.axis, 25.0):
        for o in range(-20, 21, 4):
            x, y = st.offset_point(o)
            rows.append(f"{num},{x:.3f},{y:.3f},{95.0 + 4.0 * math.sin(st.s / 100.0) + 0.04 * o:.3f},N")
            num += 1
    shots = R.parse_points("\n".join(rows))
    tin = R.build_tin(shots)
    return R.analyse(shots, al.axis, R.auto_pvis(tin, al.axis), R.Settings(), tin, al.curves), shots


def test_standard_tables_as_the_drawings():
    assert RF.PIPE_T1[600] == (75, 40, 28, 15, 32) and RF.PIPE_T2[1000] == (4.2, 3.2, 65000)
    assert RF.HEADWALL[60][2:4] == (195, 195) and RF.UDRAIN["ข-50"][:4] == (50, 50, 10, 15)
    assert RF.guide_spacing(120) == (7, 13, 21, 42) and RF.guide_spacing(800) == (15, 27, 45, 60)
    assert RF.rail_spacing(120) == 4.0 and RF.rail_spacing(30) == 3.0 and RF.rail_spacing(10) == 2.0
    assert RF.no_pass_distance(60) == 180
    q, v = RF.pipe_capacity(0.60, 0.005)
    assert q == pytest.approx(0.434, abs=0.002) and v == pytest.approx(1.54, abs=0.01)


def test_culverts_at_the_low_points_with_cover():
    an, _ = _road()
    cs = RF.find_culverts(an, {"pipe_d": 0.60})
    assert cs, "the ground's dips get culverts"
    for c in cs:
        assert c.cover >= RF.COVER_MIN - 1e-6                 # lowered into the ground if need be
        assert c.length == int(c.length) and c.length >= an.settings.width + 2 * an.settings.shoulder
        assert c.pipes == c.length * c.rows
    given = RF.find_culverts(an, {"culverts": [(500.0, 1.0, 2)]})
    assert len(given) == 1 and given[0].d == 1.0 and given[0].rows == 2


def test_signs_guide_posts_and_guard_rail_from_the_curves():
    an, _ = _road()
    fu = RF.Furniture(an, {"signs": {"speed": 60}})
    assert any(it[2] == "km" for it in fu.items) and sum(it[2] == "น-1" for it in fu.items) == 2
    assert sum(it[2] == "warn" for it in fu.items) == 4              # two curves, both ways
    assert len(fu.rail) == 1 and len(fu.guide) == 1                    # R 120 rail, R 400 posts
    m = fu.markings()
    assert m["centre"] and m["area"] == pytest.approx((m["edge"] + m["solid"] + m["broken"]) * 0.10)
    an.settings.width = 5.0
    assert not RF.Furniture(an).markings()["centre"]                   # 5 m or less: no centre line


def test_dr_and_ts_sheets_in_the_set():
    an, shots = _analysis = _road()
    S = RS.build_road_set(an, {"drain": {"u_type": "ข-50", "u_length": 400.0}, "signs": {"speed": 60}},
                          shots, ("DR", "TS"))
    assert [s.code for s in S] == ["DR-01", "DR-02", "TS-01", "TS-02"]
    t = " ".join(x for s in S for x in s.texts())
    for word in ("ทถ-5-101", "ทถ-5-103", "ทถ-5-301", "Manning", "ทถ-3-112", "GUARD RAIL", "หลักกิโลเมตร",
                 "THERMOPLASTIC", "ตารางท่อลอด"):
        assert word in t, word
    for sh in S:
        for it in sh.items:
            pts = [it[1][:2], it[1][2:]] if it[0] == "line" else it[1] if it[0] in ("poly", "fill") else []
            for x, y in pts:
                assert -1 <= x <= D.PAPER[0] + 1 and -1 <= y <= D.PAPER[1] + 1, sh.code
