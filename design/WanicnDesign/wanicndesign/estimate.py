# -*- coding: utf-8 -*-
"""Price estimate in the forms of the 2569 criteria (กรมบัญชีกลาง,
หลักเกณฑ์การคำนวณราคากลางงานก่อสร้าง พ.ศ. 2569) [CGD2569]:

* แบบ ปร.1 — รายการ ปริมาณงาน และราคา ค่างานต้นทุน: material and labour
  side by side, per section;
* แบบ ปร.1 (ก) — สรุปค่าก่อสร้าง: each section's cost × Factor F, with the
  conditions of the Factor F table;
* แบบ ปร.4 — สรุปราคากลางงานก่อสร้างอาคาร, the price in words.

Material prices per BOQ unit come from the 2569 unit-material recipes and
the province price book (:mod:`.materials`); labour from ว480 [W480].
Factor F is the user's: one value, or rows copied from the CGD table, read
between rows by straight-line proportion. Under the government method
Factor F already holds overhead, interest, profit and VAT; the private
method adds VAT on top.

The Excel export writes formulas for every amount, so a user can change a
unit price, a labour rate or Factor F in the sheet and the totals follow.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field

from .materials import RECIPES, material_rate, needed
from .quantities import SECTIONS, Line
from .rates import Rates


@dataclass
class Row:
    line: Line
    material_rate: float
    labour_rate: float          # per BOQ unit (already × labour_factor)
    missing: list = field(default_factory=list)    # materials with no price

    @property
    def material_amount(self) -> float:
        return round(self.line.qty * self.material_rate, 2)

    @property
    def labour_amount(self) -> float:
        return round(self.line.qty * self.labour_rate, 2)

    @property
    def total(self) -> float:
        return round(self.material_amount + self.labour_amount, 2)


def factor_f(cost: float, table, default: float = 1.0) -> float:
    """Factor F for a construction cost (บาท) from rows ``[[cost, F], …]`` of
    the CGD table: between two rows by straight-line proportion, below the
    first row the first F, above the last row the last F."""
    rows = sorted((float(c), float(f)) for c, f in (table or []) if float(c) >= 0 and float(f) > 0)
    if not rows:
        return float(default or 1.0)
    if cost <= rows[0][0]:
        return rows[0][1]
    for (c1, f1), (c2, f2) in zip(rows, rows[1:]):
        if cost <= c2:
            return f1 + (f2 - f1) * (cost - c1) / (c2 - c1) if c2 > c1 else f2
    return rows[-1][1]


def _load_official():
    import json
    import os

    from .rates import DATA_DIR
    with open(os.path.join(DATA_DIR, "factor_f_2569.json"), encoding="utf-8") as f:
        return json.load(f)


#: ตาราง Factor F งานก่อสร้างอาคาร, กรมบัญชีกลาง ว 481 (26 มิ.ย. 2569), interest 6 %, VAT 7 % [CGD-FACTORF].
OFFICIAL_FF = _load_official()


def loan_interest(mlr_average: float) -> int:
    """Loan interest for the price rules from the average MLR of the large banks (ประกาศกรมบัญชีกลาง
    26 มิ.ย. 2569, ข้อ 13): a whole number, a fraction of 0.50 or more rounds up, less rounds down
    (24 มิ.ย. 2569: 6.38 → 6)."""
    import math
    return int(math.floor(mlr_average + 0.5 + 1e-9))


def needs_new_table(mlr_average: float, current: float = 6.0) -> bool:
    """A new Factor F table is due when the average MLR has moved by 1 % or more from the announced rate."""
    return abs(mlr_average - current) >= 1.0 - 1e-9


def official_factor(cost: float, advance: float, retention: float, no_vat: bool = False) -> float | None:
    """Factor F of a construction cost (บาท) from the official building table for this advance payment and
    retention (หลักเกณฑ์งานอาคาร 2569 ข้อ 9.3 ข้อ 2: F = D − (D − E)(A − B)/(C − B)); ``no_vat`` gives the
    "รวมในรูป Factor" column (ข้อ 7). None when no official table has these conditions."""
    tab = next((t for t in OFFICIAL_FF["tables"]
                if abs(t["advance"] - advance) < 1e-9 and abs(t["retention"] - retention) < 1e-9), None)
    if tab is None:
        return None
    col = 2 if no_vat else 3
    a = cost / 1e6                                       # the table is in million baht
    rows = tab["rows"]
    if rows[-1][0] == ">" and a > rows[-1][1]:
        return rows[-1][col]
    pts = [(r[1], r[col]) for r in rows if r[0] != ">"]
    if a <= pts[0][0]:
        return pts[0][1]
    for (b, d), (c, e) in zip(pts, pts[1:]):
        if a <= c:
            return d - (d - e) * (a - b) / (c - b)
    return pts[-1][1]


class Estimate:
    def __init__(self, project_name: str, lines: list[Line], rates: Rates, costing=None,
                 province: str = "", area: float = 0.0):
        from .structure.building import Costing
        self.project_name = project_name
        self.rates = rates
        self.costing = costing or Costing()
        self.province = province
        self.area = area
        self.factor_cost: float | None = None     # cost that picks Factor F (a contract: all its buildings)
        self.project = None                        # the measured model (schedule: frame by floor)
        self.rows = []
        for ln in lines:
            own = rates.prices.get(ln.price_key)       # a price typed for the BOQ line itself wins
            mat, miss = (float(own), []) if own else material_rate(ln.materials, rates.prices, ln.price_key)
            lab = mat * ln.labour_pct if ln.labour_pct else rates.labour_rate(ln.labour_code) * ln.labour_factor
            self.rows.append(Row(ln, round(mat, 2), round(lab, 4), miss))

    def sections(self):
        names = [s for s in SECTIONS if any(r.line.section == s for r in self.rows)]
        names += sorted({r.line.section for r in self.rows} - set(names))
        for name in names:
            yield name, [r for r in self.rows if r.line.section == name]

    @property
    def material_total(self) -> float:
        return round(sum(r.material_amount for r in self.rows), 2)

    @property
    def labour_total(self) -> float:
        return round(sum(r.labour_amount for r in self.rows), 2)

    @property
    def total(self) -> float:
        """ค่างานต้นทุน."""
        return round(self.material_total + self.labour_total, 2)

    @property
    def factor(self) -> float:
        return self._factor()[0]

    @property
    def factor_note(self) -> str:
        return self._factor()[1]

    def _factor(self) -> tuple[float, str]:
        """Factor F and where it came from: the user's rows, the official CGD table, or the typed value.
        Funded partly by a loan with no VAT (``loan_share`` %), the two columns are averaged by share (ข้อ 8)."""
        c = self.costing
        a = self.factor_cost if self.factor_cost is not None else self.total
        if c.factor_table:
            return round(factor_f(a, c.factor_table, c.factor_f), 4), \
                "ตามตาราง Factor F ที่กรอก (เทียบอัตราส่วนระหว่างช่วง)"
        ok = (c.use_official and abs(c.interest - OFFICIAL_FF["interest"]) < 1e-9
              and abs(c.vat - OFFICIAL_FF["vat"]) < 1e-9)
        f_vat = official_factor(a, c.adv_pay, c.retention) if ok else None
        if f_vat is None:
            why = "" if not c.use_official else \
                (" (ไม่มีตารางทางการสำหรับเงื่อนไขนี้ — ตารางมีเงินล่วงหน้า 0/5/10/15 %, ประกันผลงาน 0/5/10 %, "
                 "ดอกเบี้ย 6 %, VAT 7 %)")
            return round(float(c.factor_f or 1.0), 4), "ตามค่าที่กรอก" + why
        share = min(max(c.loan_share, 0.0), 100.0) / 100
        f_loan = official_factor(a, c.adv_pay, c.retention, no_vat=True)
        f = f_loan * share + f_vat * (1 - share)
        note = (f"ตามตาราง Factor F งานก่อสร้างอาคาร กรมบัญชีกลาง ว 481 (26 มิ.ย. 2569) เงินล่วงหน้า {c.adv_pay:g} % "
                f"ประกันผลงาน {c.retention:g} % ดอกเบี้ย 6 % VAT 7 % — ค่างานต้นทุน{'ทั้งสัญญา' if self.factor_cost is not None else ''} "
                f"{a / 1e6:,.4f} ล้านบาท เทียบอัตราส่วนระหว่างช่วง (ข้อ 9.3)")
        if share:
            note += (f"; เงินกู้ไม่เสียภาษี {share * 100:g} % ใช้ช่อง รวมในรูป Factor {f_loan:.4f} "
                     f"และงบประมาณ {100 - share * 100:g} % ใช้ Factor F {f_vat:.4f} ตามสัดส่วน (ข้อ 8)")
        return round(f, 4), note

    @property
    def construction(self) -> float:
        """ค่าก่อสร้าง = ค่างานต้นทุน × Factor F."""
        return round(self.total * self.factor, 2)

    @property
    def vat_added(self) -> float:
        return round(self.construction * self.costing.vat / 100, 2) if self.costing.method == "private" else 0.0

    def extras(self, section: str) -> list[dict]:
        return [e for e in self.costing.extras if e.get("section") == section and float(e.get("qty") or 0) > 0]

    def extras_total(self, section: str) -> float:
        """Material + installation of ปร.2 ("equip") or ปร.3 ("special") lines, without VAT."""
        return round(sum(float(e["qty"]) * (float(e.get("mat") or 0) + float(e.get("lab") or 0))
                         for e in self.extras(section)), 2)

    def with_vat(self, amount: float) -> float:
        return round(amount * (1 + self.costing.vat / 100), 2)

    @property
    def grand(self) -> float:
        """ราคากลาง = ค่าก่อสร้าง (+ VAT งานเอกชน) + ครุภัณฑ์จัดซื้อ (รวม VAT) + ค่าใช้จ่ายพิเศษ (รวม VAT)."""
        return round(self.construction + self.vat_added + self.with_vat(self.extras_total("equip"))
                     + self.with_vat(self.extras_total("special")), 2)

    def missing_prices(self) -> list[str]:
        out = []
        for r in self.rows:
            out += r.missing
            if not r.line.materials and r.material_rate == 0 and not r.line.labour_code:
                out.append(r.line.item)
        return list(dict.fromkeys(out))

    def needed_materials(self) -> dict:
        """``{material: unit}`` of every material the estimate prices (for the province import)."""
        out = {}
        for r in self.rows:
            out.update(needed(r.line.materials) if r.line.materials else {r.line.price_key: r.line.unit})
        return out

    @property
    def price_ref(self) -> str:
        c = self.costing
        if not self.province:
            return "ราคาวัสดุ: ตามที่ผู้ใช้กรอก"
        return f"ราคาวัสดุ: สำนักงานพาณิชย์จังหวัด{self.province}" + (f" ประจำเดือน {c.price_month}" if c.price_month
                                                                       else "")

    # -- export -------------------------------------------------------------
    HEADERS = ["ลำดับ", "รายการ", "จำนวน", "หน่วย", "ค่าวัสดุ ราคาต่อหน่วย",
               "ค่าวัสดุ จำนวนเงิน", "ค่าแรงงาน ราคาต่อหน่วย", "ค่าแรงงาน จำนวนเงิน",
               "รวมค่าวัสดุและค่าแรงงาน", "รหัสค่าแรง ว480", "หมายเหตุ"]

    def to_csv(self, path: str) -> None:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow([f"แบบ ปร.1 รายการ ปริมาณงาน และราคา ค่างานต้นทุน — {self.project_name}"])
            w.writerow(self.HEADERS)
            n = 0
            for name, rows in self.sections():
                w.writerow(["", name])
                for r in rows:
                    n += 1
                    w.writerow([n, r.line.item, r.line.qty, r.line.unit, r.material_rate,
                                r.material_amount, r.labour_rate, r.labour_amount, r.total,
                                r.line.labour_code, r.line.note])
            w.writerow(["", "รวมค่างานต้นทุน", "", "", "", self.material_total, "",
                        self.labour_total, self.total])
            w.writerow(["", f"Factor F {self.factor:.4f}", "", "", "", "", "", "", self.construction])
            if self.vat_added:
                w.writerow(["", f"ภาษีมูลค่าเพิ่ม {self.costing.vat:g}%", "", "", "", "", "", "", self.vat_added])
            w.writerow(["", "ราคากลาง", "", "", "", "", "", "", self.grand])

    def _tools(self, name: str | None = None):
        """(bold, header, head_row, sign) for the forms of this estimate (``name`` overrides the project name)."""
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
        bold = Font(bold=True)
        head_fill = PatternFill("solid", fgColor="DDEBF7")
        thin = Side(style="thin", color="999999")
        box = Border(left=thin, right=thin, top=thin, bottom=thin)
        c = self.costing
        project = name or self.project_name

        def header(ws, form, title, ncols, group=""):
            last = get_column_letter(ncols)
            ws.append([""] * (ncols - 1) + [f"แบบ {form}"])
            ws.cell(ws.max_row, ncols).font = bold
            ws.append([title])
            ws.cell(ws.max_row, 1).font = Font(bold=True, size=14)
            ws.merge_cells(f"A{ws.max_row}:{last}{ws.max_row}")
            ws.cell(ws.max_row, 1).alignment = Alignment(horizontal="center")
            dots = "........................................"
            texts = ([f"งานหรือกลุ่มงาน  {group}"] if group else []) + [
                f"ชื่อโครงการ  {project}", f"สถานที่ก่อสร้าง  {c.location or dots}",
                f"แบบเลขที่  {c.drawing_no or dots}", f"หน่วยงานเจ้าของโครงการ  {c.owner or dots}",
                self.price_ref, f"ค่าแรงงาน: {self.rates.source}"]
            for text in texts:
                ws.append([text])
                ws.merge_cells(f"A{ws.max_row}:{last}{ws.max_row}")

        def head_row(ws, labels):
            ws.append(labels)
            for cell in ws[ws.max_row]:
                cell.font = bold
                cell.fill = head_fill
                cell.border = box
                cell.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")

        def sign(ws, ncols):
            last = get_column_letter(ncols)
            ws.append([])
            people = [("ประธานกรรมการกำหนดราคากลาง", c.chair), ("กรรมการกำหนดราคากลาง", c.member1),
                      ("กรรมการกำหนดราคากลาง", c.member2),
                      ("ผู้ถอดแบบและคำนวณราคา", c.preparer + (f"  ตำแหน่ง {c.preparer_role}" if c.preparer_role
                                                             else ""))]
            for role, person in people:
                for text in (f"(ลงชื่อ) ......................................  {role}",
                             f"( {person or '..........................................'} )", ""):
                    ws.append([text])
                    ws.merge_cells(f"A{ws.max_row}:{last}{ws.max_row}")
                    ws.cell(ws.max_row, 1).alignment = Alignment(horizontal="center")
        return bold, header, head_row, sign

    def write_pr1(self, ws, tools, group: str = "") -> tuple[list, int]:
        """แบบ ปร.1 of this estimate on ``ws``; returns [(section, subtotal row)] and the total row."""
        from openpyxl.utils import get_column_letter
        bold, header, head_row, sign = tools
        header(ws, "ปร.1", "แบบแสดงรายการ ปริมาณงาน และราคา ค่างานต้นทุน", 11, group)
        head_row(ws, self.HEADERS)
        n = 0
        subtotal = []
        for name, rows in self.sections():
            ws.append(["", name])
            ws.cell(ws.max_row, 2).font = bold
            first = ws.max_row + 1
            for r in rows:
                n += 1
                note = r.line.note
                if r.missing:
                    note = (note + " · " if note else "") + "ยังไม่มีราคา: " + ", ".join(r.missing[:3]) + \
                        (" …" if len(r.missing) > 3 else "")
                ws.append([n, r.line.item, r.line.qty, r.line.unit, r.material_rate, None,
                           r.labour_rate, None, None, r.line.labour_code, note])
                i = ws.max_row
                ws.cell(i, 6, f"=ROUND(C{i}*E{i},2)")
                ws.cell(i, 8, f"=ROUND(C{i}*G{i},2)")
                ws.cell(i, 9, f"=F{i}+H{i}")
            last = ws.max_row
            ws.append(["", f"รวม{name}", None, None, None, f"=SUM(F{first}:F{last})", None,
                       f"=SUM(H{first}:H{last})", f"=SUM(I{first}:I{last})"])
            ws.cell(ws.max_row, 2).font = bold
            subtotal.append((name, ws.max_row))
        refs = lambda col: "+".join(f"{col}{i}" for _n, i in subtotal) or "0"
        ws.append(["", "รวมค่างานต้นทุน", None, None, None, "=" + refs("F"), None, "=" + refs("H"), "=" + refs("I")])
        total_row = ws.max_row
        for cell in ws[total_row]:
            cell.font = bold
        for i, wdt in enumerate([7, 48, 11, 8, 13, 14, 13, 14, 16, 12, 44], 1):
            ws.column_dimensions[get_column_letter(i)].width = wdt
        for row in ws.iter_rows(min_row=9):
            for cell in row[2:9]:
                cell.number_format = "#,##0.00"
        sign(ws, 11)
        return subtotal, total_row

    def to_xlsx(self, path: str) -> None:
        from openpyxl import Workbook
        from openpyxl.utils import get_column_letter

        wb = Workbook()
        c = self.costing
        tools = self._tools()
        bold, header, head_row, sign = tools

        # ---- ปร.4: summary ---------------------------------------------------
        s4 = wb.active
        s4.title = "ปร.4"
        s1k = wb.create_sheet("ปร.1 (ก)")
        s1 = wb.create_sheet("ปร.1")

        subtotal, _total_row = self.write_pr1(s1, tools)

        # ---- ปร.1 (ก): sections × Factor F ----------------------------------
        header(s1k, "ปร.1 (ก)", "แบบสรุปค่าก่อสร้าง ค่างานต้นทุน", 6)
        head_row(s1k, ["ลำดับที่", "รายการ", "ค่างานต้นทุน (บาท)", "Factor F", "ค่าก่อสร้าง (บาท)", "หมายเหตุ"])
        first = s1k.max_row + 1
        fcell = f"$D${first}"
        for k, (name, row) in enumerate(subtotal, 1):
            s1k.append([k, name, f"='ปร.1'!I{row}", self.factor if k == 1 else f"={fcell}", None, ""])
            i = s1k.max_row
            s1k.cell(i, 5, f"=ROUND(C{i}*D{i},2)")
        last = s1k.max_row
        s1k.append(["", "รวมค่าก่อสร้าง", f"=SUM(C{first}:C{last})", None, f"=SUM(E{first}:E{last})", ""])
        sum_row = s1k.max_row
        for cell in s1k[sum_row]:
            cell.font = bold
        how = self.factor_note
        s1k.append([])
        for text in (f"Factor F {self.factor:.4f} — {how}", "เงื่อนไขการใช้ตาราง Factor F",
                     f"   เงินล่วงหน้าจ่าย {c.adv_pay:g} %", f"   เงินประกันผลงานหัก {c.retention:g} %",
                     f"   ดอกเบี้ยเงินกู้ {c.interest:g} % ต่อปี", f"   ภาษีมูลค่าเพิ่ม {c.vat:g} %",
                     ("ขนาดหรือเนื้อที่อาคาร " + (f"{self.area:,.2f} ตร.ม. เฉลี่ย {self.grand / self.area:,.2f} บาท/ตร.ม."
                                                if self.area > 0 else "........ ตร.ม."))):
            s1k.append(["", text])
            s1k.merge_cells(f"B{s1k.max_row}:F{s1k.max_row}")
        for i, wdt in enumerate([8, 44, 18, 11, 18, 16], 1):
            s1k.column_dimensions[get_column_letter(i)].width = wdt
        for row in s1k.iter_rows(min_row=first, max_row=sum_row):
            for cell in (row[2], row[4]):
                cell.number_format = "#,##0.00"
            row[3].number_format = "0.0000"
        sign(s1k, 6)

        # ---- ปร.4 -------------------------------------------------------------
        header(s4, "ปร.4", "แบบสรุปราคากลางงานก่อสร้างอาคาร", 4)
        head_row(s4, ["ลำดับที่", "รายการ", "ค่าก่อสร้าง (บาท)", "หมายเหตุ"])
        s4.append(["1", "ค่างานต้นทุน × Factor F (ตามแบบ ปร.1 (ก))", f"='ปร.1 (ก)'!E{sum_row}",
                   f"Factor F {self.factor:.4f}"])
        rows4 = [s4.max_row]
        if c.method == "private":
            s4.append(["2", f"ภาษีมูลค่าเพิ่ม {c.vat:g}% (งานเอกชน)", f"=ROUND(C{rows4[0]}*{c.vat / 100},2)", ""])
            rows4.append(s4.max_row)
        for no, sec, label in (("2", "equip", "ค่าครุภัณฑ์จัดซื้อ (ตามแบบ ปร.2 (ก)) รวมภาษีมูลค่าเพิ่ม"),
                               ("3", "special", "ค่าใช้จ่ายพิเศษตามข้อกำหนด (ตามแบบ ปร.3) รวมภาษีมูลค่าเพิ่ม")):
            s4.append([no if c.method == "gov" else str(int(no) + 1), label, self.with_vat(self.extras_total(sec)),
                       "" if self.extras(sec) else "ไม่มี"])
            rows4.append(s4.max_row)
        s4.append(["", "ราคากลาง", "=" + "+".join(f"C{i}" for i in rows4), ""])
        s4.cell(s4.max_row, 2).font = bold
        s4.cell(s4.max_row, 3).font = bold
        for i in rows4 + [s4.max_row]:
            s4.cell(i, 3).number_format = "#,##0.00"
        s4.append(["", f"ราคากลาง (ตัวอักษร)  ({baht_text(self.grand)})"])
        s4.merge_cells(f"B{s4.max_row}:D{s4.max_row}")
        s4.append(["", "วิธีคิด: " + ("ราคากลางราชการ (Factor F รวมภาษีมูลค่าเพิ่มแล้ว)" if c.method == "gov"
                                    else "งานเอกชน (บวกภาษีมูลค่าเพิ่มทั้งหมด)")])
        s4.merge_cells(f"B{s4.max_row}:D{s4.max_row}")
        for i, wdt in enumerate([8, 60, 20, 22], 1):
            s4.column_dimensions[get_column_letter(i)].width = wdt
        sign(s4, 4)

        self._extras_sheets(wb, header, head_row, sign, bold)
        from .schedule import plan, write_plan
        write_plan(plan(self, c.wage, c.workweek, c.crews), wb.create_sheet("แผนงานก่อสร้าง"),
                   f"แผนงานก่อสร้าง (CPM) — {self.project_name}", self.construction + self.vat_added,
                   c.adv_pay, c.retention)

        # ---- material analysis ---------------------------------------------
        self._material_sheets(wb, bold, head_row)

        lab = wb.create_sheet("ค่าแรง ว480")
        lab.append(["รหัส", "รายการ", "หน่วย", "ค่าแรง (บาท)", "เงื่อนไข"])
        for cell in lab[1]:
            cell.font = bold
        for code, item in self.rates.labour.items():
            lab.append([code, item["name"], item["unit"], item["rate"], item.get("condition", "")])
        for col, wdt in zip("ABCDE", (10, 50, 8, 12, 50)):
            lab.column_dimensions[col].width = wdt
        from .structure.report import references_sheet
        references_sheet(wb, ["CGD2569", "CGD2569-MAT", "W480", "CGD-FACTORF"])
        wb.save(path)

    def _extras_sheets(self, wb, header, head_row, sign, bold) -> None:
        """แบบ ปร.2, ปร.2 (ก) and ปร.3 (หลักเกณฑ์งานอาคาร 2569: ครุภัณฑ์ราคาผู้ผลิต/ผู้จำหน่ายยังไม่รวม VAT แล้วบวก VAT)."""
        v = self.costing.vat / 100
        p2 = wb.create_sheet("ปร.2")
        header(p2, "ปร.2", "แบบแสดงรายการ ปริมาณงาน และราคา ค่าครุภัณฑ์จัดซื้อ", 10)
        head_row(p2, ["ลำดับที่", "รายการ", "จำนวน", "หน่วย", "ค่าครุภัณฑ์ ต่อหน่วย", "ค่าครุภัณฑ์ จำนวนเงิน",
                      "ค่าติดตั้ง ต่อหน่วย", "ค่าติดตั้ง จำนวนเงิน", "รวม", "หมายเหตุ"])
        eq = self.extras("equip")
        first = p2.max_row + 1
        for k, e in enumerate(eq, 1):
            p2.append([k, e.get("item", ""), float(e["qty"]), e.get("unit", ""), float(e.get("mat") or 0), None,
                       float(e.get("lab") or 0), None, None, e.get("note", "")])
            i = p2.max_row
            p2.cell(i, 6, f"=ROUND(C{i}*E{i},2)")
            p2.cell(i, 8, f"=ROUND(C{i}*G{i},2)")
            p2.cell(i, 9, f"=F{i}+H{i}")
        if not eq:
            p2.append(["", "(ไม่มีรายการ)"])
        last = p2.max_row
        p2.append(["", "รวม", None, None, None, f"=SUM(F{first}:F{last})", None, f"=SUM(H{first}:H{last})",
                   f"=SUM(I{first}:I{last})"])
        p2.cell(p2.max_row, 2).font = bold
        sign(p2, 10)
        p2k = wb.create_sheet("ปร.2 (ก)")
        header(p2k, "ปร.2 (ก)", "แบบสรุปค่าครุภัณฑ์จัดซื้อ", 8)
        head_row(p2k, ["ลำดับที่", "รายการ", "ค่าครุภัณฑ์", f"VAT {self.costing.vat:g}%", "รวมค่าครุภัณฑ์",
                       "ค่าติดตั้ง", f"VAT {self.costing.vat:g}%", "รวมค่าติดตั้ง"])
        tot = [0.0] * 6
        for k, e in enumerate(eq, 1):
            q = float(e["qty"])
            mm, ll = q * float(e.get("mat") or 0), q * float(e.get("lab") or 0)
            vals = [round(x, 2) for x in (mm, mm * v, mm * (1 + v), ll, ll * v, ll * (1 + v))]
            tot = [a + b for a, b in zip(tot, vals)]
            p2k.append([k, e.get("item", "")] + vals)
        p2k.append(["", "รวมค่าครุภัณฑ์จัดซื้อ"] + [round(x, 2) for x in tot])
        p2k.append(["", f"รวมทั้งสิ้น (รวมภาษีมูลค่าเพิ่ม)  {self.with_vat(self.extras_total('equip')):,.2f} บาท"])
        sign(p2k, 8)
        p3 = wb.create_sheet("ปร.3")
        header(p3, "ปร.3", "แบบแสดงรายการ ปริมาณงาน และราคา ค่าใช้จ่ายพิเศษตามข้อกำหนด", 5)
        head_row(p3, ["ลำดับที่", "รายการ", "จำนวนหน่วย", "ค่าใช้จ่ายรวม (รวม VAT)", "หมายเหตุ"])
        sp = self.extras("special")
        for k, e in enumerate(sp, 1):
            amt = float(e["qty"]) * (float(e.get("mat") or 0) + float(e.get("lab") or 0))
            p3.append([k, e.get("item", ""), f"{float(e['qty']):,.2f} {e.get('unit', '')}".strip(), self.with_vat(amt),
                       e.get("note", "")])
        if not sp:
            p3.append(["", "(ไม่มีรายการ)"])
        p3.append(["", "รวมค่าใช้จ่ายพิเศษตามข้อกำหนด", "", self.with_vat(self.extras_total("special")), ""])
        p3.append(["", "แนบแบบแสดงการคำนวณและเหตุผลความจำเป็นของแต่ละรายการ"])
        sign(p3, 5)
        for ws, widths in ((p2, [8, 44, 10, 8, 14, 15, 13, 15, 16, 24]), (p2k, [8, 40, 15, 13, 15, 13, 13, 15]),
                           (p3, [8, 50, 16, 20, 30])):
            from openpyxl.utils import get_column_letter
            for i, wdt in enumerate(widths, 1):
                ws.column_dimensions[get_column_letter(i)].width = wdt

    def _material_sheets(self, wb, bold, head_row) -> None:
        from .materials import ALIASES, FORMWORK, _price
        prices = self.rates.prices
        mats = wb.create_sheet("ราคาวัสดุ")
        mats.append([self.price_ref])
        head_row(mats, ["วัสดุ", "หน่วย", "ราคาต่อหน่วย (บาท)", "สถานะ"])
        for name, unit in sorted(self.needed_materials().items()):
            p = _price(name, prices)
            mats.append([name, unit, p if p is not None else None, "มีราคา" if p is not None else "ยังไม่มีราคา"])
        for col, wdt in zip("ABCD", (60, 10, 18, 14)):
            mats.column_dimensions[col].width = wdt

        an = wb.create_sheet("วิเคราะห์ค่าวัสดุ")
        an.append(["ค่าวัสดุต่อหน่วยของแต่ละรายการ จากสูตรวัสดุมวลรวม กรมบัญชีกลาง 2569 (รวมเผื่อแล้ว) × ราคาวัสดุ"])
        head_row(an, ["รายการ / วัสดุ", "ปริมาณต่อหน่วยงาน", "หน่วย", "ราคาต่อหน่วย", "จำนวนเงิน", "ที่มา"])
        for r in self.rows:
            if not r.line.materials or all(not ref for ref, _q in r.line.materials):
                continue
            an.append([f"{r.line.item}  (ต่อ 1 {r.line.unit})", None, None, None, r.material_rate, ""])
            an.cell(an.max_row, 1).font = bold
            for ref, q in r.line.materials:
                if not ref:
                    continue
                if ref == "FORM":
                    items = [(n, qq, u, "หลักเกณฑ์ 4.1 ข้อ 3.1.1") for n, qq, u in FORMWORK]
                elif ref.startswith("R:"):
                    rc = RECIPES.get(ref[2:], {"items": [], "page": ""})
                    src = f"สูตร {ref[2:]} หน้า {rc.get('page', '')}"
                    items = [(it["name"], it.get("qty"), it["unit"], src) for it in rc["items"]]
                else:
                    items = [(ref, 1.0, "", "ราคาวัสดุโดยตรง")]
                for name, qq, unit, src in items:
                    if qq is None:
                        an.append([f"   {name}", None, unit, None, None, src + " (ตามคู่มือผู้ผลิต)"])
                        continue
                    if name.startswith("ไม้แบบ") and unit == "ตร.ม.":
                        from .materials import formwork_cost
                        p = formwork_cost(prices)[0]
                    else:
                        p = None
                        for it in RECIPES.get(ref[2:], {"items": []})["items"] if ref.startswith("R:") else []:
                            if it["name"] == name and "price" in it:
                                p = float(it["price"])
                        if p is None:
                            p = _price(ALIASES.get(name, name), prices) or _price(name, prices)
                    amount = round(q * qq * p, 2) if p is not None else None
                    an.append([f"   {name}", q * qq, unit, p, amount, src])
        for col, wdt in zip("ABCDEF", (70, 16, 10, 14, 14, 24)):
            an.column_dimensions[col].width = wdt


# ---------------------------------------------------------------------------
# Thai baht in words (same reading as the WANICNSURVEY 3D price forms)
# ---------------------------------------------------------------------------

_DIGITS = ["", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]
_PLACES = ["", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน"]


def _read_under_million(n: int, tail: bool = False) -> str:
    s = str(n)
    out = []
    for i, ch in enumerate(s):
        d = int(ch)
        place = len(s) - i - 1
        if d == 0:
            continue
        if place == 1 and d == 1:
            out.append("สิบ")
        elif place == 1 and d == 2:
            out.append("ยี่สิบ")
        elif place == 0 and d == 1 and (len(s) > 1 or tail):
            out.append("เอ็ด")
        else:
            out.append(_DIGITS[d] + _PLACES[place])
    return "".join(out)


def _read_int(n: int) -> str:
    if n == 0:
        return "ศูนย์"
    parts = []
    while n > 0:
        parts.append(n % 1_000_000)
        n //= 1_000_000
    words = ""
    for i in range(len(parts) - 1, -1, -1):
        if parts[i]:
            words += _read_under_million(parts[i], tail=i < len(parts) - 1)
        if i > 0:
            words += "ล้าน"
    return words


def baht_text(amount: float) -> str:
    """``1234.5`` → ``หนึ่งพันสองร้อยสามสิบสี่บาทห้าสิบสตางค์``."""
    amount = round(abs(float(amount)) + 1e-9, 2)
    baht = int(amount)
    satang = int(round((amount - baht) * 100))
    if satang == 100:
        baht, satang = baht + 1, 0
    return _read_int(baht) + "บาท" + ("ถ้วน" if satang == 0 else _read_int(satang) + "สตางค์")


def estimate(project, rates: Rates, costing=None, province: str = "", area: float = 0.0):
    from .quantities import takeoff
    est = Estimate(project.name, takeoff(project, rates), rates, costing, province, area)
    est.project = project
    return est


def floor_area(b) -> float:
    """Floor area of the building (ขนาดหรือเนื้อที่อาคาร): every floor and roof deck, by slab panel, m²."""
    total = 0.0
    for lv in b.levels:
        if lv.slab in ("roof", "none"):
            continue
        for i, j in b.panels(lv.name):
            total += (b.xs[i + 1] - b.xs[i]) * (b.ys[j + 1] - b.ys[j])
    return round(total, 2)


def province_prices(province: str) -> tuple[dict, str]:
    """The saved price book of the province (shared with the WANICNSURVEY 3D
    program) and its month; empty when there is none."""
    from . import province as P
    book = P.load_book(province) if province else None
    if not book:
        return {}, ""
    return dict(book["prices"]), book.get("month", "")


def for_design(res, rates: Rates | None = None) -> Estimate:
    """The priced estimate of a designed building: province prices, its costing settings and floor area."""
    import copy
    import os

    from .quantities import takeoff
    from .rates import DATA_DIR
    from .structure.to_project import to_project
    b = res.building
    project = to_project(res)
    rates = rates or Rates(override_file=os.path.join(DATA_DIR, "labour_override.json"))
    book, month = province_prices(b.province)
    rates.prices = {**book, **rates.prices}          # typed prices win over the book
    costing = copy.deepcopy(b.costing)
    if not costing.price_month:
        costing.price_month = month
    est = Estimate(project.name, takeoff(project, rates), rates, costing, b.province if book else "",
                   floor_area(b))
    est.project = project                        # for the plan: the frame by floor
    return est


class Contract:
    """Several buildings priced in one contract (หลักเกณฑ์งานอาคาร 2569 ข้อ 9.3 ข้อ 3): Factor F from the
    cost of the whole contract; one แบบ ปร.1 per building (งานหรือกลุ่มงาน, หน้า 5), ปร.1 (ก) listing every
    building × that Factor F, one ปร.2/ปร.3 and the ปร.4 of the project. The first building's costing gives
    the project details, committee and Factor F conditions."""

    def __init__(self, name: str, estimates: list[tuple[str, Estimate]]):
        if not estimates:
            raise ValueError("ไม่มีอาคารในสัญญา")
        self.name = name
        self.items = estimates
        self.lead = estimates[0][1]
        total = self.total
        for _label, est in estimates:
            est.factor_cost = total
            est.costing.factor_table = self.lead.costing.factor_table
            for k in ("use_official", "loan_share", "factor_f", "adv_pay", "retention", "interest", "vat", "method"):
                setattr(est.costing, k, getattr(self.lead.costing, k))

    @property
    def total(self) -> float:
        return round(sum(e.total for _l, e in self.items), 2)

    @property
    def factor(self) -> float:
        return self.lead.factor

    @property
    def construction(self) -> float:
        return round(sum(e.construction for _l, e in self.items), 2)

    def extras(self, section: str) -> list[dict]:
        return [dict(x, item=f"{x.get('item', '')} ({label})") for label, e in self.items for x in e.extras(section)]

    def extras_total(self, section: str) -> float:
        return round(sum(e.extras_total(section) for _l, e in self.items), 2)

    @property
    def grand(self) -> float:
        c = self.lead.costing
        vat = self.construction * c.vat / 100 if c.method == "private" else 0.0
        return round(self.construction + vat + self.lead.with_vat(self.extras_total("equip"))
                     + self.lead.with_vat(self.extras_total("special")), 2)

    @property
    def area(self) -> float:
        return round(sum(e.area for _l, e in self.items), 2)

    def to_xlsx(self, path: str) -> None:
        from openpyxl import Workbook
        from openpyxl.utils import get_column_letter
        wb = Workbook()
        lead, c = self.lead, self.lead.costing
        tools = lead._tools(self.name)
        bold, header, head_row, sign = tools
        s4 = wb.active
        s4.title = "ปร.4"
        s1k = wb.create_sheet("ปร.1 (ก)")
        totals = []
        for k, (label, est) in enumerate(self.items, 1):
            ws = wb.create_sheet(f"ปร.1 ({k})")
            _sub, row = est.write_pr1(ws, est._tools(self.name), group=label)
            totals.append((label, ws.title, row))
        header(s1k, "ปร.1 (ก)", "แบบสรุปค่าก่อสร้าง ค่างานต้นทุน", 6)
        head_row(s1k, ["ลำดับที่", "รายการ (งานหรือกลุ่มงาน)", "ค่างานต้นทุน (บาท)", "Factor F", "ค่าก่อสร้าง (บาท)",
                       "หมายเหตุ"])
        first = s1k.max_row + 1
        for k, (label, title, row) in enumerate(totals, 1):
            s1k.append([k, label, f"='{title}'!I{row}", self.factor if k == 1 else f"=$D${first}", None,
                        f"แบบ {title}"])
            i = s1k.max_row
            s1k.cell(i, 5, f"=ROUND(C{i}*D{i},2)")
        last = s1k.max_row
        s1k.append(["", "รวมค่าก่อสร้าง", f"=SUM(C{first}:C{last})", None, f"=SUM(E{first}:E{last})", ""])
        sum_row = s1k.max_row
        for cell in s1k[sum_row]:
            cell.font = bold
        s1k.append([])
        for text in (f"Factor F {self.factor:.4f} — {lead.factor_note}",
                     "สัญญาเดียว: ใช้ค่างานต้นทุนรวมทุกอาคารหาค่า Factor F (หลักเกณฑ์งานอาคาร 2569 ข้อ 9.3 ข้อ 3)",
                     "เงื่อนไขการใช้ตาราง Factor F", f"   เงินล่วงหน้าจ่าย {c.adv_pay:g} %",
                     f"   เงินประกันผลงานหัก {c.retention:g} %", f"   ดอกเบี้ยเงินกู้ {c.interest:g} % ต่อปี",
                     f"   ภาษีมูลค่าเพิ่ม {c.vat:g} %",
                     ("ขนาดหรือเนื้อที่อาคารรวม " + (f"{self.area:,.2f} ตร.ม. เฉลี่ย {self.grand / self.area:,.2f} บาท/ตร.ม."
                                                    if self.area > 0 else "........ ตร.ม."))):
            s1k.append(["", text])
            s1k.merge_cells(f"B{s1k.max_row}:F{s1k.max_row}")
        for i, wdt in enumerate([8, 44, 18, 11, 18, 16], 1):
            s1k.column_dimensions[get_column_letter(i)].width = wdt
        for row in s1k.iter_rows(min_row=first, max_row=sum_row):
            for cell in (row[2], row[4]):
                cell.number_format = "#,##0.00"
            row[3].number_format = "0.0000"
        sign(s1k, 6)
        header(s4, "ปร.4", "แบบสรุปราคากลางงานก่อสร้างอาคาร", 4)
        head_row(s4, ["ลำดับที่", "รายการ", "ค่าก่อสร้าง (บาท)", "หมายเหตุ"])
        s4.append(["1", f"ค่างานต้นทุน × Factor F (ตามแบบ ปร.1 (ก)) {len(self.items)} อาคาร",
                   f"='ปร.1 (ก)'!E{sum_row}", f"Factor F {self.factor:.4f}"])
        rows4 = [s4.max_row]
        if c.method == "private":
            s4.append(["", f"ภาษีมูลค่าเพิ่ม {c.vat:g}% (งานเอกชน)", f"=ROUND(C{rows4[0]}*{c.vat / 100},2)", ""])
            rows4.append(s4.max_row)
        for no, sec, label in (("2", "equip", "ค่าครุภัณฑ์จัดซื้อ (ตามแบบ ปร.2 (ก)) รวมภาษีมูลค่าเพิ่ม"),
                               ("3", "special", "ค่าใช้จ่ายพิเศษตามข้อกำหนด (ตามแบบ ปร.3) รวมภาษีมูลค่าเพิ่ม")):
            s4.append([no, label, lead.with_vat(self.extras_total(sec)), "" if self.extras(sec) else "ไม่มี"])
            rows4.append(s4.max_row)
        s4.append(["", "ราคากลาง", "=" + "+".join(f"C{i}" for i in rows4), ""])
        for i in rows4 + [s4.max_row]:
            s4.cell(i, 3).number_format = "#,##0.00"
        s4.cell(s4.max_row, 2).font = bold
        s4.append(["", f"ราคากลาง (ตัวอักษร)  ({baht_text(self.grand)})"])
        s4.merge_cells(f"B{s4.max_row}:D{s4.max_row}")
        for i, wdt in enumerate([8, 60, 20, 22], 1):
            s4.column_dimensions[get_column_letter(i)].width = wdt
        sign(s4, 4)
        # ปร.2/ปร.3 of all buildings, through the lead estimate with the combined lines
        saved = lead.costing.extras
        lead.costing.extras = [dict(x, section=sec) for sec in ("equip", "special") for x in self.extras(sec)]
        try:
            lead._extras_sheets(wb, header, head_row, sign, bold)
        finally:
            lead.costing.extras = saved
        from .structure.report import references_sheet
        from .schedule import plan, write_plan
        for k, (label, est) in enumerate(self.items, 1):
            write_plan(plan(est, c.wage, c.workweek, c.crews), wb.create_sheet(f"แผนงาน ({k})"),
                       f"แผนงานก่อสร้าง (CPM) — {label}", est.construction + est.vat_added, c.adv_pay, c.retention)
        references_sheet(wb, ["CGD2569", "CGD2569-MAT", "W480", "W480-MEP", "CGD-FACTORF"])
        wb.save(path)


def contract_for_designs(name: str, results, rates: Rates | None = None) -> Contract:
    """A contract from designed buildings (each priced with its own province book and quantities)."""
    return Contract(name, [(r.building.name, for_design(r, rates)) for r in results])
