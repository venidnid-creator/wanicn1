# SPDX-License-Identifier: GPL-3.0-or-later
"""รายงานพัสดุ: HTML (สำหรับพิมพ์/ส่งออก PDF) และแถวตาราง (ส่งออกตารางคำนวณ).

ทุกรายงานมีหัวหน่วยงาน, ช่องลงนามเจ้าหน้าที่ตามระเบียบฯ และบรรทัดผู้พัฒนาโปรแกรม.
"""
from __future__ import annotations

from html import escape

from . import DEVELOPER, PRODUCT_EN, PRODUCT_TH, QUALIFICATION
from . import thaidate as TD

FONT = "'TH Sarabun New','TH SarabunPSK','Laksaman','Loma','Tahoma'"


def money(v) -> str:
    return f"{float(v or 0):,.2f}"


def qty(v) -> str:
    v = float(v or 0)
    return f"{v:,.0f}" if abs(v - round(v)) < 1e-9 else f"{v:,.2f}"


def _e(v) -> str:
    return escape("" if v is None else str(v))


class Report:
    """A titled table with signature lines."""

    def __init__(self, store, title, subtitle="", landscape=False):
        self.s = store
        self.title = title
        self.subtitle = subtitle
        self.landscape = landscape
        self.header: list[str] = []
        self.rows: list[list] = []
        self.align: list[str] = []
        self.totals: list | None = None
        self.before = ""
        self.signers = ["officer", "head_officer", "head"]

    # rows used for the spreadsheet export
    def table(self) -> list[list]:
        org = self.s.setting("org_name") or ""
        out = [[self.title], [org + ("  " + self.subtitle if self.subtitle else "")], self.header]
        out += self.rows
        if self.totals:
            out.append(self.totals)
        return out

    def html(self) -> str:
        st = self.s.settings()
        org = _e(st.get("org_name") or "(ยังไม่ได้ตั้งชื่อหน่วยงาน — ไปที่ «ตั้งค่า»)")
        h = [f"<html><body style=\"font-family:{FONT}; font-size:14pt;\">",
             f"<p align=center style='font-size:18pt'><b>{_e(self.title)}</b><br>{org}"]
        if self.subtitle:
            h.append(f"<br>{_e(self.subtitle)}")
        h.append("</p>")
        if self.before:
            h.append(self.before)
        if self.header:
            h.append("<table border=1 cellspacing=0 cellpadding=3 width='100%' "
                     "style='border-collapse:collapse; font-size:12pt'>")
            h.append("<tr style='background:#E8EEF5'>" + "".join(
                f"<th>{_e(c)}</th>" for c in self.header) + "</tr>")
            for r in self.rows:
                h.append("<tr>" + "".join(
                    f"<td align={self._al(i)}>{_e(self._fmt(i, v))}</td>"
                    for i, v in enumerate(r)) + "</tr>")
            if self.totals:
                h.append("<tr style='background:#F4F1E8'>" + "".join(
                    f"<td align={self._al(i)}><b>{_e(self._fmt(i, v))}</b></td>"
                    for i, v in enumerate(self.totals)) + "</tr>")
            h.append("</table>")
        h.append(self._signatures(st))
        h.append(f"<p style='font-size:10pt; color:#55657A'>พิมพ์เมื่อ {TD.thai(TD.today())} · "
                 f"{PRODUCT_TH} ({PRODUCT_EN}) · ผู้พัฒนา {DEVELOPER} {QUALIFICATION} · "
                 "ตรวจสอบความถูกต้องกับระเบียบกระทรวงการคลังว่าด้วยการจัดซื้อจัดจ้างและ"
                 "การบริหารพัสดุภาครัฐ พ.ศ. 2560 ก่อนใช้งานจริง</p>")
        h.append("</body></html>")
        return "".join(h)

    def _al(self, i):
        return self.align[i] if i < len(self.align) else "left"

    def _fmt(self, i, v):
        a = self._al(i)
        if isinstance(v, float) and a == "right":
            return money(v)
        if isinstance(v, int) and a == "right":
            return f"{v:,}"
        return v

    def _signatures(self, st) -> str:
        cells = []
        for k in self.signers:
            name = st.get(k) or "...................................................."
            cells.append("<td align=center width='33%'><br><br>ลงชื่อ ......................................<br>"
                         f"( {_e(name)} )<br>{_e(st.get(k + '_pos', ''))}</td>")
        return "<br><table width='100%'><tr>" + "".join(cells) + "</tr></table>"


