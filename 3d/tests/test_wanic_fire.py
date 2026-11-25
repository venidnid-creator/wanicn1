# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ข12: การทนไฟ — กฎกระทรวง 2566 ข้อ 21–24, ประกาศ มท. 2567 ตาราง 17–18."""
from __future__ import annotations

from core import wanic_advice as AD
from core import wanic_building as B
from core import wanic_calc as C
from core import wanic_fire as FI
from core import wanic_rc as R


def _bldg(use, n=2, xs=(4.0, 4.0), ys=(4.0, 3.0)):
    d = B.default_data()
    R.apply_grid(d, list(xs), list(ys), n)
    d["calc"] = {"use": use}
    return d


def test_a_house_needs_no_rating():
    req = FI.requirements(_bldg("house"))
    assert not req["applies"] and not req["hours"] and not FI.checks(_bldg("house"))


def test_a_hospital_two_hours_at_the_top_and_the_least_sizes():
    d = _bldg("hospital", n=2)
    req = FI.requirements(d)
    assert req["applies"] and req["hours"] == {0: 2, 1: 2}
    got = FI.checks(d)
    cols = [g for g in got if g[0] == "column"]
    assert cols and all(g[4] == 250 for g in cols)                 # columns 20 cm < 25 cm
    assert any(g[0] == "cover" for g in got)                       # 35 mm < 50 mm
    res = C.analyse(d)
    bad = [m for m in res["members"] if " ทนไฟ ชั้น " in m.name]
    assert bad and all(not m.ok for m in bad)
    fix = AD.member_fix(res, d, next(m for m in bad if m.group == "column"))
    assert fix["changes"].get("b", 0) >= 0.25 and fix["changes"].get("h", 0) >= 0.25


def test_floors_counted_from_the_top():
    d = _bldg("hotel_like", n=6)
    d["calc"]["use"] = "condo"
    h = FI.requirements(d)["hours"]
    assert [h[f] for f in range(6)] == [2, 2, 1, 1, 1, 1]          # 1–4 from the top 1 h, 5–14 2 h


def test_auto_design_makes_them_pass():
    from core import wanic_autodesign as AU
    d = _bldg("hospital", n=2)
    lines = AU.fire_sizes(d)
    assert lines and not [g for g in FI.checks(d) if g[0] in ("slab", "column")]


def test_the_cover_is_set_by_the_fix_and_used_everywhere():
    from core.wanic_fix_view import apply
    from core import wanic_cutting as CT
    d = _bldg("hospital", n=2)
    res = C.analyse(d)
    rows = [m for m in res["members"] if " ทนไฟ ระยะหุ้ม " in m.name]
    assert {m.name.split(" ")[0] for m in rows} == {"PC1", "C1"}          # the stumps too
    curve0 = C.pm_curve(B.library_of(d)["C1"], C.basis(d))
    for row in rows:
        fix = AD.member_fix(res, d, row)
        assert fix["changes"] == {"cover": 0.05}
        apply(d, fix, fix["changes"])
    sp = B.library_of(d)["C1"]
    assert R.cover_of(sp) == 0.05
    assert max(m for m, _p in C.pm_curve(sp, C.basis(d))) < max(m for m, _p in curve0)   # less lever arm
    res = C.analyse(d)
    assert not [m for m in res["members"] if m.name.startswith("C1 ทนไฟ ระยะหุ้ม")]
    tie = next(it for it in CT.items(B.elements(d)) if it.group == "เสา" and it.bar == "ปลอก")
    assert abs(tie.length - (2 * (0.2 + 0.2 - 4 * 0.05) + 2 * 0.075)) < 1e-6
    from core import wanic_drawings as D
    assert "5.0 ซม. (ทนไฟ" in D.col_cover_text(B.elements(d))
