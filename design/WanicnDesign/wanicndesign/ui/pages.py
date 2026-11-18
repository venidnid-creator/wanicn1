# -*- coding: utf-8 -*-
"""The step pages on the right of the main window. Each page edits one part
of the :class:`~wanicndesign.structure.building.Building` and emits
``changed`` when the user applies it."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                               QTabWidget, QTextEdit, QVBoxLayout, QWidget)

from ..standards import LIVE_LOAD, LIVE_LOADS
from ..structure.building import ROOF_COVER_LOAD, Level
from ..structure.materials import CODES
from ..structure.sections import load_piles

SLAB_KINDS = [("suspended", "พื้นแขวน (บนคาน)"), ("on_ground", "พื้นวางบนดิน"),
              ("roof", "หลังคา"), ("none", "ไม่มีพื้น")]
WALL_MODES = [("perimeter", "ผนังรอบนอก"), ("all", "ผนังทุกแนว"), ("none", "ไม่มีผนัง")]
WALL_TYPES = [("brick", "อิฐมอญ"), ("qcon", "อิฐมวลเบา"), ("gypsum", "ยิปซัม/ไม้"),
              ("concrete", "คอนกรีต"), ("metal", "แผ่นเหล็ก")]
ROOF_SHAPES = [("hip", "ปั้นหยา"), ("gable", "จั่ว")]
ROOF_COVERS = [("concrete_tile", "กระเบื้องคอนกรีต"), ("ceramic_tile", "กระเบื้องเซรามิค"),
               ("metal_sheet", "เมทัลชีท"), ("asbestos", "กระเบื้องลอน")]


NG_FILL = QColor("#f8cbad")


def _spin(value, lo, hi, step=0.05, dec=2, suffix=""):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(dec)
    s.setSingleStep(step)
    s.setValue(value)
    if suffix:
        s.setSuffix(" " + suffix)
    return s


def _combo(items, current):
    c = QComboBox()
    for key, label in items:
        c.addItem(label, key)
    k = c.findData(current)
    c.setCurrentIndex(max(0, k))
    return c


def parse_spacings(text: str) -> list[float]:
    """``"4, 4, 3.5"`` or ``"2*4, 3.5"`` → [4.0, 4.0, 3.5]."""
    out = []
    for part in text.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "*" in part:
            n, v = part.split("*", 1)
            out += [float(v)] * int(n)
        else:
            out.append(float(part))
    if not out or any(v <= 0 for v in out):
        raise ValueError("ระยะกริดต้องเป็นตัวเลขมากกว่า 0 คั่นด้วยจุลภาค")
    return out


class Page(QWidget):
    changed = Signal()
    title = ""
    hint = ""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.building = None
        self.lay = QVBoxLayout(self)
        head = QLabel(f"<b>{self.title}</b>")
        self.lay.addWidget(head)
        if self.hint:
            h = QLabel(self.hint)
            h.setWordWrap(True)
            h.setStyleSheet("color:#555; background:#fff7e6; padding:6px; border:1px solid #f0d9a8;")
            self.lay.addWidget(h)

    def set_model(self, building):
        self.building = building
        self.load()

    def load(self):
        ...

    def add_apply(self, text="นำไปใช้"):
        btn = QPushButton(text)
        btn.clicked.connect(self._apply)
        self.lay.addWidget(btn)
        self.lay.addStretch(1)
        return btn

    def _apply(self):
        self.apply()
        self.changed.emit()

    def apply(self):
        ...


class ProjectPage(Page):
    title = "1. โครงการและวัสดุ"

    def __init__(self, parent=None):
        super().__init__(parent)
        f = QFormLayout()
        self.name = QLineEdit()
        self.fc = _spin(210, 100, 500, 5, 0, "ksc")
        self.cw = _spin(0.20, 0.15, 1.0, 0.05, 2, "ม.")
        self.cd = _spin(0.20, 0.15, 1.0, 0.05, 2, "ม.")
        self.code = _combo(list(CODES.items()), "EIT1007")
        self.use = _combo([(k, f"{t} ({v})") for k, t, v in LIVE_LOADS if k not in ("roof", "canopy")],
                          "house")
        self.reduce = QCheckBox("ลดน้ำหนักจรสำหรับเสาและฐานราก (กฎกระทรวง พ.ศ. 2566 ข้อ 13–14)")
        f.addRow("ชื่อโครงการ", self.name)
        f.addRow("เกณฑ์การออกแบบ", self.code)
        f.addRow("ประเภทการใช้อาคาร", self.use)
        f.addRow("", self.reduce)
        f.addRow("กำลังอัดคอนกรีต fc' (ทรงกระบอก)", self.fc)
        f.addRow("เสา กว้าง", self.cw)
        f.addRow("เสา ลึก", self.cd)
        self.lay.addLayout(f)
        self.add_apply()

    def load(self):
        b = self.building
        self.name.setText(b.name)
        self.fc.setValue(b.fc_prime)
        self.cw.setValue(b.column_width)
        self.cd.setValue(b.column_depth)
        self.code.setCurrentIndex(max(0, self.code.findData(b.design_code)))
        self.use.setCurrentIndex(max(0, self.use.findData(b.occupancy)))
        self.reduce.setChecked(b.ll_reduction)

    def apply(self):
        b = self.building
        b.name = self.name.text().strip() or b.name
        b.design_code, b.occupancy = self.code.currentData(), self.use.currentData()
        b.ll_reduction = self.reduce.isChecked()
        b.fc_prime = self.fc.value()
        b.column_width, b.column_depth = self.cw.value(), self.cd.value()


class GridPage(Page):
    title = "2. เส้นกริด"
    hint = ("ใส่ระยะช่วงกริดคั่นด้วยจุลภาค เช่น 4, 4, 3.5 (ใช้ 3*4 แทน 4, 4, 4 ได้) "
            "แล้วกด นำไปใช้ — โปรแกรมสร้างเสา คาน พื้น ฐานรากให้อัตโนมัติ "
            "จากนั้นคลิกที่แปลนเพื่อลบหรือคืนชิ้นส่วน")

    def __init__(self, parent=None):
        super().__init__(parent)
        f = QFormLayout()
        self.gx = QLineEdit()
        self.gy = QLineEdit()
        f.addRow("ระยะแนว X (1, 2, 3 …) ม.", self.gx)
        f.addRow("ระยะแนว Y (A, B, C …) ม.", self.gy)
        self.lay.addLayout(f)
        self.size = QLabel()
        self.lay.addWidget(self.size)
        self.error = QLabel()
        self.error.setStyleSheet("color:#c62828")
        self.lay.addWidget(self.error)
        reset = QPushButton("คืนชิ้นส่วนที่ลบทั้งหมด")
        reset.clicked.connect(self._reset)
        self.lay.addWidget(reset)
        self.add_apply("นำไปใช้ (สร้างชิ้นส่วนอัตโนมัติ)")

    def load(self):
        b = self.building
        self.gx.setText(", ".join(f"{v:g}" for v in b.grid_x))
        self.gy.setText(", ".join(f"{v:g}" for v in b.grid_y))
        self._size()

    def _size(self):
        b = self.building
        n = len(b.nodes())
        self.size.setText(f"ขนาดอาคาร {b.xs[-1]:.2f} × {b.ys[-1]:.2f} ม. · เสา {n} ต้น · "
                          f"พื้นที่ต่อชั้น {b.xs[-1] * b.ys[-1]:.2f} ตร.ม.")

    def apply(self):
        try:
            gx, gy = parse_spacings(self.gx.text()), parse_spacings(self.gy.text())
        except ValueError as e:
            self.error.setText(str(e))
            raise
        self.error.setText("")
        b = self.building
        if gx != b.grid_x or gy != b.grid_y:
            b.skip_nodes.clear()
            b.skip_beams.clear()
            b.skip_panels.clear()
        b.grid_x, b.grid_y = gx, gy
        self._size()

    def _apply(self):
        try:
            self.apply()
        except ValueError:
            return
        self.changed.emit()

    def _reset(self):
        b = self.building
        b.skip_nodes.clear()
        b.skip_beams.clear()
        b.skip_panels.clear()
        self._size()
        self.changed.emit()


class LevelsPage(Page):
    title = "3. ชั้น พื้น และคาน"
    hint = ("แต่ละแถวคือระดับคานหนึ่งชั้น เรียงจากล่างขึ้นบน แถวบนสุดตั้งเป็น หลังคา "
            "ผนังในแถวใด คือผนังที่ตั้งบนคานชั้นนั้นขึ้นไปถึงชั้นถัดไป")
    COLS = ["ชื่อ", "ระดับ ม.", "พื้น", "หนาพื้น ม.", "น้ำหนักจร กก./ตร.ม.", "ผิว/ทอปปิ้ง",
            "คาน b ม.", "คาน h ม.", "Mark", "ผนัง", "ชนิดผนัง"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.lay.addWidget(self.table)
        row = QHBoxLayout()
        add = QPushButton("เพิ่มชั้น")
        add.clicked.connect(self._add)
        rem = QPushButton("ลบชั้นที่เลือก")
        rem.clicked.connect(self._remove)
        self.ll = _combo([(k, f"{t[:28]} ({v})") for k, t, v in LIVE_LOADS
                          if k not in ("roof", "canopy")], "house")
        use = QPushButton("ใช้น้ำหนักจรตามกฎกระทรวง พ.ศ. 2566 ข้อ 11")
        use.clicked.connect(self._use_ll)
        for w in (add, rem, self.ll, use):
            row.addWidget(w)
        self.lay.addLayout(row)
        self.add_apply()

    def _set_row(self, r, lv: Level):
        def item(v):
            return QTableWidgetItem(f"{v:g}" if isinstance(v, float) else str(v))
        self.table.setItem(r, 0, item(lv.name))
        self.table.setItem(r, 1, item(float(lv.elevation)))
        self.table.setCellWidget(r, 2, _combo(SLAB_KINDS, lv.slab))
        self.table.setItem(r, 3, item(float(lv.slab_thickness)))
        self.table.setItem(r, 4, item(float(lv.live_load)))
        self.table.setItem(r, 5, item(float(lv.finish_load)))
        self.table.setItem(r, 6, item(float(lv.beam_width)))
        self.table.setItem(r, 7, item(float(lv.beam_depth)))
        self.table.setItem(r, 8, item(lv.beam_mark))
        self.table.setCellWidget(r, 9, _combo(WALL_MODES, lv.walls))
        self.table.setCellWidget(r, 10, _combo(WALL_TYPES, lv.wall_type))

    def load(self):
        lv = self.building.levels
        self.table.setRowCount(len(lv))
        for r, level in enumerate(lv):
            self._set_row(r, level)

    def _add(self):
        b = self.building
        top = b.levels[-1].elevation if b.levels else 0.0
        r = self.table.rowCount()
        self.table.insertRow(r)
        self._set_row(r, Level(f"FL{r + 1}", top + 3.0))

    def _remove(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def _use_ll(self):
        v = LIVE_LOAD[self.ll.currentData()]
        for r in range(self.table.rowCount()):
            if self.table.cellWidget(r, 2).currentData() in ("suspended", "on_ground"):
                self.table.setItem(r, 4, QTableWidgetItem(f"{v:g}"))

    def levels_from_table(self) -> list[Level]:
        old = {lv.name: lv for lv in (self.building.levels if self.building else [])}
        out = []
        for r in range(self.table.rowCount()):
            txt = lambda c: self.table.item(r, c).text().strip()
            out.append(Level(txt(0), float(txt(1)), self.table.cellWidget(r, 2).currentData(),
                             float(txt(3)), float(txt(4)), float(txt(5)), float(txt(6)),
                             float(txt(7)), txt(8) or "B", self.table.cellWidget(r, 9).currentData(),
                             self.table.cellWidget(r, 10).currentData()))
            prev = old.get(out[-1].name)
            if prev is not None:                 # keep what was placed on the plan
                out[-1].sub_beams = list(prev.sub_beams)
                out[-1].cantilevers = list(prev.cantilevers)
                out[-1].cant_beams = list(prev.cant_beams)
        out.sort(key=lambda lv: lv.elevation)
        return out

    def apply(self):
        self.building.levels = self.levels_from_table()


class FoundationPage(Page):
    title = "4. ฐานรากและเสาเข็ม"
    hint = "ค่ารับน้ำหนักของเสาเข็มตามตารางในโปรแกรม ต้องปรับตามผลเจาะสำรวจดินจริง"

    def __init__(self, parent=None):
        super().__init__(parent)
        f = QFormLayout()
        self.kind = _combo([("pile", "ฐานรากบนเสาเข็ม"), ("spread", "ฐานแผ่ (ไม่มีเข็ม)")], "pile")
        piles = load_piles()
        self.pile = _combo([(k, f"{k} ({v['capacity_kg'] / 1000:g} ตัน/ต้น)") for k, v in piles.items()], "I22")
        self.length = _spin(16, 1, 40, 1, 1, "ม.")
        self.depth = _spin(1.5, 0.5, 5, 0.1, 2, "ม.")
        self.qa = _spin(15000, 1000, 100000, 500, 0, "กก./ตร.ม.")
        f.addRow("ชนิด", self.kind)
        f.addRow("เสาเข็ม", self.pile)
        f.addRow("ความยาวเสาเข็ม", self.length)
        f.addRow("ความลึกใต้ฐาน Df", self.depth)
        f.addRow("กำลังรับดิน (ฐานแผ่)", self.qa)
        self.lay.addLayout(f)
        self.add_apply()

    def load(self):
        f = self.building.foundation
        self.kind.setCurrentIndex(self.kind.findData(f.kind))
        self.pile.setCurrentIndex(max(0, self.pile.findData(f.pile)))
        self.length.setValue(f.pile_length)
        self.depth.setValue(f.depth)
        self.qa.setValue(f.soil_qa)

    def apply(self):
        f = self.building.foundation
        f.kind, f.pile = self.kind.currentData(), self.pile.currentData()
        f.pile_length, f.depth, f.soil_qa = self.length.value(), self.depth.value(), self.qa.value()


class RoofPage(Page):
    title = "5. หลังคา"

    def __init__(self, parent=None):
        super().__init__(parent)
        f = QFormLayout()
        self.shape = _combo(ROOF_SHAPES, "hip")
        self.cover = _combo([(k, f"{lbl} ({ROOF_COVER_LOAD[k]} กก./ตร.ม.)") for k, lbl in ROOF_COVERS],
                            "concrete_tile")
        self.slope = _spin(30, 5, 60, 1, 0, "องศา")
        self.overhang = _spin(1.0, 0, 3, 0.1, 2, "ม.")
        self.ll = _spin(30, 0, 200, 5, 0, "กก./ตร.ม.")
        self.frame = _spin(15, 0, 100, 1, 0, "กก./ตร.ม.")
        self.purlin = _spin(0.32, 0.2, 2.0, 0.01, 2, "ม.")
        self.rafter = _spin(1.0, 0.5, 3.0, 0.05, 2, "ม.")
        for label, w in (("ทรงหลังคา", self.shape), ("วัสดุมุง", self.cover), ("ความลาด", self.slope),
                         ("ชายคายื่น", self.overhang), ("น้ำหนักจร", self.ll),
                         ("น้ำหนักโครงเหล็ก", self.frame), ("ระยะแป", self.purlin),
                         ("ระยะจันทัน", self.rafter)):
            f.addRow(label, w)
        self.lay.addLayout(f)
        self.add_apply()

    def load(self):
        r = self.building.roof
        self.shape.setCurrentIndex(self.shape.findData(r.shape))
        self.cover.setCurrentIndex(max(0, self.cover.findData(r.cover)))
        for w, v in ((self.slope, r.slope_deg), (self.overhang, r.overhang), (self.ll, r.live_load),
                     (self.frame, r.frame_load), (self.purlin, r.purlin_spacing),
                     (self.rafter, r.rafter_spacing)):
            w.setValue(v)

    def apply(self):
        r = self.building.roof
        r.shape, r.cover = self.shape.currentData(), self.cover.currentData()
        r.slope_deg, r.overhang, r.live_load = self.slope.value(), self.overhang.value(), self.ll.value()
        r.frame_load, r.purlin_spacing = self.frame.value(), self.purlin.value()
        r.rafter_spacing = self.rafter.value()


class WindPage(Page):
    title = "6. แรงลม"
    hint = ("กฎกระทรวง พ.ศ. 2566 ข้อ 17: อาคารสี่เหลี่ยมสูงไม่เกิน 40 ม. และไม่เกิน 3 เท่าความกว้างน้อยที่สุด "
            "ใช้หน่วยแรงลมตามตาราง · อาคารสาธารณะพื้นที่ตั้งแต่ 1,000 ตร.ม. เพิ่ม 15% · อาคารอื่นต้องใช้วิธีละเอียด")

    def __init__(self, parent=None):
        super().__init__(parent)
        from ..structure.wind import TERRAINS
        f = QFormLayout()
        self.enabled = QCheckBox("คิดแรงลม (บังคับสำหรับงานที่ต้องมีวิศวกรโยธาออกแบบ)")
        self.terrain = _combo(TERRAINS, "urban")
        self.public = _combo([("auto", "ตามประเภทอาคารและพื้นที่"), ("yes", "เป็นอาคารสาธารณะ ≥ 1,000 ตร.ม. (+15%)"),
                              ("no", "ไม่ใช่")], "auto")
        f.addRow(self.enabled)
        f.addRow("สภาพภูมิประเทศ", self.terrain)
        f.addRow("อาคารสาธารณะ", self.public)
        self.lay.addLayout(f)
        self.add_apply()

    def load(self):
        w = self.building.wind
        self.enabled.setChecked(w.enabled)
        self.terrain.setCurrentIndex(max(0, self.terrain.findData(w.terrain)))
        self.public.setCurrentIndex(max(0, self.public.findData(w.public)))

    def apply(self):
        w = self.building.wind
        w.enabled, w.terrain, w.public = self.enabled.isChecked(), self.terrain.currentData(), self.public.currentData()


class SeismicPage(Page):
    title = "7. แผ่นดินไหว"
    hint = ("วิธีแรงสถิตเทียบเท่าตาม มยผ. 1301/1302-61 · ค่า Ss, S1 อ่านจากตารางท้ายมาตรฐานตามอำเภอที่ตั้ง "
            "· ในแอ่งกรุงเทพฯ ให้เลือก 'กรอก SDS, SD1 เอง' และใส่ Sa จากสเปกตรัมของโซน "
            "· ตรวจกับกฎกระทรวงแผ่นดินไหว พ.ศ. 2564 ว่าอาคารนี้อยู่ในบังคับหรือไม่")

    def __init__(self, parent=None):
        super().__init__(parent)
        from ..structure.seismic import RISK_CATEGORIES, SITE_CLASSES, SYSTEMS
        f = QFormLayout()
        self.enabled = QCheckBox("ออกแบบต้านทานแผ่นดินไหว")
        self.mode = _combo([("map", "Ss, S1 จากตาราง + ประเภทชั้นดิน"), ("direct", "กรอก SDS, SD1 เอง")], "map")
        self.ss = _spin(0.0, 0, 3, 0.01, 3, "g")
        self.s1 = _spin(0.0, 0, 2, 0.01, 3, "g")
        self.site = _combo(SITE_CLASSES, "D")
        self.sds = _spin(0.0, 0, 3, 0.01, 3, "g")
        self.sd1 = _spin(0.0, 0, 2, 0.01, 3, "g")
        self.sa = _spin(0.0, 0, 3, 0.01, 3, "g")
        self.category = _combo(RISK_CATEGORIES, "II")
        self.system = _combo([(k, f"{v[0]} (R = {v[1]:g})") for k, v in SYSTEMS.items()], "IMF")
        f.addRow(self.enabled)
        for label, w in (("ข้อมูลพื้นที่", self.mode), ("Ss (คาบ 0.2 วินาที)", self.ss),
                         ("S1 (คาบ 1 วินาที)", self.s1), ("ประเภทชั้นดิน", self.site),
                         ("SDS", self.sds), ("SD1", self.sd1), ("Sa ที่คาบอาคาร (ถ้ามี)", self.sa),
                         ("ประเภทความสำคัญ", self.category), ("ระบบโครงสร้าง", self.system)):
            f.addRow(label, w)
        self.lay.addLayout(f)
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.lay.addWidget(self.preview)
        for w in (self.ss, self.s1, self.sds, self.sd1, self.sa):
            w.valueChanged.connect(self._update)
        for w in (self.mode, self.site, self.category, self.system):
            w.currentIndexChanged.connect(self._update)
        self.enabled.toggled.connect(self._update)
        self.add_apply()

    def _update(self, *_):
        from ..structure.seismic import IMPORTANCE, SYSTEMS, design_category, site_coefficients
        direct = self.mode.currentData() == "direct"
        for w in (self.ss, self.s1, self.site):
            w.setEnabled(not direct)
        for w in (self.sds, self.sd1, self.sa):
            w.setEnabled(direct)
        if direct:
            sds, sd1 = self.sds.value(), self.sd1.value()
        else:
            fa, fv = site_coefficients(self.ss.value(), self.s1.value(), self.site.currentData())
            sds, sd1 = 2 / 3 * fa * self.ss.value(), 2 / 3 * fv * self.s1.value()
        cat = design_category(sds, sd1, self.category.currentData())
        name, R, _o, cd, allowed = SYSTEMS[self.system.currentData()]
        text = (f"SDS = {sds:.3f} g · SD1 = {sd1:.3f} g · ประเภทการออกแบบ {cat} · "
                f"I = {IMPORTANCE[self.category.currentData()]:g} · R = {R:g} · Cd = {cd:g}")
        if cat not in allowed:
            text += f"<br><span style='color:#c62828'>ประเภท {cat} ไม่อนุญาตให้ใช้{name}</span>"
        self.preview.setText(text if self.enabled.isChecked() else "ไม่คิดแรงแผ่นดินไหว")

    def load(self):
        s = self.building.seismic
        self.enabled.setChecked(s.enabled)
        for c, v in ((self.mode, s.mode), (self.site, s.site_class), (self.category, s.category),
                     (self.system, s.system)):
            c.setCurrentIndex(max(0, c.findData(v)))
        for w, v in ((self.ss, s.ss), (self.s1, s.s1), (self.sds, s.sds), (self.sd1, s.sd1), (self.sa, s.sa)):
            w.setValue(v)
        self._update()

    def apply(self):
        s = self.building.seismic
        s.enabled = self.enabled.isChecked()
        s.mode, s.site_class = self.mode.currentData(), self.site.currentData()
        s.category, s.system = self.category.currentData(), self.system.currentData()
        s.ss, s.s1, s.sds, s.sd1, s.sa = (self.ss.value(), self.s1.value(), self.sds.value(),
                                          self.sd1.value(), self.sa.value())


class ResultsPage(Page):
    title = "8. ผลคำนวณและส่งออก"
    run_requested = Signal()
    export_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        row = QHBoxLayout()
        run = QPushButton("คำนวณโครงสร้าง")
        run.setStyleSheet("font-weight:bold; padding:6px;")
        run.clicked.connect(self.run_requested.emit)
        row.addWidget(run)
        for key, label in (("report", "รายการคำนวณ Excel"), ("dxf", "แบบ DXF"), ("boq", "BOQ ปร.4")):
            b = QPushButton(label)
            b.clicked.connect(lambda _c=False, k=key: self.export_requested.emit(k))
            row.addWidget(b)
        self.lay.addLayout(row)
        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setMaximumHeight(170)
        self.lay.addWidget(self.summary)
        self.tabs = QTabWidget()
        self.lay.addWidget(self.tabs)

    def show_result(self, res):
        self.tabs.clear()
        if res is None:
            self.summary.setPlainText("ยังไม่ได้คำนวณ — กด คำนวณโครงสร้าง")
            return
        lines = []
        if res.roof:
            r = res.roof
            lines.append(f"หลังคา {r.load_plan:.0f} กก./ตร.ม. · แป {r.purlin.section} · จันทัน {r.rafter.section}")
        lines.append(f"เกณฑ์ {CODES.get(res.building.design_code, '')} · fc = {res.concrete.fc:.1f} ksc")
        lines.append(f"พื้น {len(res.slabs)} แผ่น · คาน {len(res.beams)} ช่วง · เสา {len(res.columns)} ท่อน · "
                     f"ฐานราก {len(res.footings)} ฐาน · เสาเข็มรวม {res.total_piles()} ต้น")
        wr = res.wind
        if wr:
            vx, vy = wr.base_shear
            lines.append(f"แรงลม ({'เมือง' if wr.terrain == 'urban' else 'โล่ง/ชายฝั่ง'}"
                         f"{', อาคารสาธารณะ +15%' if wr.public else ''}): สูง {wr.height:.1f} ม. · "
                         f"แรงเฉือนที่ฐาน X {vx:,.0f} กก. Y {vy:,.0f} กก.")
        q = res.seismic
        if q:
            lines.append(f"แผ่นดินไหว: SDS {q.sds:.3f} SD1 {q.sd1:.3f} · ประเภท {q.category} · T {q.period:.2f} วินาที · "
                         f"Cs {q.cs:.4f} · W {q.weight:,.0f} กก. · V {q.base_shear:,.0f} กก.")
        f = res.fire
        if f and f.applies:
            lines.append("การทนไฟ: " + " · ".join(f"{n} {h:g} ชม." for n, h, _s in f.floors)
                         + (f" · หลังคา {f.roof_hours:g} ชม." if f.roof_hours else ""))
        lines.append("ผล: ผ่านทุกรายการ" if res.ok else "ผล: มีรายการไม่ผ่าน (สีแดง)")
        lines += ["⚠ " + w for w in res.warnings]
        lines.append("ผลคำนวณเบื้องต้น ต้องให้วิศวกรผู้มีใบอนุญาตตรวจสอบและลงนาม")
        self.summary.setPlainText("\n".join(lines))
        ok = lambda v: "OK" if v else "NG"
        self._table("พื้น", ["ชั้น", "แผ่น", "Mark", "ชนิด", "หนา", "เหล็กสั้น", "เหล็กยาว", "บน", "ผล",
                             "หมายเหตุ", "อ้างอิง"],
                    [(s.level, s.panel, s.mark, f"{s.kind} กรณี {s.case}" if s.case else s.kind, s.thickness,
                      s.bars_short, s.bars_long, s.bars_top, ok(s.ok), s.note, s.refs) for s in res.slabs])
        if res.stairs:
            self._table("บันได", ["ชื่อ", "ชั้น", "ช่อง", "ชนิด", "ลูกตั้ง×ลูกนอน", "ช่วง", "หนา", "M กก.-ม./ม.",
                                  "เหล็กหลัก", "เหล็กบน", "เหล็กกันร้าว", "ผล", "หมายเหตุ", "อ้างอิง"],
                        [(st.name, st.level, st.panel, "มีชานพัก" if st.kind == "landing" else "ช่วงเดียว",
                          f"{st.risers}×{st.riser * 100:.1f}/{st.tread * 100:.0f} ซม.", f"{st.span:.2f}",
                          f"{st.thickness:.2f}", f"{st.moment:,.0f}", st.bars_main, st.bars_top, st.bars_temp,
                          ok(st.ok), st.note, st.refs) for st in res.stairs])
        self._table("คาน", ["ชั้น", "ช่วง", "Mark", "b×h", "M-", "M+", "บน", "ล่าง", "ปลอก", "ผล",
                            "หมายเหตุ", "อ้างอิง"],
                    [(x.level, x.span, x.mark, f"{x.b:.2f}×{x.h:.2f}", f"{x.m_neg:,.0f}", f"{x.m_pos:,.0f}",
                      x.top, x.bottom, x.stirrup, ok(x.ok), x.note, x.refs) for x in res.beams])
        self._table("เสา", ["ตำแหน่ง", "ช่วง", "Mark", "P กก.", "ขนาด", "เหล็ก", "ปลอก", "Mx (D+L)", "My (D+L)",
                            "ผล", "แรงอัดร่วมโมเมนต์", "หมายเหตุ", "อ้างอิง"],
                    [(c.node, c.segment, c.mark, f"{c.load:,.0f}", f"{c.b:.2f}×{c.h:.2f}", c.bars, c.ties,
                      f"{c.m_dx + c.m_lx:,.0f}", f"{c.m_dy + c.m_ly:,.0f}", ok(c.ok), c.slender, c.note, c.refs)
                     for c in res.columns])
        self._table("ฐานราก", ["ตำแหน่ง", "Mark", "P กก.", "เข็ม", "จำนวน", "ขนาดฐาน", "เหล็ก X", "เหล็ก Y",
                               "ผล", "หมายเหตุ", "อ้างอิง"],
                    [(f.node, f.mark, f"{f.load:,.0f}", f.pile, f.piles,
                      f"{f.width:.2f}×{f.length:.2f}×{f.thickness:.2f}", f.bars_x, f.bars_y, ok(f.ok),
                      f.note, f.refs) for f in res.footings])
        if wr:
            kinds = {"column": "เสา", "beam": "คาน", "footing": "ฐานราก"}
            rows = [(f"ชั้น {lv.level}", f"{lv.z0:.2f}–{lv.z1:.2f} ม.", "", f"Fx {lv.fx:,.0f} Fy {lv.fy:,.0f}",
                     f"Vx {lv.vx:,.0f} Vy {lv.vy:,.0f}", f"Δ/h {max(lv.drift_x, lv.drift_y):.4f}", "", "", lv.note)
                    for lv in wr.levels]
            rows += [(kinds[c.kind], c.where, c.direction, c.demand, c.capacity, f"{c.ratio:.2f}", c.detail,
                      ok(c.ok), c.note) for c in wr.checks]
            rows += [("หมายเหตุ", w, "", "", "", "", "", "", "") for w in wr.warnings]
            self._table("แรงลม", ["ชิ้นส่วน", "ตำแหน่ง", "ทิศ", "แรง", "กำลัง", "อัตราส่วน", "ปลอก", "ผล",
                                  "หมายเหตุ"], rows)
        if q:
            rows = [(f"ชั้น {st.level}", f"hx {st.hx:.2f} ม.", f"W {st.wx:,.0f}", f"F {st.fx:,.0f}",
                     f"V {st.vx:,.0f}", f"Δx {st.drift_x * 1000:.1f} Δy {st.drift_y * 1000:.1f} มม.",
                     f"≤ {st.limit * 1000:.0f} มม. θ {st.theta:.3f}", "", ok(st.ok), st.note)
                    for st in q.storeys]
            kinds = {"column": "เสา", "beam": "คาน", "footing": "ฐานราก"}
            rows += [(kinds[c.kind], c.where, c.direction, c.demand, c.capacity, f"{c.ratio:.2f}", c.detail, "",
                      ok(c.ok), c.note) for c in q.checks]
            rows += [("หมายเหตุ", w, "", "", "", "", "", "", "", "") for w in q.warnings]
            self._table("แผ่นดินไหว", ["ชิ้นส่วน", "ตำแหน่ง", "ทิศ", "แรง", "กำลัง", "อัตราส่วน", "รายละเอียดเหล็กปลอก",
                                        "", "ผล", "หมายเหตุ"], rows)
        from ..standards import REFS, STATUS_TEXT
        self._table("มาตรฐานและที่มา", ["รหัส", "มาตรฐาน / เอกสาร", "ข้อ / ค่าที่ใช้", "สถานะ"],
                    [(REFS[c].code, REFS[c].title, REFS[c].clause, STATUS_TEXT[REFS[c].status])
                     for c in res.all_refs()])

    def _table(self, name, headers, rows):
        t = QTableWidget(len(rows), len(headers))
        t.setHorizontalHeaderLabels(headers)
        for r, row in enumerate(rows):
            for c, v in enumerate(row):
                it = QTableWidgetItem(str(v))
                if v == "NG":
                    it.setBackground(NG_FILL)
                t.setItem(r, c, it)
        t.resizeColumnsToContents()
        self.tabs.addTab(t, f"{name} ({len(rows)})")

