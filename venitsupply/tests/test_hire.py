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
    assert s.seed_structure() == 7
    tops = s.divisions()
    assert [d["name"] for d in tops][:2] == ["สำนักปลัด", "กองคลัง"] and len(tops) == 7
    edu = next(d for d in tops if d["name"].startswith("กองการศึกษา"))
    subs = [d["name"] for d in s.divisions(all_levels=True) if edu["id"] in [u["id"] for u in s.chain(d["id"])]]
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
    assert len(s.divisions()) == 7
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
    assert "ว 727" in html[1] and "10. การกำหนดระยะเวลารับประกัน" in html[1]
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
    assert h.summ.t.rowCount() == 8                       # 7 ส่วนราชการ + รวม
    for tab in (h.std, h.ana):
        h.tabs.setCurrentWidget(tab)
    assert h.ana.t.rowCount() > 100
    h.tabs.setCurrentWidget(h.cons)
    h.cons.t.selectRow(0)
    assert h.cons.months.rowCount() == 12
    h.tabs.setCurrentWidget(h.jobs)
    h.jobs.t.selectRow(next(r for r in range(h.jobs.t.rowCount()) if h.jobs.t.item(r, 0).text() == "กองคลัง"))
    assert "1.1" in h.jobs.result.text()
    w.go(w.pages.index(w.procs))
    w.procs.fy.setValue(2570)
    w.procs.div.setCurrentIndex(w.procs.div.findText("กองคลัง"))
    assert w.procs.t.rowCount() >= 1
    w.close()
    qa.processEvents()


def test_manpower_structure_from_plan():
    """แผนอัตรากำลัง 3 ปี (2570–2572) อบต.ไม้ขาว: กรอบ 211 (ไม่รวมปลัด/รองปลัด) ว่าง 34 ตามบัญชีจัดคนลงสู่ตำแหน่ง."""
    s = Store()
    n = s.seed_manpower()
    assert n["frame"] == 211 and n["vacant"] == 34
    got = {d["name"]: s.unit_analysis(d["id"]) for d in s.divisions()}
    assert {k: v["frame"] for k, v in got.items()} == {
        "สำนักปลัด": 66, "กองคลัง": 24, "กองช่าง": 34, "กองสาธารณสุขและสิ่งแวดล้อม": 39,
        "กองการศึกษา ศาสนา และวัฒนธรรม": 36, "กองสวัสดิการสังคม": 10, "หน่วยตรวจสอบภายใน": 2}
    assert {k: v["vacant"] for k, v in got.items()} == {
        "สำนักปลัด": 5, "กองคลัง": 5, "กองช่าง": 7, "กองสาธารณสุขและสิ่งแวดล้อม": 8,
        "กองการศึกษา ศาสนา และวัฒนธรรม": 7, "กองสวัสดิการสังคม": 1, "หน่วยตรวจสอบภายใน": 1}
    units = {d["name"]: d["id"] for d in s.divisions(all_levels=True)}
    steps = [r[0] for r in s.route(units["งานทะเบียนทรัพย์สินและพัสดุ"])]
    assert steps == ["ผู้เสนอ", "ความเห็นหัวหน้าฝ่ายการเงินและบัญชี", "ความเห็นเจ้าหน้าที่",
                     "ความเห็นผู้อำนวยการกองคลัง/หัวหน้าเจ้าหน้าที่", "ความเห็นปลัด", "คำสั่ง"]
    steps = [r[0] for r in s.route(units["งานป้องกันและบรรเทาสาธารณภัย"])]
    assert steps[1:3] == ["ความเห็นหัวหน้าฝ่ายป้องกันและบรรเทาสาธารณภัย", "ความเห็นหัวหน้าสำนักปลัด"]
    with pytest.raises(ValueError):
        s.save_position(dict(division_id=units["งานบัญชี"], title="x", count=1, occupied=2))


