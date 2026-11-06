"""Pavement design: AI 1970 (asphalt) and Road Note 29 (concrete) against
the worked examples of the DOH manual and the DRR calculation sheet."""

import math

from core import wanic_pavement as V


def close(a, b, tol=0.01):
    return abs(a - b) <= tol * max(1.0, abs(b))


def test_ai1970_doh_manual_example():
    # คู่มือ กรมทางหลวง บทที่ 5: 4 ช่องจราจร IDT 11,014, รถหนัก 13.94 %, 25.5 ตัน,
    # r 6.5 %, 15 ปี, CBR 5 %, AC 8 / หินคลุก 20 / รองพื้นทาง 15 / คัดเลือก ก 20 ซม.
    inp = V.AIInput(idt=11014, heavy_pct=13.94, lanes=4, gross_t=25.5, growth_pct=6.5,
                    years=15, cbr=5,
                    layers=[["ผิวทางแอสฟัลต์คอนกรีต (AC)", 8], ["ชั้นพื้นทางหินคลุก", 20],
                            ["ชั้นรองพื้นทางวัสดุมวลรวม", 15], ["ชั้นวัสดุคัดเลือก ก", 20]])
    r = V.design_ai(inp)
    assert round(r.trucks) == 691
    assert close(r.factor, 1.209, 0.001)
    assert close(r.axle_lb, 22480.8, 0.001) and close(r.gross_lb, 56202, 0.001)
    # with the manual's DTN the TA checks are those of the manual
    assert close(V.ta_required(2174, 5), 29.94, 0.002)
    assert close(V.ta_required(2174, 10), 22.69, 0.002)
    assert close(V.ta_required(2174, 25), 15.73, 0.002)
    eq = [round(row[4], 2) for row in r.layers]
    assert eq == [8.0, 10.0, 5.56, 6.67]
    assert r.ok and len(r.checks) == 3                     # over subbase, selected, subgrade
    assert "Asphalt Institute" in V.ai_report(r, "ทดสอบ")
    small = V.design_ai(V.AIInput(idt=1500, heavy_pct=8, cbr=5, years=10))
    assert "ทถ-2-303" in V.ai_report(small)
    assert "นายเวนิช ธัมมะวงษ์" in V.ai_report(r)


def test_ai1970_auto_layers_cover_every_check():
    for idt, hv, cbr in ((300, 5, 3), (1158, 19, 3), (5000, 12, 6), (11014, 13.94, 12)):
        r = V.design_ai(V.AIInput(idt=idt, heavy_pct=hv, lanes=2, cbr=cbr, years=15))
        assert r.ok, (idt, hv, cbr, r.checks)
        assert all(t % 2.5 == 0 for _n, t, *_x in r.layers)
        names = [n for n, *_x in r.layers]
        assert ("ชั้นวัสดุคัดเลือก ก" in names) == (cbr < 10)
    assert V.design_lane_pct(2) == 50 and V.design_lane_pct(4) == 45 and V.design_lane_pct(6) == 40


def test_rn29_drr_sheet_values():
    # Equivalence factors as the DRR sheet interpolates them
    assert close(V.equivalence_factor(4), 0.0544, 0.002)
    assert close(V.equivalence_factor(11), 3.3467, 0.001)
    assert close(V.equivalence_factor(5), 0.1408, 0.002)
    assert close(V.equivalence_factor(10), 2.3198, 0.001)
    assert close(V.equivalence_factor(8.16), 1.0)
    # lane share: 2 lanes 4 m → 1, wider → 0.5, 4 lanes 0.45, 6 → 0.40
    assert V.lane_factor(2, 4.0) == 1.0 and V.lane_factor(2, 6.0) == 0.5
    assert V.lane_factor(4, 14) == 0.45 and V.lane_factor(6, 21) == 0.40
    # sub-base: CBR ≤ 2 → 15, 3–14 → 8, ≥ 15 → 0 (+8 for construction traffic)
    assert V.subbase_min_cm(2) == ("อ่อน", 15.0) and V.subbase_min_cm(4)[1] == 8.0
    assert V.subbase_min_cm(15)[1] == 0.0
    # As = 2,400 t L f / 2 fs: 20 cm, 10 m, wire mesh → 1.309 cm²/m (the sheet's example)
    assert close(V.steel_area(2400 * 0.20, 10.0, 1.5, 2750), 1.309, 0.001)


def test_rn29_design_and_chart():
    r = V.design_rn29(V.RNInput(adt=200, lanes=2, width=4.0, heavy_pct=2, growth_pct=4,
                                years=20, cbr=4))
    assert r.lane_factor == 1.0
    g = ((1.04 ** 20) - 1) / 0.04
    lt = 200 * 0.02 * 0.70
    assert close(r.cumulative[0][1], g * 365 * lt, 1e-6)
    assert r.slab_cm >= 15 and r.ok
    # the chart rises with the traffic; CBR ≥ 15 takes 25 mm off, ≤ 2 adds 25
    assert V.rn29_slab_mm(1.0, 5) < V.rn29_slab_mm(10.0, 5) < V.rn29_slab_mm(50.0, 5)
    assert close(V.rn29_slab_mm(4.0, 5), 200, 0.02)
    assert close(V.rn29_slab_mm(4.0, 20), V.rn29_slab_mm(4.0, 5) - 25, 1e-6)
    assert V.rn29_slab_mm(0.1, 5, reinforced=False) > V.rn29_slab_mm(0.1, 5)
    assert close(V.rn29_steel_kg(7.5), 3.41, 0.01)
    assert r.joints["dowel"].startswith("RB19")
    assert "Road Note 29" in V.rn29_report(r)
    layers = V.rn29_layers(r)
    assert layers[0][1] == r.slab_cm / 100


def test_drr_standard_tables():
    s = V.drr_rc_standard(800, 6, 1)
    assert s["slab"] == 0.20 and ("ชั้นวัสดุคัดเลือก ก", 0.10) in s["layers"]
    s = V.drr_rc_standard(4000, 8, 2)
    assert s["slab"] == 0.25 and s["sheet"] == "ทถ-2-201(2)"
    assert V.drr_rc_standard(5000, 8, 2) is None
    a = V.drr_ac_standard(1200, 5, 7)
    assert a["layers"][0][1] == 0.05 and a["cbr"] == 4
    d = V.drr_dbst_standard(300, 8)
    assert d["layers"][1] == ("ชั้นพื้นทางหินคลุก", 0.20)
    t = V.temperature_steel(18, 3.5)
    assert t["long"] == "RB9 @ 0.23 ม." and t["trans"] == "RB6 @ 0.15 ม."
    assert not math.isnan(V.ta_minimum(500))
