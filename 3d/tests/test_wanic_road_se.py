# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""Superelevation and widening (ทถ-2-104), the cut/fill summary to Excel,
the 3D model's coordinates and satellite fit, DRR-style leaders."""
import io
import math
import zipfile

import pytest

from core import wanic_drawings as D
from core import wanic_road as R
from core import wanic_road_sheets as RS
from core.road import alignment as A

E0, N0 = 446615.779, 936290.96


def _road():
    stakes = [R.PiStake("1", E0, N0, "POT"), R.PiStake("2", E0 + 180, N0 + 520, "PI", radius=120.0),
              R.PiStake("3", E0 + 60, N0 + 1080, "PI", radius=350.0), R.PiStake("4", E0 + 250, N0 + 1650, "POT")]
    al = R.alignment_from_pis(stakes, step=2.0)
    rows, num = ["P,E,N,Z,D"], 1
    for st in A.stations(al.axis, 25.0):
        for o in (-15, -10, -6, -3, 0, 3, 6, 10, 15):
            x, y = st.offset_point(o)
            z = 18.0 + 5.0 * math.sin(st.s / 190.0) + 0.04 * o
            rows.append(f"{num},{x:.3f},{y:.3f},{z:.3f},{'CL' if o == 0 else 'GR'}")
            num += 1
    rows.append(f"BM-1,{E0 - 18:.3f},{N0 - 12:.3f},19.800,BM")
    shots = R.parse_points("\n".join(rows))
    tin = R.build_tin(shots)
    return R.analyse(shots, al.axis, R.auto_pvis(tin, al.axis), R.Settings(), tin, al.curves), shots


def test_relative_gradient_and_the_plan():
    assert R.relative_gradient(60) == 165 and R.relative_gradient(100) == 200
    assert R.relative_gradient(55) == pytest.approx(157.5)
    an, _ = _road()
    c1, c2 = an.se_plan
    assert c1.e == 8.0 and c1.notes                          # R 120 under Rmin at 60 km/h
    assert 2.5 <= c2.e < 8.0 and c2.widening == 0.0
    assert c1.widening == pytest.approx(0.9)
    # runoff at 1 : 165 about the axis of a 6 m road, 2/3 on the tangent
    assert c1.runoff == pytest.approx(3.0 * 0.08 * 165)
    assert c1.s_lc == pytest.approx(c1.s_pc - 2 / 3 * c1.runoff)
    se = R.se_at(an.se_plan, (c1.s_fse + c1.s_fse_end) / 2, an.settings)
    inner, outer = (se[1], se[0]) if c1.right else (se[0], se[1])
    assert inner == pytest.approx(8.0) and outer == pytest.approx(-8.0)
    assert R.se_at(an.se_plan, c1.s_nc - 5, an.settings) is None
    sh_out = se[2] if c1.right else se[3]
    assert sh_out - outer <= R.ROLLOVER + 1e-9                     # roll over 0.07


def test_sections_at_the_key_points_superelevated():
    an, shots = _road()
    labels = [s.label for s in an.sections if s.label]
    assert any("FULL SE" in t for t in labels) and any(t.endswith("PC") for t in labels)
    full = next(s for s in an.sections if "FULL SE 8" in s.label)
    zl, zr = R.P._z_on(full.design, -3.0), R.P._z_on(full.design, 3.0)
    assert abs(zl - zr) == pytest.approx(6.0 * 0.08, abs=0.01)    # one plane across
    S = RS.build_road_set(an, {}, shots, ("ST", "SD"))
    se = [s for s in S if s.title.startswith("การยกโค้ง")]
    assert se and "1 : 165" in " ".join(se[0].texts())
    assert any("FULL SE" in t for s in S if s.group == "ST" for t in s.texts())


def test_earthworks_summary_and_excel():
    an, _ = _road()
    rows = R.earthworks_summary(an)
    assert rows[0][1] == pytest.approx(an.cut_total) and rows[1][1] == pytest.approx(an.fill_total)
    assert rows[2][1] == pytest.approx(abs(an.cut_total - an.fill_total))
    data = R.earthworks_xlsx(an, {"project": "ทดสอบ"})
    z = zipfile.ZipFile(io.BytesIO(data))
    assert "xl/worksheets/sheet2.xml" in z.namelist()
    assert "สรุปปริมาณงานดินขุด-ถม" in z.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "สรุป" in R.earthworks_csv(an)


