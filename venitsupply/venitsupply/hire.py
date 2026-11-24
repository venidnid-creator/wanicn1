# SPDX-License-Identifier: GPL-3.0-or-later
"""จ้างเหมาบริการบุคคลธรรมดา แยกตามกอง (ไม่รวมงานก่อสร้าง).

หลักที่ใช้ (เอกสารที่เจ้าของส่งมา):
* หนังสือคณะกรรมการวินิจฉัยฯ ด่วนที่สุด ที่ กค (กวจ) 0405.2/ว 727 ลว. 22 ก.ย. 2569 — งานจ้างเหมาบริการ
  มุ่งผลสำเร็จของงาน ผู้รับจ้างมีอิสระ ไม่ใช่การจ้างแรงงาน จ่ายตามงวดหลังตรวจรับ; **ยกเว้น** ค่าปรับ
  (ระเบียบฯ ข้อ 162, 163) และหลักประกันสัญญา (ข้อ 168)
* แบบสัญญาจ้างงานบริการ (ประเภทจ้างเหมาบริการบุคคลธรรมดา) — ประกาศคณะกรรมการนโยบายฯ (ฉบับที่ 3)
  ราชกิจจานุเบกษา 21 ก.ย. 2569: จ่ายรายเดือน; เดือนไม่เต็มคิดรายวัน โดยถือว่าเดือนหนึ่งมี 30 วัน
* แนวทางร่าง TOR (กรมบัญชีกลาง) 10 หัวข้อ; ตารางราคากลาง แบบ บก.06
* บัญชีแสดงการคำนวณปริมาณงาน: นาทีต่อราย × ปริมาณต่อปี ÷ 82,800 นาที (230 วัน × 6 ชม.) = จำนวนคน
* หนังสือ มท 0808.2/ว 9636 ลว. 10 ก.ย. 2567 (หลักเกณฑ์การจ้างเหมาบริการของ อปท.) — อ้างอิงในเอกสาร;
  อัตราค่างานเป็นค่าเริ่มต้นที่แก้ได้ ต้องตรวจกับหนังสือสั่งการและมติ ก.อบต./ก.จ./ก.ท. ที่ใช้อยู่
"""
from __future__ import annotations

import calendar
import datetime as _dt
import json
import re

from . import thaidate as TD

WORK_MINUTES_YEAR = 82800            # 230 วัน × 6 ชั่วโมง × 60 นาที
LINES = ["วิชาการ", "ทั่วไป"]
KINDS = ["หัวหน้าส่วนราชการ", "ข้าราชการ/พนักงานส่วนท้องถิ่น", "ครู", "พนักงานจ้างตามภารกิจ",
         "พนักงานจ้างทั่วไป", "จ้างเหมาบริการ"]
UNIT_KINDS = ["กอง", "ฝ่าย", "หน่วยงานย่อย"]
# อัตราค่างานเริ่มต้น (บาท/เดือน) ตามสายและคุณวุฒิ — แก้ได้ในหน้าตั้งค่าของงานจ้างเหมา
DEFAULT_RATES = [
    ("วิชาการ", "ปริญญาโท", 17500), ("วิชาการ", "ปริญญาตรี", 15000),
    ("ทั่วไป", "ปวส./อนุปริญญา", 11500), ("ทั่วไป", "ปวช.", 10000),
    ("ทั่วไป", "ม.6 หรือเทียบเท่า", 9500), ("ทั่วไป", "ไม่กำหนดวุฒิ", 9000),
]
HIRE_ITEM = "ค่าจ้างเหมาบริการบุคคลภายนอก"
CONTRACT_STATUS = ["ร่าง", "ทำสัญญาแล้ว", "สิ้นสุด", "ยกเลิก"]

SQL = """
CREATE TABLE IF NOT EXISTS divisions(
  id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES divisions(id), kind TEXT DEFAULT 'กอง',
  name TEXT NOT NULL, aliases TEXT DEFAULT '', head_name TEXT DEFAULT '', head_pos TEXT DEFAULT '',
  officer_name TEXT DEFAULT '', officer_pos TEXT DEFAULT '', seq INTEGER DEFAULT 0, note TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS positions(
  id INTEGER PRIMARY KEY, division_id INTEGER NOT NULL REFERENCES divisions(id), title TEXT NOT NULL,
  line TEXT DEFAULT 'ทั่วไป', kind TEXT DEFAULT '', count INTEGER DEFAULT 1, note TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS hire_jobs(
  id INTEGER PRIMARY KEY, division_id INTEGER REFERENCES divisions(id), title TEXT NOT NULL,
  line TEXT DEFAULT 'ทั่วไป', qualification TEXT DEFAULT '', difficulty REAL DEFAULT 0,
  monthly REAL DEFAULT 0, background TEXT DEFAULT '', objective TEXT DEFAULT '',
  qualifications TEXT DEFAULT '', scope TEXT DEFAULT '', work_place TEXT DEFAULT '',
  work_hours TEXT DEFAULT 'วันจันทร์ถึงวันศุกร์ เวลา 08.30 น. ถึง 16.30 น.', note TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS hire_tasks(
  id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL REFERENCES hire_jobs(id), seq INTEGER DEFAULT 0,
  task TEXT NOT NULL, minutes REAL DEFAULT 0, volume REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS hire_contracts(
  id INTEGER PRIMARY KEY, job_id INTEGER REFERENCES hire_jobs(id), division_id INTEGER REFERENCES divisions(id),
  proc_id INTEGER REFERENCES procurements(id), budget_item_id INTEGER REFERENCES budget_items(id),
  contract_no TEXT DEFAULT '', sign_date TEXT, person TEXT NOT NULL, id_card TEXT DEFAULT '',
  address TEXT DEFAULT '', bank TEXT DEFAULT '', bank_branch TEXT DEFAULT '', account_name TEXT DEFAULT '',
  account_no TEXT DEFAULT '', start TEXT NOT NULL, end TEXT NOT NULL, monthly REAL NOT NULL,
  inspector TEXT DEFAULT '', status TEXT DEFAULT 'ร่าง', note TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS hire_months(
  id INTEGER PRIMARY KEY, contract_id INTEGER NOT NULL REFERENCES hire_contracts(id), month TEXT NOT NULL,
  days INTEGER NOT NULL, planned_days INTEGER NOT NULL, amount REAL NOT NULL, inspect_date TEXT,
  payment_id INTEGER, note TEXT DEFAULT '', UNIQUE(contract_id, month));
"""

