# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ — ReadWanicn2027
"""Reports ว651 · ว124 · ว78 as PDF (A4, Thai font) and as a spreadsheet (.xlsx).

A report is a list of blocks (paragraphs, tables, a chart, page breaks) that is
written twice: as HTML for QTextDocument → QPdfWriter, and as worksheet cells."""
from __future__ import annotations

import html
from dataclasses import dataclass, field
from pathlib import Path

from . import procure as P

DEVELOPER_LINE = "จัดทำด้วยโปรแกรม ReadWanicn2027 · ผู้พัฒนา นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ"
SHADE = "#d9e2f3"
PLAN_SHADE = "#9bbb59"


# -- blocks ------------------------------------------------------------------------------------

@dataclass
class Cell:
    text: str = ""
    align: str = "left"            # left / center / right
    bold: bool = False
    bg: str = ""
    colspan: int = 1
    rowspan: int = 1
    indent: int = 0                # ระดับย่อหน้าของรายการ
    value: object = None           # ค่าตัวเลขสำหรับตารางคำนวณ


@dataclass
class Table:
    head: list                     # rows of Cells
    body: list                     # rows of Cells
    widths: list                   # relative widths
    font_pt: float = 11.0


@dataclass
class Para:
    text: str
    align: str = "left"
    bold: bool = False
    size: float = 13.0


@dataclass
class Chart:
    image: object                  # QImage
    name: str = "chart"
    width_pct: int = 70


@dataclass
class Report:
    title: str                     # sheet / window title
    landscape: bool = False
    blocks: list = field(default_factory=list)

    def p(self, text, **kw):
        self.blocks.append(Para(text, **kw))

    def br(self):
        self.blocks.append("pagebreak")


def C(text="", **kw) -> Cell:
    return Cell(text=str(text), **kw)


def N(x, **kw) -> Cell:
    """A money cell (blank for None)."""
    kw.setdefault("align", "right")
    return Cell(text=P.money(x) if x is not None else "", value=x, **kw)


def Q(x, digits=2, **kw) -> Cell:
    kw.setdefault("align", "right")
    if x is None or x == "":
        return Cell(text="", **kw)
    return Cell(text=f"{x:,.{digits}f}", value=x, **kw)


# -- HTML / PDF -----------------------------------------------------------------------------------

def _cell_html(c: Cell, tag="td", width=None) -> str:
    style = [f"text-align:{c.align}"]
    if c.bold:
        style.append("font-weight:bold")
    if c.indent:
        style.append(f"padding-left:{4 + 10 * c.indent}px")
    attrs = f' style="{";".join(style)}"'
    if width:
        attrs += f' width="{width:.1f}%"'
    if c.bg:
        attrs += f' bgcolor="{c.bg}"'
    if c.colspan > 1:
        attrs += f' colspan="{c.colspan}"'
    if c.rowspan > 1:
        attrs += f' rowspan="{c.rowspan}"'
    t = html.escape(c.text).replace("\n", "<br>")
    return f"<{tag}{attrs}>{t}</{tag}>"


def _rows_html(rows, pct, tag) -> str:
    """Rows with a width on every cell (Qt sizes columns from the cells, not from <col>)."""
    out, taken = [], set()
    for r, row in enumerate(rows):
        col, cells = 0, []
        for c in row:
            while (r, col) in taken:
                col += 1
            w = sum(pct[col:col + c.colspan]) if col < len(pct) else None
            cells.append(_cell_html(c, tag, w))
            for rr in range(r, r + c.rowspan):
                for cc in range(col, col + c.colspan):
                    taken.add((rr, cc))
            col += c.colspan
        out.append("<tr>" + "".join(cells) + "</tr>")
    return "".join(out)


def to_html(rep: Report, family: str) -> str:
    out = []
    for b in rep.blocks:
        if b == "pagebreak":
            out.append('<p style="page-break-before:always; margin:0;"></p>')
        elif isinstance(b, Para):
            w = "bold" if b.bold else "normal"
            out.append(f'<p align="{b.align}" style="font-size:{b.size}pt; font-weight:{w}; margin:1px 0;">'
                       f'{html.escape(b.text).replace(chr(10), "<br>")}</p>')
        elif isinstance(b, Chart):
            out.append(f'<p align="center"><img src="{b.name}" width="{int(b.width_pct * 9)}"></p>')
        elif isinstance(b, Table):
            tot = sum(b.widths) or 1
            pct = [w * 100.0 / tot for w in b.widths]
            out.append(f'<table width="100%" border="1" cellspacing="0" cellpadding="1" '
                       f'style="border-collapse:collapse; font-size:{b.font_pt}pt; border-color:#444;">'
                       f'<thead>{_rows_html(b.head, pct, "th")}</thead>'
                       f'<tbody>{_rows_html(b.body, pct, "td")}</tbody></table>')
    return (f'<html><body style="font-family:\'{family}\'; font-size:13pt;">'
            + "".join(out) + "</body></html>")


