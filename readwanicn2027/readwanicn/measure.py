# SPDX-License-Identifier: GPL-3.0-or-later
"""Take-off on a PDF drawing: the scale of each page, lengths, areas and
counts measured on it, and the report as Excel or CSV. Coordinates are PDF
points (1/72 inch); the scale turns paper millimetres into metres."""
from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass, field
from pathlib import Path

PT_TO_MM = 25.4 / 72.0
#: Drawing scales offered (1:N).
STANDARD_SCALES = (1, 10, 20, 25, 50, 75, 100, 150, 200, 250, 300, 500, 1000, 1500, 2000, 2500, 5000)
KINDS = {"length": "ความยาว", "area": "พื้นที่", "count": "จำนวน"}
UNITS = {"length": "ม.", "area": "ตร.ม.", "count": "จุด"}


@dataclass
class Scale:
    """Metres of the real world per PDF point."""

    m_per_pt: float = PT_TO_MM / 1000.0 * 100.0      # 1:100
    label: str = "1:100"

    @classmethod
    def ratio(cls, n: float) -> "Scale":
        return cls(PT_TO_MM / 1000.0 * float(n), f"1:{n:g}")

    @classmethod
    def calibrated(cls, pt_distance: float, metres: float) -> "Scale":
        """From two points clicked a known distance apart on the drawing."""
        if pt_distance <= 0 or metres <= 0:
            raise ValueError("ระยะต้องมากกว่าศูนย์")
        m = metres / pt_distance
        n = m * 1000.0 / PT_TO_MM
        return cls(m, f"ตั้งเอง ≈ 1:{n:,.0f}")


@dataclass
class Measurement:
    kind: str                       # length | area | count
    page: int                       # 0-based
    points: list                    # [(x, y)] in PDF points
    scale: Scale = field(default_factory=Scale)
    name: str = ""
    file: str = ""

    @property
    def value(self) -> float:
        pts = self.points
        if self.kind == "count":
            return float(len(pts))
        if self.kind == "length":
            run = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
            return run * self.scale.m_per_pt
        if len(pts) < 3:
            return 0.0
        twice = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))
        return abs(twice) / 2.0 * self.scale.m_per_pt ** 2

    @property
    def perimeter(self) -> float:
        if self.kind != "area" or len(self.points) < 2:
            return 0.0
        pts = self.points + self.points[:1]
        return sum(math.dist(a, b) for a, b in zip(pts, pts[1:])) * self.scale.m_per_pt

    @property
    def unit(self) -> str:
        return UNITS[self.kind]

    def text(self) -> str:
        if self.kind == "count":
            return f"{int(self.value):,} {self.unit}"
        return f"{self.value:,.3f} {self.unit}"


def totals(items: list) -> dict:
    out = {k: 0.0 for k in KINDS}
    for m in items:
        out[m.kind] += m.value
    return out


def _rows(items: list) -> list:
    rows = []
    for i, m in enumerate(items, 1):
        rows.append([i, m.file, m.page + 1, KINDS[m.kind], m.name or f"{KINDS[m.kind]} {i}",
                     round(m.value, 4), m.unit, round(m.perimeter, 4) if m.kind == "area" else "",
                     m.scale.label, len(m.points)])
    return rows


HEADERS = ["ลำดับ", "ไฟล์", "หน้า", "ประเภท", "รายการ", "ปริมาณ", "หน่วย", "เส้นรอบรูป (ม.)",
           "สเกล", "จำนวนจุด"]


def report_excel(items: list, out_path, title: str = "รายงานงานวัด", by: str = "") -> None:
    """Two sheets: every measurement, and the totals by kind and by name."""
    from openpyxl import Workbook
    from openpyxl.styles import Border, Font, PatternFill, Side

    wb = Workbook()
    ws = wb.active
    ws.title = "รายการวัด"
    ws.append([title])
    ws["A1"].font = Font(bold=True, size=14)
    if by:
        ws.append([by])
    ws.append([])
    ws.append(HEADERS)
    head_row = ws.max_row
    fill = PatternFill("solid", fgColor="0F2A44")
    thin = Side(style="thin", color="999999")
    for c in ws[head_row]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = fill
    for row in _rows(items):
        ws.append(row)
        for c in ws[ws.max_row]:
            c.border = Border(top=thin, bottom=thin, left=thin, right=thin)
    first = head_row + 1
    last = ws.max_row
    ws.append([])
    for kind, label in KINDS.items():
        # a live formula, so an edited quantity updates the total
        ws.append(["", "", "", f"รวม{label}", "",
                   f'=SUMIF(D{first}:D{last},"{label}",F{first}:F{last})' if last >= first else 0,
                   UNITS[kind]])
        ws[ws.max_row][3].font = Font(bold=True)
    for col, width in zip("ABCDEFGHIJ", (7, 28, 7, 10, 28, 14, 8, 16, 18, 10)):
        ws.column_dimensions[col].width = width
    s = wb.create_sheet("สรุป")
    s.append(["สรุปตามรายการ"])
    s["A1"].font = Font(bold=True, size=13)
    s.append(["รายการ", "ประเภท", "ปริมาณรวม", "หน่วย"])
    for c in s[2]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = fill
    groups: dict = {}
    for m in items:
        key = (m.name or KINDS[m.kind], m.kind)
        groups[key] = groups.get(key, 0.0) + m.value
    for (name, kind), value in sorted(groups.items()):
        s.append([name, KINDS[kind], round(value, 4), UNITS[kind]])
    s.column_dimensions["A"].width = 32
    s.column_dimensions["C"].width = 16
    wb.save(out_path)


def report_csv(items: list, out_path) -> None:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(HEADERS)
    for row in _rows(items):
        w.writerow(row)
    Path(out_path).write_text(buf.getvalue(), encoding="utf-8-sig")
