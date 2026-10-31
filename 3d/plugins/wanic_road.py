# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
# WANICNSURVEY 3D — "WANIC ออกแบบถนน" (survey points to road sections).
# Developed for WANICNSURVEY by นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ, 2569.
"""นำเข้าจุดสำรวจ วิเคราะห์รูปตัดตามยาว รูปตัดขวาง ปริมาณดิน และสร้างโมเดลถนน 3 มิติ.

1. «📥 นำเข้าจุดสำรวจ» reads the P,N,E,Z,D file of the section survey;
   the shots coded CL make the axis (or «ใช้เส้นที่เลือก» takes a chain of
   edges drawn in the model).
2. The template (platform, crown, shoulders, cut and fill slopes) and the
   grade line as a PVI table (station, elevation, vertical curve), with
   «PVI อัตโนมัติ» to start from.
3. «🔍 วิเคราะห์» opens the results the way RoadOne shows them: the
   profile with its PVI labels, every cross section with STA / NGL /
   design elevations / cut and fill m², and the earthworks table.
4. «🏔 สร้างโมเดล 3 มิติ» puts the ground and the finished road (with its
   side slopes to daylight) in the model; DXF and CSV go out for the CAD
   and the spreadsheet. The engine is :mod:`core.wanic_road`.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from core import wanic_road as R
from core.road import alignment as A
from core.wanic_ui import safe as _safe

TITLE = "ออกแบบถนน"
KEY = "wanic_road"
BG = QColor("#101418")
GRID = QColor("#3a4048")
GROUND = QColor("#3ddc4a")
DESIGN = QColor("#ff4040")
TEXT = QColor("#e8e8e8")
AXIS = QColor("#ff5a36")
CYAN = QColor("#3fb8ff")
BAND = 64.0                     # a band of the profile: "0+000.000" standing up


def _selected_path(scene):
    """The selected chain of edges as world (x, y, z), or a Thai reason.

    Plugins are loaded by file path, so this does not import the profile
    plugin's twin of it (``import plugins.x`` fails in the Windows build)."""
    from core.group import iter_placements
    from core.sweep import order_path_edges
    edges = [e for e in scene.selection if hasattr(e, "v0") and hasattr(e, "v1")]
    if not edges:
        return "เลือกเส้นแนวทางในโมเดลก่อน (เส้นที่ต่อกันเป็นสายเดียว)"
    got = order_path_edges(edges)
    if got is None:
        return "เส้นที่เลือกต้องต่อกันเป็นสายเดียว (ไม่แตกกิ่ง ไม่ขาดตอน)"
    pts, _closed = got
    group = getattr(scene, "edit_group", None)
    matrix = None
    if group is not None:
        for top in scene.groups:
            for g, m in iter_placements(top):
                if g is group:
                    matrix = m
        matrix = matrix or getattr(group, "xform", None)
    if matrix is not None:
        pts = [matrix.map(q) for q in pts]
    return [(float(q.x()), float(q.y()), float(q.z())) for q in pts]


# -- the drawings --------------------------------------------------------------------------