# ---------------------------------------------------------------- reports
def asset_list(store, status=None) -> Report:
    r = Report(store, "บัญชีครุภัณฑ์", status or "ทุกสถานะ", landscape=True)
    r.header = ["ลำดับ", "เลขรหัสครุภัณฑ์", "รายการ", "ยี่ห้อ/รุ่น", "หมายเลขเครื่อง", "วันที่ได้มา",
                "ราคา (บาท)", "หน่วยงาน/สถานที่", "ผู้รับผิดชอบ", "สถานะ"]
    r.align = ["center", "left", "left", "left", "left", "center", "right", "left", "left", "center"]
    tot = 0.0
    for i, a in enumerate(store.assets(status=status), 1):
        r.rows.append([i, a["number"], a["name"], " ".join(x for x in (a["brand"], a["model"]) if x),
                       a["serial"], TD.thai(a["acquire_date"]), float(a["price"] or 0),
                       " / ".join(x for x in (a["department"], a["location"]) if x),
                       a["custodian"] or "", a["status"]])
        tot += a["price"] or 0
    r.totals = ["", "", f"รวม {len(r.rows)} รายการ", "", "", "", tot, "", "", ""]
    return r


def asset_card(store, aid, until_fy=None) -> Report:
    """ทะเบียนคุมทรัพย์สิน (หนึ่งรายการ) พร้อมตารางค่าเสื่อมราคา."""
    a = store.asset(aid)
    r = Report(store, "ทะเบียนคุมทรัพย์สิน", f"เลขรหัส {a['number']}")
    info = [("ประเภท", a["category"]), ("รายการ", a["name"]),
            ("ยี่ห้อ/รุ่น", " ".join(x for x in (a["brand"], a["model"]) if x)),
            ("หมายเลขเครื่อง", a["serial"]), ("วันที่ได้มา", TD.thai(a["acquire_date"])),
            ("ราคาต่อหน่วย", money(a["price"]) + " บาท"), ("วิธีได้มา", a["method"]),
            ("แหล่งเงิน", a["budget"]), ("เลขที่เอกสาร", a["document_no"]), ("ผู้ขาย/ผู้รับจ้าง", a["vendor"]),
            ("หน่วยงาน", a["department"]), ("สถานที่ตั้ง", a["location"]),
            ("ผู้รับผิดชอบ", a["custodian"]), ("อายุการใช้งาน", f"{a['life_years'] or 0:g} ปี"),
            ("ราคาซาก", money(a["salvage"]) + " บาท"), ("สถานะ", a["status"])]
    if a["disposed_date"]:
        info += [("จำหน่ายเมื่อ", TD.thai(a["disposed_date"])), ("วิธีจำหน่าย", a["disposal_method"]),
                 ("จำนวนเงินที่ได้", money(a["disposal_amount"]) + " บาท")]
    cells = "".join(f"<tr><td width='30%'><b>{_e(k)}</b></td><td>{_e(v)}</td></tr>" for k, v in info)
    r.before = f"<table cellpadding=2 width='100%'>{cells}</table><br>"
    rows = store.depreciation(a, until_fy=until_fy)
    if rows:
        r.header = ["ปีงบประมาณ", "จำนวนวัน", "ค่าเสื่อมราคา (บาท)", "ค่าเสื่อมสะสม (บาท)",
                    "มูลค่าสุทธิ (บาท)"]
        r.align = ["center", "right", "right", "right", "right"]
        r.rows = [[x["fy"], x["days"], x["dep"], x["acc"], x["book"]] for x in rows]
    else:
        r.before += ("<p>ราคาต่ำกว่าเกณฑ์การบันทึกเป็นสินทรัพย์ "
                     f"({money(store.fnum('threshold'))} บาท) — ไม่คิดค่าเสื่อมราคา</p>")
    return r


