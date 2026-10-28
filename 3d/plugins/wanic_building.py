# SPDX-License-Identifier: GPL-3.0-or-later
# WANICNSURVEY 3D — "WANIC ออกแบบอาคาร" (room plan → frame → roof → BOQ).
# Developed for WANICNSURVEY by นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ, 2569.
"""วางผังห้อง แล้วสร้างโครงสร้างและโครงหลังคาอัตโนมัติ.

A plan canvas (one floor at a time, the floor below shown faintly) where
rectangular rooms are placed, dragged with snapping, rotated and resized;
then one click builds footings, stumps, columns, beams, slabs and walls,
and a gable or hip steel roof with its covering. Rebuilding replaces what
the previous build made (one undo step); the price lines go straight into
WANIC ถอดปริมาณ. The layout engine is :mod:`core.wanic_building`.
"""
from __future__ import annotations

import copy

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMenu, QMessageBox, QPushButton, QScrollArea, QSpinBox, QVBoxLayout,
    QWidget,
)

from core import wanic_building as B

TITLE = "ออกแบบอาคาร"
NAVY = QColor("#0F2A44")
ROOM = QColor(64, 170, 110, 70)
ROOM_EDGE = QColor(30, 120, 70)
SEL = QColor("#E8772E")
GHOST = QColor(120, 130, 140, 60)


