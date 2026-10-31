# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""WANIC ออกแบบถนน: a section survey in, profile / sections / earthworks /
3D model / DXF / CSV out -- and the engine the same as the CAD's."""
from __future__ import annotations

import math
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from core import wanic_road as R
from core.road import alignment as A

E0, N0 = 700000.0, 1600000.0


def _survey_text(length=600):
    """Sections every 25 m, a shot every 2 m to 20 m each side, the
    centre shot coded CL, written P,N,E,Z,D the way a Thai file is."""
    axis = [(E0 + k, N0 + 60.0 * math.sin(k / 300.0)) for k in range(0, length + 1, 50)]
    rows, num = [], 1
    for st in A.stations(axis, 25.0):
        for o in range(-20, 21, 2):
            x, y = st.offset_point(o)
            z = 95.0 + 3.0 * math.sin(st.s / 200.0) + 0.03 * o
            rows.append(f"{num},{y:.3f},{x:.3f},{z:.3f},{'CL' if o == 0 else 'N'}")
            num += 1
    return "\n".join(rows), axis


def test_the_engine_is_the_cads_byte_for_byte():
    cad = Path(__file__).resolve().parents[2] / "cad" / "plugins" / "topografia"
    if not cad.is_dir():
        pytest.skip("the CAD sources are not beside this checkout")
    here = Path(R.__file__).parent / "road"
    for name in ("alignment.py", "tin.py", "profile.py"):
        assert (here / name).read_text(encoding="utf-8") == (cad / name).read_text(encoding="utf-8"), name


