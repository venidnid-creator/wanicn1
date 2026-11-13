# SPDX-License-Identifier: GPL-3.0-or-later
"""ฐานข้อมูลพัสดุ (SQLite ไฟล์เดียว .vsdb).

ครอบคลุมงานบริหารพัสดุตามระเบียบกระทรวงการคลังว่าด้วยการจัดซื้อจัดจ้างและ
การบริหารพัสดุภาครัฐ พ.ศ. 2560 หมวด 9: การเก็บและการบันทึก, การเบิกจ่าย,
การยืม, การตรวจสอบพัสดุประจำปี และการจำหน่ายพัสดุ.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from . import depreciation as DEP
from .budget import BudgetMixin
from .procurement import ProcurementMixin
from . import thaidate as TD

SCHEMA_VERSION = 2

# ประเภทครุภัณฑ์และอายุการใช้งาน (ปี) — ค่าเริ่มต้น แก้ไขได้ในหน้าตั้งค่า
# ให้ตรวจกับหลักเกณฑ์อายุการใช้งานของกรมบัญชีกลางที่หน่วยงานใช้อยู่
ASSET_TYPES = [
    ("01", "ครุภัณฑ์สำนักงาน", 8), ("02", "ครุภัณฑ์ยานพาหนะและขนส่ง", 8),
    ("03", "ครุภัณฑ์ไฟฟ้าและวิทยุ", 5), ("04", "ครุภัณฑ์โฆษณาและเผยแพร่", 5),
    ("05", "ครุภัณฑ์การเกษตร", 5), ("06", "ครุภัณฑ์ก่อสร้าง", 5),
    ("07", "ครุภัณฑ์สำรวจ", 5), ("08", "ครุภัณฑ์วิทยาศาสตร์และการแพทย์", 5),
    ("09", "ครุภัณฑ์งานบ้านงานครัว", 5), ("10", "ครุภัณฑ์กีฬา", 5),
    ("11", "ครุภัณฑ์คอมพิวเตอร์", 3), ("12", "ครุภัณฑ์การศึกษา", 5),
    ("13", "ครุภัณฑ์ดนตรีและนาฏศิลป์", 5), ("14", "ครุภัณฑ์โรงงาน", 5),
    ("15", "ครุภัณฑ์สนาม", 5), ("16", "ครุภัณฑ์อื่น", 5),
]
MATERIAL_TYPES = [
    ("M01", "วัสดุสำนักงาน"), ("M02", "วัสดุไฟฟ้าและวิทยุ"), ("M03", "วัสดุงานบ้านงานครัว"),
    ("M04", "วัสดุก่อสร้าง"), ("M05", "วัสดุยานพาหนะและขนส่ง"), ("M06", "วัสดุเชื้อเพลิงและหล่อลื่น"),
    ("M07", "วัสดุวิทยาศาสตร์หรือการแพทย์"), ("M08", "วัสดุการเกษตร"), ("M09", "วัสดุโฆษณาและเผยแพร่"),
    ("M10", "วัสดุคอมพิวเตอร์"), ("M11", "วัสดุสำรวจ"), ("M12", "วัสดุอื่น"),
]
STATUSES = ["ใช้งาน", "ชำรุด", "เสื่อมสภาพ", "สูญหาย", "ไม่จำเป็นต้องใช้", "จำหน่ายแล้ว"]
METHODS = ["วิธีเฉพาะเจาะจง", "วิธีประกาศเชิญชวนทั่วไป (e-bidding)", "วิธีคัดเลือก",
           "รับบริจาค", "รับโอน", "อื่น ๆ"]
BUDGETS = ["เงินงบประมาณ", "เงินนอกงบประมาณ", "เงินรายได้", "เงินบริจาค", "อื่น ๆ"]
# ข้อ 215 วิธีจำหน่าย
DISPOSALS = ["ขาย (ทอดตลาด/เฉพาะเจาะจง)", "แลกเปลี่ยน", "โอน", "แปรสภาพหรือทำลาย",
             "จำหน่ายเป็นสูญ"]
INSPECT_RESULTS = ["ใช้งานได้ปกติ", "ชำรุด", "เสื่อมสภาพ", "สูญไป", "ไม่จำเป็นต้องใช้", "ไม่พบ"]

DEFAULT_SETTINGS = {
    "org_name": "", "org_code": "", "org_address": "",
    "officer": "", "officer_pos": "เจ้าหน้าที่พัสดุ",
    "head_officer": "", "head_officer_pos": "หัวหน้าเจ้าหน้าที่",
    "head": "", "head_pos": "หัวหน้าหน่วยงานของรัฐ",
    "number_format": "{org}-{type}-{seq:04d}/{fy}",
    "threshold": str(DEP.THRESHOLD), "salvage": str(DEP.SALVAGE),
    "lang": "th",
    "specific_limit": "500000", "wht_rate": "1", "wht_min": "10000",
    "fine_rate": "0.2", "fine_rate_hire": "0.1",
}

SQL = """
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS categories(
  id INTEGER PRIMARY KEY, kind TEXT NOT NULL, code TEXT, name TEXT NOT NULL,
  life_years REAL DEFAULT 5);
