# SPDX-License-Identifier: GPL-3.0-or-later
"""A sample drawing for the tests and the screenshots: a 1:100 floor plan
on A3, a page with a table, and a photo (for the compression)."""
from __future__ import annotations

import math

import pymupdf

MM = 72.0 / 25.4                     # PDF points per paper millimetre


def plan_pt(m: float) -> float:
    """Metres on site to PDF points at 1:100."""
    return m * 1000.0 / 100.0 * MM


def make(path, font=None):
    doc = pymupdf.open()
    page = doc.new_page(width=420 * MM, height=297 * MM)        # A3 landscape
    ox, oy = 60 * MM, 50 * MM
    s = plan_pt
    rooms = [((0, 0, 4, 4), "ห้องนอน 1"), ((4, 0, 4, 4), "ห้องนอน 2"),
             ((0, 4, 5, 4), "ห้องนั่งเล่น"), ((5, 4, 3, 2), "ห้องน้ำ"), ((5, 6, 3, 2), "ครัว")]
    for (x, y, w, h), name in rooms:
        r = pymupdf.Rect(ox + s(x), oy + s(y), ox + s(x + w), oy + s(y + h))
        page.draw_rect(r, color=(0.1, 0.1, 0.1), width=2.5)
        if font:
            page.insert_text((r.x0 + 8, r.y0 + 18), f"{name} {w*h:.0f} ตร.ม.", fontsize=11,
                             fontfile=font, fontname="th")
    page.draw_line((ox, oy - 20), (ox + s(8), oy - 20), color=(0.8, 0, 0), width=0.8)
    page.insert_text((ox + s(4) - 20, oy - 26), "8.00 m", fontsize=10)
    page.insert_text((40 * MM, 280 * MM), "PLAN 1:100  (A3)", fontsize=14)
    # a table page
    p2 = doc.new_page(width=210 * MM, height=297 * MM)
    rows = [["Item", "Unit", "Qty"], ["Brick wall", "m2", "120"], ["Floor tile", "m2", "86"],
            ["Door", "set", "6"], ["Window", "set", "9"]]
    x0, y0, cw, rh = 30 * MM, 40 * MM, 45 * MM, 9 * MM
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            r = pymupdf.Rect(x0 + j * cw, y0 + i * rh, x0 + (j + 1) * cw, y0 + (i + 1) * rh)
            page2_draw = p2.draw_rect(r, color=(0, 0, 0), width=0.8)
            p2.insert_text((r.x0 + 4, r.y1 - 8), v, fontsize=11)
    p2.insert_text((x0, 30 * MM), "BILL OF QUANTITIES", fontsize=16)
    # a photo, to have something to compress
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 1600, 1200), 0)
    buf = bytearray(1600 * 1200 * 3)
    for yy in range(1200):
        for xx in range(0, 1600, 4):
            k = (yy * 1600 + xx) * 3
            v = int(128 + 120 * math.sin(xx / 37.0) * math.cos(yy / 23.0))
            buf[k:k + 3] = bytes((v, (v * 3) % 256, 255 - v))
    pix = pymupdf.Pixmap(pymupdf.csRGB, 1600, 1200, bytes(buf), 0)
    p3 = doc.new_page(width=210 * MM, height=297 * MM)
    p3.insert_image(pymupdf.Rect(20 * MM, 20 * MM, 190 * MM, 147.5 * MM), pixmap=pix)
    doc.save(path)
    doc.close()
    return path
