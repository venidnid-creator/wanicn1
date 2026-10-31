# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""The road design as A3 sheets: G, PP (plan and profile), ST, VT."""
from __future__ import annotations

import math
import re

from core import wanic_drawings as D
from core import wanic_road as R
from core import wanic_road_sheets as RS
from core.road import alignment as A

E0, N0 = 745900.0, 1454500.0


def _analysis(length=700):
    """A survey every 25 m, shots every 2 m to ±20 m, the axis bending,
    benchmarks at both ends; E,N in the first half and N,E in the second
    (two GNSS jobs joined)."""
    axis = [(E0 + 40.0 * math.sin(k / 250.0), N0 + k) for k in range(0, length + 1, 50)]
    rows, num = [], 1
    for st in A.stations(axis, 25.0):
        for o in range(-20, 21, 2):
            x, y = st.offset_point(o)
            z = 95.0 + 4.0 * math.sin(st.s / 180.0) + 0.04 * o
            code = "CL" if o == 0 else "N"
            rows.append(f"{num},{x:.3f},{y:.3f},{z:.3f},{code}" if st.s < length / 2
                        else f"{num},{y:.3f},{x:.3f},{z:.3f},{code}")
            num += 1
    rows.append(f"BM-1,{E0 - 15:.3f},{N0 + 5:.3f},94.500,BM")
    rows.append(f"BM-2,{E0 + 30:.3f},{N0 + length - 5:.3f},96.100,BM")
    shots = R.parse_points("\n".join(rows))
    ax = R.centerline_from_codes(shots)
    tin = R.build_tin(shots)
    an = R.analyse(shots, ax, R.auto_pvis(tin, ax), R.Settings(), tin)
    return an, shots


def test_two_jobs_joined_land_in_one_place():
    an, shots = _analysis()
    assert sum(s.swapped for s in shots) > 100
    assert all(abs(s.e - E0) < 200 and abs(s.n - N0) < 900 for s in shots)
    lat, lon = R.axis_centre_wgs84(an.axis)
    assert 13.1 < lat < 13.2 and 101.2 < lon < 101.3        # Chonburi, not off Vietnam


def test_the_set_like_a_road_study():
    an, shots = _analysis()
    S = RS.build_road_set(an, {"project": "ทางทดสอบ", "drawing_no": "RD-01"}, shots)
    codes = [s.code for s in S]
    assert codes[0] == "G-01" and "G-02" in codes
    pp = [s for s in S if s.group == "PP"]
    assert len(pp) == len(RS.chunks_of(an, 1000)) >= 2
    assert any(c.startswith("ST-") for c in codes) and any(c.startswith("VT-") for c in codes)
    assert [s.number for s in S] == list(range(1, len(S) + 1))
    for s in S:
        t = s.texts()
        assert s.code in t and f"/ {len(S)}" in t and "ทางทดสอบ" in t
        assert "(นายเวนิช ธัมมะวงษ์)" in t and "ออกแบบทาง" in t
        for it in s.items:
            pts = [it[1][:2], it[1][2:]] if it[0] == "line" else \
                it[1] if it[0] in ("poly", "fill") else []
            for x, y in pts:
                assert -1 <= x <= D.PAPER[0] + 1 and -1 <= y <= D.PAPER[1] + 1, s.code


def test_plan_and_profile_sheet_content():
    an, shots = _analysis()
    S = RS.build_road_set(an, {}, shots)
    pp = next(s for s in S if s.code == "PP-01")
    t = " ".join(pp.texts())
    for word in ("แปลน", "รูปตัดตามยาว", "ระดับดินเดิม", "ระดับออกแบบ", "ความสูงขุด",
                 "ความสูงถม", "แนวราบ", "แนวดิ่ง", "ผังสังเขป", "0+020", "N="):
        assert word in t, word
    assert re.search(r"[+-]\d+\.\d\d%", t)                       # grades
    assert "BM-1" in t                                           # benchmark in the plan
    assert pp.count("line", "grid") > 20                         # contours
    vc = [s for s in S if s.group == "PP" and "PVI" in " ".join(s.texts())]
    assert vc                                                    # vertical curve labels
    assert pp.scale.startswith("1:") and "V 1:" in pp.scale


def test_tables_sections_and_volumes():
    an, shots = _analysis()
    S = {s.code: s for s in RS.build_road_set(an, {}, shots)}
    g1 = " ".join(S["G-01"].texts())
    for word in ("ข้อมูลการออกแบบ", "ความยาวทาง", "ลาดดินตัด", "ปริมาณดินขุดรวม",
                 "BM-1", "13.1", "101.2"):
        assert word in g1, word
    g2 = " ".join(S["G-02"].texts())
    assert "ตารางองค์ประกอบโค้งราบ" in g2 and "ตารางโค้งดิ่ง" in g2 and "PVI STA" in g2
    st = S["ST-01"]
    t = " ".join(st.texts())
    assert "STA 0+000.00" in t and "พื้นที่ขุด" in t and "CT " in t and "CR " in t
    assert any(len(it) > 4 for it in st.items if it[0] == "fill")   # coloured cut/fill
    vt = [s for c, s in S.items() if c.startswith("VT-")]
    allt = " ".join(x for s in vt for x in s.texts())
    assert f"{an.cut_total:,.2f}" in allt and f"{an.fill_total:,.2f}" in allt
    assert "ปริมาณงานโครงสร้างทาง" in allt


def test_dxf_of_the_sheets():
    an, shots = _analysis(400)
    S = RS.build_road_set(an, {}, shots, ("G", "PP"))
    text = D.dxf_bytes(S).decode("cp874")
    assert "ANSI_874" in text and "แปลน" in text and text.rstrip().endswith("EOF")
