# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ปรับหน้าจอให้พอดีทุกเครื่อง — the side panels fit any screen and any
Windows scaling (100–175 %): every row of buttons wraps onto more lines
instead of running off the panel's edge, drop-down lists do not force the
panel wider than their shortest sensible width, and the panel scrolls up
and down when it is taller than the screen.

``fit(widget)`` does all three and returns what to put in the dock (the
widget inside a scroll area)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractButton, QAbstractSpinBox, QBoxLayout, QComboBox, QFormLayout, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QLayout, QLineEdit, QScrollArea, QSizePolicy,
                               QWidget)

#: widgets a wrapped row may hold (an input box in a row stays a row: its label must stay beside it)
_ROW_KINDS = (QAbstractButton, QLabel, QComboBox, QLineEdit, QAbstractSpinBox)
_DONE = "_wanic_fitted"


def _row_widgets(lay) -> list | None:
    """The widgets of a horizontal row that can wrap, or None."""
    out = []
    for i in range(lay.count()):
        it = lay.itemAt(i)
        if it.spacerItem() is not None:
            continue
        if it.layout() is not None:
            return None
        w = it.widget()
        if w is None:
            return None
        if not isinstance(w, _ROW_KINDS):
            return None
        out.append(w)
    buttons = sum(1 for w in out if isinstance(w, QAbstractButton))
    return out if buttons >= 1 and len(out) >= 2 else None


def _replace(parent_lay, child_lay, box: QWidget) -> bool:
    """Put ``box`` where ``child_lay`` sits in ``parent_lay``."""
    if isinstance(parent_lay, QBoxLayout):
        for i in range(parent_lay.count()):
            if parent_lay.itemAt(i).layout() is child_lay:
                st = parent_lay.stretch(i)
                parent_lay.takeAt(i)
                parent_lay.insertWidget(i, box, st)
                return True
    elif isinstance(parent_lay, QFormLayout):
        for r in range(parent_lay.rowCount()):
            for role in (QFormLayout.FieldRole, QFormLayout.SpanningRole, QFormLayout.LabelRole):
                it = parent_lay.itemAt(r, role)
                if it is not None and it.layout() is child_lay:
                    parent_lay.removeItem(it)
                    parent_lay.setWidget(r, role, box)
                    return True
    elif isinstance(parent_lay, QGridLayout):
        for i in range(parent_lay.count()):
            if parent_lay.itemAt(i).layout() is child_lay:
                r, c, rs, cs = parent_lay.getItemPosition(i)
                parent_lay.takeAt(i)
                parent_lay.addWidget(box, r, c, rs, cs)
                return True
    return False


def _parent_layout(lay):
    p = lay.parent()
    return p if isinstance(p, QLayout) else None


def reflow_rows(root: QWidget) -> int:
    """Every horizontal row of buttons under ``root`` becomes a row that
    wraps (FlowLayout). A row that is a widget's own layout is wrapped in
    place. Returns how many rows were changed."""
    from views.tray import FlowLayout
    n = 0
    lays = [l for l in root.findChildren(QHBoxLayout)]
    for lay in lays:
        ws = _row_widgets(lay)
        if not ws:
            continue
        owner = lay.parentWidget()
        parent = _parent_layout(lay)
        if parent is None:
            # the row IS the layout of a widget (e.g. a button bar): rebuild it in place
            if owner is None or owner.layout() is not lay:
                continue
            margins = lay.contentsMargins()
            for w in ws:
                lay.removeWidget(w)
            QWidget().setLayout(lay)                 # detach the old layout
            fl = FlowLayout(owner, spacing=4)
            fl.setContentsMargins(margins)
            for w in ws:
                fl.addWidget(w)
            n += 1
            continue
        box = QWidget()
        fl = FlowLayout(box, spacing=4)
        for w in ws:
            lay.removeWidget(w)
            fl.addWidget(w)
        if _replace(parent, lay, box):
            lay.setParent(None)
            n += 1
        else:                                         # could not place it: put the widgets back
            for w in ws:
                fl.removeWidget(w)
                lay.addWidget(w)
            box.deleteLater()
    return n


def relax_combos(root: QWidget, chars: int = 12) -> None:
    """A drop-down list is as wide as its longest item by default — on a
    narrow panel that pushes everything off the edge; let it shrink."""
    for cb in root.findChildren(QComboBox):
        cb.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        cb.setMinimumContentsLength(chars)
        sp = cb.sizePolicy()
        sp.setHorizontalPolicy(QSizePolicy.Expanding)
        cb.setSizePolicy(sp)


