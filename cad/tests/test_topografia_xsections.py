# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 WANICNSURVEY contributors.
"""XSECTIONS: the imported points of a corridor become cross sections every
N metres -- the centreline found in the points, the design level, the cut
and fill areas and volumes, the elevation grid in metres above MSL -- in
one undo step."""
from __future__ import annotations

import pytest

from core.commands import History
from core.document import Document
from plugins.topografia import actions, profile, xsections
from plugins.topografia.points import SurveyPoint
from plugins.topografia.tin import build_tin
from tools.base import ToolContext


def _corridor(z=lambda x, y: 100.0):
    """A 100 m corridor along x, 20 m wide, shot every 5 m."""
    return [(x * 5.0, y * 5.0 - 10.0, z(x * 5.0, y * 5.0 - 10.0))
            for x in range(21) for y in range(5)]


def test_the_centreline_follows_the_middle_of_the_points():
    axis = xsections.auto_axis([(x, y) for x, y, _z in _corridor()])
    assert axis[0][0] == pytest.approx(0.0, abs=1e-6)
    assert axis[-1][0] == pytest.approx(100.0, abs=1e-6)
    assert all(abs(y) < 1e-6 for _x, y in axis)
    assert xsections.half_width_of([(x, y) for x, y, _z in _corridor()], axis) == pytest.approx(10.0)


def test_stations_every_interval_and_the_end():
    axis = [(0.0, 0.0), (95.0, 0.0)]
    assert [round(st.s, 6) for st in xsections.station_list(axis, 20.0)] == [0, 20, 40, 60, 80, 95]


def test_flat_ground_one_metre_under_a_level_design_is_all_fill():
    tin = build_tin(_corridor())
    settings = xsections.Settings(interval=25.0, design=xsections.Design(xsections.LEVEL, 101.0),
                                  template=profile.Template(6.0, 1.0, 1.0))
    sections = xsections.run(tin, [(0.0, 0.0), (100.0, 0.0)], settings, 10.0)
    assert len(sections) == 5
    # 6 m platform + two 1:1 slopes over 1 m: (6 + 8) / 2 * 1 = 7 m²
    assert sections[2].fill_area == pytest.approx(7.0, abs=1e-6)
    assert sections[2].cut_area == pytest.approx(0.0, abs=1e-9)
    assert sections[-1].fill_total == pytest.approx(700.0, abs=1e-3)
    kinds = [k for k, _poly in xsections.regions(sections[2].ground, sections[2].design)]
    assert kinds == ["fill"]


def test_the_fitted_line_balances_a_side_slope():
    tin = build_tin(_corridor(lambda x, y: 100.0 + 0.1 * y))       # 10 % across
    settings = xsections.Settings(interval=50.0, template=profile.Template(6.0, 1.0, 1.0))
    sections = xsections.run(tin, [(0.0, 0.0), (100.0, 0.0)], settings, 10.0)
    sec = sections[1]
    assert sec.z_design == pytest.approx(100.0, abs=1e-6)
    assert sec.cut_area == pytest.approx(sec.fill_area, rel=1e-3)
    kinds = sorted(k for k, _poly in xsections.regions(sec.ground, sec.design))
    assert kinds == ["cut", "fill"]


class _Services:
    def __init__(self, document):
        self.document = document


def test_the_tool_runs_from_the_imported_points_headless():
    from plugins.topografia.tools import XSectionsTool

    document = Document.new()
    history = History(document)
    points = [SurveyPoint(str(i + 1), x, y, 100.0 + 0.05 * x) for i, (x, y, _z) in enumerate(_corridor())]
    history.execute(actions.import_points(document, points))
    echoed, done = [], []
    ctx = ToolContext(execute=history.execute, prompt=echoed.append, echo=echoed.append,
                      finish=lambda: done.append(True),
                      ask_text=lambda prompt, default="": "20",
                      undo_last=history.undo, services=_Services(document))
    tool = XSectionsTool(ctx)
    tool.start()
    tool.on_enter()                                   # beside the points
    assert done, echoed
    assert any("6 cross sections every 20 m" in line for line in echoed), echoed
    msp = document.doc.modelspace()
    texts = [e.dxf.text for e in msp if e.dxftype() == "TEXT"]
    assert "SECTION STA. 0+040.00" in texts
    assert "Elev. MSL (m)" in texts
    assert any(t == "+100.00" for t in texts)
    assert actions.surface_names(document) == ["TERRENO"]
    assert [e for e in msp if e.dxf.layer == "TOPO-EJE"]
    assert actions.contour_entities(document)
    count = len(list(msp))
    history.undo()                                    # one step takes it all back
    assert len(list(msp)) < count
    assert actions.surface_names(document) == []