def test_standard_paste_and_workload_need():
    from venitsupply import manpower as M
    items = M.parse_standard("หน้าที่และความรับผิดชอบหลัก\nปฏิบัติงาน…\n๑. ด้านการปฏิบัติการ\n๑.๑ งานหนึ่ง\nต่อบรรทัด\n"
                             "1.2 งานสอง\n๒. ด้านการวางแผน\n๒.๑ วางแผน\n๓. ด้านการประสานงาน\n๓.๑ ประสาน\n"
                             "๔. ด้านการบริการ\nให้คำแนะนำ\nคุณสมบัติเฉพาะสำหรับตำแหน่ง\nไม่เอา")
    assert items == [("ด้านการปฏิบัติการ", "งานหนึ่ง ต่อบรรทัด"), ("ด้านการปฏิบัติการ", "งานสอง"),
                     ("ด้านการวางแผน", "วางแผน"), ("ด้านการประสานงาน", "ประสาน"), ("ด้านการบริการ", "ให้คำแนะนำ")]
    assert M.parse_standard(M.SAMPLE_STANDARD[1])[7][0] == "ด้านการปฏิบัติการ" and len(M.parse_standard(
        M.SAMPLE_STANDARD[1])) == 14
    assert M.base_title("นักวิชาการพัสดุ (ปก./ชก.)") == "นักวิชาการพัสดุ" and M.need_people(2.49) == 2
    assert M.need_people(2.5) == 3 and M.need_people(0.2) == 1 and M.need_people(0) == 0
    s = Store()
    s.seed_manpower()
    units = {d["name"]: d["id"] for d in s.divisions(all_levels=True)}
    pos = next(p for p in s.positions(units["งานทะเบียนทรัพย์สินและพัสดุ"]) if p["title"] == "เจ้าพนักงานพัสดุ")
    assert s.import_standard("เจ้าพนักงานพัสดุ (ปง./ชง.)", "๑. ด้านการปฏิบัติการ\n๑.๑ จัดซื้อจัดจ้าง\n๑.๒ ทะเบียนพัสดุ\n"
                             "๒. ด้านการวางแผน\n๒.๑ แผนจัดซื้อ") == 3
    rows = s.load_rows_from_standard(pos["id"])
    assert [r["task"] for r in rows] == ["จัดซื้อจัดจ้าง", "ทะเบียนพัสดุ", "แผนจัดซื้อ"]     # ค่าว่าง: เจ้าหน้าที่เติมเอง
    assert s.position_analysis(pos["id"])["need"] is None
    rows[0].update(minutes=90, volume=1500)      # 1.63
    rows[1].update(minutes=60, volume=1200)      # 0.87
    s.set_pos_load(pos["id"], rows[:2])
    a = s.position_analysis(pos["id"])
    assert a["fte"] == 2.5 and a["need"] == 3 and a["occupied"] == 2 and a["short"] == 1 and a["vacant"] == 0
    assert s.unit_analysis(units["กองคลัง"])["short"] == 1
    jid = s.job_from_position(pos["id"], units["กองคลัง"])
    assert s.job(jid)["title"] == "ปฏิบัติงานด้านทะเบียนทรัพย์สินและพัสดุ"
    assert [t["volume"] for t in s.tasks(jid)] == [300, 240] and s.workload(jid)["fte"] == 0.5   # เฉพาะส่วนที่เกิน 0.5 คน
    assert [t["side"] for t in s.tasks(jid)] == ["ด้านการปฏิบัติการ"] * 2
    did = s.duties("เจ้าพนักงานพัสดุ")[0]["id"]
    s.save_duty(dict(text="จัดซื้อจัดจ้างผ่าน e-GP"), did)                      # แก้ในมาตรฐาน → ภาระงาน/งานจ้างตาม
    assert s.pos_load(pos["id"])[0]["task"] == "จัดซื้อจัดจ้างผ่าน e-GP" == s.tasks(jid)[0]["task"]
    s.delete_duty(did)
    assert len(s.pos_load(pos["id"])) == 1


