import math
import os

import pytest

from conftest import ROOT
from wanicndesign.structure.analysis import continuous_beam
from wanicndesign.structure.building import Building, Foundation, Level
from wanicndesign.structure.design import _column_design, _pick_c, design, design_slab
from wanicndesign.structure.materials import Concrete

BUILDING = os.path.join(ROOT, "examples", "building_2storey.json")


def test_two_equal_spans_textbook():
    spans, reac = continuous_beam([4.0, 4.0], [1000.0, 1000.0])
    assert spans[0].m_right == pytest.approx(-1000 * 16 / 8)          # −wL²/8 at the middle support
    assert reac == pytest.approx([1500.0, 5000.0, 1500.0])           # 3/8, 10/8, 3/8 wL
    assert spans[0].m_pos == pytest.approx(9 / 128 * 1000 * 16, rel=1e-6)


def test_single_span_is_simply_supported():
    spans, reac = continuous_beam([5.0], [800.0])
    assert spans[0].m_pos == pytest.approx(800 * 25 / 8)
    assert reac == pytest.approx([2000.0, 2000.0])


def test_purlin_reproduces_manual_example():
    # QuickDesign purlin sheet: W 100 kg/m², spacing 1.00, span 6.00, 15°:
    # Mx 434.67, My 116.47, Sx 31.05, Sy 8.32 → C150x50x20x3.2 (Zx 37.4, Zy 8.19 → NO.K on Sy)
    w = 100.0
    th = math.radians(15)
    m = _pick_c(w * math.cos(th) * 36 / 8, w * math.sin(th) * 36 / 8, "แป", 6.0)
    assert m.mx == pytest.approx(434.67, abs=0.01)
    assert m.my == pytest.approx(116.47, abs=0.01)
    assert m.sx_req == pytest.approx(31.05, abs=0.01)
    assert m.sy_req == pytest.approx(8.32, abs=0.01)
    assert m.zx >= 31.05 and m.zy >= 8.32


def test_wsd_constants():
    c = Concrete(fc_prime=173.33, main_grade="SD30")
    # manual Requirement form: fc' 173.33, SD30 1500 → n 9, k 0.320, j 0.893
    assert c.n in (9, 10)
    assert Concrete(fc_prime=210).fc == pytest.approx(94.5)


def test_two_way_slab_case5():
    b = Building("t", grid_x=[4.0], grid_y=[4.0], levels=[Level("FL2", 3.0)])
    s = design_slab(b, Concrete(), b.levels[0], 0, 0)
    W = 2400 * 0.10 + 50 + 200                    # house live load 200 [MR2566-11]
    assert s.kind == "two-way"
    assert s.m_pos == pytest.approx(0.050 * W * 16)
    assert s.ok


def test_column_formula_and_minimum_steel():
    c = Concrete(fc_prime=210)
    bw, h, pg, bars, ties, ok, _ = _column_design(c, 20000, 0.20, 0.20)
    assert pg == pytest.approx(0.01) and bars == "4-DB12" and ok
    # heavy load: pg would pass 4%, the section grows
    bw, h, pg, bars, ties, ok, note = _column_design(c, 120000, 0.20, 0.20)
    assert bw > 0.20 and pg <= 0.04 and ok


def test_chain_runs_and_loads_flow_down():
    res = design(Building.load(BUILDING))
    assert res.ok, res.warnings
    by_node = {}
    for col in res.columns:
        by_node.setdefault(col.node, []).append(col)
    for segs in by_node.values():
        loads = [c.load for c in segs]               # bottom segment first
        assert loads == sorted(loads, reverse=True)  # load grows going down
    total_col = sum(f.load for f in res.footings)
    assert total_col > 100000                         # two storeys + roof, > 100 t
    for f in res.footings:
        assert f.piles * f.pile_capacity >= f.load    # piles carry the column load


def test_heavy_building_upsizes_piles():
    b = Building.load(BUILDING)
    b.foundation = Foundation(pile="I18")
    res = design(b)
    assert any(f.pile != "I18" or f.piles > 1 for f in res.footings)


def test_removing_a_beam_opens_its_panels():
    b = Building.load(BUILDING)
    full = design(b)
    assert b.toggle("beam", "FL2:2A-2B") is False      # removed
    assert (0, 0) not in b.panels("FL2") and (1, 0) not in b.panels("FL2")
    assert (0, 0) in b.panels("ROOF")                  # other levels untouched
    res = design(b)
    assert len([s for s in res.slabs if s.level == "FL2"]) == \
        len([s for s in full.slabs if s.level == "FL2"]) - 2
    assert not any(x.level == "FL2" and x.span == "2A-2B" for x in res.beams)
    assert b.toggle("beam", "FL2:2A-2B") is True       # restored


def test_removing_a_column_and_a_panel():
    b = Building.load(BUILDING)
    b.toggle("node", "4C")
    b.toggle("panel", "FL2:1-2/A-B")
    res = design(b)
    assert not any(c.node == "4C" for c in res.columns)
    assert not any(s.panel == "1-2/A-B" and s.level == "FL2" for s in res.slabs)
    assert res.ok, res.warnings


