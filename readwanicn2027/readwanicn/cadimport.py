# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ — ReadWanicn2027
"""นำเข้าไฟล์เขียนแบบ: DXF (and DWG through the free ODA File Converter)
drawn to a PDF page at a standard scale, so the take-off tools measure it
in metres straight away; and SVG, XPS and pictures of drawings, which
PyMuPDF converts to PDF itself."""
from __future__ import annotations

import glob
import math
import os
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from .measure import STANDARD_SCALES

CAD_EXT = (".dxf", ".dwg")
OTHER_EXT = (".svg", ".xps", ".oxps", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif")
ALL_EXT = CAD_EXT + OTHER_EXT
#: $INSUNITS → millimetres per drawing unit
_UNIT_MM = {1: 25.4, 2: 304.8, 4: 1.0, 5: 10.0, 6: 1000.0, 8: 0.0254, 14: 100.0}
_UNIT_TH = {1: "นิ้ว", 2: "ฟุต", 4: "มิลลิเมตร", 5: "เซนติเมตร", 6: "เมตร", 14: "เดซิเมตร"}
#: The largest sheet the drawing is put on: A0 landscape, inside 10 mm margins.
SHEET_MM = (1189 - 20, 841 - 20)


class CadError(Exception):
    pass


@dataclass
class Imported:
    pdf: str
    ratio: int                # the page is the drawing at 1:ratio
    units: str                # what one drawing unit was taken to be
    guessed: bool             # the file did not say its units


def oda_converter() -> str | None:
    """ODAFileConverter.exe if installed (free from the Open Design Alliance)."""
    env = os.environ.get("ODA_FILE_CONVERTER")
    if env and Path(env).exists():
        return env
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                 os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
        hits = sorted(glob.glob(os.path.join(base, "ODA", "ODAFileConverter*", "ODAFileConverter.exe")))
        if hits:
            return hits[-1]
    return None


def read_cad(path):
    import ezdxf
    from ezdxf import recover
    if path.lower().endswith(".dwg"):
        exe = oda_converter()
        if not exe:
            raise CadError("dwg")
        from ezdxf.addons import odafc
        ezdxf.options.set("odafc-addon", "win_exec_path", exe)
        return odafc.readfile(path)
    try:
        doc, _auditor = recover.readfile(path)
    except (IOError, ezdxf.DXFStructureError) as e:
        raise CadError(f"อ่านไฟล์ไม่ได้: {e}") from e
    return doc


def _thai_fonts(doc) -> None:
    """Text styles whose font is a CAD shape font (.shx) or is not on this
    computer are drawn in Laksaman (TH Sarabun), so Thai text is not boxes."""
    from ezdxf.fonts import fonts
    fm = fonts.font_manager
    here = Path(__file__).resolve().parent.parent / "assets"
    import sys
    for d in {here, Path(getattr(sys, "_MEIPASS", here.parent)) / "assets"}:
        if (d / "Laksaman.ttf").exists() and not fm.has_font("Laksaman.ttf"):
            fm.scan_folder(d)
    for style in doc.styles:
        font = (style.dxf.get("font", "") or "").strip()
        if not font.lower().endswith((".ttf", ".ttc", ".otf")) or not fm.has_font(Path(font).name):
            style.dxf.font = "Laksaman.ttf"
            style.dxf.discard("bigfont")
            if style.has_extended_font_data:
                style.discard_extended_font_data()


def _ratio_for(span_mm: float) -> int:
    """The smallest standard 1:N that puts ``span_mm`` (real size) on the sheet."""
    for n in sorted(set(STANDARD_SCALES) | {1, 2, 5, 10, 2000, 2500, 5000, 10000, 20000, 50000}):
        if span_mm / n <= SHEET_MM[0]:
            return n
    return int(math.ceil(span_mm / SHEET_MM[0] / 1000) * 1000)


def cad_to_pdf(path, out_pdf) -> Imported:
    from ezdxf import bbox
    from ezdxf.addons.drawing import Frontend, RenderContext, config, layout
    from ezdxf.addons.drawing.pymupdf import PyMuPdfBackend

    doc = read_cad(str(path))
    _thai_fonts(doc)
    msp = doc.modelspace()
    ext = bbox.extents(msp, fast=True)
    if not ext.has_data:
        raise CadError("ไม่พบเส้นหรือข้อความในแบบ (model space ว่าง)")
    code = int(doc.header.get("$INSUNITS", 0) or 0)
    guessed = code not in _UNIT_MM
    if guessed:                                  # no units: survey drawings in metres, building drawings in mm
        code = 4 if max(ext.size.x, ext.size.y) > 5000 else 6
    unit_mm = _UNIT_MM[code]
    w_mm, h_mm = ext.size.x * unit_mm, ext.size.y * unit_mm
    landscape = w_mm >= h_mm
    long_side, short_side = (w_mm, h_mm) if landscape else (h_mm, w_mm)
    n = max(_ratio_for(long_side), _ratio_for(short_side * SHEET_MM[0] / SHEET_MM[1]))
    margin = 10
    # ezdxf rounds the page to 0.1 mm and truncates it to whole points; a page that is
    # already both (a multiple of 12.7 mm = 36 pt) keeps the drawing exactly at 1:n
    def whole(mm):
        from ezdxf.addons.drawing.pymupdf import MM_TO_POINTS
        j = math.ceil(mm / 12.7)
        while True:
            size = round(j * 12.7, 1)
            if int(size * MM_TO_POINTS) == 36 * j:
                return size
            j += 1
    page = layout.Page(whole(w_mm / n + 2 * margin), whole(h_mm / n + 2 * margin), layout.Units.mm,
                       margins=layout.Margins.all(margin))
    settings = layout.Settings(fit_page=False, scale=unit_mm / n, max_stroke_width=0.004,
                               min_stroke_width=0.25)        # mm: hairlines still print
    cfg = config.Configuration(background_policy=config.BackgroundPolicy.WHITE,
                               color_policy=config.ColorPolicy.COLOR,
                               lineweight_policy=config.LineweightPolicy.ABSOLUTE)
    backend = PyMuPdfBackend()
    Frontend(RenderContext(doc), backend, config=cfg).draw_layout(msp, finalize=True)
    data = backend.get_pdf_bytes(page, settings=settings)
    Path(out_pdf).write_bytes(data)
    return Imported(str(out_pdf), n, _UNIT_TH.get(code, "หน่วย"), guessed)


def other_to_pdf(path, out_pdf) -> str:
    """SVG / XPS / a picture of a drawing as a PDF."""
    with pymupdf.open(str(path)) as src:
        data = src.convert_to_pdf()
    Path(out_pdf).write_bytes(data)
    return str(out_pdf)


def import_file(path, out_dir=None):
    """The PDF to open for ``path`` and, for CAD, its scale (None otherwise)."""
    p = Path(path)
    out_dir = Path(out_dir) if out_dir else p.parent
    out = out_dir / f"{p.stem}-{p.suffix[1:].lower()}.pdf"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.touch(exist_ok=True)
    except OSError:                              # a read-only folder: put it with the program's files
        base = os.environ.get("APPDATA") or os.path.join(Path.home(), ".config")
        out = Path(base) / "ReadWanicn2027" / "นำเข้า" / out.name
        out.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix.lower() in CAD_EXT:
        return cad_to_pdf(p, out)
    return other_to_pdf(p, out)
