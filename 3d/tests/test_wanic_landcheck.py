# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""จ36 «ตรวจสอบพื้นที่ก่อสร้าง»: the parcels the road takes, from a parcel file."""
from __future__ import annotations

import os

from core import wanic_landcheck as LC
from core import wanic_road as R
from tests.test_wanic_road_se import _noisy_road


def _analysis():
    _t, shots = _noisy_road(0.0)
    fit = R.fit_centreline(shots)
    shots = R.apply_fit(shots, fit)
    tin = R.build_tin(shots)
    return R.analyse(shots, fit.axis, R.auto_pvis(tin, fit.axis), R.Settings(), tin, fit.curves)


def _grid(no_number_every=4):
    out, k = [], 0
    for i in range(745840, 746280, 55):
        for j in range(1454430, 1454780, 70):
            k += 1
            out.append(LC.Parcel(f"{2300 + k}" if k % no_number_every else "",
                                 [(i, j), (i + 55, j), (i + 55, j + 70), (i, j + 70)]))
    return out


def test_rai_ngan_wa_and_utm():
    assert LC.rai_ngan_wa(1600) == "1-0-0.0" and LC.rai_ngan_wa(2000) == "1-1-0.0"
    assert LC.rai_ngan_wa(1234.5) == "0-3-8.6"
    for datum in ("WGS84", "Indian1975"):
        lat, lon = R.utm_to_wgs84(745900, 1454500, 47, datum)
        e, n = LC.wgs84_to_utm(lat, lon, 47, datum)
        assert abs(e - 745900) < 0.01 and abs(n - 1454500) < 0.01


def test_the_road_takes_what_the_parcels_hold():
    an = _analysis()
    c = LC.check(an, _grid())
    # the grid covers the road: every m² of the footprint is in some parcel
    assert abs(c.total - c.footprint) < 0.5 and c.outside < 0.5
    assert len(c.taken) == 12 and len(c.known) == 9 and len(c.unknown) == 3
    assert [t.s0 for t in c.taken] == sorted(t.s0 for t in c.taken)
    # a 30 m right-of-way over 400 m: 12,000 m² (the curve's inside and outside even out)
    w = LC.check(an, _grid(), width=30)
    assert abs(w.footprint - 30 * an.length) < 5
    # a parcel the road misses is not listed
    far = LC.Parcel("9999", [(700000, 1400000), (700050, 1400000), (700050, 1400050)])
    assert all(t.parcel is not far for t in LC.check(an, _grid() + [far]).taken)


def test_parcel_files_kml_geojson_csv_dxf(tmp_path):
    ring = [(745900, 1454480), (745960, 1454480), (745960, 1454530), (745900, 1454530)]
    ll = [R.utm_to_wgs84(e, n, 47) for e, n in ring]
    coords = " ".join(f"{lon:.9f},{lat:.9f},0" for lat, lon in ll + ll[:1])
    kml = tmp_path / "p.kml"
    kml.write_text("<kml xmlns='http://www.opengis.net/kml/2.2'><Document><Placemark><name>1234</name>"
                   "<ExtendedData><Data name='ระวาง'><value>5137 II</value></Data></ExtendedData>"
                   f"<Polygon><outerBoundaryIs><LinearRing><coordinates>{coords}</coordinates>"
                   "</LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>", encoding="utf-8")
    p = LC.read_file(str(kml))[0]
    assert p.number == "1234" and "ระวาง" in p.note and abs(p.area - 3000) < 0.5
    gj = tmp_path / "p.geojson"
    import json
    gj.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"PARCEL_NO": "77"},
         "geometry": {"type": "Polygon", "coordinates": [[list(q) for q in ring + ring[:1]]]}}]}))
    p = LC.read_file(str(gj))[0]
    assert p.number == "77" and abs(p.area - 3000) < 1e-6
    cs = tmp_path / "p.csv"
    cs.write_text("แปลง,E,N,เลขที่ดิน\n" + "\n".join(f"A,{e},{n},55" for e, n in ring) +
                  "\n" + "\n".join(f"B,{e + 100},{n}," for e, n in ring), encoding="utf-8")
    ps = LC.read_file(str(cs))
    assert [q.number for q in ps] == ["55", ""] and abs(ps[1].area - 3000) < 1e-6
    import ezdxf
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline(ring, close=True)
    msp.add_text("เลขที่ดิน 4321", dxfattribs={"insert": (745930, 1454500)})
    dx = tmp_path / "p.dxf"
    doc.saveas(dx)
    p = LC.read_file(str(dx))[0]
    assert p.number == "4321" and abs(p.area - 3000) < 1e-6


def test_the_dialog_and_the_report(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("WANIC_OFFLINE", "1")
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    from core.scene import Scene
    from plugins.wanic_road import RoadPanel
    from tests.test_wanic_buttons import _App
    _t, shots = _noisy_road(0.0)
    panel = RoadPanel(_App(Scene(), "wanic_road"))
    panel.shots = shots
    panel.axis = R.centerline_from_codes(shots)
    panel.centre_fit(ask=False)
    import json
    gj = tmp_path / "parcels.geojson"
    gj.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"PARCEL_NO": p.number},
         "geometry": {"type": "Polygon", "coordinates": [[list(q) for q in p.ring + p.ring[:1]]]}}
        for p in _grid()]}))
    dlg = panel.land_check(str(gj))
    assert len(dlg.chk.taken) == 12 and "ไม่ทราบเลขที่ดิน 3 แปลง" in dlg.summary.text()
    assert dlg.table.item(3, 1).text() == "ไม่ทราบ"
    dlg.mode.setCurrentIndex(dlg.mode.findData(30.0))
    assert abs(dlg.chk.footprint - 30 * panel.analysis.length) < 5
    sh = dlg.sheet()
    t = " ".join(sh.texts())
    assert LC.PERMISSION in t and "ไม่ทราบเลขที่ดิน" in t and "คำอธิบายศัพท์" in t
    pdf = dlg.export_pdf(str(tmp_path / "r.pdf"))
    assert os.path.getsize(pdf) > 5000
    csv = dlg.export_csv(str(tmp_path / "r.csv"))
    assert "ไม่ทราบ" in open(csv, encoding="utf-8-sig").read()
