import json

import openpyxl

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
    ws = wb["ปร.4"]
    formulas = [c.value for row in ws.iter_rows() for c in row
                if isinstance(c.value, str) and c.value.startswith("=")]
    assert any(f.startswith("=ROUND(C") for f in formulas)
    assert "ค่าแรง ว480" in wb.sheetnames
