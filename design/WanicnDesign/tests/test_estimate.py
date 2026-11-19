import json

import openpyxl
import pytest

from conftest import EXAMPLE
from wanicndesign.estimate import estimate
from wanicndesign.model import Project
from wanicndesign.rates import Rates


def test_labour_amounts_follow_rates():
    est = estimate(Project.load(EXAMPLE), Rates())
    dig = next(r for r in est.rows if r.line.item == "ขุดดินฐานราก")
    assert dig.labour_rate == 181
    assert dig.labour_amount == round(dig.line.qty * 181, 2)
    rebar = next(r for r in est.rows if r.line.item == "เหล็กเสริม DB12")
    assert rebar.labour_rate == 3.9           # 3,900 บาท/ตัน → per kg


def test_material_prices_and_totals():
    prices = {"คอนกรีตผสมเสร็จ (คาน)": 2400.0}
    est = estimate(Project.load(EXAMPLE), Rates(prices=prices))
    beam = next(r for r in est.rows if r.line.item == "คอนกรีตผสมเสร็จ (คาน)")
    assert beam.material_amount == round(beam.line.qty * 2400, 2)
    assert est.total == round(est.material_total + est.labour_total, 2)


def test_labour_update_and_scale(tmp_path):
    override = tmp_path / "labour_override.json"
    r = Rates(override_file=str(override))
    r.set_labour("1.3.1c", 200)
    assert json.loads(override.read_text(encoding="utf-8")) == {"1.3.1c": 200.0}
    assert Rates(override_file=str(override)).labour_rate("1.3.1c") == 200
    r.scale_labour(10)
    assert r.labour_rate("1.3.1c") == 220


def test_xlsx_has_formulas(tmp_path):
    est = estimate(Project.load(EXAMPLE), Rates())
    out = tmp_path / "boq.xlsx"
    est.to_xlsx(str(out))
    wb = openpyxl.load_workbook(out)
    assert wb.sheetnames[:3] == ["ปร.4", "ปร.1 (ก)", "ปร.1"]
    ws = wb["ปร.1"]
    formulas = [c.value for row in ws.iter_rows() for c in row
                if isinstance(c.value, str) and c.value.startswith("=")]
    assert any(f.startswith("=ROUND(C") for f in formulas)
    summary = [c.value for row in wb["ปร.1 (ก)"].iter_rows() for c in row if isinstance(c.value, str)]
    assert any(v.startswith("='ปร.1'!I") for v in summary)
    assert any(str(c.value).startswith("='ปร.1 (ก)'!E") for row in wb["ปร.4"].iter_rows() for c in row)
    for name in ("ค่าแรง ว480", "ราคาวัสดุ", "วิเคราะห์ค่าวัสดุ", "มาตรฐานและที่มา"):
        assert name in wb.sheetnames


def test_materials_from_recipes_and_price_book():
    from wanicndesign.materials import READY_MIX, RECIPES, recipe_cost
    prices = {READY_MIX: 2500.0, "อิฐมอญ (อิฐก่อสร้างสามัญ) ขนาด 7 x 16 x 3.5 ซม.": 1.2,
              "ปูนซีเมนต์ผสม (Silica Cement)": 3.0, "น้ำยาผสมปูนก่อ": 40.0, "ทรายหยาบ": 500.0}
    est = estimate(Project.load(EXAMPLE), Rates(prices=prices))
    beam = next(r for r in est.rows if r.line.item == "คอนกรีตผสมเสร็จ (คาน)")
    assert beam.material_rate == 2500.0 and not beam.missing
    # brick wall = recipe 6.1: 138 bricks, 16.01 kg cement, 0.4 L admixture, 0.05 m³ sand, 10 L water
    rc = RECIPES["6.1"]
    assert rc["page"] == 117 and rc["items"][0]["qty"] == 138.0
    hand = 138 * 1.2 + 16.01 * 3.0 + 0.4 * 40.0 + 0.05 * 500.0 + 10 * 0.0164
    assert recipe_cost("6.1", prices) == (pytest.approx(hand), [])
    wall = next((r for r in est.rows if r.line.item == "ก่ออิฐมอญครึ่งแผ่น"), None)
    if wall:
        assert wall.material_rate == round(hand, 2)
    # a material with no price is reported, never guessed
    lean = next(r for r in est.rows if r.line.item.startswith("คอนกรีตหยาบ"))
    assert "หินเบอร์ 1-2" in lean.missing and "หินเบอร์ 1-2" in est.missing_prices()
    assert "หินเบอร์ 1-2" in est.needed_materials()


