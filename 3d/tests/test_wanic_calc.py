# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""คำนวณโครงสร้าง: the continuous-beam solver against textbook cases,
section properties, the load path and the capacity checks."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from core import wanic_building as B
from core import wanic_calc as C


def test_simple_span_udl_and_point_load():
    r = C.solve_beam([C.Span(4.0, 1000.0)])
    assert r.Mmax == pytest.approx(1000 * 16 / 8, rel=1e-3)          # wL²/8
    assert r.reactions == pytest.approx([2000.0, 2000.0])
    r = C.solve_beam([C.Span(4.0, 0.0, [(2.0, 1000.0)])])
    assert r.Mmax == pytest.approx(1000 * 4 / 4, rel=1e-3)           # PL/4


def test_two_and_three_equal_spans():
    r = C.solve_beam([C.Span(1, 1), C.Span(1, 1)])
    assert r.Mmin == pytest.approx(-0.125)                          # −wL²/8 over the middle
    assert r.reactions == pytest.approx([0.375, 1.25, 0.375])
    assert r.Mmax == pytest.approx(0.0703, abs=1e-3)                 # 9/128 wL²
    r = C.solve_beam([C.Span(1, 1)] * 3)
    assert r.Mmin == pytest.approx(-0.1, abs=1e-6)                   # −wL²/10
    assert r.reactions == pytest.approx([0.4, 1.1, 1.1, 0.4])


def test_section_properties_of_a_lip_channel_and_timber():
    s = C.section("C 75×45×15×2.3")
    assert s["kg_m"] == pytest.approx(3.35, abs=0.05)                 # the steel tables: 3.25-3.4 kg/m
    assert 3.0e-7 < s["I"] < 4.5e-7
    t = C.section('ไม้ 2"×6" (50×150)')
    assert t["timber"] and t["I"] == pytest.approx(0.05 * 0.15 ** 3 / 12, rel=1e-3)


def _house(rooms):
    d = B.default_data()
    d["floors"][0]["rooms"] = rooms
    d["settings"]["roof"] = "gable"
    return d


def test_the_whole_house_has_every_kind_and_the_loads_add_up():
    d = _house([dict(name="a", x=0, y=0, w=4, d=4), dict(name="b", x=4, y=0, w=4, d=4)])
    res = C.analyse(d)
    groups = {m.group for m in res["members"]}
    assert groups == {"roof", "slab", "beam", "column", "footing"}
    beams = [m for m in res["members"] if m.group == "beam"]
    assert all(m.diagram is not None for m in beams)
    cols = dict(res["columns"])
    assert cols[(4.0, 0.0)] > cols[(0.0, 0.0)] * 1.5                  # the middle column carries more
    # a lighter floor load gives smaller column loads
    d["calc"] = {"ll_floor": 50.0}
    light = dict(C.analyse(d)["columns"])
    assert light[(4.0, 0.0)] < cols[(4.0, 0.0)]


def test_wsd_and_piles():
    d = _house([dict(name="a", x=0, y=0, w=4, d=4)])
    d["calc"] = {"method": "WSD"}
    d.setdefault("library", {})["F1"] = {"kind": "footing", "piles": 2}
    res = C.analyse(d)
    assert res["basis"]["method"] == "WSD"
    f = [m for m in res["members"] if m.group == "footing"]
    assert f and all("เข็ม 2 ต้น" in m.name for m in f)
    assert all(0.0 < m.ratio for m in res["members"])


def test_pdf_report(tmp_path):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from core.wanic_calc_view import report_pdf
    d = _house([dict(name="a", x=0, y=0, w=4, d=4), dict(name="b", x=4, y=0, w=3, d=4)])
    report_pdf(C.analyse(d), d, tmp_path / "calc.pdf")
    data = (tmp_path / "calc.pdf").read_bytes()
    assert data.startswith(b"%PDF") and data.count(b"/Type /Page\n") + data.count(b"/Type /Page ") >= 1