# โครงสร้างตัวอย่าง อบต.ไม้ขาว (จากเว็บไซต์ อบต. — ไม่เก็บชื่อบุคคล)
MAIKHAO = [
    ("สำนักปลัด", "สำนักปลัด,สำนักลัด", [
        ("ฝ่าย", "ฝ่ายอำนวยการ"), ("ฝ่าย", "ฝ่ายปกครอง"), ("ฝ่าย", "ฝ่ายป้องกันและบรรเทาสาธารณภัย"),
        ("หน่วยงานย่อย", "หน่วยตรวจสอบภายใน")], [
        ("หัวหน้าสำนักปลัด (นักบริหารงานทั่วไป)", 1), ("นักทรัพยากรบุคคล", 2), ("นักวิเคราะห์นโยบายและแผน", 2),
        ("นักจัดการงานทั่วไป", 1), ("นักประชาสัมพันธ์", 1), ("นักป้องกันและบรรเทาสาธารณภัย", 1),
        ("นักจัดการงานเทศกิจ", 1), ("นักวิชาการคอมพิวเตอร์", 1), ("นักพัฒนาการท่องเที่ยว", 1),
        ("นักวิชาการตรวจสอบภายใน", 1), ("เจ้าพนักงานธุรการ", 2), ("เจ้าพนักงานป้องกันและบรรเทาสาธารณภัย", 1),
        ("ผู้ช่วยเจ้าพนักงานธุรการ", 5), ("ผู้ช่วยนักทรัพยากรบุคคล", 2), ("ผู้ช่วยนักวิเคราะห์นโยบายและแผน", 1),
        ("ผู้ช่วยนิติกร", 1), ("ผู้ช่วยนักประชาสัมพันธ์", 1), ("ผู้ช่วยนักป้องกันและบรรเทาสาธารณภัย", 1),
        ("ผู้ช่วยนักจัดการงานเทศกิจ", 1), ("ผู้ช่วยนักพัฒนาการท่องเที่ยว", 1),
        ("ผู้ช่วยนักวิชาการตรวจสอบภายใน", 1), ("พนักงานดับเพลิง", 10), ("พนักงานเทศกิจ", 3),
        ("พนักงานขับรถยนต์", 4), ("พนักงานขับเครื่องจักรขนาดเบา", 3), ("คนงาน", 10)]),
    ("กองคลัง", "กองคลัง", [
        ("ฝ่าย", "ฝ่ายการเงินและบัญชี"), ("ฝ่าย", "ฝ่ายพัฒนารายได้"), ("หน่วยงานย่อย", "งานพัสดุและทรัพย์สิน")], [
        ("ผู้อำนวยการกองคลัง", 1), ("นักวิชาการจัดเก็บรายได้", 1), ("นักวิชาการเงินและบัญชี", 1),
        ("นักวิชาการพัสดุ", 1), ("เจ้าพนักงานจัดเก็บรายได้", 2), ("เจ้าพนักงานการเงินและบัญชี", 2),
        ("เจ้าพนักงานพัสดุ", 2), ("เจ้าพนักงานธุรการ", 1), ("ผู้ช่วยนักวิชาการเงินและบัญชี", 1),
        ("ผู้ช่วยเจ้าพนักงานจัดเก็บรายได้", 3), ("ผู้ช่วยเจ้าพนักงานการเงินและบัญชี", 1),
        ("ผู้ช่วยเจ้าพนักงานพัสดุ", 1), ("ผู้ช่วยเจ้าพนักงานธุรการ", 1), ("พนักงานขับรถยนต์", 1), ("คนงาน", 2)]),
    ("กองช่าง", "กองช่าง", [
        ("ฝ่าย", "ฝ่ายแบบแผนและก่อสร้าง"), ("ฝ่าย", "ฝ่ายควบคุมอาคาร"), ("หน่วยงานย่อย", "งานกิจการประปา")], [
        ("ผู้อำนวยการกองช่าง", 1), ("นักจัดการงานทั่วไป", 1), ("นายช่างโยธา", 2), ("นายช่างเขียนแบบ", 2),
        ("นายช่างไฟฟ้า", 1), ("เจ้าพนักงานประปา", 1), ("เจ้าพนักงานธุรการ", 1), ("ผู้ช่วยนายช่างโยธา", 4),
        ("ผู้ช่วยนายช่างไฟฟ้า", 2), ("ผู้ช่วยนายช่างเขียนแบบ", 1), ("ผู้ช่วยเจ้าพนักงานประปา", 2),
        ("ผู้ช่วยเจ้าพนักงานธุรการ", 3), ("พนักงานจดมาตรวัดน้ำ", 2), ("คนงานประปา", 2),
        ("พนักงานขับเครื่องจักรขนาดเบา", 2), ("พนักงานขับเครื่องจักรขนาดกลาง", 2), ("พนักงานขับรถยนต์", 1),
        ("คนงาน", 1)]),
    ("กองสาธารณสุขและสิ่งแวดล้อม", "กองสาธารณสุข,กองสาธารณสุขฯ,กองสาธารณสุขและสิ่งแวดล้อม", [
        ("ฝ่าย", "ฝ่ายบริหารงานสาธารณสุข"), ("หน่วยงานย่อย", "งานรักษาความสะอาด"),
        ("หน่วยงานย่อย", "งานการแพทย์ฉุกเฉิน")], [
        ("ผู้อำนวยการกองสาธารณสุขและสิ่งแวดล้อม", 1), ("นักวิชาการสาธารณสุข", 1), ("นักวิชาการสุขาภิบาล", 1),
        ("เจ้าพนักงานสาธารณสุข", 2), ("เจ้าพนักงานธุรการ", 1), ("ผู้ช่วยนักวิชาการสาธารณสุข", 1),
        ("ผู้ช่วยเจ้าพนักงานธุรการ", 2), ("พนักงานกู้ชีพ", 3), ("พนักงานขับรถยนต์", 7),
        ("พนักงานขับเครื่องจักรขนาดกลาง", 1), ("คนงานประจำรถบรรทุกขยะ", 12), ("คนงาน", 6)]),
    ("กองการศึกษา ศาสนา และวัฒนธรรม", "กองการศึกษา,กองการศึกษาฯ,กองการศึกษา ศาสนา และวัฒนธรรม", [
        ("ฝ่าย", "ฝ่ายบริหารการศึกษา"), ("หน่วยงานย่อย", "ศูนย์พัฒนาเด็กเล็กตำบลไม้ขาว"),
        ("หน่วยงานย่อย", "ศูนย์พัฒนาเด็กเล็กบ้านท่าฉัตรไชย"), ("หน่วยงานย่อย", "โรงเรียนผู้สูงอายุตำบลไม้ขาว")], [
        ("ผู้อำนวยการกองการศึกษา ศาสนา และวัฒนธรรม", 1), ("นักวิชาการศึกษา", 2), ("เจ้าพนักงานธุรการ", 1),
        ("ครู", 5), ("ผู้ช่วยนักวิชาการศึกษา", 2), ("ผู้ช่วยครูผู้ดูแลเด็ก", 4), ("ผู้ดูแลเด็ก (ทักษะ)", 4),
        ("ผู้ช่วยเจ้าพนักงานธุรการ", 2), ("พนักงานขับรถยนต์", 2), ("นักการภารโรง", 1), ("คนงาน", 3)]),
    ("กองสวัสดิการสังคม", "กองสวัสดิการสังคม,กองสวัสดิการ", [
        ("ฝ่าย", "ฝ่ายส่งเสริมสวัสดิการสังคม")], [
        ("ผู้อำนวยการกองสวัสดิการสังคม", 1), ("นักพัฒนาชุมชน", 1), ("นักสังคมสงเคราะห์", 1),
        ("เจ้าพนักงานธุรการ", 1), ("ผู้ช่วยนักพัฒนาชุมชน", 2), ("ผู้ช่วยนักสังคมสงเคราะห์", 1),
        ("ผู้ช่วยเจ้าพนักงานธุรการ", 1), ("พนักงานขับรถยนต์", 1)]),
]