def test_word_excel_and_memos(tmp_path):
    import zipfile
    from venitsupply import demo, hire_reports as HR, reports as R
    s = demo.fill(Store())
    c = s.contracts(2570)[0]
    memo = HR.hire_approval_memo(s, c["id"]).html()
    assert "บันทึกข้อความ" in memo and "1. เรื่องเดิม" in memo and "ว 877" in memo and "4.2 เห็นควรมอบหมายให้" in memo
    assert "ความเห็นปลัด" in memo and "แผนงานแผนงาน" not in memo
    assert "รายงานผลการดำเนินการจัดทำร่างขอบเขตของงาน" in HR.tor_report_memo(s, c["id"]).html()
    assert "แบบ บก.06" in HR.price_report_memo(s, c["id"]).html()
    rep = HR.manpower_report(s)
    assert "211" in rep.html()
    pid = s.q("SELECT id FROM positions WHERE title='เจ้าพนักงานพัสดุ'")[0]["id"]
    for r, name in ((HR.hire_approval_memo(s, c["id"]), "m"), (rep, "a"), (HR.position_workload_sheet(s, pid), "w"),
                    (HR.tor(s, c["job_id"], contract=c), "t"), (HR.contract_doc(s, c["id"]), "c")):
        R.to_docx(r, tmp_path / f"{name}.docx")
        R.to_xlsx(r, tmp_path / f"{name}.xlsx")
        with zipfile.ZipFile(tmp_path / f"{name}.docx") as z:
            xml = z.read("word/document.xml").decode("utf-8")
            assert "TH SarabunPSK" in xml and "<w:tbl>" in xml or name in ("m", "t", "c")
    with zipfile.ZipFile(tmp_path / "w.xlsx") as z:
        x = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "<f>C5*D5</f>" in x and "ROUND(E5/82800,2)" in x and "SUM(F" in x
    assert "เอกสารหมายเลข 5" in HR.position_history_sheet(s, pid).html()


