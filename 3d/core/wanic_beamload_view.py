# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""น้ำหนักเพิ่มบนคาน · คานยื่น · Checkload — the three windows of the
ออกแบบโครงสร้าง คสล. panel for loads the plan does not show (a water tank,
a wall on a beam, an air-conditioner), cantilever beams out of a column,
and the column-load sanity check."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)

from core import wanic_building as B

#: common extra loads, in words a house owner knows: (name, kind, size, type)
PRESETS = [
    ("ผนังก่ออิฐมอญครึ่งแผ่น สูง 3 ม. (≈ 180 กก./ตร.ม.)", "แผ่", 540.0, "D"),
    ("ผนังอิฐมวลเบา หนา 7.5 ซม. สูง 3 ม.", "แผ่", 270.0, "D"),
    ("ถังเก็บน้ำ 1,000 ลิตร (เต็ม)", "จุด", 1100.0, "D"),
    ("ถังเก็บน้ำ 2,000 ลิตร (เต็ม)", "จุด", 2200.0, "D"),
    ("เครื่องปรับอากาศ ตัวนอก (คอยล์ร้อน)", "จุด", 60.0, "D"),
    ("ราวกันตก/กระถางต้นไม้ ระเบียง", "แผ่", 100.0, "L"),
    ("ชั้นวางของหนัก / ตู้หนังสือ", "แผ่", 300.0, "L"),
]
LOAD_HEADS = ["ชั้นคาน (1=คอดิน)", "แนว (x/y)", "แนวเส้นที่ (ม.)", "เริ่ม (ม.)", "ถึง (ม.)", "ชนิด (จุด/แผ่)",
              "ขนาด (กก. หรือ กก./ม.)", "น้ำหนัก (คงที่/จร)", "หมายเหตุ"]
CANT_HEADS = ["ชั้นคาน (1=คอดิน)", "เสาที่ x (ม.)", "เสาที่ y (ม.)", "ทิศที่ยื่น", "ยาว (ม.)", "เบอร์คาน (ว่าง=ตามคานข้างเคียง)"]


def beam_lines(data) -> list:
    """Each beam line of the plan: (label, level, axis, line, lo, hi)."""
    E = B.elements(data)
    runs: dict = {}
    for e in E["beams"]:
        (x0, y0), (x1, y1) = e["p0"], e["p1"]
        axis = "x" if abs(y1 - y0) < 1e-6 else "y"
        c = round(y0 if axis == "x" else x0, 3)
        a, b = sorted((x0, x1) if axis == "x" else (y0, y1))
        k = (e["level"], axis, c)
        lo, hi = runs.get(k, (a, b))
        runs[k] = (min(lo, a), max(hi, b))
    out = []
    n = E["n"]
    for (lvl, axis, c), (lo, hi) in sorted(runs.items()):
        lv = "คานคอดิน" if lvl == 0 else "คานหลังคา" if lvl == n else f"คานชั้น {lvl + 1}"
        out.append((f"{lv} · แนว{'นอน' if axis == 'x' else 'ตั้ง'} {'y' if axis == 'x' else 'x'} = {c:.2f} "
                    f"({'x' if axis == 'x' else 'y'} {lo:.2f}–{hi:.2f})", lvl, axis, c, lo, hi))
    return out


def _f(t, default=0.0) -> float:
    try:
        return float(str(t).replace(",", "").strip())
    except ValueError:
        return default


def load_to_row(q) -> list:
    point = "P" in q and abs(float(q.get("a", 0)) - float(q.get("b", q.get("a", 0)))) < 1e-9
    return [str(int(q.get("level", 1)) + 1), q.get("axis", "x"), f"{float(q.get('line', 0)):g}",
            f"{float(q.get('a', 0)):g}", f"{float(q.get('b', q.get('a', 0))):g}", "จุด" if point else "แผ่",
            f"{float(q.get('P' if point else 'w', 0)):g}", "จร" if q.get("type") == "L" else "คงที่",
            q.get("note", "")]


def row_to_load(cells) -> dict | None:
    lvl = int(_f(cells[0], 2)) - 1
    axis = "y" if cells[1].strip().lower().startswith("y") else "x"
    a, b = _f(cells[3]), _f(cells[4], _f(cells[3]))
    size = _f(cells[6])
    if size <= 0:
        return None
    q = {"level": max(lvl, 0), "axis": axis, "line": _f(cells[2]), "type": "L" if "จร" in cells[7] else "D",
         "note": cells[8].strip()}
    if "จุด" in cells[5]:
        q.update(a=a, b=a, P=size)
    else:
        a, b = sorted((a, b))
        if b - a < 1e-6:
            return None
        q.update(a=a, b=b, w=size)
    return q


def cant_to_row(c) -> list:
    return [str(int(c.get("level", 1)) + 1), f"{float(c['x']):g}", f"{float(c['y']):g}",
            B.CANT_DIR_TH.get(c.get("dir", "+x"), "ขวา (+x)"), f"{float(c.get('L', 1.0)):g}", c.get("mark", "") or ""]


