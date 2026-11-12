# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""บันได คสล. — the window of the RC panel: every stair of the building
with its form (straight / L / two-flight), turn, width, waist and bars; a
plan sketch and the checks of the selected one, live."""
from __future__ import annotations

import copy

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QComboBox, QDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget)

from core import wanic_building as B
from core import wanic_calc as C
from core import wanic_stair as ST

HEADS = ["ชั้น", "ตำแหน่ง (ม.)", "แบบบันได", "เลี้ยว", "กว้าง (ม.)", "หนาท้องบันได (ม.)", "เหล็กหลัก", "เหล็กกันร้าว"]
TURN_TH = {"left": "ซ้าย", "right": "ขวา"}


class StairSketch(QWidget):
    """The plan of one stair: flights, treads, landing, the way up."""

    def __init__(self):
        super().__init__()
        self.plan = None
        self.setMinimumSize(320, 260)

    def set_plan(self, plan):
        self.plan = plan
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#FFFFFF"))
        if not self.plan:
            return
        pts = [q for poly in self.plan["polys"] for q in poly]
        x0, x1 = min(q[0] for q in pts), max(q[0] for q in pts)
        y0, y1 = min(q[1] for q in pts), max(q[1] for q in pts)
        m = 24
        sc = min((self.width() - 2 * m) / max(x1 - x0, 0.1), (self.height() - 2 * m) / max(y1 - y0, 0.1))
        ox = (self.width() - (x1 - x0) * sc) / 2
        oy = (self.height() - (y1 - y0) * sc) / 2

        def T(q):
            return QPointF(ox + (q[0] - x0) * sc, self.height() - (oy + (q[1] - y0) * sc))
        lay = self.plan["layout"]
        p.setPen(QPen(QColor("#1F3A5F"), 1.6))
        for i, poly in enumerate(self.plan["polys"]):
            p.setBrush(QColor("#E8F0FB") if i >= len(lay["flights"]) else QColor("#FFFFFF"))
            p.drawPolygon(QPolygonF([T(q) for q in poly]))
        p.setPen(QPen(QColor("#64748B"), 0.8))
        for a, b in self.plan["treads"]:
            p.drawLine(T(a), T(b))
        wk = [T(q) for q in self.plan["walk"]]
        p.setPen(QPen(QColor("#B01E33"), 1.8))
        for a, b in zip(wk, wk[1:]):
            p.drawLine(a, b)
        p.setBrush(QColor("#B01E33"))
        p.drawEllipse(wk[0], 3.5, 3.5)
        p.drawText(wk[-1] + QPointF(5, -5), "ขึ้น")
        p.setPen(QColor("#334155"))
        for ld in lay["landings"]:
            c = QPointF(sum(T(q).x() for q in ld["pts"]) / 4, sum(T(q).y() for q in ld["pts"]) / 4)
            p.drawText(c + QPointF(-22, 4), f"ชานพัก +{ld['z']:.2f}")
        p.drawText(8, 16, f"{lay['n']} ลูกตั้ง × {lay['R'] * 100:.1f} ซม. · ลูกนอน {lay['g'] * 100:.0f} ซม. · "
                   f"กว้าง {lay['w']:.2f} ม.")


class StairDialog(QDialog):
    def __init__(self, parent, data):
        super().__init__(parent)
        self.setWindowTitle("บันได คสล. — ช่วงตรง / ตัว L / สองช่วง")
        self.setMinimumSize(1180, 640)
        self.data = copy.deepcopy(data)
        self.b_ = C.basis(data)
        self.rows = []                                 # the stair dicts (copies), in table order
        lay = QVBoxLayout(self)
        info = QLabel("บันไดวางในผังที่แท็บ «ออกแบบอาคาร» (เครื่องมือบันได) — ที่นี่เลือกแบบ ทิศเลี้ยว ขนาด และเหล็ก · "
                      "ตรวจตามกฎกระทรวง ฉบับที่ 55: ลูกตั้ง ≤ 20 ซม. · ลูกนอน ≥ 22 ซม. · กว้าง ≥ 0.80 ม. · "
                      "สูงช่วงละ ≤ 3.00 ม. · ท้องบันไดออกแบบเป็นพื้นทางเดียวพาดตามแนวบันได (ชานพักพาดไปกับช่วงบันได "
                      "มีคานรับชานพัก) · น้ำหนักจรบันได 300 กก./ตร.ม.")
        info.setWordWrap(True)
        info.setStyleSheet("background:#EEF6FF;padding:8px;border-radius:6px")
        lay.addWidget(info)
        self.table = QTableWidget(0, len(HEADS))
        self.table.setHorizontalHeaderLabels(HEADS)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        s = B.settings_of(self.data)
        p = ST.params(s)
        storeys = len(B.stacked(self.data)[0])
        for k, f in enumerate(self.data.get("floors") or []):
            for stp in f.get("stairs") or []:
                if not B.stair_used(stp, s, storeys):
                    continue
                r = self.table.rowCount()
                self.table.insertRow(r)
                self.rows.append(stp)
                self._item(r, 0, f"{k + 1}→{k + 2}", False)
                self._item(r, 1, f"({float(stp['x']):.2f}, {float(stp['y']):.2f})", False)
                cb = QComboBox()
                for key, th in B.STAIR_TYPES.items():
                    cb.addItem(th.split(" (")[0], key)
                cb.setCurrentIndex(list(B.STAIR_TYPES).index(B.stair_type(stp)))
                cb.currentIndexChanged.connect(self.update_view)
                self.table.setCellWidget(r, 2, cb)
                tb = QComboBox()
                for key, th in TURN_TH.items():
                    tb.addItem(th, key)
                tb.setCurrentIndex(0 if stp.get("turn", "left") == "left" else 1)
                tb.currentIndexChanged.connect(self.update_view)
                self.table.setCellWidget(r, 3, tb)
                self._item(r, 4, f"{B.stair_width(stp, s):g}")
                self._item(r, 5, f"{float(stp.get('t') or s['stair_t']):g}")
                self._item(r, 6, stp.get("bars") or p["stair_bars"])
                self._item(r, 7, stp.get("temp") or p["stair_temp"])
        self.table.itemChanged.connect(self.update_view)
        self.table.currentCellChanged.connect(lambda *_: self.update_view())
        lay.addWidget(self.table, 1)
        mid = QHBoxLayout()
        self.sketch = StairSketch()
        mid.addWidget(self.sketch, 1)
        self.report = QTextEdit()
        self.report.setReadOnly(True)
        mid.addWidget(self.report, 2)
        lay.addLayout(mid, 2)
        form = QFormLayout()
        self.ll = QLineEdit(f"{p['stair_ll']:g}")
        self.beam = QLineEdit(p["stair_beam"])
        self.ll.editingFinished.connect(self.update_view)
        self.beam.editingFinished.connect(self.update_view)
        form.addRow("น้ำหนักจรบันได (กก./ตร.ม.)", self.ll)
        form.addRow("คานรับชานพัก BS1 (กว้างxลึก เหล็กล่าง/บน ปลอก)", self.beam)
        lay.addLayout(form)
        b = QHBoxLayout()
        self.fix_btn = QPushButton("ปรับให้ผ่าน (บันไดที่เลือก)")
        self.fix_btn.clicked.connect(self.fix_selected)
        b.addWidget(self.fix_btn)
        b.addStretch(1)
        ok = QPushButton("บันทึก อัปเดตโมเดล และคำนวณใหม่")
        ok.setStyleSheet("font-weight:700")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("ยกเลิก")
        cancel.clicked.connect(self.reject)
        b.addWidget(ok)
        b.addWidget(cancel)
        lay.addLayout(b)
        if self.rows:
            self.table.setCurrentCell(0, 4)
        else:
            self.report.setHtml("<b>ยังไม่มีบันได</b> — วางบันไดในผังที่แท็บ «ออกแบบอาคาร» (อาคาร 2 ชั้นขึ้นไป) ก่อน")
        self.update_view()

    def _item(self, r, c, text, editable=True):
        it = QTableWidgetItem(text)
        if not editable:
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(r, c, it)

    def _row_values(self, r) -> dict:
        def txt(c):
            it = self.table.item(r, c)
            return it.text().strip() if it else ""

        def num(c, d):
            try:
                return float(txt(c))
            except ValueError:
                return d
        stp = self.rows[r]
        out = {"type": self.table.cellWidget(r, 2).currentData(), "turn": self.table.cellWidget(r, 3).currentData(),
               "w": num(4, B.stair_width(stp, B.settings_of(self.data))), "t": num(5, 0.15)}
        if txt(6):
            out["bars"] = txt(6)
        if txt(7):
            out["temp"] = txt(7)
        return out

    def settings(self) -> dict:
        s = dict(self.data.get("settings") or {})
        try:
            s["stair_ll"] = float(self.ll.text())
        except ValueError:
            pass
        if self.beam.text().strip():
            s["stair_beam"] = self.beam.text().strip()
        return s

    def update_view(self, *_a):
        r = self.table.currentRow()
        if not (0 <= r < len(self.rows)):
            return
        st = dict(self.rows[r], **self._row_values(r))
        s = B.settings_of(dict(self.data, settings=self.settings()))
        try:
            self.sketch.set_plan(B.stair_plan(st, s))
            dz = ST.design(st, s, self.b_, "บันไดที่เลือก")
        except Exception as e:                       # noqa: BLE001 - shown, never a crash
            self.report.setPlainText(f"คำนวณไม่ได้: {e}")
            return
        html = ["<b>ขนาดขั้น (กฎกระทรวง ฉบับที่ 55)</b><br>"]
        for a, v, lim, ok in dz["geo"]:
            html.append(f"<span style='color:{'#15803D' if ok else '#B91C1C'}'>{'✓' if ok else '✗'} {a} {v} "
                        f"({lim})</span><br>")
        html.append(f"<br><b>น้ำหนัก</b> ลาดเอียง {dz['dead_inc']:,.0f} + จร {dz['ll']:,.0f} → wu {dz['wu_inc']:,.0f} · "
                    f"ชานพัก wu {dz['wu_land']:,.0f} กก./ตร.ม.<br>")
        for m in dz["members"][1:]:
            col = "#15803D" if m.ok else "#B91C1C"
            html.append(f"<span style='color:{col}'><b>{'✓' if m.ok else '✗'} {m.name.replace('บันไดที่เลือก · ', '')}"
                        f"</b> — {m.demand} / {m.capacity} → {m.ratio:.2f}</span><br>"
                        f"<span style='color:#475569'>{m.note}</span>"
                        + (f" · <span style='color:{col}'>{m.reserve_text()}</span>" if m.qty else "") + "<br>")
        if not all(m.ok for m in dz["members"]):
            tips = ST.suggest(st, s, self.b_)[2]
            html.append("<br><b style='color:#B45309'>คำแนะนำ:</b><br>" + "<br>".join(f"→ {t}" for t in tips))
        self.report.setHtml("".join(html))

    def fix_selected(self):
        r = self.table.currentRow()
        if not (0 <= r < len(self.rows)):
            return
        st = dict(self.rows[r], **self._row_values(r))
        s = B.settings_of(dict(self.data, settings=self.settings()))
        ch, beam, _tips = ST.suggest(st, s, self.b_)
        self.table.blockSignals(True)
        if "t" in ch:
            self.table.item(r, 5).setText(f"{ch['t']:g}")
        if "bars" in ch:
            self.table.item(r, 6).setText(ch["bars"])
        if "temp" in ch:
            self.table.item(r, 7).setText(ch["temp"])
        self.table.blockSignals(False)
        if beam:
            self.beam.setText(beam)
        self.update_view()

    def apply(self, data: dict) -> int:
        """Write the table into the building document (the stair dicts by id
        and the stair settings); returns the number of stairs."""
        vals = {self.rows[r].get("id"): self._row_values(r) for r in range(len(self.rows))}
        for f in data.get("floors") or []:
            for stp in f.get("stairs") or []:
                if stp.get("id") in vals:
                    stp.update(vals[stp["id"]])
        s = dict(data.get("settings") or {})
        new = self.settings()
        for k in ("stair_ll", "stair_beam"):
            if k in new:
                s[k] = new[k]
        data["settings"] = s
        return len(vals)