class PlanCanvas(QWidget):
    """The plan of one floor, in metres (x right, y up)."""

    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel
        self.setMinimumHeight(320)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.scale = 40.0                       # pixels per metre
        self.origin = QPointF(40, 280)          # screen point of (0, 0)
        self.selected = None                    # room id
        self._drag = None                       # (room id, dx, dy, rooms copy)
        self._pan = None
        self._hover = None

    # ---- coordinates ------------------------------------------------------
    def to_screen(self, x, y) -> QPointF:
        return QPointF(self.origin.x() + x * self.scale,
                       self.origin.y() - y * self.scale)

    def to_world(self, pt):
        return ((pt.x() - self.origin.x()) / self.scale,
                (self.origin.y() - pt.y()) / self.scale)

    def rooms(self):
        return self.panel.rooms()

    def room_at(self, x, y):
        for rm in reversed(self.rooms()):
            if (rm["x"] <= x <= rm["x"] + rm["w"]
                    and rm["y"] <= y <= rm["y"] + rm["d"]):
                return rm
        return None

    def fit(self):
        rooms = self.rooms() + self.panel.rooms(self.panel.floor - 1)
        fp = B.footprint(rooms) or (0, 0, 10, 8)
        w = max(fp[2] - fp[0], 4.0) + 3
        h = max(fp[3] - fp[1], 4.0) + 3
        self.scale = max(8.0, min(self.width() / w, self.height() / h))
        cx, cy = (fp[0] + fp[2]) / 2, (fp[1] + fp[3]) / 2
        self.origin = QPointF(self.width() / 2 - cx * self.scale,
                              self.height() / 2 + cy * self.scale)
        self.update()

    # ---- painting -----------------------------------------------------------
    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#FBFAF6"))
        grid = float(B.settings_of(self.panel.data()).get("grid", 0.5)) or 0.5
        x0, y1 = self.to_world(QPointF(0, 0))
        x1, y0 = self.to_world(QPointF(self.width(), self.height()))
        step = grid
        while step * self.scale < 8:
            step *= 2
        import math
        p.setPen(QPen(QColor(225, 222, 212), 1))
        i = math.floor(x0 / step)
        while i * step <= x1:
            sx = self.to_screen(i * step, 0).x()
            p.drawLine(QPointF(sx, 0), QPointF(sx, self.height()))
            i += 1
        j = math.floor(y0 / step)
        while j * step <= y1:
            sy = self.to_screen(0, j * step).y()
            p.drawLine(QPointF(0, sy), QPointF(self.width(), sy))
            j += 1
        o = self.to_screen(0, 0)
        p.setPen(QPen(QColor(200, 60, 60), 1))
        p.drawLine(o, o + QPointF(30, 0))
        p.setPen(QPen(QColor(60, 150, 60), 1))
        p.drawLine(o, o + QPointF(0, -30))

        def rect_of(rm):
            a = self.to_screen(rm["x"], rm["y"] + rm["d"])
            return QRectF(a.x(), a.y(), rm["w"] * self.scale,
                          rm["d"] * self.scale)

        for rm in self.panel.rooms(self.panel.floor - 1):
            p.setPen(QPen(GHOST, 1, Qt.DashLine))
            p.setBrush(GHOST)
            p.drawRect(rect_of(rm))
        f = QFont(self.font())
        f.setPointSizeF(max(7.0, min(11.0, self.scale / 5)))
        p.setFont(f)
        for rm in self.rooms():
            r = rect_of(rm)
            sel = rm["id"] == self.selected
            p.setPen(QPen(SEL if sel else ROOM_EDGE, 2.5 if sel else 1.5))
            p.setBrush(ROOM)
            p.drawRect(r)
            p.setPen(NAVY)
            p.drawText(r, Qt.AlignCenter,
                       f"{rm.get('name', '')}\n{rm['w']:g} × {rm['d']:g} ม.")
        # Columns where the build will put them.
        p.setPen(Qt.NoPen)
        p.setBrush(NAVY)
        c = max(4.0, B.settings_of(self.panel.data())["col"] * self.scale)
        for x, y in B.nodes(self.rooms()):
            q = self.to_screen(x, y)
            p.drawRect(QRectF(q.x() - c / 2, q.y() - c / 2, c, c))
        if self._hover is not None:
            p.setPen(QColor(85, 101, 122))
            p.drawText(QPointF(6, self.height() - 6),
                       f"X {self._hover[0]:.2f} · Y {self._hover[1]:.2f} ม. · "
                       f"ชั้น {self.panel.floor + 1}")
        p.end()

    # ---- mouse ----------------------------------------------------------------
    def mousePressEvent(self, ev):
        x, y = self.to_world(ev.position())
        if ev.button() == Qt.MiddleButton:
            self._pan = (ev.position(), QPointF(self.origin))
            return
        rm = self.room_at(x, y)
        if ev.button() == Qt.RightButton:
            if rm is not None:
                self.selected = rm["id"]
                self.update()
                self._menu(rm, ev.globalPosition().toPoint())
            return
        if ev.button() != Qt.LeftButton:
            return
        if rm is not None:
            self.selected = rm["id"]
            self._drag = (rm["id"], x - rm["x"], y - rm["y"],
                          copy.deepcopy(self.rooms()))
        else:
            self.selected = self.panel.place_room(x, y)
        self.update()

    def mouseMoveEvent(self, ev):
        x, y = self.to_world(ev.position())
        self._hover = (x, y)
        if self._pan is not None:
            start, org = self._pan
            self.origin = org + (ev.position() - start)
        elif self._drag is not None:
            rid, dx, dy, rooms = self._drag
            for rm in rooms:
                if rm["id"] == rid:
                    moved = dict(rm, x=x - dx, y=y - dy)
                    others = [o for o in rooms if o["id"] != rid]
                    s = B.settings_of(self.panel.data())
                    snapped = B.snap_room(moved, others, s["grid"])
                    rm["x"], rm["y"] = snapped["x"], snapped["y"]
            self.panel.preview_rooms(rooms)
        self.update()

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MiddleButton:
            self._pan = None
            return
        if self._drag is not None:
            rooms = self._drag[3]
            self._drag = None
            self.panel.set_rooms(rooms)

    def mouseDoubleClickEvent(self, ev):
        x, y = self.to_world(ev.position())
        rm = self.room_at(x, y)
        if rm is not None:
            self.panel.edit_room(rm["id"])

    def wheelEvent(self, ev):
        k = 1.15 if ev.angleDelta().y() > 0 else 1 / 1.15
        pos = ev.position()
        wx, wy = self.to_world(pos)
        self.scale = max(4.0, min(400.0, self.scale * k))
        self.origin = QPointF(pos.x() - wx * self.scale,
                              pos.y() + wy * self.scale)
        self.update()

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.selected:
            self.panel.delete_room(self.selected)
            self.selected = None
        elif ev.key() == Qt.Key_R and self.selected:
            self.panel.rotate_room(self.selected)
        else:
            super().keyPressEvent(ev)

    def _menu(self, rm, at):
        m = QMenu(self)
        m.addAction("แก้ไขชื่อ/ขนาด…", lambda: self.panel.edit_room(rm["id"]))
        m.addAction("หมุน 90° (R)", lambda: self.panel.rotate_room(rm["id"]))
        m.addAction("ทำสำเนา", lambda: self.panel.duplicate_room(rm["id"]))
        m.addSeparator()
        m.addAction("ลบห้อง (Delete)", lambda: self.panel.delete_room(rm["id"]))
        m.exec(at)