def test_slab_case_follows_continuity():
    # 3 × 3 bays of 4 m: corner panel has 2 free edges (case 3), edge panel
    # 1 (case 2), the middle panel none (case 1).
    b = Building("t", grid_x=[4.0] * 3, grid_y=[4.0] * 3, levels=[Level("FL2", 3.0)])
    c = Concrete()
    W = 2400 * 0.10 + 50 + 200                    # house live load 200 [MR2566-11]
    corner = design_slab(b, c, b.levels[0], 0, 0)
    edge = design_slab(b, c, b.levels[0], 1, 0)
    middle = design_slab(b, c, b.levels[0], 1, 1)
    assert (corner.case, edge.case, middle.case) == (3, 2, 1)
    assert middle.m_pos == pytest.approx(0.025 * W * 16)
    assert edge.m_neg == pytest.approx(0.041 * W * 16)
    assert "EIT1007-SLAB" in middle.refs


def test_mr6_criteria_are_more_conservative():
    eit = Concrete(fc_prime=210, code="EIT1007")
    mr6 = Concrete(fc_prime=210, code="MR6")
    assert mr6.fc == pytest.approx(65.0)          # 0.375 × 210 = 78.75 → capped at 65
    assert mr6.fs("DB") == 1500 and eit.fs("DB") == 1700
    assert mr6.R(mr6.fs("DB")) < eit.R(eit.fs("DB"))


def test_live_load_reduction_lowers_column_loads():
    # กฎกระทรวง พ.ศ. 2566 ข้อ 13: FL4 is the 1st floor below the roof (0 %),
    # FL3 the 2nd (0 %), FL2 the 3rd (10 %). A two-storey house gets no reduction.
    b = Building.load(BUILDING)
    fl = b.levels[1]
    b.levels = [b.levels[0]] + [Level(f"FL{k}", 3.2 * (k - 1), "suspended", fl.slab_thickness,
                                      fl.live_load, fl.finish_load, fl.beam_width, 0.45, "B", "perimeter")
                                for k in (2, 3, 4)] + [b.levels[2]]
    b.levels[-1].elevation = 12.6
    b.ll_reduction = False
    plain = {(c.node, c.segment): c.load for c in design(b).columns}
    b.ll_reduction = True
    reduced = design(b).columns
    below_fl2 = [c for c in reduced if c.segment == "GB–FL2"]
    assert below_fl2 and all(c.live_reduced > 0 for c in below_fl2)
    assert all(c.load < plain[(c.node, c.segment)] for c in below_fl2)
    assert all("MR2566-13" in c.refs for c in below_fl2)
    for seg in ("FL4–ROOF", "FL3–FL4", "FL2–FL3"):            # nothing reduced above FL2
        assert all(c.live_reduced == 0 for c in reduced if c.segment == seg)
    # the reduction taken below FL2 is 10 % of FL2's live load reactions
    from wanicndesign.structure.design import design_level_beams, design_roof
    _bm, _r, live = design_level_beams(b, Concrete(), 1, design_roof(b))
    for c in below_fl2:
        assert c.live_reduced == pytest.approx(0.10 * live[b.parse_node(c.node)], rel=1e-6)
    b.design_code = "MR6"                         # transitional clause: the repealed table, FL3 gets 10 %
    old = design(b).columns
    assert all(c.live_reduced > 0 for c in old if c.segment == "FL2–FL3")
    b.occupancy = "industrial"                    # no reduction for warehouses/factories
    assert all(c.live_reduced == 0 for c in design(b).columns)


def test_two_storey_house_gets_no_reduction():
    res = design(Building.load(BUILDING))
    assert all(c.live_reduced == 0 for c in res.columns)


def test_every_result_has_references():
    res = design(Building.load(BUILDING))
    for group in (res.slabs, res.beams, res.columns, res.footings):
        assert all(x.refs for x in group)
    from wanicndesign.standards import REFS
    assert set(res.all_refs()) <= set(REFS)


def test_report_lists_standards(tmp_path):
    import openpyxl
    from wanicndesign.structure.report import write_report
    out = tmp_path / "calc.xlsx"
    write_report(design(Building.load(BUILDING)), str(out))
    wb = openpyxl.load_workbook(out)
    refs = wb["มาตรฐานและที่มา"]
    codes = [r[0] for r in refs.iter_rows(min_row=2, values_only=True)]
    assert "EIT1007-COL" in codes and "MR2566-11" in codes and "MR6-15" not in codes
    assert [c.value for c in wb["คาน"][1]][-1] == "อ้างอิง"


def test_point_load_simple_and_fixed_textbook():
    # simple span, central point load: M = PL/4, reactions P/2
    spans, reac = continuous_beam([4.0], [0.0], [[(2.0, 1000.0)]])
    assert spans[0].m_pos == pytest.approx(1000 * 4 / 4)
    assert reac == pytest.approx([500.0, 500.0])
    # two equal spans, central point load on each: middle support −3PL/16, R = 11P/16 + 11P/16
    spans, reac = continuous_beam([4.0, 4.0], [0.0, 0.0], [[(2.0, 1000.0)], [(2.0, 1000.0)]])
    assert spans[0].m_right == pytest.approx(-3 * 1000 * 4 / 16)
    assert reac[1] == pytest.approx(2 * 11 * 1000 / 16)


