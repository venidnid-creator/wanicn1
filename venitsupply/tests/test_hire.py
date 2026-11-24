import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from venitsupply import budget as B  # noqa: E402
from venitsupply import hire as H  # noqa: E402
from venitsupply.db import Store  # noqa: E402


def _store():
    s = Store()
    s.import_ordinance(B.read_table(os.path.join(os.path.dirname(B.__file__), "data", "maikhao_2570.csv")))
    s.seed_structure()
    s.assign_divisions(2570)
    return s


def test_structure_crud():
    s = Store()
    assert s.seed_structure() == 6
    tops = s.divisions()
    assert [d["name"] for d in tops][:2] == ["สำนักปลัด", "กองคลัง"] and len(tops) == 6
    edu = next(d for d in tops if d["name"].startswith("กองการศึกษา"))
    subs = [d["name"] for d in s.divisions(edu["id"])]
    assert "ศูนย์พัฒนาเด็กเล็กตำบลไม้ขาว" in subs
    new = s.save_division(dict(kind="กอง", name="กองยุทธศาสตร์และงบประมาณ"))
    unit = s.save_division(dict(kind="ฝ่าย", name="ฝ่ายแผนงาน", parent_id=new))
    assert s.top_division(unit)["id"] == new
    with pytest.raises(ValueError):
        s.delete_division(new)                     # has a sub-unit
    pos = s.save_position(dict(division_id=unit, title="ผู้ช่วยนักวิเคราะห์นโยบายและแผน"))
    s.save_position(dict(title="ผู้ช่วยนักวิเคราะห์ฯ"), pos)
    s.delete_position(pos)
    s.delete_division(unit)
    s.delete_division(new)
    assert len(s.divisions()) == 6
    assert H.classify("ผู้ช่วยเจ้าพนักงานธุรการ") == ("ทั่วไป", "พนักงานจ้างตามภารกิจ")
    assert H.classify("นักวิชาการพัสดุ") == ("วิชาการ", "ข้าราชการ/พนักงานส่วนท้องถิ่น")
    with pytest.raises(ValueError):
        s.seed_structure()                         # only once unless replace=True


def test_budget_assigned_to_divisions():
    s = _store()
    names = {d["id"]: d["name"] for d in s.divisions()}
    rows = s.budget_items(2570)
    left = [b for b in rows if not b["division_id"]]
    assert len(left) <= 10                  # no marker anywhere in their «งาน»: the officer picks the กอง
    assert all(b["task"] in ("งานไฟฟ้าและประปา", "งานบำบัดน้ำเสีย") for b in left)
    hire = {(names[b["division_id"]], b["task"]): b["amount"] for b in rows if b["name"] == H.HIRE_ITEM}
    assert hire[("กองคลัง", "งานบริหารงานคลัง")] == 500000
    assert hire[("สำนักปลัด", "งานป้องกันและบรรเทาสาธารณภัย")] == 1800000
    assert hire[("กองการศึกษา ศาสนา และวัฒนธรรม", "งานระดับก่อนวัยเรียนและประถมศึกษา")] == 1400000
    fin = next(d for d in s.divisions() if d["name"] == "กองคลัง")
    assert s.division_budget(2570, fin["id"], hire_only=True)["budget"] == 500000
    assert s.hire_budget_items(2570, fin["id"])[0]["name"] == H.HIRE_ITEM


def test_workload_and_job_value():
    s = _store()
    fin = next(d for d in s.divisions() if d["name"] == "กองคลัง")
    jid = s.save_job(dict(division_id=fin["id"], title="ผู้ช่วยงานพัสดุ", line="ทั่วไป",
                          qualification="ปวส./อนุปริญญา", difficulty=5))
    s.set_tasks(jid, [("การจัดหา", 20, 1200), ("ตรวจรับ", 20, 1200), ("การเบิกจ่าย", 20, 1200),
                      ("การทำทะเบียนพัสดุ", 20, 1400)])
    w = s.workload(jid)
    assert w["rows"][0]["share"] == 0.29 and w["rows"][3]["share"] == 0.34      # 24,000 / 82,800
    assert w["fte"] == 1.21
    v = s.job_value(s.job(jid))
    assert v["base"] == 11500 and v["suggested"] == 12100 and v["daily"] == round(12100 / 30, 2)
    s.set_hire_rates([("ทั่วไป", "ปวส./อนุปริญญา", 12000)])
    assert s.job_value(s.job(jid))["suggested"] == 12600


def test_months_partial_and_full():
    plan = list(H.month_iter(H._dt.date(2026, 10, 16), H._dt.date(2027, 1, 31)))
    assert plan[0] == ("2026-10", 16, False) and plan[1] == ("2026-11", 30, True)
    assert plan[-1] == ("2027-01", 30, True)
    s = Store()
    m = s.plan_months("2026-10-16", "2027-01-31", 12000)
    assert m[0]["amount"] == 6400.0 and sum(x["amount"] for x in m) == 6400 + 3 * 12000


