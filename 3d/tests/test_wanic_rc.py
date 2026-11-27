# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ออกแบบโครงสร้าง คสล.: bar notation, the detailing checks, the fixes
and the reinforcement take-off."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from core import wanic_building as B
from core import wanic_rc as R


def test_bars_read_as_the_drawings_write_them():
    b = R.parse_bar("4-DB12")
    assert (b.kind, b.d, b.n, b.s) == ("DB", 12, 4, 0.0)
    b = R.parse_bar("RB9@0.20")
    assert (b.kind, b.d, b.n, b.s) == ("RB", 9, 0, 0.20)
    assert R.parse_bar("SD40 16") is None or R.parse_bar("SD16").kind == "DB"
    assert R.parse_bar("hello") is None
    assert R.parse_bar("DB12").kg_m == pytest.approx(0.888, abs=0.001)
    assert R.lap_length(R.parse_bar("DB12")) == pytest.approx(0.48)
    assert R.lap_length(R.parse_bar("RB6")) == pytest.approx(0.30)          # never under 0.30 m


def test_the_standard_marks_and_what_fails():
    lib = B.DEFAULT_LIB
    assert R.check("F1", lib["F1"]).ok and R.check("C1", lib["C1"]).ok and R.check("S1", lib["S1"]).ok
    gb = R.check("GB1", lib["GB1"])
    assert not gb.ok and any("14/fy" in line for line in gb.lines())          # 2-DB12 in 0.20×0.40
    assert not R.check("C", dict(kind="column", b=0.3, h=0.3, main="4-DB12", tie="RB6@0.15")).ok
    assert not R.check("S", dict(kind="slab", t=0.10, bars="RB6@0.30")).ok
    assert not R.check("F", dict(kind="footing", w=1, l=1, t=0.30, bars="DB12@0.50")).ok
    bad = R.check("X", dict(kind="beam", b=0.2, h=0.4, top="?", bot="3-DB12", stir="RB6@0.15"))
    assert any("อ่านไม่ได้" in line for line in bad.lines())


def test_suggest_passes_without_changing_the_size():
    for spec in (B.DEFAULT_LIB["GB1"], dict(kind="slab", t=0.12, bars="RB6@0.30"),
                 dict(kind="column", b=0.3, h=0.3, main="4-DB12", tie="RB6@0.20"),
                 dict(kind="footing", w=1.2, l=1.2, t=0.30, bars="DB12@0.50")):
        new = R.suggest(spec)
        assert R.check("?", new).ok, new
        assert all(new[k] == spec[k] for k in ("b", "h", "t", "w", "l") if k in spec)
    assert R.suggest(B.DEFAULT_LIB["GB1"])["bot"] == "3-DB12"


def test_takeoff_by_bar_size_and_concrete():
    d = B.default_data()
    d["floors"][0]["rooms"] = [dict(name="a", x=0, y=0, w=4, d=4), dict(name="b", x=4, y=0, w=4, d=4)]
    E = B.elements(d)
    T = R.takeoff(E)
    assert set(T["bars"]) == {"DB12", "RB6", "RB9"}
    assert T["kg"] == pytest.approx(sum(v["kg"] for v in T["bars"].values()))
    assert T["wire"] == pytest.approx(T["kg"] / 1000 * 20)
    assert T["concrete"]["column"] == pytest.approx(6 * 0.2 * 0.2 * 3.0)
    assert sum(v["n"] for k, v in T["by_mark"].items() if k == "F1") == 6
    assert R.grid_axes(E) == ([0.0, 4.0, 8.0], [0.0, 4.0])
    assert R.axis_names(3, True) == ["A", "B", "C"] and R.axis_names(28, True)[26] == "AA"


def test_report_workbook(tmp_path):
    d = B.default_data()
    d["floors"][0]["rooms"] = [dict(name="a", x=0, y=0, w=4, d=4)]
    R.report_xlsx(B.elements(d), tmp_path / "rc.xlsx")
    import zipfile
    with zipfile.ZipFile(tmp_path / "rc.xlsx") as z:
        book = z.read("xl/workbook.xml").decode("utf-8")
        assert len([n for n in z.namelist() if n.startswith("xl/worksheets/sheet")]) == 3
    for name in ("ตรวจเหล็กเสริม", "ปริมาณตามเบอร์", "เหล็กเสริมตามขนาด"):
        assert name in book


def test_spread_footings_or_piles_both_designed_to_pass():
    """owner 27 Nov: choose spread footings or piles — both designed to pass, the model follows;
    3 storeys and up go on I piles by default."""
    import copy as _c
    from core import wanic_autodesign as AU
    from core import wanic_building as B
    d = B.default_data()
    rooms = [dict(name="a", x=0, y=0, w=4, d=4), dict(name="b", x=4, y=0, w=4, d=4)]
    d["floors"] = [dict(_c.deepcopy(d["floors"][0]), rooms=_c.deepcopy(rooms)) for _ in range(3)]
    d["settings"]["roof"] = "hip"
    assert B.foundation_mode(d) == "pile"
    out = AU.design(d)
    feet = {k: v for k, v in B.library_of(d).items() if v["kind"] == "footing"}
    assert not out["failing"] and all(int(v["piles"]) >= 1 and v["pile"] == "P1" for v in feet.values())
    for v in feet.values():                         # the cap fits its piles
        sz = B.pile_cap_size(int(v["piles"]), 0.18)
        assert (v["w"], v["l"]) == (sz["w"], sz["l"])
        pts = B.pile_points(v, 0.0, 0.0)
        assert len(pts) == int(v["piles"])
        assert all(abs(x) <= v["w"] / 2 and abs(y) <= v["l"] / 2 for x, y in pts)
    d["foundation"] = "spread"
    out = AU.design(d)
    feet = {k: v for k, v in B.library_of(d).items() if v["kind"] == "footing"}
    assert not out["failing"] and all(int(v.get("piles") or 0) == 0 for v in feet.values())
    assert max(v["w"] for v in feet.values()) > 2.0
    two = B.default_data()
    two["floors"][0]["rooms"] = _c.deepcopy(rooms)
    assert B.foundation_mode(two) == "spread"


def test_the_code_alone_by_default_and_the_reserve_as_an_option():
    """owner 27 Nov: «แก้ไข ใช้มาตรฐาน วสท.» — 100 % of the strength by default; 50 % (a reserve of
    1×) only when chosen, then auto-design brings every member within it."""
    import copy as _c
    from core import wanic_autodesign as AU
    from core import wanic_building as B
    from core import wanic_calc as C
    assert C.basis({})["max_use"] == 1.0
    d = B.default_data()
    d["floors"][0]["rooms"] = [dict(name="a", x=0, y=0, w=4, d=4), dict(name="b", x=4, y=0, w=4, d=4)]
    d["settings"]["roof"] = "gable"
    base = _c.deepcopy(d)
    AU.design(base)
    assert all(m.limit == 1.0 for m in C.analyse(base)["members"])
    d["calc"] = {"max_use": 0.5}
    out = AU.design(d)
    assert not out["failing"]
    for m in out["res"]["members"]:
        if m.limit < 1.0:
            assert (m.strength if m.strength is not None else m.ratio) <= 0.5 + 1e-9
    assert "_design" not in d["calc"]
