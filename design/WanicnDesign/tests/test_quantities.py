import pytest

from conftest import EXAMPLE
from wanicndesign.model import Beam, Column, Footing, Opening, Project, Roof, Slab, Wall
from wanicndesign.quantities import bar_count, parse_bar, takeoff
from wanicndesign.rates import Rates, q2


@pytest.fixture
def rates():
    return Rates()


def by_item(lines):
    return {ln.item: ln for ln in lines}


def test_parse_bar():
    assert parse_bar("4-DB12") == (4, "DB12", None)
    assert parse_bar("RB6@0.15") == (None, "RB6", 0.15)
    assert parse_bar("nonsense") is None
    assert bar_count(1.0, 0.15) == 7


def test_q2_rounds_half_up():
    assert q2(1.005) == 1.01
    assert q2(2.344) == 2.34


def test_excavation_shallow_and_deep(rates):
    p = Project("t", footings=[Footing("F1", 2, 1.0, 1.0, 0.4, 1.5)])
    ln = by_item(takeoff(p, rates))["ขุดดินฐานราก"]
    assert ln.qty == q2(2 * 1.5 * 1.3)          # 30% waste up to 2 m
    assert ln.labour_code == "1.3.1c"           # under 25 m³
    p = Project("t", footings=[Footing("F1", 1, 1.0, 1.0, 0.4, 2.5)])
    ln = by_item(takeoff(p, rates))["ขุดดินฐานราก"]
    assert ln.qty == q2(2.0 * 2.0 * 2.5)        # 0.50 m each side, no %


def test_column_concrete_forms_and_bars(rates):
    p = Project("t", floors=[], columns=[Column("C1", 2, 0.2, 0.2, 3.0, "4-DB12", "RB6@0.20")])
    lines = by_item(takeoff(p, rates))
    assert lines["คอนกรีตผสมเสร็จ (เสา)"].qty == q2(2 * 0.2 * 0.2 * 3.0)
    assert lines["ไม้แบบ"].qty == q2(2 * 0.8 * 3.0)
    db12 = lines["เหล็กเสริม DB12"]
    assert db12.qty == q2(2 * 4 * 3.0 * 0.888 * 1.09)
    assert db12.labour_code == "1.10.2" and db12.labour_factor == 0.001
    stirrups = 16 * (2 * (0.15 + 0.15) + 0.10) * 2   # 16 per column
    assert lines["เหล็กเสริม RB6"].qty == q2(stirrups * 0.222 * 1.05)


def test_wall_deducts_openings_and_lintels(rates):
    p = Project("t",
                openings=[Opening("window", "W1", 1.2, 1.0, 1)],
                walls=[Wall("w", "FL1", 4.0, 3.0, 0.2, 0.5, openings=["W1"], paint="P1"),
                       Wall("p", "FL1", 4.0, 3.0, 0.2, 0.5, paint="P0", count=2)])
    lines = by_item(takeoff(p, rates))
    one = 3.8 * 2.5
    assert lines["ก่ออิฐมอญครึ่งแผ่น"].qty == q2(one - 1.2 + 2 * one)
    assert lines["เสาเอ็น คานทับหลัง"].qty == q2(2 * 1.2 + 2.2 + 2 * 3.8)
    assert lines["ฉาบปูนผนังภายนอก"].qty == q2(one - 1.2)
    assert lines["ทาสีน้ำอะครีลิค ภายใน"].qty == q2((one - 1.2) + 2 * 2 * one)


def test_mortar_and_paint_codes(rates):
    p = Project("t", walls=[Wall("w", "FL1", 3.2, 3.0, 0.2, 0.5, mortar="M0", paint="P2")])
    lines = by_item(takeoff(p, rates))
    assert "ฉาบปูนผนังภายนอก" not in lines and "ฉาบปูนผนังภายใน" not in lines
    assert lines["ทาสีน้ำอะครีลิค ภายนอก"].qty == q2(2 * 3.0 * 2.5)


def test_roof_area_and_waste(rates):
    p = Project("t", roof=Roof(100.0, 30.0, "gable", "metal_sheet", ridge_length=10))
    lines = by_item(takeoff(p, rates))
    sheet = lines["มุงหลังคาเหล็กรีดลอน"]
    assert sheet.qty == q2(100 / 0.8660254 * 1.03)
    assert sheet.labour_code == "2.1.8"
    assert lines["ครอบสัน ครอบตะเข้สัน"].labour_code == "2.1.8f"


def test_single_storey_uses_single_storey_concrete_rate(rates):
    p = Project("t", floors=[], slabs=[Slab("S1", "FL1", 10, 0.1, on_ground=True)])
    assert by_item(takeoff(p, rates))["คอนกรีตผสมเสร็จ (พื้น)"].labour_code == "1.7a"


def test_example_project_runs(rates):
    lines = takeoff(Project.load(EXAMPLE), rates)
    assert len(lines) > 20
    assert all(ln.qty > 0 for ln in lines)


def test_corrugated_roof_codes_and_verges(rates):
    for shape, code in (("gable", "2.1.1"), ("shed", "2.1.1"), ("hip", "2.1.1h")):
        p = Project("t", roof=Roof(100.0, 30.0, shape, "asbestos", ridge_length=10, verge_length=12))
        lines = takeoff(p, rates)
        roof = [ln for ln in lines if ln.item.startswith("มุงกระเบื้องลอนคู่")]
        assert roof and roof[0].labour_code == code
        assert by_item(lines)["ครอบสัน ครอบตะเข้สัน"].labour_code == "2.1.1r"
        verge = [ln for ln in lines if "ครอบปั้นลม" in ln.item]
        assert verge and verge[0].qty == pytest.approx(12.0)
    p = Project("t", roof=Roof(100.0, 30.0, "gable", "concrete_tile", ridge_length=10, verge_length=8))
    assert [ln for ln in takeoff(p, rates) if "ครอบปั้นลม" in ln.item][0].labour_code == "2.1.3v"
