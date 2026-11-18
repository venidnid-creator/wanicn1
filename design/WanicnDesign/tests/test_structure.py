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
    W = 2400 * 0.10 + 50 + 150
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
    W = 2400 * 0.10 + 50 + 150
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
    # 4 floors: FL4 is the 1st floor below the roof (0 %), FL3 the 2nd (10 %),
    # FL2 the 3rd (20 %) [MR6-16]. A two-storey house gets no reduction.
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
    assert all("MR6-16" in c.refs for c in below_fl2)
    top = [c for c in reduced if c.segment == "FL4–ROOF"]
    assert all(c.live_reduced == 0 for c in top)
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
    assert "EIT1007-COL" in codes and "MR6-15" in codes
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
    fl = Level("FL2", 3.0, "suspended", 0.10, 150, 50, 0.20, 0.40, "B", "none")
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
    W = 2400 * 0.10 + 50 + 150                      # 440 kg/m²
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
    W = 2400 * 0.10 + 50 + 150
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
