# SPDX-License-Identifier: GPL-3.0-or-later
"""The page on screen and the take-off tools drawn over it."""
from __future__ import annotations

import math

import pymupdf
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from .measure import Measurement
from .snap import KINDS as SNAP_KINDS, Snapper

#: Screen pixels per PDF point at 100 % (a PDF point is 1/72 inch, a screen 96 dpi).
PX_PER_PT = 96.0 / 72.0
TOOLS = {
    "pan": "เลื่อน: ลากเพื่อเลื่อนแบบ · Ctrl+ล้อเมาส์ = ย่อ/ขยาย",
    "scale": "ตั้งสเกล: คลิก 2 จุดบนระยะที่รู้ค่า แล้วใส่ระยะจริง (ม.)",
    "length": "วัดความยาว: คลิกทีละจุด · ดับเบิลคลิกหรือ Enter = จบเส้น · Esc = ยกเลิก",
    "area": "คิดพื้นที่: คลิกรอบรูป · ดับเบิลคลิกหรือ Enter = ปิดรูป · Esc = ยกเลิก",
    "count": "นับจำนวน: คลิกทุกจุดที่ต้องการนับ · Enter = จบชุด · Esc = ยกเลิก",
    "edit": "แก้ไขข้อความและรูปภาพ: คลิกที่ข้อความเพื่อแก้ · คลิกที่รูปเพื่อเปลี่ยน/ลบ · "
            "คลิกที่ว่างเพื่อเพิ่มข้อความหรือรูป",
}
COLORS = {"length": QColor("#F59E0B"), "area": QColor("#22C55E"), "count": QColor("#EF4444"),
          "scale": QColor("#38BDF8")}


class PdfCanvas(QWidget):
    finished = Signal(str, list)          # kind, points (PDF points)
    calibrate = Signal(float)             # distance in PDF points between the 2 clicks
    zoomRequested = Signal(float)         # factor
    panBy = Signal(float, float)
    editAt = Signal(float, float)         # a click of the edit tool (PDF points, displayed page)

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
        #: For the edit tool: pt -> (x0, y0, x1, y1) of the text or picture under it, or None.
        self.probe = None
        self._hover = None
        #: ยึดจุด: snap the measuring clicks to the drawing's lines (F3 turns it off and on, Shift = free).
        self.snap_on = True
        self.snap_hit = None
        self._snapper = None
        self._snap_key = None
        self.snapChanged = None             # callback(bool) for the button

    # -- document
    def invalidate_snap(self):
        self._snapper = None
        self._snap_key = None

    def snapper(self):
        if self.doc is None:
            return None
        key = (id(self.doc), self.page_no, self.doc[self.page_no].rotation)
        if key != self._snap_key:
            from PySide6.QtWidgets import QApplication
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                self._snapper = Snapper(self.doc[self.page_no])
            finally:
                QApplication.restoreOverrideCursor()
            self._snap_key = key
        return self._snapper

    def _snap(self, pt, modifiers):
        """The clicked/hovered point after snapping, and remember what it snapped to."""
        self.snap_hit = None
        if not self.snap_on or self.tool not in ("scale", "length", "area", "count") \
                or modifiers & Qt.ShiftModifier or self.doc is None:
            return pt
        sn = self.snapper()
        hit = sn.find(pt, 12.0 / (PX_PER_PT * self.zoom)) if sn else None
        self.snap_hit = hit
        return hit.pt if hit else pt

    def set_document(self, doc, page_no: int = 0):
        self.invalidate_snap()
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
        self._hover = None
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
        pt = self._snap(self.to_pt(e.position()), e.modifiers())
        if self.tool == "edit":
            self.editAt.emit(*pt)
            return
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
        before = self.snap_hit
        self.cursor_pt = self._snap(self.to_pt(e.position()), e.modifiers())
        if (before is None) != (self.snap_hit is None) or (self.snap_hit and before and
                                                           self.snap_hit.pt != before.pt):
            self.update()
        if self.tool == "edit" and self.probe is not None:
            hover = self.probe(self.cursor_pt)
            if hover != self._hover:
                self._hover = hover
                self.setCursor(Qt.IBeamCursor if hover else Qt.CrossCursor)
                self.update()
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
        if e.key() == Qt.Key_F3:
            self.snap_on = not self.snap_on
            self.snap_hit = None
            if self.snapChanged:
                self.snapChanged(self.snap_on)
            self.update()
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter):
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
        if self.tool == "edit" and self._hover:
            x0, y0, x1, y1 = self._hover
            a, b = self.to_px((x0, y0)), self.to_px((x1, y1))
            p.setPen(QPen(QColor("#1F6FEB"), 1.6, Qt.DashLine))
            p.setBrush(QColor(31, 111, 235, 40))
            p.drawRect(QRectF(a, b).normalized().adjusted(-2, -2, 2, 2))
        if self.points:
            pts = list(self.points)
            if self.cursor_pt is not None and self.tool != "count":
                pts.append(self.cursor_pt)
            self._draw(p, self.tool, pts, "", "", live=True)
        if self.snap_hit is not None:
            self._draw_snap(p, self.snap_hit)

    def _draw_snap(self, p, hit):
        c = self.to_px(hit.pt)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor("#00C2FF"), 2))
        r = 6
        if hit.kind == "end":
            p.drawRect(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r))
        elif hit.kind == "mid":
            p.drawPolygon(QPolygonF([QPointF(c.x(), c.y() - r), QPointF(c.x() + r, c.y() + r),
                                     QPointF(c.x() - r, c.y() + r)]))
        elif hit.kind == "int":
            p.drawLine(QPointF(c.x() - r, c.y() - r), QPointF(c.x() + r, c.y() + r))
            p.drawLine(QPointF(c.x() - r, c.y() + r), QPointF(c.x() + r, c.y() - r))
        elif hit.kind == "cen":
            p.drawEllipse(c, r, r)
            p.drawLine(QPointF(c.x() - 2, c.y()), QPointF(c.x() + 2, c.y()))
        else:
            p.drawPolygon(QPolygonF([QPointF(c.x(), c.y() - r), QPointF(c.x() + r, c.y()),
                                     QPointF(c.x(), c.y() + r), QPointF(c.x() - r, c.y())]))
        label = SNAP_KINDS[hit.kind]
        f = QFont(self.font())
        f.setPointSizeF(8.5)
        p.setFont(f)
        w = p.fontMetrics().horizontalAdvance(label) + 8
        box = QRectF(c.x() + 10, c.y() + 8, w, 16)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 120, 170, 210))
        p.drawRoundedRect(box, 3, 3)
        p.setPen(QColor("white"))
        p.drawText(box, Qt.AlignCenter, label)

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