def depreciation_year(store, fy) -> Report:
    r = Report(store, "รายงานค่าเสื่อมราคาครุภัณฑ์", f"ประจำปีงบประมาณ พ.ศ. {fy}", landscape=True)
    r.header = ["ลำดับ", "เลขรหัสครุภัณฑ์", "รายการ", "วันที่ได้มา", "อายุ (ปี)", "ราคาทุน",
                "ค่าเสื่อมปีนี้", "ค่าเสื่อมสะสม", "มูลค่าสุทธิ"]
    r.align = ["center", "left", "left", "center", "center", "right", "right", "right", "right"]
    t = [0.0, 0.0, 0.0, 0.0]
    for i, x in enumerate(store.depreciation_report(fy), 1):
        a = x["asset"]
        r.rows.append([i, a["number"], a["name"], TD.thai(a["acquire_date"]), f"{a['life_years']:g}",
                       float(a["price"]), x["dep"], x["acc"], x["book"]])
        for k, v in enumerate((a["price"], x["dep"], x["acc"], x["book"])):
            t[k] += v
    r.totals = ["", "", "รวม", "", "", *t]
    return r


def material_balance(store) -> Report:
    r = Report(store, "รายงานวัสดุคงเหลือ", f"ณ วันที่ {TD.thai(TD.today())}")
    r.header = ["ลำดับ", "รหัส", "รายการ", "ประเภท", "หน่วย", "คงเหลือ", "มูลค่า (บาท)", "หมายเหตุ"]
    r.align = ["center", "left", "left", "left", "center", "right", "right", "left"]
    tot = 0.0
    for i, m in enumerate(store.materials(), 1):
        low = "ต่ำกว่าจุดสั่งซื้อ" if m["min_qty"] and m["qty"] <= m["min_qty"] else ""
        r.rows.append([i, m["code"], m["name"], m["category"] or "", m["unit"], qty(m["qty"]),
                       float(m["value"]), low])
        tot += m["value"]
    r.totals = ["", "", "รวมมูลค่า", "", "", "", tot, ""]
    return r


def stock_card(store, mid) -> Report:
    m = store.one("SELECT m.*, c.name AS category FROM materials m "
                  "LEFT JOIN categories c ON c.id=m.category_id WHERE m.id=?", (mid,))
    r = Report(store, "บัญชีวัสดุ", f"{m['code']} {m['name']} · หน่วย {m['unit']} · "
               f"ประเภท {m['category'] or '-'}", landscape=True)
    r.header = ["วัน เดือน ปี", "รับจาก/จ่ายให้", "เลขที่เอกสาร", "ราคาต่อหน่วย", "รับ", "จ่าย",
                "คงเหลือ", "มูลค่าคงเหลือ", "หมายเหตุ"]
    r.align = ["center", "left", "left", "right", "right", "right", "right", "right", "left"]
    for c in store.card(mid):
        who = c["party"] or ""
        if c["department"]:
            who = f"{who} ({c['department']})" if who else c["department"]
        r.rows.append([TD.thai(c["date"]), who, c["doc_no"], float(round(c["unit_price"], 2)),
                       qty(c["qty"]) if c["kind"] == "in" else "",
                       qty(c["qty"]) if c["kind"] == "out" else "",
                       qty(c["bal_qty"]), float(c["bal_val"]), c["note"]])
    return r