def test_partial_udl_equals_its_total():
    from wanicndesign.structure.analysis import partial_udl
    pts = partial_udl(500.0, 1.0, 3.0)
    assert sum(P for _a, P in pts) == pytest.approx(1000.0)
    spans, reac = continuous_beam([4.0], [0.0], [pts])
    assert reac == pytest.approx([500.0, 500.0])           # symmetric
    assert spans[0].m_pos == pytest.approx(500 * 2 * (4 / 4 - 2 / 8), rel=0.01)   # w·c·(L/4 − c/8)


def _one_bay(sub=None, cant=None):
    fl = Level("FL2", 3.0, "suspended", 0.10, 200, 50, 0.20, 0.40, "B", "none")
    roof = Level("ROOF", 6.0, "none", 0.0, 0, 0, 0.20, 0.40, "RB", "none")
    b = Building("t", grid_x=[4.0], grid_y=[4.0], levels=[fl, roof])
    if sub:
        b.toggle_sub_beam(fl, 0, 0, sub)
    if cant:
        b.toggle_cantilever(fl, (0, 0), (1, 0), cant)
    return b


def test_secondary_beam_hand_check():
    from wanicndesign.structure.design import design_level_beams
    b = _one_bay(sub="x")
    W = 2400 * 0.10 + 50 + 200                      # 490 kg/m²
    res = design(b)
    sb = next(x for x in res.beams if x.kind == "secondary")
    # two 4 × 2 m pieces; each sends a trapezoid (q = W·S/2, ramps a = S/2) to
    # the secondary beam: M = q(3L² − 4a²)/24 per piece, plus self weight wL²/8
    q, a, L = W * 2 / 2, 1.0, 4.0
    m_hand = 2 * q * (3 * L * L - 4 * a * a) / 24 + 2400 * 0.20 * 0.40 * L * L / 8
    assert sb.length == 4.0 and sb.m_pos == pytest.approx(m_hand, rel=0.005)
    assert sb.mark.endswith("S1")
    pieces = [s for s in res.slabs if s.level == "FL2"]
    assert len(pieces) == 2 and all(s.lx == 4.0 and s.ly == 2.0 for s in pieces)
    # the edge beams parallel to Y carry the secondary beam's reaction at mid-span
    y_beam = next(x for x in res.beams if x.span == "1A-1B" and x.level == "FL2")
    assert "แรงจุด" in y_beam.note
    # equilibrium: the four columns carry the whole floor
    _beams, reac, _live = design_level_beams(b, Concrete(), 0, None)
    total = W * 16 + 2400 * 0.20 * 0.40 * (4 * 4 + 4)
    assert sum(reac.values()) == pytest.approx(total, rel=1e-6)


def test_cantilever_slab_hand_check():
    from wanicndesign.structure.design import design_level_beams
    b = _one_bay(cant=1.5)
    W = 2400 * 0.10 + 50 + 200                    # house live load 200 [MR2566-11]
    res = design(b)
    cs = next(s for s in res.slabs if s.kind == "cantilever")
    assert cs.m_neg == pytest.approx(W * 1.5 ** 2 / 2)
    assert cs.mark == "CS1" and "STATICS" in cs.refs
    assert cs.rect == pytest.approx((0.0, -1.5, 4.0, 0.0))   # outside the A edge
    _beams, reac, _live = design_level_beams(b, Concrete(), 0, None)
    total = W * 16 + W * 1.5 * 4 + 2400 * 0.20 * 0.40 * 16
    assert sum(reac.values()) == pytest.approx(total, rel=1e-6)


def test_cantilever_too_long_for_thickness():
    b = _one_bay(cant=1.8)                         # L/10 = 0.18 > 0.10
    cs = next(s for s in design(b).slabs if s.kind == "cantilever")
    assert not cs.ok and "ความหนา" in cs.note


def test_tributary_loads_conserve_the_slab_load():
    from wanicndesign.structure.design import _tributary
    for sx, sy in ((4.0, 4.0), (4.0, 3.0), (6.0, 2.5), (5.0, 2.0)):
        px, py = _tributary(440.0, sx, sy)
        total = 2 * sum(P for _a, P in px) + 2 * sum(P for _a, P in py)
        assert total == pytest.approx(440.0 * sx * sy, rel=1e-9)


