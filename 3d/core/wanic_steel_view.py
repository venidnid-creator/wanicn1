# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ออกแบบเหล็กรูปพรรณ — the window (beams, columns, base plates designed as
the settings change) and the booklet pages."""
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QHeaderView,
                               QLabel, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout)

from core import wanic_steel as S

OK = QColor("#15803D")
BAD = QColor("#B91C1C")


def beam_rows(res):
    return [(r["name"], f"{r['L']:.2f}", f"{r['M']:,.0f}", f"{r['V']:,.0f}", r["check"].sec.label,
             r["check"].text, f"{r['check'].ratio:.2f}") for r in res["beams"]]


def column_rows(res):
    return [(r["name"], f"{r['H']:.2f}", f"{r['P']:,.0f}", f"{r['M']:,.0f}", r["check"].sec.label,
             r["check"].text, f"{r['check'].ratio:.2f}") for r in res["columns"]]


def plate_rows(res):
    out = []
    for r in res["columns"]:
        p = r.get("plate")
        if p:
            out.append((r["name"], r["check"].sec.label, f"{r['P']:,.0f}",
                        f"PL {p['N']:g}×{p['B']:g} ซม. หนา {p['t']:.0f} มม.",
                        f"{p['fp']:.1f} / {p['fp_all']:.1f}", p["bolts"]))
    return out


BEAM_HEAD = ["คาน", "ช่วงยาว (ม.)", "M (กก.-ม.)", "V (กก.)", "หน้าตัด", "หน่วยแรง (กก./ตร.ซม.)", "อัตราส่วน"]
COL_HEAD = ["เสา", "สูง (ม.)", "P (กก.)", "M (กก.-ม.)", "หน้าตัด", "หน่วยแรง (กก./ตร.ซม.)", "อัตราส่วน"]
PLATE_HEAD = ["เสา", "หน้าตัด", "P (กก.)", "แผ่นเหล็กรองฐาน", "fp / 0.35fc′", "สลักยึด"]


def summary(res) -> str:
    st = res["settings"]
    nb = sum(1 for r in res["beams"] if not r["check"].ok)
    nc = sum(1 for r in res["columns"] if not r["check"].ok)
    return (f"ออกแบบหน่วยแรงที่ยอมให้ (ASD) · Fy {res['basis']['fy_steel']:,.0f} กก./ตร.ซม. · น้ำหนักบรรทุกใช้งาน "
            f"(ไม่คูณตัวคูณ) · ระยะค้ำปีกคาน Lb = {st['lb']:g}×ช่วง · ระยะเยื้องศูนย์เสา {st['ecc']:g} ม. · "
            f"การแอ่นตัว L/{st['defl']:g}\nคาน {len(res['beams'])} แนว · เสา {len(res['columns'])} ต้น · "
            f"น้ำหนักเหล็กรูปพรรณรวม {res['weight']:,.0f} กก. — "
            + ("✓ ผ่านทุกรายการ" if not (nb or nc) else f"✗ ไม่ผ่าน คาน {nb} / เสา {nc} (เกินขนาดใหญ่สุดในตาราง)"))


class SteelDialog(QDialog):
    def __init__(self, parent, data: dict):
        super().__init__(parent)
        self.setWindowTitle("ออกแบบเหล็กรูปพรรณ (เสา H / คาน WF)")
        self.resize(1240, 720)
        self.data = data
        st = S.settings(data)
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        form = QFormLayout()
        self.beams = QCheckBox("คานชั้นบน/คานหลังคาเป็นเหล็ก WF")
        self.beams.setChecked(bool(st["beams"]))
        self.cols = QCheckBox("เสาเป็นเหล็ก H (ตอม่อ/ฐานราก คสล.)")
        self.cols.setChecked(bool(st["columns"]))
        self.group = QCheckBox("จัดกลุ่ม: เบอร์เดียวกันในชั้นเดียวกันใช้หน้าตัดเดียวกัน")
        self.group.setChecked(bool(st["group"]))
        for w in (self.beams, self.cols, self.group):
            w.toggled.connect(self.recalc)
            form.addRow(w)
        self.sp = {}
        for key, th, lo, hi, dec in (("lb", "ระยะค้ำปีกรับแรงอัด Lb (สัดส่วนของช่วง)", 0.1, 1.0, 2),
                                     ("ecc", "ระยะเยื้องศูนย์น้ำหนักบนเสา (ม.)", 0.0, 0.5, 2),
                                     ("defl", "การแอ่นตัวยอมให้ L/…", 180, 1000, 0)):
            w = QDoubleSpinBox()
            w.setRange(lo, hi)
            w.setDecimals(dec)
            w.setSingleStep(0.05 if dec else 20)
            w.setValue(float(st[key]))
            w.valueChanged.connect(self.recalc)
            self.sp[key] = w
            form.addRow(th, w)
        top.addLayout(form)
        self.info = QLabel()
        self.info.setWordWrap(True)
        top.addWidget(self.info, 1)
        lay.addLayout(top)
        self.tabs = QTabWidget()
        self.t_beam = self._table(BEAM_HEAD)
        self.t_col = self._table(COL_HEAD)
        self.t_plate = self._table(PLATE_HEAD)
        self.tabs.addTab(self.t_beam, "คาน WF")
        self.tabs.addTab(self.t_col, "เสา H")
        self.tabs.addTab(self.t_plate, "แผ่นเหล็กรองฐาน")
        lay.addWidget(self.tabs, 1)
        b = QHBoxLayout()
        b.addStretch(1)
        pdf = QPushButton("รายการคำนวณเหล็กรูปพรรณ (.pdf)")
        pdf.clicked.connect(self.export_pdf)
        ok = QPushButton("บันทึก")
        ok.setStyleSheet("font-weight: 700;")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("ยกเลิก")
        cancel.clicked.connect(self.reject)
        for w in (pdf, ok, cancel):
            b.addWidget(w)
        lay.addLayout(b)
        self.res = None
        self.recalc()

    @staticmethod
    def _table(head):
        t = QTableWidget(0, len(head))
        t.setHorizontalHeaderLabels(head)
        t.verticalHeader().hide()
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        t.horizontalHeader().setStretchLastSection(True)
        return t

    def params(self) -> dict:
        p = {k: w.value() for k, w in self.sp.items()}
        p.update(beams=self.beams.isChecked(), columns=self.cols.isChecked(), group=self.group.isChecked())
        return p

    def recalc(self, *_):
        d = {**self.data, "steel": self.params()}
        self.res = S.design_building(d)
        for t, rows, ratio_col in ((self.t_beam, beam_rows(self.res), 6), (self.t_col, column_rows(self.res), 6),
                                   (self.t_plate, plate_rows(self.res), None)):
            t.setRowCount(len(rows))
            for r, row in enumerate(rows):
                for c, v in enumerate(row):
                    it = QTableWidgetItem(v)
                    if c == ratio_col:
                        it.setForeground(OK if float(v) <= 1 else BAD)
                    t.setItem(r, c, it)
        self.info.setText(summary(self.res))

    def export_pdf(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "รายการคำนวณเหล็กรูปพรรณ", "รายการคำนวณเหล็กรูปพรรณ.pdf",
                                              "PDF (*.pdf)")
        if not path:
            return
        from core.wanic_calc_book import Book
        b_ = self.res["basis"]
        bk = Book(path, {k: b_.get(k, "") for k in ("project", "owner", "place", "engineer", "qualification")})
        steel_pages(bk, self.res)
        bk.close()
        self.info.setText(self.info.text() + f"\nบันทึกแล้ว: {path}")


def steel_pages(bk, res):
    """Booklet pages: beams, columns, base plates (30 rows a page)."""
    from core.wanic_calc_book import GREEN, RED

    def mark(rows, col):
        return [tuple((v, GREEN if float(v) <= 1 else RED) if c == col else v for c, v in enumerate(r))
                for r in rows]

    parts = (("เหล็กรูปพรรณ — คาน WF", "Steel Beam", BEAM_HEAD, mark(beam_rows(res), 6),
              [118, 22, 28, 24, 46, 118, 22]),
             ("เหล็กรูปพรรณ — เสา H", "Steel Column", COL_HEAD, mark(column_rows(res), 6),
              [100, 20, 28, 26, 46, 136, 22]),
             ("เหล็กรูปพรรณ — แผ่นเหล็กรองฐาน", "Base Plate", PLATE_HEAD, plate_rows(res),
              [100, 46, 28, 80, 40, 90]))
    for k, (title, tag, head, rows, widths) in enumerate(parts):
        if not rows:
            continue
        for i in range(0, len(rows), 28):
            bk.page(title, tag)
            y = 34
            if k == 0 and i == 0:
                for ln in summary(res).split("\n"):
                    bk.text(10, y, 384, 7, ln, 5.6)
                    y += 7
                y += 2
            bk.table(10, y, widths, [tuple(head)] + rows[i:i + 28], 7.0, left=True)
