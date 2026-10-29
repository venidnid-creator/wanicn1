# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
# WANICNSURVEY 3D — "WANIC โปรไฟล์" (parametric profiles along paths).
# Developed for WANICNSURVEY by นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ, 2569.
"""สร้างชิ้นส่วนจากรูปตัดสำเร็จรูปตามเส้นที่เลือก.

Pick a section (steel H / I / channel / lip channel / angle / tube / pipe,
concrete beam / T-beam / pile, kerb, curb & gutter, U-ditch, lined
trapezoid ditch, box culvert, RC pipe, road surface, embankment), set its
sizes, select a chain of edges (or one face for its outline) and press
«สร้างตามเส้นที่เลือก»: one group per member, which remembers its section
so it can be resized later, and is listed in the member schedule (count,
length, weight). The geometry engine is :mod:`core.wanic_profiles`.
"""
from __future__ import annotations

from core.wanic_ui import safe as _safe

from pathlib import Path

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core import wanic_profiles as P

TITLE = "โปรไฟล์"
NAVY = QColor("#0F2A44")
FILL = QColor("#3BA3D8")


def _q(p):
    return (float(p.x()), float(p.y()), float(p.z()))


def _matrix_of(scene, group):
    if group is None:
        return None
    from core.group import iter_placements
    for top in scene.groups:
        for g, m in iter_placements(top):
            if g is group:
                return m
    return getattr(group, "xform", None)


def path_from_selection(scene):
    """``(points, closed)`` in world metres from the selected edges (one
    chain) or one selected face's outline, or a Thai reason (str)."""
    from core.sweep import order_path_edges
    sel = list(scene.selection)
    edges = [e for e in sel if hasattr(e, "v0") and hasattr(e, "v1")]
    faces = [f for f in sel if hasattr(f, "loop") and hasattr(f, "vertices")]
    if edges:
        got = order_path_edges(edges)
        if got is None:
            return ("เส้นที่เลือกต้องต่อกันเป็นสายเดียว (ไม่แตกกิ่ง ไม่ขาดตอน)")
        pts, closed = got
    elif len(faces) == 1:
        pts, closed = list(faces[0].vertices), True
    else:
        return ("เลือกเส้นทางก่อน: เส้นที่ต่อกันเป็นสายเดียว "
                "หรือพื้นผิว 1 ผืน (ใช้ขอบรอบนอก)")
    m = _matrix_of(scene, getattr(scene, "edit_group", None))
    if m is not None:
        pts = [m.map(p) for p in pts]
    return [_q(p) for p in pts], bool(closed)


