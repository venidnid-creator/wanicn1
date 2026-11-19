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
    c = Costing(factor_f=1.2, use_official=False)
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


def test_official_factor_f_table_w481():
    from wanicndesign.estimate import OFFICIAL_FF, official_factor
    assert len(OFFICIAL_FF["tables"]) == 12 and OFFICIAL_FF["interest"] == 6.0
    for t in OFFICIAL_FF["tables"]:                      # every row: Factor F = Factor × 1.07 (VAT)
        assert len(t["rows"]) == 24
        assert all(abs(r[3] - r[2] * 1.07) < 5.1e-4 for r in t["rows"])
    # advance 0 %, retention 0 % — the first table of ว 481
    assert official_factor(300_000, 0, 0) == 1.3073                       # ≤ 0.5 million
    assert official_factor(5_000_000, 0, 0) == 1.3002
    assert official_factor(7_500_000, 0, 0) == pytest.approx(1.3002 - (1.3002 - 1.2942) * 2.5 / 5)
    assert official_factor(600_000_000, 0, 0) == 1.1787                   # > 500 million
    assert official_factor(1_000_000, 0, 0, no_vat=True) == 1.2196        # รวมในรูป Factor
    assert official_factor(1_000_000, 0, 5) == 1.3055                     # retention 5 %
    assert official_factor(1_000_000, 3, 0) is None                       # no such table


def test_estimate_uses_official_factor_and_loan_share():
    from wanicndesign.estimate import official_factor
    from wanicndesign.structure.building import Costing
    est = estimate(Project.load(EXAMPLE), Rates(), costing=Costing())
    assert est.factor == round(official_factor(est.total, 0, 0), 4) and "ว 481" in est.factor_note
    c = Costing(loan_share=60)
    est = estimate(Project.load(EXAMPLE), Rates(), costing=c)
    mix = 0.6 * official_factor(est.total, 0, 0, True) + 0.4 * official_factor(est.total, 0, 0)
    assert est.factor == round(mix, 4)
    est = estimate(Project.load(EXAMPLE), Rates(), costing=Costing(interest=5, factor_f=1.25))
    assert est.factor == 1.25 and "ไม่มีตาราง" in est.factor_note       # interest differs from the table


def _house_with_bath():
    import os
    from conftest import ROOT
    from wanicndesign.structure.building import Building
    b = Building.load(os.path.join(ROOT, "examples", "building_2storey.json"))
    b.levels[1].wet_bays = [b.panel_name(0, 0)]          # bathroom FL2 bay 1-2/A-B: 4 × 4 m, centre (2, 2)
    return b


def test_mep_quantities_from_the_model():
    from wanicndesign.structure.mep import mep_lines, rooms
    b = _house_with_bath()
    lines = {d["item"]: d for d in mep_lines(b)}
    n_rooms = len(rooms(b))
    assert lines["สวิตช์ทางเดียว 1 ช่อง"]["qty"] == n_rooms
    assert lines["เต้ารับคู่มีกราวด์ 2P+G"]["qty"] == 2 * (n_rooms - 1)          # none in the bathroom
    # toilet 4": meter 1A (0, 0) → (2, 2) at +3.20 m, drop 1.5 m, allowance 10 %
    assert lines['ท่อระบายน้ำ PVC 4"']["qty"] == pytest.approx((2 + 2 + 3.2 + 1.5) * 1.1)
    assert lines['ท่อระบายน้ำ PVC 4"']["code"] == '3.7/Dia 4"'
    assert lines['สต๊อปวาล์ว 1/2"']["qty"] == 3
    fit = lines['ข้อต่อ อุปกรณ์ท่อ (ท่อระบายน้ำ PVC 4")']
    assert fit["mats"] == [['ท่อ PVC ชั้น 8.5 ขนาด 4" (ระบายน้ำ)', 0.4]] and fit["labour_pct"] == 0.3
    b.mep.enabled = False
    assert mep_lines(b) == []


def test_mep_prices_and_w480_rates(tmp_path, monkeypatch):
    monkeypatch.setenv("WANIC_PRICE_DIR", str(tmp_path))
    from wanicndesign.estimate import for_design
    from wanicndesign.rates import Rates
    from wanicndesign.structure.design import design
    r = Rates(prices={'ท่อ PVC ชั้น 8.5 ขนาด 4" (ระบายน้ำ)': 150.0})
    assert r.labour_rate('3.7/Dia 4"') == 103 and r.labour_rate("4.57/C.B. 2 Pole (10, 15, 20, 30. 40 AT)") == 113
    assert r.labour_rate('4.58/โคม Downlight/ขนาด dia 4" - 6"') == 118
    est = for_design(design(_house_with_bath()), r)
    fit = next(x for x in est.rows if x.line.item == 'ข้อต่อ อุปกรณ์ท่อ (ท่อระบายน้ำ PVC 4")')
    assert fit.material_rate == 60.0 and fit.labour_rate == pytest.approx(18.0)   # 40 % of 150, labour 30 % of that
    pipe = next(x for x in est.rows if x.line.item == 'ท่อระบายน้ำ PVC 4"')
    assert pipe.material_rate == 150.0 and pipe.labour_rate == 103


