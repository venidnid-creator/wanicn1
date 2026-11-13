import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from venitsupply import budget as B  # noqa: E402
from venitsupply import procurement as P  # noqa: E402
from venitsupply.db import Store  # noqa: E402

FY = 2570


def item(s, name, amount, cat="ค่าวัสดุ", typ="วัสดุสำนักงาน", grp="งบดำเนินงาน"):
    return s.save_budget_item(dict(fy=FY, plan="แผนงานบริหารงานทั่วไป", task="งานบริหารทั่วไป",
                                   grp=grp, category=cat, type=typ, name=name, amount=amount))


def test_budget_balance_and_transfer():
    s = Store()
    a = item(s, "จัดซื้อวัสดุสำนักงาน", 100000)
    b = item(s, "จัดซื้อวัสดุคอมพิวเตอร์", 50000, typ="วัสดุคอมพิวเตอร์")
    s.transfer(a, b, 20000, "2026-11-01", "โอน 1/2570")
    assert s.balance(a)["budget"] == 80000 and s.balance(b)["budget"] == 70000
    with pytest.raises(ValueError):
        s.transfer(a, b, 90000)
    s.delete_change(s.budget_changes(a)[0]["id"])           # removes the pair too
    assert s.balance(b)["budget"] == 50000
    roll = s.budget_summary(FY, "category")
    assert roll[0]["budget"] == 150000 and roll[0]["count"] == 2


def test_procurement_flow_controls_money():
    s = Store()
    a = item(s, "จัดซื้อวัสดุสำนักงาน", 100000)
    pid = s.save_procurement(dict(kind="ซื้อ", title="ซื้อกระดาษ", budget_item_id=a,
                                  date_request="2026-11-02", method=P.suggest_method(30000)),
                             lines=[dict(name="กระดาษ A4", qty=200, unit="รีม", unit_price=150,
                                         target="material")])
    p = s.procurement(pid)
    assert p["number"] == "ซ.001/2570" and p["amount"] == 30000 and p["method"] == "วิธีเฉพาะเจาะจง"
    assert s.balance(a)["reserved"] == 30000 and s.balance(a)["available"] == 70000
    chk = s.check_budget(a, 50000)
    assert chk["available"] == 70000 and chk["after"] == 20000
    with pytest.raises(ValueError):
        s.save_procurement(dict(kind="ซื้อ", title="เกินงบ", budget_item_id=a, amount=80000))
    s.approve(pid, "2026-11-03")
    s.order(pid, "ร้านตัวอย่าง", 29000, "ซ.001/2570", "2026-11-05", "2026-11-10")
    bal = s.balance(a)
    assert bal["reserved"] == 0 and bal["committed"] == 29000 and bal["available"] == 71000
    fine = s.inspect_proc(pid, "2026-11-12")                 # 2 days late, 0.2 %/day
    assert fine == round(29000 * 0.002 * 2, 2)
    assert s.materials()[0]["qty"] == 200
    pay = s.pay(pid, date="2026-11-20", voucher_no="ฎ.15/2570")
    row = s.payments(pid)[0]
    assert row["id"] == pay and row["wht"] == round(29000 / 1.07 * 0.01, 2)
    assert row["net"] == round(29000 - row["wht"] - fine, 2)
    assert s.procurement(pid)["status"] == "เบิกจ่ายแล้ว"
    assert s.balance(a)["paid"] == 29000 and s.balance(a)["available"] == 71000
    with pytest.raises(ValueError):
        s.delete_budget_item(a)


