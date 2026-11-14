# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ — ReadWanicn2027
"""Fit any screen: tool rows that wrap onto a new line instead of running past the
window's edge, and windows that never open larger than the screen they are on
(laptops, 1366×768, Windows scaling 125–175 %)."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QDialog, QLayout, QMainWindow, QSizePolicy, QStyle, QWidget


class FlowLayout(QLayout):
    """Left to right, then onto the next line (Qt's flow-layout example)."""

    def __init__(self, parent=None, margin=0, hspacing=2, vspacing=2):
        super().__init__(parent)
        self._items = []
        self._h, self._v = hspacing, vspacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def addStretch(self, _stretch=0):        # a flow has no stretch: lets QHBoxLayout code run as is
        pass

    def addSpacing(self, size):
        from PySide6.QtWidgets import QSpacerItem
        self.addItem(QSpacerItem(size, 1))

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for it in self._items:
            size = size.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do(self, rect, test):
        m = self.contentsMargins()
        r = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line = r.x(), r.y(), 0
        for it in self._items:
            w = it.widget()
            if w is not None and w.isHidden():
                continue
            hint = it.sizeHint()
            nx = x + hint.width() + self._h
            if nx - self._h > r.right() and line > 0:
                x, y = r.x(), y + line + self._v
                nx, line = x + hint.width() + self._h, 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), hint))
            x, line = nx, max(line, hint.height())
        return y + line - rect.y() + m.bottom()


def fit_to_screen(w: QWidget, max_w: float = 0.96, max_h: float = 0.92, centre: bool = True) -> None:
    scr = w.screen()
    if scr is None:
        return
    av = scr.availableGeometry()
    width, height = min(w.width(), int(av.width() * max_w)), min(w.height(), int(av.height() * max_h))
    if (width, height) != (w.width(), w.height()):
        w.resize(width, height)
    if centre or not av.contains(w.frameGeometry()):
        w.move(av.x() + (av.width() - w.width()) // 2, av.y() + (av.height() - w.height()) // 2)


class ScreenFit(QObject):
    """Every dialog and main window, the first time it shows, is no larger than the screen."""

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Show and isinstance(obj, (QDialog, QMainWindow)) and obj.isWindow() \
                and not obj.property("_fitted"):
            obj.setProperty("_fitted", True)
            fit_to_screen(obj, centre=isinstance(obj, QMainWindow))
            from . import lang
            if lang.current() == "en" and isinstance(obj, QDialog):
                lang.apply(obj)
        return False


_filter = None


def install(app) -> None:
    global _filter
    if _filter is None:
        _filter = ScreenFit(app)
        app.installEventFilter(_filter)


del QSizePolicy, QStyle