def test_equipment_and_special_costs_forms(tmp_path):
    from wanicndesign.structure.building import Costing
    c = Costing(use_official=False, factor_f=1.2,
                extras=[{"section": "equip", "item": "เครื่องปรับอากาศ 12,000 BTU", "qty": 2, "unit": "ชุด",
                         "mat": 15000, "lab": 2000, "note": ""},
                        {"section": "special", "item": "ค่าทดสอบดิน", "qty": 1, "unit": "งาน", "mat": 10000,
                         "lab": 0, "note": ""}])
    est = estimate(Project.load(EXAMPLE), Rates(), costing=c)
    assert est.extras_total("equip") == 34000 and est.extras_total("special") == 10000
    assert est.grand == pytest.approx(est.construction + 34000 * 1.07 + 10000 * 1.07, abs=0.02)
    out = tmp_path / "f.xlsx"
    est.to_xlsx(str(out))
    wb = openpyxl.load_workbook(out)
    for name in ("ปร.2", "ปร.2 (ก)", "ปร.3"):
        assert name in wb.sheetnames
    vals = [c.value for row in wb["ปร.4"].iter_rows() for c in row]
    assert 36380.0 in vals and 10700.0 in vals


def test_mep_and_costing_round_trip(tmp_path):
    from wanicndesign.structure.building import Building
    b = _house_with_bath()
    b.mep.ac_points, b.mep.panel = 3, "2B"
    b.costing.extras = [{"section": "equip", "item": "x", "qty": 1, "unit": "ชุด", "mat": 1, "lab": 0, "note": ""}]
    p = tmp_path / "b.json"
    b.save(str(p))
    c = Building.load(str(p))
    assert c.mep.ac_points == 3 and c.mep.panel == "2B" and c.costing.extras[0]["item"] == "x"


def test_loan_interest_rounding_cgd_26_6_2569():
    from wanicndesign.estimate import loan_interest, needs_new_table
    assert loan_interest(6.38) == 6 and loan_interest(6.50) == 7 and loan_interest(6.49) == 6
    assert not needs_new_table(6.38) and needs_new_table(7.0) and needs_new_table(5.0)


def test_contract_uses_factor_f_of_the_whole_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("WANIC_PRICE_DIR", str(tmp_path))
    import os
    from conftest import ROOT
    from wanicndesign.estimate import contract_for_designs, official_factor
    from wanicndesign.structure.building import Building
    from wanicndesign.structure.design import design
    a = Building.load(os.path.join(ROOT, "examples", "building_2storey.json"))
    b = Building.load(os.path.join(ROOT, "examples", "building_2storey.json"))
    a.name, b.name = "อาคาร ก", "อาคาร ข"
    rates = Rates(prices={"คอนกรีตผสมเสร็จ 240 กก./ตร.ซม. (ลูกบาศก์)": 2500.0})
    con = contract_for_designs("โรงเรียน", [design(a), design(b)], rates)
    assert con.total == pytest.approx(sum(e.total for _l, e in con.items))
    f = round(official_factor(con.total, 0, 0), 4)
    assert con.factor == f and all(e.factor == f for _l, e in con.items)        # one F for the whole contract
    alone = con.items[0][1].total
    assert official_factor(alone, 0, 0) >= official_factor(con.total, 0, 0)    # a bigger cost never raises F
    assert con.grand == pytest.approx(sum(round(e.total * f, 2) for _l, e in con.items), abs=0.05)
    out = tmp_path / "c.xlsx"
    con.to_xlsx(str(out))
    wb = openpyxl.load_workbook(out)
    assert wb.sheetnames[:4] == ["ปร.4", "ปร.1 (ก)", "ปร.1 (1)", "ปร.1 (2)"]
    labels = [c.value for row in wb["ปร.1 (ก)"].iter_rows() for c in row]
    assert "อาคาร ก" in labels and "อาคาร ข" in labels
    assert any(str(v).startswith("='ปร.1 (2)'!I") for v in labels)
    assert any("งานหรือกลุ่มงาน  อาคาร ข" == c.value for row in wb["ปร.1 (2)"].iter_rows() for c in row)