def test_factor_f_and_price_in_words():
    from wanicndesign.estimate import baht_text, factor_f
    from wanicndesign.structure.building import Costing
    table = [[5e6, 1.30], [10e6, 1.26]]                   # illustrative rows, not the CGD table
    assert factor_f(5e6, table) == 1.30 and factor_f(1e6, table) == 1.30 and factor_f(2e7, table) == 1.26
    assert factor_f(7.5e6, table) == pytest.approx(1.28)  # straight line between rows
    assert factor_f(1e6, [], 1.25) == 1.25
    assert baht_text(1234.5) == "หนึ่งพันสองร้อยสามสิบสี่บาทห้าสิบสตางค์"
    assert baht_text(21000000) == "ยี่สิบเอ็ดล้านบาทถ้วน"
    c = Costing(factor_f=1.2)
    est = estimate(Project.load(EXAMPLE), Rates(), costing=c)
    assert est.grand == pytest.approx(round(est.total * 1.2, 2), abs=0.02)
    c.method = "private"
    est = estimate(Project.load(EXAMPLE), Rates(), costing=c)
    assert est.vat_added == pytest.approx(est.construction * 0.07, abs=0.01)


def test_province_book_prices_the_design(tmp_path, monkeypatch):
    import os
    from conftest import ROOT
    from wanicndesign import province as P
    from wanicndesign.estimate import for_design
    from wanicndesign.materials import READY_MIX
    from wanicndesign.structure.building import Building
    from wanicndesign.structure.design import design
    monkeypatch.setenv("WANIC_PRICE_DIR", str(tmp_path))
    b = Building.load(os.path.join(ROOT, "examples", "building_2storey.json"))
    b.province = "ขอนแก่น"
    P.save_book("ขอนแก่น", {READY_MIX: 2450.0, "DB12": 26.5}, "ต.ค. 2569")
    est = for_design(design(b))
    assert est.province == "ขอนแก่น" and est.costing.price_month == "ต.ค. 2569"
    assert "ขอนแก่น" in est.price_ref
    conc = [r for r in est.rows if r.line.item.startswith("คอนกรีตผสมเสร็จ")]
    assert conc and all(r.material_rate == 2450.0 for r in conc)
    assert est.area > 0
    # the commerce office's table → matched to the materials the design needs
    csv_path = tmp_path / "moc.csv"
    csv_path.write_text("รายการ,หน่วย,ตุลาคม 2569\nเหล็กเส้นข้ออ้อย SD40 ขนาด 16 มม.,ตัน,25500\n"
                        "ทรายหยาบ,ลบ.ม.,520\n", encoding="utf-8")
    rows, _month = P.read_table(str(csv_path))
    found = P.match(rows, ["DB16", "ทรายหยาบ"], {"DB16": "กก.", "ทรายหยาบ": "ลบ.ม."})
    assert found["DB16"][0] == pytest.approx(25.5) and found["ทรายหยาบ"][0] == 520.0


def test_province_module_is_the_3d_copy():
    import os
    from conftest import ROOT
    src = os.path.join(ROOT, "..", "..", "3d", "core", "wanic_province.py")
    if not os.path.exists(src):
        return
    mine = open(os.path.join(ROOT, "wanicndesign", "province.py"), encoding="utf-8").read()
    assert mine.split("\n", 1)[1] == open(src, encoding="utf-8").read()
