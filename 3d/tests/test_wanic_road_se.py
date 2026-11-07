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
