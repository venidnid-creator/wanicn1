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
    # 0.60 m of concrete pavement (with its 5 cm of sand) under an 8 m
    # finished width: less fill, more cut
    assert concrete.settings.structure == pytest.approx(0.60)
    assert [n for n, _t, _c in concrete.settings.pavement_layers()][1] == "ชั้นทรายรองพื้น"
    assert concrete.fill_total < plain.fill_total and concrete.cut_total > plain.cut_total
    assert asphalt.settings.structure == pytest.approx(0.80)
    sec = concrete.sections[8]
    assert R.P._z_on(sec.formation, 0.0) == pytest.approx(R.P._z_on(sec.design, 0.0) - 0.60)
    q = concrete.layer_quantities()
    assert q[0][0].startswith("ผิวทางคอนกรีต") and q[0][3] == pytest.approx(0.20 * 8.0 * concrete.length, rel=1e-6)
    polys = R.layer_polygons(sec.design, concrete.settings.template(), concrete.settings.pavement_layers())
    assert len(polys) == 4
    doc = R.dxf_document(concrete)
    texts = [e.dxf.text for e in doc.modelspace() if e.dxftype() == "TEXT"]
    assert "PI-1  STA. 0+259.259" in texts or any(t.startswith("PI-1  STA.") for t in texts)
    assert any(t.startswith("R = 200.0") for t in texts) and any(t.startswith("PC STA. 0+149.99") or
                                                                t.startswith("PC STA. 0+150.00") for t in texts)
    assert all(e.dxf.style == "WANIC-TH" for e in doc.modelspace() if e.dxftype() == "TEXT")
    assert "tahoma" in doc.styles.get("WANIC-TH").dxf.font.lower()
    assert any(l.dxf.name.startswith("WANIC-ชั้นทาง-") for l in doc.layers)


def test_utm_to_google_earth_and_the_place_name(monkeypatch):
    # zone 47 WGS84: the same as the 3D's own georeferencing
    from georef.datum import utm_forward, utm_inverse
    lat, lon = R.utm_to_wgs84(701250.0, 1612480.0, 47)
    assert (lat, lon) == pytest.approx(utm_inverse(701250.0, 1612480.0, 47, True), abs=1e-9)
    assert R.in_thailand(lat, lon)
    e, n = utm_forward(13.7563, 100.5018, 47)                       # Bangkok
    assert R.utm_to_wgs84(e, n, 47) == pytest.approx((13.7563, 100.5018), abs=1e-8)
    # the same grid numbers on Indian 1975 sit a few hundred metres away
    lat2, lon2 = R.utm_to_wgs84(e, n, 47, "Indian1975")
    shift = math.hypot((lat2 - 13.7563) * 110574, (lon2 - 100.5018) * 108100)
    assert 250 < shift < 600
    # zone 48 for the east of the country
    assert 102.0 < R.utm_to_wgs84(300000.0, 1800000.0, 48)[1] < 104.0
    # the KML: axis, road, stations, curves, points -- in lon,lat order
    text, _axis = _survey_text(300)
    shots = R.parse_points(text)
    cl = R.centerline_from_codes(shots)
    an = R.analyse(shots, cl, R.auto_pvis(R.build_tin(shots), cl), R.Settings())
    kml = R.kml_document(cl, an.settings, 47, "WGS84", an, shots, "ต.ทดสอบ อ.ทดสอบ จ.ทดสอบ")
    import xml.etree.ElementTree as ET
    root = ET.fromstring(kml.encode("utf-8"))
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    names = [e.text for e in root.iter("{http://www.opengis.net/kml/2.2}name")]
    assert "แนวศูนย์กลางทาง" in names and "ผิวทาง" in names and "0+100" in names
    first = root.find(".//k:LineString/k:coordinates", ns).text.split()[0].split(",")
    lat0, lon0 = R.utm_to_wgs84(cl[0][0], cl[0][1], 47)
    assert (float(first[1]), float(first[0])) == pytest.approx((lat0, lon0), abs=1e-7)
    assert "ต.ทดสอบ" in kml and "ระดับออกแบบ" in kml
    assert R.earth_web_url(14.5, 100.8).startswith("https://earth.google.com/web/@14.5000000,100.8000000")
    # จังหวัด อำเภอ ตำบล out of OpenStreetMap's answer
    place = R.parse_place({"display_name": "x", "address": {
        "suburb": "ตำบลหน้าพระลาน", "county": "อำเภอเฉลิมพระเกียรติ", "state": "จังหวัดสระบุรี"}})
    assert R.place_text(place) == "ต.หน้าพระลาน อ.เฉลิมพระเกียรติ จ.สระบุรี"


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
    monkeypatch.setenv("WANIC_OFFLINE", "1")           # no browser, no Google Earth, no network
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
    assert panel.layer_rows()[1][0] == "ชั้นทรายรองพื้น"
    # the thickness is typed in its own box; a layer goes in under the selected one
    panel.layers.cellWidget(1, 1).setValue(0.07)
    panel.layers.setCurrentCell(2, 0)
    panel.add_layer()
    assert len(panel.layer_rows()) == 5 and panel.layer_rows()[3][0] == "ชั้นทรายรองพื้น"
    assert "หนา 0.670 ม." in panel.structure.text()
    groups = len(scene.groups)
    panel.build_model()
    assert len(scene.groups) == groups + 2
    from PySide6.QtWidgets import QDialog

    from plugins.wanic_road import RoadSheetsDialog
    monkeypatch.setattr(RoadSheetsDialog, "exec", lambda self: QDialog.Accepted)
    done = _click_all(panel, skip=("ใช้เส้นที่เลือก",))
    assert any("วิเคราะห์" in t for t in done)
    pdf = [p for p in saved if p.endswith(".pdf")]
    assert pdf and open(pdf[-1], "rb").read(5) == b"%PDF-"          # the A3 sheet set
    assert os.path.exists(pdf[-1][:-4] + "_แผ่นแบบ.dxf")
    assert any(p.endswith(".dxf") and os.path.exists(p) for p in saved)
    assert any(p.endswith(".csv") and os.path.exists(p) for p in saved)
    _click_all(panel.results)
    assert not wanic_ui.LAST_ERROR
    assert any(p.endswith(".kml") and os.path.exists(p) for p in saved)
    assert "ละติจูด" in panel.place.text()
    # the place: asked in the background, written in the panel and the document
    monkeypatch.delenv("WANIC_OFFLINE")
    monkeypatch.setattr(R, "reverse_geocode", lambda lat, lon: {
        "province": "สระบุรี", "district": "เฉลิมพระเกียรติ", "subdistrict": "หน้าพระลาน"})
    panel.find_place()
    import time
    for _ in range(50):
        QApplication.processEvents()
        if panel._place:
            break
        time.sleep(0.05)
    assert panel._place == "ต.หน้าพระลาน อ.เฉลิมพระเกียรติ จ.สระบุรี" and "จ.สระบุรี" in panel.place.text()
    assert panel.open_earth_web().startswith("https://earth.google.com/web/@")
    # the document keeps the job: a fresh panel reads it back
    again = RoadPanel(app)
    again.load()
    assert again.pavement.currentData() == "drr-rc" and len(again.layer_rows()) == 5
    assert again.layer_rows()[1][:2] == ("ชั้นทรายรองพื้น", pytest.approx(0.07))
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


