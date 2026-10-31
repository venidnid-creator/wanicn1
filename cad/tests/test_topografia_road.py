# SPDX-License-Identifier: GPL-3.0-or-later
"""Topography plugin, road design: a fast and exact surface lookup on a
real-sized survey, vertical curves on the grade line, a crowned template
with shoulders, sections labelled the way a road's are read, and the
stations on the plan."""
from __future__ import annotations

import math
import time

import pytest

from core.commands import History
from core.document import Document
from plugins.topografia import actions, alignment, profile
from plugins.topografia.tin import build_tin


def _road_survey():
    """A 2.3 km winding road in UTM coordinates, surveyed as cross sections
    every 25 m, a shot every metre to 20 m each side -- the survey a
    RoadOne user brings, 5 700 points."""
    e0, n0 = 700000.0, 1600000.0
    axis = [(e0 + k, n0 + 80.0 * math.sin(k / 400.0)) for k in range(0, 2301, 50)]
    pts = []
    for st in alignment.stations(axis, 25.0):
        for o in range(-20, 21):
            x, y = st.offset_point(o)
            pts.append((x, y, 95.0 + 8.0 * math.sin(st.s / 500.0) + 0.05 * o))
    return axis, pts


def test_the_surface_lookup_is_fast_and_exact_on_a_real_road():
    axis, pts = _road_survey()
    tin = build_tin(pts)
    # exact on the surveyed shots, between triangles and on their edges
    for st in alignment.stations(axis, 25.0)[::7]:
        for o in (-20, -7, 0, 13, 20):
            x, y = st.offset_point(o)
            z = 95.0 + 8.0 * math.sin(st.s / 500.0) + 0.05 * o
            assert tin.z_at(x, y) == pytest.approx(z, abs=1e-6)
    # every sample of every section is on the surface (no hole on an edge)
    for st in alignment.stations(axis, 20.0)[1:-1]:
        assert len(profile.cross_section(tin, st, 15.0, 0.5)) == 61
    assert tin.z_at(0.0, 0.0) is None
    # VOLUMES used to take 44 s here and freeze the window
    grade = [(0.0, 96.0), (1200.0, 101.0), (alignment.polyline_length(axis), 97.0)]
    t = time.perf_counter()
    rows = profile.earthworks(tin, axis, grade, 20.0, profile.Template(), method="prismoidal")
    assert time.perf_counter() - t < 10.0
    assert len(rows) > 100 and rows[-1].cut_total > 0 and rows[-1].fill_total > 0


def test_a_sag_curve_is_labelled_like_a_road_profile_and_followed_by_the_grade():
    pvis = [(0.0, 100.0), (100.0, 97.0), (200.0, 99.0)]           # -3 % then +2 %
    (curve,) = profile.vertical_curves(pvis, 60.0)
    assert (curve.bvc, curve.evc) == pytest.approx((70.0, 130.0))
    assert curve.middle_ordinate == pytest.approx(5.0 * 60.0 / 800.0)  # + for a sag
    assert curve.z_at(70.0) == pytest.approx(97.9)
    assert curve.z_at(130.0) == pytest.approx(97.6)
    assert curve.z_at(100.0) == pytest.approx(97.0 + curve.middle_ordinate)
    grade = profile.grade_with_curves(pvis, 60.0)
    assert profile.grade_at(grade, 100.0) == pytest.approx(97.375, abs=1e-6)
    assert profile.grade_at(grade, 50.0) == pytest.approx(98.5)   # the tangent is untouched
    # too long for the tangents: cut to fit, never past the middle of a segment
    (short,) = profile.vertical_curves(pvis, 500.0)
    assert short.length == pytest.approx(100.0)
    # a crest is negative, and a straight PVI carries none
    (crest,) = profile.vertical_curves([(0, 0), (50, 2), (100, 1)], 40.0)
    assert crest.middle_ordinate < 0
    assert profile.vertical_curves([(0, 0), (50, 1), (100, 2)], 40.0) == []


