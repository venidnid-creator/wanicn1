# -*- coding: utf-8 -*-
"""Clickable structural plan of one level.

Click a column, beam or slab panel to remove it; click its dashed outline
to bring it back. After a calculation the elements are coloured by result
(green = passes, red = fails) and carry their marks.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

S = 60.0                      # pixels per metre
KIND, KEY = 0, 1              # item data slots

C_GRID = QColor("#9aa5b1")
C_PANEL = QColor(120, 170, 220, 70)
C_BEAM = QColor("#2b5797")
C_COL = QColor("#333333")
C_OK = QColor("#2e7d32")
C_NG = QColor("#c62828")
C_GONE = QColor("#b0b0b0")


class PlanView(QGraphicsView):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setBackgroundBrush(QColor("#fbfbfb"))
        self.building = None
        self.level = None
        self.result = None

    # -- data -------------------------------------------------------------------
    def set_model(self, building, level: str | None = None):
        self.building = building
        names = [lv.name for lv in building.levels]
        self.level = level if level in names else (names[0] if names else None)
        self.rebuild()

    def set_level(self, name: str):
        self.level = name
        self.rebuild()

    def set_result(self, result):
        self.result = result
        self.rebuild()

    # -- drawing ---------------------------------------------------------------
    @staticmethod
    def _p(x, y) -> QPointF:
        return QPointF(x * S, -y * S)

    def _status(self, kind: str, key: str):
        """(colour, mark) of an element from the last result, if any."""
        r = self.result
        if r is None:
            return None, ""
        lvl, _, name = key.partition(":")
        if kind == "beam":
            for x in r.beams:
                if x.level == lvl and f"{lvl}:{x.span}" == key:
                    return (C_OK if x.ok else C_NG), x.mark
        elif kind == "panel":
            for s in r.slabs:
                if s.level == lvl and s.panel == name:
                    return (C_OK if s.ok else C_NG), s.mark
        elif kind == "node":
            for c in r.columns:
                if c.node == key and c.segment.endswith(self.level or ""):
                    return (C_OK if c.ok else C_NG), c.mark
        return None, ""

    def rebuild(self):
        sc = self.scene()
        sc.clear()
        b = self.building
        if b is None or self.level is None:
            return
        xs, ys = b.xs, b.ys
        lvl = self.level
        font = QFont()
        font.setPointSizeF(8)
        # grid and bubbles
        pen = QPen(C_GRID, 1, Qt.DashDotLine)
        for i, x in enumerate(xs):
            sc.addLine(x * S, S * 0.8, x * S, -(ys[-1] + 0.8) * S, pen)
            sc.addEllipse(QRectF(x * S - 11, -(ys[-1] + 1.4) * S - 11, 22, 22), QPen(C_GRID))
            t = sc.addSimpleText(b.x_name(i), font)
            t.setPos(x * S - 4, -(ys[-1] + 1.4) * S - 8)
        for j, y in enumerate(ys):
            sc.addLine(-0.8 * S, -y * S, (xs[-1] + 0.8) * S, -y * S, pen)
            sc.addEllipse(QRectF(-1.4 * S - 11, -y * S - 11, 22, 22), QPen(C_GRID))
            t = sc.addSimpleText(b.y_name(j), font)
            t.setPos(-1.4 * S - 4, -y * S - 8)
        for a, c in zip(xs, xs[1:]):
            t = sc.addSimpleText(f"{c - a:.2f}", font)
            t.setPos((a + c) / 2 * S - 12, S * 0.9)
        for a, c in zip(ys, ys[1:]):
            t = sc.addSimpleText(f"{c - a:.2f}", font)
            t.setPos((xs[-1] + 0.9) * S, -(a + c) / 2 * S - 6)
        # panels
        present = set(b.panels(lvl))
        for j in range(len(ys) - 1):
            for i in range(len(xs) - 1):
                if not all(b.has_node(*n) for n in ((i, j), (i + 1, j), (i, j + 1), (i + 1, j + 1))):
                    continue
                key = b.panel_key(lvl, i, j)
                rect = QRectF(self._p(xs[i], ys[j + 1]), self._p(xs[i + 1], ys[j])).adjusted(6, 6, -6, -6)
                if (i, j) in present:
                    colour, mark = self._status("panel", key)
                    fill = QColor(colour) if colour else C_PANEL
                    fill.setAlpha(60)
                    it = sc.addRect(rect, QPen(Qt.NoPen), QBrush(fill))
                    if mark:
                        t = sc.addSimpleText(mark, font)
                        t.setPos(rect.center() - QPointF(8, 6))
                elif key in b.skip_panels:
                    it = sc.addRect(rect, QPen(C_GONE, 1, Qt.DashLine), QBrush(Qt.NoBrush))
                else:
                    continue
                it.setData(KIND, "panel")
                it.setData(KEY, key)
                it.setToolTip(f"พื้น {key}")
        # beams
        for j, y in enumerate(ys):
            for i in range(len(xs) - 1):
                self._beam(sc, (i, j), (i + 1, j), font)
        for i, x in enumerate(xs):
            for j in range(len(ys) - 1):
                self._beam(sc, (i, j), (i, j + 1), font)
        # columns
        cw, ch = b.column_width, b.column_depth
        for j, y in enumerate(ys):
            for i, x in enumerate(xs):
                name = b.node_name(i, j)
                w, h = max(cw, 0.25) * S, max(ch, 0.25) * S
                rect = QRectF(x * S - w / 2, -y * S - h / 2, w, h)
                if b.has_node(i, j):
                    colour, mark = self._status("node", name)
                    it = sc.addRect(rect, QPen(Qt.black), QBrush(colour or C_COL))
                    if mark:
                        t = sc.addSimpleText(mark, font)
                        t.setPos(rect.topRight() + QPointF(2, -12))
                else:
                    it = sc.addRect(rect, QPen(C_GONE, 1, Qt.DashLine), QBrush(Qt.NoBrush))
                it.setData(KIND, "node")
                it.setData(KEY, name)
                it.setToolTip(f"เสา {name}")
                it.setZValue(3)
        sc.setSceneRect(sc.itemsBoundingRect().adjusted(-20, -20, 20, 20))
        self.fitInView(sc.sceneRect(), Qt.KeepAspectRatio)

    def _beam(self, sc, a, c, font):
        b = self.building
        if not (b.has_node(*a) and b.has_node(*c)):
            return
        key = b.beam_key(self.level, a, c)
        p1, p2 = self._p(b.xs[a[0]], b.ys[a[1]]), self._p(b.xs[c[0]], b.ys[c[1]])
        if b.has_beam(self.level, a, c):
            colour, mark = self._status("beam", key)
            it = sc.addLine(p1.x(), p1.y(), p2.x(), p2.y(), QPen(colour or C_BEAM, 7, Qt.SolidLine, Qt.FlatCap))
            if mark:
                t = sc.addSimpleText(mark, font)
                mid = (p1 + p2) / 2
                t.setPos(mid + (QPointF(-8, -16) if p1.y() == p2.y() else QPointF(6, -6)))
        else:
            it = sc.addLine(p1.x(), p1.y(), p2.x(), p2.y(), QPen(C_GONE, 3, Qt.DashLine))
        it.setData(KIND, "beam")
        it.setData(KEY, key)
        it.setToolTip(f"คาน {key}")
        it.setZValue(2)

    # -- interaction -----------------------------------------------------------
    def item_at(self, pos):
        for it in self.items(pos):
            if it.data(KIND):
                return it
        return None

    def toggle(self, kind: str, key: str):
        self.building.toggle(kind, key)
        self.result = None
        self.rebuild()
        self.changed.emit()

    def mousePressEvent(self, event):
        it = self.item_at(event.position().toPoint())
        if it is not None and self.building is not None:
            self.toggle(it.data(KIND), it.data(KEY))
            return
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        f = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(f, f)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.scene() and not self.scene().sceneRect().isEmpty():
            self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)
