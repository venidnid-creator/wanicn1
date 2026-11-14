# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ — ReadWanicn2027
"""The window for ว651 · ว124 · ว78: take in the bill, enter the prices,
check the lines, the work plan and the domestic-material plan, write the reports."""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QGridLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from . import procure as P
from . import procure_report as R

IMPORT_FILTER = ("ใบแจ้งปริมาณงาน (*.xls *.xlsx *.xlsm *.csv *.docx *.pdf);;"
                 "ตารางคำนวณ (*.xls *.xlsx *.xlsm *.csv);;เอกสาร (*.docx);;PDF (*.pdf);;ทุกไฟล์ (*)")
PROJECT_FILTER = "งานปรับลดราคา (*.rwprice.json);;ทุกไฟล์ (*)"


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
        self.resize(1280, 860)
        lay = QVBoxLayout(self)

        # 1. รับข้อมูล
        g1 = QGroupBox("1. รับข้อมูลใบแจ้งปริมาณงาน (ปร.4) — ตารางคำนวณ, เอกสาร หรือ PDF")
        h = QHBoxLayout(g1)
        b = QPushButton("📥 รับข้อมูล…")
        b.setObjectName("Primary")
        b.setToolTip("นำเข้าใบแจ้งปริมาณงานและราคา (.xls .xlsx .csv .docx .pdf) แล้วบันทึกข้อมูลไว้ในโปรแกรม")
        b.clicked.connect(self.import_bill)
        h.addWidget(b)
        for text, fn, tip in (("📂 เปิดงานที่บันทึกไว้…", self.open_project, "เปิดงานที่นำเข้าและบันทึกไว้"),
                              ("💾 บันทึกงาน", self.save_project, "บันทึกข้อมูลทั้งหมด (ราคา แผนงาน แผนพัสดุ)")):
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
        lay.addWidget(self.tabs, 1)

        # reports
        row = QHBoxLayout()
        for kind, text, tip in (("651", "📄 รายงาน ว651", "แบบสรุปราคากลาง + ราคาที่ปรับลดทุกรายการ + เอกสารแนบท้ายสัญญา"),
                                ("124", "📄 รายงาน ว124", "แผนการทำงานรายเดือน + กราฟแผนงานสะสม + เกณฑ์ประเมิน"),
                                ("78", "📄 รายงาน ว78", "ภาคผนวก 1 พัสดุในประเทศ · ภาคผนวก 2 เหล็ก · ภาคผนวก 3 รายงานผล")):
            b = QPushButton(text)
            b.setObjectName("Primary")
            b.setToolTip(tip + " — บันทึกเป็น PDF และตารางคำนวณ (.xlsx)")
            b.clicked.connect(lambda _=False, k=kind: self.write_report(k))
            row.addWidget(b)
        row.addStretch(1)
        close = QPushButton("ปิด")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)
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
        h.addWidget(QLabel("เริ่มเดือน (ไม่ใส่ก็ได้):"))
        self.start = QLineEdit()
        self.start.setPlaceholderText("เช่น ตุลาคม 2569")
        self.start.editingFinished.connect(lambda: self._set_field("start", self.start.text()))
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
                e.setText(getattr(p, k) or "")
            self.budget.set_value(p.budget)
            self.months.setValue(p.months or 4)
            self.days.setValue(p.days or 30 * (p.months or 4))
            self.start.setText(p.start)
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
                    cells += [_num_item(it.qty), _num_item(r.cost), _num_item(r.factor, 4), _num_item(r.mid_up),
                              _num_item(r.reduced, bg="#fff2cc"), _num_item(r.unit_price)]
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
                                        + [f"เดือน {m + 1}\n{d} วัน" for m, d in enumerate(plan.days)])
            t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            self._lines = plan.lines
            t.setRowCount(len(plan.lines) + 2)
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
            for m in range(n):
                t.setItem(k, 5 + m, _num_item(plan.pct_plan[m], bold=True, bg="#ddebf7"))
                t.setItem(k + 1, 5 + m, _num_item(plan.acc_plan[m], bold=True, bg="#ddebf7"))
            chk = " · ".join(f"{w}: แผนสะสม {v:.2f} % (ขั้นต่ำ {need:.0f} %)" for w, _k, v, need in plan.checks)
            bad = f" · <b style='color:#c00000'>{len(plan.bad_lines)} รายการรวมไม่เท่ากับ 100 %</b>" \
                if plan.bad_lines else ""
            self.plan_info.setText(f"{n} เดือน ({sum(plan.days)} วัน) · มูลค่างาน {plan.total:,.2f} บาท · {chk}{bad}")
            self.plan_info.setTextFormat(Qt.RichText)
        finally:
            self._filling = False

    def _t124_changed(self, cell):
        if self._filling or cell.column() < 5 or cell.row() >= len(getattr(self, "_lines", [])):
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
        if kind == "124" and not any(it.plan for it in p.leaves):
            self.build_plan()
        names = {"651": "ว651 ปรับลดราคา", "124": "ว124 แผนการทำงาน", "78": "ว78 แผนการใช้พัสดุในประเทศ"}
        start = self.settings.value("procure/out", str(Path.home() / "Documents"))
        default = Path(start) / f"{names[kind]} {safe_name(p.title)[:40]}.pdf"
        path, _ = QFileDialog.getSaveFileName(self, f"บันทึกรายงาน {names[kind]}", str(default), "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        self.settings.setValue("procure/out", str(Path(path).parent))
        files = R.write(kind, p, path, self.family)
        self.record(f"รายงาน {names[kind]}")
        self.save_project(quiet=True)
        msg = "บันทึกรายงานแล้ว:\n" + "\n".join(str(f) for f in files)
        if QMessageBox.question(self, self.windowTitle(), msg + "\n\nเปิดไฟล์ PDF เลยหรือไม่?") == QMessageBox.Yes:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(files[0])))

    def closeEvent(self, e):
        if self.p.items:
            self.save_project(quiet=True)
        super().closeEvent(e)

    def accept(self):
        if self.p.items:
            self.save_project(quiet=True)
        super().accept()