class SectionPreview(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.setAlignment(Qt.AlignCenter)
        self._shape = None

    def show_section(self, family, params, anchor, rotation, mirror):
        try:
            self._shape = P.placed_outline(family, params, anchor, rotation,
                                           mirror)
        except Exception:
            self._shape = None
        self.update()

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if not self._shape:
            return
        outer, holes = self._shape
        pts = outer + [q for h in holes for q in h] + [(0.0, 0.0)]
        x0 = min(x for x, _ in pts)
        x1 = max(x for x, _ in pts)
        y0 = min(y for _, y in pts)
        y1 = max(y for _, y in pts)
        w, h = self.width() - 20, self.height() - 20
        k = min(w / max(x1 - x0, 1e-9), h / max(y1 - y0, 1e-9))
        cx = 10 + (w - (x1 - x0) * k) / 2
        cy = 10 + (h - (y1 - y0) * k) / 2

        def px(q):
            return QPointF(cx + (q[0] - x0) * k, cy + (y1 - q[1]) * k)
        path = QPainterPath()
        path.setFillRule(Qt.OddEvenFill)
        for loop in [outer] + holes:
            path.moveTo(px(loop[0]))
            for q in loop[1:]:
                path.lineTo(px(q))
            path.closeSubpath()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        fill = QColor(FILL)
        fill.setAlpha(110)
        p.setBrush(fill)
        p.setPen(QPen(NAVY, 1.5))
        p.drawPath(path)
        # The insertion point: where the path runs through the section.
        o = px((0.0, 0.0))
        p.setPen(QPen(QColor("#E5394D"), 2))
        p.drawLine(o + QPointF(-7, 0), o + QPointF(7, 0))
        p.drawLine(o + QPointF(0, -7), o + QPointF(0, 7))
        p.end()


class ProfilePanel(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self._spins: dict = {}
        self._busy = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)
        head = QLabel("<b>WANIC โปรไฟล์</b> — สร้างชิ้นส่วนจากรูปตัดตามเส้นที่เลือก")
        head.setWordWrap(True)
        lay.addWidget(head)

        form = QFormLayout()
        self.family = QComboBox()
        for group, fams in P.family_groups():
            self.family.addItem(f"— {group} —", None)
            i = self.family.count() - 1
            self.family.model().item(i).setEnabled(False)
            for f in fams:
                self.family.addItem(f["name"], f["key"])
        self.family.setCurrentIndex(1)
        self.family.currentIndexChanged.connect(self._family_changed)
        form.addRow("รูปตัด", self.family)
        self.preset = QComboBox()
        self.preset.currentIndexChanged.connect(self._preset_changed)
        form.addRow("ขนาดมาตรฐาน", self.preset)
        lay.addLayout(form)

        self.params_box = QWidget()
        self.params_form = QFormLayout(self.params_box)
        self.params_form.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.params_box)

        place = QFormLayout()
        self.anchor = QComboBox()
        for k, v in P.ANCHORS.items():
            self.anchor.addItem(v, k)
        self.anchor.currentIndexChanged.connect(self._update_preview)
        place.addRow("จุดที่เส้นทางผ่าน", self.anchor)
        row = QHBoxLayout()
        self.rotation = QDoubleSpinBox()
        self.rotation.setRange(-360, 360)
        self.rotation.setSuffix("°")
        self.rotation.valueChanged.connect(self._update_preview)
        self.mirror = QCheckBox("กลับด้าน")
        self.mirror.toggled.connect(self._update_preview)
        row.addWidget(self.rotation)
        row.addWidget(self.mirror)
        row.addStretch(1)
        place.addRow("หมุนรูปตัด", row)
        row2 = QHBoxLayout()
        self.off_u = QDoubleSpinBox()
        self.off_v = QDoubleSpinBox()
        for w, t in ((self.off_u, "ขวา "), (self.off_v, "ขึ้น ")):
            w.setRange(-100000, 100000)
            w.setDecimals(1)
            w.setPrefix(t)
            w.setSuffix(" มม.")
            row2.addWidget(w)
        place.addRow("เลื่อนจากเส้นทาง", row2)
        self.name = QLineEdit()
        self.name.setPlaceholderText("(ตั้งชื่อตามขนาดอัตโนมัติ)")
        place.addRow("ชื่อชิ้นส่วน", self.name)
        self.layer = QComboBox()
        place.addRow("เลเยอร์", self.layer)
        self.ifc = QComboBox()
        self.ifc.addItem("(ไม่ติดแท็ก)", "")
        from core.bim import IFC_CLASSES
        for c in IFC_CLASSES:
            self.ifc.addItem(c, c)
        place.addRow("แท็ก BIM", self.ifc)
        lay.addLayout(place)

        self.preview = SectionPreview()
        lay.addWidget(self.preview)
        self.info = QLabel()
        self.info.setWordWrap(True)
        lay.addWidget(self.info)

        b1 = QHBoxLayout()
        self.make_btn = QPushButton("🛠 สร้างตามเส้นที่เลือก")
        self.make_btn.setToolTip("เลือกเส้นที่ต่อกันเป็นสายเดียว หรือพื้นผิว 1 ผืน "
                                 "แล้วกดปุ่มนี้")
        self.make_btn.clicked.connect(lambda _=False: _safe(self, self.make_from_selection))
        self.load_btn = QPushButton("📐 อ่านจากชิ้นที่เลือก")
        self.load_btn.setToolTip("นำรูปตัดของชิ้นส่วนโปรไฟล์ที่เลือกมาแสดงในฟอร์ม")
        self.load_btn.clicked.connect(lambda _=False: _safe(self, self.load_selected))
        self.apply_btn = QPushButton("🔁 เปลี่ยนรูปตัดของที่เลือก")
        self.apply_btn.setToolTip("สร้างชิ้นส่วนโปรไฟล์ที่เลือกใหม่ด้วยรูปตัดในฟอร์ม "
                                  "(ตามเส้นทางเดิม)")
        self.apply_btn.clicked.connect(lambda _=False: _safe(self, self.apply_to_selected))
        for b in (self.make_btn, self.load_btn, self.apply_btn):
            b1.addWidget(b)
        lay.addLayout(b1)

        sched_head = QHBoxLayout()
        sched_head.addWidget(QLabel("<b>รายการโปรไฟล์ในโมเดล</b>"))
        sched_head.addStretch(1)
        exp = QPushButton("📤 ส่งออก CSV…")
        exp.clicked.connect(lambda _=False: _safe(self, self.export_schedule))
        sched_head.addWidget(exp)
        lay.addLayout(sched_head)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["รูปตัด", "จำนวน", "ยาวรวม (ม.)", "ปริมาตร (ลบ.ม.)",
             "น้ำหนัก (กก.)", "ประเภท"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.table, 1)
        note = QLabel("น้ำหนักคิดจากพื้นที่หน้าตัดที่วาด × 7,850 กก./ลบ.ม. "
                      "(ไม่รวมมุมโค้ง) จึงต่ำกว่าตารางผู้ผลิตเล็กน้อย")
        note.setWordWrap(True)
        note.setStyleSheet("color: palette(mid);")
        lay.addWidget(note)
        from core.wanic_sign import label_html
        _sig = QLabel(label_html("WANIC โปรไฟล์"))
        _sig.setWordWrap(True)
        lay.addWidget(_sig)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(400)
        self._timer.timeout.connect(self.refresh)
        self._family_changed()

    # ---- form ---------------------------------------------------------------
    def family_key(self) -> str:
        return self.family.currentData() or "h"

    def _family_changed(self, *_):
        if self.family.currentData() is None:
            return
        fam = P.FAMILIES[self.family_key()]
        self._busy = True
        self.preset.clear()
        for label, p in fam["presets"]:
            self.preset.addItem(label, p)
        self.preset.addItem("(กำหนดเอง)", None)
        while self.params_form.rowCount():
            self.params_form.removeRow(0)
        self._spins = {}
        for k, label in fam["params"]:
            sp = QDoubleSpinBox()
            sp.setRange(-1e6 if k == "d" else 0.0, 1e6)
            sp.setDecimals(2)
            if k not in P.UNITLESS:
                sp.setSuffix(" มม.")
            sp.valueChanged.connect(self._param_edited)
            self.params_form.addRow(label, sp)
            self._spins[k] = sp
        i = self.ifc.findData(fam["ifc"])
        self.ifc.setCurrentIndex(max(i, 0))
        self._busy = False
        self.preset.setCurrentIndex(0)
        self._preset_changed()

    def _preset_changed(self, *_):
        p = self.preset.currentData()
        if not p or self._busy:
            self._update_preview()
            return
        self._busy = True
        for k, sp in self._spins.items():
            sp.setValue(float(p.get(k, sp.value())))
        self._busy = False
        self._update_preview()

    def _param_edited(self, *_):
        if self._busy:
            return
        self._busy = True
        cur = self.params()
        idx = self.preset.count() - 1
        for i in range(self.preset.count()):
            p = self.preset.itemData(i)
            if p and all(abs(float(p[k]) - cur.get(k, 0)) < 1e-9 for k in p):
                idx = i
                break
        self.preset.setCurrentIndex(idx)
        self._busy = False
        self._update_preview()

    def params(self) -> dict:
        return {k: sp.value() for k, sp in self._spins.items()}

    def spec(self) -> dict:
        return {"family": self.family_key(), "params": self.params(),
                "anchor": self.anchor.currentData(),
                "rotation": self.rotation.value(),
                "mirror": self.mirror.isChecked(),
                "offset": (self.off_u.value() / 1000.0,
                           self.off_v.value() / 1000.0),
                "name": self.name.text().strip(),
                "layer": self.layer.currentData() or None,
                "ifc": self.ifc.currentData() or ""}

    def _update_preview(self, *_):
        fam, p = self.family_key(), self.params()
        why = P.validate(fam, p)
        if why:
            self.info.setText(f"<span style='color:#B01E33'>{why}</span>")
            self.preview.show_section(None, None, "c", 0, False)
            self.make_btn.setEnabled(False)
            return
        self.make_btn.setEnabled(True)
        self.preview.show_section(fam, p, self.anchor.currentData() or "c",
                                  self.rotation.value(),
                                  self.mirror.isChecked())
        a = P.section_area(fam, p)
        text = (f"<b>{P.describe(fam, p)}</b> · พื้นที่หน้าตัด {a * 1e4:,.2f} ตร.ซม."
                f" · ปริมาตร {a:,.4f} ลบ.ม./ม.")
        if P.FAMILIES[fam]["steel"]:
            text += f" · น้ำหนักประมาณ {P.weight_per_m(fam, p):,.2f} กก./ม."
        self.info.setText(text + " · <span style='color:#E5394D'>+</span> "
                          "= จุดที่เส้นทางผ่าน")

    def _fill_layers(self):
        cur = self.layer.currentData()
        self.layer.blockSignals(True)
        self.layer.clear()
        self.layer.addItem("(เลเยอร์ปัจจุบัน/ค่าเริ่มต้น)", None)
        for lay in getattr(self.app.scene, "layers", []) or []:
            name = getattr(lay, "name", None)
            if name and name != "Layer 0":
                self.layer.addItem(name, name)
        i = self.layer.findData(cur)
        self.layer.setCurrentIndex(max(i, 0))
        self.layer.blockSignals(False)

    # ---- actions ------------------------------------------------------------
    def _flash(self, text):
        f = getattr(self.app.viewport, "flash_status", None)
        if callable(f):
            f(text)

    def make_from_selection(self):
        from core.history import InsertGroupCommand
        got = path_from_selection(self.app.scene)
        if isinstance(got, str):
            QMessageBox.information(self, TITLE, got)
            return
        pts, closed = got
        spec = self.spec()
        spec.update(path=pts, closed=closed)
        g = P.build_member(spec)
        if isinstance(g, str):
            QMessageBox.warning(self, TITLE, g)
            return
        self.app.viewport.history.execute(InsertGroupCommand(g))
        self._after_edit()
        rec = P.member_record(g)
        self._flash(f"สร้าง {rec['label']} ยาว {rec['length']:,.3f} ม. แล้ว")

    def _selected_members(self):
        return [g for g in self.app.scene.selection
                if P.member_record(g) is not None]

    def load_selected(self):
        ms = self._selected_members()
        if not ms:
            QMessageBox.information(self, TITLE, "เลือกชิ้นส่วนที่สร้างด้วย "
                                    "WANIC โปรไฟล์ก่อน")
            return
        rec = P.member_record(ms[0])
        i = self.family.findData(rec.get("family"))
        if i < 0:
            return
        self.family.setCurrentIndex(i)
        self._busy = True
        for k, sp in self._spins.items():
            sp.setValue(float(rec["params"].get(k, sp.value())))
        self._busy = False
        self._param_edited()
        self.anchor.setCurrentIndex(max(self.anchor.findData(rec.get("anchor")), 0))
        self.rotation.setValue(float(rec.get("rotation") or 0))
        self.mirror.setChecked(bool(rec.get("mirror")))
        off = rec.get("offset") or (0, 0)
        self.off_u.setValue(float(off[0]) * 1000)
        self.off_v.setValue(float(off[1]) * 1000)
        self._update_preview()

    def apply_to_selected(self):
        from core.history import (CompoundCommand, DeleteGroupCommand,
                                  InsertGroupCommand)
        ms = self._selected_members()
        if not ms:
            QMessageBox.information(self, TITLE, "เลือกชิ้นส่วนที่สร้างด้วย "
                                    "WANIC โปรไฟล์ก่อน")
            return
        cmds, fails = [], 0
        for old in ms:
            rec = P.member_record(old)
            spec = self.spec()
            spec.update(path=rec["path"], closed=rec.get("closed"))
            if not spec["name"] and old.name != rec.get("label"):
                spec["name"] = old.name           # keep a name the user gave
            if spec["layer"] is None:
                spec["layer"] = getattr(old, "layer", None)
            g = P.build_member(spec)
            if isinstance(g, str):
                fails += 1
                continue
            cmds += [DeleteGroupCommand(old), InsertGroupCommand(g)]
        if cmds:
            self.app.viewport.history.execute(CompoundCommand(cmds))
            self._after_edit()
        msg = f"เปลี่ยนรูปตัดแล้ว {len(cmds) // 2} ชิ้น"
        if fails:
            msg += f" · ทำไม่ได้ {fails} ชิ้น"
        self._flash(msg)

    def _after_edit(self):
        vp = self.app.viewport
        n = getattr(vp, "notify_scene_changed", None)
        if callable(n):
            n()
        vp.update()
        self.refresh()

    def export_schedule(self):
        rows = P.schedule(self.app.scene)
        if not rows:
            QMessageBox.information(self, TITLE, "ยังไม่มีชิ้นส่วนโปรไฟล์ในโมเดล")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "ส่งออกรายการโปรไฟล์", "รายการโปรไฟล์.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            Path(path).write_text(P.schedule_csv(rows), encoding="utf-8")
        except OSError as e:
            QMessageBox.warning(self, TITLE, f"บันทึกไม่ได้: {e}")

    # ---- schedule -------------------------------------------------------------
    def schedule(self):
        self._timer.start()

    def refresh(self):
        self._fill_layers()
        try:
            rows = P.schedule(self.app.scene)
        except Exception:
            rows = []
        self.table.setRowCount(len(rows))
        right = int(Qt.AlignRight | Qt.AlignVCenter)
        for r, row in enumerate(rows):
            vals = [row["label"], str(row["count"]), f"{row['length']:,.3f}",
                    f"{row['volume']:,.4f}",
                    "" if row["weight"] is None else f"{row['weight']:,.2f}",
                    row["family"]]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c in (1, 2, 3, 4):
                    it.setTextAlignment(right)
                self.table.setItem(r, c, it)


