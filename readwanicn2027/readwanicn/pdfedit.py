# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ — ReadWanicn2027
"""แก้ไขข้อความและรูปภาพ in a PDF: find the line of text or the picture
under a click, replace the text (removed with a redaction, written again
in a Thai font with HarfBuzz shaping through ``insert_htmlbox``), add new
text, and insert, replace or delete pictures.

Points come in the displayed page's coordinates (after /Rotate), as the
canvas gives them; PyMuPDF's text and image boxes are unrotated, so every
point goes through ``page.derotation_matrix`` first."""
from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path

import pymupdf

#: The font the edits are written in; Laksaman is TLWG's TH Sarabun.
FONT_FILE = "Laksaman.ttf"


@dataclass
class Span:
    rect: pymupdf.Rect          # unrotated page space
    text: str
    size: float
    color: int                  # 0xRRGGBB
    bold: bool
    font: str


def _unrot(page, pt) -> pymupdf.Point:
    return pymupdf.Point(pt) * page.derotation_matrix


def to_display(page, rect: pymupdf.Rect) -> pymupdf.Rect:
    return rect * page.rotation_matrix


def line_at(page, pt) -> Span | None:
    """The whole line of text under ``pt`` (a line, so a sentence is edited at once)."""
    p = _unrot(page, pt)
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            r = pymupdf.Rect(line["bbox"])
            if not (r + (-2, -2, 2, 2)).contains(p):
                continue
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans:
                continue
            big = max(spans, key=lambda s: s["size"])
            return Span(r, "".join(s["text"] for s in line["spans"]).strip(), big["size"], big["color"],
                        bool(big["flags"] & 16) or "bold" in big["font"].lower(), big["font"])
    return None


def image_at(page, pt):
    """``(xref, rect)`` of the picture under ``pt``, topmost first."""
    p = _unrot(page, pt)
    for info in reversed(page.get_image_info(xrefs=True)):
        r = pymupdf.Rect(info["bbox"])
        if info.get("width", 2) <= 1 and info.get("height", 2) <= 1:
            continue                             # what delete_image leaves behind
        if r.contains(p) and info.get("xref"):
            return info["xref"], r
    return None


def _hex(color: int) -> str:
    return f"#{color:06X}"


def _write(page, rect, text, size, color, bold, font_dir, align="left"):
    css = (f"@font-face {{font-family: th; src: url({FONT_FILE});}}"
           f"@font-face {{font-family: th; src: url(Laksaman-Bold.ttf); font-weight: bold;}}"
           f"* {{font-family: th; font-size: {size:.2f}pt; color: {_hex(color)}; margin: 0; padding: 0;"
           f" line-height: 1.0; text-align: {align}; {'font-weight: bold;' if bold else ''}}}")
    body = "<br>".join(html.escape(t) for t in text.split("\n"))
    arch = pymupdf.Archive(str(font_dir))
    return page.insert_htmlbox(rect, f"<p>{body}</p>", css=css, archive=arch, rotate=page.rotation)


def replace_line(page, span: Span, new_text: str, font_dir, size=None, color=None, bold=None) -> None:
    """Take the line out and write ``new_text`` in its place, same size and colour."""
    page.add_redact_annot(span.rect, fill=False)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
    if not new_text.strip():
        return
    size = size or span.size
    # room to the right for longer text, and a little height for Thai marks above and below
    r = pymupdf.Rect(span.rect.x0, span.rect.y0 - size * 0.25,
                     max(span.rect.x1 + size * 2 * max(0, len(new_text) - len(span.text)),
                         span.rect.x1 + size), span.rect.y1 + size * 0.4)
    r.x1 = min(r.x1, page.rect.width if page.rotation in (0, 180) else page.rect.height)
    _write(page, r, new_text, size, span.color if color is None else color,
           span.bold if bold is None else bold, font_dir)


def add_text(page, pt, text: str, font_dir, size=16.0, color=0, bold=False) -> None:
    """New text with its top-left corner at the clicked point."""
    p = _unrot(page, pt)
    lines = text.split("\n")
    width = max(len(t) for t in lines) * size * 0.62 + size
    r = pymupdf.Rect(p.x, p.y, p.x + width, p.y + len(lines) * size * 1.5 + size * 0.5)
    _write(page, r, text, size, color, bold, font_dir)


def delete_image(page, xref: int) -> None:
    page.delete_image(xref)


def replace_image(page, xref: int, filename) -> None:
    page.replace_image(xref, filename=str(filename))


def insert_image(page, pt, filename, width_pt: float = 150.0) -> pymupdf.Rect:
    pix = pymupdf.Pixmap(str(filename))
    h = width_pt * pix.height / max(1, pix.width)
    p = _unrot(page, pt)
    r = pymupdf.Rect(p.x, p.y, p.x + width_pt, p.y + h)
    page.insert_image(r, filename=str(filename), rotate=page.rotation)
    return r


def font_dir_of(asset) -> Path:
    return Path(asset(FONT_FILE)).parent
