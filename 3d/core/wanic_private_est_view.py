# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ประมาณราคางานเอกชน 8 หมวด — the window: the waste by kind, overhead and
profit, VAT, the steel's price; the summary of the eight categories and
the bill whose unit prices are edited in place."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QCheckBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QHeaderView,
                               QLabel, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout)

from core import wanic_private_est as P

BILL_HEAD = ["ลำดับ", "รายการ", "ปริมาณสุทธิ", "เผื่อ %", "ปริมาณ", "หน่วย", "ค่าวัสดุ/หน่วย", "ค่าวัสดุ",
             "ค่าแรง/หน่วย", "ค่าแรง", "รวม (บาท)"]
EDIT = QColor("#FFF7D6")


class PrivateEstDialog(QDialog):
    def __init__(self, parent, data: dict):
        super().__init__(parent)
        self.setWindowTitle("ประมาณราคางานเอกชน 8 หมวด")
        self.resize(1320, 820)
        self.data = data
        st = P.settings(data)
        self.prices = dict(st["prices"] or {})
        lay = QHBoxLayout(self)
        form = QFormLayout()
        self.over = QDoubleSpinBox()
        self.over.setRange(0, 50)
        self.over.setDecimals(2)
        self.over.setValue(float(st["overhead"]))
        form.addRow("ค่าดำเนินการและกำไร (%)", self.over)
        self.vat = QCheckBox("รวมภาษีมูลค่าเพิ่ม 7%")
        self.vat.setChecked(bool(st["vat"]))
        form.addRow(self.vat)
        form.addRow(QLabel("— เผื่อเสีย (%) —"))
        self.waste = {}
        for k, th in P.WASTE_TH.items():
            w = QDoubleSpinBox()
            w.setRange(0, 50)
            w.setDecimals(1)
            w.setValue(float(st["waste"][k]))
            self.waste[k] = w
            form.addRow(th, w)
        form.addRow(QLabel("— เหล็กรูปพรรณที่ออกแบบ (Truss / WF-H / แป) —"))
        self.sp_mat = QDoubleSpinBox()
        self.sp_mat.setRange(0, 1000)
        self.sp_mat.setDecimals(2)
        self.sp_mat.setValue(float(st["steel_price"]))
        self.sp_lab = QDoubleSpinBox()
        self.sp_lab.setRange(0, 1000)
        self.sp_lab.setDecimals(2)
        self.sp_lab.setValue(float(st["steel_lab"]))
        form.addRow("ค่าวัสดุ (บาท/กก.)", self.sp_mat)
        form.addRow("ค่าแรง (บาท/กก.)", self.sp_lab)
        for w in [self.over, self.sp_mat, self.sp_lab] + list(self.waste.values()):
            w.valueChanged.connect(self.recalc)
        self.vat.toggled.connect(self.recalc)
        left = QVBoxLayout()
        left.addLayout(form)
        tip = QLabel("ปริมาณงานมาจากแบบเดียวกับ BOQ ราชการ (ไม่มี Factor F)\n"
                     "แก้ราคาต่อหน่วยได้ในตาราง «รายการ» ช่องสีเหลือง — โปรแกรมจำไว้ตามชื่อรายการ\n"
                     "ถ้าใช้ Truss แทนจันทัน ให้ตรวจไม่ให้นับโครงหลังคาซ้ำ")
        tip.setWordWrap(True)
        left.addWidget(tip)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setStyleSheet("font-size: 15px; font-weight: 700;")
        left.addWidget(self.info)
        left.addStretch(1)
        b = QHBoxLayout()
        xl = QPushButton("บันทึก Excel (.xlsx)")
        xl.clicked.connect(self.export)
        ok = QPushButton("บันทึก")
        ok.setStyleSheet("font-weight: 700;")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("ยกเลิก")
        cancel.clicked.connect(self.reject)
        for w in (xl, ok, cancel):
            b.addWidget(w)
        left.addLayout(b)
        lay.addLayout(left)
        self.tabs = QTabWidget()
        self.t_sum = QTableWidget(0, 5)
        self.t_sum.setHorizontalHeaderLabels(["ลำดับ", "หมวด", "ค่าวัสดุ", "ค่าแรง", "รวม (บาท)"])
        self.t_sum.verticalHeader().hide()
        self.t_sum.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.t_bill = QTableWidget(0, len(BILL_HEAD))
        self.t_bill.setHorizontalHeaderLabels(BILL_HEAD)
        self.t_bill.verticalHeader().hide()
        self.t_bill.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.t_bill.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.t_bill.itemChanged.connect(self._edited)
        self.tabs.addTab(self.t_sum, "สรุป 8 หมวด")
        self.tabs.addTab(self.t_bill, "รายการ")
        lay.addWidget(self.tabs, 1)
        self.res = None
        self._loading = False
        self.recalc()

    def params(self) -> dict:
        return {"overhead": self.over.value(), "vat": self.vat.isChecked(),
                "waste": {k: w.value() for k, w in self.waste.items()}, "prices": self.prices,
                "steel_price": self.sp_mat.value(), "steel_lab": self.sp_lab.value()}

    def _edited(self, item):
        if self._loading or item.column() not in (6, 8):
            return
        desc = item.data(Qt.UserRole)
        if not desc:
            return
        try:
            v = float(item.text().replace(",", ""))
        except ValueError:
            return
        pr = dict(self.prices.get(desc) or {})
        pr["mat" if item.column() == 6 else "lab"] = v
        self.prices[desc] = pr
        self.recalc()

    def recalc(self, *_):
        self.res = P.compute({**self.data, "private_est": self.params()})
        self._loading = True
        bold = QFont()
        bold.setBold(True)
        rows = []
        for no, th, items in self.res["cats"]:
            m = sum(r["mat_total"] for r in items)
            lb = sum(r["lab_total"] for r in items)
            rows.append((str(no), th, m, lb, m + lb, False))
        st = self.res["settings"]
        rows.append(("", "รวมค่าก่อสร้าง", None, None, self.res["direct"], True))
        rows.append(("", f"ค่าดำเนินการและกำไร {st['overhead']:g}%", None, None, self.res["overhead"], True))
        if st["vat"]:
            rows.append(("", "ภาษีมูลค่าเพิ่ม 7%", None, None, self.res["vat"], True))
        rows.append(("", "รวมราคาทั้งสิ้น", None, None, self.res["total"], True))
        self.t_sum.setRowCount(len(rows))
        for r, (a, b, m, lb, t, strong) in enumerate(rows):
            for c, v in enumerate((a, b, "" if m is None else f"{m:,.2f}", "" if lb is None else f"{lb:,.2f}",
                                   f"{t:,.2f}")):
                it = QTableWidgetItem(v)
                if c >= 2:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if strong:
                    it.setFont(bold)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.t_sum.setItem(r, c, it)
        bill = []
        for no, th, items in self.res["cats"]:
            if not items:
                continue
            bill.append((str(no), th, None))
            for i, r in enumerate(items, 1):
                bill.append((f"{no}.{i}", r["desc"], r))
        self.t_bill.setRowCount(len(bill))
        for k, (code, desc, r) in enumerate(bill):
            if r is None:
                vals = (code, desc) + ("",) * 9
            else:
                vals = (code, desc, f"{r['net']:,.2f}", f"{r['waste']:g}", f"{r['qty']:,.2f}", r["unit"],
                        f"{r['mat']:,.2f}", f"{r['mat_total']:,.2f}", f"{r['lab']:,.2f}", f"{r['lab_total']:,.2f}",
                        f"{r['total']:,.2f}")
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if r is None:
                    it.setFont(bold)
                if r is not None and c in (6, 8):
                    it.setBackground(EDIT)
                    it.setData(Qt.UserRole, r["desc"])
                else:
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                if c >= 2 and c != 5:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.t_bill.setItem(k, c, it)
        self._loading = False
        self.info.setText(f"รวมราคาทั้งสิ้น {self.res['total']:,.2f} บาท")

    def export(self):
        from PySide6.QtWidgets import QFileDialog
        from core import wanic_calc as C
        path, _ = QFileDialog.getSaveFileName(self, "ประมาณราคางานเอกชน", "ประมาณราคางานเอกชน.xlsx",
                                              "ตารางคำนวณ (*.xlsx)")
        if not path:
            return
        b_ = C.basis(self.data)
        P.save_xlsx(self.res, path, {k: b_.get(k, "") for k in ("project", "owner", "place", "engineer",
                                                                "qualification")})
        self.info.setText(self.info.text() + f"\nบันทึกแล้ว: {path}")
