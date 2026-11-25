# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ฉ2 PDFIMPORT: a vector PDF page back into DXF lines, polylines and text, at
the drawing's scale; the Thai marks a PDF font hides in its private codes."""
from __future__ import annotations

import math

import pytest

pymupdf = pytest.importorskip("pymupdf")
ezdxf = pytest.importorskip("ezdxf")

from formats import pdf_in as PI  # noqa: E402


def _pdf(path):
    doc = pymupdf.open()
    pg = doc.new_page(width=842, height=595)                 # A4 landscape, points
    pg.draw_line((72, 72), (72 + 283.4646, 72), color=(1, 0, 0), width=0.5)   # 100 mm on paper
    pg.draw_rect(pymupdf.Rect(100, 200, 200, 300), color=(0, 0, 0), width=1)
    pg.draw_bezier((300, 300), (350, 250), (400, 350), (450, 300), color=(0, 0, 1))
    pg.insert_text((100, 400), "PLAN 1:100", fontsize=12)
    doc.save(str(path))


def test_lines_polylines_curves_and_text_at_the_drawing_scale(tmp_path):
    src = tmp_path / "plan.pdf"
    _pdf(src)
    assert PI.page_count(str(src)) == 1
    res = PI.convert(str(src), page=0, scale=100)                     # a 1:100 plan → real mm
    assert res.path.endswith("plan-p1.dxf") and res.lines >= 1 and res.polylines >= 2 and res.texts == 1
    doc = ezdxf.readfile(res.path)
    msp = doc.modelspace()
    line = next(e for e in msp.query("LINE"))
    a, b = line.dxf.start, line.dxf.end
    assert math.dist((a.x, a.y), (b.x, b.y)) == pytest.approx(100 * 100, rel=1e-3)   # 100 mm × 100
    assert line.dxf.true_color == ezdxf.colors.rgb2int((255, 0, 0))
    rect = [e for e in msp.query("LWPOLYLINE") if e.closed]
    assert rect and len(rect[0]) == 4
    curve = [e for e in msp.query("LWPOLYLINE") if not e.closed]
    assert curve and len(curve[0]) > 6                                 # a Bézier as a fine polyline
    t = next(e for e in msp.query("TEXT"))
    assert t.dxf.text == "PLAN 1:100" and t.dxf.style == "PDF_TH"
    assert t.dxf.height == pytest.approx(12 * 0.72 * PI.PT_MM * 100, rel=1e-3)
    # metres, and the page's y turned upright (PDF y runs down)
    res_m = PI.convert(str(src), str(tmp_path / "m.dxf"), page=0, scale=100, unit="m")
    ln = next(e for e in ezdxf.readfile(res_m.path).modelspace().query("LINE"))
    assert ln.dxf.start.y == pytest.approx((595 - 72) * PI.PT_MM * 100 / 1000, rel=1e-6)


def test_thai_marks_and_unreadable_codes():
    assert PI.clean_text("วิศวกรสํารวจ") == ("วิศวกรสำรวจ", 0)
    assert PI.clean_text("ผู้") == ("ผู้้", 0)                   # a lowered mai tho → ้
    assert PI.clean_text("0000") == ("0?000", 1)


def test_a_missing_page_is_said(tmp_path):
    src = tmp_path / "p.pdf"
    _pdf(src)
    with pytest.raises(ValueError):
        PI.convert(str(src), page=5)
