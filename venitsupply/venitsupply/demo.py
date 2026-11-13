# SPDX-License-Identifier: GPL-3.0-or-later
"""ข้อมูลตัวอย่างสำหรับทดลองใช้ (สมมติทั้งหมด)."""
from __future__ import annotations

from .db import Store


def fill(s: Store) -> Store:
    st = dict(org_name="สำนักงานทดลองใช้โปรแกรม (ข้อมูลสมมติ)", org_code="0701",
              officer="นางสาวพัสดุ ตัวอย่าง", head_officer="นายหัวหน้า ทดลอง", head="นายผู้อำนวยการ สมมติ",
              head_pos="ผู้อำนวยการ")
    for k, v in st.items():
        s.set_setting(k, v)
    cat = {c["code"]: c["id"] for c in s.categories("asset")}
    mcat = {c["code"]: c["id"] for c in s.categories("material")}
    A = [("01", "โต๊ะทำงานเหล็ก", "Lucky", "DX-1", "", 12500, "2022-03-15", "งานธุรการ", "ห้องธุรการ", "นายเอ ใจดี"),
         ("01", "ตู้เหล็กเก็บเอกสาร 4 ลิ้นชัก", "Elephant", "F4", "", 6900, "2023-01-10", "งานธุรการ", "ห้องธุรการ", "นายเอ ใจดี"),
         ("11", "เครื่องคอมพิวเตอร์ สำหรับงานประมวลผล", "Dell", "OptiPlex 7010", "CN-7Q2", 28000, "2024-11-20", "งานสำรวจ", "ห้องสำรวจ", "นายบี มั่นคง"),
         ("11", "เครื่องพิมพ์เลเซอร์", "Brother", "HL-L2370", "E7832", 8900, "2025-02-05", "งานสำรวจ", "ห้องสำรวจ", "นายบี มั่นคง"),
         ("07", "กล้องประมวลผลรวม (Total Station)", "Topcon", "GM-52", "TS1180", 285000, "2021-06-01", "งานสำรวจ", "คลังเครื่องมือ", "นายซี แม่นยำ"),
         ("07", "กล้องระดับอัตโนมัติ", "Sokkia", "B40A", "LV221", 45000, "2023-08-18", "งานสำรวจ", "คลังเครื่องมือ", "นายซี แม่นยำ"),
         ("02", "รถยนต์บรรทุก (ดีเซล) ขนาด 1 ตัน", "Toyota", "Hilux Revo", "กข 1234", 789000, "2020-10-01", "งานธุรการ", "โรงจอดรถ", "นายดี ขับดี"),
         ("03", "เครื่องปรับอากาศ 18,000 บีทียู", "Daikin", "FTKC18", "AC9981", 26500, "2022-04-02", "งานการเงิน", "ห้องการเงิน", "นางอี รอบคอบ")]
    ids = []
    for c, name, brand, model, serial, price, date, dept, loc, who in A:
        ids.append(s.save_asset(dict(category_id=cat[c], name=name, brand=brand, model=model, serial=serial,
                                     price=price, acquire_date=date, department=dept, location=loc,
                                     custodian=who, method="วิธีเฉพาะเจาะจง", budget="เงินงบประมาณ")))
    M = [("M01", "กระดาษถ่ายเอกสาร A4 80 แกรม", "รีม", 20, [(50, 115), (40, 120)], 75),
         ("M01", "ปากกาลูกลื่น สีน้ำเงิน", "ด้าม", 24, [(100, 6)], 60),
         ("M10", "ตลับหมึกเครื่องพิมพ์เลเซอร์", "กล่อง", 2, [(6, 1890)], 5),
         ("M11", "หมุดหลักฐานคอนกรีต", "อัน", 50, [(200, 85)], 120),
         ("M06", "น้ำมันดีเซล", "ลิตร", 100, [(500, 31.94)], 380)]
    for c, name, unit, mn, ins, out in M:
        m = s.save_material(dict(name=name, unit=unit, min_qty=mn, category_id=mcat[c], location="คลังพัสดุ"))
        for i, (q, p) in enumerate(ins):
            s.receive(m, f"2026-10-0{1 + i * 3}", q, p, f"ตร.{i + 1}/2570", "ห้างหุ้นส่วนตัวอย่าง")
        s.issue(m, "2026-10-20", out, "บ.15/2570", "นายบี มั่นคง", "งานสำรวจ")
    s.lend(ids[5], "นายเอฟ ออกภาคสนาม", "2026-10-25", "2026-11-05", "สำรวจแนวถนน", "งานสำรวจ")
    s.lend(ids[4], "นายจี ทดลอง", "2026-11-10", "2026-11-30", "วางหมุดหลักฐาน", "งานสำรวจ")
    for a in ids[:5]:
        s.inspect(2569, a, "ใช้งานได้ปกติ", "2026-10-15")
    s.inspect(2569, ids[7], "ชำรุด", "2026-10-15", "คอมเพรสเซอร์เสีย")
    budget(s)
    return s