def to_pdf(rep: Report, path, family: str) -> None:
    from PySide6.QtCore import QMarginsF, QSizeF, QUrl
    from PySide6.QtGui import QFont, QPageLayout, QPageSize, QPdfWriter, QTextDocument
    writer = QPdfWriter(str(path))
    writer.setResolution(300)
    writer.setTitle(rep.title)
    writer.setCreator("ReadWanicn2027")
    orient = QPageLayout.Landscape if rep.landscape else QPageLayout.Portrait
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), orient, QMarginsF(12, 12, 10, 12),
                                     QPageLayout.Millimeter))
    doc = QTextDocument()
    doc.setDefaultFont(QFont(family, 13))
    for b in rep.blocks:
        if isinstance(b, Chart):
            doc.addResource(QTextDocument.ImageResource, QUrl(b.name), b.image)
    doc.setHtml(to_html(rep, family))
    fmt = doc.rootFrame().frameFormat()
    fmt.setMargin(0)
    doc.rootFrame().setFrameFormat(fmt)
    doc.documentLayout().setPaintDevice(writer)
    doc.setPageSize(QSizeF(writer.pageLayout().paintRectPixels(writer.resolution()).size()))
    doc.print_(writer)


def font_file() -> str:
    f = Path(__file__).resolve().parent.parent / "assets" / "Laksaman.ttf"
    return str(f) if f.exists() else ""


def number_pages(path) -> None:
    """หน้า n/N at the foot of each page, and the developer line."""
    import pymupdf
    doc = pymupdf.open(str(path))
    n = doc.page_count
    f = font_file()
    for i, page in enumerate(doc):
        r = page.rect
        kw = dict(fontsize=7.5, color=(0.35, 0.35, 0.35))
        if f:
            kw.update(fontfile=f, fontname="th")
        page.insert_text((r.width - 70, r.height - 14), f"หน้า {i + 1}/{n}", **kw)
        page.insert_text((34, r.height - 14), DEVELOPER_LINE, **kw)
    tmp = str(path) + ".tmp"
    doc.save(tmp, garbage=3, deflate=True)
    doc.close()
    Path(tmp).replace(path)


# -- spreadsheet ------------------------------------------------------------------------------------

def to_xlsx(reports: list, path, family: str = "TH SarabunPSK") -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    wb.remove(wb.active)
    thin = Side(style="thin", color="555555")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    for rep in reports:
        ws = wb.create_sheet(rep.title[:31])
        ws.page_setup.orientation = "landscape" if rep.landscape else "portrait"
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        r = 1
        ncols = max([len(b.widths) for b in rep.blocks if isinstance(b, Table)] or [6])
        widths_set = False
        for b in rep.blocks:
            if b == "pagebreak":
                from openpyxl.worksheet.pagebreak import Break
                ws.row_breaks.append(Break(id=r - 1))
                continue
            if isinstance(b, Para):
                c = ws.cell(r, 1, b.text)
                c.font = Font(name=family, size=b.size + 1, bold=b.bold)
                c.alignment = Alignment(horizontal={"center": "center", "right": "right"}.get(b.align, "left"),
                                        vertical="center")
                if b.align == "center":
                    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
                r += 1
                continue
            if isinstance(b, Chart):
                r += 1
                continue
            if not widths_set:
                tot = sum(b.widths) or 1
                for i, w in enumerate(b.widths):
                    ws.column_dimensions[get_column_letter(i + 1)].width = max(6, w * 160 / tot)
                widths_set = True
            taken = set()
            for kind, rows in (("head", b.head), ("body", b.body)):
                for row in rows:
                    col = 1
                    for cell in row:
                        while (r, col) in taken:
                            col += 1
                        v = cell.value if cell.value is not None else cell.text
                        if isinstance(v, str) and cell.indent:
                            v = "   " * cell.indent + v
                        c = ws.cell(r, col, v)
                        c.font = Font(name=family, size=b.font_pt + 3, bold=cell.bold or kind == "head")
                        c.alignment = Alignment(horizontal={"center": "center", "right": "right"}.get(
                            cell.align, "left"), vertical="center", wrap_text=kind == "head")
                        c.border = box
                        if isinstance(cell.value, float):
                            c.number_format = "#,##0.00"
                        bg = cell.bg or (SHADE if kind == "head" else "")
                        if bg:
                            c.fill = PatternFill("solid", fgColor=bg.lstrip("#"))
                        if cell.colspan > 1 or cell.rowspan > 1:
                            ws.merge_cells(start_row=r, start_column=col, end_row=r + cell.rowspan - 1,
                                           end_column=col + cell.colspan - 1)
                            for rr in range(r, r + cell.rowspan):
                                for cc in range(col, col + cell.colspan):
                                    taken.add((rr, cc))
                                    ws.cell(rr, cc).border = box
                        col += cell.colspan
                    r += 1
            r += 1
        ws.cell(r + 1, 1, DEVELOPER_LINE).font = Font(name=family, size=10, color="777777")
    wb.save(str(path))


# -- common pieces ---------------------------------------------------------------------------------

def _work_name(p: P.Project) -> str:
    return p.work[0]


def _project_line(p: P.Project) -> str:
    s = f"โครงการ {p.title or '...........................'}"
    if p.budget:
        s += f"  งบประมาณ {p.budget:,.2f} บาท"
    if p.project_no:
        s += f"  เลขที่โครงการ {p.project_no}"
    return s


def _name_cell(it: P.Item, bold=None) -> Cell:
    return C(it.label, indent=max(0, it.level - 1), bold=it.header if bold is None else bold)


# -- ว651 -------------------------------------------------------------------------------------------

