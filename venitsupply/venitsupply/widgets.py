# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared widgets: Buddhist-era date edit, form dialog, tables, style."""
from __future__ import annotations

import datetime as _dt

from PySide6.QtCore import QDate, QLocale, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCalendarWidget, QComboBox, QDialog,
                               QDialogButtonBox, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
                               QScrollArea, QSpinBox, QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout,
                               QWidget)

from .i18n import T

NAVY, ORANGE, BRASS, IVORY, MUTED = "#0F2A44", "#C46420", "#C9A14A", "#F6F3EC", "#55657A"

SARABUN = ("TH Sarabun New", "TH SarabunPSK", "Sarabun", "TH Sarabun PSK")
OTHER_THAI = ("Leelawadee UI", "Leelawadee", "Tahoma", "Loma", "Laksaman", "Noto Sans Thai")
UI = {"scale": 1.0}


def thai_digit_font(family: str) -> bool:
    """True when the font (regular or bold face) draws 0–9 as Thai digits ๐–๙ — e.g. «IT๙» variants.
    Such a font makes some numbers in the program Thai and others Arabic, so it is not used for the screens."""
    try:
        from PySide6.QtGui import QFont, QPainterPath
        for bold in (False, True):
            f = QFont(family, 20)
            f.setBold(bold)
            a, b = QPainterPath(), QPainterPath()
            a.addText(0, 0, f, "0123456789")
            b.addText(0, 0, f, "๐๑๒๓๔๕๖๗๘๙")
            ra, rb = a.boundingRect(), b.boundingRect()
            if a.elementCount() == b.elementCount() and abs(ra.width() - rb.width()) < 0.5 \
                    and abs(ra.height() - rb.height()) < 0.5:
                return True
    except Exception:  # noqa: BLE001
        return False
    return False


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
        sar = next((f for f in SARABUN if f in have and not thai_digit_font(f)), None)
        if sar:
            fam, base = sar, 16.0
        else:
            fam = next((f for f in OTHER_THAI if f in have and not thai_digit_font(f)), "Tahoma")
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
QMenuBar {{ font-size: {round(m["base"] * 1.15, 1)}pt; padding: 2px; }}
QMenuBar::item {{ padding: 4px 14px; }}
QMenu {{ font-size: {round(m["base"] * 1.1, 1)}pt; }}
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


THAI_MONTHS = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม",
               "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
THAI_MONTHS_SHORT = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
BE_MIN, BE_MAX = 2400, 2700


