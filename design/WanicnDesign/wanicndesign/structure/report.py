# -*- coding: utf-8 -*-
"""Calculation report (Excel): summary, roof, slabs, beams, columns, footings."""
from __future__ import annotations

from .design import DesignResult

NOTE = ("ผลคำนวณเบื้องต้นด้วยวิธีหน่วยแรงใช้งาน (WSD) ต้องให้วิศวกรโยธาผู้มีใบอนุญาต"
        "ตรวจสอบและลงนามก่อนนำไปใช้")


def _sheet(wb, title, headers, rows, widths):
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    ws = wb.create_sheet(title)
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="DDEBF7")
    red = PatternFill("solid", fgColor="F8CBAD")
    for r in rows:
        ws.append(list(r))
        if r and r[-2] == "NG":
            for c in ws[ws.max_row]:
                c.fill = red
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    return ws


def ok(x) -> str:
    return "OK" if x else "NG"


def write_report(res: DesignResult, path: str) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    b, mat = res.building, res.concrete
    wb = Workbook()
    ws = wb.active
    ws.title = "สรุป"
    ws.append([f"รายการคำนวณโครงสร้าง — {b.name}"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([NOTE])
    ws.append([])
    rows = [
        ("กำลังอัดคอนกรีต fc' (ทรงกระบอก)", f"{mat.fc_prime:g} ksc"),
        ("fc = 0.45 fc'", f"{mat.fc:.1f} ksc"),
        ("n = Es/Ec", mat.n),
        ("เหล็กข้ออ้อย", f"{mat.main_grade} fs = {mat.fs('DB'):g} ksc"),
        ("เหล็กเส้นกลม", f"{mat.tie_grade} fs = {mat.fs('RB'):g} ksc"),
        ("ขนาดอาคาร (แนวกริด)", f"{b.xs[-1]:.2f} x {b.ys[-1]:.2f} ม."),
        ("จำนวนชั้น", len(b.levels)),
        ("ฐานราก", f"{b.foundation.kind} {b.foundation.pile} ยาว {b.foundation.pile_length:g} ม."),
        ("จำนวนเสาเข็มรวม", res.total_piles()),
        ("ผลรวม", "ผ่านทุกรายการ" if res.ok else "มีรายการไม่ผ่าน ดูแถวสีแดง"),
    ]
    for r in rows:
        ws.append(list(r))
    for w in res.warnings:
        ws.append(["⚠", w])
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 60

    if res.roof:
        r = res.roof
        _sheet(wb, "หลังคา", ["รายการ", "ค่า", "หน่วย", "ผล", "หมายเหตุ"], [
            ("น้ำหนักลงคานหลังคา (ต่อพื้นที่ราบ)", round(r.load_plan, 1), "กก./ตร.ม.", "", ""),
            ("พื้นที่หลังคา (ราบ)", round(r.plan_area, 2), "ตร.ม.", "", ""),
            ("พื้นที่หลังคา (ตามลาด)", round(r.slope_area, 2), "ตร.ม.", "", ""),
            ("สันหลังคา", round(r.ridge, 2), "ม.", "", ""),
            ("ตะเข้สัน (รวม)", round(r.hips, 2), "ม.", "", ""),
            ("เชิงชาย", round(r.eave, 2), "ม.", "", ""),
            (f"แป {r.purlin.section} ช่วง {r.purlin.span:.2f} ม.",
             f"Mx {r.purlin.mx:.1f} My {r.purlin.my:.1f}", "กก.-ม.",
             f"Sx {r.purlin.sx_req:.2f}≤{r.purlin.zx} Sy {r.purlin.sy_req:.2f}≤{r.purlin.zy}",
             ok(r.purlin.ok), r.purlin.source),
            (f"จันทัน {r.rafter.section} ช่วง {r.rafter.span:.2f} ม.", f"Mx {r.rafter.mx:.1f}",
             "กก.-ม.", f"Sx {r.rafter.sx_req:.2f}≤{r.rafter.zx}", ok(r.rafter.ok), r.rafter.source),
            ("น้ำหนักเหล็กโครงหลังคาโดยประมาณ", round(r.steel_kg, 0), "กก.", "", ""),
        ], [42, 22, 10, 30, 6, 30])

    _sheet(wb, "พื้น", ["ชั้น", "แผ่น", "Mark", "ชนิด", "Lx", "Ly", "m", "W กก./ตร.ม.",
                        "M+ กก.-ม./ม.", "M- กก.-ม./ม.", "หนา ม.", "d ต้องการ ซม.", "เหล็กล่างช่วงสั้น",
                        "เหล็กล่างช่วงยาว", "เหล็กบน", "ผล", "หมายเหตุ"],
           [(s.level, s.panel, s.mark, s.kind, s.lx, s.ly, round(s.m, 2), round(s.load),
             round(s.m_pos, 1), round(s.m_neg, 1), s.thickness, round(s.d_req, 1), s.bars_short,
             s.bars_long, s.bars_top, ok(s.ok), s.note) for s in res.slabs],
           [7, 12, 6, 10, 6, 6, 6, 10, 10, 10, 7, 10, 14, 14, 12, 5, 30])
    _sheet(wb, "คาน", ["ชั้น", "แนว", "ช่วง", "Mark", "b ม.", "h ม.", "ยาว ม.", "w กก./ม.",
                       "M- กก.-ม.", "M+ กก.-ม.", "V กก.", "d ต้องการ ซม.", "As บน ซม.²", "As ล่าง ซม.²",
                       "เหล็กบน", "เหล็กล่าง", "ปลอก", "ผล", "หมายเหตุ"],
           [(x.level, x.line, x.span, x.mark, x.b, x.h, x.length, round(x.w), round(x.m_neg),
             round(x.m_pos), round(x.v), round(x.d_req, 1), round(x.as_top, 2), round(x.as_bot, 2),
             x.top, x.bottom, x.stirrup, ok(x.ok), x.note) for x in res.beams],
           [7, 5, 10, 6, 6, 6, 7, 9, 9, 9, 9, 9, 9, 9, 10, 10, 12, 5, 34])
    _sheet(wb, "เสา", ["ตำแหน่ง", "ช่วงเสา", "Mark", "สูง ม.", "P กก.", "b ม.", "h ม.", "pg",
                       "เหล็กยืน", "ปลอก", "ผล", "หมายเหตุ"],
           [(c.node, c.segment, c.mark, round(c.height, 2), round(c.load), c.b, c.h, round(c.pg, 4),
             c.bars, c.ties, ok(c.ok), c.note) for c in res.columns],
           [9, 16, 6, 7, 10, 6, 6, 8, 10, 12, 5, 30])
    _sheet(wb, "ฐานราก", ["ตำแหน่ง", "Mark", "ชนิด", "P กก.", "เสาเข็ม", "จำนวน", "รับ/ต้น กก.",
                          "กว้าง ม.", "ยาว ม.", "หนา ม.", "เหล็ก X", "เหล็ก Y", "ผล", "หมายเหตุ"],
           [(f.node, f.mark, f.kind, round(f.load), f.pile, f.piles, f.pile_capacity, f.width,
             f.length, f.thickness, f.bars_x, f.bars_y, ok(f.ok), f.note) for f in res.footings],
           [9, 6, 7, 10, 8, 7, 10, 7, 7, 7, 10, 10, 5, 36])
    wb.save(path)