def issue_slip(store, move_ids) -> Report:
    """ใบเบิกพัสดุ for one or more issue moves."""
    r = Report(store, "ใบเบิกพัสดุ")
    r.header = ["ลำดับ", "รายการ", "จำนวน", "หน่วย", "ราคาต่อหน่วย", "จำนวนเงิน", "หมายเหตุ"]
    r.align = ["center", "left", "right", "center", "right", "right", "left"]
    party = dept = doc = date = ""
    tot = 0.0
    for i, mv in enumerate(move_ids, 1):
        row = store.one("SELECT mv.*, m.name, m.unit, m.id AS mid FROM moves mv "
                        "JOIN materials m ON m.id=mv.material_id WHERE mv.id=?", (mv,))
        c = next(x for x in store.card(row["mid"]) if x["id"] == mv)
        party, doc, date = row["party"], row["doc_no"], row["date"]
        dept = c["department"] or dept
        r.rows.append([i, row["name"], qty(row["qty"]), row["unit"], float(round(c["unit_price"], 2)),
                       float(c["value"]), row["note"]])
        tot += c["value"]
    r.subtitle = f"เลขที่ {doc or '-'}  วันที่ {TD.thai(date)}"
    r.before = (f"<p>ข้าพเจ้า {_e(party or '..............................')} "
                f"หน่วยงาน {_e(dept or '..............................')} "
                "ขอเบิกพัสดุตามรายการต่อไปนี้ เพื่อใช้ในราชการ</p>")
    r.totals = ["", "รวมเงิน", "", "", "", tot, ""]
    return r


def loans_report(store, open_only=False) -> Report:
    r = Report(store, "ทะเบียนการยืมพัสดุ", "เฉพาะที่ยังไม่คืน" if open_only else "ทั้งหมด",
               landscape=True)
    r.header = ["ลำดับ", "เลขรหัส", "รายการ", "ผู้ยืม", "หน่วยงาน", "วัตถุประสงค์", "วันที่ยืม",
                "กำหนดคืน", "วันที่คืน", "สภาพเมื่อคืน"]
    r.align = ["center", "left", "left", "left", "left", "left", "center", "center", "center", "left"]
    for i, ln in enumerate(store.loans(open_only), 1):
        r.rows.append([i, ln["number"], ln["asset_name"], ln["borrower"], ln["department"],
                       ln["purpose"], TD.thai(ln["date_out"]), TD.thai(ln["due_date"]),
                       TD.thai(ln["date_back"]) or "ยังไม่คืน", ln["condition_back"]])
    return r


def inspection_report(store, fy) -> Report:
    """รายงานผลการตรวจสอบพัสดุประจำปี (ข้อ 213)."""
    rows = store.inspection(fy)
    r = Report(store, "รายงานผลการตรวจสอบพัสดุประจำปี", f"ปีงบประมาณ พ.ศ. {fy}", landscape=True)
    r.header = ["ลำดับ", "เลขรหัสครุภัณฑ์", "รายการ", "สถานที่", "ราคา (บาท)", "ผลการตรวจ", "หมายเหตุ"]
    r.align = ["center", "left", "left", "left", "right", "center", "left"]
    for i, x in enumerate(rows, 1):
        a = x["asset"]
        r.rows.append([i, a["number"], a["name"], a["location"], float(a["price"] or 0),
                       x["result"] or "ยังไม่ได้ตรวจ", x["note"]])
    counts = {}
    for x in rows:
        counts[x["result"] or "ยังไม่ได้ตรวจ"] = counts.get(x["result"] or "ยังไม่ได้ตรวจ", 0) + 1
    summ = " · ".join(f"{k} {v} รายการ" for k, v in counts.items())
    r.before = (f"<p>คณะกรรมการตรวจสอบพัสดุได้ตรวจสอบการรับจ่ายพัสดุตั้งแต่วันที่ "
                f"{TD.thai(TD.fiscal_range(fy)[0])} ถึงวันที่ "
                f"{TD.thai(TD.fiscal_range(fy)[1])} และตรวจนับพัสดุคงเหลือ ณ วันสิ้นปีงบประมาณ "
                f"รวม {len(rows)} รายการ — {_e(summ)}</p>")
    r.signers = ["officer", "head_officer", "head"]
    return r


