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
    size: float = 0.0              # ขนาดตัวอักษรเฉพาะช่อง (0 = ตามตาราง)
    digits: int = 2                # ทศนิยมในตารางคำนวณ


@dataclass
class Table:
    head: list                     # rows of Cells
    body: list                     # rows of Cells
    widths: list                   # relative widths
    font_pt: float = 11.0
    border: int = 1                # 0 = no lines (the boxes of the ว651 summary)
    width_pct: int = 100


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
    footer: bool = True            # the developer line at the foot of each page

    def p(self, text, **kw):
        self.blocks.append(Para(P.arabic(text), **kw))

    def br(self):
        self.blocks.append("pagebreak")


def C(text="", **kw) -> Cell:
    return Cell(text=P.arabic(text), **kw)


def N(x, **kw) -> Cell:
    """A money cell (blank for None)."""
    kw.setdefault("align", "right")
    return Cell(text=P.money(x) if x is not None else "", value=x, **kw)


def Q(x, digits=2, **kw) -> Cell:
    kw.setdefault("align", "right")
    if x is None or x == "":
        return Cell(text="", **kw)
    return Cell(text=f"{x:,.{digits}f}", value=x, digits=digits, **kw)


# -- HTML / PDF -----------------------------------------------------------------------------------

def _cell_html(c: Cell, tag="td", width=None) -> str:
    style = [f"text-align:{c.align}"]
    if isinstance(c.value, (int, float)) and not isinstance(c.value, bool):
        style.append("white-space:nowrap")           # 4,900,000.00 never breaks over two lines
    if c.size:
        style.append(f"font-size:{c.size}pt")
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
            out.append(f'<table width="{b.width_pct}%" border="{b.border}" cellspacing="0" cellpadding="1" '
                       f'style="border-collapse:collapse; font-size:{b.font_pt}pt; border-color:#444;">'
                       f'<thead>{_rows_html(b.head, pct, "th")}</thead>'
                       f'<tbody>{_rows_html(b.body, pct, "td")}</tbody></table>')
    return (f'<html><body style="font-family:\'{family}\'; font-size:13pt;">'
            + "".join(out) + "</body></html>")


def report_family(family: str = "") -> str:
    """The bundled Laksaman for the reports: its regular and bold faces both have Arabic digits
    (a TH Sarabun IT๙ bold face on the computer printed Thai digits in the bold cells)."""
    from PySide6.QtGui import QFontDatabase
    ok = False
    for name in ("Laksaman.ttf", "Laksaman-Bold.ttf"):
        f = Path(__file__).resolve().parent.parent / "assets" / name
        if f.exists() and QFontDatabase.addApplicationFont(str(f)) >= 0:
            ok = True
    return "Laksaman" if ok else (family or "Laksaman")


def to_pdf(rep: Report, path, family: str) -> None:
    from PySide6.QtCore import QMarginsF, QSizeF, QUrl
    from PySide6.QtGui import QFont, QPageLayout, QPageSize, QPdfWriter, QTextDocument
    writer = QPdfWriter(str(path))
    writer.setResolution(300)
    writer.setTitle(rep.title)
    writer.setCreator("ReadWanicn2027")
    orient = QPageLayout.Landscape if rep.landscape else QPageLayout.Portrait
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), orient, QMarginsF(12, 12, 10, MARGIN_BOTTOM_MM),
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


def close_tables(page) -> None:
    """A table that runs on to the next page ends here without a bottom line: draw it
    (เส้นปิดท้ายทุกแผ่น)."""
    import pymupdf
    vert, horiz = [], []
    for d in page.get_drawings():
        for it in d["items"]:
            if it[0] == "l":
                a, b = it[1], it[2]
                if abs(a.x - b.x) < 0.3 and abs(a.y - b.y) > 2:
                    vert.append((a.x, min(a.y, b.y), max(a.y, b.y)))
                elif abs(a.y - b.y) < 0.3:
                    horiz.append((min(a.x, b.x), max(a.x, b.x), a.y))
            elif it[0] == "re":
                r = it[1]
                if r.width < 1.2 and r.height > 2:
                    vert.append((r.x0, r.y0, r.y1))
                elif r.height < 1.2:
                    horiz.append((r.x0, r.x1, r.y0))
    if not vert:
        return
    clip = page.rect.height - MARGIN_BOTTOM_MM * 72 / 25.4      # Qt cuts a split row at the margin
    bottom = max(v[2] for v in vert)
    xs = [v[0] for v in vert if abs(v[2] - bottom) < 1.0]
    bottom = min(bottom, clip)
    if len(xs) < 2:
        return
    x0, x1 = min(xs), max(xs)
    if any(abs(h[2] - bottom) < 1.0 and h[0] <= x0 + 2 and h[1] >= x1 - 2 for h in horiz):
        return
    page.draw_line(pymupdf.Point(x0, bottom), pymupdf.Point(x1, bottom), color=(0.27, 0.27, 0.27), width=0.6)


