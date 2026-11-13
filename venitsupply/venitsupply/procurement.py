# SPDX-License-Identifier: GPL-3.0-or-later
"""จัดซื้อ จัดจ้าง เช่า แลกเปลี่ยน — ผูกกับงบประมาณตามข้อบัญญัติ.

ขั้นตอน: ขออนุมัติ (รายงานขอซื้อ/ขอจ้าง) → อนุมัติแล้ว (จองเงิน)
→ ก่อหนี้ผูกพัน (ใบสั่งซื้อ/สั่งจ้าง/สัญญา) → ตรวจรับแล้ว → เบิกจ่ายแล้ว (หรือ ยกเลิก)

ทุกขั้นตรวจยอดคงเหลือของรายการงบประมาณก่อน: มีเงินเท่าไร ครั้งนี้ใช้เท่าไร เหลือเท่าไร
"""
from __future__ import annotations

import datetime as _dt

from . import thaidate as TD

KINDS = ["ซื้อ", "จ้าง", "เช่า", "แลกเปลี่ยน"]
KIND_PREFIX = {"ซื้อ": "ซ", "จ้าง": "จ", "เช่า": "ช", "แลกเปลี่ยน": "ลป"}
METHODS = ["วิธีเฉพาะเจาะจง", "วิธีคัดเลือก", "วิธีประกาศเชิญชวนทั่วไป (e-market)",
           "วิธีประกาศเชิญชวนทั่วไป (e-bidding)"]
CONTRACT_TYPES = ["ใบสั่งซื้อ/ใบสั่งจ้าง", "ข้อตกลงเป็นหนังสือ", "สัญญา"]
STATUSES = ["ขออนุมัติ", "อนุมัติแล้ว", "ก่อหนี้ผูกพัน", "ตรวจรับแล้ว", "เบิกจ่ายแล้ว", "ยกเลิก"]
SPECIFIC_LIMIT = 500000.0      # มาตรา 56 (2) (ข) วิธีเฉพาะเจาะจง วงเงินไม่เกิน 500,000 บาท
WHT_RATE = 0.01                # ภาษีหัก ณ ที่จ่าย ส่วนราชการ 1 %
WHT_MIN = 10000.0              # จ่ายครั้งหนึ่งตั้งแต่ 10,000 บาท
VAT = 0.07

SQL = """
CREATE TABLE IF NOT EXISTS procurements(
  id INTEGER PRIMARY KEY, fy INTEGER NOT NULL, number TEXT, kind TEXT NOT NULL,
  method TEXT DEFAULT '', title TEXT NOT NULL, reason TEXT DEFAULT '',
  budget_item_id INTEGER REFERENCES budget_items(id), amount REAL DEFAULT 0,
  median_price REAL DEFAULT 0, vendor TEXT DEFAULT '', vendor_tax_id TEXT DEFAULT '',
  vendor_vat INTEGER DEFAULT 1, contract_amount REAL DEFAULT 0, egp_no TEXT DEFAULT '',
  date_request TEXT, date_approve TEXT, order_no TEXT DEFAULT '', order_date TEXT,
  contract_type TEXT DEFAULT '', due_date TEXT, inspect_date TEXT, inspect_note TEXT DEFAULT '',
  fine REAL DEFAULT 0, status TEXT DEFAULT 'ขออนุมัติ', rent_from TEXT, rent_to TEXT,
  exchange_asset_id INTEGER, committee TEXT DEFAULT '', requester TEXT DEFAULT '',
  note TEXT DEFAULT '', cancel_reason TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS procurement_lines(
  id INTEGER PRIMARY KEY, proc_id INTEGER NOT NULL REFERENCES procurements(id),
  name TEXT NOT NULL, qty REAL DEFAULT 1, unit TEXT DEFAULT '', unit_price REAL DEFAULT 0,
  target TEXT DEFAULT '', category_id INTEGER, registered INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS payments(
  id INTEGER PRIMARY KEY, proc_id INTEGER NOT NULL REFERENCES procurements(id),
  date TEXT NOT NULL, amount REAL NOT NULL, wht REAL DEFAULT 0, fine REAL DEFAULT 0,
  net REAL DEFAULT 0, voucher_no TEXT DEFAULT '', note TEXT DEFAULT '');
"""