def test_floor_equilibrium_whole_building():
    from wanicndesign.structure.design import design_level_beams, design_roof
    b = Building.load(BUILDING)
    li = 1                                           # FL2
    lv = b.levels[li]
    _beams, reac, _live = design_level_beams(b, Concrete(), li, design_roof(b))
    W = 2400 * lv.slab_thickness + lv.finish_load + lv.live_load
    area = b.xs[-1] * b.ys[-1]
    beam_len = sum(abs(b.xs[c[0]] - b.xs[a[0]]) + abs(b.ys[c[1]] - b.ys[a[1]])
                   for _d, run in b.beam_lines(lv.name) for a, c in zip(run, run[1:]))
    above = b.levels[li + 1]
    wall_h = above.elevation - lv.elevation - above.beam_depth
    perim = 2 * (b.xs[-1] + b.ys[-1])
    total = W * area + 2400 * lv.beam_width * lv.beam_depth * beam_len + 180 * wall_h * perim
    assert sum(reac.values()) == pytest.approx(total, rel=1e-6)


# ---------------------------------------------------------------------------
# Earthquake — มยผ. 1301/1302-61 (ASCE 7-05 basis), hand checks
# ---------------------------------------------------------------------------

def test_site_coefficients_and_design_category():
    from wanicndesign.structure.seismic import design_category, site_coefficients
    fa, fv = site_coefficients(0.30, 0.10, "C")
    assert (fa, fv) == pytest.approx((1.2, 1.7))
    fa, fv = site_coefficients(0.625, 0.15, "D")          # midway between table columns
    assert fa == pytest.approx(1.3) and fv == pytest.approx(2.2)
    assert design_category(0.10, 0.05, "II") == "A"
    assert design_category(0.24, 0.113, "II") == "B"
    assert design_category(0.24, 0.113, "IV") == "C"
    assert design_category(0.40, 0.10, "II") == "C"
    assert design_category(0.20, 0.25, "II") == "D"


def test_plane_frame_against_closed_form():
    from wanicndesign.structure.frame2d import Member, solve_frame
    E, I, h, P = 2.0e9, 1e-4, 3.0, 1000.0
    # cantilever column: δ = P h³ / 3EI
    disp, f = solve_frame([(0, 0), (0, h)], [Member(0, 1, E, 1.0, I)], {0}, {1: (P, 0, 0)})
    assert disp[1][0] == pytest.approx(P * h ** 3 / (3 * E * I), rel=1e-6)
    assert abs(f[0][2]) == pytest.approx(P * h, rel=1e-6)                  # base moment
    # portal with a very stiff beam: δ = P h³ / 24EI, each column takes P/2
    nodes = [(0, 0), (0, h), (4, h), (4, 0)]
    mem = [Member(0, 1, E, 1.0, I), Member(1, 2, E, 1.0, I * 1e6), Member(3, 2, E, 1.0, I)]
    disp, f = solve_frame(nodes, mem, {0, 3}, {1: (P, 0, 0)})
    assert disp[1][0] == pytest.approx(P * h ** 3 / (24 * E * I), rel=1e-3)
    assert abs(f[0][1]) == pytest.approx(P / 2, rel=1e-3)


def test_column_interaction_points():
    from wanicndesign.structure.seismic import column_bars, phi_mn_at, phi_mn_beam, pm_curve
    fc, fy = 210.0, 4000.0
    bars = column_bars(4, "DB16", 30.0, 30.0)
    ast = sum(a for _y, a in bars)
    curve = pm_curve(30.0, 30.0, bars, fc, fy)
    p0 = 0.80 * 0.70 * (0.85 * fc * (900 - ast) + fy * ast)             # φ tied 0.70 [MR2566-8]
    assert curve[1] == pytest.approx(p0)
    assert phi_mn_at(curve, p0 * 1.01) == 0.0
    # pure bending: about the beam value of the tension bars (compression bars add a little)
    d = 30.0 - (4.0 + 0.6 + 0.8)
    m_beam = phi_mn_beam(ast / 2, 30.0, d, fc, fy)
    assert m_beam * 0.98 <= phi_mn_at(curve, 0.0) <= m_beam * 1.12
    # a moderate axial load raises the moment capacity (below the balance point)
    assert phi_mn_at(curve, 20000.0) > phi_mn_at(curve, 0.0)


def _quake_building():
    b = Building.load(BUILDING)
    b.seismic.enabled = True
    b.seismic.ss, b.seismic.s1, b.seismic.site_class = 0.30, 0.10, "C"
    return b


def test_equivalent_static_forces():
    res = design(_quake_building())
    q = res.seismic
    assert q.sds == pytest.approx(2 / 3 * 1.2 * 0.30)
    assert q.sd1 == pytest.approx(2 / 3 * 1.7 * 0.10)
    assert q.category == "B"
    assert q.period == pytest.approx(0.02 * 6.2)
    assert q.cs == pytest.approx(q.sds * 1.0 / 5.0)                       # Sa = SDS, I = 1, R = 5
    assert q.base_shear == pytest.approx(q.cs * q.weight)
    assert sum(s.fx for s in q.storeys) == pytest.approx(q.base_shear)
    wh = [s.wx * s.hx for s in q.storeys]                                  # k = 1
    for s, x in zip(q.storeys, wh):
        assert s.fx == pytest.approx(q.base_shear * x / sum(wh))
    assert q.storeys[0].vx == pytest.approx(q.base_shear)
    assert "DPT1301" in res.all_refs() and "MR-EQ2564" in res.all_refs()
    assert any(c.kind == "footing" for c in q.checks) and any(c.kind == "beam" for c in q.checks)