def test_contract_flow_by_division():
    s = _store()
    fin = next(d for d in s.divisions() if d["name"] == "กองคลัง")
    item = s.hire_budget_items(2570, fin["id"])[0]
    jid = s.save_job(dict(division_id=fin["id"], title="ผู้ช่วยงานพัสดุ", line="ทั่วไป", qualification="ปวส./อนุปริญญา"))
    cid = s.save_contract(dict(job_id=jid, division_id=fin["id"], budget_item_id=item["id"], person="นายทดสอบ ระบบ",
                               id_card="1234567890123", start="2026-10-01", end="2027-09-30", monthly=12000))
    c = s.contract(cid)
    assert c["contract_no"] == "1/2570" and s.procurement(c["proc_id"])["amount"] == 144000
    assert s.procurement(c["proc_id"])["division_id"] == fin["id"]
    assert s.balance(item["id"])["reserved"] == 144000
    with pytest.raises(ValueError):                 # across two fiscal years
        s.save_contract(dict(job_id=jid, division_id=fin["id"], budget_item_id=item["id"], person="ข",
                             start="2027-09-01", end="2027-10-31", monthly=10000))
    with pytest.raises(ValueError):                 # more than the กอง's budget
        s.save_contract(dict(job_id=jid, division_id=fin["id"], budget_item_id=item["id"], person="ค",
                             start="2026-10-01", end="2027-09-30", monthly=40000))
    s.sign_contract(cid, "2026-10-01")
    assert s.balance(item["id"])["committed"] == 144000
    assert s.inspect_month(cid, "2026-10") == 12000
    s.pay_month(cid, "2026-10", "2026-10-31", "ฎ.1/2570")
    assert s.balance(item["id"])["paid"] == 12000
    assert s.inspect_month(cid, "2026-11", days=20) == 8000            # 12,000 / 30 × 20
    s.pay_month(cid, "2026-11")
    with pytest.raises(ValueError):
        s.pay_month(cid, "2026-12")                                     # not inspected
    for mth in [x["month"] for x in s.months(cid)][2:]:
        s.inspect_month(cid, mth)
        s.pay_month(cid, mth)
    assert s.contract(cid)["status"] == "สิ้นสุด"
    assert s.balance(item["id"])["paid"] == 140000
    assert s.balance(item["id"])["available"] == 500000 - 140000      # unpaid days back to the budget
    summ = {x["division"]["name"]: x for x in s.hire_summary(2570)}
    assert summ["กองคลัง"]["paid"] == 140000 and summ["กองคลัง"]["contracts"] == 1


def test_hire_documents():
    from venitsupply import hire_reports as HR
    assert HR.baht_text(12500.5) == "หนึ่งหมื่นสองพันห้าร้อยบาทห้าสิบสตางค์"
    assert HR.baht_text(144000) == "หนึ่งแสนสี่หมื่นสี่พันบาทถ้วน"
    assert HR.baht_text(21) == "ยี่สิบเอ็ดบาทถ้วน" and HR.baht_text(1_000_001) == "หนึ่งล้านหนึ่งบาทถ้วน"
    s = _store()
    fin = next(d for d in s.divisions() if d["name"] == "กองคลัง")
    item = s.hire_budget_items(2570, fin["id"])[0]
    jid = s.save_job(dict(division_id=fin["id"], title="ผู้ช่วยงานพัสดุ", line="ทั่วไป", qualification="ปวส./อนุปริญญา"))
    s.set_tasks(jid, [("การจัดหา", 20, 1200), ("ตรวจรับ", 20, 1200)])
    cid = s.save_contract(dict(job_id=jid, division_id=fin["id"], budget_item_id=item["id"], person="นายทดสอบ ระบบ",
                               start="2026-10-16", end="2027-09-30", monthly=12000, bank="กรุงไทย"))
    s.sign_contract(cid, "2026-10-15")
    s.inspect_month(cid, "2026-10", date="2026-10-31")
    docs = [HR.workload_sheet(s, jid), HR.tor(s, jid), HR.bk06(s, jid, s.contract(cid)), HR.hire_request(s, cid),
            HR.contract_doc(s, cid), HR.monthly_inspection(s, cid, "2026-10"), HR.hire_register(s, 2570),
            HR.division_summary(s, 2570)]
    html = [d.html() for d in docs]
    assert "0.58" in html[0]                                       # 2 × 24,000 / 82,800 → 0.29 + 0.29
    assert "ว 727" in html[1] and "10. การรับประกัน" in html[1]
    assert "แบบ บก.06" in html[2] and "500,000.00" in html[2]
    assert "ข้อ 22" in html[3] and "ผู้อำนวยการกองคลัง" in html[3]
    assert "ข้อ 8 การบังคับค่าเสียหาย" in html[4] and "วันละ 400.00 บาท" in html[4] and "12 งวด" in html[4] and "11 เดือน 16 วัน" in html[4]
    assert "6,400.00" in html[5] and "16" in html[5]
    assert "1/2570" in html[6] and "กองคลัง" in html[7]


def test_hire_page_builds(tmp_path):
    """หน้าจอจ้างเหมาบุคคลเปิดได้ทุกแท็บกับข้อมูลตัวอย่าง (ไม่มีจอ: offscreen)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from venitsupply import app as A, demo
    qa = QApplication.instance() or QApplication([])
    path = str(tmp_path / "h.vsdb")
    demo.fill(Store(path)).close()
    w = A.MainWindow(path)
    h = w.hire
    w.go(w.pages.index(h))
    h.fy.setValue(2570)
    for tab in (h.summ, h.org, h.jobs, h.cons):
        h.tabs.setCurrentWidget(tab)
    assert h.summ.t.rowCount() == 7                       # 6 กอง + รวม
    h.tabs.setCurrentWidget(h.cons)
    h.cons.t.selectRow(0)
    assert h.cons.months.rowCount() == 12
    h.tabs.setCurrentWidget(h.jobs)
    h.jobs.t.selectRow(1)
    assert "1.21" in h.jobs.result.text()
    w.go(w.pages.index(w.procs))
    w.procs.fy.setValue(2570)
    w.procs.div.setCurrentIndex(w.procs.div.findText("กองคลัง"))
    assert w.procs.t.rowCount() >= 1
    w.close()
    qa.processEvents()
