import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from venitsupply import depreciation as DEP  # noqa: E402
from venitsupply import thaidate as TD  # noqa: E402
from venitsupply.db import Store  # noqa: E402


def test_fiscal_year():
    assert TD.fiscal_year("2026-09-30") == 2569
    assert TD.fiscal_year("2026-10-01") == 2570
    s, e = TD.fiscal_range(2570)
    assert str(s) == "2025-10-01"[:0] + "2026-10-01" and str(e) == "2027-09-30"
    assert TD.thai("2026-11-13") == "13 พ.ย. 2569"


def test_depreciation_straight_line():
    # 36,501 บาท, 5 ปี, ซาก 1 → 7,300 ต่อปี; ได้มา 1 ต.ค. = เต็มปีแรก
    rows = DEP.schedule(36501, "2020-10-01", 5, until_fy=2580)
    assert [r["fy"] for r in rows] == [2564, 2565, 2566, 2567, 2568]
    assert rows[0]["days"] == 365 and rows[0]["dep"] == 7300.0
    assert rows[-1]["acc"] == 36500.0 and rows[-1]["book"] == 1.0


def test_depreciation_first_year_by_days_and_threshold():
    rows = DEP.schedule(36501, "2021-04-01", 5, until_fy=2570)
    # 1 เม.ย. – 30 ก.ย. 2564 = 183 วัน
    assert rows[0]["fy"] == 2564 and rows[0]["days"] == 183
    assert rows[0]["dep"] == round(7300 * 183 / 365, 2)
    assert rows[-1]["acc"] == 36500.0          # never below salvage
    assert DEP.schedule(9500, "2021-04-01", 5) == []   # under 10,000 → expensed


def test_asset_numbers_and_report(tmp_path):
    s = Store(tmp_path / "a.vsdb")
    s.set_setting("org_code", "1234")
    cat = s.categories("asset")[10]                 # คอมพิวเตอร์ 3 ปี
    a1 = s.save_asset(dict(name="คอมพิวเตอร์โน้ตบุ๊ก", category_id=cat["id"], price=25000,
                           acquire_date="2025-11-01", department="งานสำรวจ", custodian="นายเอ"))
    a2 = s.save_asset(dict(name="เครื่องพิมพ์", category_id=cat["id"], price=8000,
                           acquire_date="2025-12-01"))
    assert s.asset(a1)["number"] == "1234-11-0001/2569"
    assert s.asset(a2)["number"] == "1234-11-0002/2569"
    assert s.asset(a1)["life_years"] == 3 and s.asset(a1)["custodian"] == "นายเอ"
    rep = s.depreciation_report(2569)
    assert len(rep) == 1 and rep[0]["asset"]["id"] == a1     # printer below threshold
    s.close()
    s2 = Store(tmp_path / "a.vsdb")                           # persisted, not reseeded
    assert len(s2.categories("asset")) == 16 and len(s2.assets()) == 2


def test_fifo_stock_card():
    s = Store()
    m = s.save_material(dict(name="กระดาษ A4", unit="รีม", min_qty=5))
    s.receive(m, "2026-10-02", 10, 100)
    s.receive(m, "2026-10-05", 10, 120)
    s.issue(m, "2026-10-06", 15, party="นายบี", department="งานธุรการ")
    card = s.card(m)
    assert card[-1]["value"] == 10 * 100 + 5 * 120
    assert card[-1]["bal_qty"] == 5 and card[-1]["bal_val"] == 600
    with pytest.raises(ValueError):
        s.issue(m, "2026-10-07", 6)
    with pytest.raises(ValueError):          # cannot issue before it was received
        s.issue(m, "2026-10-01", 1)
    assert s.summary()["low_stock"][0]["name"] == "กระดาษ A4"


def test_loans_inspection_disposal():
    s = Store()
    cat = s.categories("asset")[6]
    a = s.save_asset(dict(name="กล้องระดับ", category_id=cat["id"], price=45000,
                          acquire_date="2024-01-15"))
    ln = s.lend(a, "นายซี", "2026-10-01", "2026-10-10", "สำรวจถนน")
    with pytest.raises(ValueError):
        s.lend(a, "นายดี", "2026-10-02")
    assert len(s.overdue("2026-11-01")) == 1
    s.give_back(ln, "2026-11-02")
    assert s.overdue("2026-11-03") == []
    s.inspect(2570, a, "ชำรุด")
    assert s.asset(a)["status"] == "ชำรุด"
    assert s.inspection(2570)[0]["result"] == "ชำรุด"
    s.dispose(a, "2027-03-01", "ขาย (ทอดตลาด/เฉพาะเจาะจง)", 5000)
    assert s.asset(a)["status"] == "จำหน่ายแล้ว"
    rows = s.depreciation(s.asset(a), until_fy=2580)
    assert rows[-1]["fy"] == 2570                       # stops at disposal
    assert s.inspection(2570) == []


