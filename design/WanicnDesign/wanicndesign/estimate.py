# -*- coding: utf-8 -*-
"""Bill of quantities priced in the ปร.4 layout: material and labour
side by side, per section, with totals.

The Excel export writes formulas for every amount, so a user can change a
unit price or a labour rate in the sheet and the totals follow — the same
way QuickDesign's Est.xls is used.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass

from .quantities import SECTIONS, Line
from .rates import Rates


@dataclass
class Row:
    line: Line
    material_rate: float
    labour_rate: float          # per BOQ unit (already × labour_factor)

    @property
    def material_amount(self) -> float:
        return round(self.line.qty * self.material_rate, 2)

    @property
    def labour_amount(self) -> float:
        return round(self.line.qty * self.labour_rate, 2)

    @property
    def total(self) -> float:
        return round(self.material_amount + self.labour_amount, 2)


class Estimate:
    def __init__(self, project_name: str, lines: list[Line], rates: Rates):
        self.project_name = project_name
        self.rates = rates
        self.rows = [Row(ln, rates.price(ln.price_key),
                         round(rates.labour_rate(ln.labour_code) * ln.labour_factor, 4))
                     for ln in lines]

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
        return round(self.material_total + self.labour_total, 2)

    def missing_prices(self) -> list[str]:
        return [r.line.item for r in self.rows if r.material_rate == 0 and not r.line.labour_code]

    # -- export -------------------------------------------------------------
    HEADERS = ["ลำดับ", "รายการ", "จำนวน", "หน่วย", "ค่าวัสดุ ราคาต่อหน่วย",
               "ค่าวัสดุ จำนวนเงิน", "ค่าแรงงาน ราคาต่อหน่วย", "ค่าแรงงาน จำนวนเงิน",
               "รวมค่าวัสดุและค่าแรงงาน", "รหัสค่าแรง ว480", "หมายเหตุ"]

    def to_csv(self, path: str) -> None:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow([f"ใบประมาณราคา (ปร.4) — {self.project_name}"])
            w.writerow(self.HEADERS)
            n = 0
            for name, rows in self.sections():
                w.writerow(["", name])
                for r in rows:
                    n += 1
                    w.writerow([n, r.line.item, r.line.qty, r.line.unit, r.material_rate,
                                r.material_amount, r.labour_rate, r.labour_amount, r.total,
                                r.line.labour_code, r.line.note])
            w.writerow(["", "รวมทั้งสิ้น", "", "", "", self.material_total, "",
                        self.labour_total, self.total])

    def to_xlsx(self, path: str) -> None:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter

        wb = Workbook()
        ws = wb.active
        ws.title = "ปร.4"
        bold = Font(bold=True)
        ws.append([f"ใบประมาณราคา (ปร.4) — {self.project_name}"])
        ws["A1"].font = Font(bold=True, size=14)
        ws.append([f"ค่าแรงตาม {self.rates.source}"])
        ws.append(self.HEADERS)
        for c in ws[3]:
            c.font = bold
            c.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
            c.fill = PatternFill("solid", fgColor="DDEBF7")
        n = 0
        subtotal_cells = []
        for name, rows in self.sections():
            ws.append(["", name])
            ws.cell(ws.max_row, 2).font = bold
            first = ws.max_row + 1
            for r in rows:
                n += 1
                ws.append([n, r.line.item, r.line.qty, r.line.unit, r.material_rate, None,
                           r.labour_rate, None, None, r.line.labour_code, r.line.note])
                i = ws.max_row
                ws.cell(i, 6, f"=ROUND(C{i}*E{i},2)")
                ws.cell(i, 8, f"=ROUND(C{i}*G{i},2)")
                ws.cell(i, 9, f"=F{i}+H{i}")
            last = ws.max_row
            ws.append(["", f"รวม{name}", None, None, None, f"=SUM(F{first}:F{last})", None,
                       f"=SUM(H{first}:H{last})", f"=SUM(I{first}:I{last})"])
            ws.cell(ws.max_row, 2).font = bold
            subtotal_cells.append(ws.max_row)
        refs = lambda col: "+".join(f"{col}{i}" for i in subtotal_cells) or "0"
        ws.append(["", "รวมค่าวัสดุและค่าแรงงานทั้งสิ้น", None, None, None, "=" + refs("F"),
                   None, "=" + refs("H"), "=" + refs("I")])
        for c in ws[ws.max_row]:
            c.font = bold
        widths = [7, 48, 11, 8, 13, 14, 13, 14, 16, 12, 40]
        for i, wdt in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = wdt
        for row in ws.iter_rows(min_row=4):
            for c in row[2:9]:
                c.number_format = "#,##0.00"

        lab = wb.create_sheet("ค่าแรง ว480")
        lab.append(["รหัส", "รายการ", "หน่วย", "ค่าแรง (บาท)", "เงื่อนไข"])
        for c in lab[1]:
            c.font = bold
        for code, item in self.rates.labour.items():
            lab.append([code, item["name"], item["unit"], item["rate"], item.get("condition", "")])
        for col, wdt in zip("ABCDE", (10, 50, 8, 12, 50)):
            lab.column_dimensions[col].width = wdt
        wb.save(path)


def estimate(project, rates: Rates):
    from .quantities import takeoff
    return Estimate(project.name, takeoff(project, rates), rates)
