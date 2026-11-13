# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared widgets: Buddhist-era date edit, form dialog, tables, style."""
from __future__ import annotations

import datetime as _dt

from PySide6.QtCore import QDate, QDateTime, Qt
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDateEdit, QDialog,
                               QDialogButtonBox, QDoubleSpinBox, QFrame, QGridLayout,
                               QHeaderView, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                               QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from .i18n import T

NAVY, ORANGE, BRASS, IVORY, MUTED = "#0F2A44", "#C46420", "#C9A14A", "#F6F3EC", "#55657A"

SARABUN = ("TH Sarabun New", "TH SarabunPSK", "Sarabun", "TH Sarabun PSK")
OTHER_THAI = ("Leelawadee UI", "Leelawadee", "Tahoma", "Loma", "Laksaman", "Noto Sans Thai")
UI = {"scale": 1.0}


def ui_metrics() -> dict:
    """Font family and sizes that fit this computer's screen.

    TH Sarabun has small glyphs (needs ~15 pt); Tahoma/Leelawadee are big (~10 pt). The size is
    then scaled to the screen's available height (logical pixels, so Windows display scaling
    such as 125 % / 150 % is already included)."""
    fam = SARABUN[0]
    base = 15.0
    try:
        from PySide6.QtGui import QFontDatabase, QGuiApplication
        have = set(QFontDatabase.families())
        sar = next((f for f in SARABUN if f in have), None)
        if sar:
            fam, base = sar, 16.0
        else:
            fam = next((f for f in OTHER_THAI if f in have), "Tahoma")
            base = 11.5
        scr = QGuiApplication.primaryScreen()
        if scr is not None:
            h = scr.availableGeometry().height()
            base *= max(1.0, min(1.2, h / 950.0))     # never smaller than the base
    except Exception:  # noqa: BLE001 — no application yet
        pass
    return dict(family=fam, base=round(base, 1), title=round(base * 1.6, 1), value=round(base * 1.45, 1),
                small=round(base * 0.8, 1))


def make_style(m=None) -> str:
    m = m or ui_metrics()
    UI["scale"] = m["base"] / 15.0
    return f"""
* {{ font-family: '{m["family"]}','TH Sarabun New','Leelawadee UI','Tahoma','Loma'; font-size: {m["base"]}pt; }}
QMainWindow, QWidget#page {{ background: {IVORY}; }}
QListWidget#nav {{ background: {NAVY}; color: white; border: none; padding-top: 6px; }}
QListWidget#nav::item {{ padding: 8px 12px; border-left: 4px solid transparent; }}
QListWidget#nav::item:selected {{ background: #1B3D60; border-left: 4px solid {ORANGE}; color: white; }}
QLabel#title {{ font-size: {m["title"]}pt; font-weight: bold; color: {NAVY}; }}
QLabel#hint {{ color: {MUTED}; }}
QFrame#card {{ background: white; border: 1px solid #DCD6C8; border-radius: 10px; }}
QLabel#cardvalue {{ font-size: {m["value"]}pt; font-weight: bold; color: {NAVY}; }}
QLabel#cardlabel {{ color: {MUTED}; }}
QPushButton {{ background: white; border: 1px solid #C8C0AE; border-radius: 6px; padding: 3px 10px; }}
QPushButton:hover {{ border-color: {ORANGE}; }}
QPushButton#primary {{ background: {ORANGE}; color: white; border: none; font-weight: bold; }}
QTableWidget {{ background: white; gridline-color: #E4DFD3; selection-background-color: #F3D9C4;
               selection-color: black; }}
QHeaderView::section {{ background: #E8EEF5; color: {NAVY}; padding: 3px; border: none;
                        border-right: 1px solid #D0D8E2; font-weight: bold; }}
QGroupBox {{ font-weight: bold; color: {NAVY}; border: 1px solid #DCD6C8; border-radius: 8px;
             margin-top: 12px; padding-top: 8px; background: white; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
QSpinBox {{ min-width: 6.5em; font-size: {round(m["base"] * 1.12, 1)}pt; font-weight: bold;
            color: {NAVY}; padding: 2px 4px; }}
QComboBox {{ min-width: 6em; }}
QMenuBar {{ font-size: {m["base"]}pt; }}
"""