def disposal_report(store) -> Report:
    r = Report(store, "ทะเบียนการจำหน่ายพัสดุ", landscape=True)
    r.header = ["ลำดับ", "เลขรหัส", "รายการ", "ราคาทุน", "วันที่จำหน่าย", "วิธีจำหน่าย",
                "จำนวนเงินที่ได้", "เลขที่เอกสาร"]
    r.align = ["center", "left", "left", "right", "center", "left", "right", "left"]
    for i, a in enumerate(store.assets(status="จำหน่ายแล้ว"), 1):
        r.rows.append([i, a["number"], a["name"], float(a["price"] or 0), TD.thai(a["disposed_date"]),
                       a["disposal_method"], float(a["disposal_amount"] or 0), a["disposal_doc"]])
    return r


def to_pdf(report: Report, path) -> None:
    """Render *report* to an A4 PDF with Qt (Thai text shaped by Qt)."""
    from PySide6.QtCore import QMarginsF, QSizeF
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument

    w = QPdfWriter(str(path))
    w.setResolution(150)
    w.setPageLayout(QPageLayout(QPageSize(QPageSize.A4),
                                QPageLayout.Landscape if report.landscape else QPageLayout.Portrait,
                                QMarginsF(12, 12, 12, 12)))
    w.setTitle(report.title)
    w.setCreator(f"{PRODUCT_TH} ({PRODUCT_EN})")
    doc = QTextDocument()
    doc.setHtml(report.html())
    rect = w.pageLayout().paintRectPixels(w.resolution())
    doc.setPageSize(QSizeF(rect.width(), rect.height()))
    doc.print_(w)


def to_xlsx(report: Report, path) -> None:
    from . import xlsx
    xlsx.write(path, [(report.title, report.table())], header_rows=3)


# ======================================================= budget & procurement
def _budget_box(store, p) -> str:
    if not p["budget_item_id"]:
        return ""
    b = store.balance(p["budget_item_id"], exclude_proc=p["id"])
    this = p["contract_amount"] or p["amount"] or 0
    it = store.budget_item(p["budget_item_id"])
    rows = [("แผนงาน / งาน", f"{it['plan']} / {it['task']}"),
            ("งบ / หมวด / ประเภท", f"{it['grp']} / {it['category']} / {it['type']}"),
            ("รายการตามข้อบัญญัติ", it["name"]),
            ("งบประมาณตามข้อบัญญัติ", money(b["approved"]) + " บาท"),
            ("โอนเพิ่ม/ลด และข้อบัญญัติเพิ่มเติม", money(b["changes"]) + " บาท"),
            ("ใช้ไปแล้ว/ผูกพัน/จองไว้ (รายการอื่น)", money(b["paid"] + b["committed"] + b["reserved"]) + " บาท"),
            ("คงเหลือก่อนครั้งนี้", money(b["available"]) + " บาท"),
            ("ครั้งนี้", money(this) + " บาท"),
            ("คงเหลือหลังครั้งนี้", money(b["available"] - this) + " บาท")]
    cells = "".join(f"<tr><td width='42%'>{_e(k)}</td><td><b>{_e(v)}</b></td></tr>" for k, v in rows)
    return ("<p><b>ตรวจสอบงบประมาณ</b></p><table border=1 cellspacing=0 cellpadding=3 width='100%' "
            f"style='border-collapse:collapse; font-size:12pt'>{cells}</table>")


def _lines_table(r, store, pid):
    r.header = ["ลำดับ", "รายการ", "จำนวน", "หน่วย", "ราคาต่อหน่วย", "จำนวนเงิน"]
    r.align = ["center", "left", "right", "center", "right", "right"]
    tot = 0.0
    for i, ln in enumerate(store.lines(pid), 1):
        amt = round((ln["qty"] or 0) * (ln["unit_price"] or 0), 2)
        r.rows.append([i, ln["name"], qty(ln["qty"]), ln["unit"], float(ln["unit_price"] or 0), amt])
        tot += amt
    return tot


