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


def test_slab_coefficients_and_edge_continuity():
    assert C.slab_moment(1.0, 0) == pytest.approx(0.033)              # interior panel
    assert C.slab_moment(1.0, 4) == pytest.approx(0.050)              # all edges discontinuous
    assert C.slab_moment(0.5, 2) == pytest.approx(0.090)
    assert C.slab_moment(0.95, 1) == pytest.approx((0.041 + 0.048) / 2)
    rooms = [dict(x=0, y=0, w=4, d=4), dict(x=4, y=0, w=4, d=4), dict(x=0, y=4, w=4, d=3)]
    assert C.discontinuous_edges(rooms[0], rooms) == 2
    assert C.discontinuous_edges(rooms[1], rooms) == 3
    assert C.discontinuous_edges(dict(x=0, y=0, w=4, d=4), []) == 4


def test_column_interaction_curve_and_ratio():
    curve = C.pm_curve(B.DEFAULT_LIB["C1"], C.basis({}))
    p0 = curve[0][1]
    assert p0 == pytest.approx(0.8 * 0.7 * (0.85 * 240 * (400 - 4.52) + 4000 * 4.52), rel=0.01)
    assert curve[-1][1] == 0.0 and curve[-1][0] > 0                  # pure bending at the end
    assert max(m for m, _ in curve) > curve[-1][0]                    # the balance point bulges out
    assert C.pm_ratio(curve, 0.0, p0 / 2) == pytest.approx(0.5, abs=0.01)
    assert C.pm_ratio(curve, 5000.0, 10000.0) > 1.0


def test_wind_uplift_on_a_light_roof():
    d = _house([dict(name="a", x=0, y=0, w=4, d=4), dict(name="b", x=4, y=0, w=4, d=4)])
    d["calc"] = {"wind": 100.0}
    roof = [m for m in C.analyse(d)["members"] if m.group == "roof"]
    assert any("แรงลม" in m.name for m in roof)
    assert any("จุดยึด" in m.name for m in roof)
    d["calc"] = {"wind": 0.0}
    assert not any("แรงลม" in m.name for m in C.analyse(d)["members"])


def test_the_a3_booklet(tmp_path):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from core.wanic_calc_book import make_book
    d = _house([dict(name="a", x=0, y=0, w=4, d=4), dict(name="b", x=4, y=0, w=4, d=4)])
    res = C.analyse(d)
    assert res["cards"] and all(c["P"] > 0 for c in res["cards"])
    stump = max(c["P"] for c in res["cards"] if c["floor"] < 0)
    col = max(c["P"] for c in res["cards"] if c["floor"] == 0)
    assert stump > col                                              # the stump carries the ground beams too
    n = make_book(res, d, tmp_path / "book.pdf", {"project": "ทดสอบ", "engineer": "ผู้คำนวณ"})
    beams = sum(1 for m in res["members"] if m.group == "beam")
    assert n >= 2 + beams + 1
    assert (tmp_path / "book.pdf").read_bytes().startswith(b"%PDF")
