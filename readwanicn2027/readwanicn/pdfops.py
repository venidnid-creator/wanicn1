# SPDX-License-Identifier: GPL-3.0-or-later
"""PDF work, headless: combine, compress at three qualities, delete and
rotate pages, and the text and tables of a PDF out to Excel, CSV and Word.
Built on PyMuPDF; never writes over the source file unless asked to."""
from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass
from pathlib import Path

import pymupdf

#: (label, image resolution dpi, JPEG quality) of each compression level.
QUALITIES = {
    "high": ("คุณภาพสูง (ไฟล์เล็กลงเล็กน้อย ภาพคมชัด)", 200, 85),
    "medium": ("คุณภาพกลาง (สมดุล เหมาะส่งอีเมล)", 150, 70),
    "low": ("คุณภาพต่ำ (ไฟล์เล็กที่สุด สำหรับดูบนจอ)", 96, 50),
}


@dataclass
class CompressResult:
    before: int
    after: int

    @property
    def saved_percent(self) -> float:
        return 0.0 if self.before <= 0 else (1.0 - self.after / self.before) * 100.0


def combine(paths: list, out_path) -> int:
    """Every page of ``paths`` in order into ``out_path``; returns the page count."""
    if not paths:
        raise ValueError("ยังไม่ได้เลือกไฟล์ที่จะรวม")
    out = pymupdf.open()
    for path in paths:
        with pymupdf.open(path) as src:
            out.insert_pdf(src)
    out.save(out_path, garbage=3, deflate=True)
    count = out.page_count
    out.close()
    return count


def compress(path, out_path, level: str = "medium") -> CompressResult:
    """Images downsampled to the level's resolution and re-encoded at its
    JPEG quality, fonts subset, unused objects dropped, streams deflated."""
    if level not in QUALITIES:
        raise ValueError(f"ระดับการบีบอัดไม่ถูกต้อง: {level}")
    _label, dpi, quality = QUALITIES[level]
    before = os.path.getsize(path)
    doc = pymupdf.open(path)
    try:
        doc.rewrite_images(dpi_threshold=dpi + 10, dpi_target=dpi, quality=quality)
    except Exception:          # a PDF without images, or an image MuPDF cannot re-encode
        pass
    try:
        doc.subset_fonts()
    except Exception:
        pass
    doc.save(out_path, garbage=4, deflate=True, deflate_images=True, deflate_fonts=True,
             clean=True, use_objstms=1)
    doc.close()
    after = os.path.getsize(out_path)
    if after > before:         # never hand back a bigger file
        Path(out_path).write_bytes(Path(path).read_bytes())
        after = before
    return CompressResult(before, after)


def delete_pages(doc: "pymupdf.Document", pages: list) -> None:
    for p in sorted(set(pages), reverse=True):
        doc.delete_page(p)


def rotate_page(doc: "pymupdf.Document", page: int, degrees: int = 90) -> None:
    pg = doc[page]
    pg.set_rotation((pg.rotation + degrees) % 360)


# -- exports --------------------------------------------------------------------------

def page_tables(doc, page_no: int) -> list:
    """The tables MuPDF finds on a page, each a list of rows of strings."""
    out = []
    try:
        found = doc[page_no].find_tables()
        for table in found.tables:
            rows = [[("" if c is None else str(c)) for c in row] for row in table.extract()]
            if rows:
                out.append(rows)
    except Exception:
        pass
    return out


def page_lines(doc, page_no: int) -> list:
    return [line for line in doc[page_no].get_text("text").splitlines() if line.strip()]


def export_excel(doc, out_path, title: str = "") -> int:
    """Each page's tables (or, without tables, its text lines) on a sheet
    of its own; returns the number of rows written."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    wb.remove(wb.active)
    rows_written = 0
    head = PatternFill("solid", fgColor="0F2A44")
    for p in range(doc.page_count):
        ws = wb.create_sheet(f"หน้า {p + 1}")
        ws.append([f"{title} — หน้า {p + 1}"])
        ws["A1"].font = Font(bold=True, size=13)
        tables = page_tables(doc, p)
        if tables:
            for k, table in enumerate(tables):
                ws.append([])
                ws.append([f"ตารางที่ {k + 1}"])
                for r, row in enumerate(table):
                    ws.append(row)
                    rows_written += 1
                    if r == 0:
                        for cell in ws[ws.max_row]:
                            cell.font = Font(bold=True, color="FFFFFF")
                            cell.fill = head
        else:
            ws.append([])
            for line in page_lines(doc, p):
                ws.append([line])
                rows_written += 1
        for col in ws.columns:
            width = max((len(str(c.value)) for c in col if c.value is not None), default=8)
            ws.column_dimensions[col[0].column_letter].width = min(60, max(10, width + 2))
            for c in col:
                c.alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(out_path)
    return rows_written


def export_csv(doc, out_path) -> int:
    """All pages into one CSV (UTF-8 with BOM, so Excel shows Thai):
    page, table/line number and the cells."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["หน้า", "ตาราง", "แถว", "ข้อมูล"])
    n = 0
    for p in range(doc.page_count):
        tables = page_tables(doc, p)
        if tables:
            for k, table in enumerate(tables):
                for r, row in enumerate(table):
                    w.writerow([p + 1, k + 1, r + 1] + row)
                    n += 1
        else:
            for r, line in enumerate(page_lines(doc, p)):
                w.writerow([p + 1, "", r + 1, line])
                n += 1
    Path(out_path).write_text(buf.getvalue(), encoding="utf-8-sig")
    return n


def export_word(doc, out_path, title: str = "") -> int:
    """A .docx with each page's text under its heading and its tables as
    Word tables; returns the number of pages written."""
    from docx import Document
    from docx.shared import Pt

    d = Document()
    style = d.styles["Normal"]
    style.font.name = "TH Sarabun New"
    style.font.size = Pt(14)
    d.add_heading(title or "เอกสาร PDF", level=0)
    for p in range(doc.page_count):
        d.add_heading(f"หน้า {p + 1}", level=1)
        tables = page_tables(doc, p)
        for table in tables:
            cols = max(len(r) for r in table)
            t = d.add_table(rows=0, cols=cols)
            t.style = "Table Grid"
            for row in table:
                cells = t.add_row().cells
                for i, v in enumerate(row):
                    cells[i].text = v
            d.add_paragraph()
        if not tables:
            for line in page_lines(doc, p):
                d.add_paragraph(line)
    d.save(out_path)
    return doc.page_count