def test_hire_rent_exchange_assets():
    s = Store()
    eq = item(s, "จัดซื้อเครื่องคอมพิวเตอร์", 60000, cat="ค่าครุภัณฑ์", typ="ครุภัณฑ์คอมพิวเตอร์",
              grp="งบลงทุน")
    cat = s.categories("asset")[10]["id"]
    old = s.save_asset(dict(name="คอมพิวเตอร์เครื่องเก่า", category_id=cat, price=20000,
                            acquire_date="2019-01-01"))
    pid = s.save_procurement(dict(kind="แลกเปลี่ยน", title="แลกเปลี่ยนคอมพิวเตอร์", budget_item_id=eq,
                                  exchange_asset_id=old, date_request="2026-12-01"),
                             lines=[dict(name="คอมพิวเตอร์ใหม่", qty=2, unit="เครื่อง", unit_price=12000,
                                         target="asset", category_id=cat)])
    s.approve(pid)
    s.order(pid, "บริษัทตัวอย่าง", 24000)
    s.inspect_proc(pid, "2026-12-10")
    assert s.asset(old)["status"] == "จำหน่ายแล้ว" and s.asset(old)["disposal_method"] == "แลกเปลี่ยน"
    assert len([a for a in s.assets() if a["name"] == "คอมพิวเตอร์ใหม่"]) == 2
    svc = item(s, "จ้างเหมาบริการ", 100000, cat="ค่าใช้สอย", typ="รายจ่ายเพื่อให้ได้มาซึ่งบริการ")
    h = s.save_procurement(dict(kind="จ้าง", title="จ้างทำความสะอาด", budget_item_id=svc, amount=60000,
                                date_request="2026-10-05"))
    s.approve(h)
    s.order(h, "นายจ้าง ตัวอย่าง", 60000, date="2026-10-06", vendor_vat=False)
    s.pay(h, 20000, "2026-11-30")                            # monthly instalments
    s.pay(h, 20000, "2026-12-31")
    assert s.procurement(h)["status"] == "ก่อหนี้ผูกพัน"
    assert s.balance(svc)["committed"] == 20000 and s.balance(svc)["paid"] == 40000
    assert s.payments(h)[0]["wht"] == 200.0                   # no VAT: 1 % of 20,000
    with pytest.raises(ValueError):
        s.pay(h, 30000)
    r = s.save_procurement(dict(kind="เช่า", title="เช่าเครื่องถ่ายเอกสาร", budget_item_id=svc, amount=30000,
                                rent_from="2026-10-01", rent_to="2027-09-30"))
    assert s.procurement(r)["number"] == "ช.001/2570"
    s.cancel(r, "ไม่ใช้แล้ว")
    assert s.balance(svc)["reserved"] == 0


def test_statistics():
    s = Store()
    a = item(s, "วัสดุ", 500000)
    for d, amt in (("2025-11-10", 10000), ("2026-11-03", 20000), ("2026-11-03", 5000), ("2026-12-01", 7000)):
        pid = s.save_procurement(dict(kind="ซื้อ", title="x", budget_item_id=a, amount=amt, date_request=d))
        s.approve(pid, d)
        s.order(pid, "ร้าน", amt, date=d)
        s.pay(pid, date=d)
    day = s.stats("day", year=2026, month=11)
    assert len(day) == 30 and day[2]["count"] == 2 and day[2]["paid"] == 25000
    mon = s.stats("month", fy=2570)
    assert mon[0]["label"].startswith("ต.ค.") and mon[1]["committed"] == 25000 and mon[2]["paid"] == 7000
    yr = s.stats("year", fy_from=2569, fy_to=2570)
    assert [y["paid"] for y in yr] == [10000, 32000]
    br = s.breakdown(2569, 2570, "method")
    assert br[0]["count"] == 4 and br[0]["paid"] == 42000


def test_import_table(tmp_path):
    from venitsupply import xlsx
    p = tmp_path / "b.xlsx"
    xlsx.write(p, [("งบ", [["แผนงาน", "งาน", "งบ", "หมวด", "ประเภท", "รายการ", "จำนวนเงิน"],
                           ["แผนงานบริหารงานทั่วไป", "งานบริหารทั่วไป", "งบดำเนินงาน", "ค่าวัสดุ",
                            "วัสดุสำนักงาน", "ค่าวัสดุสำนักงาน", 120000],
                           ["", "", "", "", "วัสดุคอมพิวเตอร์", "ค่าวัสดุคอมพิวเตอร์", "50,000"]])])
    s = Store()
    assert s.import_budget(FY, B.read_table(p)) == 2
    rows = s.budget_items(FY)
    assert rows[1]["category"] == "ค่าวัสดุ" and rows[1]["amount"] == 50000
    c = tmp_path / "b.csv"
    c.write_text("แผนงาน,งาน,งบ,หมวด,ประเภท,รายการ,จำนวนเงิน\nก,ข,ค,ค่าใช้สอย,ง,จ,\"1,000\"\n", encoding="utf-8")
    assert s.import_budget(2571, B.read_table(c)) == 1
    assert s.copy_budget_year(FY, 2572) == 2