def number_pages(path, footer: bool = True) -> None:
    """หน้า n/N at the foot of each page, the developer line, and the closing line of cut tables."""
    import pymupdf
    doc = pymupdf.open(str(path))
    n = doc.page_count
    f = font_file()
    for i, page in enumerate(doc):
        close_tables(page)
        r = page.rect
        kw = dict(fontsize=7.5, color=(0.35, 0.35, 0.35))
        if f:
            kw.update(fontfile=f, fontname="th")
        page.insert_text((r.width - 70, r.height - 14), f"หน้า {i + 1}/{n}", **kw)
        if footer:
            page.insert_text((34, r.height - 14), DEVELOPER_LINE, **kw)
    tmp = str(path) + ".tmp"
    doc.save(tmp, garbage=3, deflate=True)
    doc.close()
    Path(tmp).replace(path)


# -- spreadsheet ------------------------------------------------------------------------------------

XLSX_FONT = "TH SarabunPSK"
PAGE_CHARS = {False: 112.0, True: 168.0}      # column-width units across an A4 page (portrait / landscape)


def _visible_len(t: str) -> int:
    """Characters that take room on the line (Thai vowel and tone marks above/below do not)."""
    import unicodedata
    return sum(1 for ch in str(t) if not unicodedata.combining(ch) and ch not in "\u0e31\u0e34\u0e35\u0e36\u0e37"
               "\u0e38\u0e39\u0e3a\u0e47\u0e48\u0e49\u0e4a\u0e4b\u0e4c\u0e4d")