def report_651(p: P.Project) -> list:
    """สิ่งที่ส่งมาด้วย 1 (แบบสรุปราคากลาง + ราคาที่ปรับลดทุกรายการ) and
    สิ่งที่ส่งมาด้วย 2 (เอกสารแนบท้ายสัญญา) for the chosen one of the four kinds of work."""
    res = P.compute_651(p)
    red = res.red
    south = res.uplift > 1.0
    work = _work_name(p)
    qty_word = p.work[1]
    a = Report("ว651 สรุปราคากลาง")
    a.p(f"แบบสรุปราคากลาง{work}", align="center", bold=True, size=15)
    if south:
        a.p(P.SOUTH_NOTE, align="center", size=12)
    a.p(_project_line(p), align="center", size=12)
    if p.agency:
        a.p(f"หน่วยงานเจ้าของโครงการ/งานก่อสร้าง {p.agency}", align="center", size=12)
    # ตาราง: สรุปราคากลางโครงการ
    a.p(f"ตาราง : สรุปราคากลางโครงการ{work}", bold=True, size=12)
    head = [[C("ลำดับที่", align="center"), C("รายการ", align="center"), C("หน่วย", align="center"),
             C("ค่างานต้นทุน", align="center"), C("Factor F / Vat", align="center"), C("ราคากลาง", align="center")]
            + ([C("ราคากลาง บวกเพิ่มร้อยละ 5", align="center")] if south else [])]
    body = []
    names = [f"{work} (ค่าวัสดุและค่าแรง)", "งานครุภัณฑ์จัดซื้อ (ถ้ามี)", "ค่าใช้จ่ายพิเศษตามข้อกำหนด (ถ้ามี)"]
    for i, (g, nm) in enumerate(zip(res.groups, names)):
        _n, cost, fac, mid, mid_up, _red = g
        row = [C(i + 1, align="center"), C(nm), C("บาท", align="center"), N(cost if cost else None),
               Q(fac, 4, align="center"), N(mid if cost else None)]
        if south:
            row.append(N(mid_up if cost else None))
        body.append(row)
    body.append([C("รวม", align="right", bold=True, colspan=5), N(res.mid_total, bold=True)]
                + ([N(res.mid_up_total, bold=True)] if south else []))
    a.blocks.append(Table(head, body, [7, 45, 8, 16, 11, 16] + ([18] if south else []), 11))
    a.p("ตาราง : ราคาตามคำเสนอของผู้ชนะการจัดซื้อจัดจ้าง", bold=True, size=12)
    a.blocks.append(Table([[C("ลำดับที่", align="center"), C("รายการ", align="center"), C("หน่วย", align="center"),
                            C("ราคาที่เสนอ", align="center")]],
                          [[C(1, align="center"), C("ราคาตามคำเสนอของผู้ชนะการจัดซื้อจัดจ้าง"),
                            C("บาท", align="center"), N(p.offer, bold=True, bg="#fff2cc")]], [7, 60, 10, 23], 11))
    sp = P.r2(P.special_total(p) * res.uplift)
    mid_label = "ราคากลางบวกเพิ่มร้อยละ 5" if south else "ราคากลาง"
    a.blocks.append(Table(
        [[C("วิธีการคำนวณราคากลางหักค่าใช้จ่ายพิเศษตามข้อกำหนด", colspan=2, align="left"),
          C("วิธีการคำนวณราคาตามคำเสนอ ฯ หักค่าใช้จ่ายพิเศษตามข้อกำหนด", colspan=2, align="left")]],
        [[C(mid_label), N(P.r2(p.mid_price * res.uplift)), C("ราคาที่เสนอของผู้ชนะการจัดซื้อจัดจ้าง"), N(p.offer)],
         [C("หัก ค่าใช้จ่ายพิเศษตามข้อกำหนด"), N(sp), C("หัก ค่าใช้จ่ายพิเศษตามข้อกำหนด"), N(sp)],
         [C("ผลต่างระหว่างราคากลางหักค่าใช้จ่ายพิเศษตามข้อกำหนด", bold=True), N(red.mid_net, bold=True),
          C("ผลต่างระหว่างราคาตามคำเสนอ ฯ หักค่าใช้จ่ายพิเศษตามข้อกำหนด", bold=True), N(red.offer_net, bold=True)]],
        [33, 17, 33, 17], 9.5))
    a.blocks.append(Table(
        [[C("ผลต่างระหว่างราคากลางกับราคาคำเสนอ ฯ หักค่าใช้จ่ายพิเศษตามข้อกำหนด", colspan=3)]],
        [[C("ผลต่างระหว่างราคากลางหักค่าใช้จ่ายพิเศษตามข้อกำหนด"), N(red.mid_net), C("(1)", align="center")],
         [C("หัก ผลต่างระหว่างราคาที่เสนอ ฯ หักค่าใช้จ่ายพิเศษตามข้อกำหนด"), N(red.offer_net), C("(2)", align="center")],
         [C("ผลต่างระหว่างราคากลางกับราคาคำเสนอ ฯ หักค่าใช้จ่ายพิเศษตามข้อกำหนด", bold=True), N(red.diff, bold=True),
          C("(3)", align="center")],
         [C("ผลต่างตาม (3) เทียบกับราคากลางหักค่าใช้จ่ายพิเศษตามข้อกำหนด (1) คิดเป็นร้อยละ", bold=True),
          Q(red.pct_down, 2, bold=True, bg="#fff2cc"), C("")]],
        [70, 20, 10], 9.5))
    a.blocks.append(Table(
        [[C("การคำนวณร้อยละวัสดุในการจ้าง", colspan=2, align="center")]],
        [[C("ราคากลาง", bg="#c6d9f1"), N(P.r2(p.mid_price * res.uplift), bg="#c6d9f1")],
         [C("ราคาเสนอ", bg="#ffff00"), N(p.offer, bg="#ffff00")],
         [C("ลดลง", bg="#00b050", align="right"), N(red.diff, bg="#00b050")],
         [C("ค่างานลดลง (ร้อยละ)", bg="#ffff00"), Q(red.pct_down, 2, bg="#ffff00")],
         [C("ค่างานคงเหลือ (ร้อยละ)", bg="#e6b9b8"), Q(red.pct_left, 2, bg="#e6b9b8")]],
        [60, 40], 10))
    # รายการทั้งหมด
    a.br()
    a.p(f"แบบสรุปราคากลาง{work} — รายการ", align="center", bold=True, size=14)
    a.p(_project_line(p), align="center", size=11)
    mid_cols = [C("ค่างานต้นทุน", align="center"), C("Factor F / Vat", align="center"), C("ราคากลาง", align="center")]
    if south:
        mid_cols.append(C("ราคากลาง บวกเพิ่มร้อยละ 5", align="center"))
    head = [[C("ลำดับที่", align="center", rowspan=2), C("รายการ", align="center", rowspan=2),
             C("หน่วย", align="center", rowspan=2), C(qty_word, align="center", rowspan=2),
             C("ราคากลางงานก่อสร้าง (บาท)", align="center", colspan=len(mid_cols)),
             C("ราคาที่ปรับลดตามคำเสนอ (บาท)", align="center", colspan=2)],
            mid_cols + [C("ราคาที่ปรับลด", align="center"), C("ราคาต่อหน่วย", align="center")]]
    sub_mid = P.subtotals(res.rows, "mid")
    sub_up = P.subtotals(res.rows, "mid_up")
    sub_red = P.subtotals(res.rows, "reduced")
    body = []
    for i, r in enumerate(res.rows):
        it = r.item
        if it.header:
            row = [C(it.no or "", align="center"), _name_cell(it), C(""), C(""), C(""), C(""),
                   N(sub_mid.get(i), bold=True)]
            if south:
                row.append(N(sub_up.get(i), bold=True))
            row += [N(sub_red.get(i), bold=True), C("")]
        else:
            mark = " (*)" if i == res.adjust_row else ""
            row = [C(it.no or "", align="center"), C(it.label + mark, indent=max(0, it.level - 1)),
                   C(it.unit, align="center"), Q(it.qty), N(r.cost), Q(r.factor, 4, align="center"), N(r.mid)]
            if south:
                row.append(N(r.mid_up))
            row += [N(r.reduced), N(r.unit_price)]
        body.append(row)
    body.append([C("วงเงินรวม", align="right", bold=True, colspan=6), N(res.mid_total, bold=True)]
                + ([N(res.mid_up_total, bold=True)] if south else [])
                + [N(res.reduced_total, bold=True, bg="#fff2cc"), C("(*)", align="center")])
    a.blocks.append(Table(head, body, [6, 40, 7, 9, 12, 8, 12] + ([12] if south else []) + [12, 10], 9.5))
    a.p("หมายเหตุ (*) ส่วนต่างนี้ให้ปรับเพิ่ม / ลด ในรายการใดรายการหนึ่งได้ตามความเหมาะสม ยกเว้น "
        "รายการค่าใช้จ่ายพิเศษตามข้อกำหนด ทั้งนี้ วงเงินรวมของการปรับลดราคาจะต้องเท่ากับ"
        "ราคาตามคำเสนอของผู้ชนะการจัดซื้อจัดจ้าง", size=10.5)
    if res.adjust_row >= 0:
        adj = res.rows[res.adjust_row]
        a.p(f"โปรแกรมปรับเศษ {adj.adjusted:+,.2f} บาท ในรายการ «{adj.item.label}» "
            f"(รายการที่มีมูลค่ามากที่สุด) วงเงินรวมเท่ากับราคาเสนอ {p.offer:,.2f} บาท", size=10.5)
    a.p("แบบฟอร์มตามหนังสือด่วนที่สุด ที่ กค (กวจ) 0405.3/ว651 ลงวันที่ 26 กันยายน 2568", size=10.5)

    # สิ่งที่ส่งมาด้วย 2: เอกสารแนบท้ายสัญญา
    b = Report("ว651 แนบท้ายสัญญา")
    b.p("แบบแสดงรายการ ปริมาณงาน และราคา", align="center", bold=True, size=15)
    b.p(f"เอกสารแนบท้ายสัญญาจ้างก่อสร้าง : {work}", align="center", bold=True, size=13)
    if south:
        b.p(P.SOUTH_NOTE, align="center", size=11.5)
    b.p(f"เลขที่ {p.contract_no or '................'}  ลงวันที่ {p.contract_date or '................'}",
        align="center", size=12)
    b.p(_project_line(p), align="center", size=12)
    info = [("หน่วยงานเจ้าของโครงการ", p.agency or ""),
            ("วงเงินงบประมาณ", f"{p.budget:,.2f} บาท" if p.budget else ""),
            ("ราคากลางงานก่อสร้าง", f"{res.mid_up_total:,.2f} บาท"),
            ("วงเงินตามสัญญา", f"{p.offer:,.2f} บาท"),
            ("ชื่อผู้รับจ้าง", p.contractor or "")]
    b.blocks.append(Table([], [[C(k, bold=True), C(v)] for k, v in info], [30, 70], 11.5))
    head = [[C("ลำดับที่", align="center", rowspan=2), C("รายการ", align="center", rowspan=2),
             C("หน่วย", align="center", rowspan=2), C(qty_word, align="center", rowspan=2),
             C("ราคาที่ปรับลดตามคำเสนอ (บาท)", align="center", colspan=2)],
            [C("ราคา", align="center"), C("ราคาต่อหน่วย", align="center")]]
    body = []
    for i, r in enumerate(res.rows):
        it = r.item
        if it.header:
            body.append([C(it.no or "", align="center"), _name_cell(it), C(""), C(""),
                         N(sub_red.get(i), bold=True), C("")])
        else:
            body.append([C(it.no or "", align="center"), C(it.label, indent=max(0, it.level - 1)),
                         C(it.unit, align="center"), Q(it.qty), N(r.reduced), N(r.unit_price)])
    body.append([C("วงเงินตามสัญญา", align="right", bold=True, colspan=4), N(res.reduced_total, bold=True,
                                                                              bg="#fff2cc"), C("")])
    b.blocks.append(Table(head, body, [7, 52, 9, 10, 13, 11], 10))
    b.p(f"({P.baht_text(res.reduced_total)})", align="right", size=11)
    b.p("แบบฟอร์มตามหนังสือด่วนที่สุด ที่ กค (กวจ) 0405.3/ว651 ลงวันที่ 26 กันยายน 2568", size=10.5)
    return [a, b]