def budget(s: Store):
    """ข้อบัญญัติงบประมาณรายจ่ายจริงของ อบต.ไม้ขาว ปี 2570 (พร้อมปี 2569 และรายจ่ายจริง 2567–2568)
    และรายการจัดซื้อจัดจ้างตัวอย่าง — รายการจัดซื้อจัดจ้างเป็นข้อมูลสมมติทั้งหมด."""
    import datetime as _dt
    from pathlib import Path

    from . import budget as B
    s.set_setting("org_name", "องค์การบริหารส่วนตำบลไม้ขาว (ทดลองใช้ — รายการจัดซื้อจัดจ้างเป็นข้อมูลสมมติ)")
    s.set_setting("org_address", "100 หมู่ที่ 5 ถนนเทพกระษัตรี ตำบลไม้ขาว อำเภอถลาง จังหวัดภูเก็ต 83110")
    s.import_ordinance(B.read_table(Path(B.__file__).resolve().parent / "data" / "maikhao_2570.csv"))

    def find(fy, name, task="งานบริหารทั่วไป", type_=None):
        for b in s.budget_items(fy):
            if (task is None or b["task"] == task) and (b["name"] == name or name in b["name"]) \
                    and (type_ is None or type_ in b["type"]):
                return b["id"]
        raise KeyError(name)

    s.transfer(find(2570, "วัสดุคอมพิวเตอร์"), find(2570, "วัสดุสำนักงาน"), 15000,
               "2026-11-05", "คำสั่งโอน 1/2570", "เพิ่มค่ากระดาษ (ตัวอย่าง)")
    cat = {c["code"]: c["id"] for c in s.categories("asset")}
    mcat = {c["code"]: c["id"] for c in s.categories("material")}

    def proc(bid, kind, title, d, lines=None, amount=None, vendor="ร้านตัวอย่างพาณิชย์", contract=None,
             due=None, paid=True, inspect=True, stop=None):
        pid = s.save_procurement(dict(kind=kind, title=title, budget_item_id=bid, date_request=d,
                                      amount=amount or 0, reason="เพื่อใช้ในราชการ", requester="สำนักปลัด",
                                      committee="นายตรวจรับ ตัวอย่าง"), lines=lines)
        if stop == "request":
            return pid
        s.approve(pid, d)
        if stop == "approve":
            return pid
        s.order(pid, vendor, contract or s.procurement(pid)["amount"], date=d, due_date=due or d)
        if inspect:
            s.inspect_proc(pid, due or d, fine=0)
        if paid:
            s.pay(pid, date=due or d)
        return pid

    # ปี 2569: น้ำมันรายเดือน วัสดุสำนักงานรายไตรมาส จ้างเหมาบริการทั้งปี
    fuel, office, hire = (find(2569, n) for n in ("วัสดุเชื้อเพลิงและหล่อลื่น", "วัสดุสำนักงาน", "ค่าจ้างเหมาบริการ"))
    for mth in range(10, 22):
        yy, mm = 2025 + (mth - 1) // 12, (mth - 1) % 12 + 1
        d = _dt.date(yy, mm, 8).isoformat()
        proc(fuel, "ซื้อ", "ซื้อน้ำมันเชื้อเพลิงประจำเดือน", d, amount=15000 + 900 * ((mth * 7) % 5),
             vendor="สหกรณ์การเกษตรตัวอย่าง")
        if mth % 3 == 0:
            proc(office, "ซื้อ", "ซื้อวัสดุสำนักงาน", d, amount=21000 + 2500 * (mth % 4))
    proc(hire, "จ้าง", "จ้างเหมาบริการทำความสะอาดอาคารสำนักงาน", "2025-10-01", amount=300000,
         vendor="นางสาวสะอาด ตัวอย่าง")
    # ปี 2570 (ปัจจุบัน)
    fuel, office, hire = (find(2570, n) for n in ("วัสดุเชื้อเพลิงและหล่อลื่น", "วัสดุสำนักงาน", "ค่าจ้างเหมาบริการ"))
    proc(fuel, "ซื้อ", "ซื้อน้ำมันเชื้อเพลิงประจำเดือนตุลาคม", "2026-10-08", amount=15200,
         vendor="สหกรณ์การเกษตรตัวอย่าง")
    proc(fuel, "ซื้อ", "ซื้อน้ำมันเชื้อเพลิงประจำเดือนพฤศจิกายน", "2026-11-06", amount=14800,
         vendor="สหกรณ์การเกษตรตัวอย่าง")
    proc(office, "ซื้อ", "ซื้อกระดาษถ่ายเอกสารและหมึกพิมพ์", "2026-11-03",
         lines=[dict(name="กระดาษถ่ายเอกสาร A4 80 แกรม", qty=100, unit="รีม", unit_price=118, target="material",
                     category_id=mcat["M01"]),
                dict(name="ตลับหมึกเครื่องพิมพ์เลเซอร์", qty=4, unit="กล่อง", unit_price=1890, target="material",
                     category_id=mcat["M10"])], due="2026-11-10")
    h = proc(hire, "จ้าง", "จ้างเหมาบริการทำความสะอาดอาคาร ต.ค. 2569 – ก.ย. 2570", "2026-10-01",
             amount=324000, vendor="นางสาวสะอาด ตัวอย่าง", inspect=False, paid=False)
    s.pay(h, 27000, "2026-10-31", "ฎ.12/2570")
    proc(hire, "เช่า", "เช่าเครื่องถ่ายเอกสาร ต.ค. 2569 – ก.ย. 2570", "2026-10-02", amount=36000,
         vendor="บริษัทเครื่องถ่ายเอกสารตัวอย่าง จำกัด", inspect=False, paid=False)
    eq = next(b for b in s.budget_items(2570) if b["category"] == "ค่าครุภัณฑ์"
              and "คอมพิวเตอร์" in b["type"] and 20000 <= b["amount"] <= 120000)
    unit = round(eq["amount"] / 2, -2)
    proc(eq["id"], "ซื้อ", eq["name"][:80], "2026-11-11",
         lines=[dict(name=eq["name"][:80], qty=2, unit="เครื่อง", unit_price=unit, target="asset",
                     category_id=cat["11"])], stop="approve")
    road = max((b for b in s.budget_items(2570) if b["category"] == "ค่าที่ดินและสิ่งก่อสร้าง"),
               key=lambda b: b["amount"])
    proc(road["id"], "จ้าง", road["name"][:90], "2026-11-12", amount=road["amount"], stop="request")