def test_seismic_weight_is_the_dead_load_above_the_base():
    b = _quake_building()
    res = design(b)
    dead_cols = sum(2400 * c.b * c.h * c.height for c in res.columns if not c.segment.startswith("ฐานราก"))
    # beams' dead reactions at FL2 and ROOF plus all columns above GB; half of the GB–FL2 columns
    # belong to GB (the base), so W lies between these bounds
    assert res.seismic.weight > 0
    w_gb_half = sum(2400 * c.b * c.h * c.height / 2 for c in res.columns if c.segment.startswith("GB"))
    assert res.seismic.weight + w_gb_half > dead_cols


def test_strong_shaking_adds_steel_or_fails_clearly():
    b = _quake_building()
    b.seismic.mode, b.seismic.sds, b.seismic.sd1 = "direct", 0.49, 0.19     # category C, IMF allowed
    b.seismic.category = "III"                                                # Δa = 0.015 h
    res = design(b)
    q = res.seismic
    assert q.category == "C"
    assert not any(w.startswith("NG") for w in q.warnings)
    changed = [c for c in res.columns if "แผ่นดินไหว" in c.note] + \
              [x for x in res.beams if "แผ่นดินไหว" in x.note]
    assert changed                               # something was strengthened
    assert all(c.ratio <= 1.0 for c in q.checks if c.ok)
    assert all(max(s.drift_x, s.drift_y) <= s.limit for s in q.storeys)    # columns grew for drift
    assert any("การเคลื่อนตัว" in c.note for c in res.columns)


def test_category_d_needs_a_special_frame():
    b = _quake_building()
    b.seismic.mode, b.seismic.sds, b.seismic.sd1 = "direct", 0.60, 0.30
    res = design(b)
    assert res.seismic.category == "D" and not res.seismic.ok and not res.ok


def test_seismic_off_by_default_and_round_trip(tmp_path):
    b = Building.load(BUILDING)
    assert design(b).seismic is None
    b2 = _quake_building()
    p = tmp_path / "b.json"
    b2.save(str(p))
    assert Building.load(str(p)).seismic.ss == pytest.approx(0.30)


def test_seismic_report_sheets(tmp_path):
    from openpyxl import load_workbook
    from wanicndesign.structure.report import write_report
    res = design(_quake_building())
    p = tmp_path / "r.xlsx"
    write_report(res, str(p))
    names = load_workbook(p).sheetnames
    assert {"แผ่นดินไหว", "แผ่นดินไหว-ชั้น", "แผ่นดินไหว-ชิ้นส่วน"} <= set(names)


# ---------------------------------------------------------------------------
# Cantilever beams and stairs — hand checks
# ---------------------------------------------------------------------------

def test_overhang_moment_on_a_continuous_beam():
    # one span L = 4, w = 1000, right overhang moment 1125: R_A = wL/2 − M/L (statics)
    spans, r = continuous_beam([4.0], [1000.0], None, (0.0, 1125.0))
    assert spans[0].m_right == pytest.approx(-1125.0)
    assert r[0] == pytest.approx(2000 - 1125 / 4)
    # two equal spans, left overhang moment 500: three-moment equation gives M_B
    spans, _r = continuous_beam([4.0, 4.0], [1000.0, 1000.0], None, (500.0, 0.0))
    assert spans[0].m_right == pytest.approx(-(2 * 1000 * 4 ** 3 / 4 - 500 * 4) / 16)


def test_cantilever_beam_statics_and_line_effect():
    from wanicndesign.structure.design import design_level_beams, design_roof
    b = Building.load(BUILDING)
    fl2 = b.level("FL2")
    li = b.levels.index(fl2)
    mat = Concrete()
    roof = design_roof(b)
    _r0, reac0, _l0 = design_level_beams(b, mat, li, roof)
    b.toggle_cant_beam(fl2, (0, 0), "-y", 1.5, 500.0, False)
    beams, reac1, _l1 = design_level_beams(b, mat, li, roof)
    cb = next(x for x in beams if x.kind == "cantilever")
    w = 2400 * cb.b * cb.h
    assert cb.m_neg == pytest.approx(w * 1.5 ** 2 / 2 + 500 * 1.5)        # M = wL²/2 + PL
    assert cb.v == pytest.approx(w * 1.5 + 500)
    # the whole cantilever load reaches the columns
    assert sum(reac1.values()) - sum(reac0.values()) == pytest.approx(cb.v, rel=1e-6)
    # the back span carries the cantilever moment at its end
    back = next(x for x in beams if x.kind == "beam" and x.span == "1A-1B")
    assert back.m_neg >= cb.m_neg - 1e-6 and "คานยื่น" in back.note


def _stair_building(kind="landing", occupancy="house"):
    from wanicndesign.structure.building import Stair
    b = Building.load(BUILDING)
    b.occupancy = occupancy
    b.stairs.append(Stair("ST1", "3-4/A-B", "GB", "y", kind, 0.25, 0.12))
    return b


