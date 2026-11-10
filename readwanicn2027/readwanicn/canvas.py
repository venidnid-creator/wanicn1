# SPDX-License-Identifier: GPL-3.0-or-later
"""The page on screen and the take-off tools drawn over it."""
from __future__ import annotations

import math

import pymupdf
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from .measure import Measurement

#: Screen pixels per PDF point at 100 % (a PDF point is 1/72 inch, a screen 96 dpi).
PX_PER_PT = 96.0 / 72.0
TOOLS = {
    "pan": "เลื่อน: ลากเพื่อเลื่อนแบบ · Ctrl+ล้อเมาส์ = ย่อ/ขยาย",
    "scale": "ตั้งสเกล: คลิก 2 จุดบนระยะที่รู้ค่า แล้วใส่ระยะจริง (ม.)",
    "length": "วัดความยาว: คลิกทีละจุด · ดับเบิลคลิกหรือ Enter = จบเส้น · Esc = ยกเลิก",
    "area": "คิดพื้นที่: คลิกรอบรูป · ดับเบิลคลิกหรือ Enter = ปิดรูป · Esc = ยกเลิก",
    "count": "นับจำนวน: คลิกทุกจุดที่ต้องการนับ · Enter = จบชุด · Esc = ยกเลิก",
}
COLORS = {"length": QColor("#F59E0B"), "area": QColor("#22C55E"), "count": QColor("#EF4444"),
          "scale": QColor("#38BDF8")}


class PdfCanvas(QWidget):
    finished = Signal(str, list)          # kind, points (PDF points)
    calibrate = Signal(float)             # distance in PDF points between the 2 clicks
    zoomRequested = Signal(float)         # factor
    panBy = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Canvas")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.doc = None
        self.page_no = 0
        self.zoom = 1.0
        self.tool = "pan"
        self.points: list = []
        self.cursor_pt = None
        self.measurements: list = []      # Measurement of this file
        self._image = None
        self._drag = None

    # -- document
    def set_document(self, doc, page_no: int = 0):
        self.doc = doc
        self.page_no = page_no
        self.points = []
        self.render()

    def render(self):
        if self.doc is None or self.doc.page_count == 0:
            self._image = None
            self.resize(10, 10)
            self.update()
            return
        self.page_no = max(0, min(self.page_no, self.doc.page_count - 1))
        z = PX_PER_PT * self.zoom
        pix = self.doc[self.page_no].get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=False)
        fmt = QImage.Format_RGB888
        self._image = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()
        self.setFixedSize(pix.width + 40, pix.height + 40)
        self.update()

    def page_size(self):
        r = self.doc[self.page_no].rect
        return r.width, r.height

    # -- coordinates: PDF points of the displayed (rotated) page
    def to_pt(self, pos: QPointF):
        z = PX_PER_PT * self.zoom
        return ((pos.x() - 20) / z, (pos.y() - 20) / z)

    def to_px(self, pt) -> QPointF:
        z = PX_PER_PT * self.zoom
        return QPointF(20 + pt[0] * z, 20 + pt[1] * z)

    def set_tool(self, tool: str):
        self.tool = tool
        self.points = []
        self.setCursor(Qt.OpenHandCursor if tool == "pan" else Qt.CrossCursor)
        self.update()

    # -- mouse and keys
    def mousePressEvent(self, e):
        if self._image is None:
            return
        if self.tool == "pan" or e.button() == Qt.MiddleButton:
            self._drag = e.globalPosition()
            self.setCursor(Qt.ClosedHandCursor)
            return
        if e.button() != Qt.LeftButton:
            return
        pt = self.to_pt(e.position())
        self.points.append(pt)
        if self.tool == "scale" and len(self.points) == 2:
            d = math.dist(*self.points)
            self.points = []
            self.calibrate.emit(d)
        self.update()

    def mouseDoubleClickEvent(self, e):
        if self.tool in ("length", "area"):
            # the double click added the same point twice
            if len(self.points) >= 2 and self.points[-1] == self.points[-2]:
                self.points.pop()
            self.finish()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            d = e.globalPosition() - self._drag
            self._drag = e.globalPosition()
            self.panBy.emit(-d.x(), -d.y())
            return
        self.cursor_pt = self.to_pt(e.position())
        if self.points:
            self.update()

    def mouseReleaseEvent(self, e):
        if self._drag is not None:
            self._drag = None
            self.setCursor(Qt.OpenHandCursor if self.tool == "pan" else Qt.CrossCursor)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            self.zoomRequested.emit(1.15 if e.angleDelta().y() > 0 else 1 / 1.15)
            e.accept()
        else:
            e.ignore()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.finish()
        elif e.key() == Qt.Key_Escape:
            self.points = []
            self.update()
        elif e.key() == Qt.Key_Backspace and self.points:
            self.points.pop()
            self.update()
        else:
            super().keyPressEvent(e)

    def finish(self):
        need = {"length": 2, "area": 3, "count": 1}.get(self.tool)
        if need and len(self.points) >= need:
            self.finished.emit(self.tool, list(self.points))
        self.points = []
        self.update()

    # -- drawing
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self._image is None:
            return
        p.fillRect(QRectF(24, 24, self._image.width(), self._image.height()), QColor(0, 0, 0, 90))
        p.drawImage(20, 20, self._image)
        f = QFont(self.font())
        f.setPointSizeF(9)
        f.setBold(True)
        p.setFont(f)
        for m in self.measurements:
            if m.page == self.page_no:
                self._draw(p, m.kind, m.points, m.text(), m.name)
        if self.points:
            pts = list(self.points)
            if self.cursor_pt is not None and self.tool != "count":
                pts.append(self.cursor_pt)
            self._draw(p, self.tool, pts, "", "", live=True)

    def _draw(self, p, kind, pts, label, name, live=False):
        color = COLORS.get(kind, QColor("#F59E0B"))
        px = [self.to_px(q) for q in pts]
        if kind == "count":
            for i, q in enumerate(px, 1):
                p.setPen(QPen(QColor("white"), 1.5))
                p.setBrush(color)
                p.drawEllipse(q, 7, 7)
                p.drawText(QRectF(q.x() - 7, q.y() - 7, 14, 14), Qt.AlignCenter, str(i))
            anchor = px[-1] if px else None
        else:
            pen = QPen(color, 2.4, Qt.DashLine if live else Qt.SolidLine)
            p.setPen(pen)
            if kind == "area" and len(px) >= 3:
                fill = QColor(color)
                fill.setAlpha(60)
                p.setBrush(fill)
                p.drawPolygon(QPolygonF(px))
            else:
                p.setBrush(Qt.NoBrush)
                for a, b in zip(px, px[1:]):
                    p.drawLine(a, b)
            p.setBrush(color)
            p.setPen(Qt.NoPen)
            for q in px:
                p.drawEllipse(q, 3.2, 3.2)
            anchor = px[-1] if px else None
        if anchor is not None and label:
            text = f"{name}: {label}" if name else label
            r = p.fontMetrics().boundingRect(text)
            box = QRectF(anchor.x() + 8, anchor.y() - r.height() - 10, r.width() + 12, r.height() + 6)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(15, 42, 68, 220))
            p.drawRoundedRect(box, 4, 4)
            p.setPen(QColor("white"))
            p.drawText(box, Qt.AlignCenter, text)
