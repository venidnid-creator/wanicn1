# SPDX-License-Identifier: GPL-3.0-or-later
"""«รูปทรง»: rectangle, circle and triangle measured on a drawing, and «อ่านรูปทรงจากแบบ»
that finds the outline around a click from the drawing's own lines."""
from __future__ import annotations

import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("READWANICN_OFFLINE", "1")

import pymupdf
import pytest

from readwanicn import measure, snap

MM = 72.0 / 25.4


def _drawing():
    """A footing 1.30 × 0.85 m at 1:20 drawn as four separate lines, with a hatched column
    and three piles (circles Ø 0.30 m), a triangle and a closed rectangle path."""
    doc = pymupdf.open()
    page = doc.new_page(width=420 * MM, height=297 * MM)
    s = 1000 / 20 * MM                                        # PDF points per metre at 1:20
    ox, oy = 50 * MM, 40 * MM
    w, h = 1.30 * s, 0.85 * s
    for a, b in (((0, 0), (w, 0)), ((w, 0), (w, h)), ((w, h), (0, h)), ((0, h), (0, 0))):
        page.draw_line((ox + a[0], oy + a[1]), (ox + b[0], oy + b[1]), width=1)
    for k in range(-6, 7):                                    # diagonal hatching of a column 0.20 m
        c = 0.10 * s
        x0, y0 = ox + w / 2 - c, oy + h / 2 - c
        page.draw_line((x0 + max(0, k) * c / 3, y0 + max(0, -k) * c / 3),
                       (x0 + min(6, 6 + k) * c / 3, y0 + min(6, 6 - k) * c / 3), width=0.3)
    for i in range(3):
        page.draw_circle((ox + (0.20 + 0.45 * i) * s, oy + 0.22 * s), 0.15 * s, width=0.6)
    page.draw_polyline([(300 * MM, 60 * MM), (360 * MM, 60 * MM), (300 * MM, 120 * MM), (300 * MM, 60 * MM)],
                       width=0.8, closePath=True)
    page.draw_rect(pymupdf.Rect(200 * MM, 150 * MM, 260 * MM, 190 * MM), width=0.8)
    return doc, page, s, (ox, oy, w, h)


def test_read_the_shape_around_a_click():
    doc, page, s, (ox, oy, w, h) = _drawing()
    sn = snap.Snapper(page)
    # inside the footing, away from piles and column: the rectangle from the four lines
    kind, pts = sn.shape_at((ox + 0.15 * s, oy + 0.75 * s))
    assert kind == "rect"
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    assert (max(xs) - min(xs)) / s == pytest.approx(1.30, abs=0.003)
    assert (max(ys) - min(ys)) / s == pytest.approx(0.85, abs=0.003)
    # inside a pile: the circle
    kind, pts = sn.shape_at((ox + 0.65 * s, oy + 0.22 * s))
    assert kind == "circle"
    assert math.dist(*pts) / s == pytest.approx(0.15, abs=0.003)
    # the triangle and the closed rectangle
    assert sn.shape_at((310 * MM, 75 * MM))[0] == "tri"
    kind, pts = sn.shape_at((230 * MM, 170 * MM))
    assert kind == "rect" and abs(snap._area(pts)) == pytest.approx(60 * 40 * MM * MM, rel=1e-3)
    assert sn.shape_at((5, 5)) is None                       # nothing around the page corner


def test_shape_measurements():
    sc = measure.Scale.ratio(20)
    k = sc.m_per_pt
    rect = measure.Measurement("area", 0, [(0, 0), (1.3 / k, 0), (1.3 / k, 0.85 / k), (0, 0.85 / k)], sc, shape="rect")
    assert rect.value == pytest.approx(1.105) and rect.perimeter == pytest.approx(4.30)
    assert rect.dims() == "1.300 × 0.850 ม."
    circ = measure.Measurement("area", 0, [(0, 0), (0.15 / k, 0)], sc, shape="circle")
    assert circ.value == pytest.approx(math.pi * 0.15 ** 2) and circ.dims() == "Ø 0.300 ม."
    assert circ.perimeter == pytest.approx(2 * math.pi * 0.15)
    tri = measure.Measurement("area", 0, [(0, 0), (3 / k, 0), (0, 4 / k)], sc, shape="tri")
    assert tri.value == pytest.approx(6.0) and tri.perimeter == pytest.approx(12.0)
    assert "วงกลม" in measure._rows([circ])[0][3]


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_canvas_shape_tools(app):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    from readwanicn.canvas import PdfCanvas
    doc, page, s, (ox, oy, w, h) = _drawing()
    c = PdfCanvas()
    c.set_document(doc, 0)
    got = []
    c.shapeFinished.connect(lambda kind, pts: got.append((kind, pts)))

    def click(pt):
        pos = c.to_px(pt)
        ev = QMouseEvent(QMouseEvent.MouseButtonPress, QPointF(pos), QPointF(pos), Qt.LeftButton,
                         Qt.LeftButton, Qt.NoModifier)
        c.mousePressEvent(ev)
    c.set_tool("rect")
    click((ox, oy))
    click((ox + w, oy + h))                                   # snaps to the corners
    assert got[-1][0] == "rect" and len(got[-1][1]) == 4
    c.set_tool("circle")
    click((ox + 0.65 * s, oy + 0.22 * s))
    click((ox + 0.80 * s, oy + 0.22 * s))
    assert got[-1][0] == "circle"
    c.set_tool("tri")
    for p in ((0, 0), (100, 0), (0, 100)):
        click((300 + p[0], 300 + p[1]))
    assert got[-1][0] == "tri"
    c.set_tool("auto")
    click((ox + 0.15 * s, oy + 0.75 * s))
    assert got[-1][0] == "rect"
    c.deleteLater()