def test_the_grade_line_keeps_its_curves_and_the_sections_follow_them():
    tin = build_tin([(i * 10.0, j * 10.0, 100.0) for i in range(31) for j in range(21)])
    document = Document.new()
    history = History(document)
    history.execute(actions.build_surface(document, tin))
    msp = document.doc.modelspace()
    axis = msp.add_lwpolyline([(0.0, 100.0), (200.0, 100.0)])
    history.execute(actions.draw_profile(document, tin, axis, (400.0, 0.0), 20.0, 1.0, 10.0, 1.0, "EJE"))
    anchor = actions.profile_entities(document)[0]
    frame = actions.ProfileFrame.from_entity(anchor)
    design = msp.add_lwpolyline([frame.to_drawing(0.0, 100.0), frame.to_drawing(100.0, 97.0),
                                 frame.to_drawing(200.0, 99.0)])
    history.execute(actions.register_grade(document, design, anchor, frame, curve_lengths=60.0))
    texts = [e.dxf.text for e in msp if e.dxftype() == "TEXT"]
    assert "PVI STA. 0+100.000" in texts and "ELEV. = 97.000" in texts
    assert "VC. = 60.000" in texts and "MO. = +0.375" in texts
    assert "G = -3.000 %" in texts and "G = +2.000 %" in texts
    assert any(t.startswith("PVC STA. 0+070.000") for t in texts)
    assert any(actions.is_vertical_curve(e) for e in msp)
    assert actions.grade_curve_lengths(design) == pytest.approx([0.0, 60.0, 0.0])
    grade = actions.grade_of(design, frame)
    assert profile.grade_at(grade, 100.0) == pytest.approx(97.375, abs=1e-6)
    rows = actions.earthworks_rows(tin, axis, grade, 20.0, profile.Template(6.0, 1.0, 1.0))
    at_100 = next(r for r in rows if abs(r.s - 100.0) < 1e-6)
    assert at_100.z_design == pytest.approx(97.375, abs=1e-6)
    history.undo()
    assert not actions.is_grade(design) and not any(actions.is_vertical_curve(e) for e in msp)


def test_a_crowned_platform_with_shoulders():
    t = profile.Template(width=6.0, cut_hv=1.0, fill_hv=2.0, crown=2.5, shoulder=1.0, shoulder_slope=4.0)
    top = [c for p in t.top(89.386) for c in p]
    assert top == pytest.approx([-4.0, 89.271, -3.0, 89.311, 0.0, 89.386, 3.0, 89.311, 4.0, 89.271])
    ground = [(-15.0, 88.0), (15.0, 88.0)]
    design = profile.design_section(ground, 89.386, t)
    # a fill both ways at 2:1 from the shoulder edge down to the ground
    assert design[0] == pytest.approx((-4.0 - 2.0 * 1.271, 88.0))
    assert design[-1] == pytest.approx((4.0 + 2.0 * 1.271, 88.0))
    cut, fill = profile.areas(ground, design)
    assert cut == pytest.approx(0.0)
    top_area = 2 * (3.0 * (1.311 + 1.386) / 2.0 + 1.0 * (1.311 + 1.271) / 2.0)
    assert fill == pytest.approx(top_area + 2 * (2.0 * 1.271 * 1.271 / 2.0))
    # without crown and shoulders it is the old flat platform exactly
    assert profile.Template(6.0).top(100.0) == [(-3.0, 100.0), (3.0, 100.0)]


def test_stations_and_section_lines_on_the_plan():
    document = Document.new()
    history = History(document)
    msp = document.doc.modelspace()
    axis = msp.add_lwpolyline([(0.0, 0.0), (60.0, 0.0), (60.0, 40.0)])
    history.execute(actions.station_marks(document, axis, 25.0, 10.0))
    lines = [e for e in msp if e.dxftype() == "LINE" and actions.is_station_mark(e)
             and abs((e.dxf.end - e.dxf.start).magnitude - 20.0) < 1e-6]   # not the PI's cross
    assert len(lines) == 5                                           # 0, 25, 50, 75, 100
    texts = [e.dxf.text for e in msp if e.dxftype() == "TEXT"]
    assert {"0+000", "0+025", "0+050", "0+075", "0+100"} <= set(texts)
    assert "BEGIN STA. 0+000.000" in texts and "PI-1  STA. 0+060.000" in texts
    assert "Δ = 90°00'00\" LT" in texts and "(ANGLE POINT)" in texts
    assert "END STA. 0+100.000" in texts
    # the section line at 0+025 crosses the axis square, 10 m each side
    line = next(e for e in lines if abs(e.dxf.start.x - 25.0) < 1e-6)
    assert {round(line.dxf.start.y, 6), round(line.dxf.end.y, 6)} == {10.0, -10.0}
    assert alignment.format_station(2175.0, 0) == "2+175"
    history.undo()
    assert not [e for e in msp if e.dxftype() in ("LINE", "TEXT")]