def test_model_coordinates_and_the_satellite_fit():
    from core import wanic_sitemap as M
    an, shots = _road()
    marks = R.model_marks(an, shots)
    assert any(t.startswith("BM-1  N 936,278.960  E 446,597.779") for _p, t in marks)
    assert any(t.startswith("PC-1") for _p, t in marks) and any(t.startswith("STA 0+100.000") for _p, t in marks)
    x0, y0, x1, y1 = R.map_window(an)
    assert 50.0 <= R.map_margin(an) <= 100.0
    ox, oy, _ = an.origin
    ll = [R.utm_to_wgs84(x + ox, y + oy) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    view = M.fit_view(ll, x1 - x0, y1 - y0, max_px=4096, margin=0.0)
    fit = R.map_fit(an, view)
    for x, y in ((x0, y0), ((x0 + x1) / 2, (y0 + y1) / 2)):
        a, b, c, d, e, f = fit
        u, v = a * x + b * y + c, d * x + e * y + f
        assert R.uv_to_local(fit, u, v) == pytest.approx((x, y), abs=1e-6)
        assert -0.05 <= u <= 1.05 and -0.05 <= v <= 1.05


def test_drop_leaders_never_cross():
    sh = D.Sheet("T", "t")
    pts = [((100.0 - 6 * i, 200.0 - i), f"ชั้นที่ {i}") for i in range(5)]
    y = D.drop_leaders(sh, pts, 110.0, 180.0, 4.0, 1.8)
    assert y < 180.0 - 4 * 4.0
    rows = sorted(it[1][1] for it in sh.items if it[0] == "text")
    assert len(set(rows)) == 5


def test_points_order_in_southern_thailand():
    """N under 1,000,000 (Phang Nga): the header, or the 840,000 bound of an easting, tells."""
    a = R.parse_points("P,E,N,Z,D\n1,446000,936000,10,CL\n")[0]
    b = R.parse_points("1,446000,936000,10,CL\n")[0]
    c = R.parse_points("1,936000,446000,10,CL\n")[0]
    assert (a.e, a.n) == (b.e, b.n) == (c.e, c.n) == (446000.0, 936000.0)
    assert R.header_order(["Point", "Northing", "Easting", "Elev", "Code"]) == "PNEZD"


def test_a_surveyed_curve_is_drawn_as_its_true_arc_with_its_speed():
    """จ34: shots every 15 m on a 90° curve of R 50 — the axis becomes the
    arc (every point on the circle, 1 m apart), PC/PT on the new axis, and
    the entry speed V = √(127 R (e + f))."""
    import math
    from core.road import alignment as A
    pts = [(-100.0, 0.0), (-50.0, 0.0), (0.0, 0.0)]
    for k in range(1, 6):
        a = -math.pi / 2 + math.pi / 2 * k / 6
        pts.append((50 * math.cos(a), 50 + 50 * math.sin(a)))
    pts += [(50.0, 50.0), (50.0, 100.0), (50.0, 150.0)]
    axis, curves = R.smooth_axis(pts, A.horizontal_curves(pts))
    c = curves[0]
    assert abs(c.radius - 50) < 1e-6 and abs(c.s_pc - 100) < 1e-6
    assert abs((c.s_pt - c.s_pc) - c.length) < 0.01           # PC→PT is the arc
    on = [p for p in axis if p[0] > 1e-6 and p[1] < 50 - 1e-6]
    assert len(on) > 70 and max(abs(math.hypot(x, y - 50) - 50) for x, y in on) < 1e-6
    assert R.entry_speed(100, 6) == 50 and R.entry_speed(500, 6) == 100
    assert R.entry_speed(0, 6) == 0 and R.entry_speed(5000, 8) == 120


def _noisy_road(noise, seed=3):
    """A straight 150 m, a 70° left curve of R 80, a straight 160 m; the
    CL shots every 20 m off the line by up to ``noise`` m, side shots
    every 10 m to ±20 m."""
    import math
    import random
    from core.road import alignment as A
    rnd, d = random.Random(seed), math.radians(70)
    true = [(745900.0, 1454500.0), (746050.0, 1454500.0)]
    for k in range(1, 41):
        a = -math.pi / 2 + d * k / 40
        true.append((746050 + 80 * math.cos(a), 1454580 + 80 * math.sin(a)))
    true.append((true[-1][0] + 160 * math.cos(d), true[-1][1] + 160 * math.sin(d)))
    rows, num = [], 1
    for st in A.stations(true, 10.0):
        for o in range(-20, 21, 2):
            if o:
                x, y = st.offset_point(o)
                rows.append(f"{num},{x:.3f},{y:.3f},{95 + st.s / 100 + 0.03 * o:.3f},N")
                num += 1
    for k, st in enumerate(A.stations(true, 20.0)):
        if abs(st.s / 20 - round(st.s / 20)) < 1e-6:
            x, y = st.offset_point(rnd.uniform(-noise, noise))
            rows.append(f"C{k:03d},{x:.3f},{y:.3f},{95 + st.s / 100:.3f},CL")
    return true, R.parse_points("\n".join(rows))


def test_centre_fit_puts_the_cl_shots_on_the_line_to_be_built():
    """จ35 «ปรับค่ากึ่งกลาง»: tangents + the circle found from shots off
    by 0.3 m, every CL shot moved onto it (N E, and Z by the ground's
    slope), nearer the true line than before; the other shots untouched."""
    import math
    from core.road import alignment as A

    def off(line, e, n):
        st = A.point_at(line, A.station_of(line, (e, n)))
        return math.hypot(st.x - e, st.y - n)
    true, shots = _noisy_road(0.0)
    fit = R.fit_centreline(shots)
    assert [s.radius for s in fit.stakes if s.kind == "PI"] == [80.0] and fit.worst < 0.02
    true, shots = _noisy_road(0.3)
    fit = R.fit_centreline(shots)
    assert [s.radius for s in fit.stakes if s.kind == "PI"] == [80.0]
    new = R.apply_fit(shots, fit)
    cl = [k for k, s in enumerate(shots) if s.code == "CL"]
    assert len(fit.moves) == len(cl) and [m[5] for m in fit.moves] == sorted(m[5] for m in fit.moves)
    before = sum(off(true, shots[k].e, shots[k].n) for k in cl) / len(cl)
    after = sum(off(true, new[k].e, new[k].n) for k in cl) / len(cl)
    assert after < before * 0.7
    assert all(off(fit.axis, new[k].e, new[k].n) < 0.01 for k in cl)
    assert all(abs(new[k].z - shots[k].z) < 0.05 for k in cl)
    assert all(new[k] is shots[k] for k in range(len(shots)) if k not in cl)
    # one shot coded CL by mistake, 3 m off: flagged, and the line not steered by it
    shots.append(R.Shot("X1", 746060.0, 1454503.5, 95.6, "CL"))
    fit = R.fit_centreline(shots)
    assert [s.radius for s in fit.stakes if s.kind == "PI"] == [80.0]
    assert max(fit.moves, key=lambda m: m[4])[1] == "X1"


def test_the_centre_fit_button_and_undo(qtbot=None):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["WANIC_OFFLINE"] = "1"
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    from core.scene import Scene
    from plugins.wanic_road import RoadPanel
    from tests.test_wanic_buttons import _App
    _true, shots = _noisy_road(0.3)
    panel = RoadPanel(_App(Scene(), "wanic_road"))
    panel.shots = shots
    panel.axis = R.centerline_from_codes(shots)
    fit = panel.centre_fit(ask=False)
    assert fit and panel.undo_fit.isVisibleTo(panel)
    assert panel.shots is not shots and len(panel.axis) == len(fit.moves)
    panel.centre_undo()
    assert panel.shots is shots and not panel.undo_fit.isVisibleTo(panel)


def test_the_curve_tables_in_plain_words():
    """The owner: the G sheet tells anyone what each curve is."""
    from core import wanic_road_sheets as RS
    _true, shots = _noisy_road(0.0)
    cl = R.centerline_from_codes(shots)
    tin = R.build_tin(shots)
    an = R.analyse(shots, cl, R.auto_pvis(tin, cl), R.Settings(), tin)
    words = RS.plain_words(an)
    assert any("เลี้ยวซ้าย 70 องศา" in w and "รัศมี 80 ม." in w and "กม./ชม." in w for w in words)
    g = [s for s in RS.build_road_set(an, {}, shots) if s.code == "G-02"][0]
    t = g.texts()
    assert "อธิบายตารางให้เข้าใจง่าย" in t and "ความหมายของหัวตาราง" in t
