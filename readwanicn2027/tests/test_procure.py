# SPDX-License-Identifier: GPL-3.0-or-later
"""ว651 price reduction, ว124 work plan, ว78 domestic-material plans: reading the bill
from a spreadsheet, a document and a PDF, the arithmetic, the reports and the window."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("READWANICN_OFFLINE", "1")

import pymupdf
import pytest

from readwanicn import procure as P

ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")

# a ปร.4 shaped like the e-GP export: two header rows, numbered headings, material + labour
HEAD = [["ลำดับที่", "รายการ", "จำนวน", "หน่วย", "ค่าวัสดุ", "", "ค่าแรงงาน", "", "รวม", "หมายเหตุ"],
        ["", "", "", "", "ราคาต่อหน่วย", "จำนวนเงิน", "ราคาต่อหน่วย", "จำนวนเงิน", "ค่าวัสดุและแรงงาน", ""]]
LINES = [
    [1, "1. งานก่อสร้างอาคาร"],
    [2, "   1.1 งานโครงสร้าง"],
    [3, "      1.1.1 คอนกรีตผสมเสร็จ (Cube 240 ksc.)", 10, "ลบ.ม.", 3000, 30000, 400, 4000, 34000],
    [4, "      1.1.2 เหล็กข้ออ้อย DB 12 มม. (SD40)", 1000, "กก.", 22, 22000, 4, 4000, 26000],
    [5, "      1.1.3 เหล็กกล่อง 100 x 100 x 3.2 mm. (8.70 kg/m. +/-)", 10, "ท่อน", 1500, 15000, "", "", 15000],
    [6, "      1.1.4 แผ่นเหล็ก Plate 250 X 250 X 15 มม.", 4, "แผ่น", 600, 2400, "", "", 2400],
    [7, "      1.1.5 ทาสีกันสนิมเหล็ก", 20, "ตร.ม.", 80, 1600, 40, 800, 2400],
    [8, "   1.2 งานสถาปัตยกรรม"],
    [9, "      1.2.1 ผนังก่ออิฐมอญ", 100, "ตร.ม.", 150, 15000, 100, 10000, 25000],
    [10, "      1.2.2 เหล็กตะแกรง Wire Mesh Ø 4 mm. @ 0.20 m.#", 50, "ตร.ม.", 60, 3000, 20, 1000, 4000],
]
COST = 34000 + 26000 + 15000 + 2400 + 2400 + 25000 + 4000          # 108,800
FOOT = [["", "", "", "", "", "", "", "f", 1.3015]]


def _rows():
    return [["แบบ ปร.4"], ["ชื่อโครงการ/งานก่อสร้าง  ก่อสร้างอาคารทดสอบ ตำบลทดสอบ"],
            ["หน่วยงานเจ้าของโครงการ/งานก่อสร้าง  องค์การบริหารส่วนตำบลทดสอบ"]] + HEAD + LINES + FOOT


def _xlsx(path):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "ต้นฉบับ"
    for r in _rows():
        ws.append(r)
    wb.save(path)


def _docx(path):
    import docx
    d = docx.Document()
    d.add_paragraph("ชื่อโครงการ ก่อสร้างอาคารทดสอบ")
    t = d.add_table(rows=0, cols=10)
    for r in HEAD + LINES:
        cells = t.add_row().cells
        for i, v in enumerate(r):
            cells[i].text = str(v)
    d.save(path)


def _pdf(path):
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    font = os.path.join(ASSETS, "Laksaman.ttf")
    widths = [40, 280, 50, 45, 70, 70, 70, 70, 80, 40]
    y = 40
    for r in HEAD[:1] + LINES:
        x = 20
        for i, w in enumerate(widths):
            page.draw_rect(pymupdf.Rect(x, y, x + w, y + 18), width=0.5)
            v = r[i] if i < len(r) else ""
            if i == 0 and r is HEAD[0]:
                v = "ลำดับที่"
            page.insert_text((x + 2, y + 13), str(v), fontsize=8, fontfile=font, fontname="th")
            x += w
        y += 18
    doc.save(path)


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# -- arithmetic -------------------------------------------------------------------------------

def test_reduction_matches_the_651_examples():
    # ว651 ตัวอย่างงานก่อสร้างทาง: 2,376,181.32 / 2,200,000 / ค่าใช้จ่ายพิเศษ 500,000 → ร้อยละ 9.39
    r = P.reduction(2_376_181.32, 2_200_000, 500_000)
    assert r.mid_net == 1_876_181.32 and r.offer_net == 1_700_000 and r.diff == 176_181.32
    assert round(r.pct_down, 2) == 9.39
    # ตัวอย่างชลประทาน → ร้อยละ 4.20
    assert round(P.reduction(3_109_714.96, 3_000_000, 500_000).pct_down, 2) == 4.20
    # ตัวอย่าง 3 จังหวัดชายแดนภาคใต้: ราคากลาง 25,181,816 บวกเพิ่มร้อยละ 5 = 26,440,906.80
    s = P.reduction(25_181_816, 24_800_000, 1_000_000, P.SOUTH_UPLIFT)
    assert s.mid_net == 25_390_906.80 and s.offer_net == 23_750_000 and s.diff == 1_640_906.80
    # the owner's sheet: 4,831,709.89 → 4,790,000 = ลดลง 41,709.89, 0.86 %, คงเหลือ 99.14 %
    o = P.reduction(4_831_709.89, 4_790_000)
    assert o.diff == 41_709.89 and round(o.pct_down, 2) == 0.86 and round(o.pct_left, 2) == 99.14


def _building_example() -> P.Project:
    """ว651 ตัวอย่างงานก่อสร้างอาคาร: 16,230,000 × 1.2592 + ครุภัณฑ์ 3,500,000 × 1.07 + พิเศษ 1,000,000."""
    items = [P.Item("1 งานก่อสร้างอาคาร", header=True, code="1", level=1),
             P.Item("1.1 เสาเหล็กกล่อง", "ท่อน", 100, cost=5_000_000, code="1.1", level=2),
             P.Item("1.2 แผงกั้นห้อง", "ชุด", 100, cost=4_000_000, code="1.2", level=2),
             P.Item("1.3 งานอื่น", "งาน", 1, cost=7_230_000, code="1.3", level=2),
             P.Item("2 งานครุภัณฑ์จัดซื้อ", header=True, code="2", level=1),
             P.Item("2.1 โต๊ะ", "ตัว", 50, cost=2_000_000, code="2.1", level=2, equip=True),
             P.Item("2.2 เก้าอี้", "ตัว", 50, cost=1_500_000, code="2.2", level=2, equip=True),
             P.Item("3 ค่าใช้จ่ายพิเศษตามข้อกำหนด", header=True, code="3", level=1),
             P.Item("3.1 ค่าใช้จ่ายสำหรับอุปกรณ์พิเศษ", "งาน", 1, cost=500_000, code="3.1", level=2, special=True),
             P.Item("3.2 ค่าใช้จ่ายที่เกิดจากการกำหนดให้ใช้ร้านพิเศษ", "งาน", 1, cost=500_000, code="3.2", level=2,
                    special=True)]
    return P.Project(items=items, factor=1.2592, mid_price=25_181_816, offer=24_800_000)


def test_651_spreads_the_offer_over_every_line():
    p = _building_example()
    res = P.compute_651(p)
    assert res.factor == 1.2592
    assert res.mid_total == 25_181_816.0
    groups = {g[0]: g for g in res.groups}
    assert groups["งานก่อสร้าง"][3] == 20_436_816.0
    assert groups["งานครุภัณฑ์จัดซื้อ"][3] == 3_745_000.0
    assert groups["ค่าใช้จ่ายพิเศษตามข้อกำหนด"][3] == 1_000_000.0
    # ค่าใช้จ่ายพิเศษ is not reduced; the rest adds up to the offer to the satang
    assert [r.reduced for r in res.rows if r.item.special] == [500_000.0, 500_000.0]
    assert res.reduced_total == 24_800_000.0
    assert round(res.red.pct_down, 2) == 1.58
    adj = res.rows[res.adjust_row]
    assert not adj.item.special and abs(adj.adjusted) < 0.05
    for r in res.rows:
        if not r.item.header and r.item.qty:
            assert r.unit_price == P.r2(r.reduced / r.item.qty)
    sub = P.subtotals(res.rows, "reduced")
    assert abs(sub[0] + sub[4] + sub[7] - 24_800_000) < 0.005


def test_651_south_adds_five_per_cent():
    p = _building_example()
    p.work_type = "building_south"
    res = P.compute_651(p)
    assert res.mid_up_total == 26_440_906.80
    assert [r.reduced for r in res.rows if r.item.special] == [525_000.0, 525_000.0]
    assert res.reduced_total == 24_800_000.0


def test_124_plan_and_checkpoints():
    p = _building_example()
    P.auto_plan(p, 8)
    p.days = 240
    plan = P.compute_124(p)
    assert plan.months == 8 and plan.days == [30] * 8
    assert not plan.bad_lines
    assert abs(plan.acc_money[-1] - 24_800_000) < 0.05 and abs(plan.acc_plan[-1] - 100) < 1e-6
    assert all(b >= a for a, b in zip(plan.acc_plan, plan.acc_plan[1:]))
    assert [c[3] for c in plan.checks] == [25.0, 65.0, 85.0]
    assert plan.checks[0][1] == 3                     # day 120 of 240 is the end of month 4
    assert P.month_days(3, 75) == [30, 30, 15]


def test_78_weights_and_rates(tmp_path):
    p = P.read_bill(_write(tmp_path, "bill.xlsx", _xlsx))
    p.offer = P.r2(p.mid_price * 0.97)
    w = P.compute_78(p)
    steel = {it.code: t for it, t, _d in w.steel}
    assert set(steel) == {"1.1.2", "1.1.3", "1.1.4", "1.2.2"}          # not ทาสีกันสนิมเหล็ก
    assert steel["1.1.2"] == pytest.approx(1.0)                         # 1,000 กก.
    assert steel["1.1.3"] == pytest.approx(10 * 8.70 * 6 / 1000)        # kg/m × 6 m a bar
    assert steel["1.1.4"] == pytest.approx(4 * 0.25 * 0.25 * 0.015 * 7850 / 1000)
    assert steel["1.2.2"] == pytest.approx(50 * 2 / 0.2 * 3.14159265 * 0.004 ** 2 / 4 * 7850 / 1000, rel=1e-6)
    assert w.mat_pct == 100.0 and w.steel_pct == 100.0 and w.mat_ok and w.steel_ok
    it = next(i for i, _t, _d in w.steel if i.code == "1.1.2")
    it.domestic = 50.0
    assert not P.compute_78(p).steel_ok
    assert P.compute_78(p).exempt.startswith("วงเงินจ้าง")             # under 500,000 baht


def test_baht_text():
    assert P.baht_text(4_790_000) == "สี่ล้านเจ็ดแสนเก้าหมื่นบาทถ้วน"
    assert P.baht_text(121.25) == "หนึ่งร้อยยี่สิบเอ็ดบาทยี่สิบห้าสตางค์"
    assert P.num("๑,๒๓๔.๕๐") == 1234.5 and P.num("-") is None


# -- reading --------------------------------------------------------------------------------

def _write(tmp_path, name, fn):
    path = tmp_path / name
    fn(str(path))
    return str(path)


@pytest.mark.parametrize("name,fn", [("bill.xlsx", _xlsx), ("bill.docx", _docx), ("bill.pdf", _pdf)])
def test_read_bill_from_spreadsheet_document_and_pdf(tmp_path, name, fn):
    p = P.read_bill(_write(tmp_path, name, fn))
    leaves = p.leaves
    assert len(leaves) == 7
    assert p.cost_total == pytest.approx(COST)
    assert [it.code for it in p.items][:3] == ["1", "1.1", "1.1.1"]
    assert p.items[0].header and p.items[1].header and not p.items[2].header
    assert leaves[0].qty == 10 and leaves[0].unit == "ลบ.ม."
    if name == "bill.xlsx":
        assert p.factor == 1.3015
        assert p.mid_price == P.r2(COST * 1.3015)
        assert p.title.startswith("ก่อสร้างอาคารทดสอบ")
        assert p.agency == "องค์การบริหารส่วนตำบลทดสอบ"


def test_project_saves_and_loads(tmp_path):
    p = _building_example()
    P.auto_plan(p, 4)
    p.items[1].kg_per_unit = 52.2
    path = tmp_path / "งาน.rwprice.json"
    p.save(path)
    q = P.Project.load(path)
    assert q.to_dict() == p.to_dict()
    assert q.items[5].equip and q.items[8].special and q.items[1].kg_per_unit == 52.2


# -- reports and window ------------------------------------------------------------------------

def test_reports_pdf_and_spreadsheet(app, tmp_path):
    from openpyxl import load_workbook

    from readwanicn import procure_report as R
    p = _building_example()
    p.title = "อาคารทดสอบ"
    P.auto_plan(p, 6)
    p.days = 180
    for kind, sheets in (("651", 2), ("124", 1), ("78", 3)):
        files = R.write(kind, p, tmp_path / f"r{kind}.pdf", "Laksaman")
        doc = pymupdf.open(str(files[0]))
        text = "".join(pg.get_text() for pg in doc)
        assert doc.page_count >= 1 and "หน้า 1/" in text
        assert len(load_workbook(files[1]).sheetnames) == sheets
        if kind == "651":
            assert "24,800,000.00" in text and "1.58" in text
        if kind == "124":
            assert "ACC PLAN" in text
        if kind == "78":
            assert "ภาคผนวก 3" in text
    p.work_type = "road"
    files = R.write("651", p, tmp_path / "road.pdf", "Laksaman", xlsx=False)
    assert "สะพาน และท" in "".join(pg.get_text() for pg in pymupdf.open(str(files[0])))


def test_window_fills_and_edits(app, tmp_path, monkeypatch):
    from PySide6.QtCore import QStandardPaths, Qt

    from readwanicn import procure_view as V
    monkeypatch.setattr(V, "store_dir", lambda: tmp_path)
    QStandardPaths.setTestModeEnabled(True)
    p = P.read_bill(_write(tmp_path, "bill.xlsx", _xlsx))
    p.offer = 130_000
    dlg = V.ProcureDialog("Laksaman", project=p)
    assert dlg.t651.rowCount() == len(p.items)
    assert dlg.kind.currentData() == "building"
    dlg.months.setValue(3)
    assert dlg.t124.columnCount() == 5 + 3 and P.compute_124(p).months == 3
    assert dlg.p.days == 90
    # tick a line as ครุภัณฑ์: its factor becomes 1.07
    dlg.t651.item(2, 9).setCheckState(Qt.Checked)
    assert p.items[2].equip and P.compute_651(p).rows[2].factor == P.VAT_FACTOR
    # untick a steel line in ว78
    row = next(i for i, it in enumerate(dlg._rows78) if it.code == "1.1.2")
    dlg.t78.item(row, 4).setCheckState(Qt.Unchecked)
    assert not p.items[3].is_steel
    dlg.save_project(quiet=True)
    assert dlg.path and dlg.path.exists()
    pd = V.PriceDialog(p)
    pd.mid.setText("150,000")
    pd.offer.setText("140,000")
    assert pd.down.text() == "10,000.00" and pd.pct_down.text() == "6.67" and pd.pct_left.text() == "93.33"
    pd.accept()
    assert p.mid_price == 150_000 and p.offer == 140_000
    for w in (pd, dlg):
        w.deleteLater()


# -- 2027.4.1: dates, construction order, actual progress, CSV, Arabic digits -----------------------

def test_thai_dates_and_month_labels():
    assert P.thai_date("2026-11-14") == "14 พฤศจิกายน 2569"
    assert P.thai_date("๑๔ พย.๒๕๖๙") == "14 พย.2569"            # free text kept, digits made Arabic
    assert P.month_labels("2026-11-14", 3) == ["พ.ย. 69", "ธ.ค. 69", "ม.ค. 70"]
    assert P.month_labels("", 3) == []


def _house() -> P.Project:
    L = lambda code, name, unit="งาน", qty=1, cost=0.0, **kw: P.Item(  # noqa: E731
        f"{code} {name}", unit, qty, cost=cost, code=code, level=code.count(".") + 1, **kw)
    H = lambda code, name: P.Item(f"{code} {name}", header=True, code=code, level=code.count(".") + 1)  # noqa
    items = [H("1", "งานก่อสร้างอาคาร"), L("1.1", "งานวางผัง สำรวจ ปรับพื้นที่", "ตร.ม.", 100, 5_000),
             H("1.2", "งานฐานราก"), L("1.2.1", "งานขุดดิน", "ลบ.ม.", 50, 20_000),
             L("1.2.2", "คอนกรีตโครงสร้าง", "ลบ.ม.", 10, 40_000),
             H("1.3", "งานเสาและคาน"), L("1.3.1", "คอนกรีตโครงสร้าง", "ลบ.ม.", 20, 120_000),
             H("1.4", "งานหลังคา"), L("1.4.1", "กระเบื้องหลังคา", "ตร.ม.", 200, 80_000),
             H("1.5", "งานผนัง"), L("1.5.1", "ผนังก่ออิฐมอญ", "ตร.ม.", 300, 90_000),
             H("1.6", "งานระบบไฟฟ้า"), L("1.6.1", "เดินสายไฟ", "จุด", 40, 60_000),
             H("1.7", "งานตกแต่ง"), L("1.7.1", "ทาสีภายนอก", "ตร.ม.", 600, 50_000),
             L("1.8", "ประตูหน้าต่าง", "ชุด", 10, 70_000),
             H("2", "งานรั้วและลาน"), L("2.1", "รั้วคอนกรีต", "ม.", 100, 100_000),
             H("3", "งานป้ายชื่อและครุภัณฑ์"), L("3.1", "ป้ายชื่ออาคาร", "ป้าย", 1, 30_000),
             L("3.2", "โต๊ะเก้าอี้", "ชุด", 10, 40_000, equip=True)]
    return P.Project(items=items, factor=1.3, mid_price=0, offer=0)


def test_plan_follows_the_order_of_construction():
    p = _house()
    p.mid_price = P.r2(p.cost_total * 1.3) + P.r2(p.equip_total * P.VAT_FACTOR)
    p.offer = P.r2(p.mid_price * 0.98)
    P.auto_plan(p, 8)

    def first(code):
        it = next(i for i in p.items if i.code == code)
        assert abs(sum(it.plan) - 100) < 0.01
        return next(m for m, v in enumerate(it.plan) if v > 0)
    assert first("1.1") == 0 and first("1.2.1") <= 1
    assert first("1.2.1") <= first("1.3.1") <= first("1.4.1")
    assert first("1.3.1") < first("1.7.1") and first("1.5.1") < first("1.7.1")
    assert first("1.7.1") <= first("1.8")
    assert first("2.1") > first("1.2.1")                         # external works after the start
    for code in ("3.1", "3.2"):                                  # sign and equipment: last month
        it = next(i for i in p.items if i.code == code)
        assert it.plan == [0.0] * 7 + [100.0]
    plan = P.compute_124(p)
    assert not plan.bad_lines and abs(plan.acc_plan[-1] - 100) < 1e-6
    assert all(b >= a for a, b in zip(plan.acc_plan, plan.acc_plan[1:]))


def test_actual_progress_line():
    p = _house()
    p.mid_price, p.offer = 1_000_000, 950_000
    P.auto_plan(p, 4)
    p.actual = [10.0, 20.5]
    plan = P.compute_124(p)
    assert plan.acc_actual[:2] == [10.0, 30.5] and plan.acc_actual[2:] == [None, None]
    assert plan.diff[1] == pytest.approx(30.5 - plan.acc_plan[1])


def test_csv_and_arabic_digits(app, tmp_path):
    import csv

    from readwanicn import procure_report as R
    p = _building_example()
    p.title = "อาคาร ระยะที่ ๓"
    P.auto_plan(p, 4)
    files = R.write_csv("651", p, tmp_path / "w651.csv")
    assert len(files) == 2 and all(f.exists() for f in files)
    rows = list(csv.reader(open(files[0], encoding="utf-8-sig")))
    flat = " ".join(" ".join(r) for r in rows)
    assert "ระยะที่ 3" in flat and "๓" not in flat
    assert any("24800000.00" in c for r in rows for c in r)      # numbers without commas, ready to edit
    for kind, n in (("124", 1), ("78", 3)):
        assert len(R.write_csv(kind, p, tmp_path / f"w{kind}.csv")) == n
    assert "๓" not in R.to_html(R.report_651(p)[0], "Laksaman")


def _road():
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    L = lambda c, n, u, q, cost, **k: P.Item(n, u, q, cost=cost, code=c, level=c.count(".") + 1, **k)  # noqa
    H = lambda c, n: P.Item(n, header=True, code=c, level=c.count(".") + 1)  # noqa
    items = [H("1", "งานทาง"), L("1.1", "งานถางป่าขุดตอ", "ตร.ม.", 2880, 5800), L("1.2", "งานตัดดิน", "ลบ.ม.", 180, 9700),
             L("1.3", "งานพื้นทางหินคลุก", "ลบ.ม.", 406, 550000), L("1.4", "งานลาดแอสฟัลต์ไพรม์โค้ต", "ตร.ม.", 2587, 125000),
             L("1.5", "งานชั้นผิวทางแอสฟัลต์คอนกรีต", "ตร.ม.", 2541, 1120000), L("1.6", "งานตีเส้นจราจร", "ตร.ม.", 142, 43000),
             H("2", "งานสะพาน"), L("2.1", "ค่าตัดและสกัดหัวเสาเข็ม", "ต้น", 10, 3950),
             L("2.2", "งานเสาตอม่อ+คาน+กำแพงกันดิน", "SET", 2, 165000),
             L("2.3", "คานสะพานอัดแรง Plank Girder", "คาน", 8, 229000), L("2.4", "ราวสะพาน คสล.", "เมตร", 16, 38000),
             L("3", "งานป้ายประชาสัมพันธ์โครงการ", "ป้าย", 1, 2620),
             L("4", "ค่าใช้จ่ายพิเศษตามข้อกำหนดฯ", "", 1, 14445, special=True)]
    p = P.Project(items=items, factor=1.2655, work_type="road")
    p.mid_price = P.r2(sum(i.cost for i in items if not i.header and not i.special) * 1.2655) + 14445
    p.offer, p.start = 2_700_000, "2026-11-20"
    return p


def test_plan_has_work_in_every_month_in_road_order():
    p = _road()
    P.auto_plan(p, 8)
    plan = P.compute_124(p)
    assert all(m > 0 for m in plan.money)                        # money in every month of the contract
    assert abs(plan.acc_plan[-1] - 100) < 1e-6 and not plan.bad_lines
    first = {it.code: next(m for m, v in enumerate(it.plan) if v > 0) for it in p.leaves}
    assert first["1.1"] == 0 and first["1.2"] <= first["1.3"] <= first["1.4"] <= first["1.5"] <= first["1.6"]
    assert first["2.1"] <= first["2.2"] <= first["2.3"] <= first["2.4"]
    assert next(i for i in p.leaves if i.code == "3").plan[-1] == 100.0
    assert all(abs(v - 12.5) < 0.01 for v in next(i for i in p.leaves if i.code == "4").plan)
    k = next(c for w, c, _a, _n in plan.checks if "1 ใน 2" in w)
    assert plan.acc_plan[k] >= 25


def test_651_adjusted_line_grey_and_noted(app):
    from readwanicn import procure_report as R
    p = _road()
    res = P.compute_651(p)
    assert res.adjust_row >= 0
    note = R.adjust_note(res)
    assert "ลำดับที่" in note and "แรเงาสีเทา" in note
    a = R.report_651(p)[0]
    texts = [b.text for b in a.blocks if isinstance(b, R.Para)]
    assert any("ลำดับที่" in t for t in texts)
    rows = [row for b in a.blocks if isinstance(b, R.Table) for row in b.body]
    assert any(any(c.bg == R.GREY and "(*)" in c.text for c in row) for row in rows)


def test_work_plan_and_a4_sheets(app, tmp_path):
    from openpyxl import load_workbook

    from readwanicn import procure_report as R
    p = _road()
    P.auto_plan(p, 8)
    rep = R.report_work(p)[0]
    table = next(b for b in rep.blocks if isinstance(b, R.Table))
    assert len(table.head[0]) == 7 + 8 and len(table.head[1]) == 8
    bars = [c for row in table.body for c in row if c.bg == R.BAR]
    assert bars
    assert R.bar_halves([0, 30, 70, 0]) == [False, False, False, True, True, True, False, False]
    for kind in ("651", "124", "work", "78"):
        f = R.write_sheet(kind, p, tmp_path / f"{kind}.xlsx")[0]
        wb = load_workbook(f)
        for ws in wb.worksheets:
            assert int(ws.page_setup.paperSize) == 9 and ws.sheet_properties.pageSetUpPr.fitToPage
            assert ws.page_setup.fitToWidth == 1
    assert R.write_sheet("651", p, tmp_path / "x.csv")[0].suffix == ".csv"
    assert R.write("work", p, tmp_path / "work.pdf", "Laksaman")[0].exists()


def test_sheets_with_excel_control_characters(app, tmp_path):
    """Names read from an Excel bill can hold \\x0b (Alt+Enter) and other control characters:
    the .xlsx must still be written (they were refused and nothing was saved)."""
    from readwanicn import procure_report as R
    p = _road()
    P.auto_plan(p, 8)
    p.items[1].name = "งานถางป่า\x0bขุดตอ\x01"
    assert P.text("ก\x0bข\x1f") == "ก ข"
    for kind in ("651", "124", "work", "78"):
        f = R.write_sheet(kind, p, tmp_path / f"{kind}.xlsx")[0]
        assert f.exists() and f.stat().st_size > 1000
    R.WRITE_ERRORS.clear()
    files = R.write("651", p, tmp_path / "r651.pdf", "Laksaman")
    assert not R.WRITE_ERRORS and any(str(f).endswith(".xlsx") for f in files)
