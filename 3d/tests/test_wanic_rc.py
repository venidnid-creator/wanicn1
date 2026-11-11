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