class RoomDialog(QDialog):
    def __init__(self, room, parent=None):
        super().__init__(parent)
        self.setWindowTitle("แก้ไขห้อง")
        f = QFormLayout(self)
        self.name = QLineEdit(room.get("name", ""))
        self.w = QDoubleSpinBox()
        self.d = QDoubleSpinBox()
        for sp, v in ((self.w, room["w"]), (self.d, room["d"])):
            sp.setRange(0.5, 100.0)
            sp.setDecimals(2)
            sp.setSingleStep(0.5)
            sp.setSuffix(" ม.")
            sp.setValue(float(v))
        f.addRow("ชื่อห้อง", self.name)
        f.addRow("กว้าง X", self.w)
        f.addRow("ลึก Y", self.d)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)


def _spin(lo, hi, val, step=0.05, dec=2, suffix=" ม."):
    sp = QDoubleSpinBox()
    sp.setRange(lo, hi)
    sp.setDecimals(dec)
    sp.setSingleStep(step)
    sp.setSuffix(suffix)
    sp.setValue(val)
    return sp


class BuildingPanel(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.floor = 0
        self._preview = None
        self._loading = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)
        head = QLabel("<b>WANIC ออกแบบอาคาร</b> — วางผังห้อง แล้วสร้างโครงสร้าง"
                      "และหลังคาอัตโนมัติ")
        head.setWordWrap(True)
        lay.addWidget(head)

        # Floor bar.
        fb = QHBoxLayout()
        self.floor_box = QComboBox()
        self.floor_box.currentIndexChanged.connect(self._floor_changed)
        fb.addWidget(QLabel("ชั้น"))
        fb.addWidget(self.floor_box, 1)
        for text, tip, fn in (
                ("＋ ชั้นใหม่", "เพิ่มชั้นใหม่ด้านบน (ว่าง)", self.add_floor),
                ("⧉ คัดลอกชั้นนี้ขึ้นไป", "สร้างชั้นใหม่ด้านบนที่มีห้องเหมือนชั้นนี้",
                 self.copy_floor),
                ("✕ ลบชั้น", "ลบชั้นที่เลือก", self.delete_floor)):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, f=fn: f())
            fb.addWidget(b)
        lay.addLayout(fb)

        # Room palette.
        rp = QGridLayout()
        self.preset = QComboBox()
        for name, w, d in B.ROOM_PRESETS:
            self.preset.addItem(f"{name} {w:g}×{d:g} ม.", (name, w, d))
        self.preset.currentIndexChanged.connect(self._preset_changed)
        self.room_name = QLineEdit()
        self.room_w = _spin(0.5, 100, 3.0, 0.5)
        self.room_d = _spin(0.5, 100, 3.0, 0.5)
        rp.addWidget(QLabel("ห้องสำเร็จรูป"), 0, 0)
        rp.addWidget(self.preset, 0, 1, 1, 3)
        rp.addWidget(QLabel("ชื่อ"), 1, 0)
        rp.addWidget(self.room_name, 1, 1, 1, 3)
        rp.addWidget(QLabel("กว้าง X"), 2, 0)
        rp.addWidget(self.room_w, 2, 1)
        rp.addWidget(QLabel("ลึก Y"), 2, 2)
        rp.addWidget(self.room_d, 2, 3)
        lay.addLayout(rp)
        hint = QLabel("คลิกที่ว่างบนผัง = วางห้อง · ลากห้อง = ย้าย (ดูดติดขอบห้องอื่น"
                      "และกริด) · ดับเบิลคลิก = แก้ขนาด · R = หมุน · Delete = ลบ · "
                      "ล้อเมาส์ = ซูม · ปุ่มกลาง = เลื่อน")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(mid);")
        lay.addWidget(hint)

        self.canvas = PlanCanvas(self)
        lay.addWidget(self.canvas, 1)
        cb = QHBoxLayout()
        for text, fn in (("⤢ พอดีหน้าจอ", self.canvas.fit),
                         ("🗑 ล้างห้องชั้นนี้", self.clear_floor)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, f=fn: f())
            cb.addWidget(b)
        cb.addStretch(1)
        lay.addLayout(cb)

        # Build buttons.
        bb = QGridLayout()

        def btn(text, tip, fn, r, c, color):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setStyleSheet(f"QPushButton{{background:{color};color:white;"
                            "font-weight:bold;padding:6px;border-radius:6px}}")
            b.clicked.connect(lambda _=False: fn())
            bb.addWidget(b, r, c)
        btn("🏗 สร้าง/อัปเดตโครงสร้าง", "ฐานราก ตอม่อ เสา คาน พื้น ผนัง ทุกชั้น",
            lambda: self.build(("structure",)), 0, 0, "#2E7D4F")
        btn("🏠 สร้าง/อัปเดตหลังคา", "โครงหลังคาเหล็กและแผ่นหลังคา",
            lambda: self.build(("roof",)), 0, 1, "#C46420")
        btn("✅ สร้างทั้งหมด", "โครงสร้าง + หลังคา",
            lambda: self.build(("structure", "roof")), 1, 0, "#0F2A44")
        btn("💰 ส่งรายการราคาไป ถอดปริมาณ",
            "เพิ่มรายการราคา (ราคาเริ่ม 0) ผูกตามชื่อชิ้นส่วน ในแท็บ ถอดปริมาณ",
            self.send_rates, 1, 1, "#3B6FB6")
        lay.addLayout(bb)
        rm = QPushButton("ลบสิ่งที่สร้างโดย ออกแบบอาคาร")
        rm.clicked.connect(lambda _=False: self.remove_built())
        lay.addWidget(rm)
        self.status = QLabel()
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        # Settings.
        self.fields = {}
        st = QGroupBox("ขนาดชิ้นส่วน (ค่าเริ่มต้น — ให้วิศวกรกำหนดขนาดจริง)")
        sf = QFormLayout(st)

        def num(key, label, lo, hi, step=0.05, dec=2, suffix=" ม."):
            sp = _spin(lo, hi, float(B.DEFAULT_SETTINGS[key]), step, dec,
                       suffix)
            sp.editingFinished.connect(self._save_settings)
            self.fields[key] = sp
            sf.addRow(label, sp)

        def pair(k1, k2, label):
            row = QHBoxLayout()
            for k in (k1, k2):
                sp = _spin(0.05, 5, float(B.DEFAULT_SETTINGS[k]))
                sp.editingFinished.connect(self._save_settings)
                self.fields[k] = sp
                row.addWidget(sp)
            sf.addRow(label, row)
        num("floor_h", "ความสูงชั้น", 2.0, 10.0, 0.1)
        num("grid", "ระยะกริดผัง", 0.05, 5.0, 0.05)
        num("footing_w", "ฐานราก F1 กว้าง × ยาว", 0.3, 5.0)
        num("footing_t", "ฐานราก F1 หนา", 0.1, 2.0)
        num("footing_depth", "ความลึกท้องฐานราก", 0.3, 10.0, 0.1)
        num("stump", "ตอม่อ PC1 (สี่เหลี่ยมจัตุรัส)", 0.1, 2.0)
        num("col", "เสา C1 (สี่เหลี่ยมจัตุรัส)", 0.1, 2.0)
        pair("gb_b", "gb_h", "คานคอดิน GB1 กว้าง × ลึก")
        pair("b_b", "b_h", "คานชั้นบน B1 กว้าง × ลึก")
        pair("rb_b", "rb_h", "คานหลังคา RB1 กว้าง × ลึก")
        num("slab_t", "พื้น S หนา", 0.05, 1.0, 0.01)
        self.walls = QCheckBox("สร้างผนังก่ออิฐรอบห้อง")
        self.walls.toggled.connect(lambda _v: self._save_settings())
        sf.addRow(self.walls)
        num("wall_t", "ผนังหนา", 0.05, 0.5, 0.01)
        lay.addWidget(st)

        rf = QGroupBox("หลังคา")
        rff = QFormLayout(rf)
        self.roof = QComboBox()
        for k, v in (("hip", "ปั้นหยา"), ("gable", "จั่ว"),
                     ("none", "ไม่สร้างหลังคา")):
            self.roof.addItem(v, k)
        self.roof.currentIndexChanged.connect(lambda _i: self._save_settings())
        rff.addRow("แบบหลังคา", self.roof)
        sf_backup = sf
        sf = rff
        num("pitch", "ความชัน", 5.0, 60.0, 1.0, 1, "°")
        num("overhang", "ชายคายื่น", 0.0, 3.0, 0.1)
        num("rafter_sp", "ระยะจันทัน", 0.3, 3.0, 0.1)
        num("purlin_sp", "ระยะแป (ตามแนวลาด)", 0.2, 2.0, 0.05)
        sf = sf_backup
        labels = [lab for lab, _f, _p in B.steel_presets()]
        self.steel = {}
        for key, th in (("ridge", "อกไก่"), ("hip", "ตะเฆ่สัน"),
                        ("rafter", "จันทัน"), ("purlin", "แป"), ("post", "ดั้ง")):
            c = QComboBox()
            c.addItems(labels)
            c.currentIndexChanged.connect(lambda _i: self._save_settings())
            self.steel[key] = c
            rff.addRow(th, c)
        self.skin = QCheckBox("สร้างแผ่นหลังคา (คิดพื้นที่มุงหลังคา)")
        self.skin.toggled.connect(lambda _v: self._save_settings())
        rff.addRow(self.skin)
        lay.addWidget(rf)
        note = QLabel("รุ่นนี้วางหลังคาคลุมกรอบสี่เหลี่ยมรอบห้องของชั้นบนสุด "
                      "ปริมาณคอนกรีตนับรอยต่อเสา-คานซ้ำเล็กน้อย")
        note.setWordWrap(True)
        note.setStyleSheet("color: palette(mid);")
        lay.addWidget(note)

        self._preset_changed()
        self.refresh()
        QTimer.singleShot(0, self.canvas.fit)

    # ---- document data -------------------------------------------------------
    def data(self) -> dict:
        d = self.app.document_data(None) or B.default_data()
        d.setdefault("floors", [{"rooms": []}])
        if not d["floors"]:
            d["floors"] = [{"rooms": []}]
        d["settings"] = B.settings_of(d)
        return d

    def _write(self, d):
        self._loading = True
        try:
            self.app.set_document_data(d)
        finally:
            self._loading = False
        self.refresh()

    def rooms(self, floor=None):
        if floor is None:
            floor = self.floor
            if self._preview is not None:
                return self._preview
        floors = self.data()["floors"]
        if floor < 0 or floor >= len(floors):
            return []
        return floors[floor].get("rooms") or []

    def preview_rooms(self, rooms):
        self._preview = rooms
        self.canvas.update()

    def set_rooms(self, rooms):
        self._preview = None
        d = self.data()
        d["floors"][self.floor]["rooms"] = rooms
        self._write(d)

    def _next_id(self, d):
        ids = [int(str(r.get("id", "r0"))[1:] or 0)
               for f in d["floors"] for r in f.get("rooms") or []
               if str(r.get("id", "")).startswith("r")
               and str(r.get("id", ""))[1:].isdigit()]
        return f"r{max(ids, default=0) + 1}"

    # ---- rooms ------------------------------------------------------------------
    def _preset_changed(self, *_):
        name, w, d = self.preset.currentData()
        self.room_name.setText(name)
        self.room_w.setValue(w)
        self.room_d.setValue(d)

    def place_room(self, x, y):
        d = self.data()
        rooms = d["floors"][self.floor]["rooms"]
        w, dd = self.room_w.value(), self.room_d.value()
        rm = {"id": self._next_id(d), "name": self.room_name.text().strip()
              or "ห้อง", "x": x - w / 2, "y": y - dd / 2, "w": w, "d": dd}
        rm = B.snap_room(rm, rooms, d["settings"]["grid"])
        rooms.append(rm)
        self._write(d)
        return rm["id"]

    def _edit(self, rid, fn):
        d = self.data()
        rooms = d["floors"][self.floor]["rooms"]
        for i, rm in enumerate(rooms):
            if rm["id"] == rid:
                res = fn(rooms, i, rm)
                if res is not False:
                    self._write(d)
                return

    def edit_room(self, rid):
        def fn(rooms, i, rm):
            dlg = RoomDialog(rm, self)
            if dlg.exec() != QDialog.Accepted:
                return False
            rm.update(name=dlg.name.text().strip() or rm.get("name", ""),
                      w=dlg.w.value(), d=dlg.d.value())
        self._edit(rid, fn)

    def rotate_room(self, rid):
        def fn(rooms, i, rm):
            cx, cy = rm["x"] + rm["w"] / 2, rm["y"] + rm["d"] / 2
            rm["w"], rm["d"] = rm["d"], rm["w"]
            rm.update(B.snap_room(dict(rm, x=cx - rm["w"] / 2,
                                       y=cy - rm["d"] / 2),
                                  [o for o in rooms if o is not rm],
                                  self.data()["settings"]["grid"]))
        self._edit(rid, fn)

    def duplicate_room(self, rid):
        def fn(rooms, i, rm):
            new = dict(rm, id=self._next_id(self.data()), x=rm["x"] + rm["w"])
            rooms.append(B.snap_room(new, rooms, self.data()["settings"]["grid"]))
        self._edit(rid, fn)

    def delete_room(self, rid):
        def fn(rooms, i, rm):
            del rooms[i]
        self._edit(rid, fn)

    def clear_floor(self):
        d = self.data()
        d["floors"][self.floor]["rooms"] = []
        self._write(d)

    # ---- floors -----------------------------------------------------------------
    def add_floor(self):
        d = self.data()
        d["floors"].append({"rooms": []})
        self.floor = len(d["floors"]) - 1
        self._write(d)

    def copy_floor(self):
        d = self.data()
        nid = int(self._next_id(d)[1:])
        new = []
        for rm in copy.deepcopy(d["floors"][self.floor]["rooms"]):
            new.append(dict(rm, id=f"r{nid}"))
            nid += 1
        d["floors"].insert(self.floor + 1, {"rooms": new})
        self.floor += 1
        self._write(d)

    def delete_floor(self):
        d = self.data()
        if len(d["floors"]) <= 1:
            d["floors"] = [{"rooms": []}]
        else:
            del d["floors"][self.floor]
            self.floor = max(0, self.floor - 1)
        self._write(d)

    def _floor_changed(self, i):
        if self._loading or i < 0:
            return
        self.floor = i
        self.canvas.selected = None
        self.canvas.update()

    # ---- settings -----------------------------------------------------------------
    def _save_settings(self):
        if self._loading:
            return
        d = self.data()
        s = d["settings"]
        for k, sp in self.fields.items():
            s[k] = sp.value()
        s["walls"] = self.walls.isChecked()
        s["skin"] = self.skin.isChecked()
        s["roof"] = self.roof.currentData()
        for k, c in self.steel.items():
            s[k] = c.currentText()
        if s != self.data()["settings"]:
            self._write(d)

    def refresh(self):
        d = self.data()
        self._loading = True
        try:
            self.floor = min(self.floor, len(d["floors"]) - 1)
            self.floor_box.clear()
            for i, f in enumerate(d["floors"]):
                n = len(f.get("rooms") or [])
                self.floor_box.addItem(f"ชั้น {i + 1}  ({n} ห้อง)")
            self.floor_box.setCurrentIndex(self.floor)
            s = d["settings"]
            for k, sp in self.fields.items():
                sp.setValue(float(s[k]))
            self.walls.setChecked(bool(s["walls"]))
            self.skin.setChecked(bool(s["skin"]))
            self.roof.setCurrentIndex(max(self.roof.findData(s["roof"]), 0))
            for k, c in self.steel.items():
                i = c.findText(s[k])
                c.setCurrentIndex(max(i, 0))
        finally:
            self._loading = False
        self.canvas.update()

    def schedule(self):
        if not self._loading and self.canvas._drag is None:
            QTimer.singleShot(0, self.refresh)

    # ---- building -------------------------------------------------------------------
    def build(self, parts):
        from core.history import (CompoundCommand, DeleteGroupCommand,
                                  InsertGroupCommand)
        d = self.data()
        if not any(f.get("rooms") for f in d["floors"]):
            QMessageBox.information(self, TITLE, "ยังไม่มีห้องในผัง — คลิกบนผังเพื่อ"
                                    "วางห้องก่อน")
            return
        groups, count = B.build(d, parts)
        old = B.generated(self.app.scene, parts)
        if not groups and not old:
            self.status.setText("ไม่มีอะไรให้สร้าง")
            return
        cmds = [DeleteGroupCommand(g) for g in old]
        cmds += [InsertGroupCommand(g) for g in groups]
        self.app.viewport.history.execute(CompoundCommand(cmds))
        self.app.scene.selection.clear()
        vp = self.app.viewport
        n = getattr(vp, "notify_scene_changed", None)
        if callable(n):
            n()
        vp.update()
        floors = sum(1 for f in d["floors"] if f.get("rooms"))
        msg = (f"สร้างเสร็จ {floors} ชั้น — {B.summary(count)}"
               + (f" (แทนของเดิม {len(old)} ชิ้น)" if old else ""))
        self.status.setText(msg)
        f = getattr(vp, "flash_status", None)
        if callable(f):
            f(msg)

    def remove_built(self):
        from core.history import CompoundCommand, DeleteGroupCommand
        old = B.generated(self.app.scene)
        if not old:
            self.status.setText("ยังไม่มีชิ้นส่วนที่สร้างไว้")
            return
        self.app.viewport.history.execute(
            CompoundCommand([DeleteGroupCommand(g) for g in old]))
        self.app.viewport.update()
        self.status.setText(f"ลบแล้ว {len(old)} ชิ้น (กด Undo เพื่อเอากลับ)")

    def send_rates(self):
        from core.history import SetPluginDataCommand
        from core.wanic_takeoff import default_data as tk_default
        scene = self.app.scene
        cur = (getattr(scene, "plugin_data", {}) or {}).get(B.TAKEOFF_KEY)
        import json
        tk = json.loads(json.dumps(cur)) if cur else tk_default()
        tk.setdefault("rates", [])
        have = {(r.get("by"), r.get("value"), r.get("qty"), r.get("desc"))
                for r in tk["rates"]}
        added = 0
        for r in B.takeoff_rates(self.data()):
            k = (r["by"], r["value"], r["qty"], r["desc"])
            if k in have:
                continue
            r["id"] = f"wb{len(tk['rates']) + 1}_{added}"
            tk["rates"].append(r)
            added += 1
        self.app.viewport.history.execute(
            SetPluginDataCommand(B.TAKEOFF_KEY, tk))
        vp = self.app.viewport
        n = getattr(vp, "notify_scene_changed", None)
        if callable(n):
            n()
        self.status.setText(f"เพิ่มรายการราคา {added} รายการในแท็บ «ถอดปริมาณ» "
                            "แล้ว — กรอกราคาวัสดุ/ค่าแรงต่อหน่วยที่นั่น")
        win = self.app.window
        dock = None
        for name, dk in (getattr(win, "extension_panels", lambda: {})()
                         or {}).items():
            if name.endswith(B.TAKEOFF_KEY):
                dock = dk
        if dock is not None:
            try:
                win.set_tray_shown(dock, True)
                dock.raise_()
            except Exception:
                pass


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
    panel = BuildingPanel(app)
    dock = app.add_panel(TITLE, panel)
    app.window._wanic_building = panel
    app.on_document_changed(panel.schedule)

    def show():
        app.show_panel(dock)
        dock.raise_()
        panel.refresh()
        QTimer.singleShot(0, panel.canvas.fit)

    app.add_menu_action("WANIC ออกแบบอาคาร…", show,
                        tip="วางผังห้อง แล้วสร้างฐานราก เสา คาน พื้น ผนัง "
                            "และโครงหลังคาอัตโนมัติ")
    QTimer.singleShot(0, lambda: _join_tray(app.window, dock))