def test_budget_reports():
    from venitsupply import reports as R
    s = Store()
    a = item(s, "จัดซื้อวัสดุสำนักงาน", 100000)
    pid = s.save_procurement(dict(kind="ซื้อ", title="ซื้อกระดาษ", budget_item_id=a, reason="ใช้ในสำนักงาน"),
                             lines=[dict(name="กระดาษ", qty=10, unit="รีม", unit_price=150)])
    s.approve(pid)
    s.order(pid, "ร้าน ก", 1500, due_date="2026-12-01")
    s.inspect_proc(pid, "2026-11-20", register=False)
    s.pay(pid, date="2026-11-21")
    req = R.proc_request(s, pid).html()
    assert "ข้อ 22" in req and "คงเหลือหลังครั้งนี้" in req and "98,500.00" in req
    for rep in (R.purchase_order(s, pid), R.inspection_doc(s, pid), R.proc_register(s, FY),
                R.payment_register(s, FY), R.budget_status(s, FY), R.budget_status(s, FY, "category"),
                R.stats_report(s, s.stats("month", fy=FY), "สถิติ", "")):
        assert "นายเวนิช" in rep.html()


def test_maikhao_ordinance_2570():
    """ข้อบัญญัติ อบต.ไม้ขาว 2570 ในชุดโปรแกรม: ยอดตรงกับข้อ 4 ทุกแผนงาน."""
    from venitsupply import reports as R
    path = os.path.join(os.path.dirname(B.__file__), "data", "maikhao_2570.csv")
    rows = B.read_table(path)
    s = Store()
    got = s.import_ordinance(rows)
    assert set(got["budget"]) == {2569, 2570} and set(got["actual"]) == {2567, 2568}
    plans = {r["key"][0]: r["budget"] for r in s.budget_summary(2570, "plan")}
    assert round(sum(plans.values())) == 205000000
    expect = {"แผนงานบริหารงานทั่วไป": 43090770, "แผนงานการรักษาความสงบภายใน": 12701580,
              "แผนงานการศึกษา": 27769330, "แผนงานสาธารณสุข": 7697460, "แผนงานสังคมสงเคราะห์": 3773160,
              "แผนงานเคหะและชุมชน": 19480040, "แผนงานสร้างความเข้มแข็งของชุมชน": 4422200,
              "แผนงานการศาสนา วัฒนธรรม และนันทนาการ": 8646280, "แผนงานอุตสาหกรรมและการโยธา": 40828020,
              "แผนงานการพาณิชย์": 7454460, "แผนงานงบกลาง": 29136700}
    assert {k: round(v) for k, v in plans.items()} == expect
    years, cmp = s.compare_years("plan")
    assert years == [2567, 2568, 2569, 2570]
    assert "จ่ายจริง 2567" in R.budget_compare(s, "category").html()
    again = s.import_ordinance(rows, replace=True)
    assert again == got and round(sum(r["budget"] for r in s.budget_summary(2570))) == 205000000


def test_ordinance_tool_header():
    rows = [["แผนงาน", "งาน", "งบ", "หมวด", "ประเภท", "รายการ", "ประมาณการ 2570", "หมายเหตุ"],
            ["ก", "ข", "งบดำเนินงาน", "ค่าวัสดุ", "วัสดุสำนักงาน", "วัสดุสำนักงาน", "1,000.00", ""],
            ["ก", "ข", "งบดำเนินงาน", "ค่าวัสดุ", "วัสดุอื่น", "วัสดุอื่น", "0", ""]]
    s = Store()
    assert s.import_ordinance(rows) == {"budget": {2570: 1}, "actual": {}}
    with pytest.raises(ValueError):
        s.import_ordinance([["แผนงาน", "งาน"]])