def test_reports_build(tmp_path):
    import zipfile
    from venitsupply import reports as R
    s = Store()
    s.set_setting("org_name", "สำนักงานทดสอบ")
    cat = s.categories("asset")[0]
    a = s.save_asset(dict(name="โต๊ะทำงาน", category_id=cat["id"], price=12000, acquire_date="2024-05-01"))
    m = s.save_material(dict(name="ปากกา", unit="ด้าม"))
    s.receive(m, "2026-10-01", 50, 10)
    mv = s.issue(m, "2026-10-03", 5, party="นายอี", department="งานการเงิน", doc_no="บ.1/2570")
    for rep in (R.asset_list(s), R.asset_card(s, a, 2570), R.depreciation_year(s, 2570),
                R.material_balance(s), R.stock_card(s, m), R.issue_slip(s, [mv]),
                R.loans_report(s), R.inspection_report(s, 2570), R.disposal_report(s)):
        html = rep.html()
        assert "สำนักงานทดสอบ" in html and "นายเวนิช ธัมมะวงษ์" in html
    assert "50.00" in R.issue_slip(s, [mv]).html()
    p = tmp_path / "x.xlsx"
    R.to_xlsx(R.asset_list(s), p)
    with zipfile.ZipFile(p) as z:
        assert "โต๊ะทำงาน" in z.read("xl/worksheets/sheet1.xml").decode()


def test_demo_data():
    from venitsupply import demo
    s = demo.fill(Store())
    sm = s.summary()
    assert sm["assets"] == 8 and sm["materials"] >= 5 and sm["loans_open"] == 2


def test_leap_year_is_one_full_year():
    rows = DEP.schedule(285000, "2021-06-01", 5, until_fy=2580)
    full = [r for r in rows if r["days"] in (365, 366)]
    assert all(r["dep"] == 56999.8 for r in full[:-1])
    assert rows[-1]["acc"] == 284999.0


def test_life_notice_import_and_alerts(tmp_path):
    """ประกาศ อบต.ไม้ขาว 3 ต.ค. 2565: ฟ้าอ่อน/เหลือง/ส้ม + นำเข้าบัญชีตรวจสอบ + สีอายุการใช้งาน."""
    import datetime as dt
    import openpyxl
    from venitsupply import lifecycle as L, reports as R
    s = Store()
    s.set_setting("org_name", "องค์การบริหารส่วนตำบลไม้ขาว")
    s.save_category("asset", "99", "ครุภัณฑ์ทดลอง", 4)
    out = s.ensure_lifecycle()
    cats = {c["code"]: c for c in s.categories("asset")}
    assert cats["01"]["life_years"] == 12 and cats["11"]["life_years"] == 5 and cats["01"]["notice_status"] == "match"
    assert "ปรับอายุจาก 8 เป็น 12 ปี" in cats["01"]["notice_note"]
    assert cats["17"]["notice_status"] == "added" and cats["99"]["notice_status"] == "missing"
    assert all(c["notice_note"].startswith("แจ้งสถานะ") for c in cats.values())
    assert out["categories"] >= 22 and s.current_notice()["notice_date"] == L.NOTICE_DATE
    assert L.parse_thai_date("01 ตุลาคม 2550") == dt.date(2007, 10, 1)
    assert L.parse_thai_date("15 กรกฏาคม 2560") == dt.date(2017, 7, 15) and L.parse_thai_date(2557) == dt.date(2013, 10, 1)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "บัญชี 1ชำรุด"
    ws.append(["ลำดับที่", "หมายเลขครุภัณฑ์", "รายการ", "ได้รับมาเมื่อ", "ราคาที่ได้มา"])
    ws.append(["กองคลัง"])
    ws.append([1, "416-56-0001", "เครื่องคอมพิวเตอร์ Lenovo", "01 ตุลาคม 2555", 25000])
    ws.append([2, "482-58-0020/1", "กล้องวงจรปิดพร้อมเลนส์", "01 ตุลาคม 2565", 9000])
    ws2 = wb.create_sheet("บัญชี4 พร้อมใช้งาน")
    ws2.append(["ลำดับ", "หมายเลขครุภัณฑ์", "รายการ", "ได้รับมาเมื่อ", "ราคาที่ได้มา"])
    ws2.append(["สำนักปลัด"])
    ws2.append([1, "400-69-0001", "โต๊ะทำงาน", "01 ตุลาคม 2568", 5000])
    ws2.append([2, "416-56-0001", "เครื่องคอมพิวเตอร์ Lenovo", "01 ตุลาคม 2555", 25000])        # เลขซ้ำ
    p = tmp_path / "x.xlsx"
    wb.save(p)
    st = s.import_inspection_xlsx(p)
    assert st["added"] == 4 and st["sheets"]["บัญชี 1ชำรุด"] == 2
    a = {x["number"]: x for x in s.assets()}
    assert a["416-56-0001"]["category"] == "ครุภัณฑ์คอมพิวเตอร์" and a["416-56-0001"]["department"] == "กองคลัง"
    assert a["482-58-0020/1"]["life_years"] == 5 and a["400-69-0001"]["life_years"] == 12   # ชนิดย่อย: กล้องวงจรปิด
    assert "416-56-0001#2" in a
    info = s.asset_life(a["416-56-0001"], dt.date(2026, 11, 26))
    assert info["state"] == "หมดอายุแล้ว" and info["color"] == "#F8C9C4"
    assert "ขายทอดตลาด" in s.suggestion(a["416-56-0001"], info)
    assert L.life_state(dt.date(2027, 6, 1), dt.date(2026, 11, 26))[0] == "เหลือไม่เกิน 1 ปี"
    assert L.life_state(dt.date(2030, 1, 1), dt.date(2026, 11, 26))[1] == "#D5F0DD"
    rep = R.lifecycle_report(s)
    assert "กองคลัง · ปีงบประมาณ 2556" in rep.html()