FIELDS = ("fy", "number", "kind", "method", "title", "reason", "budget_item_id", "amount",
          "median_price", "vendor", "vendor_tax_id", "vendor_vat", "egp_no", "date_request",
          "due_date", "rent_from", "rent_to", "exchange_asset_id", "committee", "requester", "note")


def suggest_method(amount, limit=SPECIFIC_LIMIT) -> str:
    return METHODS[0] if float(amount or 0) <= limit else METHODS[3]


def wht(amount, vendor_vat=True, rate=WHT_RATE, minimum=WHT_MIN) -> float:
    """ภาษีหัก ณ ที่จ่ายจากยอดก่อนภาษีมูลค่าเพิ่ม."""
    base = float(amount or 0) / (1 + VAT) if vendor_vat else float(amount or 0)
    return round(base * rate, 2) if float(amount or 0) >= minimum else 0.0


class ProcurementMixin:
    """Procurement methods of :class:`venitsupply.db.Store`."""

    def _proc_init(self):
        self.con.executescript(SQL)

    # ----------------------------------------------------------- helpers
    def next_proc_number(self, kind, fy) -> str:
        pre = KIND_PREFIX.get(kind, "พ")
        n = 1
        while self.one("SELECT 1 FROM procurements WHERE number=?", (f"{pre}.{n:03d}/{fy}",)):
            n += 1
        return f"{pre}.{n:03d}/{fy}"

    def procurement(self, pid):
        return self.one("SELECT p.*, b.name AS budget_name, b.category, b.type, b.plan, b.task "
                        "FROM procurements p LEFT JOIN budget_items b ON b.id=p.budget_item_id "
                        "WHERE p.id=?", (pid,))

    def lines(self, pid):
        return self.q("SELECT * FROM procurement_lines WHERE proc_id=? ORDER BY id", (pid,))

    def payments(self, pid=None):
        if pid:
            return self.q("SELECT * FROM payments WHERE proc_id=? ORDER BY date, id", (pid,))
        return self.q("SELECT pay.*, p.number, p.title, p.vendor FROM payments pay "
                      "JOIN procurements p ON p.id=pay.proc_id ORDER BY pay.date, pay.id")

    def paid(self, pid) -> float:
        return self.one("SELECT IFNULL(SUM(amount),0) AS s FROM payments WHERE proc_id=?", (pid,))["s"]

    def procurements(self, fy=None, kind=None, status=None, text=""):
        sql = ("SELECT p.*, b.name AS budget_name, b.category, b.type FROM procurements p "
               "LEFT JOIN budget_items b ON b.id=p.budget_item_id WHERE 1=1")
        args = []
        for col, v in (("p.fy", fy), ("p.kind", kind), ("p.status", status)):
            if v:
                sql += f" AND {col}=?"
                args.append(v)
        if text:
            sql += " AND (p.number LIKE ? OR p.title LIKE ? OR p.vendor LIKE ? OR p.egp_no LIKE ?)"
            args += [f"%{text}%"] * 4
        return self.q(sql + " ORDER BY p.date_request DESC, p.id DESC", args)

    def check_budget(self, bid, amount, exclude_proc=None) -> dict:
        """มีเงินเท่าไร / ครั้งนี้ / เหลือเท่าไร — raises when the money is not enough."""
        b = self.balance(bid, exclude_proc=exclude_proc)
        after = round(b["available"] - float(amount or 0), 2)
        out = dict(b, this=float(amount or 0), after=after)
        if after < -0.004:
            raise ValueError(f"งบประมาณไม่พอ: คงเหลือ {b['available']:,.2f} บาท "
                             f"ครั้งนี้ {float(amount):,.2f} บาท ขาด {-after:,.2f} บาท")
        return out

    # -------------------------------------------------------------- flow
    def save_procurement(self, data: dict, lines=None, pid=None) -> int:
        d = {k: data[k] for k in FIELDS if k in data}
        if not str(d.get("title", "x")).strip():
            raise ValueError("กรอกชื่อรายการ/โครงการ")
        if d.get("kind") and d["kind"] not in KINDS:
            raise ValueError("ประเภทการจัดหาไม่ถูกต้อง")
        lines = lines if lines is not None else None
        if lines:
            total = round(sum(float(x.get("qty") or 0) * float(x.get("unit_price") or 0) for x in lines), 2)
            if not d.get("amount"):
                d["amount"] = total
        cur = self.procurement(pid) if pid else None
        if cur and cur["status"] not in ("ขออนุมัติ", "อนุมัติแล้ว"):
            # after the order only notes and dates may change
            d = {k: v for k, v in d.items() if k in ("note", "committee", "due_date", "egp_no", "vendor_tax_id")}
            lines = None
        if d.get("budget_item_id") and "amount" in d:
            self.check_budget(d["budget_item_id"], d["amount"], exclude_proc=pid)
        if not pid and not d.get("method"):
            d["method"] = suggest_method(d.get("amount") or 0, self.fnum("specific_limit", SPECIFIC_LIMIT))
        if not pid:
            d.setdefault("fy", TD.fiscal_year(d.get("date_request") or TD.today()))
            d.setdefault("date_request", str(TD.today()))
            if not d.get("number"):
                d["number"] = self.next_proc_number(d.get("kind", "ซื้อ"), d["fy"])
            pid = self.run(f"INSERT INTO procurements({','.join(d)}) VALUES({','.join('?' * len(d))})",
                           tuple(d.values()))
        elif d:
            self.run(f"UPDATE procurements SET {','.join(f'{k}=?' for k in d)} WHERE id=?", (*d.values(), pid))
        if lines is not None:
            self.con.execute("DELETE FROM procurement_lines WHERE proc_id=?", (pid,))
            for x in lines:
                self.con.execute("INSERT INTO procurement_lines(proc_id,name,qty,unit,unit_price,target,"
                                 "category_id) VALUES(?,?,?,?,?,?,?)",
                                 (pid, x["name"], x.get("qty") or 1, x.get("unit", ""),
                                  x.get("unit_price") or 0, x.get("target", ""), x.get("category_id")))
            self.con.commit()
        return pid

    def _status(self, pid, want, new, **cols):
        p = self.procurement(pid)
        if p is None:
            raise ValueError("ไม่พบรายการ")
        if p["status"] not in want:
            raise ValueError(f"รายการอยู่ในขั้น «{p['status']}» ทำขั้นนี้ไม่ได้")
        cols["status"] = new
        self.run(f"UPDATE procurements SET {','.join(f'{k}=?' for k in cols)} WHERE id=?",
                 (*cols.values(), pid))
        return p

    def approve(self, pid, date=None):
        p = self.procurement(pid)
        if p and p["budget_item_id"]:
            self.check_budget(p["budget_item_id"], p["amount"], exclude_proc=pid)
        self._status(pid, ("ขออนุมัติ",), "อนุมัติแล้ว", date_approve=str(date or TD.today()))

    def order(self, pid, vendor, contract_amount, order_no="", date=None, due_date=None,
              contract_type=CONTRACT_TYPES[0], egp_no=None, vendor_vat=None, vendor_tax_id=None):
        """ก่อหนี้ผูกพัน: ออกใบสั่งซื้อ/สั่งจ้าง หรือทำสัญญา."""
        p = self.procurement(pid)
        if p and p["budget_item_id"]:
            self.check_budget(p["budget_item_id"], contract_amount, exclude_proc=pid)
        cols = dict(vendor=vendor, contract_amount=float(contract_amount), order_no=order_no,
                    order_date=str(date or TD.today()), due_date=due_date or None,
                    contract_type=contract_type)
        if egp_no is not None:
            cols["egp_no"] = egp_no
        if vendor_vat is not None:
            cols["vendor_vat"] = int(bool(vendor_vat))
        if vendor_tax_id is not None:
            cols["vendor_tax_id"] = vendor_tax_id
        if not cols["order_no"]:
            cols["order_no"] = p["number"] if p else ""
        self._status(pid, ("อนุมัติแล้ว",), "ก่อหนี้ผูกพัน", **cols)

    def fine_for(self, pid, delivered) -> float:
        """ค่าปรับส่งมอบล่าช้า: ต่อวัน = ราคา × อัตรา (ซื้อ/เช่า ค่าเริ่มต้น 0.2 %, จ้าง 0.1 %
        ไม่ต่ำกว่าวันละ 100 บาทสำหรับงานจ้าง) — อัตราแก้ได้ในตั้งค่าตามที่ระบุในสัญญา."""
        p = self.procurement(pid)
        due, got = TD.parse(p["due_date"]), TD.parse(delivered)
        if not due or not got or got <= due:
            return 0.0
        hire = p["kind"] == "จ้าง"
        rate = self.fnum("fine_rate_hire" if hire else "fine_rate", 0.1 if hire else 0.2) / 100
        per_day = (p["contract_amount"] or p["amount"] or 0) * rate
        if hire:
            per_day = max(per_day, 100.0)
        return round(per_day * (got - due).days, 2)

    def inspect_proc(self, pid, date=None, note="", fine=None, register=True):
        """ตรวจรับ — ลงทะเบียนครุภัณฑ์/รับวัสดุเข้าคลังจากรายการที่เลือกไว้."""
        date = str(date or TD.today())
        if fine is None:
            fine = self.fine_for(pid, date)
        p = self._status(pid, ("ก่อหนี้ผูกพัน",), "ตรวจรับแล้ว", inspect_date=date,
                         inspect_note=note, fine=fine)
        if register:
            self.register_lines(pid, date)
        if p["kind"] == "แลกเปลี่ยน" and p["exchange_asset_id"]:
            self.dispose(p["exchange_asset_id"], date, "แลกเปลี่ยน", 0, p["number"])
        return fine

    def register_lines(self, pid, date):
        p = self.procurement(pid)
        for ln in self.lines(pid):
            if ln["registered"] or ln["target"] not in ("asset", "material"):
                continue
            if ln["target"] == "asset":
                for _ in range(max(1, int(round(ln["qty"] or 1)))):
                    self.save_asset(dict(name=ln["name"], category_id=ln["category_id"],
                                         unit=ln["unit"] or "เครื่อง", price=ln["unit_price"],
                                         acquire_date=date, vendor=p["vendor"],
                                         document_no=p["order_no"] or p["number"],
                                         method=p["method"], budget="เงินงบประมาณ", status="ใช้งาน"))
            else:
                m = self.one("SELECT id FROM materials WHERE name=?", (ln["name"],))
                mid = m["id"] if m else self.save_material(dict(name=ln["name"], unit=ln["unit"] or "ชิ้น",
                                                                category_id=ln["category_id"]))
                self.receive(mid, date, ln["qty"], ln["unit_price"], p["order_no"] or p["number"],
                             p["vendor"], f"ตรวจรับ {p['number']}")
            self.con.execute("UPDATE procurement_lines SET registered=1 WHERE id=?", (ln["id"],))
        self.con.commit()

    def pay(self, pid, amount=None, date=None, voucher_no="", note="", final=None) -> int:
        """เบิกจ่าย (จ่ายได้หลายงวด) — หักภาษี ณ ที่จ่ายและค่าปรับ."""
        p = self.procurement(pid)
        if p["status"] not in ("ก่อหนี้ผูกพัน", "ตรวจรับแล้ว"):
            raise ValueError("ต้องออกใบสั่ง/ทำสัญญาก่อนจึงเบิกจ่ายได้")
        total = p["contract_amount"] or p["amount"]
        done = self.paid(pid)
        amount = round(total - done, 2) if amount is None else float(amount)
        if amount <= 0 or done + amount > total + 0.004:
            raise ValueError(f"จำนวนเงินเกินยอดตามใบสั่ง/สัญญา (คงค้าง {total - done:,.2f} บาท)")
        taken = self.one("SELECT IFNULL(SUM(fine),0) AS s FROM payments WHERE proc_id=?", (pid,))["s"]
        fine = max(0.0, (p["fine"] or 0) - taken)
        tax = wht(amount, bool(p["vendor_vat"]), self.fnum("wht_rate", 1) / 100,
                  self.fnum("wht_min", WHT_MIN))
        net = round(amount - tax - fine, 2)
        mid = self.run("INSERT INTO payments(proc_id,date,amount,wht,fine,net,voucher_no,note) "
                       "VALUES(?,?,?,?,?,?,?,?)",
                       (pid, str(date or TD.today()), amount, tax, fine, net, voucher_no, note))
        if final or (final is None and done + amount >= total - 0.004):
            self.run("UPDATE procurements SET status='เบิกจ่ายแล้ว' WHERE id=?", (pid,))
        return mid

    def cancel(self, pid, reason=""):
        if self.paid(pid) > 0:
            raise ValueError("รายการนี้เบิกจ่ายแล้ว ยกเลิกไม่ได้")
        self.run("UPDATE procurements SET status='ยกเลิก', cancel_reason=? WHERE id=?", (reason, pid))

    def delete_procurement(self, pid):
        if self.paid(pid) > 0:
            raise ValueError("รายการนี้เบิกจ่ายแล้ว ลบไม่ได้")
        self.con.execute("DELETE FROM procurement_lines WHERE proc_id=?", (pid,))
        self.run("DELETE FROM procurements WHERE id=?", (pid,))

    # -------------------------------------------------------- statistics
    def _events(self, start: _dt.date, end: _dt.date):
        """(date, kind, amount, proc) for requests, commitments and payments in [start, end]."""
        s, e = str(start), str(end)
        ev = []
        for p in self.q("SELECT p.*, b.category FROM procurements p LEFT JOIN budget_items b "
                        "ON b.id=p.budget_item_id WHERE p.status<>'ยกเลิก'"):
            if p["date_request"] and s <= p["date_request"] <= e:
                ev.append((p["date_request"], "request", p["amount"] or 0, p))
            if p["order_date"] and s <= p["order_date"] <= e:
                ev.append((p["order_date"], "commit", p["contract_amount"] or 0, p))
        for pay in self.q("SELECT pay.*, p.kind, p.method, b.category FROM payments pay "
                          "JOIN procurements p ON p.id=pay.proc_id "
                          "LEFT JOIN budget_items b ON b.id=p.budget_item_id "
                          "WHERE pay.date BETWEEN ? AND ?", (s, e)):
            ev.append((pay["date"], "paid", pay["amount"], pay))
        return ev

    def stats(self, mode, fy=None, year=None, month=None, fy_from=None, fy_to=None) -> list[dict]:
        """mode 'day' (year, month ค.ศ.), 'month' (fy), 'year' (fy_from..fy_to).

        Each bucket: label, count (requests), requested, committed, paid.
        """
        if mode == "day":
            start = _dt.date(year, month, 1)
            end = (_dt.date(year + (month == 12), month % 12 + 1, 1) - _dt.timedelta(days=1))
            keys = [start + _dt.timedelta(days=i) for i in range((end - start).days + 1)]
            label = {k: str(k.day) for k in keys}
            key = TD.parse
        elif mode == "month":
            start, end = TD.fiscal_range(fy)
            keys = [(start.year + (start.month + i - 1) // 12, (start.month + i - 1) % 12 + 1) for i in range(12)]
            label = {k: f"{TD.MONTHS_SHORT[k[1] - 1]} {str(k[0] + 543)[2:]}" for k in keys}
            key = (lambda d: (TD.parse(d).year, TD.parse(d).month))
        else:
            start, end = TD.fiscal_range(fy_from)[0], TD.fiscal_range(fy_to)[1]
            keys = list(range(fy_from, fy_to + 1))
            label = {k: str(k) for k in keys}
            key = TD.fiscal_year
        out = {k: dict(label=label[k], count=0, requested=0.0, committed=0.0, paid=0.0) for k in keys}
        for d, kind, amt, _ in self._events(start, end):
            k = key(d)
            if k not in out:
                continue
            if kind == "request":
                out[k]["count"] += 1
                out[k]["requested"] += amt
            elif kind == "commit":
                out[k]["committed"] += amt
            else:
                out[k]["paid"] += amt
        return [out[k] for k in keys]

    def breakdown(self, fy_from, fy_to, by="method") -> list[dict]:
        """Commitments of fiscal years fy_from..fy_to grouped by method / kind / category / vendor."""
        start, end = TD.fiscal_range(fy_from)[0], TD.fiscal_range(fy_to)[1]
        out: dict[str, dict] = {}
        for p in self.q("SELECT p.*, b.category FROM procurements p LEFT JOIN budget_items b "
                        "ON b.id=p.budget_item_id WHERE p.status<>'ยกเลิก' "
                        "AND p.date_request BETWEEN ? AND ?", (str(start), str(end))):
            k = p[by] or "-"
            t = out.setdefault(k, dict(label=k, count=0, amount=0.0, committed=0.0, paid=0.0))
            t["count"] += 1
            t["amount"] += p["amount"] or 0
            t["committed"] += p["contract_amount"] or 0
            t["paid"] += self.paid(p["id"])
        return sorted(out.values(), key=lambda x: -x["amount"])