def wrap_labels(root: QWidget) -> None:
    """Long one-line labels (hints) wrap instead of widening the panel."""
    for lab in root.findChildren(QLabel):
        if not lab.wordWrap() and len(lab.text()) > 60 and "\n" not in lab.text():
            lab.setWordWrap(True)


def wrap_forms(root: QWidget) -> None:
    """A form puts its label above the field when the two do not fit on
    one line (instead of pushing the panel wider)."""
    for fl in root.findChildren(QFormLayout):
        fl.setRowWrapPolicy(QFormLayout.WrapLongRows)
        fl.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)


def fit(widget: QWidget) -> QWidget:
    """Make a side panel fit any screen; returns the widget to dock."""
    if getattr(widget, _DONE, False):
        return widget
    try:
        reflow_rows(widget)
        relax_combos(widget)
        wrap_labels(widget)
        wrap_forms(widget)
    except Exception:                                 # noqa: BLE001 - fitting never breaks a panel
        pass
    setattr(widget, _DONE, True)
    if isinstance(widget, QScrollArea):
        widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        return widget
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setWidget(widget)
    setattr(scroll, _DONE, True)
    return scroll


# ---- dialogs ---------------------------------------------------------------------------------

def fit_dialog(dlg) -> None:
    """A window larger than the screen (a 1366×768 laptop, or Windows at
    125–150 %) is made to fit: its rows of buttons wrap, its forms put the
    label above the field, its fixed minimum size is capped to the screen
    (the tables in it shrink and scroll) and it is moved onto the screen so
    the OK / Cancel buttons are always visible."""
    if getattr(dlg, _DONE, False):
        return
    setattr(dlg, _DONE, True)
    scr = dlg.screen() if hasattr(dlg, "screen") else None
    if scr is None:
        return
    av = scr.availableGeometry()
    maxw, maxh = int(av.width() * 0.96), int(av.height() * 0.92)
    try:
        reflow_rows(dlg)
        relax_combos(dlg)
        wrap_forms(dlg)
    except Exception:                                 # noqa: BLE001
        pass
    mn = dlg.minimumSize()
    if mn.width() > maxw or mn.height() > maxh:
        dlg.setMinimumSize(min(mn.width(), maxw), min(mn.height(), maxh))
    w = min(max(dlg.width(), dlg.minimumWidth()), maxw)
    h = min(max(dlg.height(), dlg.minimumHeight()), maxh)
    dlg.resize(w, h)
    g = dlg.frameGeometry()
    x = min(max(g.x(), av.x()), av.right() - w)
    y = min(max(g.y(), av.y()), av.bottom() - h)
    dlg.move(max(x, av.x()), max(y, av.y()))


class DialogFitter:
    """An application-wide filter: every dialog is fitted to the screen the
    first time it shows."""

    def __init__(self):
        from PySide6.QtCore import QEvent, QObject

        class _F(QObject):
            def eventFilter(self, obj, ev):           # noqa: N802 - Qt override
                if ev.type() == QEvent.Show:
                    from PySide6.QtWidgets import QDialog
                    if isinstance(obj, QDialog) and not getattr(obj, _DONE, False):
                        try:
                            fit_dialog(obj)
                        except Exception:             # noqa: BLE001 - never stops a dialog
                            pass
                return False
        self.f = _F()


_FITTER = None


def install(app) -> None:
    """Fit every dialog of the application to the screen."""
    global _FITTER
    if _FITTER is None:
        _FITTER = DialogFitter()
        app.installEventFilter(_FITTER.f)


def widen_docks(win, share: float = 0.42, at_least: int = 470) -> None:
    """On a small or scaled screen the side panels start too narrow for
    their buttons: give them about 42 % of the window (never less than
    ``at_least`` logical px when the window allows), once at start."""
    from PySide6.QtWidgets import QDockWidget
    docks = [d for d in win.findChildren(QDockWidget)
             if d.isVisible() and not d.isFloating() and win.dockWidgetArea(d) == Qt.RightDockWidgetArea]
    if not docks:
        return
    want = max(int(win.width() * share), min(at_least, int(win.width() * 0.5)))
    if docks[0].width() >= want:
        return
    win.resizeDocks([docks[0]], [want], Qt.Horizontal)