class ProfileView(QWidget):
    """The longitudinal profile, drawn like the CAD's: grid with
    elevations both sides, ground (green), grade (red) with its vertical
    curves, G = ±x.xxx % and the PVI STA / ELEV / VC / MO labels, and the
    station / ground / design bands."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.an = None
        self.setMinimumSize(900, 480)

    def show_analysis(self, an):
        self.an = an
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), BG)
        an = self.an
        if an is None or not an.profile:
            p.setPen(TEXT)
            p.drawText(self.rect(), Qt.AlignCenter, "ยังไม่มีผลการวิเคราะห์")
            return
        p.setRenderHint(QPainter.Antialiasing)
        zs = [q.z for q in an.profile if q.z is not None] + [z for _s, z in an.grade]
        datum, top = math.floor(min(zs)) - 1.0, math.ceil(max(zs)) + 1.0
        L = max(an.length, 1e-6)
        left, right, up, bands = 70.0, 70.0, 40.0, 3 * BAND
        w = self.width() - left - right
        h = self.height() - up - bands - 20.0

        def xy(s, z):
            return QPointF(left + s / L * w, up + (top - z) / (top - datum) * h)
        font = QFont(self.font())
        font.setPointSizeF(7.5)
        p.setFont(font)
        step = 1.0 if top - datum <= 30 else 5.0
        level = datum
        while level <= top + 1e-9:
            a, b = xy(0, level), xy(L, level)
            p.setPen(QPen(GRID, 1))
            p.drawLine(a, b)
            p.setPen(TEXT)
            p.drawText(QRectF(0, a.y() - 8, left - 6, 16), Qt.AlignRight | Qt.AlignVCenter, f"{level:.3f}")
            p.drawText(QRectF(b.x() + 6, b.y() - 8, right, 16), Qt.AlignLeft | Qt.AlignVCenter,
                       f"{level:.3f}")
            level += step
        y0 = up + h
        # stations: grid line and the three bands, labels standing up
        last = -1e9
        for q in an.profile:
            x = xy(q.s, datum).x()
            p.setPen(QPen(GRID, 1))
            p.drawLine(QPointF(x, up), QPointF(x, y0 + bands))
            if x - last < 13:
                continue
            last = x
            zd = R.P.grade_at(an.grade, q.s) if an.grade else None
            for k, txt in enumerate((A.format_station(q.s, 3),
                                     "" if q.z is None else f"{q.z:.3f}",
                                     "" if zd is None else f"{zd:.3f}")):
                if not txt:
                    continue
                p.save()
                p.translate(x + 4, y0 + bands - k * BAND - 4)
                p.rotate(-90)
                p.setPen(TEXT if k != 2 else DESIGN)
                p.drawText(QPointF(0, 0), txt)
                p.restore()
        p.setPen(QPen(GRID, 1))
        for k in range(4):
            p.drawLine(QPointF(4, y0 + k * BAND), QPointF(left + w, y0 + k * BAND))
        p.setPen(TEXT)
        for k, title in enumerate(("ระดับออกแบบ", "ระดับดินเดิม", "สถานี")):
            p.drawText(QRectF(4, y0 + k * BAND, left - 8, BAND), Qt.AlignLeft | Qt.AlignVCenter
                       | Qt.TextWordWrap, title)
        # the lines
        path = QPainterPath()
        first = True
        for q in an.profile:
            if q.z is None:
                first = True
                continue
            (path.moveTo if first else path.lineTo)(xy(q.s, q.z))
            first = False
        p.setPen(QPen(GROUND, 1.6))
        p.drawPath(path)
        if an.grade:
            base = [(s, z) for s, z, _v in an.pvis]
            p.setPen(QPen(DESIGN, 0.8, Qt.DashLine))
            for (s0, z0), (s1, z1) in zip(base, base[1:]):
                p.drawLine(xy(s0, z0), xy(s1, z1))
            path = QPainterPath(xy(*an.grade[0]))
            for s, z in an.grade[1:]:
                path.lineTo(xy(s, z))
            p.setPen(QPen(DESIGN, 2.0))
            p.drawPath(path)
            p.setPen(TEXT)
            for (s0, z0), (s1, z1), g in zip(base, base[1:], R.P.grade_slopes(base)):
                a, b = xy(s0, z0), xy(s1, z1)
                p.save()
                p.translate((a.x() + b.x()) / 2, (a.y() + b.y()) / 2 - 6)
                p.rotate(math.degrees(math.atan2(b.y() - a.y(), b.x() - a.x())))
                p.drawText(QRectF(-60, -14, 120, 14), Qt.AlignCenter, f"G = {g:+.3f} %")
                p.restore()
            for c in an.curves:
                a = xy(c.s, c.z)
                p.setPen(QPen(TEXT, 1))
                p.drawLine(a, QPointF(a.x(), a.y() - 70))
                for k, txt in enumerate((f"PVI STA. {A.format_station(c.s, 3)}", f"ELEV. = {c.z:.3f}",
                                         f"VC. = {c.length:.3f}", f"MO. = {c.middle_ordinate:+.3f}")):
                    p.drawText(QPointF(a.x() + 4, a.y() - 60 + k * 12), txt)
                for s_end in (c.bvc, c.evc):
                    b = xy(s_end, c.z_at(s_end))
                    p.drawLine(QPointF(b.x(), b.y() - 6), QPointF(b.x(), b.y() + 6))
        p.setPen(CYAN)
        font.setPointSizeF(9.5)
        p.setFont(font)
        p.drawText(QPointF(left, 20), f"รูปตัดตามยาว  ระยะทาง {an.length:,.3f} ม."
                   + (f"   ดินตัด {an.cut_total:,.1f} ม³   ดินถม {an.fill_total:,.1f} ม³"
                      if an.rows else ""))


class SectionsView(QWidget):
    """Every cross section in a grid, the RoadOne way: elevation scale,
    the axis in red, ground green, design red, the design elevations at
    the edges and the axis, STA. / NGL = under it and ดินตัด / ดินถม ม²
    beside it."""

    CELL_W, CELL_H = 420, 260

    def __init__(self, parent=None, columns: int = 3):
        super().__init__(parent)
        self.an = None
        self.columns = columns
        self.setMinimumWidth(self.CELL_W * columns)

    def show_analysis(self, an):
        self.an = an
        rows = math.ceil(len(an.sections) / self.columns) if an else 0
        self.setMinimumHeight(max(200, rows * self.CELL_H))
        self.resize(self.CELL_W * self.columns, max(200, rows * self.CELL_H))
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), BG)
        an = self.an
        if an is None or not an.sections:
            p.setPen(TEXT)
            p.drawText(self.rect(), Qt.AlignCenter, "ยังไม่มีรูปตัดขวาง")
            return
        p.setRenderHint(QPainter.Antialiasing)
        font = QFont(self.font())
        font.setPointSizeF(7.5)
        p.setFont(font)
        hw = an.settings.half_width
        visible = ev.rect()
        for k, sec in enumerate(an.sections):
            col, row = k % self.columns, k // self.columns
            cell = QRectF(col * self.CELL_W, row * self.CELL_H, self.CELL_W, self.CELL_H)
            if not cell.intersects(QRectF(visible)):
                continue
            self._paint_section(p, cell, sec, hw, an)

    def _paint_section(self, p, cell, sec, hw, an):
        zz = [z for _o, z in sec.ground] + ([z for _o, z in sec.design] if sec.design else [])
        datum, top = math.floor(min(zz)) - 1.0, math.ceil(max(zz)) + 1.0
        x0, x1 = cell.left() + 38, cell.right() - 110
        y0, y1 = cell.top() + 22, cell.bottom() - 46
        # across at the width's scale, up exaggerated up to 5x, the way a
        # road section is drawn (H 1:200, V 1:50): at true shape a 30 m
        # wide section of a 2 m embankment is a flat line
        kx = (x1 - x0) / (2 * hw)
        ky = min((y1 - y0) / (top - datum), 5.0 * kx)
        cx = (x0 + x1) / 2

        def xy(o, z):
            return QPointF(cx + o * kx, y1 - (z - datum) * ky)
        p.setPen(QPen(GRID, 1))
        p.drawLine(xy(-hw, datum), xy(-hw, top))
        level = datum
        while level <= top + 1e-9:
            a = xy(-hw, level)
            p.setPen(QPen(GRID, 1))
            p.drawLine(QPointF(a.x() - 5, a.y()), a)
            p.setPen(TEXT)
            p.drawText(QRectF(a.x() - 36, a.y() - 7, 30, 14), Qt.AlignRight | Qt.AlignVCenter,
                       f"{level:.0f}—")
            level += 1.0 if top - datum <= 20 else 5.0
        p.setPen(QPen(AXIS, 1.2))
        p.drawLine(xy(0, datum), xy(0, top))
        path = QPainterPath(xy(*sec.ground[0]))
        for o, z in sec.ground[1:]:
            path.lineTo(xy(o, z))
        p.setPen(QPen(GROUND, 1.5))
        p.drawPath(path)
        if sec.design:
            path = QPainterPath(xy(*sec.design[0]))
            for o, z in sec.design[1:]:
                path.lineTo(xy(o, z))
            p.setPen(QPen(DESIGN, 1.8))
            p.drawPath(path)
            p.setPen(TEXT)
            half = an.settings.width / 2.0
            # left edge ends at its point, right edge starts at its, the
            # axis above both: three numbers 6 m apart never run together
            for o, box, align in ((-half, (-62, -20), Qt.AlignRight), (0.0, (-30, -34), Qt.AlignCenter),
                                  (half, (2, -20), Qt.AlignLeft)):
                z = R.P._z_on(sec.design, o)
                if z is not None:
                    a = xy(o, z)
                    p.drawText(QRectF(a.x() + box[0], a.y() + box[1], 60, 14),
                               align | Qt.AlignVCenter, f"{z:.3f}")
            tx = cell.right() - 104
            ty = cell.top() + 30
            p.drawText(QPointF(tx, ty), f"ดินตัด  {sec.cut:.3f} ม²")
            p.drawText(QPointF(tx, ty + 16), f"ดินถม  {sec.fill:.3f} ม²")
        p.setPen(CYAN)
        p.drawText(QRectF(cell.left(), cell.bottom() - 42, cell.width() - 80, 16), Qt.AlignCenter,
                   f"STA.  {A.format_station(sec.s, 3)}")
        if sec.z_ground is not None:
            p.setPen(TEXT)
            p.drawText(QRectF(cell.left(), cell.bottom() - 26, cell.width() - 80, 16), Qt.AlignCenter,
                       f"NGL  =  {sec.z_ground:.3f}")


class ResultsDialog(QDialog):
    """The analysis in three tabs and its exports."""

    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel
        self.setWindowTitle("WANIC ออกแบบถนน — ผลการวิเคราะห์")
        self.resize(1200, 800)
        lay = QVBoxLayout(self)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        lay.addWidget(self.summary)
        self.tabs = QTabWidget()
        self.profile = ProfileView()
        self.sections = SectionsView()
        scroll = QScrollArea()
        scroll.setWidget(self.sections)
        scroll.setWidgetResizable(False)
        scroll.setStyleSheet("background:#101418")
        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            ["สถานี", "ระดับดินเดิม", "ระดับออกแบบ", "พท.ดินตัด ม²", "พท.ดินถม ม²",
             "ดินตัด ม³", "ดินถม ม³", "ดินตัดสะสม", "ดินถมสะสม", "สุทธิสะสม"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tabs.addTab(self.profile, "รูปตัดตามยาว")
        self.tabs.addTab(scroll, "รูปตัดขวาง")
        self.tabs.addTab(self.table, "ปริมาณดิน")
        lay.addWidget(self.tabs, 1)
        row = QHBoxLayout()
        for text, fn in (("🏔 สร้างโมเดล 3 มิติ", panel.build_model),
                         ("💾 ส่งออก DXF (ผัง รูปตัดตามยาว รูปตัดขวาง)", panel.export_dxf),
                         ("💾 ส่งออกตารางปริมาณดิน (CSV)", panel.export_csv)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, f=fn: _safe(self, f))
            row.addWidget(b)
        lay.addLayout(row)

    def show_analysis(self, an):
        self.profile.show_analysis(an)
        self.sections.show_analysis(an)
        self.table.setRowCount(len(an.rows))
        right = Qt.AlignRight | Qt.AlignVCenter
        for r, row in enumerate(an.rows):
            vals = [A.format_station(row.s, 3),
                    "" if row.z_ground is None else f"{row.z_ground:.3f}",
                    "" if row.z_design is None else f"{row.z_design:.3f}",
                    f"{row.cut_area:.3f}", f"{row.fill_area:.3f}", f"{row.cut_volume:,.3f}",
                    f"{row.fill_volume:,.3f}", f"{row.cut_total:,.3f}", f"{row.fill_total:,.3f}",
                    f"{row.mass:+,.3f}"]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c:
                    it.setTextAlignment(right)
                self.table.setItem(r, c, it)
        text = (f"แนวทางยาว {an.length:,.3f} ม. · รูปตัดขวาง {len(an.sections)} รูป ทุก "
                f"{an.settings.step:g} ม. · พื้นผิว {len(an.tin.triangles):,} สามเหลี่ยม")
        if an.rows:
            text += (f"<br><b>ดินตัด {an.cut_total:,.3f} ม³ · ดินถม {an.fill_total:,.3f} ม³ · "
                     f"สุทธิ {an.cut_total - an.fill_total:+,.3f} ม³</b>")
        if an.warnings:
            text += "<br><span style='color:#d97706'>⚠ " + "<br>⚠ ".join(an.warnings[:6]) + "</span>"
        self.summary.setText(text)


# -- the panel -----------------------------------------------------------------------------

class RoadPanel(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.shots: list = []
        self.axis: list = []
        self.origin = (0.0, 0.0, 0.0)
        self.analysis = None
        self.results = None
        lay = QVBoxLayout(self)

        box = QGroupBox("1. ข้อมูลสำรวจและแนวทาง")
        f = QVBoxLayout(box)
        row = QHBoxLayout()
        self.order = QComboBox()
        for key, label in (("auto", "ลำดับคอลัมน์: อัตโนมัติ"), ("PNEZD", "P,N,E,Z,รหัส"),
                           ("PENZD", "P,E,N,Z,รหัส"), ("NEZD", "N,E,Z,รหัส"), ("ENZD", "E,N,Z,รหัส")):
            self.order.addItem(label, key)
        row.addWidget(self.order)
        b = QPushButton("📥 นำเข้าจุดสำรวจ…")
        b.clicked.connect(lambda: _safe(self, self.import_points))
        row.addWidget(b)
        f.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel("รหัสศูนย์กลางทาง"))
        self.cl_code = QLineEdit("CL")
        self.cl_code.setMaximumWidth(70)
        row.addWidget(self.cl_code)
        b = QPushButton("แนวทางจากจุด CL")
        b.clicked.connect(lambda: _safe(self, self.axis_from_codes))
        row.addWidget(b)
        b = QPushButton("ใช้เส้นที่เลือก")
        b.setToolTip("เลือกเส้นที่ต่อกันเป็นสายเดียวในโมเดล แล้วกดเพื่อใช้เป็นแนวศูนย์กลางทาง")
        b.clicked.connect(lambda: _safe(self, self.axis_from_selection))
        row.addWidget(b)
        b = QPushButton("⇄ กลับทิศ")
        b.clicked.connect(lambda: _safe(self, self.reverse_axis))
        row.addWidget(b)
        f.addLayout(row)
        self.info = QLabel("ยังไม่มีข้อมูล — นำเข้าไฟล์จุดสำรวจ (.csv .txt) ที่มีรหัส CL ตามแนวศูนย์กลาง")
        self.info.setWordWrap(True)
        f.addWidget(self.info)
        lay.addWidget(box)

        box = QGroupBox("2. รูปแบบทาง")
        form = QFormLayout(box)
        self.spins = {}
        d = R.Settings()
        for key, label, lo, hi, dec, suffix in (
                ("step", "ช่วงรูปตัดขวาง", 1, 500, 2, " ม."),
                ("half_width", "ความกว้างรูปตัดแต่ละข้าง", 2, 200, 2, " ม."),
                ("width", "ความกว้างผิวทาง (รวม)", 0, 60, 2, " ม."),
                ("crown", "ความลาดขวางหลังเต่า", -10, 10, 2, " %"),
                ("shoulder", "ไหล่ทางแต่ละข้าง", 0, 10, 2, " ม."),
                ("shoulder_slope", "ความลาดไหล่ทาง", -10, 20, 2, " %"),
                ("cut_hv", "ลาดดินตัด (ราบ:ดิ่ง)", 0.1, 10, 2, " : 1"),
                ("fill_hv", "ลาดดินถม (ราบ:ดิ่ง)", 0.1, 10, 2, " : 1"),
                ("max_edge", "ตัดสามเหลี่ยมที่ด้านยาวเกิน (0 = ไม่ตัด)", 0, 1000, 1, " ม.")):
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setDecimals(dec)
            s.setSuffix(suffix)
            s.setValue(getattr(d, key))
            form.addRow(label, s)
            self.spins[key] = s
        self.method = QComboBox()
        self.method.addItem("ปริซึมอยด์ (Prismoidal)", "prismoidal")
        self.method.addItem("พื้นที่เฉลี่ยปลายตัด (End area)", "end-area")
        form.addRow("วิธีคำนวณปริมาตร", self.method)
        lay.addWidget(box)

        box = QGroupBox("3. เส้นระดับออกแบบ (PVI)")
        v = QVBoxLayout(box)
        self.pvi = QTableWidget(0, 3)
        self.pvi.setHorizontalHeaderLabels(["สถานี (ม.)", "ระดับ (ม.)", "โค้งดิ่ง VC (ม.)"])
        self.pvi.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pvi.setMinimumHeight(150)
        v.addWidget(self.pvi)
        row = QHBoxLayout()
        for text, fn in (("➕ เพิ่ม", self.add_pvi), ("➖ ลบ", self.remove_pvi),
                         ("⚙ PVI อัตโนมัติ", self.auto_pvi)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, fn=fn: _safe(self, fn))
            row.addWidget(b)
        v.addLayout(row)
        lay.addWidget(box)

        row = QHBoxLayout()
        b = QPushButton("🔍 วิเคราะห์")
        b.setStyleSheet("font-weight:bold;padding:6px")
        b.clicked.connect(lambda: _safe(self, self.analyse))
        row.addWidget(b)
        b = QPushButton("🏔 สร้างโมเดล 3 มิติ")
        b.clicked.connect(lambda: _safe(self, self.build_model))
        row.addWidget(b)
        lay.addLayout(row)
        row = QHBoxLayout()
        b = QPushButton("💾 DXF")
        b.clicked.connect(lambda: _safe(self, self.export_dxf))
        row.addWidget(b)
        b = QPushButton("💾 CSV ปริมาณดิน")
        b.clicked.connect(lambda: _safe(self, self.export_csv))
        row.addWidget(b)
        lay.addLayout(row)
        try:
            from core.wanic_sign import label_html
            sign = QLabel(label_html("ออกแบบถนน"))
            sign.setWordWrap(True)
            lay.addWidget(sign)
        except Exception:
            pass
        lay.addStretch(1)
        QTimer.singleShot(0, lambda: _safe(self, self.load))

    # ---- the document ------------------------------------------------------------------
    def settings(self) -> R.Settings:
        s = R.Settings(**{k: float(w.value()) for k, w in self.spins.items()})
        s.method = self.method.currentData()
        return s

    def pvis(self) -> list:
        out = []
        for r in range(self.pvi.rowCount()):
            cells = [self.pvi.item(r, c) for c in range(3)]
            try:
                s = float(cells[0].text().replace(",", ""))
                z = float(cells[1].text().replace(",", ""))
            except (AttributeError, ValueError):
                continue
            try:
                vc = float(cells[2].text()) if cells[2] and cells[2].text().strip() else 0.0
            except ValueError:
                vc = 0.0
            out.append((s, z, vc))
        return sorted(out)

    def set_pvis(self, pvis):
        self.pvi.setRowCount(0)
        for s, z, vc in pvis:
            r = self.pvi.rowCount()
            self.pvi.insertRow(r)
            for c, v in enumerate((f"{s:.3f}", f"{z:.3f}", f"{vc:g}")):
                self.pvi.setItem(r, c, QTableWidgetItem(v))

    def save(self):
        data = {"shots": [[s.name, s.e, s.n, s.z, s.code] for s in self.shots],
                "axis": [list(p) for p in self.axis], "origin": list(self.origin),
                "pvis": [list(p) for p in self.pvis()],
                "settings": {k: float(w.value()) for k, w in self.spins.items()},
                "method": self.method.currentData(), "cl": self.cl_code.text()}
        self._last = json.loads(json.dumps(data))
        setter = getattr(self.app, "set_document_data", None)
        if callable(setter):
            setter(data)

    def load(self):
        getter = getattr(self.app, "document_data", None)
        data = getter(None) if callable(getter) else None
        # every edit of the model calls this: only another document (or an
        # undo of ours) reloads, so PVIs being typed are not thrown away
        if not data or data == getattr(self, "_last", None):
            return
        self._last = data
        self.analysis = None
        self.shots = [R.Shot(str(n), float(e), float(no), float(z), str(c))
                      for n, e, no, z, c in data.get("shots", [])]
        self.axis = [tuple(p) for p in data.get("axis", [])]
        self.origin = tuple(data.get("origin", (0.0, 0.0, 0.0)))
        for k, v in (data.get("settings") or {}).items():
            if k in self.spins:
                self.spins[k].setValue(float(v))
        i = self.method.findData(data.get("method", "prismoidal"))
        if i >= 0:
            self.method.setCurrentIndex(i)
        self.cl_code.setText(data.get("cl", "CL"))
        self.set_pvis(data.get("pvis", []))
        self._report()

    def _report(self, extra: str = ""):
        cl = sum(1 for s in self.shots if R.is_cl(s.code, self._codes()))
        text = f"จุดสำรวจ {len(self.shots):,} จุด · จุดศูนย์กลางทาง {cl} จุด"
        if len(self.axis) >= 2:
            text += f" · แนวทางยาว {A.polyline_length(self.axis):,.3f} ม."
        self.info.setText(text + (f"<br>{extra}" if extra else ""))

    def _codes(self):
        return tuple(c.strip() for c in self.cl_code.text().split(",") if c.strip()) or R.CL_CODES

    def _flash(self, text):
        f = getattr(self.app.viewport, "flash_status", None)
        if callable(f):
            f(text)

    # ---- 1. data and axis ---------------------------------------------------------------
    def import_points(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "นำเข้าจุดสำรวจ", "", "ไฟล์จุด (*.csv *.txt *.pnt *.xyz);;ทุกไฟล์ (*)")
        if not path:
            return
        raw = Path(path).read_bytes()
        for enc in ("utf-8-sig", "cp874", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        try:
            self.shots = R.parse_points(text, self.order.currentData())
        except ValueError as e:
            QMessageBox.warning(self, TITLE, str(e))
            return
        self.analysis = None
        self.axis = R.centerline_from_codes(self.shots, self._codes())
        if len(self.axis) >= 2 and not self.pvis():
            self.auto_pvi(save=False)
        self.save()
        self._report("" if len(self.axis) >= 2 else
                     "ไม่พบจุดรหัส CL — เขียนเส้นแนวทางในโมเดลแล้วกด «ใช้เส้นที่เลือก»")
        self._flash(f"นำเข้าจุดสำรวจ {len(self.shots):,} จุด")

    def axis_from_codes(self):
        axis = R.centerline_from_codes(self.shots, self._codes())
        if len(axis) < 2:
            QMessageBox.information(self, TITLE, "ไม่พบจุดที่มีรหัสศูนย์กลางทางอย่างน้อย 2 จุด")
            return
        self.axis = axis
        self.save()
        self._report()

    def axis_from_selection(self):
        pts = _selected_path(self.app.scene)
        if isinstance(pts, str):
            QMessageBox.information(self, TITLE, pts)
            return
        ox, oy, _oz = self.origin
        self.axis = [(x + ox, y + oy) for x, y, _z in pts]
        self.save()
        self._report()

    def reverse_axis(self):
        if len(self.axis) < 2:
            return
        length = A.polyline_length(self.axis)
        self.axis = list(reversed(self.axis))
        self.set_pvis(sorted((length - s, z, vc) for s, z, vc in self.pvis()))
        self.save()
        self._report()

    # ---- 3. grade line -----------------------------------------------------------------
    def add_pvi(self):
        pv = self.pvis()
        s = (pv[-1][0] + 100.0) if pv else 0.0
        z = pv[-1][1] if pv else 100.0
        self.set_pvis(pv + [(s, z, 0.0)])

    def remove_pvi(self):
        r = self.pvi.currentRow()
        self.pvi.removeRow(r if r >= 0 else self.pvi.rowCount() - 1)

    def auto_pvi(self, save: bool = True):
        if len(self.axis) < 2 or len(self.shots) < 3:
            QMessageBox.information(self, TITLE, "นำเข้าจุดสำรวจและกำหนดแนวทางก่อน")
            return
        tin = R.build_tin(self.shots, self.spins["max_edge"].value())
        self.set_pvis(R.auto_pvis(tin, self.axis))
        if save:
            self.save()

    # ---- analysis and outputs ----------------------------------------------------------
    def analyse(self):
        if len(self.shots) < 3:
            QMessageBox.information(self, TITLE, "นำเข้าจุดสำรวจก่อน (อย่างน้อย 3 จุด)")
            return None
        try:
            an = R.analyse(self.shots, self.axis, self.pvis(), self.settings())
        except ValueError as e:
            QMessageBox.warning(self, TITLE, str(e))
            return None
        self.analysis = an
        self.save()
        if self.results is None:
            self.results = ResultsDialog(self)
        self.results.show_analysis(an)
        self.results.show()
        self.results.raise_()
        self._report(f"ดินตัด {an.cut_total:,.3f} ม³ · ดินถม {an.fill_total:,.3f} ม³")
        return an

    def _ensure(self):
        return self.analysis or self.analyse()

    def build_model(self):
        an = self._ensure()
        if an is None:
            return
        import numpy as np

        from core.group import Group
        from core.history import CompoundCommand, InsertGroupCommand
        from core.mesh import Mesh

        def group(tris, name, color):
            mesh = Mesh()
            if tris:
                pos = np.asarray([c for t in tris for c in t], dtype=np.float64)
                n = len(tris)
                mesh.add_faces_bulk(pos, np.full(n, 3, dtype=np.int64), np.ones(n, dtype=np.int64))
            g = Group(mesh, name=name)
            g.material = {"color": color}
            g.ext = {KEY: {"origin": list(an.origin)}}
            return g
        self.origin = an.origin
        groups = [group(R.terrain_mesh(an), "ภูมิประเทศ (TIN)", (0.55, 0.68, 0.42))]
        road = R.corridor_mesh(an)
        if road:
            groups.append(group(road, "ถนนออกแบบ", (0.35, 0.35, 0.38)))
        self.app.viewport.history.execute(CompoundCommand([InsertGroupCommand(g) for g in groups]))
        n = getattr(self.app.viewport, "notify_scene_changed", None)
        if callable(n):
            n()
        self.app.viewport.update()
        self.save()
        self._flash(f"สร้างโมเดลแล้ว: พื้นผิว {len(an.tin.triangles):,} สามเหลี่ยม"
                    + (f" · ถนน {len(road):,} สามเหลี่ยม" if road else "")
                    + f" · จุดอ้างอิง E {an.origin[0]:,.0f} N {an.origin[1]:,.0f}")

    def export_dxf(self):
        an = self._ensure()
        if an is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "ส่งออก DXF", "ออกแบบถนน.dxf", "DXF (*.dxf)")
        if not path:
            return
        R.dxf_document(an).saveas(path)
        self._flash(f"บันทึก {path} แล้ว")

    def export_csv(self):
        an = self._ensure()
        if an is None:
            return
        if not an.rows:
            QMessageBox.information(self, TITLE, "ยังไม่มีปริมาณดิน (ใส่ PVI อย่างน้อย 2 จุด)")
            return
        path, _ = QFileDialog.getSaveFileName(self, "ส่งออกตารางปริมาณดิน", "ปริมาณดิน.csv",
                                              "CSV (*.csv)")
        if not path:
            return
        Path(path).write_text(R.earthworks_csv(an), encoding="utf-8-sig")
        self._flash(f"บันทึก {path} แล้ว")


def setup(app) -> None:
    panel = RoadPanel(app)
    dock = app.add_panel(TITLE, panel)
    app.window._wanic_road = panel
    app.on_document_changed(lambda: QTimer.singleShot(0, lambda: _safe(panel, panel.load)))

    def show():
        app.show_panel(dock)
        dock.raise_()

    app.add_menu_action("WANIC ออกแบบถนน…", show,
                        tip="นำเข้าจุดสำรวจ วิเคราะห์รูปตัดตามยาว รูปตัดขวาง "
                            "ปริมาณดินตัด-ถม และสร้างโมเดลถนน 3 มิติ")