CREATE TABLE IF NOT EXISTS departments(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS people(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, position TEXT DEFAULT '',
  department_id INTEGER REFERENCES departments(id));
CREATE TABLE IF NOT EXISTS assets(
  id INTEGER PRIMARY KEY, number TEXT UNIQUE, name TEXT NOT NULL,
  category_id INTEGER REFERENCES categories(id),
  brand TEXT DEFAULT '', model TEXT DEFAULT '', serial TEXT DEFAULT '', unit TEXT DEFAULT 'เครื่อง',
  acquire_date TEXT, price REAL DEFAULT 0, method TEXT DEFAULT '', budget TEXT DEFAULT '',
  document_no TEXT DEFAULT '', vendor TEXT DEFAULT '',
  department_id INTEGER REFERENCES departments(id), location TEXT DEFAULT '',
  custodian_id INTEGER REFERENCES people(id),
  life_years REAL, salvage REAL DEFAULT 1, status TEXT DEFAULT 'ใช้งาน', note TEXT DEFAULT '',
  disposed_date TEXT, disposal_method TEXT DEFAULT '', disposal_amount REAL DEFAULT 0,
  disposal_doc TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS materials(
  id INTEGER PRIMARY KEY, code TEXT UNIQUE, name TEXT NOT NULL,
  category_id INTEGER REFERENCES categories(id), unit TEXT DEFAULT 'ชิ้น',
  min_qty REAL DEFAULT 0, location TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS moves(
  id INTEGER PRIMARY KEY, material_id INTEGER NOT NULL REFERENCES materials(id),
  date TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('in','out')),
  qty REAL NOT NULL, unit_price REAL DEFAULT 0, doc_no TEXT DEFAULT '',
  party TEXT DEFAULT '', department_id INTEGER REFERENCES departments(id), note TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS loans(
  id INTEGER PRIMARY KEY, asset_id INTEGER NOT NULL REFERENCES assets(id),
  borrower TEXT NOT NULL, department TEXT DEFAULT '', purpose TEXT DEFAULT '',
  date_out TEXT NOT NULL, due_date TEXT, date_back TEXT, condition_back TEXT DEFAULT '',
  note TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS inspections(
  id INTEGER PRIMARY KEY, fy INTEGER NOT NULL, asset_id INTEGER NOT NULL REFERENCES assets(id),
  date TEXT, result TEXT NOT NULL, note TEXT DEFAULT '', UNIQUE(fy, asset_id));
"""


class Store(BudgetMixin, ProcurementMixin):
    """All data of one agency in one file."""

    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        self.con = sqlite3.connect(self.path)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript(SQL)
        self._budget_init()
        self._proc_init()
        if self.setting("schema") is None:
            self._seed()
        for k, v in DEFAULT_SETTINGS.items():     # settings added by newer versions
            self.con.execute("INSERT OR IGNORE INTO settings VALUES(?,?)", (k, v))
        self.con.execute("INSERT OR REPLACE INTO settings VALUES('schema',?)", (str(SCHEMA_VERSION),))
        self.con.commit()

    # ------------------------------------------------------------- basics
    def _seed(self):
        c = self.con
        for k, v in DEFAULT_SETTINGS.items():
            c.execute("INSERT OR IGNORE INTO settings VALUES(?,?)", (k, v))
        for code, name, life in ASSET_TYPES:
            c.execute("INSERT INTO categories(kind,code,name,life_years) VALUES('asset',?,?,?)",
                      (code, name, life))
        for code, name in MATERIAL_TYPES:
            c.execute("INSERT INTO categories(kind,code,name,life_years) VALUES('material',?,?,0)",
                      (code, name))
        c.execute("INSERT OR REPLACE INTO settings VALUES('schema',?)", (str(SCHEMA_VERSION),))
        c.commit()

    def q(self, sql, args=()) -> list[sqlite3.Row]:
        return self.con.execute(sql, args).fetchall()

    def one(self, sql, args=()):
        return self.con.execute(sql, args).fetchone()

    def run(self, sql, args=()) -> int:
        cur = self.con.execute(sql, args)
        self.con.commit()
        return cur.lastrowid

    def close(self):
        self.con.close()

    def setting(self, key, default=None):
        r = self.one("SELECT value FROM settings WHERE key=?", (key,))
        return r["value"] if r else default

    def set_setting(self, key, value):
        self.run("INSERT OR REPLACE INTO settings VALUES(?,?)", (key, str(value)))

    def settings(self) -> dict:
        return {r["key"]: r["value"] for r in self.q("SELECT * FROM settings")}

    def fnum(self, key, default=0.0) -> float:
        try:
            return float(self.setting(key, default))
        except (TypeError, ValueError):
            return float(default)

    # --------------------------------------------------------- lookups
    def categories(self, kind):
        return self.q("SELECT * FROM categories WHERE kind=? ORDER BY code", (kind,))

    def save_category(self, kind, code, name, life, cid=None):
        if cid:
            self.run("UPDATE categories SET code=?,name=?,life_years=? WHERE id=?",
                     (code, name, life, cid))
            return cid
        return self.run("INSERT INTO categories(kind,code,name,life_years) VALUES(?,?,?,?)",
                        (kind, code, name, life))

    def departments(self):
        return self.q("SELECT * FROM departments ORDER BY name")

    def department_id(self, name) -> int | None:
        name = (name or "").strip()
        if not name:
            return None
        r = self.one("SELECT id FROM departments WHERE name=?", (name,))
        return r["id"] if r else self.run("INSERT INTO departments(name) VALUES(?)", (name,))

    def people(self):
        return self.q("SELECT p.*, d.name AS department FROM people p "
                      "LEFT JOIN departments d ON d.id=p.department_id ORDER BY p.name")

    def person_id(self, name, position="", department="") -> int | None:
        name = (name or "").strip()
        if not name:
            return None
        r = self.one("SELECT id FROM people WHERE name=?", (name,))
        if r:
            return r["id"]
        return self.run("INSERT INTO people(name,position,department_id) VALUES(?,?,?)",
                        (name, position, self.department_id(department)))

    # ------------------------------------------------------------ assets
    def next_number(self, category_id, acquire_date=None) -> str:
        cat = self.one("SELECT code FROM categories WHERE id=?", (category_id,))
        fy = TD.fiscal_year(acquire_date or TD.today())
        org = self.setting("org_code") or "0000"
        fmt = self.setting("number_format") or DEFAULT_SETTINGS["number_format"]
        typ = cat["code"] if cat else "00"
        seq = 1
        while True:
            num = fmt.format(org=org, type=typ, seq=seq, fy=fy)
            if not self.one("SELECT 1 FROM assets WHERE number=?", (num,)):
                return num
            seq += 1

    ASSET_FIELDS = ("number", "name", "category_id", "brand", "model", "serial", "unit",
                    "acquire_date", "price", "method", "budget", "document_no", "vendor",
                    "department_id", "location", "custodian_id", "life_years", "salvage",
                    "status", "note")

    def save_asset(self, data: dict, aid: int | None = None) -> int:
        d = {k: data.get(k) for k in self.ASSET_FIELDS if k in data}
        if "department" in data:
            d["department_id"] = self.department_id(data["department"])
        if "custodian" in data:
            d["custodian_id"] = self.person_id(data["custodian"])
        if d.get("life_years") in (None, "") and d.get("category_id"):
            c = self.one("SELECT life_years FROM categories WHERE id=?", (d["category_id"],))
            d["life_years"] = c["life_years"] if c else 5
        if d.get("salvage") in (None, ""):
            d["salvage"] = self.fnum("salvage", DEP.SALVAGE)
        if not aid and not d.get("number"):
            d["number"] = self.next_number(d.get("category_id"), d.get("acquire_date"))
        if aid:
            sets = ",".join(f"{k}=?" for k in d)
            self.run(f"UPDATE assets SET {sets} WHERE id=?", (*d.values(), aid))
            return aid
        cols = ",".join(d)
        return self.run(f"INSERT INTO assets({cols}) VALUES({','.join('?' * len(d))})",
                        tuple(d.values()))

    def delete_asset(self, aid):
        self.con.execute("DELETE FROM loans WHERE asset_id=?", (aid,))
        self.con.execute("DELETE FROM inspections WHERE asset_id=?", (aid,))
        self.run("DELETE FROM assets WHERE id=?", (aid,))

    def assets(self, text="", status=None, include_disposed=True):
        sql = ("SELECT a.*, c.name AS category, c.code AS category_code, d.name AS department, "
               "p.name AS custodian FROM assets a "
               "LEFT JOIN categories c ON c.id=a.category_id "
               "LEFT JOIN departments d ON d.id=a.department_id "
               "LEFT JOIN people p ON p.id=a.custodian_id WHERE 1=1")
        args = []
        if text:
            sql += (" AND (a.number LIKE ? OR a.name LIKE ? OR a.serial LIKE ? OR a.brand LIKE ?"
                    " OR a.location LIKE ? OR IFNULL(p.name,'') LIKE ?)")
            args += [f"%{text}%"] * 6
        if status:
            sql += " AND a.status=?"
            args.append(status)
        if not include_disposed:
            sql += " AND a.status<>'จำหน่ายแล้ว'"
        return self.q(sql + " ORDER BY a.number", args)

    def asset(self, aid):
        r = self.q("SELECT a.*, c.name AS category, c.code AS category_code, d.name AS department, "
                   "p.name AS custodian FROM assets a LEFT JOIN categories c ON c.id=a.category_id "
                   "LEFT JOIN departments d ON d.id=a.department_id "
                   "LEFT JOIN people p ON p.id=a.custodian_id WHERE a.id=?", (aid,))
        return r[0] if r else None

    def depreciation(self, a, until_fy=None) -> list[dict]:
        return DEP.schedule(a["price"], a["acquire_date"], a["life_years"], a["salvage"],
                            until_fy=until_fy, disposed=a["disposed_date"],
                            threshold=self.fnum("threshold", DEP.THRESHOLD))

    def depreciation_report(self, fy) -> list[dict]:
        """One row per capitalised asset owned in fiscal year *fy*."""
        start, end = TD.fiscal_range(fy)
        out = []
        for a in self.assets():
            acq = TD.parse(a["acquire_date"])
            if acq is None or acq > end:
                continue
            dis = TD.parse(a["disposed_date"])
            if dis and dis < start:
                continue
            rows = self.depreciation(a, until_fy=fy)
            if not rows:
                continue
            y = DEP.for_year(rows, fy)
            out.append(dict(asset=a, dep=y["dep"], acc=y["acc"],
                            book=round(a["price"] - y["acc"], 2)))
        return out

    def dispose(self, aid, date, method, amount=0.0, doc=""):
        self.run("UPDATE assets SET status='จำหน่ายแล้ว', disposed_date=?, disposal_method=?, "
                 "disposal_amount=?, disposal_doc=? WHERE id=?", (date, method, amount, doc, aid))

    # ---------------------------------------------------------- materials
    def save_material(self, data: dict, mid=None) -> int:
        f = ("code", "name", "category_id", "unit", "min_qty", "location")
        d = {k: data.get(k) for k in f if k in data}
        if not mid and not d.get("code"):
            n = self.one("SELECT COUNT(*) AS n FROM materials")["n"] + 1
            while self.one("SELECT 1 FROM materials WHERE code=?", (f"V{n:04d}",)):
                n += 1
            d["code"] = f"V{n:04d}"
        if mid:
            self.run(f"UPDATE materials SET {','.join(f'{k}=?' for k in d)} WHERE id=?",
                     (*d.values(), mid))
            return mid
        return self.run(f"INSERT INTO materials({','.join(d)}) VALUES({','.join('?' * len(d))})",
                        tuple(d.values()))

    def delete_material(self, mid):
        self.con.execute("DELETE FROM moves WHERE material_id=?", (mid,))
        self.run("DELETE FROM materials WHERE id=?", (mid,))

    def receive(self, mid, date, qty, unit_price, doc_no="", party="", note="") -> int:
        if qty <= 0:
            raise ValueError("จำนวนต้องมากกว่า 0")
        return self.run("INSERT INTO moves(material_id,date,kind,qty,unit_price,doc_no,party,note) "
                        "VALUES(?,?,'in',?,?,?,?,?)", (mid, date, qty, unit_price, doc_no, party, note))

    def issue(self, mid, date, qty, doc_no="", party="", department="", note="") -> int:
        """จ่ายวัสดุ — ราคาตามวิธีเข้าก่อนออกก่อน (FIFO)."""
        if qty <= 0:
            raise ValueError("จำนวนต้องมากกว่า 0")
        bal = self.stock(mid, until=date)["qty"]
        if qty > bal + 1e-9:
            raise ValueError(f"วัสดุคงเหลือไม่พอ (คงเหลือ {bal:g})")
        return self.run("INSERT INTO moves(material_id,date,kind,qty,unit_price,doc_no,party,"
                        "department_id,note) VALUES(?,?,'out',?,0,?,?,?,?)",
                        (mid, date, qty, doc_no, party, self.department_id(department), note))

    def delete_move(self, move_id):
        self.run("DELETE FROM moves WHERE id=?", (move_id,))

    def card(self, mid, until=None) -> list[dict]:
        """บัญชีวัสดุ (stock card): each move with FIFO value and running balance."""
        sql = ("SELECT m.*, d.name AS department FROM moves m "
               "LEFT JOIN departments d ON d.id=m.department_id WHERE material_id=?")
        args = [mid]
        if until:
            sql += " AND date<=?"
            args.append(str(until))
        layers: list[list[float]] = []   # [qty, unit price]
        out = []
        bal_qty = bal_val = 0.0
        for m in self.q(sql + " ORDER BY date, kind, id", args):
            if m["kind"] == "in":
                layers.append([m["qty"], m["unit_price"]])
                val = m["qty"] * m["unit_price"]
                bal_qty += m["qty"]
                bal_val += val
            else:
                need, val = m["qty"], 0.0
                while need > 1e-9 and layers:
                    take = min(need, layers[0][0])
                    val += take * layers[0][1]
                    layers[0][0] -= take
                    need -= take
                    if layers[0][0] <= 1e-9:
                        layers.pop(0)
                bal_qty -= m["qty"]
                bal_val -= val
            out.append(dict(id=m["id"], date=m["date"], kind=m["kind"], qty=m["qty"],
                            unit_price=(val / m["qty"]) if m["qty"] else 0, value=round(val, 2),
                            doc_no=m["doc_no"], party=m["party"], department=m["department"],
                            note=m["note"], bal_qty=round(bal_qty, 4), bal_val=round(bal_val, 2)))
        return out

    def stock(self, mid, until=None) -> dict:
        c = self.card(mid, until)
        return dict(qty=c[-1]["bal_qty"], value=c[-1]["bal_val"]) if c else dict(qty=0.0, value=0.0)

    def materials(self, text=""):
        sql = ("SELECT m.*, c.name AS category FROM materials m "
               "LEFT JOIN categories c ON c.id=m.category_id")
        args = []
        if text:
            sql += " WHERE m.code LIKE ? OR m.name LIKE ?"
            args = [f"%{text}%"] * 2
        out = []
        for m in self.q(sql + " ORDER BY m.code", args):
            s = self.stock(m["id"])
            out.append(dict(m) | dict(qty=s["qty"], value=s["value"]))
        return out

    # -------------------------------------------------------------- loans
    def lend(self, aid, borrower, date_out, due_date="", purpose="", department="", note=""):
        if self.one("SELECT 1 FROM loans WHERE asset_id=? AND date_back IS NULL", (aid,)):
            raise ValueError("ครุภัณฑ์นี้ถูกยืมอยู่ ยังไม่ได้คืน")
        a = self.asset(aid)
        if a and a["status"] == "จำหน่ายแล้ว":
            raise ValueError("ครุภัณฑ์นี้จำหน่ายแล้ว")
        return self.run("INSERT INTO loans(asset_id,borrower,department,purpose,date_out,due_date,note)"
                        " VALUES(?,?,?,?,?,?,?)",
                        (aid, borrower, department, purpose, date_out, due_date or None, note))

    def give_back(self, loan_id, date_back, condition="ใช้งานได้ปกติ"):
        self.run("UPDATE loans SET date_back=?, condition_back=? WHERE id=?",
                 (date_back, condition, loan_id))

    def loans(self, open_only=False):
        sql = ("SELECT l.*, a.number, a.name AS asset_name FROM loans l "
               "JOIN assets a ON a.id=l.asset_id")
        if open_only:
            sql += " WHERE l.date_back IS NULL"
        return self.q(sql + " ORDER BY l.date_out DESC, l.id DESC")

    def overdue(self, on=None):
        on = str(TD.parse(on) or TD.today())
        return self.q("SELECT l.*, a.number, a.name AS asset_name FROM loans l "
                      "JOIN assets a ON a.id=l.asset_id WHERE l.date_back IS NULL "
                      "AND l.due_date IS NOT NULL AND l.due_date<? ORDER BY l.due_date", (on,))

    # -------------------------------------------------------- inspections
    def inspect(self, fy, aid, result, date=None, note="", update_status=True):
        self.run("INSERT OR REPLACE INTO inspections(fy,asset_id,date,result,note) VALUES(?,?,?,?,?)",
                 (fy, aid, str(date or TD.today()), result, note))
        status = {"ใช้งานได้ปกติ": "ใช้งาน", "ชำรุด": "ชำรุด", "เสื่อมสภาพ": "เสื่อมสภาพ",
                  "สูญไป": "สูญหาย", "ไม่พบ": "สูญหาย",
                  "ไม่จำเป็นต้องใช้": "ไม่จำเป็นต้องใช้"}.get(result)
        if update_status and status:
            self.run("UPDATE assets SET status=? WHERE id=? AND status<>'จำหน่ายแล้ว'", (status, aid))

    def inspection(self, fy):
        """Every asset owned at the end of fiscal year *fy* with its result (or None)."""
        _, end = TD.fiscal_range(fy)
        rows = []
        for a in self.assets():
            acq = TD.parse(a["acquire_date"])
            if acq and acq > end:
                continue
            dis = TD.parse(a["disposed_date"])
            if dis and dis <= end and a["status"] == "จำหน่ายแล้ว":
                continue
            r = self.one("SELECT * FROM inspections WHERE fy=? AND asset_id=?", (fy, a["id"]))
            rows.append(dict(asset=a, result=r["result"] if r else None,
                             note=r["note"] if r else "", date=r["date"] if r else None))
        return rows

    # ----------------------------------------------------------- summary
    def summary(self) -> dict:
        assets = self.assets()
        live = [a for a in assets if a["status"] != "จำหน่ายแล้ว"]
        fy = TD.fiscal_year(TD.today())
        dep = self.depreciation_report(fy)
        mats = self.materials()
        by_status = {s: sum(1 for a in assets if a["status"] == s) for s in STATUSES}
        return dict(
            assets=len(live), asset_value=sum(a["price"] or 0 for a in live),
            book_value=sum(r["book"] for r in dep), dep_year=sum(r["dep"] for r in dep), fy=fy,
            materials=len(mats), material_value=sum(m["value"] for m in mats),
            low_stock=[m for m in mats if m["min_qty"] and m["qty"] <= m["min_qty"]],
            loans_open=len(self.loans(open_only=True)), overdue=len(self.overdue()),
            by_status=by_status,
            inspected=sum(1 for r in self.inspection(fy - 1) if r["result"]),
            to_inspect=len(self.inspection(fy - 1)), inspect_fy=fy - 1,
        ) | self._budget_totals(fy)

    def _budget_totals(self, fy) -> dict:
        t = dict(b_budget=0.0, b_bound=0.0, b_paid=0.0, b_left=0.0)
        for r in self.budget_summary(fy):
            t["b_budget"] += r["budget"]
            t["b_bound"] += r["reserved"] + r["committed"]
            t["b_paid"] += r["paid"]
            t["b_left"] += r["available"]
        t["procs"] = len([p for p in self.procurements(fy) if p["status"] != "ยกเลิก"])
        return t