def proc_request(store, pid) -> Report:
    """รายงานขอซื้อ/ขอจ้าง/ขอเช่า/ขอแลกเปลี่ยน (ระเบียบฯ ข้อ 22)."""
    p = store.procurement(pid)
    r = Report(store, f"รายงานขอ{p['kind']}", f"เลขที่ {p['number']}  วันที่ {TD.thai(p['date_request'])}")
    tot = _lines_table(r, store, pid)
    amount = p["amount"] or tot
    info = [("1. เหตุผลและความจำเป็น", p["reason"] or "-"),
            ("2. รายละเอียดของพัสดุ", p["title"]),
            ("3. ราคากลาง", (money(p["median_price"]) + " บาท") if p["median_price"] else "-"),
            ("4. วงเงินที่จะ" + p["kind"], f"{money(amount)} บาท (รวมภาษีมูลค่าเพิ่ม)"),
            ("5. กำหนดเวลาที่ต้องการใช้", TD.thai(p["due_date"]) or "-"),
            ("6. วิธีจัดหาและเหตุผล", p["method"] or "-"),
            ("7. หลักเกณฑ์การพิจารณาคัดเลือก", "เกณฑ์ราคา"),
            ("8. ผู้ตรวจรับพัสดุ / คณะกรรมการ", p["committee"] or "-")]
    if p["kind"] == "เช่า":
        info.append(("ระยะเวลาเช่า", f"{TD.thai(p['rent_from'])} ถึง {TD.thai(p['rent_to'])}"))
    if p["kind"] == "แลกเปลี่ยน" and p["exchange_asset_id"]:
        a = store.asset(p["exchange_asset_id"])
        info.append(("พัสดุที่นำไปแลกเปลี่ยน", f"{a['number']} {a['name']} (ราคาทุน {money(a['price'])} บาท)"))
    cells = "".join(f"<tr><td width='38%' valign=top><b>{_e(k)}</b></td><td>{_e(v)}</td></tr>" for k, v in info)
    r.before = (f"<p>เรียน {_e(store.setting('head_pos') or 'หัวหน้าหน่วยงานของรัฐ')}</p>"
                f"<p>ด้วย {_e(p['requester'] or 'เจ้าหน้าที่')} มีความประสงค์จะ{_e(p['kind'])} "
                f"{_e(p['title'])} เจ้าหน้าที่ได้ตรวจสอบแล้ว จึงขอรายงานตามระเบียบกระทรวงการคลังว่าด้วย"
                "การจัดซื้อจัดจ้างและการบริหารพัสดุภาครัฐ พ.ศ. 2560 ข้อ 22 ดังนี้</p>"
                f"<table cellpadding=2 width='100%'>{cells}</table><br>{_budget_box(store, p)}"
                "<p><b>รายละเอียดพัสดุ</b></p>")
    r.totals = ["", "รวมเป็นเงิน", "", "", "", tot]
    return r


def purchase_order(store, pid) -> Report:
    p = store.procurement(pid)
    title = {"ซื้อ": "ใบสั่งซื้อ", "จ้าง": "ใบสั่งจ้าง", "เช่า": "ใบสั่งเช่า"}.get(p["kind"], "ข้อตกลงแลกเปลี่ยน")
    if p["contract_type"] == "สัญญา":
        title = f"สัญญา{p['kind']} (สรุปสาระสำคัญ)"
    r = Report(store, title, f"เลขที่ {p['order_no'] or p['number']}  วันที่ {TD.thai(p['order_date'])}")
    tot = _lines_table(r, store, pid)
    amount = p["contract_amount"] or tot
    vat = round(amount * 7 / 107, 2) if p["vendor_vat"] else 0.0
    r.before = (f"<p>ผู้ขาย/ผู้รับจ้าง: <b>{_e(p['vendor'])}</b> เลขประจำตัวผู้เสียภาษี {_e(p['vendor_tax_id'] or '-')}"
                f"<br>อ้างอิง: รายงานขอ{_e(p['kind'])} เลขที่ {_e(p['number'])} · โครงการ e-GP {_e(p['egp_no'] or '-')}"
                f" · {_e(p['method'])}<br>กำหนดส่งมอบภายในวันที่ <b>{_e(TD.thai(p['due_date']) or '-')}</b></p>")
    r.totals = ["", f"รวมเป็นเงินทั้งสิ้น (ภาษีมูลค่าเพิ่ม {money(vat)})", "", "", "", float(amount)]
    return r