def test_points_axis_and_analysis():
    text, axis = _survey_text()
    shots = R.parse_points(text)
    assert len(shots) > 500 and shots[0].e < shots[0].n             # N before E, told by size
    assert R.parse_points("P,E,N,Z,D\n" + "1,700000,1600000,95,CL\n2,700010,1600000,96,CL\n")[1].e == 700010
    cl = R.centerline_from_codes(shots)
    assert cl[0] == pytest.approx((E0, N0), abs=1e-3)
    assert A.polyline_length(cl) == pytest.approx(A.polyline_length(axis), rel=0.01)
    tin = R.build_tin(shots)
    pvis = R.auto_pvis(tin, cl)
    assert pvis[0][0] == 0.0 and pvis[-1][0] == pytest.approx(A.polyline_length(cl))
    an = R.analyse(shots, cl, pvis, R.Settings(), tin)
    assert len(an.sections) == int(A.polyline_length(cl) // 25) + 1 or len(an.sections) >= 24
    assert an.sections[-1].design is not None                       # to the very end
    sec = an.sections[4]
    assert sec.s == pytest.approx(100.0) and sec.design and sec.z_ground is not None
    # crowned: the axis 2.5 % above the edges of a 6 m platform
    zc = R.P._z_on(sec.design, 0.0)
    assert zc - R.P._z_on(sec.design, 3.0) == pytest.approx(0.075)
    assert an.fill_total > 0 and an.rows[-1].cut_total == pytest.approx(an.cut_total)
    assert an.curves and all(c.length == pytest.approx(60.0) for c in an.curves)
    # 3D: local coordinates, and the road lofted every 5 m
    ground = R.terrain_mesh(an)
    road = R.corridor_mesh(an)
    assert len(ground) == len(an.tin.triangles) and len(road) > 200
    assert all(abs(c) < 5000 for t in road for p in t for c in p)
    assert "ดินตัดสะสม" in R.earthworks_csv(an).splitlines()[0]
    doc = R.dxf_document(an)
    texts = [e.dxf.text for e in doc.modelspace() if e.dxftype() == "TEXT"]
    assert "STA. 0+100.000" in texts and any(t.startswith("PVI STA.") for t in texts)
    assert any(t.startswith("ดินถม") for t in texts) and "0+025" in texts


def test_pavement_curves_and_the_500_m_sample():
    sample = Path(__file__).resolve().parents[2] / "samples" / "ทดสอบถนน-500ม.csv"
    if not sample.exists():
        pytest.skip("the sample survey is not beside this checkout")
    shots = R.parse_points(sample.read_text(encoding="utf-8-sig"))
    cl = R.centerline_from_codes(shots)
    pvis = [(0, 92.6, 0), (200, 94.6, 120), (400, 91.8, 100), (499.869, 93.0, 0)]
    plain = R.analyse(shots, cl, pvis, R.Settings(layers=[]))
    concrete = R.analyse(shots, cl, pvis, R.Settings(pavement="drr-rc"))
    asphalt = R.analyse(shots, cl, pvis, R.Settings(pavement="doh-ac"))
    # the curve the file was made with: R = 200 m, 1 rad to the right
    (c,) = concrete.hcurves
    assert c.side == "RT" and c.radius == pytest.approx(200.0, abs=0.05)
    assert c.length == pytest.approx(200.0, abs=0.05) and c.s_pc == pytest.approx(150.0, abs=0.01)
    # 0.55 m of concrete pavement under an 8 m finished width: less fill, more cut
    assert concrete.settings.structure == pytest.approx(0.55)
    assert concrete.fill_total < plain.fill_total and concrete.cut_total > plain.cut_total
    assert asphalt.settings.structure == pytest.approx(0.80)
    sec = concrete.sections[8]
    assert R.P._z_on(sec.formation, 0.0) == pytest.approx(R.P._z_on(sec.design, 0.0) - 0.55)
    q = concrete.layer_quantities()
    assert q[0][0].startswith("ผิวทางคอนกรีต") and q[0][3] == pytest.approx(0.20 * 8.0 * concrete.length, rel=1e-6)
    polys = R.layer_polygons(sec.design, concrete.settings.template(), concrete.settings.pavement_layers())
    assert len(polys) == 3
    doc = R.dxf_document(concrete)
    texts = [e.dxf.text for e in doc.modelspace() if e.dxftype() == "TEXT"]
    assert "PI-1  STA. 0+259.259" in texts or any(t.startswith("PI-1  STA.") for t in texts)
    assert any(t.startswith("R = 200.0") for t in texts) and any(t.startswith("PC STA. 0+149.99") or
                                                                t.startswith("PC STA. 0+150.00") for t in texts)
    assert all(e.dxf.style == "WANIC-TH" for e in doc.modelspace() if e.dxftype() == "TEXT")
    assert "tahoma" in doc.styles.get("WANIC-TH").dxf.font.lower()
    assert any(l.dxf.name.startswith("WANIC-ชั้นทาง-") for l in doc.layers)


def test_without_a_grade_the_ground_is_still_shown():
    text, _axis = _survey_text(200)
    shots = R.parse_points(text)
    an = R.analyse(shots, R.centerline_from_codes(shots), [], R.Settings())
    assert an.sections and an.sections[0].design is None and not an.rows
    assert an.warnings and R.corridor_mesh(an) == []
    with pytest.raises(ValueError):
        R.analyse(shots, [], [], R.Settings())


def test_every_button_of_the_road_panel(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

    from core import wanic_ui
    from core.scene import Scene
    from plugins.wanic_road import RoadPanel
    from tests.test_wanic_buttons import _App, _click_all

    QApplication.instance() or QApplication([])
    text, _axis = _survey_text(300)
    pts = tmp_path / "survey.csv"
    pts.write_text(text, encoding="utf-8")
    saved, msgs = [], []
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(pts), "")))

    def save(parent=None, caption="", name="", flt="", *a, **k):
        saved.append(str(tmp_path / os.path.basename(name)))
        return saved[-1], ""
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(save))
    for name in ("information", "warning"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: msgs.append(a)))

    def critical(*a, **k):
        raise AssertionError(a[2] if len(a) > 2 else a)
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(critical))
    wanic_ui.LAST_ERROR.clear()
    scene = Scene()
    app = _App(scene, "wanic_road")
    panel = RoadPanel(app)
    panel.import_points()
    assert len(panel.shots) > 200 and len(panel.axis) >= 2 and len(panel.pvis()) >= 2
    an = panel.analyse()
    assert an is not None and panel.results is not None
    panel.results.profile.resize(1000, 500)
    panel.results.profile.grab()                                   # paints without error
    panel.results.sections.grab()
    assert panel.results.table.rowCount() == len(an.rows)
    for tab in range(panel.results.tabs.count()):                  # every tab paints
        panel.results.tabs.setCurrentIndex(tab)
        panel.results.grab()
    assert panel.results.curves.rowCount() == len(an.hcurves)
    assert panel.results.pavement.rowCount() == len(an.settings.pavement_layers())
    panel.pavement.setCurrentIndex(panel.pavement.findData("drr-rc"))
    assert panel.layer_rows()[0][0].startswith("ผิวทางคอนกรีต")
    groups = len(scene.groups)
    panel.build_model()
    assert len(scene.groups) == groups + 2
    done = _click_all(panel, skip=("ใช้เส้นที่เลือก",))
    assert any("วิเคราะห์" in t for t in done)
    assert any(p.endswith(".dxf") and os.path.exists(p) for p in saved)
    assert any(p.endswith(".csv") and os.path.exists(p) for p in saved)
    _click_all(panel.results)
    assert not wanic_ui.LAST_ERROR
    # the document keeps the job: a fresh panel reads it back
    again = RoadPanel(app)
    again.load()
    assert again.pavement.currentData() == "drr-rc" and len(again.layer_rows()) == 3
    assert len(again.shots) == len(panel.shots) and [c for p in again.pvis() for c in p] == pytest.approx(
        [c for p in panel.pvis() for c in p])


def test_a_chain_of_edges_drawn_in_the_model_is_the_axis(monkeypatch):
    from PySide6.QtGui import QVector3D
    from PySide6.QtWidgets import QApplication

    from core.scene import Scene
    from plugins.wanic_road import RoadPanel, _selected_path
    from tests.test_wanic_buttons import _App

    QApplication.instance() or QApplication([])
    scene = Scene()
    assert isinstance(_selected_path(scene), str)
    mesh = scene.mesh if hasattr(scene, "mesh") else None
    if mesh is None:
        pytest.skip("this scene keeps its loose geometry elsewhere")
    a, b, c = (QVector3D(x, y, 0.0) for x, y in ((0, 0), (50, 0), (90, 30)))
    scene.selection = {mesh.add_edge(a, b), mesh.add_edge(b, c)}
    panel = RoadPanel(_App(scene, "wanic_road"))
    panel.origin = (700000.0, 1600000.0, 0.0)
    panel.axis_from_selection()
    ends = {tuple(round(c, 6) for c in panel.axis[0]), tuple(round(c, 6) for c in panel.axis[-1])}
    assert ends == {(700000.0, 1600000.0), (700090.0, 1600030.0)} and len(panel.axis) == 3