def classify(title: str) -> tuple[str, str]:
    """(สาย, ประเภท) of a position title — a first guess the officer can change."""
    t = title.replace(" ", "")
    if t.startswith(("ผู้อำนวยการ", "หัวหน้าสำนัก", "ปลัด", "รองปลัด")):
        return "วิชาการ", "หัวหน้าส่วนราชการ"
    if t.startswith("ครู"):
        return "วิชาการ", "ครู"
    if t.startswith("ผู้ช่วยนัก") or t.startswith("ผู้ช่วยนิติกร"):
        return "วิชาการ", "พนักงานจ้างตามภารกิจ"
    if t.startswith(("ผู้ช่วย", "ผู้ดูแลเด็ก")):
        return "ทั่วไป", "พนักงานจ้างตามภารกิจ"
    if t.startswith(("พนักงาน", "คนงาน", "นักการ")):
        return "ทั่วไป", "พนักงานจ้างทั่วไป"
    if t.startswith("นัก"):
        return "วิชาการ", "ข้าราชการ/พนักงานส่วนท้องถิ่น"
    return "ทั่วไป", "ข้าราชการ/พนักงานส่วนท้องถิ่น"


def month_iter(start: _dt.date, end: _dt.date):
    """(YYYY-MM, days hired that month capped at 30, full month?) for each month of [start, end]."""
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        last = calendar.monthrange(y, m)[1]
        a = max(start, _dt.date(y, m, 1))
        b = min(end, _dt.date(y, m, last))
        full = a.day == 1 and b.day == last
        days = 30 if full else min(30, (b - a).days + 1)
        yield f"{y:04d}-{m:02d}", days, full
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