def test_stair_geometry_and_load():
    from wanicndesign.structure.stairs import geometry, strip
    b = _stair_building()
    st = b.stairs[0]
    g = geometry(b, st)
    assert (g.risers, g.riser) == (16, pytest.approx(0.20))               # 3.20 m / 0.20 m
    assert [f.risers for f in g.flights] == [8, 8]
    assert g.flights[0].going == pytest.approx(7 * 0.25)
    assert g.landing_z == pytest.approx(1.60)
    t, L, a = 0.20, 4.0, 1.75
    cos = 0.25 / math.hypot(0.25, 0.20)
    w1 = 2400 * (t / cos + 0.10) + 50 + 300                               # waist + half riser + finish + LL
    w2 = 2400 * t + 50 + 300
    m, r0, r1, wi, wf = strip(g, g.flights[0], t, 50, 300)
    assert (wi, wf) == (pytest.approx(w1), pytest.approx(w2))
    R0 = (w1 * a * (L - a / 2) + w2 * (L - a) ** 2 / 2) / L
    assert r0 == pytest.approx(R0, rel=2e-3)
    assert r0 + r1 == pytest.approx(w1 * a + w2 * (L - a), rel=1e-6)
    if R0 <= w1 * a:                                                       # zero shear on the flight
        x = R0 / w1
        m_hand = R0 * x - w1 * x * x / 2
    else:                                                                  # … or on the landing
        x = a + (R0 - w1 * a) / w2
        m_hand = R0 * x - w1 * a * (x - a / 2) - w2 * (x - a) ** 2 / 2
    assert m == pytest.approx(m_hand, rel=5e-3)


def test_stair_design_and_bt_beam():
    res = design(_stair_building())
    st = res.stairs[0]
    assert st.ok, st.note
    assert st.thickness == pytest.approx(0.20)                             # 4.0/20 × 0.971 → 0.20
    bt = [x for x in res.beams if x.kind == "stair"]
    assert len(bt) == 1 and bt[0].mark == "BT1" and bt[0].z_top == pytest.approx(1.60)
    assert "MR55-STAIR" in res.all_refs() and "QD-STAIR" in res.all_refs()
    # the stair bay is open on FL2
    assert not any(s.panel.startswith("3-4/A-B") for s in res.slabs if s.level == "FL2")
    assert any("บันได" in x.note for x in res.beams if x.level == "GB")


def test_stair_rules_of_ministerial_regulation_55():
    res = design(_stair_building("straight"))
    st = res.stairs[0]
    assert not st.ok and "ชานพัก" in st.note                                # one flight 3.20 m > 3.00 m
    res = design(_stair_building("landing", "office"))
    st = res.stairs[0]
    assert st.risers == 18 and st.riser <= 0.18                            # other buildings: riser ≤ 18 cm


def test_stairs_and_cantilever_beams_round_trip(tmp_path):
    b = _stair_building()
    b.toggle_cant_beam(b.level("FL2"), (0, 0), "-y", 1.2, 0.0, True)
    p = tmp_path / "b.json"
    b.save(str(p))
    b2 = Building.load(str(p))
    assert b2.stairs[0].panel == "3-4/A-B"
    assert b2.cant_beams(b2.level("FL2"))[0][2:] == (1.2, 0.0, True)


def test_balcony_on_cantilever_beams():
    """Slab 4.0 × 1.5 on the edge beam, two cantilever beams and a tip beam:
    one-way (m = 0.375), W·S/2 to each long edge; the tip beam is simply
    supported on the cantilever beam tips."""
    from wanicndesign.structure.design import _slab_load, design_level_beams, design_roof
    b = Building.load(BUILDING)
    fl2 = b.level("FL2")
    li = b.levels.index(fl2)
    mat, roof = Concrete(), design_roof(b)
    _r, reac0, live0 = design_level_beams(b, mat, li, roof)
    for n in ((0, 0), (1, 0)):
        b.toggle_cant_beam(fl2, n, "-y", 1.5, 0.0, False)
    b.toggle_cantilever(fl2, (0, 0), (1, 0), 1.5)
    beams, reac1, live1 = design_level_beams(b, mat, li, roof)
    W, LL = _slab_load(fl2)
    tip = next(x for x in beams if "ปลาย" in x.span)
    sw = 2400 * tip.b * tip.h
    R_tip = (W * 1.5 / 2 + sw) * 4.0 / 2
    assert tip.m_pos == pytest.approx((W * 1.5 / 2 + sw) * 4.0 ** 2 / 8, rel=2e-3)
    for cb in (x for x in beams if x.kind == "cantilever"):
        w = 2400 * cb.b * cb.h
        assert cb.m_neg == pytest.approx(w * 1.5 ** 2 / 2 + R_tip * 1.5, rel=2e-3)
    # every kilogram of the balcony reaches the columns
    cbs = [x for x in beams if x.kind == "cantilever"]
    total = W * 4.0 * 1.5 + sw * 4.0 + sum(2400 * x.b * x.h * x.length for x in cbs)
    assert sum(reac1.values()) - sum(reac0.values()) == pytest.approx(total, rel=1e-3)
    assert sum(live1.values()) - sum(live0.values()) == pytest.approx(LL * 4.0 * 1.5, rel=1e-3)
    res = design(b)
    bal = next(s for s in res.slabs if "ยื่น" in s.panel)
    assert bal.kind == "one-way" and bal.ok