# -- ว124 -------------------------------------------------------------------------------------------

def s_curve(plan: "P.Plan124", w=1800, h=760):
    """%ACC PLAN (and the ว124 thresholds) as a picture."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor("white"))
    g = QPainter(img)
    g.setRenderHint(QPainter.Antialiasing)
    L, T, R, B = 110, 50, 40, 90
    pw, ph = w - L - R, h - T - B
    g.setFont(QFont("Laksaman", 15))
    g.setPen(QPen(QColor("#bbbbbb"), 1))
    for k in range(0, 11):
        y = T + ph - ph * k / 10
        g.drawLine(L, int(y), L + pw, int(y))
        g.setPen(QColor("#333333"))
        g.drawText(QRectF(0, y - 14, L - 12, 28), Qt.AlignRight | Qt.AlignVCenter, f"{k * 10}%")
        g.setPen(QPen(QColor("#bbbbbb"), 1))
    n = plan.months
    xs = [L + pw * (m + 1) / n for m in range(n)]
    g.setPen(QColor("#333333"))
    for m, x in enumerate(xs):
        g.drawText(QRectF(x - 60, T + ph + 8, 120, 30), Qt.AlignCenter, f"เดือน {m + 1}")
    g.setPen(QPen(QColor("#333333"), 2))
    g.drawLine(L, T + ph, L + pw, T + ph)
    g.drawLine(L, T, L, T + ph)
    pts = [QPointF(L, T + ph)] + [QPointF(x, T + ph - ph * min(100, v) / 100) for x, v in zip(xs, plan.acc_plan)]
    g.setPen(QPen(QColor("#1f4e79"), 4))
    for a, b in zip(pts, pts[1:]):
        g.drawLine(a, b)
    g.setBrush(QColor("#1f4e79"))
    for p_, v in zip(pts[1:], plan.acc_plan):
        g.drawEllipse(p_, 6, 6)
        g.drawText(QRectF(p_.x() - 70, p_.y() - 36, 140, 28), Qt.AlignCenter, f"{v:.2f}%")
    # ว124 thresholds
    g.setPen(QPen(QColor("#c00000"), 2, Qt.DashLine))
    cum = [sum(plan.days[:i + 1]) for i in range(n)]
    tot = cum[-1] or 1
    for words, _k, _v, need in plan.checks:
        frac = {"เกิน 1 ใน 2 ของระยะเวลา": 0.5, "เกิน 3 ใน 4 ของระยะเวลา": 0.75}.get(words, 1.0)
        x = L + pw * frac
        y = T + ph - ph * need / 100
        g.drawLine(QPointF(x - 30, y), QPointF(x + 30, y))
        g.drawText(QRectF(x - 140, y + 4, 280, 26), Qt.AlignCenter, f"ขั้นต่ำ {need:.0f}%")
    del tot
    g.setPen(QColor("#1f4e79"))
    g.drawText(QRectF(L, 6, pw, 36), Qt.AlignCenter, "% ACC PLAN — ร้อยละของแผนดำเนินงานสะสม")
    g.end()
    return img


def report_124(p: P.Project) -> list:
    plan = P.compute_124(p)
    n = plan.months
    rep = Report("ว124 แผนการทำงาน", landscape=True)
    rep.p("แผนการทำงาน", align="center", bold=True, size=15)
    rep.p(_project_line(p), align="center", size=11.5)
    rep.p(f"ระยะเวลาก่อสร้างตามแผนดำเนินงานทั้งสัญญา {n} เดือน ({sum(plan.days)} วัน)"
          + (f" เริ่ม {p.start}" if p.start else ""), align="center", size=11.5)
    fs = 9.5 if n <= 8 else 8.5 if n <= 12 else 7.0
    head = [[C("ที่", align="center", rowspan=2), C("รายการ", align="center", rowspan=2),
             C("หน่วย", align="center", rowspan=2), C("ปริมาณงาน", align="center", rowspan=2),
             C("ราคาต่อหน่วย", align="center", rowspan=2), C("เป็นเงิน", align="center", rowspan=2),
             C("%", align="center", rowspan=2)] + [C(f"เดือนที่ {m + 1}", align="center") for m in range(n)],
            [C(f"{d} วัน", align="center") for d in plan.days]]
    lines = {id(it): (a, pc, pl) for it, a, pc, pl in plan.lines}
    res = P.compute_651(p)
    body = []
    k = 0
    for r in res.rows:
        it = r.item
        if it.header:
            body.append([C(""), _name_cell(it), C(""), C(""), C(""), C(""), C("")] + [C("") for _m in range(n)])
            continue
        k += 1
        a, pc, pl = lines[id(it)]
        cells = [C(k, align="center"), C(it.label, indent=max(0, it.level - 1)), C(it.unit, align="center"),
                 Q(it.qty), N(r.unit_price), N(a), Q(pc, 2)]
        for v in pl:
            cells.append(Q(v, 0 if abs(v - round(v)) < 1e-6 else 2, align="center",
                           bg=PLAN_SHADE if v > 0 else "") if v > 0 else C(""))
        body.append(cells)
    body.append([C("รวม", align="right", bold=True, colspan=5), N(plan.total, bold=True), Q(100.0, 2, bold=True)]
                + [C("") for _m in range(n)])

    def line(name, vals, money_=False, bold=False):
        return [C(name, align="right", bold=True, colspan=7)] + [
            (Q(v, 0, bold=bold) if money_ else Q(v, 2, bold=bold)) if v is not None else C("") for v in vals]
    blank = [None] * n
    body += [line("Money", plan.money, True), line("AccMoney", plan.acc_money, True),
             line("% PLAN", plan.pct_plan), line("% ACC PLAN", plan.acc_plan, bold=True),
             line("% ACTUAL", blank), line("% ACC ACTUAL", blank), line("% ACC DIFF", blank),
             line("% PLAN/2", [v / 2 for v in plan.pct_plan]), line("% PLAN/2 DIFF", blank)]
    widths = [3, 26, 4.5, 6, 7, 9.5, 5.5] + [max(4.5, 48.0 / n)] * n
    rep.blocks.append(Table(head, body, widths, fs))
    rep.blocks.append(Chart(s_curve(plan), "scurve.png", 80))
    rep.p("เกณฑ์การประเมินผลการทำงาน (ว124 ข้อ 2.2)", bold=True, size=12)
    chk = [[C("ช่วงเวลา", align="center"), C("ถึงเดือนที่", align="center"),
            C("แผนสะสม (%)", align="center"), C("ผลงานสะสมขั้นต่ำ (%)", align="center")]]
    rows = [[C(w), C(k_ + 1, align="center"), Q(v, 2, align="center"), Q(need, 0, align="center")]
            for w, k_, v, need in plan.checks]
    rep.blocks.append(Table(chk, rows, [40, 15, 20, 25], 10.5))
    notes = [
        "หมายเหตุ",
        f"1) กำหนดระยะเวลาการก่อสร้างตามแผนดำเนินงานทั้งสัญญา จำนวน {sum(plan.days)} วัน ({n} เดือน)",
        "2) ช่องที่แรเงา หมายถึง ระยะเวลาการก่อสร้างตามแผนดำเนินงานของแต่ละรายการก่อสร้าง",
        "3) ตัวเลขในช่อง หมายถึง ร้อยละของงานที่ผู้รับจ้างต้องดำเนินการตามแผนงานประจำเดือนของแต่ละรายการ "
        "(แต่ละรายการรวมกัน 100 %)",
        "4) Money มูลค่างานแต่ละเดือน คำนวณจากร้อยละตามแผนงานเทียบกับมูลค่างานของแต่ละรายการ · "
        "5) AccMoney มูลค่างานสะสม",
        "6) % PLAN ร้อยละของแผนดำเนินงาน เทียบกับมูลค่างานทั้งโครงการ · 7) % ACC PLAN ร้อยละของแผนสะสม",
        "8) % ACTUAL / 9) % ACC ACTUAL ร้อยละของการดำเนินงานจริง (กรอกระหว่างก่อสร้าง) · "
        "10) % ACC DIFF ความแตกต่างระหว่างงานจริงกับแผนสะสม",
        "เกณฑ์ ว124: เมื่อพ้น ½ ของเวลาผลงานสะสมต้องไม่น้อยกว่าร้อยละ 25 · พ้น ¾ ไม่น้อยกว่าร้อยละ 65 · "
        "ครบกำหนดไม่น้อยกว่าร้อยละ 85 และพ้น ½ ของเวลาผลงานประจำเดือนต้องไม่น้อยกว่าร้อยละ 50 ของแผน (% PLAN/2)",
    ]
    for t in notes:
        rep.p(t, size=10.5, bold=t == "หมายเหตุ")
    rep.p("ลงชื่อ ................................................ (คู่สัญญาฝ่ายผู้รับจ้าง)", align="right", size=12)
    rep.p(f"({p.signer or p.contractor or '................................................'})", align="right",
          size=12)
    rep.p("ตามหนังสือคณะกรรมการวินิจฉัยฯ ที่ กค (กวจ) 0405.2/ว124 — แผนการทำงานถือเป็นเอกสารส่วนหนึ่งของสัญญา",
          size=10)
    return [rep]


# -- ว78 --------------------------------------------------------------------------------------------

def report_78(p: P.Project) -> list:
    w = P.compute_78(p)
    res = P.compute_651(p)
    price = {id(r.item): r for r in res.rows}
    out = []
    a = Report("ว78 ภาคผนวก 1")
    a.p("ภาคผนวก 1", align="right", bold=True, size=12)
    a.p("ตารางการจัดทำแผนการใช้พัสดุที่ผลิตภายในประเทศ", align="center", bold=True, size=15)
    a.p(f"โครงการ {p.title or '..........................................'}", align="center", size=12)
    a.p("รายการพัสดุหรือครุภัณฑ์ที่ใช้ในโครงการ\nแผนการใช้พัสดุที่ผลิตภายในประเทศ", align="center", bold=True,
        size=12)
    if w.exempt:
        a.p(w.exempt, size=11.5, bold=True)
    head = [[C("ลำดับ", align="center"), C("รายการ", align="center"), C("หน่วย", align="center"),
             C("ปริมาณ", align="center"), C("ราคาต่อหน่วย\n(บาท)", align="center"),
             C("เป็นเงิน\n(รวม)", align="center"), C("พัสดุ\nในประเทศ", align="center"),
             C("พัสดุ\nต่างประเทศ", align="center")]]
    body = []
    for k, (it, amt, d) in enumerate(w.materials, 1):
        body.append([C(k, align="center"), C(it.label), C(it.unit, align="center"), Q(it.qty),
                     N(price[id(it)].unit_price), N(amt), N(amt * d / 100), N(amt * (100 - d) / 100)])
    body.append([C("รวม", bold=True, align="center"), C(""), C(""), C(""), C(""), N(w.mat_total, bold=True),
                 N(w.mat_domestic, bold=True), N(w.mat_total - w.mat_domestic, bold=True)])
    body.append([C("อัตรา\n(ร้อยละ)", bold=True, align="center"), C(""), C(""), C(""), C(""),
                 Q(100.0, 2, bold=True), Q(w.mat_pct, 2, bold=True, bg="#e2efda" if w.mat_ok else "#f8cbad"),
                 Q(100 - w.mat_pct if w.mat_total else 0.0, 2, bold=True)])
    a.blocks.append(Table(head, body, [6, 40, 7, 8, 10, 11, 11, 11], 10))
    a.p(f"เกณฑ์: พัสดุที่ผลิตภายในประเทศไม่น้อยกว่าร้อยละ {P.DOMESTIC_MIN:.0f} ของมูลค่าพัสดุที่ใช้ในงานก่อสร้าง — "
        + ("ผ่าน" if w.mat_ok else "ไม่ผ่าน"), size=11)
    _sign(a, "คู่สัญญาฝ่ายผู้รับจ้าง", p.signer or p.contractor)
    out.append(a)

    b = Report("ว78 ภาคผนวก 2")
    b.p("ภาคผนวก 2", align="right", bold=True, size=12)
    b.p("ตารางการจัดทำแผนการใช้เหล็กที่ผลิตภายในประเทศ", align="center", bold=True, size=15)
    b.p(f"โครงการ {p.title or '..........................................'}", align="center", size=12)
    b.p("รายการพัสดุหรือครุภัณฑ์ที่ใช้ในโครงการ\nแผนการใช้เหล็กที่ผลิตภายในประเทศ", bold=True, size=12)
    b.p(f"ปริมาณเหล็กทั้งโครงการ {w.steel_t:,.4f} ตัน", bold=True, size=12)
    head = [[C("ลำดับ", align="center"), C("รายการ", align="center"), C("หน่วย", align="center"),
             C("ปริมาณ", align="center"), C("น้ำหนัก\n(ตัน)", align="center"),
             C("เหล็ก\nในประเทศ (ตัน)", align="center"), C("เหล็ก\nต่างประเทศ (ตัน)", align="center")]]
    body = []
    for k, (it, t, d) in enumerate(w.steel, 1):
        body.append([C(k, align="center"), C(it.label), C(it.unit, align="center"), Q(it.qty),
                     Q(t, 4) if t is not None else C("ไม่ทราบน้ำหนัก", align="center", bg="#f8cbad"),
                     Q(t * d / 100, 4) if t is not None else C(""),
                     Q(t * (100 - d) / 100, 4) if t is not None else C("")])
    body.append([C("รวม", bold=True, align="center"), C(""), C(""), C(""), Q(w.steel_t, 4, bold=True),
                 Q(w.steel_dom_t, 4, bold=True), Q(w.steel_t - w.steel_dom_t, 4, bold=True)])
    body.append([C("อัตรา\n(ร้อยละ)", bold=True, align="center"), C(""), C(""), C(""), Q(100.0, 2, bold=True),
                 Q(w.steel_pct, 2, bold=True, bg="#e2efda" if w.steel_ok else "#f8cbad"),
                 Q(100 - w.steel_pct if w.steel_t else 0.0, 2, bold=True)])
    b.blocks.append(Table(head, body, [6, 46, 7, 9, 10, 11, 11], 10))
    if w.missing_weight:
        b.p(f"รายการที่ยังไม่ทราบน้ำหนัก {len(w.missing_weight)} รายการ — กรอก «กก./หน่วย» ในโปรแกรมก่อนออกรายงานฉบับจริง",
            size=11, bold=True)
    b.p(f"เกณฑ์: เหล็กที่ผลิตภายในประเทศไม่น้อยกว่าร้อยละ {P.STEEL_MIN:.0f} ของปริมาณเหล็กทั้งหมดตามสัญญา — "
        + ("ผ่าน" if w.steel_ok else "ไม่ผ่าน"), size=11)
    _sign(b, "คู่สัญญาฝ่ายผู้รับจ้าง", p.signer or p.contractor)
    out.append(b)

    c = Report("ว78 ภาคผนวก 3")
    c.p("ภาคผนวก 3", align="right", bold=True, size=12)
    c.p("ตารางรายงานผลการใช้พัสดุที่ผลิตภายในประเทศ", align="center", bold=True, size=15)
    c.p(f"โครงการ {p.title or '..........................................'}", align="center", size=12)
    all_value = w.mat_total + w.steel_value
    n_lines = len(w.materials) + len(w.steel)
    c.p("การใช้พัสดุทั้งโครงการ", bold=True, size=12)
    c.p(f"รายการพัสดุทั้งโครงการ  {n_lines:,} รายการ\nมูลค่าพัสดุทั้งโครงการ  {all_value:,.2f} บาท", size=12)
    c.p("มูลค่าการใช้พัสดุที่ผลิตภายในประเทศ", bold=True, size=12)
    c.blocks.append(Table([[C("รายการ", align="center"), C("จำนวนเงิน (บาท)", align="center"),
                            C("อัตรา (ร้อยละ)", align="center")]],
                          [[C("มูลค่าพัสดุที่ผลิตภายในประเทศ"), N(w.mat_domestic), Q(w.mat_pct, 2, align="center")],
                           [C("มูลค่าพัสดุที่ผลิตจากต่างประเทศ"), N(w.mat_total - w.mat_domestic),
                            Q(100 - w.mat_pct if w.mat_total else 0, 2, align="center")]], [50, 25, 25], 11))
    c.p("ปริมาณการใช้เหล็กทั้งโครงการ", bold=True, size=12)
    c.p(f"ปริมาณการใช้เหล็กทั้งโครงการ  {w.steel_t:,.4f} ตัน      มูลค่าเหล็กทั้งโครงการ  {w.steel_value:,.2f} บาท",
        size=12)
    c.blocks.append(Table([[C("รายการ", align="center"), C("หน่วย", align="center"), C("จำนวน", align="center"),
                            C("อัตรา (ร้อยละ)", align="center")]],
                          [[C("ปริมาณการใช้เหล็กที่ผลิตภายในประเทศ"), C("ตัน", align="center"), Q(w.steel_dom_t, 4),
                            Q(w.steel_pct, 2, align="center")]], [45, 15, 20, 20], 11))
    ok = w.mat_ok and w.steel_ok
    box = lambda on: "☑" if on else "☐"   # noqa: E731
    c.p("สรุป", bold=True, size=12)
    c.p(f"{box(ok)} เป็นไปตามกฎกระทรวงกำหนดพัสดุและวิธีการจัดซื้อจัดจ้างพัสดุที่รัฐต้องการส่งเสริมหรือสนับสนุน "
        f"(ฉบับที่ 2) พ.ศ. 2563\n      {box(w.mat_ok)} ร้อยละ 60 พัสดุทั่วไป (มูลค่า)   "
        f"{box(w.steel_ok and bool(w.steel))} ร้อยละ 90 เหล็ก (ปริมาณ)", size=12)
    c.p(f"{box(not ok)} ไม่เป็นไปตามกฎกระทรวงกำหนดพัสดุและวิธีการจัดซื้อจัดจ้างพัสดุที่รัฐต้องการส่งเสริมหรือสนับสนุน "
        "(ฉบับที่ 2) พ.ศ. 2563\n      เหตุผล/ความจำเป็นที่หน่วยงานของรัฐไม่สามารถดำเนินการได้\n"
        "      ..............................................................................................", size=12)
    _sign(c, "ประธานกรรมการตรวจรับพัสดุ", "")
    c.p("ตามหนังสือคณะกรรมการวินิจฉัยฯ ว78 — กฎกระทรวงกำหนดพัสดุที่รัฐต้องการส่งเสริมหรือสนับสนุน (ฉบับที่ 2) พ.ศ. 2563",
        size=10)
    out.append(c)
    return out


def _sign(rep: Report, role: str, name: str):
    rep.p(" ", size=8)
    rep.p(f"ลงชื่อ ................................................ ({role})", align="right", size=12)
    rep.p(f"({name or '................................................'})", align="right", size=12)


REPORTS = {"651": report_651, "124": report_124, "78": report_78}


def write(kind: str, p: P.Project, pdf_path, family: str, xlsx: bool = True) -> list:
    """Write the reports of `kind` (651 / 124 / 78): one PDF (parts merged) and one .xlsx.
    Returns the paths written."""
    reps = REPORTS[kind](p)
    pdf_path = Path(pdf_path)
    written = []
    if len(reps) == 1:
        to_pdf(reps[0], pdf_path, family)
        number_pages(pdf_path)
    else:
        import pymupdf
        parts = []
        for i, rep in enumerate(reps):
            part = pdf_path.with_name(f"{pdf_path.stem}.part{i}.pdf")
            to_pdf(rep, part, family)
            parts.append(part)
        out = pymupdf.open()
        for part in parts:
            with pymupdf.open(str(part)) as d:
                out.insert_pdf(d)
        out.save(str(pdf_path), garbage=3, deflate=True)
        out.close()
        for part in parts:
            part.unlink(missing_ok=True)
        number_pages(pdf_path)
    written.append(pdf_path)
    if xlsx:
        xp = pdf_path.with_suffix(".xlsx")
        to_xlsx(reps, xp)
        written.append(xp)
    return written