def inspection_doc(store, pid) -> Report:
    p = store.procurement(pid)
    r = Report(store, "ใบตรวจรับพัสดุ", f"ตามใบสั่ง/สัญญา เลขที่ {p['order_no'] or p['number']}")
    _lines_table(r, store, pid)
    late = ""
    if p["fine"]:
        late = f" ส่งมอบล่าช้า มีค่าปรับ {money(p['fine'])} บาท"
    r.before = (f"<p>ผู้ตรวจรับพัสดุได้ตรวจรับพัสดุจาก {_e(p['vendor'])} เมื่อวันที่ {_e(TD.thai(p['inspect_date']))} "
                f"(กำหนดส่งมอบ {_e(TD.thai(p['due_date']) or '-')}) ถูกต้องครบถ้วนตามใบสั่ง/สัญญา{_e(late)} "
                f"{_e(p['inspect_note'] or '')}</p><p>ผู้ตรวจรับ: {_e(p['committee'] or '-')}</p>")
    return r


def proc_register(store, fy) -> Report:
    r = Report(store, "ทะเบียนคุมการจัดซื้อจัดจ้าง", f"ปีงบประมาณ พ.ศ. {fy}", landscape=True)
    r.header = ["เลขที่", "วันที่ขอ", "ประเภท", "รายการ", "วิธี", "วงเงิน", "ผู้ขาย/ผู้รับจ้าง",
                "ตามใบสั่ง/สัญญา", "เบิกจ่ายแล้ว", "สถานะ"]
    r.align = ["left", "center", "center", "left", "left", "right", "left", "right", "right", "center"]
    t = [0.0, 0.0, 0.0]
    for p in reversed(store.procurements(fy)):
        paid = store.paid(p["id"])
        r.rows.append([p["number"], TD.thai(p["date_request"]), p["kind"], p["title"],
                       (p["method"] or "").replace("วิธี", ""), float(p["amount"] or 0), p["vendor"],
                       float(p["contract_amount"] or 0), float(paid), p["status"]])
        if p["status"] != "ยกเลิก":
            t[0] += p["amount"] or 0
            t[1] += p["contract_amount"] or 0
            t[2] += paid
    r.totals = ["", "", "", "รวม", "", t[0], "", t[1], t[2], ""]
    return r


def payment_register(store, fy) -> Report:
    start, end = TD.fiscal_range(fy)
    r = Report(store, "ทะเบียนคุมการเบิกจ่ายเงิน", f"ปีงบประมาณ พ.ศ. {fy}", landscape=True)
    r.header = ["วันที่", "เลขที่ใบสำคัญ", "อ้างอิง", "รายการ", "ผู้รับเงิน", "จำนวนเงิน", "ภาษีหัก ณ ที่จ่าย",
                "ค่าปรับ", "จ่ายสุทธิ"]
    r.align = ["center", "left", "left", "left", "left", "right", "right", "right", "right"]
    t = [0.0] * 4
    for x in store.payments():
        if not (str(start) <= x["date"] <= str(end)):
            continue
        r.rows.append([TD.thai(x["date"]), x["voucher_no"], x["number"], x["title"], x["vendor"],
                       float(x["amount"]), float(x["wht"]), float(x["fine"]), float(x["net"])])
        for i, k in enumerate(("amount", "wht", "fine", "net")):
            t[i] += x[k]
    r.totals = ["", "", "", "รวม", "", *t]
    return r


