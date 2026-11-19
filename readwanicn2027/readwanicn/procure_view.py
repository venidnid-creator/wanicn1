# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ — ReadWanicn2027
"""The window for ว651 · ว124 · ว78: take in the bill, enter the prices,
check the lines, the work plan and the domestic-material plan, write the reports."""
from __future__ import annotations

import re
from pathlib import Path

import datetime as dt

from PySide6.QtCore import QDate, QLocale, QSettings, QStandardPaths, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCalendarWidget, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget, QToolButton, QVBoxLayout, QWidget,
)

from . import procure as P
from . import procure_report as R

IMPORT_FILTER = ("ใบแจ้งปริมาณงาน (*.xls *.xlsx *.xlsm *.csv *.docx *.pdf);;"
                 "ตารางคำนวณ (*.xls *.xlsx *.xlsm *.csv);;เอกสาร (*.docx);;PDF (*.pdf);;ทุกไฟล์ (*)")
PROJECT_FILTER = "งานปรับลดราคา (*.rwprice.json);;ทุกไฟล์ (*)"


REPORT_LABEL = {"651": "รายงาน ว651", "124": "รายงาน ว124", "work": "แผนปฏิบัติงาน", "78": "รายงาน ว78"}
SHORT_LABEL = {"651": "ว651", "124": "ว124", "work": "แผนปฏิบัติงาน", "78": "ว78"}
REPORT_NAME = {"651": "ว651 ปรับลดราคา", "124": "ว124 แผนการทำงาน", "work": "แผนปฏิบัติงาน",
               "78": "ว78 แผนการใช้พัสดุในประเทศ"}


def store_dir() -> Path:
    """Where the imported bills are kept (บันทึกข้อมูลไว้)."""
    base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) or str(Path.home() / ".readwanicn")
    d = Path(base) / "ปรับลดราคา"
    d.mkdir(parents=True, exist_ok=True)
    return d


def safe_name(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]+', " ", s or "งาน").strip()
    return (s[:60] or "งาน").strip()


class MoneyEdit(QLineEdit):
    """A field for baht: shows 4,831,709.89, takes ๑๒๓ or 1,234."""

    def __init__(self, value=0.0, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignRight)
        self.set_value(value)
        self.editingFinished.connect(lambda: self.set_value(self.value()))

    def value(self) -> float:
        return P.num(self.text()) or 0.0

    def set_value(self, v):
        self.setText(P.money(v) if v else "")