STYLE = make_style(dict(family=SARABUN[0], base=15.0, title=24.0, value=22.0, small=12.0))


def pt(n: float) -> float:
    """A font size designed for the 15 pt layout, scaled to this computer."""
    return round(n * UI["scale"], 1)


def px(n: float) -> int:
    """A size designed for the 15 pt layout, scaled to this computer."""
    return int(round(n * UI["scale"]))


def scrolled(widget):
    """*widget* inside a frameless scroll area: it fills the space when there is room and
    scrolls on a small or scaled screen instead of pushing the window off the screen."""
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.NoFrame)
    sa.setWidget(widget)
    return sa


def fit_to_screen(w, width, height, maximize_if_small=False):
    """Resize *w* to (width, height) but never larger than 95 % of the available screen,
    and centre it there."""
    from PySide6.QtGui import QGuiApplication
    scr = (w.screen() if hasattr(w, "screen") and w.screen() else None) or QGuiApplication.primaryScreen()
    if scr is None:
        w.resize(width, height)
        return
    g = scr.availableGeometry()
    ww, hh = min(width, int(g.width() * 0.95)), min(height, int(g.height() * 0.92))
    w.resize(ww, hh)
    w.move(g.x() + (g.width() - ww) // 2, g.y() + max(0, (g.height() - hh) // 2))
    if maximize_if_small and (width > g.width() or height > g.height()):
        w.showMaximized()


class ThaiDateEdit(QDateEdit):
    """Date edit that shows and accepts the Buddhist-era year: 13/11/2569."""

    def __init__(self, value=None, parent=None):
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat("d/M/yyyy")
        self.set_iso(value or _dt.date.today().isoformat())

    def textFromDateTime(self, dt: QDateTime) -> str:  # noqa: N802 (Qt)
        d = dt.date()
        return f"{d.day()}/{d.month()}/{d.year() + 543}"

    def _parse(self, text):
        try:
            d, m, y = (int(x) for x in text.strip().split("/"))
            y = y - 543 if y > 2400 else y
            q = QDate(y, m, d)
            return q if q.isValid() else None
        except ValueError:
            return None

    def dateTimeFromText(self, text: str) -> QDateTime:  # noqa: N802 (Qt)
        q = self._parse(text)
        return QDateTime(q) if q else QDateTime(self.date())

    def validate(self, text, pos):
        return (QValidator.Acceptable if self._parse(text) else QValidator.Intermediate, text, pos)

    def iso(self) -> str:
        return self.date().toString("yyyy-MM-dd")

    def set_iso(self, s):
        q = QDate.fromString(str(s)[:10], "yyyy-MM-dd")
        if q.isValid():
            self.setDate(q)


class FormDialog(QDialog):
    """A dialog built from field specs ``(key, label, kind, extra)``.

    kinds: text, multi, num, money, int, date, combo (extra=list), edit-combo (extra=list).
    """

    def __init__(self, parent, title, fields, values=None, hints=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.w = {}
        outer = QVBoxLayout(self)
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setHorizontalSpacing(10)
        two = len(fields) > 9                     # long forms: two columns so they fit the screen
        values = values or {}
        row = col = 0
        for key, label, kind, *extra in fields:
            extra = extra[0] if extra else None
            w = self._make(key, kind, extra, values.get(key), hints)
            self.w[key] = (kind, w)
            lab = QLabel(T(label))
            wide = kind == "multi" and two
            if wide and col == 1:
                row, col = row + 1, 0
            grid.addWidget(lab, row, col * 2, Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(w, row, col * 2 + 1, 1, 3 if wide else 1)
            if two and not wide and col == 0:
                col = 1
            else:
                row, col = row + 1, 0
        grid.setColumnStretch(1, 1)
        if two:
            grid.setColumnStretch(3, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(T("บันทึก"))
        bb.button(QDialogButtonBox.Ok).setObjectName("primary")
        bb.button(QDialogButtonBox.Cancel).setText(T("ยกเลิก"))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)                       # always visible, outside the scroll area
        hint = body.sizeHint()
        fit_to_screen(self, max(px(560), hint.width() + 60), hint.height() + px(120))

    def _make(self, key, kind, extra, v, hints):
        if kind in ("num", "money", "int"):
            w = QDoubleSpinBox()
            w.setRange(0, 1e12)
            w.setDecimals(0 if kind == "int" else 2)
            w.setGroupSeparatorShown(True)
            w.setValue(float(v or 0))
        elif kind == "date":
            w = ThaiDateEdit(v)
        elif kind in ("combo", "edit-combo"):
            w = QComboBox()
            w.setEditable(kind == "edit-combo")
            for it in extra or []:
                if isinstance(it, tuple):
                    w.addItem(T(it[1]), it[0])
                else:
                    w.addItem(T(it), it)
            if v is not None:
                i = w.findData(v)
                if i >= 0:
                    w.setCurrentIndex(i)
                elif kind == "edit-combo":
                    w.setEditText(str(v))
        elif kind == "multi":
            w = QPlainTextEdit(str(v or ""))
            w.setFixedHeight(px(70))
        else:
            w = QLineEdit(str(v or ""))
            if hints and key in hints:
                w.setPlaceholderText(hints[key])
        return w

    def layout_form(self):
        """The grid that holds the fields (for callers that add a row)."""
        return self.findChild(QScrollArea).widget().layout()

    def add_row(self, widget):
        g = self.layout_form()
        g.addWidget(widget, g.rowCount(), 0, 1, 4)

    def values(self) -> dict:
        out = {}
        for k, (kind, w) in self.w.items():
            if kind in ("num", "money", "int"):
                out[k] = w.value()
            elif kind == "date":
                out[k] = w.iso()
            elif kind == "combo":
                out[k] = w.currentData()
            elif kind == "edit-combo":
                txt = w.currentText().strip()
                i = w.findText(txt)
                out[k] = w.itemData(i) if i >= 0 else txt
            elif kind == "multi":
                out[k] = w.toPlainText().strip()
            else:
                out[k] = w.text().strip()
        return out


def table(headers, stretch=1) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels([T(h) for h in headers])
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setAlternatingRowColors(False)
    t.verticalHeader().setVisible(False)
    h = t.horizontalHeader()
    h.setSectionResizeMode(QHeaderView.ResizeToContents)
    if stretch is not None:
        h.setSectionResizeMode(stretch, QHeaderView.Stretch)
    return t


def fill(t: QTableWidget, rows, ids=None, right=()):
    t.setRowCount(0)
    for r, row in enumerate(rows):
        t.insertRow(r)
        for c, v in enumerate(row):
            if isinstance(v, float):
                txt = f"{v:,.2f}"
            elif isinstance(v, int) and not isinstance(v, bool):
                txt = f"{v:,}"
            else:
                txt = "" if v is None else str(v)
            it = QTableWidgetItem(txt)
            if c in right or isinstance(v, (int, float)):
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if c == 0 and ids is not None:
                it.setData(Qt.UserRole, ids[r])
            t.setItem(r, c, it)


def selected_id(t: QTableWidget):
    r = t.currentRow()
    if r < 0 or t.item(r, 0) is None:
        return None
    return t.item(r, 0).data(Qt.UserRole)


def need_selection(parent):
    QMessageBox.information(parent, T("พัสดุเวนิช"), T("เลือกรายการก่อน"))


def error(parent, exc):
    QMessageBox.warning(parent, T("ข้อผิดพลาด"), str(exc))