def test_thai_dates_be():
    """วันที่ พ.ศ.: พิมพ์ได้หลายแบบ ปีผิดไม่ยอมรับ ไม่มีปีเพี้ยน (2295)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from venitsupply.widgets import ThaiDateEdit, parse_be
    QApplication.instance() or QApplication([])
    d = H._dt.date
    for s in ("1/10/2569", "1/10/69", "๑/๑๐/๒๕๖๙", "1 ต.ค. 2569", "1 ตุลาคม 2569", "1-10-2569", "1/10/2026"):
        assert parse_be(s) == d(2026, 10, 1), s
    for s in ("31/2/2569", "1/10/2295", "", "abc"):
        assert parse_be(s) is None
    w = ThaiDateEdit("")
    assert w.iso() == str(d.today()) and w.edit.text().endswith(str(d.today().year + 543))
    w.set_iso("1752-09-14")                                        # ค่าต่ำสุดเก่าของ QDateEdit → ใช้วันนี้
    assert w.iso() == str(d.today())
    w.edit.setText("30/9/2570")
    w._typed()
    assert w.iso() == "2027-09-30" and w.edit.text() == "30/9/2570"


def test_budget_year_no_crossing():
    """งบประมาณปีไหนใช้ปีนั้น: ขอ/อนุมัติ/ก่อหนี้ในปีเท่านั้น; ตรวจรับ/เบิกจ่ายข้ามปีได้เมื่อก่อหนี้แล้ว."""
    s = _store()
    item = next(b for b in s.budget_items(2570) if b["category"] == "วัสดุ" or b["name"] == "วัสดุสำนักงาน")
    with pytest.raises(ValueError, match="ปีงบประมาณ พ.ศ. 2571"):
        s.save_procurement(dict(kind="ซื้อ", title="x", budget_item_id=item["id"], amount=1000,
                                date_request="2027-10-05"))
    pid = s.save_procurement(dict(kind="ซื้อ", title="x", budget_item_id=item["id"], amount=1000,
                                  date_request="2027-09-20"))
    with pytest.raises(ValueError, match="ห้ามข้ามปี"):
        s.approve(pid, "2027-10-01")
    s.approve(pid, "2027-09-21")
    with pytest.raises(ValueError, match="ห้ามข้ามปี"):
        s.order(pid, "ร้าน", 1000, date="2027-10-02")
    s.order(pid, "ร้าน", 1000, date="2027-09-25")
    s.inspect_proc(pid, "2027-10-10")                              # เบิกเหลื่อมปี: ก่อหนี้ไว้แล้วในปี 2570
    s.pay(pid, date="2027-10-15")
    assert s.procurement(pid)["status"] == "เบิกจ่ายแล้ว" and s.balance(item["id"])["paid"] >= 1000


def test_merge_structure_and_bundled_standards():
    """ไฟล์ที่เจ้าหน้าที่สร้าง «คลัง» ไว้เอง: เติมครบทุกกองโดยไม่ลบของเดิม + มาตรฐานกำหนดตำแหน่ง 98 ตำแหน่ง."""
    s = Store()
    s.set_setting("org_name", "องค์การบริหารส่วนตำบลไม้ขาว")
    own = s.save_division(dict(kind="กอง", name="คลัง"))
    s.save_position(dict(division_id=own, title="ผู้อำนวยการกอง", count=1, occupied=1))
    out = s.ensure_manpower()
    tops = {d["name"]: d for d in s.divisions()}
    assert len(tops) == 7 and tops["กองคลัง"]["id"] == own and "คลัง" in tops["กองคลัง"]["aliases"]
    assert out["standards"] == 1019 and s.ensure_manpower() == dict(units=0, positions=0, standards=0)   # ครั้งเดียว
    assert any(p["title"] == "ผู้อำนวยการกอง" for p in s.positions(own))                               # ของเดิมอยู่ครบ
    assert s.unit_analysis(own)["frame"] == 25                                                           # 24 + 1 ของเดิม
    assert s.standard_for("ผู้ช่วยเจ้าพนักงานพัสดุ") == "เจ้าพนักงานพัสดุ"
    assert not s.q("SELECT 1 FROM duties WHERE title LIKE 'นักบริหารงาน%'")       # ไม่ใช้สายบริหาร/อำนวยการ
    head = next(p for p in s.positions(own) if p["is_head"])
    a = s.position_analysis(head["id"])
    assert a["excluded"] and s.unit_analysis(own)["positions"] == 17     # 20 แถวตำแหน่ง + 1 ของเดิม − ผอ./หัวหน้าฝ่าย 4
    rows = s.duty_rows("นักวิชาการพัสดุ")
    assert rows[0]["no"] == "1.1" and any(r["level"] == 1 and r["no"].count(".") == 2 for r in rows)
    units = {d["name"]: d["id"] for d in s.divisions(all_levels=True)}
    pos = next(p for p in s.positions(units["งานทะเบียนทรัพย์สินและพัสดุ"]) if p["title"] == "ผู้ช่วยเจ้าพนักงานพัสดุ")
    load = s.load_rows_from_standard(pos["id"])
    assert load and all(r["side"] in ("ด้านการปฏิบัติการ", "ด้านการบริการ") for r in load)
    heads = [r for r in load if r["kind"] == "head"]
    leaves = [r for r in load if r["kind"] == "leaf"]
    assert leaves and all(r["minutes"] == 0 for r in leaves)                 # เจ้าหน้าที่เติมเอง
    main = s.q("SELECT id FROM duties WHERE title='เจ้าพนักงานพัสดุ' AND parent_id IS NULL ORDER BY seq")[0]["id"]
    sub = s.save_duty(dict(parent_id=main, text="จัดซื้อวัสดุสำนักงาน"))
    load2 = s.load_rows_from_standard(pos["id"])
    assert len([r for r in load2 if r["kind"] == "head"]) == len(heads) + (0 if any(
        h["duty_id"] == main for h in heads) else 1)
    assert any(r["duty_id"] == sub and r["no"].count(".") == 2 for r in load2)
    s.delete_duty(main)
    assert not s.q("SELECT 1 FROM duties WHERE id=?", (sub,))


def test_propose_subs():
    from venitsupply.manpower import propose_subs
    subs = propose_subs("ตรวจสอบ ปรับปรุงแก้ไข ซ่อมแซม บำรุงรักษาในงานด้านการช่างต่าง ๆ เช่น ถนน สะพาน ทางเท้า "
                        "และสิ่งสาธารณประโยชน์อื่นๆ เพื่อให้เป็นไปตามบทบัญญัติของกฎหมาย")
    assert subs[:2] == ["ตรวจสอบ ปรับปรุงแก้ไข ซ่อมแซม บำรุงรักษา — ถนน", "ตรวจสอบ ปรับปรุงแก้ไข ซ่อมแซม บำรุงรักษา — สะพาน"]
    assert propose_subs("วางแผนการทำงานที่รับผิดชอบ เพื่อให้งานสำเร็จ") == []