def parse_be(text: str):
    """«1/10/2569», «1-10-69», «๑/๑๐/๒๕๖๙», «1 ต.ค. 2569», «1 ตุลาคม 2569» → date (ค.ศ.) or None.

    The year is พ.ศ.; two digits mean 25xx; a ค.ศ. year (1900–2199) is converted. Out of range → None."""
    import re as _re
    t = (text or "").strip().translate(str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789"))
    if not t:
        return None
    m = _re.match(r"^(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{2,4})$", t)
    if m:
        d, mo, y = (int(x) for x in m.groups())
    else:
        m = _re.match(r"^(\d{1,2})\s*([^\d\s]+)\s*(\d{2,4})$", t)
        if not m:
            return None
        name = m.group(2).replace(" ", "")
        mo = next((i + 1 for i, (a, b) in enumerate(zip(THAI_MONTHS, THAI_MONTHS_SHORT))
                   if name in (a, b, b.replace(".", ""))), None)
        if mo is None:
            return None
        d, y = int(m.group(1)), int(m.group(3))
    if y < 100:
        y += 2500
    if 1900 <= y < 2200:          # พิมพ์เป็น ค.ศ. — แปลงให้
        y += 543
    if not (BE_MIN <= y <= BE_MAX):
        return None
    try:
        return _dt.date(y - 543, mo, d)
    except ValueError:
        return None


def fmt_be(d) -> str:
    return f"{d.day}/{d.month}/{d.year + 543}" if d else ""


class _BECalendar(QFrame):
    """Popup calendar: Thai month names and พ.ศ. year (QCalendarWidget's own header shows ค.ศ., so it is hidden)."""

    def __init__(self, owner):
        super().__init__(owner, Qt.Popup)
        self.owner = owner
        self.setFrameShape(QFrame.StyledPanel)
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        prev, nxt = QToolButton(), QToolButton()
        prev.setText("‹")
        nxt.setText("›")
        self.month = QComboBox()
        self.month.addItems(THAI_MONTHS)
        self.year = QSpinBox()
        self.year.setRange(BE_MIN, BE_MAX)
        self.year.setPrefix("พ.ศ. ")
        for w in (prev, self.month, self.year, nxt):
            top.addWidget(w)
        lay.addLayout(top)
        self.cal = QCalendarWidget()
        self.cal.setNavigationBarVisible(False)
        self.cal.setLocale(QLocale(QLocale.Thai, QLocale.Thailand))
        self.cal.setFirstDayOfWeek(Qt.Sunday)
        self.cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.cal.setGridVisible(True)
        lay.addWidget(self.cal)
        today = QPushButton(T("วันนี้"))
        lay.addWidget(today)
        prev.clicked.connect(lambda: self.cal.showPreviousMonth())
        nxt.clicked.connect(lambda: self.cal.showNextMonth())
        self.month.currentIndexChanged.connect(self._go)
        self.year.valueChanged.connect(self._go)
        self.cal.currentPageChanged.connect(self._page)
        self.cal.clicked.connect(self._pick)
        self.cal.activated.connect(self._pick)
        today.clicked.connect(lambda: self._pick(QDate.currentDate()))

    def open_at(self, q: QDate):
        self.cal.setSelectedDate(q)
        self.cal.setCurrentPage(q.year(), q.month())
        self._page(q.year(), q.month())
        self.adjustSize()
        self.move(self.owner.mapToGlobal(self.owner.rect().bottomLeft()))
        self.show()
        self.cal.setFocus()

    def _page(self, y, m):
        for w, v in ((self.month, m - 1), (self.year, y + 543)):
            w.blockSignals(True)
            (w.setCurrentIndex if w is self.month else w.setValue)(v)
            w.blockSignals(False)

    def _go(self, *_):
        self.cal.setCurrentPage(self.year.value() - 543, self.month.currentIndex() + 1)

    def _pick(self, q):
        self.owner.setDate(q)
        self.hide()


class ThaiDateEdit(QWidget):
    """Date field in พ.ศ.: type «1/10/2569» (also 1/10/69, ๑/๑๐/๒๕๖๙, 1 ต.ค. 2569) or pick from a Thai calendar.
    Empty / invalid values never fall back to a strange year: an invalid entry is refused with a message
    and the previous date is kept."""

    dateChanged = Signal(QDate)

    def __init__(self, value=None, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("วัน/เดือน/ปี พ.ศ. เช่น 1/10/2569")
        self.edit.setToolTip(T("พิมพ์วันที่เป็น พ.ศ. เช่น 1/10/2569 หรือ 1/10/69 หรือกดปุ่มปฏิทิน"))
        self.edit.setMinimumWidth(self.edit.fontMetrics().horizontalAdvance("30/12/25690") + 16)   # ไม่ให้ตัดเหลือ «69»
        self.btn = QToolButton()
        self.btn.setText("📅")
        self.btn.setToolTip(T("เลือกจากปฏิทิน"))
        lay.addWidget(self.edit, 1)
        lay.addWidget(self.btn)
        self.thai = QLabel()
        self.thai.setObjectName("hint")
        lay.addWidget(self.thai)
        self._d = _dt.date.today()
        self._popup = None
        self.edit.editingFinished.connect(self._typed)
        self.btn.clicked.connect(self._show_cal)
        self.set_iso(value or _dt.date.today().isoformat())

    # ---- API (compatible with the former QDateEdit subclass)
    def date(self) -> QDate:
        return QDate(self._d.year, self._d.month, self._d.day)

    def setDate(self, q):
        d = _dt.date(q.year(), q.month(), q.day()) if isinstance(q, QDate) else q
        if d is None or not (BE_MIN <= d.year + 543 <= BE_MAX):
            return
        changed = d != self._d
        self._d = d
        self._show()
        if changed:
            self.dateChanged.emit(self.date())

    def iso(self) -> str:
        return self._d.isoformat()

    def set_iso(self, s):
        try:
            d = _dt.date.fromisoformat(str(s)[:10]) if s else _dt.date.today()
        except ValueError:
            d = _dt.date.today()
        if not (BE_MIN <= d.year + 543 <= BE_MAX):
            d = _dt.date.today()
        self.setDate(d)
        self._show()

    # ---- internals
    def _show(self):
        self.edit.setText(fmt_be(self._d))
        self.edit.setStyleSheet("")
        self.thai.setText(f"{THAI_MONTHS_SHORT[self._d.month - 1]}")

    def _typed(self):
        if getattr(self, "_warning", False) or self.edit.text().strip() == fmt_be(self._d):
            return
        d = parse_be(self.edit.text())
        if d is None:
            self._warning = True
            self.edit.setStyleSheet("border: 2px solid #C72B1E;")
            QMessageBox.warning(self, T("วันที่ไม่ถูกต้อง"),
                                T(f"«{self.edit.text()}» ไม่ใช่วันที่ที่ถูกต้อง — พิมพ์เป็น วัน/เดือน/ปี พ.ศ. "
                                  f"เช่น 1/10/2569 (ปี พ.ศ. {BE_MIN}–{BE_MAX})"))
            self._warning = False
            self._show()
            return
        self.setDate(d)

    def _show_cal(self):
        if self._popup is None:
            self._popup = _BECalendar(self)
        self._popup.open_at(self.date())


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
