# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ฉ2 PDFIMPORT: a vector PDF page (a drawing printed to PDF by any CAD) as
real DXF entities — lines, polylines, curves (as fine polylines), filled
areas' outlines and the text — that can be edited, measured and snapped to.

The page's points (1/72 inch) become millimetres of paper times the drawing
scale: a 1:100 plan printed to PDF comes back in real millimetres (or
metres). A scanned PDF (a picture only) has no lines to read: say so, and
PDFATTACH (the raster way) is the tool for it.

PyMuPDF reads the page (``page.get_drawings()`` / ``get_text("dict")``).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

PT_MM = 25.4 / 72.0
#: drawing scales offered (1:n)
SCALES = (1, 20, 25, 50, 100, 200, 250, 500, 1000, 2000)


@dataclass
class Result:
    path: str
    page: int
    lines: int = 0
    polylines: int = 0
    texts: int = 0
    fills: int = 0
    raster_only: bool = False
    size: tuple = (0.0, 0.0)            # the page in drawing units
    notes: list = field(default_factory=list)


def page_count(pdf_path: str) -> int:
    import pymupdf
    with pymupdf.open(pdf_path) as doc:
        return doc.page_count


def _rgb(c):
    if not c:
        return None
    return tuple(max(0, min(255, int(round(v * 255)))) for v in c[:3])


def _lineweight(w_mm: float) -> int:
    """The nearest DXF lineweight (1/100 mm) at least 0.05 mm."""
    weights = (5, 9, 13, 15, 18, 20, 25, 30, 35, 40, 50, 53, 60, 70, 80, 90, 100, 106, 120, 140, 158, 200, 211)
    v = max(5, int(round(w_mm * 100)))
    return min(weights, key=lambda x: abs(x - v))


