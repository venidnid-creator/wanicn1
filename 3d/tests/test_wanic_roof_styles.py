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


def test_a_separate_lower_building_gets_its_own_roof():
    """owner 27 Nov: «กรณีสร้างอาคารแยก แล้วโครงหลังคาไม่สร้างตาม» — a one-storey room beside a
    two-storey building is roofed at its own height."""
    import copy as _c
    from core import wanic_building as B
    d = B.default_data()
    main = [dict(name="a", x=0, y=0, w=5, d=4), dict(name="b", x=5, y=0, w=5, d=4)]
    f0 = _c.deepcopy(d["floors"][0])
    f0["rooms"] = main + [dict(name="c", x=14, y=0, w=5, d=4)]
    f1 = _c.deepcopy(d["floors"][0])
    f1["rooms"] = _c.deepcopy(main)
    d["floors"] = [f0, f1]
    d["settings"]["roof"] = "hip"
    assert [(len(r), n) for r, n in B.roof_zones(d)] == [(2, 2), (1, 1)]
    L = B.roof_lines(d)
    assert (14.0, 0.0, 19.0, 4.0) in L["rects"]
    H = float(B.settings_of(d)["floor_h"])
    assert any(abs(h[2] - H) < 1e-6 for h in L["heads"]) and any(abs(h[2] - 2 * H) < 1e-6 for h in L["heads"])
    assert min(p[2] for seg in L["rafter"] for p in seg if 14 <= p[0] <= 19) < 2 * H


def test_the_soffit_of_each_roof_part_at_its_own_eave():
    """owner 27 Nov: «ปรับฝ้าภายนอกใหม่» — a lower separate building has its soffit under its own
    eave, not hanging at the other roof's level; none inside the taller building's walls."""
    import copy as _c
    from core import wanic_building as B
    d = B.default_data()
    main = [dict(name="a", x=0, y=0, w=5, d=4), dict(name="b", x=5, y=0, w=5, d=4)]
    f0 = _c.deepcopy(d["floors"][0])
    f0["rooms"] = main + [dict(name="c", x=14, y=0, w=5, d=4)]
    f1 = _c.deepcopy(d["floors"][0])
    f1["rooms"] = _c.deepcopy(main)
    d["floors"] = [f0, f1]
    d["settings"]["roof"] = "hip"
    parts = B.soffit_parts(d)
    assert len(parts) == 2
    (hi_cells, z_hi), (lo_cells, z_lo) = sorted(parts, key=lambda p: -p[1])
    H = float(B.settings_of(d)["floor_h"])
    assert z_hi > z_lo + H * 0.8
    assert all(c[0] >= 13 for c in lo_cells) and all(c[2] <= 11 for c in hi_cells)


def test_a_lean_to_drains_to_the_chosen_side_in_one_plane():
    """owner 27 Nov: «น้ำฝนจะต้องไหลออกไปด้านหลังอาคาร ด้านข้างซ้าย ด้านข้างขวา»."""
    from core import wanic_building as B
    d = B.default_data()
    d["floors"][0]["rooms"] = [dict(name="a", x=0, y=0, w=5, d=4), dict(name="b", x=5, y=0, w=5, d=4),
                               dict(name="c", x=0, y=4, w=5, d=4)]
    d["settings"]["roof"] = "shed"
    for drain, axis, low_at_max in (("back", 1, True), ("front", 1, False), ("left", 0, False),
                                    ("right", 0, True)):
        d["settings"]["shed_drain"] = drain
        L = B.roof_lines(d)
        pts = [p for poly in L["skin"] for p in poly]
        lo = min(pts, key=lambda p: p[2])
        hi = max(pts, key=lambda p: p[2])
        assert (lo[axis] > hi[axis]) == low_at_max, drain
        # one plane: z is a function of that axis alone
        k = (hi[2] - lo[2]) / (hi[axis] - lo[axis])
        assert all(abs(p[2] - (lo[2] + k * (p[axis] - lo[axis]))) < 1e-6 for p in pts), drain