class ThaiDateEdit(QWidget):
    """A date shown as «14 พฤศจิกายน 2569», chosen from a calendar; today when nothing is set."""

    changed = Signal(str)                 # 'YYYY-MM-DD'

    def __init__(self, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        self.view = QLineEdit()
        self.view.setReadOnly(True)
        self.view.setPlaceholderText("กด 📅 เพื่อเลือกวันที่")
        h.addWidget(self.view, 1)
        pick = QToolButton()
        pick.setText("📅")
        pick.setToolTip("เลือกวันที่จากปฏิทิน")
        pick.clicked.connect(self.choose)
        h.addWidget(pick)
        today = QToolButton()
        today.setText("วันนี้")
        today.clicked.connect(lambda: self.set_iso(dt.date.today().isoformat(), emit=True))
        h.addWidget(today)
        self._iso = ""
        self.view.mousePressEvent = lambda _e: self.choose()

    def iso(self) -> str:
        return self._iso

    def set_iso(self, iso: str, emit=False):
        self._iso = iso or ""
        self.view.setText(P.thai_date(self._iso) if self._iso else "")
        if emit:
            self.changed.emit(self._iso)

    def choose(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("เลือกวันที่")
        v = QVBoxLayout(dlg)
        cal = QCalendarWidget()
        cal.setGridVisible(True)
        cal.setLocale(QLocale(QLocale.Thai, QLocale.Thailand))
        cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        cal.setStyleSheet("QCalendarWidget QAbstractItemView { color:#111; background:#ffffff;"
                          " selection-background-color:#1f78c8; selection-color:white; }"
                          " QCalendarWidget QWidget#qt_calendar_navigationbar { background:#1f4e79; min-height:34px; }"
                          " QCalendarWidget QToolButton { color:white; background:transparent; border:none;"
                          " font-size:12pt; font-weight:bold; padding:2px 8px; }"
                          " QCalendarWidget QToolButton:hover { background:#2e75b6; border-radius:4px; }"
                          " QCalendarWidget QToolButton::menu-indicator { image:none; width:0; }"
                          " QCalendarWidget QSpinBox { color:#111; background:white; font-size:12pt; }"
                          " QCalendarWidget QMenu { color:#111; background:white; }")
        month = QLabel()                    # the month in Thai with the Buddhist year, large and clear
        month.setAlignment(Qt.AlignCenter)
        month.setStyleSheet("font-size:15pt; font-weight:bold; color:#1f4e79; background:#fff2cc;"
                            " border-radius:6px; padding:4px 10px;")
        v.addWidget(month)
        show_month = lambda y, m: month.setText(f"{P.THAI_MONTHS[m - 1]} {y + 543}")  # noqa: E731
        cal.currentPageChanged.connect(show_month)
        d = P.iso_date(self._iso) or dt.date.today()
        cal.setSelectedDate(QDate(d.year, d.month, d.day))
        show_month(d.year, d.month)
        v.addWidget(cal)
        note = QLabel()
        v.addWidget(note)
        show = lambda: note.setText("วันที่เลือก: " + P.thai_date(cal.selectedDate().toString("yyyy-MM-dd")))  # noqa
        cal.selectionChanged.connect(show)
        show()
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("ตกลง")
        bb.button(QDialogButtonBox.Cancel).setText("ยกเลิก")
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        cal.activated.connect(lambda _d: dlg.accept())
        v.addWidget(bb)
        if dlg.exec() == QDialog.Accepted:
            self.set_iso(cal.selectedDate().toString("yyyy-MM-dd"), emit=True)


# -- the popup: การคำนวณร้อยละวัสดุในการจ้าง ------------------------------------------------------

class PriceDialog(QDialog):
    """ราคากลาง and ราคาเสนอ are typed; ลดลง, ค่างานลดลง and ค่างานคงเหลือ are worked out (ว651)."""

    COLORS = ("#c6d9f1", "#ffff00", "#00b050", "#ffff00", "#e6b9b8")

    def __init__(self, project: P.Project, parent=None):
        super().__init__(parent)
        self.p = project
        self.setWindowTitle("การคำนวณร้อยละวัสดุในการจ้าง (ว651)")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        head = QLabel("การคำนวณร้อยละวัสดุในการจ้าง")
        head.setStyleSheet("font-size:15pt;font-weight:bold;")
        lay.addWidget(head)
        info = QLabel(f"{P.WORK_TYPE_NAMES.get(project.work_type)}\n"
                      f"ค่างานต้นทุนตามใบแจ้งปริมาณงาน {project.cost_total:,.2f} บาท"
                      + (f" · Factor F ในไฟล์ {project.factor:.4f}" if project.factor else ""))
        info.setWordWrap(True)
        lay.addWidget(info)
        grid = QGridLayout()
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(0)
        self.mid = MoneyEdit(project.mid_price)
        self.offer = MoneyEdit(project.offer)
        self.down = QLabel()
        self.pct_down = QLabel()
        self.pct_left = QLabel()
        rows = (("1. ราคากลาง", self.mid), ("2. ราคาเสนอ", self.offer), ("3. ลดลง", self.down),
                ("4. ค่างานลดลง (ร้อยละ)", self.pct_down), ("5. ค่างานคงเหลือ (ร้อยละ)", self.pct_left))
        for r, ((text, w), col) in enumerate(zip(rows, self.COLORS)):
            lab = QLabel(text)
            for x in (lab, w):
                x.setStyleSheet(f"background:{col};color:black;padding:6px;font-size:13pt;"
                                "border:1px solid #888;")
                x.setMinimumHeight(36)
            if isinstance(w, QLabel):
                w.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(lab, r, 0)
            grid.addWidget(w, r, 1)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        lay.addLayout(grid)
        form = QFormLayout()
        self.special = MoneyEdit(project.special)
        self.special.setToolTip("ค่าใช้จ่ายพิเศษตามข้อกำหนด (ถ้ามี) — ไม่นำมาปรับลด (ว651 ข้อ 1.2.2)")
        form.addRow("ค่าใช้จ่ายพิเศษตามข้อกำหนด (ถ้ามี):", self.special)
        if project.special_items_total and not project.special:
            form.addRow("", QLabel(f"(ในใบแจ้งปริมาณงานมีรายการค่าใช้จ่ายพิเศษ {project.special_items_total:,.2f} บาท)"))
        self.uplift = QLabel()
        form.addRow(self.uplift)
        lay.addLayout(form)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setStyleSheet("color:#b00000;")
        lay.addWidget(self.note)
        for w in (self.mid, self.offer, self.special):
            w.textChanged.connect(self.refresh)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("ตกลง")
        bb.button(QDialogButtonBox.Cancel).setText("ยกเลิก")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.refresh()
        self.mid.setFocus()

    def refresh(self):
        sp = self.special.value() or self.p.special_items_total
        up = self.p.uplift
        red = P.reduction(self.mid.value(), self.offer.value(), sp, up)
        self.down.setText(P.money(red.diff) or "0.00")
        self.pct_down.setText(f"{red.pct_down:,.2f}")
        self.pct_left.setText(f"{red.pct_left:,.2f}")
        self.uplift.setText(f"ราคากลางบวกเพิ่มร้อยละ 5 = {self.mid.value() * up:,.2f} บาท (3 จังหวัดชายแดนภาคใต้)"
                            if up > 1 else "")
        notes = []
        if self.offer.value() > self.mid.value() * up > 0:
            notes.append("ราคาเสนอสูงกว่าราคากลาง — ต้องต่อรองราคาตาม ว651 ข้อ 1.2.4")
        if self.p.cost_total and self.mid.value():
            f = (self.mid.value() - sp - self.p.equip_total * P.VAT_FACTOR) / self.p.cost_total
            if not self.p.factor or abs(f - self.p.factor) > 0.0005:
                notes.append(f"Factor F จากราคากลางที่กรอก = {f:.4f}")
        self.note.setText("\n".join(notes))

    def accept(self):
        if self.mid.value() <= 0 or self.offer.value() <= 0:
            QMessageBox.warning(self, self.windowTitle(), "กรุณากรอกราคากลางและราคาเสนอ")
            return
        self.p.mid_price = self.mid.value()
        self.p.offer = self.offer.value()
        self.p.special = self.special.value()
        super().accept()


# -- the window -------------------------------------------------------------------------------------

def _item(text, align=Qt.AlignLeft, editable=False, bold=False, bg=None) -> QTableWidgetItem:
    it = QTableWidgetItem(str(text))
    it.setTextAlignment(align | Qt.AlignVCenter)
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
    if editable:
        flags |= Qt.ItemIsEditable
    it.setFlags(flags)
    if bold:
        f = it.font()
        f.setBold(True)
        it.setFont(f)
    if bg:
        it.setBackground(QColor(bg))
        it.setForeground(QColor("#111111"))          # shaded cells stay readable in the dark themes
    return it


def _num_item(x, digits=2, **kw):
    return _item("" if x is None else f"{x:,.{digits}f}", Qt.AlignRight, **kw)


class ProcureDialog(QDialog):
    """ปรับลดราคา ว651 · แผนการทำงาน ว124 · แผนการใช้พัสดุ ว78"""

    def __init__(self, family: str = "Laksaman", record=None, parent=None, project: P.Project | None = None):
        super().__init__(parent)
        self.family = family
        self.record = record or (lambda *_a: None)
        self.settings = QSettings("WANICNSURVEY", "ReadWanicn2027")
        self.p = project or P.Project()
        self.path: Path | None = None
        self._filling = False
        self.setWindowTitle("ปรับลดราคา ว651 · แผนการทำงาน ว124 · แผนการใช้พัสดุ ว78")
        self.setSizeGripEnabled(True)
        self.setMinimumSize(640, 420)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        # everything but the report buttons scrolls, so the buttons stay in view on any screen
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 4, 0)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        # 1. รับข้อมูล
        g1 = QGroupBox("1. รับข้อมูลใบแจ้งปริมาณงาน (ปร.4) — ตารางคำนวณ, เอกสาร หรือ PDF")
        h = QHBoxLayout(g1)
        b = QPushButton("📥 รับข้อมูล…")
        b.setObjectName("Primary")
        b.setToolTip("นำเข้าใบแจ้งปริมาณงานและราคา (.xls .xlsx .csv .docx .pdf) แล้วบันทึกข้อมูลไว้ในโปรแกรม")
        b.clicked.connect(self.import_bill)
        h.addWidget(b)
        for text, fn, tip in (("📂 เปิดงานที่บันทึกไว้…", self.open_project, "เปิดงานที่นำเข้าและบันทึกไว้"),
                              ("💾 บันทึกงาน", self.save_project, "บันทึกข้อมูลทั้งหมด (ราคา แผนงาน แผนพัสดุ)"),
                              ("🗑 ล้างข้อมูล (เริ่มงานใหม่)", lambda: self.clear_project(ask=True),
                               "บันทึกงานปัจจุบันไว้ แล้วล้างข้อมูลทั้งหมดบนหน้าจอ เพื่อรับใบแจ้งปริมาณงานชุดใหม่")):
            bb = QPushButton(text)
            bb.setToolTip(tip)
            bb.clicked.connect(fn)
            h.addWidget(bb)
        self.src = QLabel("ยังไม่ได้รับข้อมูล")
        self.src.setWordWrap(True)
        h.addWidget(self.src, 1)
        lay.addWidget(g1)

        # 2. ประเภทงาน + ข้อมูลโครงการ
        g2 = QGroupBox("2. ประเภทงานตาม ว651 และข้อมูลโครงการ")
        f = QGridLayout(g2)
        self.kind = QComboBox()
        for k, name in P.WORK_TYPE_NAMES.items():
            self.kind.addItem(name, k)
        self.kind.currentIndexChanged.connect(self._kind_changed)
        f.addWidget(QLabel("ประเภทงาน:"), 0, 0)
        f.addWidget(self.kind, 0, 1, 1, 3)
        self.fields = {}
        spec = (("title", "ชื่อโครงการ"), ("agency", "หน่วยงานเจ้าของโครงการ"), ("place", "สถานที่ก่อสร้าง"),
                ("project_no", "เลขที่โครงการ"), ("contractor", "ชื่อผู้รับจ้าง"), ("contract_no", "สัญญาเลขที่"),
                ("contract_date", "ลงวันที่"), ("signer", "ผู้ลงนามแผน (ผู้รับจ้าง)"))
        for i, (key, label) in enumerate(spec):
            if key == "contract_date":
                e = ThaiDateEdit()
                e.changed.connect(lambda iso: self._set_field("contract_date", iso))
                self.contract_date = e
            else:
                e = QLineEdit()
                e.editingFinished.connect(lambda k=key, w=e: self._set_field(k, w.text()))
                self.fields[key] = e
            r, c = 1 + i // 2, (i % 2) * 2
            f.addWidget(QLabel(label + ":"), r, c)
            f.addWidget(e, r, c + 1)
        self.budget = MoneyEdit()
        self.budget.editingFinished.connect(lambda: self._set_field("budget", self.budget.value()))
        f.addWidget(QLabel("วงเงินงบประมาณ (บาท):"), 5, 0)
        f.addWidget(self.budget, 5, 1)
        f.setColumnStretch(1, 1)
        f.setColumnStretch(3, 1)
        lay.addWidget(g2)

        # 3. ราคา
        g3 = QGroupBox("3. ราคากลางและราคาเสนอ (คำนวณรวมทั้งโครงการ แล้วจึงกระจายลงทุกรายการ)")
        h3 = QHBoxLayout(g3)
        pb = QPushButton("💰 กรอกราคากลาง / ราคาเสนอ…")
        pb.clicked.connect(self.ask_prices)
        h3.addWidget(pb)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.RichText)
        h3.addWidget(self.summary, 1)
        lay.addWidget(g3)

        # tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_651(), "รายการปรับลดราคา ว651")
        self.tabs.addTab(self._tab_124(), "แผนการทำงาน ว124")
        self.tabs.addTab(self._tab_78(), "แผนการใช้พัสดุในประเทศ ว78")
        self.tabs.setMinimumHeight(300)
        lay.addWidget(self.tabs, 1)

        # reports: always visible under the scrolling part
        bar = QFrame()
        bar.setObjectName("ReportBar")
        row = QGridLayout(bar)
        row.setContentsMargins(0, 6, 0, 0)
        row.setHorizontalSpacing(8)
        row.setVerticalSpacing(4)
        self.report_buttons = {}
        for col, (kind, tip) in enumerate((("651", "แบบสรุปราคากลาง + ราคาที่ปรับลดทุกรายการ + เอกสารแนบท้ายสัญญา"),
                                           ("124", "แผนการทำงานรายเดือน + กราฟแผนงานสะสม + เกณฑ์ประเมิน"),
                                           ("work", "แผนปฏิบัติงาน (Bar Chart) ทุกรายการ ช่องละครึ่งเดือน "
                                                    "วันเริ่ม–สิ้นสุด — ใช้ข้อมูลเดียวกับแผน ว124"),
                                           ("78", "ภาคผนวก 1 พัสดุในประเทศ · ภาคผนวก 2 เหล็ก · ภาคผนวก 3 รายงานผล"))):
            b = QPushButton(f"📄 {REPORT_LABEL[kind]}")
            b.setObjectName("Primary")
            b.setMinimumHeight(38)
            b.setToolTip(tip + " — บันทึกเป็น PDF และตารางคำนวณ (.xlsx)")
            b.clicked.connect(lambda _=False, k=kind: self.write_report(k))
            c = QPushButton(f"🧾 ตารางคำนวณ {SHORT_LABEL[kind]}")
            c.setMinimumHeight(34)
            c.setToolTip(tip + " — ตารางคำนวณ (.xlsx) จัดหน้าพร้อมพิมพ์ A4 แล้ว แก้ไขได้ (เลือก .csv ได้)")
            c.clicked.connect(lambda _=False, k=kind: self.write_csv(k))
            row.addWidget(b, 0, col)
            row.addWidget(c, 1, col)
            self.report_buttons[kind] = (b, c)
        close = QPushButton("ปิด")
        close.setMinimumHeight(38)
        close.clicked.connect(self.accept)
        row.addWidget(close, 0, 5, 2, 1)
        row.setColumnStretch(4, 1)
        outer.addWidget(bar)
        if project is None:
            self._open_last()
        self.fill()

    # -- tabs
    def _tab_651(self):
        w = QWidget()
        v = QVBoxLayout(w)
        hint = QLabel("ติ๊ก «ครุภัณฑ์» สำหรับงานครุภัณฑ์จัดซื้อ (Factor = VAT 1.07) และ «ค่าใช้จ่ายพิเศษ» "
                      "สำหรับรายการที่ไม่ปรับลด — (*) คือรายการที่รับเศษสตางค์ให้วงเงินรวมเท่าราคาเสนอ")
        hint.setWordWrap(True)
        v.addWidget(hint)
        self.t651 = QTableWidget(0, 11)
        self.t651.setHorizontalHeaderLabels(["ลำดับ", "รายการ", "หน่วย", "จำนวน", "ค่างานต้นทุน", "Factor F",
                                             "ราคากลาง", "ราคาที่ปรับลด", "ราคาต่อหน่วย", "ครุภัณฑ์",
                                             "ค่าใช้จ่ายพิเศษ"])
        self._setup(self.t651, 1)
        self.t651.itemChanged.connect(self._t651_changed)
        v.addWidget(self.t651, 1)
        return w

    def _tab_124(self):
        w = QWidget()
        v = QVBoxLayout(w)
        h = QHBoxLayout()
        h.addWidget(QLabel("ระยะเวลาทำงาน:"))
        self.months = QSpinBox()
        self.months.setRange(1, 60)
        self.months.setSuffix(" เดือน")
        h.addWidget(self.months)
        self.days = QSpinBox()
        self.days.setRange(1, 1800)
        self.days.setSuffix(" วัน")
        self.days.setToolTip("ระยะเวลาตามสัญญา (วัน) — เดือนละ 30 วัน เดือนสุดท้ายได้วันที่เหลือ")
        h.addWidget(self.days)
        self.months.valueChanged.connect(self._months_changed)
        self.days.valueChanged.connect(self._days_changed)
        h.addWidget(QLabel("วันเริ่มงาน:"))
        self.start = ThaiDateEdit()
        self.start.setMinimumWidth(260)
        self.start.changed.connect(self._start_changed)
        h.addWidget(self.start)
        b = QPushButton("⚙ สร้างแผนงาน")
        b.setObjectName("Primary")
        b.setToolTip("กระจายรายการลงแต่ละเดือนตามลำดับในใบแจ้งปริมาณงาน ให้มูลค่างานแต่ละเดือนใกล้เคียงกัน\n"
                     "แล้วแก้ร้อยละในตารางได้ (แต่ละรายการรวมกัน 100 %)")
        b.clicked.connect(self.build_plan)
        h.addWidget(b)
        h.addStretch(1)
        v.addLayout(h)
        self.plan_info = QLabel()
        self.plan_info.setWordWrap(True)
        v.addWidget(self.plan_info)
        self.t124 = QTableWidget(0, 4)
        self._setup(self.t124, 0)
        self.t124.itemChanged.connect(self._t124_changed)
        v.addWidget(self.t124, 1)
        return w

    def _tab_78(self):
        w = QWidget()
        v = QVBoxLayout(w)
        hint = QLabel("ติ๊ก «เหล็ก» รายการที่นับเป็นเหล็ก (ภาคผนวก 2 คิดเป็นตัน) — กรอก «กก./หน่วย» เมื่อโปรแกรมหาน้ำหนักไม่ได้ "
                      "· แก้ «% ในประเทศ» ได้ทุกรายการ (ค่าเริ่มต้น 100)")
        hint.setWordWrap(True)
        v.addWidget(hint)
        self.info78 = QLabel()
        self.info78.setWordWrap(True)
        self.info78.setTextFormat(Qt.RichText)
        v.addWidget(self.info78)
        self.t78 = QTableWidget(0, 8)
        self.t78.setHorizontalHeaderLabels(["รายการ", "หน่วย", "ปริมาณ", "เป็นเงิน (ปรับลด)", "เหล็ก", "กก./หน่วย",
                                            "ตัน", "% ในประเทศ"])
        self._setup(self.t78, 0)
        self.t78.itemChanged.connect(self._t78_changed)
        v.addWidget(self.t78, 1)
        return w

    @staticmethod
    def _setup(t: QTableWidget, stretch: int):
        t.verticalHeader().hide()
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setAlternatingRowColors(True)
        hh = t.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(stretch, QHeaderView.Stretch)

    # -- data in
    def import_bill(self):
        start = self.settings.value("procure/dir", str(Path.home() / "Documents"))
        path, _ = QFileDialog.getOpenFileName(self, "รับข้อมูลใบแจ้งปริมาณงาน", start, IMPORT_FILTER)
        if not path:
            return
        self.settings.setValue("procure/dir", str(Path(path).parent))
        try:
            p = P.read_bill(path)
        except Exception as e:                        # shown to the user, never swallowed
            QMessageBox.critical(self, self.windowTitle(), f"อ่านไฟล์ไม่สำเร็จ:\n{e}")
            return
        p.work_type = self.kind.currentData() or "building"
        self.p = p
        self.path = None
        self.record("รับข้อมูลใบแจ้งปริมาณงาน")
        self.fill()
        QMessageBox.information(self, self.windowTitle(),
                                f"รับข้อมูลแล้ว {len(p.leaves):,} รายการ (หัวข้อ {len(p.items) - len(p.leaves):,})\n"
                                f"ค่างานต้นทุน {p.cost_total:,.2f} บาท"
                                + (f"\nFactor F {p.factor:.4f} → ราคากลาง {p.mid_price:,.2f} บาท" if p.factor else "")
                                + "\n\nต่อไป: กรอกราคากลางและราคาเสนอ")
        self.ask_prices()
        self.save_project(quiet=True)

    def ask_prices(self):
        if not self.p.items:
            QMessageBox.information(self, self.windowTitle(), "กรุณารับข้อมูลใบแจ้งปริมาณงานก่อน")
            return
        if PriceDialog(self.p, self).exec() == QDialog.Accepted:
            self.record("กรอกราคากลาง/ราคาเสนอ")
            if not any(it.plan for it in self.p.leaves):
                P.auto_plan(self.p, self.p.months or 4)
            self.fill()
            self.save_project(quiet=True)

    def _set_field(self, key, value):
        if getattr(self.p, key) != value:
            setattr(self.p, key, value)
            self._refresh_summary()

    def _kind_changed(self):
        if self._filling:
            return
        self.p.work_type = self.kind.currentData()
        self.fill()

    def _months_changed(self, m):
        if self._filling:
            return
        self.p.months = m
        self._filling = True
        self.days.setValue(30 * m)
        self._filling = False
        self.p.days = 30 * m
        self.build_plan()

    def _days_changed(self, d):
        if self._filling:
            return
        self.p.days = d
        need = max(1, -(-d // 30))
        if need != self.p.months:
            self.p.months = need
            self._filling = True
            self.months.setValue(need)
            self._filling = False
            self.build_plan()
        else:
            self.fill_124()

    def _start_changed(self, iso):
        self.p.start = iso
        self.fill_124()

    def build_plan(self):
        if not self.p.items:
            return
        P.auto_plan(self.p, self.months.value())
        if not self.p.days:
            self.p.days = self.days.value()
        self.record("สร้างแผนการทำงาน ว124")
        self.fill_124()

    # -- filling
    def fill(self):
        self._filling = True
        try:
            p = self.p
            i = self.kind.findData(p.work_type)
            self.kind.setCurrentIndex(max(0, i))
            for k, e in self.fields.items():
                e.setText(P.arabic(getattr(p, k)) or "")
            if p.items and not p.contract_date:          # ลงวันที่: today unless chosen
                p.contract_date = dt.date.today().isoformat()
            self.contract_date.set_iso(p.contract_date if P.iso_date(p.contract_date) else "")
            if not P.iso_date(p.contract_date) and p.contract_date:
                self.contract_date.view.setText(P.arabic(p.contract_date))
            self.budget.set_value(p.budget)
            self.months.setValue(p.months or 4)
            self.days.setValue(p.days or 30 * (p.months or 4))
            self.start.set_iso(p.start if P.iso_date(p.start) else "")
            if p.items:
                src = Path(p.source).name if p.source else "—"
                self.src.setText(f"ไฟล์: {src} · {len(p.leaves):,} รายการ · ค่างานต้นทุน {p.cost_total:,.2f} บาท"
                                 + (f" · Factor F {p.factor:.4f}" if p.factor else "")
                                 + (f"\nบันทึกไว้ที่: {self.path}" if self.path else ""))
        finally:
            self._filling = False
        self._refresh_summary()
        self.fill_651()
        self.fill_124()
        self.fill_78()

    def _refresh_summary(self):
        p = self.p
        if not p.items:
            self.summary.setText("รับข้อมูลใบแจ้งปริมาณงานก่อน")
            return
        if not p.offer:
            self.summary.setText("ยังไม่ได้กรอกราคากลางและราคาเสนอ")
            return
        res = P.compute_651(p)
        red = res.red
        s = (f"ราคากลาง <b>{p.mid_price * res.uplift:,.2f}</b> · ราคาเสนอ <b>{p.offer:,.2f}</b> · "
             f"ลดลง <b>{red.diff:,.2f}</b> · ค่างานลดลง <b>{red.pct_down:,.2f} %</b> · "
             f"ค่างานคงเหลือ <b>{red.pct_left:,.2f} %</b> · Factor F {res.factor:.4f}"
             f" · รวมราคาที่ปรับลด <b>{res.reduced_total:,.2f}</b>")
        if res.warnings:
            s += "<br><span style='color:#c00000'>" + "<br>".join(res.warnings) + "</span>"
        self.summary.setText(s)

    def fill_651(self):
        t = self.t651
        self._filling = True
        try:
            res = P.compute_651(self.p) if self.p.items else None
            rows = res.rows if res else []
            t.setRowCount(len(rows))
            sub_mid = P.subtotals(rows, "mid_up")
            sub_red = P.subtotals(rows, "reduced")
            for i, r in enumerate(rows):
                it = r.item
                bg = "#eef2f8" if it.header else None
                name = "    " * max(0, it.level - 1) + it.label + (" (*)" if res and i == res.adjust_row else "")
                cells = [_item(it.no, Qt.AlignCenter, bg=bg), _item(name, bold=it.header, bg=bg),
                         _item(it.unit, Qt.AlignCenter, bg=bg)]
                if it.header:
                    cells += [_item("", bg=bg), _item("", bg=bg), _item("", bg=bg),
                              _num_item(sub_mid.get(i), bold=True, bg=bg), _num_item(sub_red.get(i), bold=True, bg=bg),
                              _item("", bg=bg)]
                else:
                    adj = bool(res) and i == res.adjust_row
                    if adj:
                        cells = [_item(it.no, Qt.AlignCenter, bg="#d9d9d9"), _item(name, bold=True, bg="#d9d9d9"),
                                 _item(it.unit, Qt.AlignCenter, bg="#d9d9d9")]
                        cells[1].setToolTip(R.adjust_note(res))
                    cells += [_num_item(it.qty), _num_item(r.cost), _num_item(r.factor, 4), _num_item(r.mid_up),
                              _num_item(r.reduced, bg="#d9d9d9" if adj else "#fff2cc", bold=adj),
                              _num_item(r.unit_price, bg="#d9d9d9" if adj else None)]
                for c, cell in enumerate(cells):
                    t.setItem(i, c, cell)
                for c, flag in ((9, it.equip), (10, it.special)):
                    chk = _item("", Qt.AlignCenter, bg=bg)
                    if not it.header and i < len(self.p.items):
                        chk.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                        chk.setCheckState(Qt.Checked if flag else Qt.Unchecked)
                    t.setItem(i, c, chk)
        finally:
            self._filling = False

    def _t651_changed(self, cell):
        if self._filling or cell.column() not in (9, 10):
            return
        r = cell.row()
        if r >= len(self.p.items):
            return
        it = self.p.items[r]
        on = cell.checkState() == Qt.Checked
        if cell.column() == 9:
            it.equip = on
        else:
            it.special = on
        self.fill()

    def fill_124(self):
        t = self.t124
        self._filling = True
        try:
            p = self.p
            if not p.items or not p.offer:
                t.setRowCount(0)
                self.plan_info.setText("กรอกราคากลางและราคาเสนอก่อน แล้วกด «สร้างแผนงาน»")
                return
            plan = P.compute_124(p)
            n = plan.months
            t.setColumnCount(5 + n)
            t.setHorizontalHeaderLabels(["รายการ", "หน่วย", "เป็นเงิน", "%", "รวม %"]
                                        + [f"เดือน {m + 1}\n{plan.labels[m] if plan.labels else f'{d} วัน'}"
                                           for m, d in enumerate(plan.days)])
            t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            self._lines = plan.lines
            t.setRowCount(len(plan.lines) + 4)
            for i, (it, a, pc, pl) in enumerate(plan.lines):
                tot = sum(pl)
                t.setItem(i, 0, _item(it.label))
                t.setItem(i, 1, _item(it.unit, Qt.AlignCenter))
                t.setItem(i, 2, _num_item(a))
                t.setItem(i, 3, _num_item(pc))
                t.setItem(i, 4, _num_item(tot, bold=True, bg=None if abs(tot - 100) < 0.05 else "#f8cbad"))
                for m, v in enumerate(pl):
                    t.setItem(i, 5 + m, _num_item(v if v else None, editable=True,
                                                  bg="#c4d79b" if v else None))
            k = len(plan.lines)
            t.setItem(k, 0, _item("% PLAN", bold=True))
            t.setItem(k + 1, 0, _item("% ACC PLAN", bold=True))
            for c in range(1, 5):
                t.setItem(k, c, _item(""))
                t.setItem(k + 1, c, _item(""))
            t.setItem(k + 2, 0, _item("% ACTUAL ผลงานจริง (กรอกได้ · แสดงในแผนปฏิบัติงาน)", bold=True))
            t.setItem(k + 3, 0, _item("% ACC ACTUAL ผลงานจริงสะสม", bold=True))
            for c in range(1, 5):
                t.setItem(k + 2, c, _item(""))
                t.setItem(k + 3, c, _item(""))
            for m in range(n):
                t.setItem(k, 5 + m, _num_item(plan.pct_plan[m], bold=True, bg="#ddebf7"))
                t.setItem(k + 1, 5 + m, _num_item(plan.acc_plan[m], bold=True, bg="#ddebf7"))
                t.setItem(k + 2, 5 + m, _num_item(plan.actual[m], editable=True, bg="#fce4d6"))
                t.setItem(k + 3, 5 + m, _num_item(plan.acc_actual[m], bold=True, bg="#fce4d6"))
            chk = " · ".join(f"{w}: แผนสะสม {v:.2f} % (ขั้นต่ำ {need:.0f} %)" for w, _k, v, need in plan.checks)
            bad = f" · <b style='color:#c00000'>{len(plan.bad_lines)} รายการรวมไม่เท่ากับ 100 %</b>" \
                if plan.bad_lines else ""
            self.plan_info.setText(f"{n} เดือน ({sum(plan.days)} วัน) · มูลค่างาน {plan.total:,.2f} บาท · {chk}{bad}")
            self.plan_info.setTextFormat(Qt.RichText)
        finally:
            self._filling = False

    def _t124_changed(self, cell):
        if self._filling or cell.column() < 5:
            return
        lines = getattr(self, "_lines", [])
        if cell.row() == len(lines) + 2:                  # % ACTUAL of a month
            m = cell.column() - 5
            act = list(self.p.actual) + [None] * max(0, self.p.months - len(self.p.actual))
            act[m] = P.num(cell.text())
            while act and act[-1] is None:
                act.pop()
            self.p.actual = act
            self.fill_124()
            return
        if cell.row() >= len(lines):
            return
        it = self._lines[cell.row()][0]
        m = cell.column() - 5
        plan = list(it.plan) + [0.0] * max(0, self.p.months - len(it.plan))
        plan[m] = P.num(cell.text()) or 0.0
        it.plan = plan
        self.fill_124()

    def fill_78(self):
        t = self.t78
        self._filling = True
        try:
            p = self.p
            if not p.items:
                t.setRowCount(0)
                self.info78.setText("")
                return
            res = P.compute_651(p)
            leaves = [r for r in res.rows if not r.item.header and not r.item.special
                      and r.item in p.items]
            self._rows78 = [r.item for r in leaves]
            t.setRowCount(len(leaves))
            for i, r in enumerate(leaves):
                it = r.item
                k = P.kg_per_unit(it) if it.is_steel else None
                t.setItem(i, 0, _item(it.label))
                t.setItem(i, 1, _item(it.unit, Qt.AlignCenter))
                t.setItem(i, 2, _num_item(it.qty))
                t.setItem(i, 3, _num_item(r.reduced))
                chk = _item("", Qt.AlignCenter)
                chk.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                chk.setCheckState(Qt.Checked if it.is_steel else Qt.Unchecked)
                t.setItem(i, 4, chk)
                miss = it.is_steel and k is None
                t.setItem(i, 5, _num_item(k, 3, editable=it.is_steel, bg="#f8cbad" if miss else None))
                t.setItem(i, 6, _num_item(it.qty * k / 1000 if k is not None else None, 4))
                t.setItem(i, 7, _num_item(it.domestic, editable=True))
            w = P.compute_78(p)
            ok = lambda b: "<b style='color:#2e7d32'>ผ่าน</b>" if b else "<b style='color:#c00000'>ไม่ผ่าน</b>"  # noqa
            s = (f"ภาคผนวก 1 พัสดุในประเทศ {w.mat_domestic:,.2f} / {w.mat_total:,.2f} บาท = "
                 f"<b>{w.mat_pct:.2f} %</b> (≥ 60) {ok(w.mat_ok)} · ภาคผนวก 2 เหล็ก {w.steel_t:,.4f} ตัน "
                 f"ในประเทศ <b>{w.steel_pct:.2f} %</b> (≥ 90) {ok(w.steel_ok)}")
            if w.missing_weight:
                s += f" · <b style='color:#c00000'>เหล็ก {len(w.missing_weight)} รายการยังไม่ทราบน้ำหนัก</b>"
            if w.exempt:
                s += f"<br>{w.exempt}"
            self.info78.setText(s)
        finally:
            self._filling = False

    def _t78_changed(self, cell):
        if self._filling or cell.row() >= len(getattr(self, "_rows78", [])):
            return
        it = self._rows78[cell.row()]
        c = cell.column()
        if c == 4:
            it.steel = cell.checkState() == Qt.Checked
        elif c == 5:
            it.kg_per_unit = P.num(cell.text())
        elif c == 7:
            v = P.num(cell.text())
            it.domestic = max(0.0, min(100.0, v if v is not None else 100.0))
        else:
            return
        self.fill_78()

    # -- saving
    def clear_project(self, ask: bool = False) -> bool:
        """A new job: the one on screen is saved (it stays under «เปิดงานที่บันทึกไว้»), then every
        field, price, plan and table is emptied, and the window no longer reopens it."""
        if ask and self.p.items and QMessageBox.question(
                self, self.windowTitle(), "ล้างข้อมูลทั้งหมดบนหน้าจอเพื่อเริ่มงานใหม่?\n\n"
                "งานปัจจุบันจะถูกบันทึกไว้ก่อน เปิดกลับมาได้ที่ «📂 เปิดงานที่บันทึกไว้…»") != QMessageBox.Yes:
            return False
        if self.p.items:
            self.save_project(quiet=True)
        self.p = P.Project()
        self.path = None
        self.settings.setValue("procure/last", "")
        self.fill()
        self.contract_date.set_iso("")
        self.src.setText("ยังไม่ได้รับข้อมูล — กด «📥 รับข้อมูล…» เพื่อนำเข้าใบแจ้งปริมาณงานชุดใหม่")
        self.tabs.setCurrentIndex(0)
        return True

    def _open_last(self):
        last = self.settings.value("procure/last", "")
        if last and Path(last).exists():
            try:
                self.p = P.Project.load(last)
                self.path = Path(last)
            except Exception:                         # a damaged file: start empty
                self.p = P.Project()

    def save_project(self, quiet=False):
        if not self.p.items:
            if not quiet:
                QMessageBox.information(self, self.windowTitle(), "ยังไม่มีข้อมูลให้บันทึก")
            return
        if self.path is None:
            self.path = store_dir() / f"{safe_name(self.p.title or Path(self.p.source).stem)}.rwprice.json"
        self.p.save(self.path)
        self.settings.setValue("procure/last", str(self.path))
        if not quiet:
            self.fill()
            QMessageBox.information(self, self.windowTitle(), f"บันทึกงานแล้ว\n{self.path}")

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "เปิดงานที่บันทึกไว้", str(store_dir()), PROJECT_FILTER)
        if not path:
            return
        try:
            self.p = P.Project.load(path)
        except Exception as e:
            QMessageBox.critical(self, self.windowTitle(), f"เปิดไม่สำเร็จ:\n{e}")
            return
        self.path = Path(path)
        self.settings.setValue("procure/last", path)
        self.fill()

    def write_report(self, kind: str):
        p = self.p
        if not p.items:
            QMessageBox.information(self, self.windowTitle(), "กรุณารับข้อมูลใบแจ้งปริมาณงานก่อน")
            return
        if not p.offer or not p.mid_price:
            self.ask_prices()
            if not p.offer:
                return
        if kind in ("124", "work") and not any(it.plan for it in p.leaves):
            self.build_plan()
        names = REPORT_NAME
        start = self.settings.value("procure/out", str(Path.home() / "Documents"))
        default = Path(start) / f"{names[kind]} {safe_name(p.title)[:40]}.pdf"
        path, _ = QFileDialog.getSaveFileName(self, f"บันทึกรายงาน {names[kind]}", str(default), "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        self.settings.setValue("procure/out", str(Path(path).parent))
        R.WRITE_ERRORS.clear()
        try:
            files = R.write(kind, p, path, self.family)
        except Exception as e:
            self._failed(f"บันทึกรายงาน {names[kind]} ไม่สำเร็จ", e, path)
            return
        self.record(f"รายงาน {names[kind]}")
        if R.WRITE_ERRORS:
            QMessageBox.warning(self, self.windowTitle(), "บันทึก PDF แล้ว แต่ตารางคำนวณไม่สำเร็จ:\n"
                                + "\n".join(R.WRITE_ERRORS))
        self.save_project(quiet=True)
        msg = "บันทึกรายงานแล้ว:\n" + "\n".join(str(f) for f in files)
        if QMessageBox.question(self, self.windowTitle(), msg + "\n\nเปิดไฟล์ PDF เลยหรือไม่?") == QMessageBox.Yes:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(files[0])))

    def write_csv(self, kind: str):
        p = self.p
        if not p.items:
            QMessageBox.information(self, self.windowTitle(), "กรุณารับข้อมูลใบแจ้งปริมาณงานก่อน")
            return
        if not p.offer or not p.mid_price:
            self.ask_prices()
            if not p.offer:
                return
        if kind in ("124", "work") and not any(it.plan for it in p.leaves):
            self.build_plan()
        names = REPORT_NAME
        start = self.settings.value("procure/out", str(Path.home() / "Documents"))
        default = Path(start) / f"{names[kind]} {safe_name(P.arabic(p.title))[:40]}.xlsx"
        path, flt = QFileDialog.getSaveFileName(
            self, f"บันทึกตารางคำนวณ {names[kind]}", str(default),
            "ตารางคำนวณ จัดหน้าพร้อมพิมพ์ A4 (*.xlsx);;ไฟล์ข้อมูลคั่นด้วยจุลภาค ไม่มีการจัดหน้า (*.csv)")
        if not path:
            return
        if not path.lower().endswith((".xlsx", ".csv")):
            path += ".csv" if "csv" in flt else ".xlsx"
        self.settings.setValue("procure/out", str(Path(path).parent))
        try:
            files = R.write_sheet(kind, p, path)
        except Exception as e:
            self._failed(f"บันทึกตารางคำนวณ {names[kind]} ไม่สำเร็จ", e, path)
            return
        if not all(Path(f).exists() for f in files):
            QMessageBox.warning(self, self.windowTitle(), "ไม่พบไฟล์ที่บันทึก:\n" + "\n".join(map(str, files)))
            return
        self.record(f"ตารางคำนวณ {names[kind]}")
        self.save_project(quiet=True)
        msg = "บันทึกแล้ว:\n" + "\n".join(str(f) for f in files)
        if QMessageBox.question(self, self.windowTitle(), msg + "\n\nเปิดไฟล์เลยหรือไม่?") == QMessageBox.Yes:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(files[0])))

    def _failed(self, what: str, e: Exception, path):
        """Never silent: say what failed and why (a file open in another program is the usual cause)."""
        import traceback
        traceback.print_exc()
        hint = ""
        if isinstance(e, PermissionError):
            hint = "\n\nไฟล์นี้อาจเปิดค้างอยู่ในโปรแกรมอื่น — ปิดไฟล์แล้วลองใหม่ หรือบันทึกเป็นชื่ออื่น"
        QMessageBox.critical(self, self.windowTitle(), f"{what}\n{path}\n\n{type(e).__name__}: {e}{hint}")

    def showEvent(self, e):
        """Fit the screen it opens on (laptops, 125–175 % scaling): never larger than the
        available area, centred, the report buttons always on screen."""
        super().showEvent(e)
        if getattr(self, "_fitted", False):
            return
        self._fitted = True
        scr = self.screen() or (self.parent().screen() if self.parent() else None)
        if scr is None:
            return
        av = scr.availableGeometry()
        w = min(1300, int(av.width() * 0.96))
        h = min(900, int(av.height() * 0.92))
        self.resize(w, h)
        self.move(av.x() + (av.width() - w) // 2, av.y() + (av.height() - h) // 2)

    def closeEvent(self, e):
        if self.p.items:
            self.save_project(quiet=True)
        super().closeEvent(e)

    def accept(self):
        if self.p.items:
            self.save_project(quiet=True)
        super().accept()

