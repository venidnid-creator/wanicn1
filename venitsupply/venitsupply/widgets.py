# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared widgets: Buddhist-era date edit, form dialog, tables, style."""
from __future__ import annotations

import datetime as _dt

from PySide6.QtCore import QDate, QDateTime, Qt
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDateEdit, QDialog,
                               QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QHeaderView, QLineEdit, QMessageBox, QPlainTextEdit,
                               QTableWidget, QTableWidgetItem)

from .i18n import T

NAVY, ORANGE, BRASS, IVORY, MUTED = "#0F2A44", "#C46420", "#C9A14A", "#F6F3EC", "#55657A"

STYLE = f"""
* {{ font-family: 'TH Sarabun New','Laksaman','Loma','Tahoma'; font-size: 15pt; }}
QMainWindow, QWidget#page {{ background: {IVORY}; }}
QListWidget#nav {{ background: {NAVY}; color: white; border: none; padding-top: 8px; }}
QListWidget#nav::item {{ padding: 10px 14px; border-left: 4px solid transparent; }}
QListWidget#nav::item:selected {{ background: #1B3D60; border-left: 4px solid {ORANGE}; color: white; }}
QLabel#title {{ font-size: 24pt; font-weight: bold; color: {NAVY}; }}
QLabel#hint {{ color: {MUTED}; }}
QFrame#card {{ background: white; border: 1px solid #DCD6C8; border-radius: 10px; }}
QLabel#cardvalue {{ font-size: 22pt; font-weight: bold; color: {NAVY}; }}
QLabel#cardlabel {{ color: {MUTED}; }}
QPushButton {{ background: white; border: 1px solid #C8C0AE; border-radius: 6px; padding: 4px 12px; }}
QPushButton:hover {{ border-color: {ORANGE}; }}
QPushButton#primary {{ background: {ORANGE}; color: white; border: none; font-weight: bold; }}
QTableWidget {{ background: white; gridline-color: #E4DFD3; selection-background-color: #F3D9C4;
               selection-color: black; }}
QHeaderView::section {{ background: #E8EEF5; color: {NAVY}; padding: 4px; border: none;
                        border-right: 1px solid #D0D8E2; font-weight: bold; }}
QGroupBox {{ font-weight: bold; color: {NAVY}; border: 1px solid #DCD6C8; border-radius: 8px;
             margin-top: 14px; padding-top: 10px; background: white; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
"""


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
        self.setMinimumWidth(560)
        self.w = {}
        lay = QFormLayout(self)
        values = values or {}
        for key, label, kind, *extra in fields:
            extra = extra[0] if extra else None
            v = values.get(key)
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
                w.setFixedHeight(70)
            else:
                w = QLineEdit(str(v or ""))
                if hints and key in hints:
                    w.setPlaceholderText(hints[key])
            self.w[key] = (kind, w)
            lay.addRow(T(label), w)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(T("บันทึก"))
        bb.button(QDialogButtonBox.Ok).setObjectName("primary")
        bb.button(QDialogButtonBox.Cancel).setText(T("ยกเลิก"))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addRow(bb)

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