def _bezier(p0, p1, p2, p3, n=12):
    out = []
    for i in range(1, n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                    a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


#: the Thai PUA glyphs (shifted / lowered marks of Windows and Mac Thai fonts) → the real characters
THAI_PUA = {0xF700: "\u0e10", 0xF701: "\u0e34", 0xF702: "\u0e35", 0xF703: "\u0e36", 0xF704: "\u0e37",
            0xF705: "\u0e48", 0xF706: "\u0e49", 0xF707: "\u0e4a", 0xF708: "\u0e4b", 0xF709: "\u0e4c",
            0xF70A: "\u0e48", 0xF70B: "\u0e49", 0xF70C: "\u0e4a", 0xF70D: "\u0e4b", 0xF70E: "\u0e4c",
            0xF70F: "\u0e0d", 0xF710: "\u0e31", 0xF711: "\u0e4d", 0xF712: "\u0e47", 0xF713: "\u0e48",
            0xF714: "\u0e49", 0xF715: "\u0e4a", 0xF716: "\u0e4b", 0xF717: "\u0e4c", 0xF718: "\u0e38",
            0xF719: "\u0e39", 0xF71A: "\u0e3a"}


def clean_text(t: str) -> tuple:
    """(text, unreadable count): ำ written as ํ + า joined back; the private-use
    codes a PDF font gives for a glyph it does not name become «?»."""
    t = "".join(THAI_PUA.get(ord(ch), ch) for ch in t)
    t = t.replace("\u0e4d\u0e32", "\u0e33").strip()
    bad = sum(1 for ch in t if 0xE000 <= ord(ch) <= 0xF8FF)
    if bad:
        t = "".join("?" if 0xE000 <= ord(ch) <= 0xF8FF else ch for ch in t)
    return t, bad


def convert(pdf_path: str, out_path: str | None = None, page: int = 0, scale: float = 100.0,
            unit: str = "mm") -> Result:
    """Page ``page`` (0-based) of ``pdf_path`` to a DXF at ``out_path`` (beside
    the PDF by default, «name-p1.dxf»): 1 pt = 25.4/72 mm of paper × ``scale``,
    in ``unit`` ("mm" or "m"). Returns what was written."""
    import ezdxf
    import pymupdf
    src = Path(pdf_path)
    out = Path(out_path) if out_path else src.with_name(f"{src.stem}-p{page + 1}.dxf")
    k = PT_MM * float(scale) / (1000.0 if unit == "m" else 1.0)     # drawing units per point
    res = Result(str(out), page)
    dxf = ezdxf.new("R2018", setup=True)
    dxf.header["$INSUNITS"] = 6 if unit == "m" else 4
    msp = dxf.modelspace()
    for name, colour in (("PDF_LINES", 7), ("PDF_FILLS", 8), ("PDF_TEXT", 7)):
        if name not in dxf.layers:
            dxf.layers.add(name, color=colour)
    if "PDF_TH" not in dxf.styles:                       # a font with Thai in it, as AutoCAD reads it
        dxf.styles.add("PDF_TH", font="tahoma.ttf")
    unread = 0
    with pymupdf.open(str(src)) as doc:
        if not 0 <= page < doc.page_count:
            raise ValueError(f"ไม่มีหน้า {page + 1} ในไฟล์ (มี {doc.page_count} หน้า)")
        pg = doc[page]
        H = pg.rect.height
        res.size = (pg.rect.width * k, H * k)

        def P(pt):                                      # PDF y runs down; the drawing's runs up
            return (pt.x * k, (H - pt.y) * k)
        for d in pg.get_drawings():
            stroke, fill = _rgb(d.get("color")), _rgb(d.get("fill"))
            width = float(d.get("width") or 0.0) * PT_MM          # on paper, mm
            attribs = {"layer": "PDF_FILLS" if (fill and not stroke) else "PDF_LINES"}
            col = stroke or fill
            if col and col != (0, 0, 0):
                attribs["true_color"] = ezdxf.colors.rgb2int(col)
            if width:
                attribs["lineweight"] = _lineweight(width)
            # the path, segment by segment, joined into polylines where they meet
            runs, cur = [], []
            for it in d.get("items") or []:
                op = it[0]
                if op == "l":
                    a, b = P(it[1]), P(it[2])
                    if cur and math.dist(cur[-1], a) < 1e-6:
                        cur.append(b)
                    else:
                        if cur:
                            runs.append(cur)
                        cur = [a, b]
                elif op == "c":
                    a = P(it[1])
                    pts = _bezier(a, P(it[2]), P(it[3]), P(it[4]))
                    if cur and math.dist(cur[-1], a) < 1e-6:
                        cur.extend(pts)
                    else:
                        if cur:
                            runs.append(cur)
                        cur = [a] + pts
                elif op == "re":
                    if cur:
                        runs.append(cur)
                        cur = []
                    r = it[1]
                    runs.append([P(r.bl), P(r.br), P(r.tr), P(r.tl), P(r.bl)])
                elif op == "qu":
                    if cur:
                        runs.append(cur)
                        cur = []
                    q = it[1]
                    runs.append([P(q.ll), P(q.lr), P(q.ur), P(q.ul), P(q.ll)])
            if cur:
                runs.append(cur)
            closed_path = bool(d.get("closePath"))
            for pts in runs:
                pts = [p for i, p in enumerate(pts) if i == 0 or math.dist(p, pts[i - 1]) > 1e-9]
                if len(pts) < 2:
                    continue
                closed = closed_path or (len(pts) > 2 and math.dist(pts[0], pts[-1]) < 1e-6)
                if closed and math.dist(pts[0], pts[-1]) < 1e-6:
                    pts = pts[:-1]
                if len(pts) == 2 and not closed:
                    msp.add_line(pts[0], pts[1], dxfattribs=attribs)
                    res.lines += 1
                else:
                    msp.add_lwpolyline(pts, close=closed, dxfattribs=attribs)
                    res.polylines += 1
                if attribs["layer"] == "PDF_FILLS":
                    res.fills += 1
        for block in pg.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                dx, dy = line.get("dir", (1.0, 0.0))
                ang = math.degrees(math.atan2(-dy, dx))         # y runs down in the PDF
                for span in line.get("spans", []):
                    txt, bad = clean_text(span.get("text") or "")
                    unread += bad
                    if not txt:
                        continue
                    size = float(span.get("size") or 0.0)
                    ox, oy = span.get("origin", (0.0, 0.0))
                    attribs = {"layer": "PDF_TEXT", "height": max(size * 0.72 * k, 1e-6),
                               "rotation": ang, "style": "PDF_TH"}
                    col = span.get("color")
                    if col:
                        rgb = ((col >> 16) & 255, (col >> 8) & 255, col & 255)
                        if rgb != (0, 0, 0):
                            attribs["true_color"] = ezdxf.colors.rgb2int(rgb)
                    t = msp.add_text(txt, dxfattribs=attribs)
                    t.set_placement((ox * k, (H - oy) * k))
                    res.texts += 1
        if unread:
            res.notes.append(f"อักษร {unread} ตัวอ่านรหัสไม่ได้ (ฟอนต์ในไฟล์ PDF ไม่บอกว่าเป็นตัวอะไร) "
                             "— แสดงเป็น «?» ตรวจและแก้ข้อความเหล่านั้น")
        if not (res.lines or res.polylines or res.texts) and pg.get_images():
            res.raster_only = True
            res.notes.append("หน้านี้เป็นภาพสแกน ไม่มีเส้นให้อ่าน — ใช้ PDFATTACH (แนบเป็นภาพ) แทน")
    dxf.saveas(str(out))
    return res
