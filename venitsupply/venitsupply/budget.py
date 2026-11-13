# SPDX-License-Identifier: GPL-3.0-or-later
"""งบประมาณรายจ่ายตามข้อบัญญัติ (องค์กรปกครองส่วนท้องถิ่น).

โครงสร้างตามรูปแบบข้อบัญญัติงบประมาณรายจ่าย:
แผนงาน → งาน → งบ → หมวด → ประเภท → รายการ/โครงการ (จำนวนเงิน)

ยอดเงินของแต่ละรายการ::

    ตามข้อบัญญัติ + โอนเพิ่ม − โอนลด + ข้อบัญญัติเพิ่มเติม = งบประมาณที่ใช้ได้
    งบประมาณที่ใช้ได้ − จองเงิน (ขอซื้อ/ขอจ้างที่อนุมัติ) − ก่อหนี้ผูกพัน (ใบสั่ง/สัญญา ยังไม่จ่าย)
                     − เบิกจ่ายแล้ว = คงเหลือ

รหัสและชื่อในรายการนี้เป็นค่าแนะนำ — ให้ตรวจกับข้อบัญญัติของหน่วยงานเสมอ
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from xml.etree import ElementTree as ET

from . import thaidate as TD

# แผนงาน (ด้าน) — รหัสตามที่ใช้ทั่วไปในข้อบัญญัติ อปท.
PLANS = [
    ("00110", "แผนงานบริหารงานทั่วไป"), ("00120", "แผนงานการรักษาความสงบภายใน"),
    ("00210", "แผนงานการศึกษา"), ("00220", "แผนงานสาธารณสุข"),
    ("00230", "แผนงานสังคมสงเคราะห์"), ("00240", "แผนงานเคหะและชุมชน"),
    ("00250", "แผนงานสร้างความเข้มแข็งของชุมชน"), ("00260", "แผนงานการศาสนาวัฒนธรรมและนันทนาการ"),
    ("00310", "แผนงานอุตสาหกรรมและการโยธา"), ("00320", "แผนงานการเกษตร"),
    ("00330", "แผนงานการพาณิชย์"), ("00410", "แผนงานงบกลาง"),
]
TASKS = [
    "งานบริหารทั่วไป", "งานวางแผนสถิติและวิชาการ", "งานบริหารงานคลัง",
    "งานบริหารทั่วไปเกี่ยวกับการรักษาความสงบภายใน", "งานป้องกันภัยฝ่ายพลเรือนและระงับอัคคีภัย",
    "งานบริหารทั่วไปเกี่ยวกับการศึกษา", "งานระดับก่อนวัยเรียนและประถมศึกษา",
    "งานบริหารทั่วไปเกี่ยวกับสาธารณสุข", "งานบริการสาธารณสุขและงานสาธารณสุขอื่น",
    "งานสวัสดิการสังคมและสังคมสงเคราะห์", "งานบริหารทั่วไปเกี่ยวกับเคหะและชุมชน",
    "งานไฟฟ้าถนน", "งานกำจัดขยะมูลฝอยและสิ่งปฏิกูล", "งานส่งเสริมและสนับสนุนความเข้มแข็งชุมชน",
    "งานกีฬาและนันทนาการ", "งานศาสนาวัฒนธรรมท้องถิ่น", "งานก่อสร้างโครงสร้างพื้นฐาน",
    "งานส่งเสริมการเกษตร", "งานอนุรักษ์แหล่งน้ำและป่าไม้", "งานกิจการประปา", "งบกลาง",
]
# งบ → หมวด → ประเภท
STRUCTURE = {
    "งบกลาง": {"งบกลาง": [
        "เงินสมทบกองทุนประกันสังคม", "เงินสมทบกองทุนเงินทดแทน", "เบี้ยยังชีพผู้สูงอายุ",
        "เบี้ยยังชีพคนพิการ", "เบี้ยยังชีพผู้ป่วยเอดส์", "สำรองจ่าย", "รายจ่ายตามข้อผูกพัน",
        "เงินสมทบกองทุนบำเหน็จบำนาญข้าราชการส่วนท้องถิ่น (กบท.)"]},
    "งบบุคลากร": {"เงินเดือน (ฝ่ายการเมือง)": ["เงินเดือนนายก/รองนายก", "เงินค่าตอบแทนสมาชิกสภา"],
                 "เงินเดือน (ฝ่ายประจำ)": ["เงินเดือนพนักงาน", "เงินเพิ่มต่าง ๆ ของพนักงาน",
                                          "ค่าจ้างลูกจ้างประจำ", "ค่าตอบแทนพนักงานจ้าง",
                                          "เงินเพิ่มต่าง ๆ ของพนักงานจ้าง"]},
    "งบดำเนินงาน": {
        "ค่าตอบแทน": ["ค่าตอบแทนผู้ปฏิบัติราชการอันเป็นประโยชน์แก่องค์กรปกครองส่วนท้องถิ่น",
                      "ค่าเบี้ยประชุม", "ค่าตอบแทนการปฏิบัติงานนอกเวลาราชการ", "ค่าเช่าบ้าน",
                      "เงินช่วยเหลือการศึกษาบุตร"],
        "ค่าใช้สอย": ["รายจ่ายเพื่อให้ได้มาซึ่งบริการ", "รายจ่ายเกี่ยวกับการรับรองและพิธีการ",
                      "รายจ่ายเกี่ยวเนื่องกับการปฏิบัติราชการที่ไม่เข้าลักษณะรายจ่ายหมวดอื่น ๆ",
                      "ค่าบำรุงรักษาและซ่อมแซม"],
        "ค่าวัสดุ": ["วัสดุสำนักงาน", "วัสดุไฟฟ้าและวิทยุ", "วัสดุงานบ้านงานครัว", "วัสดุก่อสร้าง",
                     "วัสดุยานพาหนะและขนส่ง", "วัสดุเชื้อเพลิงและหล่อลื่น", "วัสดุวิทยาศาสตร์หรือการแพทย์",
                     "วัสดุการเกษตร", "วัสดุโฆษณาและเผยแพร่", "วัสดุคอมพิวเตอร์", "วัสดุเครื่องแต่งกาย",
                     "วัสดุกีฬา", "วัสดุอาหารเสริม (นม)", "วัสดุสำรวจ", "วัสดุอื่น"],
        "ค่าสาธารณูปโภค": ["ค่าไฟฟ้า", "ค่าน้ำประปา ค่าน้ำบาดาล", "ค่าบริการโทรศัพท์",
                           "ค่าบริการไปรษณีย์", "ค่าบริการสื่อสารและโทรคมนาคม"]},
    "งบลงทุน": {
        "ค่าครุภัณฑ์": ["ครุภัณฑ์สำนักงาน", "ครุภัณฑ์ยานพาหนะและขนส่ง", "ครุภัณฑ์ไฟฟ้าและวิทยุ",
                        "ครุภัณฑ์โฆษณาและเผยแพร่", "ครุภัณฑ์การเกษตร", "ครุภัณฑ์ก่อสร้าง", "ครุภัณฑ์สำรวจ",
                        "ครุภัณฑ์วิทยาศาสตร์หรือการแพทย์", "ครุภัณฑ์งานบ้านงานครัว", "ครุภัณฑ์กีฬา",
                        "ครุภัณฑ์คอมพิวเตอร์", "ครุภัณฑ์การศึกษา", "ครุภัณฑ์ดนตรีและนาฏศิลป์",
                        "ครุภัณฑ์โรงงาน", "ครุภัณฑ์สนาม", "ครุภัณฑ์อื่น"],
        "ค่าที่ดินและสิ่งก่อสร้าง": ["ค่าก่อสร้างอาคารต่าง ๆ", "ค่าก่อสร้างสิ่งสาธารณูปโภค",
                                     "ค่าบำรุงรักษาและปรับปรุงที่ดินและสิ่งก่อสร้าง",
                                     "ค่าชดเชยสัญญาแบบปรับราคาได้ (ค่า K)"]},
    "งบรายจ่ายอื่น": {"รายจ่ายอื่น": ["รายจ่ายอื่น"]},
    "งบเงินอุดหนุน": {"เงินอุดหนุน": ["เงินอุดหนุนองค์กรปกครองส่วนท้องถิ่น", "เงินอุดหนุนส่วนราชการ",
                                      "เงินอุดหนุนเอกชน", "เงินอุดหนุนกิจการที่เป็นสาธารณประโยชน์"]},
}
GROUPS = list(STRUCTURE)
CATEGORIES = [c for g in STRUCTURE.values() for c in g]
# หมวดที่ใช้จัดซื้อจัดจ้างได้ (หมวดอื่น เช่น เงินเดือน เงินอุดหนุน ไม่ผ่านงานพัสดุ)
PROCUREMENT_CATEGORIES = ["ค่าใช้สอย", "ค่าวัสดุ", "ค่าครุภัณฑ์", "ค่าที่ดินและสิ่งก่อสร้าง",
                          "ค่าสาธารณูปโภค", "ค่าตอบแทน", "รายจ่ายอื่น"]
CHANGE_KINDS = ["โอนเพิ่ม", "โอนลด", "ข้อบัญญัติเพิ่มเติม", "ลดตามข้อบัญญัติเพิ่มเติม"]
LEVELS = ["plan", "task", "grp", "category", "type"]
LEVEL_NAMES = ["แผนงาน", "งาน", "งบ", "หมวด", "ประเภท"]

SQL = """
CREATE TABLE IF NOT EXISTS budget_items(
  id INTEGER PRIMARY KEY, fy INTEGER NOT NULL, plan TEXT NOT NULL, task TEXT NOT NULL,
  grp TEXT NOT NULL, category TEXT NOT NULL, type TEXT NOT NULL, name TEXT NOT NULL,
  amount REAL NOT NULL DEFAULT 0, note TEXT DEFAULT '', seq INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS budget_changes(
  id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL REFERENCES budget_items(id),
  date TEXT NOT NULL, kind TEXT NOT NULL, amount REAL NOT NULL, doc_no TEXT DEFAULT '',
  note TEXT DEFAULT '', pair INTEGER);
"""


class BudgetMixin:
    """Budget methods of :class:`venitsupply.db.Store`."""

    def _budget_init(self):
        self.con.executescript(SQL)

    # ------------------------------------------------------------ items
    BUDGET_FIELDS = ("fy", "plan", "task", "grp", "category", "type", "name", "amount", "note")

    def save_budget_item(self, data: dict, bid=None) -> int:
        d = {k: data[k] for k in self.BUDGET_FIELDS if k in data}
        for k in ("plan", "task", "grp", "category", "type", "name"):
            if k in d and not str(d[k]).strip():
                raise ValueError(f"กรอก{LEVEL_NAMES[LEVELS.index(k)] if k in LEVELS else 'รายการ'}ให้ครบ")
        if bid:
            self.run(f"UPDATE budget_items SET {','.join(f'{k}=?' for k in d)} WHERE id=?",
                     (*d.values(), bid))
            return bid
        return self.run(f"INSERT INTO budget_items({','.join(d)}) VALUES({','.join('?' * len(d))})",
                        tuple(d.values()))

    def delete_budget_item(self, bid):
        if self.one("SELECT 1 FROM procurements WHERE budget_item_id=? AND status<>'ยกเลิก'", (bid,)):
            raise ValueError("รายการนี้มีการจัดซื้อจัดจ้างอ้างอิงอยู่ ลบไม่ได้")
        self.con.execute("DELETE FROM budget_changes WHERE item_id=?", (bid,))
        self.run("DELETE FROM budget_items WHERE id=?", (bid,))

    def budget_years(self) -> list[int]:
        return [r["fy"] for r in self.q("SELECT DISTINCT fy FROM budget_items ORDER BY fy")]

    def budget_item(self, bid):
        return self.one("SELECT * FROM budget_items WHERE id=?", (bid,))

    def budget_items(self, fy, procurement_only=False):
        rows = self.q("SELECT * FROM budget_items WHERE fy=? ORDER BY seq, id", (fy,))   # ลำดับตามข้อบัญญัติ
        if procurement_only:
            rows = [r for r in rows if r["category"] in PROCUREMENT_CATEGORIES]
        return rows

    # ---------------------------------------------------------- changes
    def change_budget(self, bid, kind, amount, date=None, doc_no="", note="", pair=None) -> int:
        if kind not in CHANGE_KINDS:
            raise ValueError("ชนิดการเปลี่ยนแปลงไม่ถูกต้อง")
        amount = abs(float(amount))
        if amount <= 0:
            raise ValueError("จำนวนเงินต้องมากกว่า 0")
        signed = -amount if kind in ("โอนลด", "ลดตามข้อบัญญัติเพิ่มเติม") else amount
        if signed < 0 and self.balance(bid)["available"] + 1e-6 < amount:
            raise ValueError(f"คงเหลือไม่พอให้ลด (คงเหลือ {self.balance(bid)['available']:,.2f} บาท)")
        return self.run("INSERT INTO budget_changes(item_id,date,kind,amount,doc_no,note,pair) "
                        "VALUES(?,?,?,?,?,?,?)",
                        (bid, str(date or TD.today()), kind, signed, doc_no, note, pair))

    def transfer(self, from_id, to_id, amount, date=None, doc_no="", note=""):
        """โอนงบประมาณจากรายการหนึ่งไปอีกรายการ (บันทึกโอนลด/โอนเพิ่มคู่กัน)."""
        if from_id == to_id:
            raise ValueError("เลือกรายการต้นทางและปลายทางต่างกัน")
        a = self.change_budget(from_id, "โอนลด", amount, date, doc_no, note)
        b = self.change_budget(to_id, "โอนเพิ่ม", amount, date, doc_no, note, pair=a)
        self.run("UPDATE budget_changes SET pair=? WHERE id=?", (b, a))
        return a, b

    def budget_changes(self, bid=None, fy=None):
        sql = ("SELECT c.*, b.name, b.fy, b.category, b.type FROM budget_changes c "
               "JOIN budget_items b ON b.id=c.item_id WHERE 1=1")
        args = []
        if bid:
            sql += " AND c.item_id=?"
            args.append(bid)
        if fy:
            sql += " AND b.fy=?"
            args.append(fy)
        return self.q(sql + " ORDER BY c.date, c.id", args)

    def delete_change(self, cid):
        r = self.one("SELECT pair FROM budget_changes WHERE id=?", (cid,))
        if r and r["pair"]:
            self.con.execute("DELETE FROM budget_changes WHERE id=?", (r["pair"],))
        self.run("DELETE FROM budget_changes WHERE id=?", (cid,))

    # ---------------------------------------------------------- balance
    def balance(self, bid, exclude_proc=None, until=None) -> dict:
        """ยอดเงินของรายการ: approved, changes, budget, reserved, committed, paid, available."""
        b = self.budget_item(bid)
        if b is None:
            return dict(approved=0, changes=0, budget=0, reserved=0, committed=0, paid=0, available=0)
        dq = " AND date<=?" if until else ""
        da = (str(until),) if until else ()
        ch = self.one(f"SELECT IFNULL(SUM(amount),0) AS s FROM budget_changes WHERE item_id=?{dq}",
                      (bid, *da))["s"]
        reserved = committed = paid = 0.0
        for p in self.q("SELECT * FROM procurements WHERE budget_item_id=? AND status<>'ยกเลิก'", (bid,)):
            if exclude_proc and p["id"] == exclude_proc:
                continue
            pd = self.one("SELECT IFNULL(SUM(amount),0) AS s FROM payments WHERE proc_id=?"
                          + (" AND date<=?" if until else ""), (p["id"], *da))["s"]
            paid += pd
            if p["status"] in ("ขออนุมัติ", "อนุมัติแล้ว"):
                reserved += p["amount"] or 0
            elif p["status"] in ("ก่อหนี้ผูกพัน", "ตรวจรับแล้ว"):
                committed += max(0.0, (p["contract_amount"] or p["amount"] or 0) - pd)
            # เบิกจ่ายแล้ว: นับเฉพาะยอดที่จ่าย (ส่วนต่างที่ไม่ได้จ่ายคืนกลับเป็นคงเหลือ)
        budget = (b["amount"] or 0) + ch
        return dict(approved=b["amount"] or 0, changes=ch, budget=budget, reserved=reserved,
                    committed=committed, paid=paid,
                    available=round(budget - reserved - committed - paid, 2))

    def budget_summary(self, fy, level=None) -> list[dict]:
        """Every item with its balance; with *level* rolled up by that column."""
        rows = []
        for b in self.budget_items(fy):
            rows.append(dict(item=b) | self.balance(b["id"]))
        if not level:
            return rows
        keys = LEVELS[:LEVELS.index(level) + 1]
        out: dict[tuple, dict] = {}
        for r in rows:
            k = tuple(r["item"][x] for x in keys)
            t = out.setdefault(k, dict(key=k, approved=0, changes=0, budget=0, reserved=0,
                                       committed=0, paid=0, available=0, count=0))
            for f in ("approved", "changes", "budget", "reserved", "committed", "paid", "available"):
                t[f] += r[f]
            t["count"] += 1
        return list(out.values())

    def copy_budget_year(self, src_fy, dst_fy, with_amounts=True) -> int:
        n = 0
        for b in self.budget_items(src_fy):
            self.save_budget_item(dict(fy=dst_fy, plan=b["plan"], task=b["task"], grp=b["grp"],
                                       category=b["category"], type=b["type"], name=b["name"],
                                       amount=b["amount"] if with_amounts else 0, note=b["note"]))
            n += 1
        return n

    # ----------------------------------------------------------- import
    def import_budget(self, fy, rows) -> int:
        """rows: [แผนงาน, งาน, งบ, หมวด, ประเภท, รายการ, จำนวนเงิน, (หมายเหตุ)] — header skipped."""
        n = 0
        last = ["", "", "", "", ""]
        for r in rows:
            r = [str(x).strip() if x is not None else "" for x in r] + [""] * 8
            if not any(r[:7]):
                continue
            amt = _num(r[6])
            if amt is None:          # header or a text line
                continue
            for i in range(5):       # blank cells repeat the row above (merged cells)
                last[i] = r[i] or last[i]
            if not r[5]:
                continue
            self.save_budget_item(dict(fy=fy, plan=last[0], task=last[1], grp=last[2],
                                       category=last[3], type=last[4], name=r[5], amount=amt,
                                       note=r[7]))
            n += 1
        return n


def _num(s):
    s = str(s).replace(",", "").replace("บาท", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def read_table(path) -> list[list[str]]:
    """Rows of a .csv or .xlsx file (first sheet), no outside library."""
    path = str(path)
    if path.lower().endswith(".csv"):
        raw = open(path, "rb").read()
        for enc in ("utf-8-sig", "cp874"):
            try:
                return list(csv.reader(io.StringIO(raw.decode(enc))))
            except UnicodeDecodeError:
                continue
        raise ValueError("อ่านไฟล์ CSV ไม่ได้")
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")))
        sheet = sorted(n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml", n))[0]
        root = ET.fromstring(z.read(sheet))
    out = []
    for row in root.iter(f"{{{ns['m']}}}row"):
        cells = {}
        for c in row.findall("m:c", ns):
            col = re.match(r"[A-Z]+", c.get("r")).group(0)
            idx = 0
            for ch in col:
                idx = idx * 26 + ord(ch) - 64
            t = c.get("t")
            if t == "inlineStr":
                v = "".join(x.text or "" for x in c.iter(f"{{{ns['m']}}}t"))
            else:
                ve = c.find("m:v", ns)
                v = ve.text if ve is not None else ""
                if t == "s" and v:
                    v = shared[int(v)]
            cells[idx - 1] = v
        if cells:
            out.append([cells.get(i, "") for i in range(max(cells) + 1)])
    return out