# ---------------------------------------------------------------------------
# Gravity frames, slender columns, combined footings — hand checks
# ---------------------------------------------------------------------------

def test_frame_member_loads_against_closed_form():
    from wanicndesign.structure.frame2d import Member, solve_frame
    E, Ib, Ic, L, h, w, P = 2.0e9, 1e-3, 1e-4, 4.0, 3.0, 1000.0, 2000.0
    # fixed-fixed beam: wL²/12 and PL/8
    _d, f = solve_frame([(0, 0), (L, 0)], [Member(0, 1, E, 1.0, Ib)], {0, 1}, {}, {0: (-w, [(L / 2, -P)])})
    assert f[0][2] == pytest.approx(w * L * L / 12 + P * L / 8)
    assert f[0][1] == pytest.approx(w * L / 2 + P / 2)
    # symmetric portal: joint moment = FEM · kc / (kc + kb/2) (moment distribution, symmetry)
    nodes = [(0, 0), (0, h), (L, h), (L, 0)]
    mem = [Member(0, 1, E, 10.0, Ic), Member(1, 2, E, 10.0, Ib), Member(3, 2, E, 10.0, Ic)]
    _d, f = solve_frame(nodes, mem, {0, 3}, {}, {1: (-w, [])})
    kc, kb = 4 * Ic / h, 2 * Ib / L
    assert f[1][2] == pytest.approx(w * L * L / 12 * kc / (kc + kb), rel=1e-3)
    assert abs(f[0][2]) == pytest.approx(f[1][2] / 2, rel=1e-3)          # carry-over ½ to the fixed base


def test_moment_magnifier_hand_value():
    from wanicndesign.structure.columns import magnifier
    fc, pu, pd = 210.0, 30000.0, 15000.0
    lam, delta, slender = magnifier(pu, pd, 25.0, 25.0, 300.0, fc)
    assert lam == pytest.approx(300 / (0.3 * 25)) and slender
    ec = 15100 * math.sqrt(fc)
    ei = 0.4 * ec * 25 * 25 ** 3 / 12 / (1 + 1.4 * pd / pu)
    pc = math.pi ** 2 * ei / 300 ** 2
    assert delta == pytest.approx(1 / (1 - pu / (0.75 * pc)))
    assert magnifier(pu, pd, 40.0, 40.0, 250.0, fc)[2] is False        # λ = 20.8 ≤ 22


def test_gravity_frame_moments_in_columns_and_beams():
    res = design(Building.load(BUILDING))
    assert res.frames is not None and res.frames.stability
    corner = next(c for c in res.columns if c.node == "1A" and c.segment == "GB–FL2")
    assert corner.m_dx > 0 and corner.m_dy > 0 and corner.slender
    assert "EIT1008-SLENDER" in res.all_refs() and "EIT1008-BIAX" in res.all_refs()
    # every column passes the strength check after any added bars
    assert all(float(c.slender.split(" ")[0]) <= 1.0 for c in res.columns)


def test_cantilever_beam_bends_the_column():
    b = Building.load(BUILDING)
    before = next(c for c in design(b).columns if c.node == "4A" and c.segment == "GB–FL2").m_dy
    b.toggle_cant_beam(b.level("FL2"), (3, 0), "x", 2.0, 1000.0, False)   # out along +X from 4A
    after = next(c for c in design(b).columns if c.node == "4A" and c.segment == "GB–FL2")
    assert after.m_dx > 0 and after.m_dy == pytest.approx(before, rel=0.05)


def _narrow(kind, pile="I22"):
    b = Building.load(BUILDING)
    b.grid_x = [4.0, 0.8, 3.5]
    b.foundation.kind, b.foundation.pile = kind, pile
    return b


def test_combined_spread_footing_has_uniform_pressure():
    from wanicndesign.structure.footings import _beam_moments, _shear_at
    b = _narrow("spread")
    res = design(b)
    cf = [f for f in res.footings if f.kind == "combined"]
    assert cf, "the two middle columns of the narrow bay must share a footing"
    f = cf[0]
    (n1, n2) = f.nodes
    x1 = b.xs[b.parse_node(n1)[0]]
    p1 = next(c for c in res.columns if c.node == n1 and c.segment.startswith("ฐานราก")).load
    p2 = f.load - p1
    xr = x1 + p2 * 0.8 / f.load                                           # resultant
    assert f.cx == pytest.approx(xr, abs=0.03)                             # centred on it (to rounding)
    assert f.width * f.length * b.foundation.soil_qa >= f.load + f.weight - 1
    assert f.mark.startswith("CF") and f.ok
    up = [(0.5, 3.0), (1.5, 1.0)]
    downs = [(1.0, 4.0)]
    assert _shear_at(2.0, up, downs) == pytest.approx(0.0)                 # statics of the helper
    assert _beam_moments(2.0, up, downs)[0] == pytest.approx(1.5)