def _lines_needed(text: str, width_units: float, size: float) -> int:
    per = max(1.0, width_units * 12.0 / max(size, 6.0))       # on the safe side: TH Sarabun or a wider font
    n = 0
    for part in str(text).split("\n"):
        n += max(1, -(-_visible_len(part) // int(per)))
    return n


def to_xlsx(reports: list, path, family: str = XLSX_FONT) -> None:
    """Every report as a sheet ready to print on A4 as it is: paper, orientation, margins and
    fit-to-width set; column widths from the report's table; long names wrapped with the row
    heights to match; the table header repeated on every page; page numbers in the footer;
    the S-curve of ว124 as a picture."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.pagebreak import Break
    wb = Workbook()
    wb.remove(wb.active)
    thin = Side(style="thin", color="555555")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    horiz = {"center": "center", "right": "right"}
    for rep in reports:
        ws = wb.create_sheet(rep.title[:31])
        ps = ws.page_setup
        ps.orientation = "landscape" if rep.landscape else "portrait"
        ps.paperSize = ws.PAPERSIZE_A4
        ps.fitToWidth, ps.fitToHeight = 1, 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.print_options.horizontalCentered = True
        ws.page_margins.left = ws.page_margins.right = 0.4
        ws.page_margins.top, ws.page_margins.bottom = 0.5, 0.55
        ws.page_margins.header, ws.page_margins.footer = 0.2, 0.25
        ws.oddFooter.right.text = "หน้า &P/&N"
        ws.oddFooter.right.size = 9
        if rep.footer:
            ws.oddFooter.left.text = DEVELOPER_LINE
            ws.oddFooter.left.size = 8
        ws.sheet_view.showGridLines = False
        tables = [b for b in rep.blocks if isinstance(b, Table)]
        main = max(tables, key=lambda t: (len(t.body) + len(t.head), len(t.widths))) if tables else None
        page = PAGE_CHARS[rep.landscape]

        def cuts(t: Table) -> list:
            tot_ = sum(t.widths) or 1
            x, out = 0.0, []
            for w in t.widths:
                x += w * page * t.width_pct / 100.0 / tot_
                out.append(x)
            return out
        # one grid for the whole sheet: every table's column edges (close ones merged), so each
        # table keeps its own columns as merged cells
        marks = sorted({0.0, *[round(x, 1) for t in tables for x in cuts(t)]}) if tables else \
            [page / 6 * k for k in range(7)]
        edges = [marks[0]]
        for x in marks[1:]:
            if x - edges[-1] >= 1.5:
                edges.append(x)
            else:
                edges[-1] = max(edges[-1], x) if len(edges) > 1 else edges[-1]
        grid = [b_ - a_ for a_, b_ in zip(edges, edges[1:])] or [page]
        ncols = len(grid)
        for i, w in enumerate(grid):
            ws.column_dimensions[get_column_letter(i + 1)].width = round(w, 2)

        def spans(t: Table) -> list:
            """Grid columns of each column of table t."""
            out, prev = [], 0
            for x in cuts(t):
                end = min(range(len(edges)), key=lambda k: abs(edges[k] - x))
                end = min(max(end, prev + 1), ncols)
                out.append((min(prev, ncols - 1), end - 1))
                prev = end
            return out

        def width_of(c0, c1):
            return sum(grid[c0:c1 + 1])

        r = 1
        for blk in rep.blocks:
            if blk == "pagebreak":
                ws.row_breaks.append(Break(id=r - 1))
                continue
            if isinstance(blk, Para):
                c = ws.cell(r, 1, blk.text if blk.text.strip() else None)
                size = blk.size + 2
                c.font = Font(name=family, size=size, bold=blk.bold)
                c.alignment = Alignment(horizontal=horiz.get(blk.align, "left"), vertical="center", wrap_text=True)
                if ncols > 1:
                    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
                n = _lines_needed(blk.text, width_of(0, ncols - 1), size) if blk.text.strip() else 1
                ws.row_dimensions[r].height = max(8, size * 1.45 * n) if blk.text.strip() else 6
                r += 1
                continue
            if isinstance(blk, Chart):
                try:
                    import tempfile

                    from openpyxl.drawing.image import Image as XImage
                    tmp = Path(tempfile.mkdtemp()) / f"{blk.name}"
                    blk.image.save(str(tmp))
                    img = XImage(str(tmp))
                    scale = width_of(0, ncols - 1) * 7.0 * blk.width_pct / 100.0 / img.width
                    img.width, img.height = img.width * scale, img.height * scale
                    ws.add_image(img, f"{get_column_letter(max(1, int(ncols * (1 - blk.width_pct / 100) / 2)))}{r}")
                    rows_ = int(img.height / 20) + 1
                    for k_ in range(rows_):
                        ws.row_dimensions[r + k_].height = 15
                    r += rows_ + 1
                except Exception:                  # no picture support: leave the space
                    r += 1
                continue
            sp = spans(blk)
            size = blk.font_pt + 3
            first = r
            taken = set()
            for kind, rows in (("head", blk.head), ("body", blk.body)):
                for row in rows:
                    col, need = 0, 1
                    for cell in row:
                        while (r, col) in taken:
                            col += 1
                        if col >= len(sp):
                            break
                        last = min(len(sp) - 1, col + cell.colspan - 1)
                        g0, g1 = sp[col][0], sp[last][1]
                        v = cell.value if cell.value is not None else (cell.text or None)
                        if isinstance(v, str) and cell.indent:
                            v = "   " * cell.indent + v
                        c = ws.cell(r, g0 + 1, v)
                        csize = (cell.size or blk.font_pt) + 3
                        c.font = Font(name=family, size=csize, bold=cell.bold or kind == "head")
                        is_num = isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool)
                        c.alignment = Alignment(horizontal=horiz.get(cell.align, "left"), vertical="center",
                                                wrap_text=not is_num, shrink_to_fit=is_num)
                        if is_num:
                            c.number_format = "#,##0" if cell.digits == 0 else "#,##0." + "0" * cell.digits
                        bg = cell.bg or (SHADE if kind == "head" and blk.border else "")
                        if bg:
                            c.fill = PatternFill("solid", fgColor=bg.lstrip("#"))
                        rspan = max(1, cell.rowspan)
                        if g1 > g0 or rspan > 1:
                            ws.merge_cells(start_row=r, start_column=g0 + 1, end_row=r + rspan - 1, end_column=g1 + 1)
                        for rr in range(r, r + rspan):
                            for cc in range(col, last + 1):
                                taken.add((rr, cc))
                            if blk.border:
                                for gc in range(g0, g1 + 1):
                                    ws.cell(rr, gc + 1).border = box
                        if not is_num and cell.text and rspan == 1:
                            need = max(need, _lines_needed(cell.text, width_of(g0, g1), csize))
                        col = last + 1
                    ws.row_dimensions[r].height = max(14, size * 1.5 * need)
                    r += 1
            if blk is main and blk.head:
                ws.print_title_rows = f"{first}:{first + len(blk.head) - 1}"
            r += 1
    wb.save(str(path))


# -- CSV ------------------------------------------------------------------------------------------

def _csv_rows(rep: Report) -> list:
    out = []
    for b in rep.blocks:
        if isinstance(b, Para):
            if b.text.strip():
                out.append([b.text])
        elif isinstance(b, Table):
            n = len(b.widths)
            for kind, rows in (("head", b.head), ("body", b.body)):
                taken = set()
                for r, row in enumerate(rows):
                    line, col = [""] * n, 0
                    for c in row:
                        while (r, col) in taken:
                            col += 1
                        if col >= n:
                            break
                        t = c.text
                        if c.value is not None and isinstance(c.value, (int, float)):
                            t = t.replace(",", "")           # numbers stay numbers for editing
                        elif c.indent:
                            t = "  " * c.indent + t
                        line[col] = t
                        for rr in range(r, r + c.rowspan):
                            for cc in range(col, col + c.colspan):
                                taken.add((rr, cc))
                        col += c.colspan
                    out.append(line)
            out.append([])
    return out


def to_csv(reports: list, path) -> list:
    """One .csv per part (UTF-8 with BOM so the spreadsheet program reads Thai)."""
    import csv
    path = Path(path)
    written = []
    for rep in reports:
        f = path if len(reports) == 1 else path.with_name(f"{path.stem} - {rep.title}.csv")
        with open(f, "w", newline="", encoding="utf-8-sig") as fh:
            csv.writer(fh).writerows(_csv_rows(rep))
        written.append(f)
    return written


def write_csv(kind: str, p: P.Project, csv_path) -> list:
    return to_csv(REPORTS[kind](p), csv_path)


def write_sheet(kind: str, p: P.Project, path) -> list:
    """The report as a spreadsheet ready to print on A4 (.xlsx), or as plain CSV for a .csv path."""
    if str(path).lower().endswith(".csv"):
        return write_csv(kind, p, path)
    to_xlsx(REPORTS[kind](p), path)
    return [Path(path)]


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

GREY = "#d9d9d9"
MARGIN_BOTTOM_MM = 12


def _bill_events(rows, totals: bool):
    """('head'|'line', index) for each row, and ('total', header index) after each group of
    level 1–2 closes (the «รวม …» lines of the building examples in ว651)."""
    out, open_ = [], []
    for i, r in enumerate(rows):
        lvl = r.item.level
        if totals and r.item.code:
            while open_ and rows[open_[-1]].item.level >= lvl:
                out.append(("total", open_.pop()))
        out.append(("head" if r.item.header else "line", i))
        if totals and r.item.header and lvl <= 2 and r.item.code:
            open_.append(i)
    while totals and open_:
        out.append(("total", open_.pop()))
    return out


def _group_name(it: P.Item) -> str:
    name = it.label
    if it.code and name.startswith(it.code):
        name = name[len(it.code):].lstrip(". ")
    return name


def adjust_note(res) -> str:
    """Which line took the satang the even spread left over (แรเงาสีเทาในตาราง)."""
    if res.adjust_row < 0:
        return "การปรับลดลงตัวทุกรายการ ไม่มีส่วนต่างที่ต้องปรับ"
    r = res.rows[res.adjust_row]
    k = sum(1 for x in res.rows[:res.adjust_row + 1] if not x.item.header)
    no = P.arabic(r.item.no or r.item.code) or str(k)
    way = "เพิ่ม" if r.adjusted > 0 else "ลด"
    return (f"ส่วนต่างที่เกลี่ยไม่ลงตัว {abs(r.adjusted):,.2f} บาท ปรับ{way}ในลำดับที่ {no} "
            f"«{P.arabic(r.item.label)}» (แรเงาสีเทา)")


def report_651(p: P.Project) -> list:
    """สิ่งที่ส่งมาด้วย 1 (แบบสรุปราคากลาง with every line reduced) and สิ่งที่ส่งมาด้วย 2
    (เอกสารแนบท้ายสัญญา), laid out as the examples of ว651 for the chosen kind of work."""
    res = P.compute_651(p)
    red = res.red
    south = res.uplift > 1.0
    work = _work_name(p)
    qty_word = p.work[1]
    building = p.work_type in ("building", "building_south")
    title = P.arabic(p.title) or "..........................."
    head_line = f"โครงการ{work} {title}"
    if p.budget:
        head_line += f"  งบประมาณ {p.budget:,.2f} บาท"
    if p.project_no:
        head_line += f"  เลขที่โครงการ {p.project_no}"

    a = Report("ว651 สรุปราคากลาง", footer=False)
    a.p(f"แบบสรุปราคากลาง{work}", align="center", bold=True, size=14)
    if south:
        a.p(P.SOUTH_NOTE, align="center", size=11)
    a.p(head_line, align="center", size=11)
    # ตาราง : สรุปราคากลางโครงการ
    a.p(f"ตาราง : สรุปราคากลางโครงการ{work}", size=11)
    head = [[C("ลำดับที่", align="center"), C("รายการ", align="center"), C("หน่วย", align="center"),
             C("ค่างานต้นทุน", align="center"), C("Factor F / Vat", align="center"), C("ราคากลาง", align="center")]
            + ([C("ราคากลาง\nบวกเพิ่มร้อยละ 5", align="center")] if south else [])]
    names = [f"{work} (ค่าวัสดุและค่าแรง)" if building else work, "งานครุภัณฑ์จัดซื้อ (ถ้ามี)",
             "ค่าใช้จ่ายพิเศษตามข้อกำหนด (ถ้ามี)"]
    body = []
    for i, (g, nm) in enumerate(zip(res.groups, names)):
        _n, cost, fac, mid, mid_up, _red = g
        body.append([C(i + 1, align="center"), C(nm), C("บาท", align="center"), N(cost), Q(fac, 4, align="right"),
                     N(mid)] + ([N(mid_up)] if south else []))
    body.append([C("", colspan=4 if not south else 4), C("รวม", align="right"), N(res.mid_total, bold=True, bg=GREY)]
                + ([N(res.mid_up_total, bold=True, bg=GREY)] if south else []))
    a.blocks.append(Table(head, body, [9, 40, 8, 16, 12, 16] + ([17] if south else []), 9.5,
                          width_pct=90 if south else 82))
    a.p("ตาราง : ราคาตามคำเสนอของผู้ชนะการจัดซื้อจัดจ้าง", size=11)
    a.blocks.append(Table([[C("ลำดับที่", align="center"), C("รายการ", align="center"), C("หน่วย", align="center"),
                            C("ราคาที่เสนอ", align="center")]],
                          [[C(1, align="center"), C("ราคาตามคำเสนอของผู้ชนะการจัดซื้อจัดจ้าง"),
                            C("บาท", align="center"), N(p.offer, bg=GREY)]], [9, 52, 9, 20], 9.5, width_pct=62))
    a.p(" ", size=4)
    sp = P.r2(P.special_total(p) * res.uplift)
    mid_label = "ราคากลางบวกเพิ่มร้อยละ 5" if south else "ราคากลาง"
    mid_val = P.r2(p.mid_price * res.uplift)
    a.blocks.append(Table([], [
        [C("วิธีการคำนวณราคากลางหักค่าใช้จ่ายพิเศษตามข้อกำหนด", bold=True), C(""), C(""),
         C("วิธีการคำนวณราคาตามคำเสนอ ฯ หักค่าใช้จ่ายพิเศษตามข้อกำหนด", bold=True), C("")],
        [C(mid_label), N(mid_val), C(""), C("ราคาที่เสนอของผู้ชนะการจัดซื้อจัดจ้าง"), N(p.offer)],
        [C("หัก ค่าใช้จ่ายพิเศษตามข้อกำหนด"), N(sp), C(""), C("หัก ค่าใช้จ่ายพิเศษตามข้อกำหนด"), N(sp)],
        [C("ผลต่างระหว่างราคากลางหักค่าใช้จ่ายพิเศษตามข้อกำหนด"), N(red.mid_net, bg=GREY), C(""),
         C("ผลต่างระหว่างราคาตามคำเสนอ ฯ หักค่าใช้จ่ายพิเศษตามข้อกำหนด"), N(red.offer_net, bg=GREY)]],
        [33, 14, 4, 35, 14], 8.5, border=0))
    a.p(" ", size=4)
    a.p("ผลต่างระหว่างราคากลางกับราคาตามคำเสนอ ฯ หักค่าใช้จ่ายพิเศษตามข้อกำหนด", bold=True, size=9.5)
    a.blocks.append(Table([], [
        [C("ผลต่างระหว่างราคากลางหักค่าใช้จ่ายพิเศษตามข้อกำหนด"), N(red.mid_net), C("(1)", align="center"),
         C(""), C(""), C("")],
        [C("หัก ผลต่างระหว่างราคาที่เสนอ ฯ หักค่าใช้จ่ายพิเศษตามข้อกำหนด"), N(red.offer_net), C("(2)", align="center"),
         C(""), C("ผลต่างตาม (3) เทียบกับราคากลางหักค่าใช้จ่ายพิเศษตามข้อกำหนด (1)", align="right", bg=GREY),
         C("", bg=GREY)],
        [C("ผลต่างระหว่างราคากลางกับราคาตามคำเสนอ ฯ หักค่าใช้จ่ายพิเศษตามข้อกำหนด"), N(red.diff, bg=GREY),
         C("(3)", align="center"), C(""), C("คิดเป็นร้อยละ", align="right", bg=GREY),
         Q(red.pct_down, 2, bold=True, bg=GREY, align="center")]],
        [33, 13, 5, 3, 37, 9], 8.5, border=0))
    a.p(" ", size=4)
    # รายการ
    mid_cols = [C("ค่างานต้นทุน", align="center"), C("Factor F / Vat", align="center"), C("ราคากลาง", align="center")]
    if south:
        mid_cols.append(C("ราคากลาง\nบวกเพิ่มร้อยละ 5", align="center"))
    head = [[C("ลำดับที่", align="center", rowspan=2), C("รายการ", align="center", rowspan=2),
             C("หน่วย", align="center", rowspan=2), C(qty_word, align="center", rowspan=2),
             C("ราคากลางงานก่อสร้าง (บาท)", align="center", colspan=len(mid_cols)),
             C("ราคาที่ปรับลดตามคำเสนอ (บาท)", align="center", colspan=2)],
            mid_cols + [C("ราคาที่ปรับลด", align="center"), C("ราคาต่อหน่วย", align="center")]]
    sub = {k: P.subtotals(res.rows, k) for k in ("cost", "mid", "mid_up", "reduced")}
    body = []
    for kind, i in _bill_events(res.rows, building):
        r = res.rows[i]
        it = r.item
        if kind == "head":
            row = [C(it.no or it.code, align="center"), _name_cell(it), C(""), C("")]
            if building:
                row += [C("")] * (len(mid_cols) + 2)
            else:
                row += [C(""), C(""), N(sub["mid"].get(i))] + ([N(sub["mid_up"].get(i))] if south else []) \
                    + [N(sub["reduced"].get(i)), C("")]
        elif kind == "line":
            adj = i == res.adjust_row
            row = [C(it.no or "", align="center", bg=GREY if adj else ""),
                   C(it.label + (" (*)" if adj else ""), indent=max(0, it.level - 1), bg=GREY if adj else ""),
                   C(it.unit, align="center"), Q(it.qty), N(r.cost), Q(r.factor, 4, align="center"), N(r.mid)]
            if south:
                row.append(N(r.mid_up))
            row += [N(r.reduced, bg=GREY if adj else "", bold=adj), N(r.unit_price, bg=GREY if adj else "")]
        else:
            name = f"รวม {_group_name(it)}" if it.level == 1 else f"รวม{_group_name(it)}"
            row = [C(""), C(name, bold=True, align="right" if it.level == 1 else "left",
                            indent=max(0, it.level - 1)), C(""), C(""),
                   N(sub["cost"].get(i), bold=True), C(""), N(sub["mid"].get(i), bold=True)]
            if south:
                row.append(N(sub["mid_up"].get(i), bold=True))
            row += [N(sub["reduced"].get(i), bold=True), C("")]
        body.append(row)
    ncol = 4 + len(mid_cols)
    body.append([C("วงเงินรวม", align="right", colspan=ncol - 1)]
                + [N(res.mid_up_total if south else res.mid_total)]
                + [N(res.reduced_total, bold=True, bg=GREY), C("(*)", align="left")])
    a.blocks.append(Table(head, body, [5, 33, 6, 8, 12.5, 7, 12.5] + ([13] if south else []) + [14, 11], 8.5))
    a.p("หมายเหตุ  (*) ส่วนต่างนี้ให้ปรับเพิ่ม/ลด ในรายการใดรายการหนึ่งได้ตามความเหมาะสม ยกเว้น "
        "รายการค่าใช้จ่ายพิเศษตามข้อกำหนด\n             ทั้งนี้ วงเงินรวมของการปรับลดราคาจะต้องเท่ากับ"
        "ราคาตามคำเสนอของผู้ชนะการจัดซื้อจัดจ้าง", size=9.5)
    a.p("             " + adjust_note(res), size=9.5, bold=True)

    # สิ่งที่ส่งมาด้วย 2: เอกสารแนบท้ายสัญญา
    b = Report("ว651 แนบท้ายสัญญา", footer=False)
    b.p("แบบแสดงรายการ ปริมาณงาน และราคา", align="center", bold=True, size=13)
    b.p(f"เอกสารแนบท้ายสัญญาจ้างก่อสร้าง : {work}", align="center", bold=True, size=12)
    if south:
        b.p(P.SOUTH_NOTE, align="center", size=11)
    b.p(f"เลขที่ {P.arabic(p.contract_no) or '................'}  ลงวันที่ "
        f"{P.thai_date(p.contract_date) or '................'}", align="center", size=12)
    b.p(head_line, align="center", size=11.5)
    info = [("หน่วยงานเจ้าของโครงการ", P.arabic(p.agency)),
            ("วงเงินงบประมาณ", f"{p.budget:,.2f}  บาท" if p.budget else ""),
            ("ราคากลางงานก่อสร้าง", f"{(res.mid_up_total if south else res.mid_total):,.2f}  บาท"),
            ("วงเงินตามสัญญา", f"{p.offer:,.2f}  บาท"),
            ("ชื่อผู้รับจ้าง", P.arabic(p.contractor))]
    b.blocks.append(Table([], [[C(k), C(v)] for k, v in info], [32, 68], 10.5, border=0, width_pct=70))
    b.p(" ", size=4)
    head = [[C("ลำดับที่", align="center", rowspan=2), C("รายการ", align="center", rowspan=2),
             C("หน่วย", align="center", rowspan=2), C(qty_word, align="center", rowspan=2),
             C("ราคาที่ปรับลดตามคำเสนอ (บาท)", align="center", colspan=2)],
            [C("ราคา" if building else "ราคาที่ปรับลด", align="center"), C("ราคาต่อหน่วย", align="center")]]
    body = []
    for kind, i in _bill_events(res.rows, building):
        r = res.rows[i]
        it = r.item
        if kind == "head":
            body.append([C(it.no or it.code, align="center"), _name_cell(it), C(""), C(""),
                         C("") if building else N(sub["reduced"].get(i)), C("")])
        elif kind == "line":
            body.append([C(it.no or "", align="center"), C(it.label, indent=max(0, it.level - 1)),
                         C(it.unit, align="center"), Q(it.qty), N(r.reduced), N(r.unit_price)])
        else:
            name = f"รวม {_group_name(it)}" if it.level == 1 else f"รวม{_group_name(it)}"
            body.append([C(""), C(name, bold=True, align="right" if it.level == 1 else "left",
                                  indent=max(0, it.level - 1)), C(""), C(""),
                         N(sub["reduced"].get(i), bold=True), C("")])
    body.append([C("วงเงินตามสัญญา", align="right", colspan=4), N(res.reduced_total, bold=True, bg=GREY), C("")])
    b.blocks.append(Table(head, body, [7, 55, 8, 10, 12, 10], 9))
    return [a, b]


# -- ว124 -------------------------------------------------------------------------------------------

def s_curve(plan: "P.Plan124", w=1800, h=760):
    """% ACC PLAN and % ACC ACTUAL (as the ว124 example) with the thresholds, as a picture."""
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
        g.drawText(QRectF(x - 70, T + ph + 8, 140, 30), Qt.AlignCenter,
                   plan.labels[m] if plan.labels else f"เดือน {m + 1}")
    g.setPen(QPen(QColor("#333333"), 2))
    g.drawLine(L, T + ph, L + pw, T + ph)
    g.drawLine(L, T, L, T + ph)
    # second line: % ACC ACTUAL — the months reported, then the estimate that the work ends as
    # planned (dashed) all the way to the last month
    fc = plan.forecast or plan.acc_plan
    apts = [QPointF(L, T + ph)] + [QPointF(x, T + ph - ph * min(100, v) / 100) for x, v in zip(xs, fc)]
    for k_, (a_, b_) in enumerate(zip(apts, apts[1:])):
        g.setPen(QPen(QColor("#f4a261"), 10, Qt.SolidLine, Qt.RoundCap))
        if k_ <= plan.last_actual:
            g.setPen(QPen(QColor("#c55a11"), 5))
        g.drawLine(a_, b_)
    g.setBrush(QColor("#c55a11"))
    g.setPen(QColor("#c55a11"))
    for k_, (p_, v) in enumerate(zip(apts[1:], fc)):
        g.drawEllipse(p_, 7, 7)
        if k_ <= plan.last_actual or abs(v - plan.acc_plan[k_]) > 0.5:
            g.drawText(QRectF(p_.x() - 70, p_.y() + 8, 140, 28), Qt.AlignCenter, f"{v:.2f}%")
    # legend
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
        g.drawText(QRectF(min(x - 140, L + pw - 200), y + 4, 200 if x - 140 > L + pw - 200 else 280, 26),
                   Qt.AlignCenter, f"ขั้นต่ำ {need:.0f}%")
    del tot
    g.setPen(QColor("#1f4e79"))
    act_name = "% ACC ACTUAL (ผลงานจริง + คาดการณ์ตามแผน)" if plan.last_actual >= 0 \
        else "% ACC ACTUAL (คาดการณ์ว่าเสร็จตามแผน)"
    for k_, (col, name) in enumerate((("#1f4e79", "% ACC PLAN (แผนสะสม)"), ("#f4a261", act_name))):
        x0 = L + pw / 2 - 560 + k_ * 520
        g.setPen(QPen(QColor(col), 5))
        g.drawLine(QPointF(x0, 26), QPointF(x0 + 50, 26))
        g.setPen(QColor("#222222"))
        g.drawText(QRectF(x0 + 60, 8, 520, 36), Qt.AlignLeft | Qt.AlignVCenter, name)
    g.end()
    return img


def report_124(p: P.Project) -> list:
    plan = P.compute_124(p)
    n = plan.months
    rep = Report("ว124 แผนการทำงาน", landscape=True)
    rep.p("แผนการทำงาน", align="center", bold=True, size=15)
    rep.p(_project_line(p), align="center", size=11.5)
    rep.p(f"ระยะเวลาก่อสร้างตามแผนดำเนินงานทั้งสัญญา {n} เดือน ({sum(plan.days)} วัน)"
          + (f" เริ่ม {P.thai_date(p.start)}" if p.start else ""), align="center", size=11.5)
    fs = 9.0 if n <= 8 else 8.0 if n <= 12 else 6.5
    head = [[C("ที่", align="center", rowspan=2), C("รายการ", align="center", rowspan=2),
             C("หน่วย", align="center", rowspan=2), C("ปริมาณงาน", align="center", rowspan=2),
             C("ราคาต่อหน่วย", align="center", rowspan=2), C("เป็นเงิน", align="center", rowspan=2),
             C("%", align="center", rowspan=2)] + [C(f"เดือนที่ {m + 1}", align="center") for m in range(n)],
            [C(plan.labels[m] if plan.labels else f"{d} วัน", align="center", bold=True, bg="#fff2cc")
             for m, d in enumerate(plan.days)]]
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
        small = fs - (1.5 if n > 6 else 0.5)          # the baht of a month fits its column on one line
        return [C(name, align="right", bold=True, colspan=7)] + [
            (Q(v, 0, bold=bold, size=small) if money_ else Q(v, 2, bold=bold)) if v is not None else C("")
            for v in vals]
    half = [v / 2 for v in plan.pct_plan]
    half_diff = [(a_ - h) if a_ is not None else None for a_, h in zip(plan.actual, half)]
    body += [line("Money", plan.money, True), line("AccMoney", plan.acc_money, True),
             line("% PLAN", plan.pct_plan), line("% ACC PLAN", plan.acc_plan, bold=True),
             line("% ACTUAL", plan.actual), line("% ACC ACTUAL", plan.acc_actual, bold=True),
             line("% ACC DIFF", plan.diff), line("% PLAN/2", half), line("% PLAN/2 DIFF", half_diff)]
    widths = [3, 21, 4.5, 6, 7, 9.5, 5] + [max(4.5, 54.0 / n)] * n
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
    _sign(rep, "คู่สัญญาฝ่ายผู้รับจ้าง", p.signer or p.contractor)
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
    """ลงชื่อ / (ชื่อ) / ตำแหน่ง centred one under the other in the right half of the page."""
    rep.p(" ", size=8)
    line = "." * 52
    rows = [[C(""), C(f"ลงชื่อ {line}", align="center")],
            [C(""), C(f"({P.arabic(name) or line})", align="center")],
            [C(""), C(role, align="center")]]
    rep.blocks.append(Table([], rows, [45, 55], 12, border=0))


# -- แผนปฏิบัติงาน (Bar Chart) ----------------------------------------------------------------------

BAR = "#2e75b6"


def bar_halves(plan: list) -> list:
    """Which half-months a line works in, from its per-cent per month: the first month of a line
    that starts late takes only its second half, the last month of one that ends early only its
    first half (a month counts as full at ¾ of the line's average month)."""
    on = [m for m, v in enumerate(plan) if v > 0]
    halves = [False] * (2 * len(plan))
    if not on:
        return halves
    full = 100.0 / len(on)
    for m in on:
        halves[2 * m] = halves[2 * m + 1] = True
    if len(on) > 1:
        if plan[on[0]] < 0.75 * full:
            halves[2 * on[0]] = False
        if plan[on[-1]] < 0.75 * full:
            halves[2 * on[-1] + 1] = False
    return halves


def report_work(p: P.Project) -> list:
    """แผนปฏิบัติงาน: every line of the bill as a bar over the half-months it works in, with its
    start and end dates and days, from the same plan as ว124 (so the work and the money agree)."""
    import datetime as dt
    plan = P.compute_124(p)
    n = plan.months
    rep = Report("แผนปฏิบัติงาน", landscape=True)
    rep.p("แผนปฏิบัติงาน (Bar Chart)", align="center", bold=True, size=15)
    rep.p(_project_line(p), align="center", size=11.5)
    start = P.iso_date(p.start)
    days_total = sum(plan.days)
    rep.p(f"ระยะเวลาก่อสร้าง {days_total} วัน ({n} เดือน)"
          + (f"  เริ่ม {P.thai_date(p.start)}  สิ้นสุด "
             f"{P.thai_date((start + dt.timedelta(days=days_total - 1)).isoformat())}" if start else ""),
          align="center", size=11.5)
    cum = [0]
    for d in plan.days:
        cum.append(cum[-1] + d)
    head = [[C("ที่", align="center", rowspan=2), C("รายการ", align="center", rowspan=2),
             C("ปริมาณ", align="center", rowspan=2), C("หน่วย", align="center", rowspan=2),
             C("เริ่ม", align="center", rowspan=2), C("สิ้นสุด", align="center", rowspan=2),
             C("วัน", align="center", rowspan=2)]
            + [C(f"เดือนที่ {m + 1}", align="center", colspan=2) for m in range(n)],
            [C(plan.labels[m] if plan.labels else f"{plan.days[m]} วัน", align="center", colspan=2, bold=True,
               bg="#fff2cc") for m in range(n)]]
    lines = {id(it): pl for it, _a, _pc, pl in plan.lines}
    res = P.compute_651(p)
    body, k = [], 0
    fs = 8.5 if n <= 8 else 7.5 if n <= 12 else 6.5

    def day_of(half):                      # first day (0-based) of a half-month
        m, h = divmod(half, 2)
        return cum[m] + (plan.days[m] // 2 if h else 0)

    def date(d):
        if not start:
            return f"วันที่ {d + 1}"
        x = start + dt.timedelta(days=d)
        return f"{x.day} {P.THAI_MONTHS_SHORT[x.month - 1]} {str(x.year + 543)[2:]}"
    for r in res.rows:
        it = r.item
        if it.header:
            body.append([C(""), _name_cell(it), C(""), C(""), C(""), C(""), C("")]
                        + [C("") for _h in range(2 * n)])
            continue
        k += 1
        halves = bar_halves(lines[id(it)])
        on = [h for h, v in enumerate(halves) if v]
        if on:
            d0, d1 = day_of(on[0]), day_of(on[-1] + 1) - 1 if on[-1] + 1 < 2 * n else days_total - 1
            when = [C(date(d0), align="center"), C(date(d1), align="center"), C(d1 - d0 + 1, align="center")]
        else:
            when = [C(""), C(""), C("")]
        body.append([C(k, align="center"), C(it.label, indent=max(0, it.level - 1)), Q(it.qty),
                     C(it.unit, align="center")] + when
                    + [C("", bg=BAR if v else "") for v in halves])
    acc = [C("แผนงานสะสม (%)", align="right", bold=True, colspan=7)] + [
        Q(v, 2, bold=True, align="center", colspan=2) for v in plan.acc_plan]
    body.append(acc)
    rep.blocks.append(Table(head, body, [3, 27, 6, 4.5, 6.5, 6.5, 3.5] + [max(2.2, 44.0 / (2 * n))] * (2 * n), fs))
    rep.p("หมายเหตุ  แถบสีน้ำเงิน คือ ช่วงเวลาทำงานของแต่ละรายการ (ช่องละครึ่งเดือน) จัดลำดับก่อน–หลังตามขั้นตอนการก่อสร้าง "
          "และสอดคล้องกับแผนการทำงาน ว124 (มูลค่างานทุกเดือน)", size=10)
    _sign(rep, "ผู้รับจ้าง", p.signer or p.contractor)
    return [rep]


REPORTS = {"651": report_651, "124": report_124, "78": report_78, "work": report_work}


def write(kind: str, p: P.Project, pdf_path, family: str, xlsx: bool = True) -> list:
    """Write the reports of `kind` (651 / 124 / 78): one PDF (parts merged) and one .xlsx.
    Returns the paths written."""
    reps = REPORTS[kind](p)
    family = report_family(family)
    pdf_path = Path(pdf_path)
    written = []
    footer = all(r.footer for r in reps)
    if len(reps) == 1:
        to_pdf(reps[0], pdf_path, family)
        number_pages(pdf_path, footer)
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
        number_pages(pdf_path, footer)
    written.append(pdf_path)
    if xlsx:
        xp = pdf_path.with_suffix(".xlsx")
        to_xlsx(reps, xp)
        written.append(xp)
    return written