def test_a_curve_surveyed_on_its_centre_line_gives_its_pi_pc_pt():
    """Tangent 150 m, a right curve R = 200 m of 1 rad, tangent 150 m,
    shots every 25 m on the centre line (one at PC and PT)."""
    def at(s):
        if s <= 150.0:
            return (s, 0.0)
        if s <= 350.0:
            a = (s - 150.0) / 200.0
            return (150.0 + 200.0 * math.sin(a), -200.0 * (1.0 - math.cos(a)))
        e, n = at(350.0)
        return (e + (s - 350.0) * math.cos(-1.0), n + (s - 350.0) * math.sin(-1.0))
    shots = [at(25.0 * k) for k in range(21)]
    (curve,) = alignment.horizontal_curves(shots)
    assert curve.side == "RT" and curve.delta == pytest.approx(math.degrees(1.0), abs=1e-6)
    assert curve.radius == pytest.approx(200.0, rel=1e-6)
    assert curve.tangent == pytest.approx(200.0 * math.tan(0.5))
    assert curve.length == pytest.approx(200.0)
    assert curve.external == pytest.approx(200.0 * (1 / math.cos(0.5) - 1))
    assert curve.middle_ordinate == pytest.approx(200.0 * (1 - math.cos(0.5)))
    assert curve.s_pc == pytest.approx(150.0) and curve.pi == pytest.approx((150.0 + curve.tangent, 0.0))
    assert alignment.format_dms(curve.delta) == "57°17'45\""
    assert alignment.horizontal_curves([(0, 0), (50, 0), (100, 0.1)]) == []


def test_the_road_tools_run_headless():
    from tests.test_topografia_earthworks import _Harness
    from plugins.topografia.tools import GradeLineTool, ProfileTool, StationsTool

    h = _Harness(build_tin([(i * 10.0, j * 10.0, 100.0) for i in range(31) for j in range(21)]))
    axis = h.msp.add_lwpolyline([(0.0, 100.0), (200.0, 100.0)])
    tool = StationsTool(h.ctx)
    tool.start()
    tool.on_selection([axis])
    assert tool.on_option("50")
    tool.on_enter()
    tool.on_enter()
    assert h.finished and any("Stations every 50 m" in line for line in h.echoed)

    h.finished = False
    tool = ProfileTool(h.ctx)
    tool.start()
    # the station marks just drawn are not taken for the axis
    tool.on_selection([e for e in h.msp if actions.is_station_mark(e)] + [axis])
    assert tool.on_option("20")
    tool.on_enter()
    tool.on_enter()
    tool.on_point((400.0, 0.0))
    assert h.finished
    frame = actions.ProfileFrame.from_entity(actions.profile_entities(h.document)[0])
    assert frame.axis_handle == axis.dxf.handle

    design = h.msp.add_lwpolyline([frame.to_drawing(0.0, 100.0), frame.to_drawing(100.0, 97.0),
                                   frame.to_drawing(200.0, 99.0)])
    h.finished = False
    grade = GradeLineTool(h.ctx)
    grade.start()
    grade.on_selection([design])
    assert not h.finished                                            # asks for the curve
    assert grade.on_option("60")
    assert h.finished and actions.is_grade(design)
    assert any("VC 60.000 m, MO +0.375 m" in line for line in h.echoed)


def test_breaklines_along_the_road_are_forced_in_quickly():
    axis, pts = _road_survey()
    marks = alignment.stations(axis, 10.0)
    lines = [[(*st.offset_point(off), 96.0) for st in marks]
             for off in (-3.3, 3.3, -7.7, 7.7)]                       # edges of pavement and shoulder
    t = time.perf_counter()
    tin = build_tin(pts, lines)
    assert time.perf_counter() - t < 15.0                            # 16 s before, on a fast machine
    edges = tin.edges()
    where = {(round(p[0], 6), round(p[1], 6)): i for i, p in enumerate(tin.points)}
    for line in lines:
        for a, b in zip(line, line[1:]):
            i, j = where[(round(a[0], 6), round(a[1], 6))], where[(round(b[0], 6), round(b[1], 6))]
            assert (min(i, j), max(i, j)) in edges
    assert tin.stats()["bad_edges"] == 0


def test_thai_text_in_a_latin_style_is_drawn_in_a_thai_font():
    """ดินตัด in an Arial style came out as boxes: ezdxf never falls back
    to another font for a missing glyph."""
    from ezdxf.addons.drawing.unified_text_renderer import UnifiedTextRenderer
    from ezdxf.fonts import fonts

    from core import ezdxf_patches

    ezdxf_patches.apply()
    face = None
    for name in ezdxf_patches.THAI_FONTS:
        if fonts.font_manager.has_font(name):
            face = name
            break
    if face is None:
        pytest.skip("no Thai font installed on this machine")
    renderer = UnifiedTextRenderer()
    arial = fonts.get_font_face("arial.ttf")
    thai = fonts.get_font_face(face)
    assert renderer.get_text_line_width("ดินตัด", arial) == pytest.approx(
        renderer.get_text_line_width("ดินตัด", thai))
    # Latin text keeps its own font
    assert renderer.get_text_line_width("STA. 0+100", arial) != pytest.approx(
        renderer.get_text_line_width("STA. 0+100", thai))