def test_combined_pile_cap_carries_the_load():
    b = _narrow("pile", "I18")
    res = design(b)
    cf = [f for f in res.footings if f.kind == "combined"]
    assert cf
    for f in cf:
        assert f.piles * f.pile_capacity >= f.load + f.weight - 1
        assert "เข็ม" in f.note and f.ok


# ---------------------------------------------------------------------------
# กฎกระทรวง กำหนดการออกแบบโครงสร้างอาคาร พ.ศ. 2566 (supplied by the owner)
# ---------------------------------------------------------------------------

def test_law_2566_live_loads_and_stairs():
    from wanicndesign.standards import LIVE_LOAD, NO_REDUCTION, STAIR_LIVE, ll_reduction
    assert (LIVE_LOAD["house"], LIVE_LOAD["roof"], LIVE_LOAD["canopy"], LIVE_LOAD["office"]) == (200, 50, 100, 250)
    assert (STAIR_LIVE["house"], STAIR_LIVE["apartment"], STAIR_LIVE["office"], STAIR_LIVE["assembly"]) == \
        (200, 400, 300, 500)
    assert [ll_reduction(k) for k in range(9)] == [0, 0, 0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.5]   # ข้อ 13
    assert {"school", "hospital", "parking"} <= NO_REDUCTION                                  # ข้อ 14


def test_law_2566_strength_reduction_factors():
    from wanicndesign.structure.seismic import (PHI, column_bars, phi_mn_at, phi_mn_beam, pm_curve,
                                                use_quality_control)
    bars = column_bars(4, "DB16", 30.0, 30.0)
    try:
        use_quality_control(True)
        assert PHI == {"b": 0.90, "c": 0.70, "v": 0.85}
        good = pm_curve(30.0, 30.0, bars, 210.0, 4000.0)
        m_good = phi_mn_beam(4.0, 20.0, 35.0, 210.0, 4000.0)
        use_quality_control(False)                                   # no quality control specified
        assert PHI == {"b": 0.75, "c": 0.60, "v": 0.70}
        poor = pm_curve(30.0, 30.0, bars, 210.0, 4000.0)
        assert poor[1] / good[1] == pytest.approx(0.60 / 0.70)       # compression cap
        assert phi_mn_at(poor, 0.0) / phi_mn_at(good, 0.0) == pytest.approx(0.75 / 0.90, rel=3e-3)
        assert phi_mn_beam(4.0, 20.0, 35.0, 210.0, 4000.0) / m_good == pytest.approx(0.75 / 0.90)
    finally:
        use_quality_control(True)


def test_wind_pressure_tables():
    from wanicndesign.structure.wind import force_on, pressure
    assert [pressure(z, "urban", False) for z in (5, 15, 30)] == [60, 80, 120]
    assert [pressure(z, "open", False) for z in (5, 15, 30)] == [100, 120, 160]
    assert pressure(5, "urban", True) == pytest.approx(69.0)                 # public building +15 %
    assert force_on(8.0, 12.0, 10.0, "urban", False) == pytest.approx(60 * 2 * 10 + 80 * 2 * 10)


def test_wind_on_the_example_house():
    from wanicndesign.structure.wind import force_on, roof_rise
    b = Building.load(BUILDING)
    res = design(b)
    w = res.wind
    assert w is not None and w.applicable and not w.public
    H = 6.2 + roof_rise(b)
    assert w.height == pytest.approx(H)
    e = b.roof.overhang
    total_x = force_on(0, 6.2, b.ys[-1], "urban", False) + force_on(6.2, H, b.ys[-1] + 2 * e, "urban", False)
    assert w.base_shear[0] == pytest.approx(total_x)
    assert sum(lv.fx for lv in w.levels) == pytest.approx(total_x)
    assert any(c.kind == "column" for c in w.checks) and all(c.ok for c in w.checks)
    assert "MR2566-17" in res.all_refs() and res.ok


def test_wind_table_not_for_slender_buildings():
    b = Building("tower", grid_x=[3.0], grid_y=[3.0],
                 levels=[Level("GB", 0.0, "on_ground")] + [Level(f"FL{k}", 3.0 * (k - 1)) for k in range(2, 6)])
    b.levels[-1].slab = "none"
    res = design(b)
    assert not res.wind.applicable and not res.ok                          # 12 m > 3 × 3 m


def test_fire_rating_rules():
    from wanicndesign.structure.fire import requirements
    b = Building.load(BUILDING)
    f = requirements(b)
    assert not f.applies                                   # a two-storey house
    b.occupancy = "hospital"
    f = requirements(b)
    assert f.applies and all(h == 2.0 for _n, h, _s in f.floors) and f.roof_hours == 1.0
    b.occupancy = "apartment"
    f = requirements(b)
    assert f.applies and all(h == 1.0 for _n, h, _s in f.floors) and f.roof_hours == 0.0   # ≤ 1,000 m²
    res = design(b)
    assert res.fire.applies and "MR2566-23" in res.all_refs()
