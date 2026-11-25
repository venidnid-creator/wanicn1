# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ฉ3: the A0–A4 paper blocks — the sheet's edge, the drawing frame (25 mm
on the left for binding, 10 mm round the rest; ISO 5457) and the title block
in the lower right corner, every field an attribute to fill in (ATTEDIT).
The text is in «เวนิช» (Venit, the program's own font, from Charm under the
OFL) — the default of the blocks.

A block is drawn in paper millimetres and inserted at the drawing's scale:
a 1:100 plan drawn in millimetres takes the A3 block at ×100.
"""
from __future__ import annotations

import datetime

#: ISO 216, landscape (width, height) mm
SIZES = {"A0": (1189.0, 841.0), "A1": (841.0, 594.0), "A2": (594.0, 420.0),
         "A3": (420.0, 297.0), "A4": (297.0, 210.0)}
STYLE, STYLE_BOLD = "เวนิช", "เวนิช หนา"
FONT, FONT_BOLD = "Venit-Regular.ttf", "Venit-Bold.ttf"
LAYER = "WANIC_FRAME"
THAI_MONTHS = ("ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.")

#: the title block's fields: (tag, label, default)
FIELDS = [("OFFICE", "", "WANICNSURVEY"), ("PROJECT", "โครงการ", ""), ("LOCATION", "สถานที่", ""),
          ("TITLE", "แสดงแบบ", ""), ("DESIGNER", "ผู้ออกแบบ", "นายเวนิช ธัมมะวงษ์"),
          ("CHECKER", "ผู้ตรวจ", ""), ("SCALE", "มาตราส่วน", "1:100"), ("DATE", "วันที่", ""),
          ("SHEET", "แผ่นที่", "A-01")]


def thai_date(d: datetime.date | None = None) -> str:
    d = d or datetime.date.today()
    return f"{d.day} {THAI_MONTHS[d.month - 1]} {d.year + 543}"


def block_name(size: str, portrait: bool = False) -> str:
    return f"WANIC_{size.upper()}{'_P' if portrait else ''}"


def ensure_styles(doc) -> None:
    """«เวนิช» and «เวนิช หนา» — the text styles of the blocks."""
    for name, font in ((STYLE, FONT), (STYLE_BOLD, FONT_BOLD)):
        if name not in doc.styles:
            doc.styles.add(name, font=font)


def define(doc, size: str = "A3", portrait: bool = False) -> str:
    """The block of ``size`` (A0–A4) in ``doc`` (once); returns its name."""
    size = size.upper()
    if size not in SIZES:
        raise ValueError(f"ไม่รู้จักขนาดกระดาษ {size} (A0–A4)")
    name = block_name(size, portrait)
    if name in doc.blocks:
        return name
    ensure_styles(doc)
    if LAYER not in doc.layers:
        doc.layers.add(LAYER, color=7)
    W, H = SIZES[size]
    if portrait:
        W, H = H, W
    blk = doc.blocks.new(name)
    a = {"layer": LAYER}
    left, m = 25.0, 10.0
    blk.add_lwpolyline([(0, 0), (W, 0), (W, H), (0, H)], close=True, dxfattribs=dict(a, lineweight=13))
    blk.add_lwpolyline([(left, m), (W - m, m), (W - m, H - m), (left, H - m)], close=True,
                       dxfattribs=dict(a, lineweight=70))
    # the title block: 180 × 56 mm on A0–A3, the frame's width on A4 portrait
    tw = min(180.0, W - left - m)
    th = 56.0 if size != "A4" else 48.0
    x0, x1, y0 = W - m - tw, W - m, m
    y1 = y0 + th
    blk.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True, dxfattribs=dict(a, lineweight=50))
    # rows: office (tall) · project · location · title · designer/checker · scale/date/sheet
    rows = [y1 - 14, y1 - 22, y1 - 30, y1 - 38, y1 - 46]
    for y in rows:
        blk.add_line((x0, y), (x1, y), dxfattribs=dict(a, lineweight=25))
    xm = x0 + tw / 2
    blk.add_line((xm, rows[4]), (xm, rows[3]), dxfattribs=dict(a, lineweight=25))
    thirds = [x0 + tw / 3, x0 + 2 * tw / 3]
    for xx in thirds:
        blk.add_line((xx, y0), (xx, rows[4]), dxfattribs=dict(a, lineweight=25))
    lab_h, val_h = 2.2, 3.2

    def label(text, x, y):
        if text:
            blk.add_text(text, dxfattribs=dict(a, style=STYLE, height=lab_h)).set_placement((x + 1.5, y + 1.2))

    def field(tag, x, y, h=val_h, bold=False, width=None):
        default = next(d for t, _l, d in FIELDS if t == tag)
        if tag == "DATE":
            default = thai_date()
        att = blk.add_attdef(tag, (x, y), default or " ",
                             dxfattribs=dict(a, style=STYLE_BOLD if bold else STYLE, height=h))
        att.dxf.prompt = next(lab for t, lab, _d in FIELDS if t == tag) or "ชื่อสำนักงาน"
        if width:
            from ezdxf.enums import TextEntityAlignment
            att.set_placement((x, y), align=TextEntityAlignment.LEFT)
        return att
    # office, big
    field("OFFICE", x0 + 4, rows[0] + 4.5, h=6.0, bold=True)
    label("โครงการ", x0, rows[1])
    field("PROJECT", x0 + 22, rows[1] + 2.2, bold=True)
    label("สถานที่", x0, rows[2])
    field("LOCATION", x0 + 22, rows[2] + 2.2)
    label("แสดงแบบ", x0, rows[3])
    field("TITLE", x0 + 22, rows[3] + 2.2, bold=True)
    label("ผู้ออกแบบ", x0, rows[4])
    field("DESIGNER", x0 + 18, rows[4] + 2.2)
    label("ผู้ตรวจ", xm, rows[4])
    field("CHECKER", xm + 14, rows[4] + 2.2)
    for (tag, lab), xx in zip((("SCALE", "มาตราส่วน"), ("DATE", "วันที่"), ("SHEET", "แผ่นที่")),
                              (x0, thirds[0], thirds[1])):
        label(lab, xx, y0 + 5.5)
        field(tag, xx + 2, y0 + 1.6, h=3.6 if tag == "SHEET" else val_h, bold=tag == "SHEET")
    # จ37 — the owner's words, under the frame on the right
    blk.add_text("การนำข้อมูลไปใช้จะต้องได้รับอนุญาตจากเจ้าของพื้นที่แล้วเท่านั้น",
                 dxfattribs=dict(a, style=STYLE, height=2.4)).set_placement((x0, y1 + 2.0))
    return name


def unit_factor(doc) -> float:
    """Drawing units per paper millimetre at 1:1 — 0.001 for a drawing in metres."""
    try:
        u = int(doc.header.get("$INSUNITS", 4) or 4)
    except Exception:                                     # noqa: BLE001
        u = 4
    return {6: 0.001, 5: 0.1, 4: 1.0, 1: 1 / 25.4}.get(u, 1.0)


def insert(doc, size: str = "A3", at=(0.0, 0.0), scale: float = 1.0, portrait: bool = False,
           values: dict | None = None, space=None):
    """The block of ``size`` inserted at ``at`` × ``scale`` (the drawing's 1:n,
    in the drawing's units) with its attributes filled (``values`` by tag,
    the defaults otherwise) into ``space`` (model space by default)."""
    name = define(doc, size, portrait)
    msp = space if space is not None else doc.modelspace()
    shown = scale
    scale = scale * unit_factor(doc)
    ref = msp.add_blockref(name, at, dxfattribs={"xscale": scale, "yscale": scale, "layer": LAYER})
    vals = {t: d for t, _l, d in FIELDS}
    vals["DATE"] = thai_date()
    vals["SCALE"] = f"1:{shown:g}"
    vals.update(values or {})
    ref.add_auto_attribs({k: (v if v else " ") for k, v in vals.items()})
    return ref