def test_cl_code_may_lead_a_longer_description():
    """Field books write ``CL STA 0+020`` / ``CL PC STA 0+220``: the first
    word is the code."""
    from core import wanic_road as R
    for d in ("CL", "cl", "CL12", "CL-3", "CL STA 0+020", "CL PC STA 0+220",
              "ศก STA 0+000", "C/L 5"):
        assert R.is_cl(d), d
    for d in ("CLOSE", "EP-L STA 0+000", "TOE-R", "", "STA CL"):
        assert not R.is_cl(d), d
    text = ("Point,N,E,Z_MSL,Description\n"
            "BM-1,873810.247,424867.877,18.050,หมุดหลักฐาน BM-1\n"
            "1,873805.658,424874.431,17.860,TOE-L STA 0+000\n"
            "5,873801.643,424880.165,18.400,CL STA 0+000\n"
            "14,873818.026,424891.637,19.300,CL STA 0+020\n"
            "23,873834.409,424903.109,20.200,CL STA 0+040\n")
    shots = R.parse_points(text)
    axis = R.centerline_from_codes(shots)
    assert len(axis) == 3


def test_rows_written_n_e_in_an_e_n_file_are_turned_round():
    """A GNSS/RTK export joining two jobs: part E,N and part N,E. The N,E
    rows used to land 700 km away (Google Earth showed the wrong place)."""
    rows = ["9,745911.488,1454500.84,95.615,N",
            "15,745895.682,1454520.734,94.873,CL",
            "18,745884.444,1454543.05,94.085,CL",
            "21,745873.171,1454565.269,93.445,CL"]
    rows += [f"{i},{1454498.7468 + 20 * i},{745906.9425 - 9 * i},95.6,N"
             for i in range(3, 12)]
    shots = R.parse_points("\n".join(rows))
    assert sum(s.swapped for s in shots) == 9
    assert all(744000 < s.e < 747000 and 1454000 < s.n < 1457000
               for s in shots)
    # nothing to turn in a clean file
    clean = R.parse_points("\n".join(rows[:4]))
    assert not any(s.swapped for s in clean)
    assert R.duplicate_names(R.parse_points("1,10,10,1,N\n1,12,11,1,N\n"
                                            "2,14,12,1,N")) == ["1"]