def row_to_cant(cells) -> dict | None:
    L = _f(cells[4])
    if L <= 0:
        return None
    d = next((k for k, v in B.CANT_DIR_TH.items() if v == cells[3] or k == cells[3].strip()), "+x")
    out = {"level": max(int(_f(cells[0], 2)) - 1, 0), "x": _f(cells[1]), "y": _f(cells[2]), "dir": d, "L": L}
    if cells[5].strip():
        out["mark"] = cells[5].strip()
    return out


class _TableDialog(QDialog):
    heads: list = []

    def _table(self, rows):
        self.table = QTableWidget(0, len(self.heads))
        self.table.setHorizontalHeaderLabels(self.heads)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        for r in rows:
            self.add_row(r)
        return self.table

    def add_row(self, cells):
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c, v in enumerate(cells):
            self.table.setItem(r, c, QTableWidgetItem(str(v)))
        self.table.setCurrentCell(r, 0)

    def del_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def cells(self):
        for r in range(self.table.rowCount()):
            yield [(self.table.item(r, c).text() if self.table.item(r, c) else "") for c in range(len(self.heads))]

    def _buttons(self, lay, extra=()):
        b = QHBoxLayout()
        for w in extra:
            b.addWidget(w)
        dl = QPushButton("ลบแถวที่เลือก")
        dl.clicked.connect(self.del_row)
        b.addWidget(dl)
        b.addStretch(1)
        ok = QPushButton("บันทึก อัปเดตโมเดล และคำนวณใหม่")
        ok.setStyleSheet("font-weight:700")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("ยกเลิก")
        cancel.clicked.connect(self.reject)
        b.addWidget(ok)
        b.addWidget(cancel)
        lay.addLayout(b)


class BeamLoadDialog(_TableDialog):
    heads = LOAD_HEADS

    def __init__(self, parent, data):
        super().__init__(parent)
        self.setWindowTitle("น้ำหนักเพิ่มบนคาน (น้ำหนักจุด / น้ำหนักแผ่)")
        self.setMinimumSize(1080, 520)
        lay = QVBoxLayout(self)
        info = QLabel("ใส่น้ำหนักที่ไม่มีในผัง เช่น ถังน้ำ ผนังที่ก่อบนคาน แอร์ ระเบียง — "
                      "<b>น้ำหนักจุด</b> = ของวางจุดเดียว (กก.) ใส่ «เริ่ม» = ตำแหน่ง · "
                      "<b>น้ำหนักแผ่</b> = ของยาวตามคาน (กก./ม.) จาก «เริ่ม» ถึง «ถึง» · "
                      "ตำแหน่งวัดตามแกนเดียวกับผัง (ม.) · โปรแกรมคูณตัวคูณน้ำหนักให้เอง (คงที่ 1.4 / จร 1.7)")
        info.setWordWrap(True)
        info.setStyleSheet("background:#EEF6FF;padding:8px;border-radius:6px")
        lay.addWidget(info)
        pick = QHBoxLayout()
        pick.addWidget(QLabel("คาน:"))
        self.lines = QComboBox()
        self.lines_data = beam_lines(data)
        for t, *_r in self.lines_data:
            self.lines.addItem(t)
        pick.addWidget(self.lines, 2)
        pick.addWidget(QLabel("ของที่วาง:"))
        self.preset = QComboBox()
        self.preset.addItem("กำหนดเอง")
        for p in PRESETS:
            self.preset.addItem(f"{p[0]} — {p[2]:,.0f} {'กก.' if p[1] == 'จุด' else 'กก./ม.'}")
        pick.addWidget(self.preset, 2)
        add = QPushButton("เพิ่มบนคานนี้")
        add.clicked.connect(self.add_from_pick)
        pick.addWidget(add)
        lay.addLayout(pick)
        lay.addWidget(self._table([load_to_row(q) for q in B.beam_loads(data)]))
        self._buttons(lay)

    def add_from_pick(self):
        if not self.lines_data:
            return
        _t, lvl, axis, c, lo, hi = self.lines_data[self.lines.currentIndex()]
        k = self.preset.currentIndex()
        if k > 0:
            name, kind, size, typ = PRESETS[k - 1]
        else:
            name, kind, size, typ = "", "แผ่", 500.0, "D"
        mid = (lo + hi) / 2
        a, b = (mid, mid) if kind == "จุด" else (lo, hi)
        self.add_row([str(lvl + 1), axis, f"{c:g}", f"{a:g}", f"{b:g}", kind, f"{size:g}",
                      "จร" if typ == "L" else "คงที่", name.split(" (")[0]])

    def loads(self) -> list:
        return [q for q in (row_to_load(c) for c in self.cells()) if q]