class HireMixin:
    """Divisions, positions and personal service hiring — methods of :class:`venitsupply.db.Store`."""

    def _hire_init(self):
        self.con.executescript(SQL)
        for table, col, decl in (("budget_items", "division_id", "INTEGER"),
                                 ("procurements", "division_id", "INTEGER")):
            cols = [r[1] for r in self.con.execute(f"PRAGMA table_info({table})")]
            if col not in cols:
                self.con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        self.con.commit()

    # ------------------------------------------------------- divisions
    def divisions(self, parent_id=None, all_levels=False):
        if all_levels:
            return self.q("SELECT * FROM divisions ORDER BY seq, id")
        if parent_id is None:
            return self.q("SELECT * FROM divisions WHERE parent_id IS NULL ORDER BY seq, id")
        return self.q("SELECT * FROM divisions WHERE parent_id=? ORDER BY seq, id", (parent_id,))

    def division(self, did):
        return self.one("SELECT * FROM divisions WHERE id=?", (did,))

    def top_division(self, did):
        """The กอง a sub-unit belongs to."""
        d = self.division(did)
        while d is not None and d["parent_id"]:
            d = self.division(d["parent_id"])
        return d

    def save_division(self, data: dict, did=None) -> int:
        f = ("parent_id", "kind", "name", "aliases", "head_name", "head_pos", "officer_name", "officer_pos",
             "seq", "note")
        d = {k: data[k] for k in f if k in data}
        if "name" in d and not str(d["name"]).strip():
            raise ValueError("กรอกชื่อกอง/หน่วยงาน")
        if did:
            if d.get("parent_id") == did:
                raise ValueError("หน่วยงานเป็นหน่วยงานย่อยของตัวเองไม่ได้")
            self.run(f"UPDATE divisions SET {','.join(f'{k}=?' for k in d)} WHERE id=?", (*d.values(), did))
            return did
        if "seq" not in d:
            d["seq"] = (self.one("SELECT IFNULL(MAX(seq),0) AS s FROM divisions")["s"] or 0) + 1
        return self.run(f"INSERT INTO divisions({','.join(d)}) VALUES({','.join('?' * len(d))})", tuple(d.values()))

    def delete_division(self, did):
        if self.q("SELECT 1 FROM divisions WHERE parent_id=?", (did,)):
            raise ValueError("ลบหน่วยงานย่อยก่อน")
        if self.one("SELECT 1 FROM hire_contracts WHERE division_id=? AND status<>'ยกเลิก'", (did,)):
            raise ValueError("มีสัญญาจ้างของหน่วยงานนี้อยู่ ลบไม่ได้")
        self.con.execute("DELETE FROM positions WHERE division_id=?", (did,))
        self.con.execute("UPDATE budget_items SET division_id=NULL WHERE division_id=?", (did,))
        self.con.execute("UPDATE procurements SET division_id=NULL WHERE division_id=?", (did,))
        self.con.execute("UPDATE hire_jobs SET division_id=NULL WHERE division_id=?", (did,))
        self.run("DELETE FROM divisions WHERE id=?", (did,))

    def positions(self, division_id=None):
        if division_id is None:
            return self.q("SELECT p.*, d.name AS division FROM positions p JOIN divisions d ON d.id=p.division_id "
                          "ORDER BY d.seq, p.id")
        return self.q("SELECT * FROM positions WHERE division_id=? ORDER BY id", (division_id,))

    def save_position(self, data: dict, pid=None) -> int:
        f = ("division_id", "title", "line", "kind", "count", "note")
        d = {k: data[k] for k in f if k in data}
        if "title" in d and not str(d["title"]).strip():
            raise ValueError("กรอกชื่อตำแหน่ง")
        if pid:
            self.run(f"UPDATE positions SET {','.join(f'{k}=?' for k in d)} WHERE id=?", (*d.values(), pid))
            return pid
        return self.run(f"INSERT INTO positions({','.join(d)}) VALUES({','.join('?' * len(d))})", tuple(d.values()))

    def delete_position(self, pid):
        self.run("DELETE FROM positions WHERE id=?", (pid,))

    def seed_structure(self, template=MAIKHAO, replace=False) -> int:
        """โครงสร้างตัวอย่าง (อบต.ไม้ขาว): 6 กอง หน่วยงานย่อย และตำแหน่ง — แก้/ลบได้ทั้งหมด."""
        if self.q("SELECT 1 FROM divisions") and not replace:
            raise ValueError("มีโครงสร้างหน่วยงานอยู่แล้ว")
        n = 0
        for name, aliases, subs, posts in template:
            did = self.save_division(dict(kind="กอง", name=name, aliases=aliases))
            n += 1
            for kind, sub in subs:
                self.save_division(dict(kind=kind, name=sub, parent_id=did))
            for title, count in posts:
                line, kind = classify(title)
                self.save_position(dict(division_id=did, title=title, line=line, kind=kind, count=count))
        return n

    # ------------------------------------------- budget items ↔ กอง
    def _division_for_text(self, text: str):
        tops = self.divisions()
        marks = re.findall(r"\(([^()]{2,60})\)", text or "")
        for mk in reversed(marks):
            mk = mk.strip()
            for d in tops:
                names = [d["name"]] + [a.strip() for a in (d["aliases"] or "").split(",") if a.strip()]
                if any(mk == n or (len(n) > 3 and mk.startswith(n)) for n in names):
                    return d["id"]
        return None

    def assign_divisions(self, fy, overwrite=False) -> int:
        """กองของแต่ละรายการงบ: จากคำชี้แจง «(กองคลัง)»; ไม่มี → กองที่พบมากที่สุดใน «งาน» เดียวกัน."""
        items = self.budget_items(fy)
        found, by_task = {}, {}
        for b in items:
            did = self._division_for_text(b["detail"])
            if did:
                found[b["id"]] = did
                by_task.setdefault((b["plan"], b["task"]), {}).setdefault(did, 0)
                by_task[(b["plan"], b["task"])][did] += 1
        n = 0
        for b in items:
            if b["division_id"] and not overwrite:
                continue
            did = found.get(b["id"])
            if did is None and (b["plan"], b["task"]) in by_task:
                cnt = by_task[(b["plan"], b["task"])]
                did = max(cnt, key=cnt.get)
            if did:
                self.con.execute("UPDATE budget_items SET division_id=? WHERE id=?", (did, b["id"]))
                n += 1
        self.con.commit()
        return n

    def set_item_division(self, bid, did):
        self.run("UPDATE budget_items SET division_id=? WHERE id=?", (did, bid))

    def division_budget(self, fy, did, hire_only=False) -> dict:
        """Totals of a กอง's budget items (optionally only «ค่าจ้างเหมาบริการบุคคลภายนอก»)."""
        t = dict(budget=0.0, reserved=0.0, committed=0.0, paid=0.0, available=0.0, items=0)
        for b in self.q("SELECT id, name FROM budget_items WHERE fy=? AND division_id=?", (fy, did)):
            if hire_only and HIRE_ITEM not in b["name"]:
                continue
            bal = self.balance(b["id"])
            for k in ("budget", "reserved", "committed", "paid", "available"):
                t[k] += bal[k]
            t["items"] += 1
        return t

    def hire_budget_items(self, fy, did):
        """รายการงบที่จ้างเหมาบริการบุคคลได้ของกอง (ค่าจ้างเหมาบริการบุคคลภายนอก ก่อน)."""
        rows = self.q("SELECT * FROM budget_items WHERE fy=? AND division_id=? AND category='ค่าใช้สอย' "
                      "ORDER BY seq, id", (fy, did))
        main = [b for b in rows if HIRE_ITEM in b["name"]]
        return main + [b for b in rows if b not in main and "จ้างเหมา" in b["name"]]

    # ---------------------------------------------------------- rates
    def hire_rates(self) -> list[tuple[str, str, float]]:
        raw = self.setting("hire_rates")
        try:
            rows = json.loads(raw) if raw else DEFAULT_RATES
            return [(str(a), str(b), float(c)) for a, b, c in rows]
        except (ValueError, TypeError):
            return list(DEFAULT_RATES)

    def set_hire_rates(self, rows):
        self.set_setting("hire_rates", json.dumps([list(r) for r in rows], ensure_ascii=False))

    def base_rate(self, line, qualification) -> float:
        for a, b, c in self.hire_rates():
            if a == line and b == qualification:
                return c
        same = [c for a, b, c in self.hire_rates() if a == line]
        return min(same) if same else 0.0

    def job_value(self, job) -> dict:
        """ค่างาน: อัตราตามสาย/คุณวุฒิ × (1 + ความยากของงาน %) ปัดขึ้นหลักร้อย, เทียบปริมาณงาน (คน)."""
        base = self.base_rate(job["line"], job["qualification"])
        diff = float(job["difficulty"] or 0)
        suggested = int(-(-base * (1 + diff / 100) // 100) * 100) if base else 0
        fte = self.workload(job["id"])["fte"]
        minwage = self.fnum("min_wage_day", 400)
        monthly = float(job["monthly"] or 0) or suggested
        notes = []
        if fte and fte < 0.5:
            notes.append(f"ปริมาณงานเทียบได้ {fte:.2f} คน (ต่ำกว่าครึ่ง) — พิจารณารวมงานหรือจ้างเฉพาะช่วง")
        elif fte > 1.5:
            notes.append(f"ปริมาณงานเทียบได้ {fte:.2f} คน — อาจต้องจ้าง {round(fte)} คน หรือแบ่งงาน")
        if monthly and minwage and monthly / 30 < minwage:
            notes.append(f"ค่าจ้างต่อวัน {monthly / 30:,.2f} บาท ต่ำกว่าค่าแรงขั้นต่ำที่ตั้งไว้ {minwage:,.0f} บาท/วัน")
        return dict(base=base, difficulty=diff, suggested=suggested, monthly=monthly, daily=round(monthly / 30, 2),
                    fte=fte, notes=notes)

    # ----------------------------------------------- jobs and workload
    JOB_FIELDS = ("division_id", "title", "line", "qualification", "difficulty", "monthly", "background",
                  "objective", "qualifications", "scope", "work_place", "work_hours", "note")

    def save_job(self, data: dict, jid=None) -> int:
        d = {k: data[k] for k in self.JOB_FIELDS if k in data}
        if "title" in d and not str(d["title"]).strip():
            raise ValueError("กรอกชื่องานที่จะจ้าง")
        if jid:
            self.run(f"UPDATE hire_jobs SET {','.join(f'{k}=?' for k in d)} WHERE id=?", (*d.values(), jid))
            return jid
        return self.run(f"INSERT INTO hire_jobs({','.join(d)}) VALUES({','.join('?' * len(d))})", tuple(d.values()))

    def delete_job(self, jid):
        if self.one("SELECT 1 FROM hire_contracts WHERE job_id=? AND status<>'ยกเลิก'", (jid,)):
            raise ValueError("มีสัญญาจ้างของงานนี้อยู่ ลบไม่ได้")
        self.con.execute("DELETE FROM hire_tasks WHERE job_id=?", (jid,))
        self.run("DELETE FROM hire_jobs WHERE id=?", (jid,))

    def job(self, jid):
        return self.one("SELECT j.*, d.name AS division FROM hire_jobs j LEFT JOIN divisions d ON d.id=j.division_id "
                        "WHERE j.id=?", (jid,))

    def jobs(self, division_id=None):
        sql = "SELECT j.*, d.name AS division FROM hire_jobs j LEFT JOIN divisions d ON d.id=j.division_id"
        if division_id:
            return self.q(sql + " WHERE j.division_id=? ORDER BY j.id", (division_id,))
        return self.q(sql + " ORDER BY d.seq, j.id")

    def set_tasks(self, jid, tasks):
        """tasks: [(task, minutes, volume)] — the workload sheet of a job."""
        self.con.execute("DELETE FROM hire_tasks WHERE job_id=?", (jid,))
        for i, (task, minutes, volume) in enumerate(tasks, 1):
            if str(task).strip():
                self.con.execute("INSERT INTO hire_tasks(job_id,seq,task,minutes,volume) VALUES(?,?,?,?,?)",
                                 (jid, i, str(task).strip(), float(minutes or 0), float(volume or 0)))
        self.con.commit()

    def tasks(self, jid):
        return self.q("SELECT * FROM hire_tasks WHERE job_id=? ORDER BY seq, id", (jid,))

    def workload(self, jid) -> dict:
        """บัญชีแสดงการคำนวณปริมาณงาน: each row = นาที × ปริมาณ ÷ นาทีทำงานต่อปี (rounded to 2 places,
        as in the official sheets), total = sum of the rows."""
        per_year = self.fnum("work_minutes_year", WORK_MINUTES_YEAR) or WORK_MINUTES_YEAR
        rows, total_min, fte = [], 0.0, 0.0
        for t in self.tasks(jid):
            mins = (t["minutes"] or 0) * (t["volume"] or 0)
            share = round(mins / per_year, 2)
            rows.append(dict(task=t["task"], minutes=t["minutes"], volume=t["volume"], total=mins, share=share))
            total_min += mins
            fte += share
        return dict(rows=rows, total=total_min, fte=round(fte, 2), per_year=per_year)

    # ------------------------------------------------------- contracts
    C_FIELDS = ("job_id", "division_id", "budget_item_id", "contract_no", "sign_date", "person", "id_card",
                "address", "bank", "bank_branch", "account_name", "account_no", "start", "end", "monthly",
                "inspector", "note")

    def plan_months(self, start, end, monthly) -> list[dict]:
        start, end = TD.parse(start), TD.parse(end)
        if not start or not end or end < start:
            raise ValueError("วันเริ่มและวันสิ้นสุดสัญญาไม่ถูกต้อง")
        daily = float(monthly) / 30
        out = []
        for month, days, full in month_iter(start, end):
            amount = float(monthly) if full else round(daily * days, 2)
            out.append(dict(month=month, days=days, full=full, amount=amount))
        return out

    def contract_total(self, start, end, monthly) -> float:
        return round(sum(m["amount"] for m in self.plan_months(start, end, monthly)), 2)

    def contracts(self, fy=None, division_id=None):
        sql = ("SELECT c.*, j.title AS job, d.name AS division, p.number AS proc_no, p.status AS proc_status "
               "FROM hire_contracts c LEFT JOIN hire_jobs j ON j.id=c.job_id "
               "LEFT JOIN divisions d ON d.id=c.division_id LEFT JOIN procurements p ON p.id=c.proc_id WHERE 1=1")
        args = []
        if fy:
            s, e = TD.fiscal_range(fy)
            sql += " AND c.start<=? AND c.end>=?"
            args += [str(e), str(s)]
        if division_id:
            sql += " AND c.division_id=?"
            args.append(division_id)
        return self.q(sql + " ORDER BY c.start DESC, c.id DESC", args)

    def contract(self, cid):
        r = self.q("SELECT c.*, j.title AS job, d.name AS division FROM hire_contracts c "
                   "LEFT JOIN hire_jobs j ON j.id=c.job_id LEFT JOIN divisions d ON d.id=c.division_id "
                   "WHERE c.id=?", (cid,))
        return r[0] if r else None

    def next_contract_no(self, fy) -> str:
        n = 1
        while self.one("SELECT 1 FROM hire_contracts WHERE contract_no=?", (f"{n}/{fy}",)):
            n += 1
        return f"{n}/{fy}"

    def save_contract(self, data: dict, cid=None) -> int:
        """Create/update a contract and its procurement (จ้าง, วิธีเฉพาะเจาะจง) on the กอง's budget item.
        The money is checked against the budget item like every procurement."""
        d = {k: data[k] for k in self.C_FIELDS if k in data}
        cur = self.contract(cid) if cid else None
        merged = dict(cur) if cur else {}
        merged.update(d)
        if not str(merged.get("person", "")).strip():
            raise ValueError("กรอกชื่อผู้รับจ้าง")
        if not merged.get("budget_item_id"):
            raise ValueError("เลือกรายการงบประมาณของกอง")
        total = self.contract_total(merged["start"], merged["end"], merged["monthly"])
        fy = TD.fiscal_year(merged["start"])
        if TD.fiscal_year(merged["end"]) != fy:
            raise ValueError("สัญญาต้องอยู่ภายในปีงบประมาณเดียวกัน (1 ต.ค. – 30 ก.ย.) ตามงบของปีนั้น")
        job = self.job(merged["job_id"]) if merged.get("job_id") else None
        title = f"จ้างเหมาบริการบุคคลธรรมดา {job['title'] if job else ''} ({merged['person']})".replace("  ", " ")
        if not merged.get("contract_no"):
            d["contract_no"] = merged["contract_no"] = self.next_contract_no(fy)
        if cur and cur["proc_id"]:
            p = self.procurement(cur["proc_id"])
            if p["status"] in ("ขออนุมัติ", "อนุมัติแล้ว"):
                self.save_procurement(dict(title=title, amount=total, budget_item_id=merged["budget_item_id"],
                                           vendor=merged["person"], due_date=merged["end"]), pid=cur["proc_id"])
            elif abs((p["contract_amount"] or 0) - total) > 0.01:
                raise ValueError("ทำสัญญาแล้ว แก้ไขวันที่หรือค่าจ้างไม่ได้ — ยกเลิกแล้วทำใหม่")
            pid = cur["proc_id"]
        else:
            pid = self.save_procurement(dict(
                kind="จ้าง", title=title, budget_item_id=merged["budget_item_id"], amount=total,
                method="วิธีเฉพาะเจาะจง", date_request=str(TD.today() if TD.fiscal_year(TD.today()) == fy
                                                           else TD.fiscal_range(fy)[0]),
                due_date=merged["end"], vendor=merged["person"], committee=merged.get("inspector", ""),
                reason=(job["background"] if job else "") or "เพื่อให้การปฏิบัติงานของกองบรรลุผลตามภารกิจ",
                requester=(self.division(merged["division_id"])["name"] if merged.get("division_id") else "")))
            self.run("UPDATE procurements SET division_id=? WHERE id=?", (merged.get("division_id"), pid))
        d["proc_id"] = pid
        if cid:
            self.run(f"UPDATE hire_contracts SET {','.join(f'{k}=?' for k in d)} WHERE id=?", (*d.values(), cid))
        else:
            cid = self.run(f"INSERT INTO hire_contracts({','.join(d)}) VALUES({','.join('?' * len(d))})",
                           tuple(d.values()))
        self._sync_months(cid)
        return cid

    def _sync_months(self, cid):
        c = self.contract(cid)
        plan = self.plan_months(c["start"], c["end"], c["monthly"])
        keep = {m["month"] for m in plan}
        for r in self.q("SELECT * FROM hire_months WHERE contract_id=?", (cid,)):
            if r["month"] not in keep and not r["payment_id"]:
                self.con.execute("DELETE FROM hire_months WHERE id=?", (r["id"],))
        for m in plan:
            ex = self.one("SELECT * FROM hire_months WHERE contract_id=? AND month=?", (cid, m["month"]))
            if ex is None:
                self.con.execute("INSERT INTO hire_months(contract_id,month,days,planned_days,amount) VALUES(?,?,?,?,?)",
                                 (cid, m["month"], m["days"], m["days"], m["amount"]))
            elif not ex["inspect_date"]:
                self.con.execute("UPDATE hire_months SET days=?, planned_days=?, amount=? WHERE id=?",
                                 (m["days"], m["days"], m["amount"], ex["id"]))
        self.con.commit()

    def sign_contract(self, cid, date=None):
        """อนุมัติจ้างและลงนามสัญญา = ก่อหนี้ผูกพันเต็มจำนวนสัญญาในงบของกอง."""
        c = self.contract(cid)
        p = self.procurement(c["proc_id"])
        date = str(date or TD.today())
        if p["status"] == "ขออนุมัติ":
            self.approve(p["id"], date)
        p = self.procurement(c["proc_id"])
        if p["status"] == "อนุมัติแล้ว":
            self.order(p["id"], c["person"], p["amount"], c["contract_no"], date, c["end"], "สัญญา",
                       vendor_vat=False, vendor_tax_id=c["id_card"])
        self.run("UPDATE hire_contracts SET status='ทำสัญญาแล้ว', sign_date=? WHERE id=?", (date, cid))

    def months(self, cid):
        return self.q("SELECT * FROM hire_months WHERE contract_id=? ORDER BY month", (cid,))

    def inspect_month(self, cid, month, days=None, date=None, note="") -> float:
        """ตรวจรับงานประจำเดือน: ส่งงานครบ = ค่าจ้างเต็มงวด; ไม่ครบ = ค่าจ้างรายวัน × วันที่ส่งงานครบถ้วน."""
        c = self.contract(cid)
        if c["status"] != "ทำสัญญาแล้ว":
            raise ValueError("ต้องลงนามสัญญาก่อนตรวจรับ")
        m = self.one("SELECT * FROM hire_months WHERE contract_id=? AND month=?", (cid, month))
        if m is None:
            raise ValueError("ไม่มีงวดเดือนนี้ในสัญญา")
        if m["payment_id"]:
            raise ValueError("งวดนี้เบิกจ่ายแล้ว")
        days = m["planned_days"] if days is None else int(days)
        if days < 0 or days > m["planned_days"]:
            raise ValueError(f"จำนวนวันต้องอยู่ระหว่าง 0 – {m['planned_days']}")
        full_amount = self.plan_amount(c, month)
        amount = full_amount if days == m["planned_days"] else round(c["monthly"] / 30 * days, 2)
        self.run("UPDATE hire_months SET days=?, amount=?, inspect_date=?, note=? WHERE id=?",
                 (days, amount, str(date or TD.today()), note, m["id"]))
        return amount

    def plan_amount(self, c, month) -> float:
        for m in self.plan_months(c["start"], c["end"], c["monthly"]):
            if m["month"] == month:
                return m["amount"]
        return 0.0

    def pay_month(self, cid, month, date=None, voucher_no="") -> int:
        """เบิกจ่ายงวดเดือนที่ตรวจรับแล้ว (ไม่มีค่าปรับตาม ว 727). งวดสุดท้ายปิดสัญญา."""
        c = self.contract(cid)
        m = self.one("SELECT * FROM hire_months WHERE contract_id=? AND month=?", (cid, month))
        if m is None or not m["inspect_date"]:
            raise ValueError("ต้องตรวจรับงวดนี้ก่อนเบิกจ่าย")
        if m["payment_id"]:
            raise ValueError("งวดนี้เบิกจ่ายแล้ว")
        if not m["amount"]:
            self.run("UPDATE hire_months SET payment_id=-1 WHERE id=?", (m["id"],))
            pay_id = -1
        else:
            pending = [x for x in self.months(cid) if not x["payment_id"] and x["id"] != m["id"]]
            pay_id = self.pay(c["proc_id"], m["amount"], date or m["inspect_date"], voucher_no,
                              f"งวดเดือน {month_name(month)}", final=not pending)
            self.run("UPDATE hire_months SET payment_id=? WHERE id=?", (pay_id, m["id"]))
        if not [x for x in self.months(cid) if not x["payment_id"]]:
            self.run("UPDATE hire_contracts SET status='สิ้นสุด' WHERE id=?", (cid,))
            p = self.procurement(c["proc_id"])
            if p["status"] != "เบิกจ่ายแล้ว":     # unpaid days returned to the budget
                self.run("UPDATE procurements SET status='เบิกจ่ายแล้ว', contract_amount=? WHERE id=?",
                         (self.paid(c["proc_id"]), c["proc_id"]))
        return pay_id

    def cancel_contract(self, cid, reason=""):
        c = self.contract(cid)
        if any(m["payment_id"] for m in self.months(cid)):
            raise ValueError("มีงวดที่เบิกจ่ายแล้ว ใช้การบอกเลิกสัญญาและปิดงวดแทน")
        if c["proc_id"]:
            self.cancel(c["proc_id"], reason)
        self.run("UPDATE hire_contracts SET status='ยกเลิก', note=? WHERE id=?", (reason, cid))

    def ending_soon(self, days=30, on=None):
        on = TD.parse(on) or TD.today()
        lim = on + _dt.timedelta(days=days)
        return [c for c in self.contracts() if c["status"] == "ทำสัญญาแล้ว" and str(on) <= c["end"] <= str(lim)]

    def hire_summary(self, fy) -> list[dict]:
        """Per กอง: งบจ้างเหมาบุคคล, ผูกพันตามสัญญา, จ่ายแล้ว, คงเหลือ, จำนวนสัญญา."""
        out = []
        for d in self.divisions():
            b = self.division_budget(fy, d["id"], hire_only=True)
            cons = [c for c in self.contracts(fy, d["id"]) if c["status"] != "ยกเลิก"]
            out.append(dict(division=d, budget=b["budget"], committed=b["committed"] + b["reserved"],
                            paid=b["paid"], available=b["available"], contracts=len(cons),
                            monthly=sum(c["monthly"] for c in cons if c["status"] == "ทำสัญญาแล้ว")))
        return out


def month_name(month: str) -> str:
    y, m = (int(x) for x in month.split("-"))
    return f"{TD.MONTHS[m - 1]} {y + 543}"