def _join_tray(window, dock) -> None:
    tray = getattr(window, "tray", None)
    try:
        if (tray is None or dock.isFloating() or dock.isHidden()
                or window.tabifiedDockWidgets(dock)
                or window.dockWidgetArea(dock) != window.dockWidgetArea(tray)):
            return
        window.tabifyDockWidget(tray, dock)
        tray.raise_()
    except Exception:
        pass


def setup(app) -> None:
    panel = ProfilePanel(app)
    dock = app.add_panel(TITLE, panel)
    app.window._wanic_profiles = panel
    app.on_document_changed(panel.schedule)

    def show():
        app.show_panel(dock)
        dock.raise_()
        panel.refresh()

    app.add_menu_action("WANIC โปรไฟล์…", show,
                        tip="สร้างเหล็กรูปพรรณ คาน คสล. คันหิน รางระบายน้ำ "
                            "ท่อ ถนน ตามเส้นที่เลือก")

    def context(menu, selection):
        sel = list(selection)
        has_path = any(hasattr(e, "v0") for e in sel) or (
            len(sel) == 1 and hasattr(sel[0], "loop"))
        members = [g for g in sel if P.member_record(g) is not None]
        if has_path:
            def make():
                show()
                panel.make_from_selection()
            menu.addAction("สร้างโปรไฟล์ตามเส้นที่เลือก",
                           lambda: QTimer.singleShot(0, make))
        if members:
            def edit():
                show()
                panel.load_selected()
            menu.addAction("แก้ไขรูปตัดโปรไฟล์…",
                           lambda: QTimer.singleShot(0, edit))

    app.add_context_menu(context)
    QTimer.singleShot(0, lambda: _join_tray(app.window, dock))
    QTimer.singleShot(0, panel.refresh)