def budget_status(store, fy, level=None) -> Report:
    """รายงานสถานะงบประมาณรายจ่าย (ตามข้อบัญญัติ / หลังโอน / ผูกพัน / เบิกจ่าย / คงเหลือ)."""
    from .budget import LEVEL_NAMES, LEVELS
    sub = f"ประจำปีงบประมาณ พ.ศ. {fy} · ณ วันที่ {TD.thai(TD.today())}"
    r = Report(store, "รายงานสถานะการใช้จ่ายงบประมาณตามข้อบัญญัติ", sub, landscape=True)
    cols = ["ตามข้อบัญญัติ", "โอน/เพิ่มเติม", "งบหลังโอน", "จองเงิน", "ก่อหนี้ผูกพัน", "เบิกจ่ายแล้ว",
            "คงเหลือ", "% ใช้"]
    if level:
        n = LEVELS.index(level) + 1
        r.header = LEVEL_NAMES[:n] + cols
        rows = store.budget_summary(fy, level)
        keyf = (lambda x: list(x["key"]))
    else:
        r.header = ["แผนงาน", "งาน", "หมวด", "ประเภท", "รายการ"] + cols
        rows = store.budget_summary(fy)
        keyf = (lambda x: [x["item"]["plan"], x["item"]["task"], x["item"]["category"], x["item"]["type"],
                           x["item"]["name"]])
    k = len(r.header) - len(cols)
    r.align = ["left"] * k + ["right"] * len(cols)
    t = [0.0] * 7
    for x in rows:
        used = x["reserved"] + x["committed"] + x["paid"]
        pct = f"{used / x['budget'] * 100:.1f}" if x["budget"] else "-"
        vals = [x["approved"], x["changes"], x["budget"], x["reserved"], x["committed"], x["paid"], x["available"]]
        r.rows.append(keyf(x) + [float(v) for v in vals] + [pct])
        t = [a + b for a, b in zip(t, vals)]
    used = t[3] + t[4] + t[5]
    r.totals = ["รวม"] + [""] * (k - 1) + t + [f"{used / t[2] * 100:.1f}" if t[2] else "-"]
    return r


def stats_report(store, rows, title, subtitle) -> Report:
    r = Report(store, title, subtitle)
    r.header = ["ช่วงเวลา", "จำนวนรายการขอ", "วงเงินที่ขอ", "ก่อหนี้ผูกพัน", "เบิกจ่าย"]
    r.align = ["center", "right", "right", "right", "right"]
    t = [0, 0.0, 0.0, 0.0]
    for x in rows:
        r.rows.append([x["label"], x["count"], float(x["requested"]), float(x["committed"]), float(x["paid"])])
        t = [t[0] + x["count"], t[1] + x["requested"], t[2] + x["committed"], t[3] + x["paid"]]
    r.totals = ["รวม", *t]
    r.signers = ["officer", "head"]
    return r


def budget_compare(store, level="category") -> Report:
    """เปรียบเทียบงบประมาณ/รายจ่ายจริงหลายปี ตามระดับที่เลือก."""
    from .budget import LEVEL_NAMES, LEVELS
    years, rows = store.compare_years(level)
    actual = {r["fy"] for r in store.q("SELECT DISTINCT fy FROM budget_actuals")}
    r = Report(store, "เปรียบเทียบงบประมาณรายจ่ายหลายปี",
               f"สรุปตาม{LEVEL_NAMES[LEVELS.index(level)]} · ปีที่มีรายจ่ายจริงแสดงรายจ่ายจริง "
               "ปีอื่นแสดงงบประมาณหลังโอน", landscape=True)
    n = LEVELS.index(level) + 1
    r.header = LEVEL_NAMES[:n] + [f"{'จ่ายจริง' if y in actual else 'งบประมาณ'} {y}" for y in years]
    r.align = ["left"] * n + ["right"] * len(years)
    tot = [0.0] * len(years)
    for x in rows:
        vals = [float(x["values"].get(y, 0)) for y in years]
        r.rows.append(list(x["key"]) + vals)
        tot = [a + b for a, b in zip(tot, vals)]
    r.totals = ["รวม"] + [""] * (n - 1) + tot
    r.signers = ["officer", "head"]
    return r
