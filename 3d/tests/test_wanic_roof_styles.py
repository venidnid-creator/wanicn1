# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""Gable trusses on the walls and symmetric; ทรงไทย, จั่วซ้อน; timber frames."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core import wanic_building as B
from core import wanic_partprice as PP


def _data(roof, **kw):
    d = B.default_data()
    d["floors"][0]["rooms"] = [dict(name="ห้องนอน", x=0, y=0, w=4, d=4),
                               dict(name="ห้องนั่งเล่น", x=4, y=0, w=4, d=4)]
    d["settings"].update(roof=roof, pitch=35.0, overhang=1.0, **kw)
    return d


def test_gable_trusses_stand_on_the_walls_not_out_on_the_overhang():
    L = B.roof_lines(_data("gable"))
    xs = sorted({round(p[0][0], 3) for p in L["post"]})
    assert xs[0] == 0.0 and xs[-1] == 8.0         # the gable walls, none out at -1.0 / 9.0
    ties = {round(seg[0][0], 3) for seg in L["tie"]}
    assert min(ties) >= 0.0 and max(ties) <= 8.0


def test_each_truss_is_symmetric_about_the_ridge():
    L = B.roof_lines(_data("gable"))
    yc = 2.0
    for x in (0.0, 4.0, 8.0):
        st = sorted(round(m[0][1] - yc, 3) for m in L["strut"] if abs(m[0][0] - x) < 1e-6)
        assert st == sorted(-v for v in st) and st
        br = sorted(round(m[1][1] - yc, 3) for m in L["brace"] if abs(m[0][0] - x) < 1e-6)
        assert br == sorted(-v for v in br)


def test_thai_roof_is_steep_with_a_skirt_each_side():
    L = B.roof_lines(_data("thai"))
    top = max(p[2] for poly in L["skin"] for p in poly)
    g = B.roof_lines(_data("gable"))
    assert top > max(p[2] for poly in g["skin"] for p in poly)      # steeper
    low = min(p[2] for poly in L["skin"] for p in poly)
    assert low < min(p[2] for poly in g["skin"] for p in poly) + 0.5
    assert len(L["skin"]) >= 4                                        # 2 slopes + 2 skirts


def test_double_gable_adds_a_lower_front_gable_running_the_same_way():
    L = B.roof_lines(_data("double"))
    ridges = sorted(L["ridge"], key=lambda r: -r[0][2])
    assert len(ridges) >= 2
    main, front = ridges[0], ridges[-1]
    assert front[0][2] < main[0][2]
    assert abs(front[0][1] - front[1][1]) < 1e-6                      # along x, like the main ridge
    assert min(front[0][0], front[1][0]) < -1.0                       # out in front of the gable


def test_timber_frame_members_are_timber_and_priced_by_volume():
    d = _data("gable", **B.TIMBER_FRAME)
    groups, _c = B.build(d, ("roof",))
    raft = next(g for g in groups if g.ext[B.EXT_KEY]["kind"] == "rafter")
    rows = dict(map(tuple, raft.ext[B.EXT_KEY]["info"]))
    assert "ไม้" in rows["หน้าตัด"] and "โครงหลังคาไม้" in rows["ชนิด"]
    assert PP._qty(raft, "rafter", raft.ext[B.EXT_KEY]["info"])[0] == "timber"
    assert all(B.is_timber(v) for v in B.TIMBER_FRAME.values())