class CantileverDialog(_TableDialog):
    heads = CANT_HEADS

    def __init__(self, parent, data):
        super().__init__(parent)
        self.setWindowTitle("คานยื่น (Cantilever)")
        self.setMinimumSize(900, 440)
        E = B.elements(data)
        lay = QVBoxLayout(self)
        info = QLabel("คานที่ยื่นออกจากเสา ปลายอีกด้านลอย (ระเบียง กันสาด) — เลือกเสา ทิศ และความยาว · "
                      "โมเดล 3D แบบ และ BOQ เพิ่มคานให้อัตโนมัติ · น้ำหนักบนคานยื่น (พื้นระเบียง ราว) "
                      "ใส่เพิ่มที่ «น้ำหนักเพิ่มบนคาน…» · คานยื่นควรลึกอย่างน้อย L/8 (ACI)")
        info.setWordWrap(True)
        info.setStyleSheet("background:#EEF6FF;padding:8px;border-radius:6px")
        lay.addWidget(info)
        pick = QHBoxLayout()
        pick.addWidget(QLabel("เสา:"))
        self.cols = QComboBox()
        self.cols_data = sorted({(round(c["x"], 3), round(c["y"], 3)) for c in E["columns"]})
        for x, y in self.cols_data:
            self.cols.addItem(f"({x:.2f}, {y:.2f})")
        pick.addWidget(self.cols, 1)
        pick.addWidget(QLabel("ชั้นคาน:"))
        self.level = QComboBox()
        for lv in range(E["n"] + 1):
            self.level.addItem("คานคอดิน" if lv == 0 else "คานหลังคา" if lv == E["n"] else f"คานชั้น {lv + 1}", lv)
        if E["n"] >= 1:
            self.level.setCurrentIndex(1)
        pick.addWidget(self.level)
        pick.addWidget(QLabel("ทิศ:"))
        self.dir = QComboBox()
        for k, v in B.CANT_DIR_TH.items():
            self.dir.addItem(v, k)
        pick.addWidget(self.dir)
        add = QPushButton("เพิ่มคานยื่น 1.50 ม.")
        add.clicked.connect(self.add_from_pick)
        pick.addWidget(add)
        lay.addLayout(pick)
        lay.addWidget(self._table([cant_to_row(c) for c in B.cantilevers(data)]))
        self._buttons(lay)

    def add_from_pick(self):
        if not self.cols_data:
            return
        x, y = self.cols_data[self.cols.currentIndex()]
        self.add_row([str(self.level.currentData() + 1), f"{x:g}", f"{y:g}", self.dir.currentText(), "1.5", ""])

    def cantilevers(self) -> list:
        return [c for c in (row_to_cant(r) for r in self.cells()) if c]


class CheckloadDialog(QDialog):
    def __init__(self, parent, ck: dict):
        super().__init__(parent)
        self.setWindowTitle("Checkload — ตรวจน้ำหนักลงเสา")
        self.setMinimumSize(1000, 520)
        lay = QVBoxLayout(self)
        lo, hi = ck["range"]
        head = QLabel(f"<b>น้ำหนักลงเสาชั้นล่างรวม {ck['total'] / 1000:,.1f} ตัน</b> บนพื้นที่รับน้ำหนักรวม "
                      f"{ck['area']:,.1f} ตร.ม. (ทุกชั้น + หลังคา) → เฉลี่ย <b>{ck['mean']:,.0f} กก./ตร.ม.</b> "
                      f"(บ้าน คสล. ทั่วไป {lo:,.0f}–{hi:,.0f})<br>"
                      "Wcol = น้ำหนักที่คำนวณได้จากคาน (ใช้งาน) · Wcol-Area = พื้นที่ × ค่าเฉลี่ยทั้งอาคาร · "
                      "Wfloor = Wcol ÷ พื้นที่ — ถ้าต่างกันมาก แปลว่ามีน้ำหนักพิเศษ หรือใส่ข้อมูลผิด ควรตรวจทาน")
        head.setWordWrap(True)
        lay.addWidget(head)
        t = QTableWidget(len(ck["rows"]), 8)
        t.setHorizontalHeaderLabels(["เสา", "ตำแหน่ง", "พื้นที่รับ (ตร.ม.)", "Wcol (ตัน)", "Wcol-Area (ตัน)",
                                     "ต่าง (%)", "Wfloor (กก./ตร.ม.)", "ผล"])
        t.verticalHeader().hide()
        for i, r in enumerate(ck["rows"]):
            vals = [r["mark"], f"({r['x']:.2f}, {r['y']:.2f})", f"{r['A']:,.2f}", f"{r['W'] / 1000:,.2f}",
                    f"{r['WA'] / 1000:,.2f}", f"{r['diff']:+.0f}", f"{r['Wf']:,.0f}", r["note"]]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                if c == 7:
                    it.setForeground(QColor("#15803D") if r["ok"] and v == "ปกติ" else
                                     QColor("#B45309") if r["ok"] else QColor("#B91C1C"))
                t.setItem(i, c, it)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        t.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(t)
        b = QHBoxLayout()
        b.addStretch(1)
        ok = QPushButton("ปิด")
        ok.clicked.connect(self.accept)
        b.addWidget(ok)
        lay.addLayout(b)
