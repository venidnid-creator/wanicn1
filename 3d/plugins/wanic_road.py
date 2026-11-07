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
import os
import threading
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from core import wanic_pavement as V
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
        # the horizontal curves: PC to PT bracketed over the grid
        p.setPen(QPen(CYAN, 1.2))
        for c in an.hcurves:
            if c.radius <= 0:
                continue
            a, b = xy(c.s_pc, top), xy(c.s_pt, top)
            yb = up + 4
            p.drawLine(QPointF(a.x(), yb), QPointF(b.x(), yb))
            p.drawLine(QPointF(a.x(), yb - 4), QPointF(a.x(), yb + 4))
            p.drawLine(QPointF(b.x(), yb - 4), QPointF(b.x(), yb + 4))
            p.drawText(QRectF(a.x(), yb + 2, max(b.x() - a.x(), 160), 14), Qt.AlignLeft,
                       f" PI-{c.number}  R = {c.radius:.3f}  Δ = {A.format_dms(c.delta)} {c.side}")
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
            layers = an.settings.pavement_layers()
            if layers and sec.formation:
                for _name, outline, colour in R.layer_polygons(sec.design, an.settings.template(),
                                                               layers):
                    poly = QPainterPath(xy(*outline[0]))
                    for o, z in outline[1:]:
                        poly.lineTo(xy(o, z))
                    poly.closeSubpath()
                    p.setPen(QPen(QColor(200, 200, 200), 0.6))
                    p.setBrush(QColor.fromRgbF(*colour))
                    p.drawPath(poly)
                p.setBrush(Qt.NoBrush)
                path = QPainterPath(xy(*sec.formation[0]))
                for o, z in sec.formation[1:]:
                    path.lineTo(xy(o, z))
                p.setPen(QPen(QColor("#d946ef"), 1.2))
                p.drawPath(path)
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
        self.curves = QTableWidget(0, 14)
        self.curves.setHorizontalHeaderLabels(
            ["PI", "สถานี PI", "E (PI)", "N (PI)", "Δ", "ทิศ", "R (ม.)", "T (ม.)", "L (ม.)",
             "E ระยะภายนอก (ม.)", "M ระยะกลางโค้ง (ม.)", "LC คอร์ด (ม.)", "สถานี PC", "สถานี PT"])
        self.curves.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.curves.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tabs.addTab(self.curves, "โค้งราบ (PI PC PT)")
        self.pavement = QTableWidget(0, 5)
        self.pavement.setHorizontalHeaderLabels(
            ["ชั้นทาง", "หนา (ม.)", "กว้าง (ม.)", "ปริมาตร (ม³)", "พื้นที่ (ม²)"])
        self.pavement.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.pavement.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tabs.addTab(self.pavement, "ชั้นทาง")
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
        self.curves.setRowCount(len(an.hcurves))
        fs = A.format_station
        for r, c in enumerate(an.hcurves):
            vals = [f"PI-{c.number}", fs(c.s_pi, 3), f"{c.pi[0]:,.3f}", f"{c.pi[1]:,.3f}",
                    A.format_dms(c.delta), c.side]
            if c.radius > 0:
                vals += [f"{c.radius:.3f}", f"{c.tangent:.3f}", f"{c.length:.3f}", f"{c.external:.3f}",
                         f"{c.middle_ordinate:.3f}", f"{c.chord:.3f}", fs(c.s_pc, 3), fs(c.s_pt, 3)]
            else:
                vals += ["จุดหักมุม", "", "", "", "", "", "", ""]
            for k, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if k > 1:
                    it.setTextAlignment(right)
                self.curves.setItem(r, k, it)
        quantities = an.layer_quantities()
        self.pavement.setRowCount(len(quantities))
        for r, (name, th, w, vol, area) in enumerate(quantities):
            for k, v in enumerate((name, f"{th:.3f}", f"{w:.3f}", f"{vol:,.3f}",
                                   f"{area:,.3f}" if r == 0 else "")):
                it = QTableWidgetItem(v)
                if k:
                    it.setTextAlignment(right)
                self.pavement.setItem(r, k, it)
        text = (f"แนวทางยาว {an.length:,.3f} ม. · รูปตัดขวาง {len(an.sections)} รูป ทุก "
                f"{an.settings.step:g} ม. · พื้นผิว {len(an.tin.triangles):,} สามเหลี่ยม")
        text += (f" · โค้งราบ {sum(1 for c in an.hcurves if c.radius > 0)} โค้ง"
                 f"<br>{R.PAVEMENTS.get(an.settings.pavement, ('กำหนดเอง',))[0]} · ชั้นทางหนารวม "
                 f"{an.settings.structure:.3f} ม. (ดินตัด-ถมวัดถึงใต้ชั้นทาง)")
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
        self.pis: list = []            # R.PiStake: the axis designed through the field PIs
        self.pi_curves: list = []
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
        b = QPushButton("📍 แนวทางจากหมุด PI")
        b.setToolTip("ออกแบบแนวทางผ่านหมุด PI/POT ที่วางในสนาม: แนวตรงระหว่างหมุด และโค้งวงกลม"
                     "ที่ทุก PI — รัศมีจากรหัส PIR=…, PIE=… (ระยะ E) หรือ PIT=… ในสนาม "
                     "ถ้าไม่มี ประมาณจากจุด CL ที่สำรวจ")
        b.clicked.connect(lambda: _safe(self, self.axis_from_pis))
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

        box = QGroupBox("3. โครงสร้างชั้นทาง (ถนนคอนกรีต / ลาดยาง)")
        v = QVBoxLayout(box)
        self.pavement = QComboBox()
        for key, (title, kind, _layers) in R.PAVEMENTS.items():
            self.pavement.addItem(title, key)
        self.pavement.currentIndexChanged.connect(lambda _i: _safe(self, self._pavement_changed))
        v.addWidget(self.pavement)
        self.layers = QTableWidget(0, 2)
        self.layers.setHorizontalHeaderLabels(["ชั้นทาง (บนลงล่าง) — เลือกหรือพิมพ์ชื่อ", "หนา (ม.)"])
        self.layers.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.layers.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.layers.setMinimumHeight(170)
        v.addWidget(self.layers)
        self.structure = QLabel()
        v.addWidget(self.structure)
        row = QHBoxLayout()
        for text, fn in (("➕ เพิ่มชั้น", self.add_layer), ("➖ ลบชั้น", self.remove_layer),
                         ("▲", lambda: self.move_layer(-1)), ("▼", lambda: self.move_layer(1))):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, fn=fn: _safe(self, fn))
            row.addWidget(b)
        v.addLayout(row)
        calc = QPushButton("🧮 ออกแบบความหนาโครงสร้างทาง (AI 1970 / Road Note 29)…")
        calc.setToolTip("คำนวณ DTN / ESA ความหนาแต่ละชั้น ตรวจสอบทุกชั้น เทียบแบบมาตรฐาน ทช. "
                        "ใส่ผลลงตารางชั้นทาง และบันทึกรายการคำนวณเป็น PDF")
        calc.clicked.connect(lambda _=False: _safe(self, self.open_pavement_design))
        v.addWidget(calc)
        note = QLabel("<span style='color:#6b7280;font-size:11px'>ความหนาเป็นค่าเริ่มต้นตามแบบทั่วไปของ "
                      "ทช./ทล. — ตรวจกับแบบมาตรฐานที่เลือกตามปริมาณจราจรและ CBR ของโครงการ "
                      "แล้วแก้ในตารางได้ · ดินตัด-ถมคิดถึงใต้ชั้นทาง</span>")
        note.setWordWrap(True)
        v.addWidget(note)
        lay.addWidget(box)
        self._pavement_changed()

        box = QGroupBox("4. เส้นระดับออกแบบ (PVI)")
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

        box = QGroupBox("5. ตำแหน่งบนแผนที่ (Google Earth)")
        v = QVBoxLayout(box)
        row = QHBoxLayout()
        row.addWidget(QLabel("ระบบพิกัดที่สำรวจ"))
        self.grid = QComboBox()
        for label, zone, datum in R.GRIDS:
            self.grid.addItem(label, (zone, datum))
        self.grid.currentIndexChanged.connect(lambda _i: self._grid_changed())
        row.addWidget(self.grid, 1)
        v.addLayout(row)
        row = QHBoxLayout()
        for text, fn, tip in (
                ("📍 จังหวัด อำเภอ ตำบล", self.find_place,
                 "แปลงพิกัด UTM เป็นละติจูด/ลองจิจูด แล้วถาม OpenStreetMap ว่าแนวทางอยู่ตำบล อำเภอ จังหวัดใด"),
                ("🌏 เปิดใน Google Earth", self.open_google_earth,
                 "บันทึกแนวทาง ผิวทาง สถานี โค้งราบ และจุดสำรวจเป็นไฟล์ KML แล้วเปิดด้วย Google Earth Pro"),
                ("🌐 Google Earth บนเว็บ", self.open_earth_web,
                 "เปิด Google Earth ในเบราว์เซอร์ตรงที่ตั้งงาน (ลากไฟล์ KML ลงไปเพื่อดูแนวทาง)")):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, fn=fn: _safe(self, fn))
            row.addWidget(b)
        v.addLayout(row)
        self.place = QLabel("ตำแหน่ง: — (กด «📍 จังหวัด อำเภอ ตำบล»)")
        self.place.setWordWrap(True)
        self.place.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(self.place)
        lay.addWidget(box)
        self._place = ""

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
        b = QPushButton("📐 แบบงานทาง A3 (แปลน-รูปตัดตามยาว · รูปตัดขวาง · ตาราง) PDF/DXF…")
        b.setStyleSheet("QPushButton{background:#8A5A00;color:white;font-weight:bold;"
                        "padding:6px;border-radius:6px}")
        b.setToolTip("ชุดแบบ G (ผังสังเขป ข้อมูลออกแบบ ตารางโค้ง หมุด), PP (แปลนและรูปตัดตามยาว "
                     "พร้อมแถบระดับ), ST (รูปตัดขวางทุกสถานี พร้อมพื้นที่/ปริมาตร), VT (ตารางปริมาณดิน)")
        b.clicked.connect(lambda: _safe(self, self.export_sheets))
        lay.addWidget(b)
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
        s.pavement = self.pavement.currentData()
        s.layers = self.layer_rows()
        return s

    # ---- pavement layers -----------------------------------------------------------------
    def open_pavement_design(self):
        PavementDesignDialog(self).exec()
        self.save()

    def layer_rows(self) -> list:
        """(name, thickness, colour) of each row, top first: the name from
        its editable list, the thickness from its spin box (typed or
        stepped, 0.005 m to 3 m)."""
        out = []
        for r in range(self.layers.rowCount()):
            name = self.layers.cellWidget(r, 0)
            thick = self.layers.cellWidget(r, 1)
            label = name.currentText().strip() if name is not None else ""
            label = label or f"ชั้นที่ {r + 1}"
            t = float(thick.value()) if thick is not None else 0.0
            out.append((label, t, R.layer_colour(label, r)))
        return out

    def set_layers(self, layers):
        self.layers.setRowCount(0)
        for name, t, *_c in layers:
            self._insert_layer(self.layers.rowCount(), str(name), float(t))
        self._show_structure()

    def _insert_layer(self, r: int, name: str, t: float):
        self.layers.insertRow(r)
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(list(R.LAYER_NAMES))
        combo.setCurrentText(name)
        combo.currentTextChanged.connect(lambda _t: self._layers_edited())
        spin = QDoubleSpinBox()
        spin.setRange(0.0, 3.0)
        spin.setDecimals(3)
        spin.setSingleStep(0.01)
        spin.setSuffix(" ม.")
        spin.setValue(t)
        spin.valueChanged.connect(lambda _v: self._layers_edited())
        self.layers.setCellWidget(r, 0, combo)
        self.layers.setCellWidget(r, 1, spin)
        self.layers.setRowHeight(r, 28)

    def _layers_edited(self):
        self.analysis = None
        self._show_structure()

    def _show_structure(self):
        rows = self.layer_rows() if hasattr(self, "structure") else []
        if hasattr(self, "structure"):
            self.structure.setText(f"รวม {len(rows)} ชั้น หนา {sum(t for _n, t, _c in rows):.3f} ม.")

    def _pavement_changed(self):
        key = self.pavement.currentData()
        if key != "custom":
            self.set_layers(R.pavement_layers(key))
        self.analysis = None

    def _selected_layer(self) -> int:
        for r in range(self.layers.rowCount()):
            for c in (0, 1):
                w = self.layers.cellWidget(r, c)
                if w is not None and (w.hasFocus() or (w.focusProxy() and w.focusProxy().hasFocus())):
                    return r
        return self.layers.currentRow()

    def add_layer(self):
        """A new layer under the selected one (at the bottom when none is)."""
        r = self._selected_layer()
        r = self.layers.rowCount() if r < 0 else r + 1
        self._insert_layer(r, "ชั้นทรายรองพื้น", 0.05)
        self.layers.setCurrentCell(r, 0)
        self._layers_edited()

    def remove_layer(self):
        r = self._selected_layer()
        self.layers.removeRow(r if r >= 0 else self.layers.rowCount() - 1)
        self._layers_edited()

    def move_layer(self, step: int):
        rows = self.layer_rows()
        r = self._selected_layer()
        if not (0 <= r < len(rows)) or not (0 <= r + step < len(rows)):
            return
        rows[r], rows[r + step] = rows[r + step], rows[r]
        self.set_layers(rows)
        self.layers.setCurrentCell(r + step, 0)
        self._layers_edited()

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
                "pis": R.pi_rows(self.pis),
                "pvis": [list(p) for p in self.pvis()],
                "settings": {k: float(w.value()) for k, w in self.spins.items()},
                "method": self.method.currentData(), "cl": self.cl_code.text(),
                "pavement": self.pavement.currentData(),
                "grid": self.grid.currentIndex(), "place": self._place,
                "layers": [[n, t] for n, t, _c in self.layer_rows()]}
        if getattr(self, "pave_design", None):
            data["pave_design"] = self.pave_design
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
        self.pis, self.pi_curves = [], []
        if data.get("pis"):
            al = R.alignment_from_pis(R.stakes_of(data["pis"]))
            self.pis, self.pi_curves = al.stakes, al.curves
        self.origin = tuple(data.get("origin", (0.0, 0.0, 0.0)))
        for k, v in (data.get("settings") or {}).items():
            if k in self.spins:
                self.spins[k].setValue(float(v))
        i = self.method.findData(data.get("method", "prismoidal"))
        if i >= 0:
            self.method.setCurrentIndex(i)
        self.cl_code.setText(data.get("cl", "CL"))
        i = self.pavement.findData(data.get("pavement", "drr-ac"))
        if i >= 0:
            self.pavement.blockSignals(True)
            self.pavement.setCurrentIndex(i)
            self.pavement.blockSignals(False)
        if "layers" in data:
            self.set_layers(data["layers"])
        self.pave_design = data.get("pave_design")
        self.grid.blockSignals(True)
        self.grid.setCurrentIndex(int(data.get("grid", 0)))
        self.grid.blockSignals(False)
        self._place = data.get("place", "")
        self._show_place()
        self.set_pvis(data.get("pvis", []))
        self._report()

    def _report(self, extra: str = ""):
        cl = sum(1 for s in self.shots if R.is_cl(s.code, self._codes()))
        text = f"จุดสำรวจ {len(self.shots):,} จุด · จุดศูนย์กลางทาง {cl} จุด"
        if len(self.axis) >= 2:
            text += f" · แนวทางยาว {A.polyline_length(self.axis):,.3f} ม."
            if self.pis:
                text += f" (ออกแบบผ่านหมุด PI {sum(1 for s in self.pis if s.kind == 'PI')} หมุด)"
        self.info.setText(text + (f"<br>{extra}" if extra else ""))
        if hasattr(self, "place"):
            self._show_place()

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
        self.pis, self.pi_curves = [], []
        pi_notes = []
        if len(R.pi_stakes(self.shots)) >= 3:
            pi_notes = self._design_through_pis()
        if len(self.axis) >= 2 and not self.pvis():
            self.auto_pvi(save=False)
        self.save()
        self._report("" if len(self.axis) >= 2 else
                     "ไม่พบจุดรหัส CL — เขียนเส้นแนวทางในโมเดลแล้วกด «ใช้เส้นที่เลือก»")
        self._flash(f"นำเข้าจุดสำรวจ {len(self.shots):,} จุด")
        notes = []
        turned = sum(1 for s in self.shots if s.swapped)
        if turned:
            notes.append(f"พบ {turned:,} จุดที่บันทึกเป็น N,E สลับกับส่วนอื่นของไฟล์ "
                         "(ไฟล์ GNSS/RTK ที่รวมหลายงาน) — สลับเป็น E,N ให้แล้ว "
                         "ตำแหน่งบน Google Earth และพื้นผิวดินจึงถูกต้อง")
        dup = R.duplicate_names(self.shots)
        if dup:
            notes.append(f"เลขจุดซ้ำ {len(dup):,} เลข (เช่น {', '.join(dup[:5])}) — "
                         "ใช้ได้ตามปกติ แต่ควรตั้งเลขจุดใหม่เพื่ออ้างอิงได้ถูกจุด")
        if self.pis:
            notes.append(self._pi_summary(pi_notes))
        if notes:
            QMessageBox.information(self, TITLE, "\n\n".join(notes))

    def _design_through_pis(self, stakes=None) -> list:
        """Set the axis from the PI stakes (from the shots unless given);
        the notes of the design."""
        stakes = stakes if stakes is not None else R.pi_stakes(self.shots)
        cl = R.centerline_from_codes(self.shots, self._codes())
        al = R.alignment_from_pis(stakes, cl)
        self.axis, self.pis, self.pi_curves = al.axis, al.stakes, al.curves
        return al.notes

    def _pi_summary(self, notes) -> str:
        pis = [s for s in self.pis if s.kind == "PI"]
        lines = [f"แนวทางออกแบบผ่านหมุด PI {len(pis)} หมุด "
                 f"(ยาว {A.polyline_length(self.axis):,.3f} ม.) แทนแนวจุด CL:"]
        for s in pis:
            r = f"R = {s.radius:,.1f} ม." if s.radius else "จุดหักมุม"
            lines.append(f"  • {s.name}: {r} — {s.source}")
        return "\n".join(lines + [f"⚠ {n}" for n in notes])

    def axis_from_pis(self):
        if len(R.pi_stakes(self.shots)) < 2:
            QMessageBox.information(self, TITLE, "ไม่พบหมุด PI/POT อย่างน้อย 2 หมุด "
                                    "(รหัส PI, PIE=…, PIR=…, POT, BOP, EOP)")
            return
        notes = self._design_through_pis()
        self.save()
        self._report()
        QMessageBox.information(self, TITLE, self._pi_summary(notes))

    def axis_from_codes(self):
        axis = R.centerline_from_codes(self.shots, self._codes())
        if len(axis) < 2:
            QMessageBox.information(self, TITLE, "ไม่พบจุดที่มีรหัสศูนย์กลางทางอย่างน้อย 2 จุด")
            return
        self.axis = axis
        self.pis, self.pi_curves = [], []
        self.save()
        self._report()

    def axis_from_selection(self):
        pts = _selected_path(self.app.scene)
        if isinstance(pts, str):
            QMessageBox.information(self, TITLE, pts)
            return
        ox, oy, _oz = self.origin
        self.axis = [(x + ox, y + oy) for x, y, _z in pts]
        self.pis, self.pi_curves = [], []
        self.save()
        self._report()

    def reverse_axis(self):
        if len(self.axis) < 2:
            return
        length = A.polyline_length(self.axis)
        if self.pis:
            self._design_through_pis(list(reversed(self.pis)))
        else:
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

    # ---- on the globe ---------------------------------------------------------------------
    def _zone_datum(self):
        zone, datum = self.grid.currentData()
        return int(zone), str(datum)

    def _grid_changed(self):
        self._place = ""
        self._show_place()

    def _centre(self):
        if len(self.axis) < 2:
            QMessageBox.information(self, TITLE, "นำเข้าจุดสำรวจและกำหนดแนวทางก่อน")
            return None
        zone, datum = self._zone_datum()
        lat, lon = R.axis_centre_wgs84(self.axis, zone, datum)
        if not R.in_thailand(lat, lon):
            QMessageBox.warning(
                self, TITLE,
                f"พิกัดกลางแนวทางแปลงได้ ละติจูด {lat:.6f} ลองจิจูด {lon:.6f} ซึ่งอยู่นอกประเทศไทย\n"
                "ตรวจระบบพิกัด (โซน 47 หรือ 48, WGS84 หรือ Indian 1975) และลำดับคอลัมน์ N/E ของไฟล์")
        return lat, lon

    def _show_place(self):
        text = "ตำแหน่ง: "
        if len(self.axis) >= 2:
            zone, datum = self._zone_datum()
            lat, lon = R.axis_centre_wgs84(self.axis, zone, datum)
            text += f"กลางแนวทาง ละติจูด {lat:.6f}° ลองจิจูด {lon:.6f}° (WGS84)"
        else:
            text += "—"
        if self._place:
            text += f"<br><b>{self._place}</b>"
        self.place.setText(text)

    def find_place(self):
        got = self._centre()
        if got is None:
            return
        lat, lon = got
        if os.environ.get("WANIC_OFFLINE"):
            self._place = ""
            self._show_place()
            return
        self.place.setText(self.place.text() + "<br>กำลังถาม OpenStreetMap…")
        result: dict = {}

        def work():
            try:
                result["place"] = R.reverse_geocode(lat, lon)
            except Exception as e:                      # shown to the user below
                result["error"] = e
        thread = threading.Thread(target=work, daemon=True)
        thread.start()

        def poll():
            if thread.is_alive():
                QTimer.singleShot(200, poll)
                return
            if "error" in result:
                self._show_place()
                QMessageBox.warning(self, TITLE, "ถามตำแหน่งจาก OpenStreetMap ไม่สำเร็จ "
                                    f"(ต้องต่ออินเทอร์เน็ต): {result['error']}")
                return
            self._place = R.place_text(result["place"])
            self._show_place()
            self.save()
            self._flash(f"แนวทางอยู่ที่ {self._place}")
        QTimer.singleShot(200, poll)

    def kml_text(self) -> str:
        zone, datum = self._zone_datum()
        return R.kml_document(self.axis, self.settings(), zone, datum, self.analysis, self.shots,
                              self._place)

    def open_google_earth(self):
        if self._centre() is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "บันทึกไฟล์สำหรับ Google Earth",
                                              "ถนน-GoogleEarth.kml", "Google Earth (*.kml)")
        if not path:
            return
        Path(path).write_text(self.kml_text(), encoding="utf-8")
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        if os.environ.get("WANIC_OFFLINE") or not QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            QMessageBox.information(
                self, TITLE, f"บันทึก {path} แล้ว\nเปิดด้วย Google Earth Pro (ดับเบิลคลิกไฟล์) หรือกด "
                "«🌐 Google Earth บนเว็บ» แล้วลากไฟล์ลงในหน้าเว็บ")
        self._flash(f"บันทึก {path} แล้ว — เปิดใน Google Earth")

    def open_earth_web(self):
        got = self._centre()
        if got is None:
            return
        url = R.earth_web_url(*got, distance=max(800.0, A.polyline_length(self.axis) * 1.6))
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        if not os.environ.get("WANIC_OFFLINE"):
            QDesktopServices.openUrl(QUrl(url))
        self._flash("เปิด Google Earth บนเว็บแล้ว — ลากไฟล์ KML ลงในหน้าเว็บเพื่อดูแนวทาง")
        return url

    # ---- analysis and outputs ----------------------------------------------------------
    def analyse(self):
        if len(self.shots) < 3:
            QMessageBox.information(self, TITLE, "นำเข้าจุดสำรวจก่อน (อย่างน้อย 3 จุด)")
            return None
        try:
            an = R.analyse(self.shots, self.axis, self.pvis(), self.settings(),
                           hcurves=self.pi_curves if self.pis else None)
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
            concrete = R.pavement_kind(an.settings.pavement) == "concrete"
            groups.append(group(road, "ถนนคอนกรีต" if concrete else "ถนนลาดยาง",
                                (0.80, 0.80, 0.77) if concrete else (0.20, 0.20, 0.22)))
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

    def export_sheets(self):
        """The drawing set of the road (PDF and DXF, A3)."""
        an = self._ensure()
        if an is None:
            return []
        dlg = RoadSheetsDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return []
        info = dlg.info()
        if info.get("drain", {}).get("u_both"):             # both sides, the whole road
            info["drain"]["u_length"] = 2.0 * an.designed_length
        zone, datum = self._zone_datum()
        info.update(zone=zone, datum=datum, pave=getattr(self, "pave_design", None),
                    crs=f"UTM {datum} โซน {zone}N · ระดับ MSL",
                    location=info.get("location") or self._place)
        from core import wanic_drawings as D
        from core import wanic_road_sheets as RS
        site, site_note = self._site_map(an, info)
        sheets = RS.build_road_set(an, info, self.shots, info["groups"], site)
        if not sheets:
            QMessageBox.information(self, TITLE, "ยังไม่มีแนวทางที่วิเคราะห์แล้ว")
            return []
        name = (info.get("project") or "แบบงานทาง").replace(" ", "_")
        path, _ = QFileDialog.getSaveFileName(self, "บันทึกแบบงานทาง", f"{name}.pdf",
                                              "PDF (*.pdf);;DXF (*.dxf)")
        if not path:
            return []
        stem = os.path.splitext(path)[0]
        saved = []
        if info.get("pdf", True):
            from plugins.wanic_building import render_pdf
            render_pdf(sheets, stem + ".pdf", info.get("paper", "A3"))
            saved.append(stem + ".pdf" + (" (A4 ย่อทั้งแผ่น)" if info.get("paper") == "A4" else ""))
        if info.get("dxf", True):
            Path(stem + "_แผ่นแบบ.dxf").write_bytes(D.dxf_bytes(sheets))
            saved.append(stem + "_แผ่นแบบ.dxf")
        groups = ", ".join(f"{g} {sum(1 for x in sheets if x.group == g)} แผ่น"
                           for g in info["groups"] if any(x.group == g for x in sheets))
        self._flash(f"ส่งออกแบบงานทาง {len(sheets)} แผ่น ({groups})")
        QMessageBox.information(self, TITLE, f"ส่งออกแบบงานทาง {len(sheets)} แผ่น ({groups})\n"
                                + "\n".join(saved) + (f"\n\n{site_note}" if site_note else ""))
        return saved

    def _site_map(self, an, info):
        """The location sheet's pictures: satellite tiles (downloaded in the
        background) or a picture saved from Google Earth Pro; the ตำบล
        อำเภอ จังหวัด asked from OpenStreetMap when not known yet.
        Returns (site or None, a note for the user)."""
        from PySide6.QtWidgets import QApplication, QProgressDialog

        from core import wanic_road_sheets as RS
        from core import wanic_sitemap as M
        mode = info.get("site", "tiles")
        if mode == "none":
            return None, ""
        main, vic = RS.site_views(an, info)
        site = {"mode": mode, "main": main, "vicinity": vic, "credit": M.SOURCES["esri"][2]}
        note = []
        if mode == "file":
            img = QImage(info.get("site_file") or "")
            if img.isNull():
                note.append("เปิดภาพจาก Google Earth Pro ไม่ได้ — ใช้ภาพถ่ายดาวเทียมแทน")
                site["mode"] = mode = "tiles"
            else:
                site.update(image=_jpeg(img), size=(img.width(), img.height()), main=None)
        offline = bool(os.environ.get("WANIC_OFFLINE"))
        result: dict = {"done": 0, "total": 0}

        def work():
            try:
                if not info.get("location") and not offline:
                    lat, lon = R.axis_centre_wgs84(an.axis, int(info["zone"]), info["datum"])
                    result["place"] = R.place_text(R.reverse_geocode(lat, lon))
            except Exception as e:                      # noqa: BLE001 -- told below
                result["place_error"] = e

            def prog(i, n):
                result["done"] = i
            views = ([main] if mode == "tiles" else []) + [vic]
            result["total"] = sum(len(v.tiles()) for v in views)
            result["tiles"] = [M.fetch_tiles(v, progress=prog) for v in views]
        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        dlg = QProgressDialog("กำลังดาวน์โหลดภาพถ่ายดาวเทียมและหาตำบล อำเภอ จังหวัด…",
                              "ข้ามแผนที่", 0, 0, self)
        dlg.setWindowTitle(TITLE)
        dlg.setMinimumDuration(400)
        while thread.is_alive():
            QApplication.processEvents()
            if result["total"]:
                dlg.setMaximum(result["total"])
                dlg.setValue(min(result["done"], result["total"] - 1))
            if dlg.wasCanceled():
                note.append("ข้ามการดาวน์โหลดภาพถ่ายดาวเทียม")
                break
            thread.join(0.05)
        dlg.close()
        tiles = result.get("tiles") or []
        if mode == "tiles":
            site["image"] = stitch(main, tiles[0]) if tiles else None
            vtiles = tiles[1] if len(tiles) > 1 else {}
            if not site["image"] and not dlg.wasCanceled():
                note.append("ดาวน์โหลดภาพถ่ายดาวเทียมไม่ได้ (ต้องต่ออินเทอร์เน็ต) — แผนที่ตั้งมีแต่แนวทาง "
                            "หรือแนบภาพที่บันทึกจาก Google Earth Pro แทน")
        else:
            vtiles = tiles[0] if tiles else {}
        site["vicinity_image"] = stitch(vic, vtiles)
        if result.get("place"):
            self._place = info["location"] = result["place"]
            self._show_place()
            self.save()
        elif "place_error" in result:
            note.append("หาตำบล อำเภอ จังหวัด จาก OpenStreetMap ไม่สำเร็จ — พิมพ์ในช่อง «สถานที่» ได้")
        return site, "\n".join(note)

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



class PavementDesignDialog(QDialog):
    """ออกแบบความหนาโครงสร้างชั้นทาง: AI 1970 (ถนนลาดยาง) / Road Note 29
    (ถนน คสล.) — the data, the calculation sheet beside it as it changes,
    the layers into the panel's table, the sheet to PDF."""

    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel
        self.setWindowTitle("ออกแบบความหนาโครงสร้างชั้นทาง — AI 1970 / Road Note 29")
        self.resize(1180, 760)
        saved = dict(getattr(panel, "pave_design", None) or {})
        lay = QHBoxLayout(self)
        left = QVBoxLayout()
        self.tabs = QTabWidget()
        left.addWidget(self.tabs)
        lay.addLayout(left, 0)
        right = QVBoxLayout()
        from PySide6.QtWidgets import QTextBrowser
        self.view = QTextBrowser()
        right.addWidget(self.view, 1)
        row = QHBoxLayout()
        for text, fn in (("✅ ใส่ลงตารางชั้นทาง", self.apply_layers),
                         ("📐 ใช้ตามแบบมาตรฐาน ทช.", self.apply_standard),
                         ("🖨 บันทึกรายการคำนวณ PDF", self.save_pdf),
                         ("ปิด", self.accept)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, fn=fn: _safe(self, fn))
            row.addWidget(b)
        right.addLayout(row)
        lay.addLayout(right, 1)
        self.f = {}
        self.project = QLineEdit(saved.get("project", ""))
        self.project.setPlaceholderText("ชื่อโครงการ / สายทาง")
        left.insertWidget(0, self.project)
        self.project.textChanged.connect(lambda _t: self.refresh())

        # --- AI 1970 ---
        w = QWidget()
        form = QFormLayout(w)
        ai = saved.get("ai", {})
        for key, label, lo, hi, dec, suf, dflt in (
                ("idt", "IDT ปริมาณจราจรปีแรก (2 ทิศทาง)", 1, 500000, 0, " คัน/วัน", 1000),
                ("heavy_pct", "ร้อยละรถบรรทุกหนัก 6 ล้อขึ้นไป (A)", 0.1, 100, 2, " %", 10),
                ("lanes", "จำนวนช่องจราจร", 1, 12, 0, " ช่อง", 2),
                ("gross_t", "น้ำหนักเฉลี่ยรถบรรทุกหนัก", 1, 60, 1, " ตัน", 21),
                ("growth_pct", "อัตราเพิ่มปริมาณจราจร (r)", 0, 20, 2, " %", 5),
                ("years", "อายุการออกแบบ (n)", 1, 40, 0, " ปี", 15),
                ("cbr", "CBR ดินคันทาง (เปอร์เซ็นไทล์ 80)", 0.5, 100, 1, " %", 5)):
            form.addRow(label, self._spin(("ai", key), lo, hi, dec, suf, ai.get(key, dflt)))
        self.ai_table = QComboBox()
        self.ai_table.addItem("ออกแบบชั้นทางอัตโนมัติ (ผิว AC + หินคลุก + รองพื้นทาง + คัดเลือก)", "auto")
        self.ai_table.addItem("ตรวจสอบชั้นทางตามตารางในแผง (ข้อ 3)", "table")
        self.ai_table.setCurrentIndex(1 if ai.get("source") == "table" else 0)
        self.ai_table.currentIndexChanged.connect(lambda _i: self.refresh())
        form.addRow("ชั้นทาง", self.ai_table)
        note = QLabel("<span style='color:#6b7280;font-size:11px'>คู่มือกรมทางหลวง: AI ฉบับที่ 8 (1970) · "
                      "Substitution Ratio AC 1.0 · หินคลุก 2.0 · มวลรวม 2.7 · คัดเลือก ก 3.0 · ข 3.5</span>")
        note.setWordWrap(True)
        form.addRow(note)
        self.tabs.addTab(w, "ถนนลาดยาง (AI 1970)")

        # --- Road Note 29 ---
        w = QWidget()
        form = QFormLayout(w)
        rn = saved.get("rn", {})
        width = self.panel.spins["width"].value() if hasattr(self.panel, "spins") else 6.0
        for key, label, lo, hi, dec, suf, dflt in (
                ("adt", "ปริมาณการจราจร ADT", 1, 500000, 0, " คัน/วัน", 500),
                ("lanes", "จำนวนช่องจราจร", 1, 12, 0, " ช่อง", 2),
                ("width", "ความกว้างผิวจราจร", 2, 60, 2, " ม.", width or 6.0),
                ("heavy_pct", "ร้อยละรถบรรทุกหนักทั้งหมด", 0.1, 100, 2, " %", 10),
                ("lt_pct", "ร้อยละรถบรรทุก 6 ล้อ (ของรถหนัก)", 0, 100, 1, " %", 70),
                ("ht_pct", "ร้อยละรถบรรทุก 10 ล้อ (ของรถหนัก)", 0, 100, 1, " %", 30),
                ("loaded_pct", "สัดส่วนรถบรรทุกที่บรรทุกของ (: รถเปล่า)", 0, 100, 0, " %", 100),
                ("growth_pct", "Growth Rate (r)", 0, 20, 2, " %", 4),
                ("years", "อายุการออกแบบ (n)", 1, 50, 0, " ปี", 20),
                ("cbr", "Design CBR Subgrade", 0.5, 100, 1, " %", 4),
                ("slab_length", "ระยะรอยต่อตามขวาง (ยาวแผ่น)", 3, 30, 2, " ม.", 10),
                ("lane_width", "ความกว้างแผ่น (ช่องจราจร)", 2, 6, 2, " ม.", 3.0),
                ("chart_mm", "ความหนาที่อ่านจากกราฟเอง (0 = โปรแกรมอ่านให้)", 0, 400, 1, " มม.", 0),
                ("slab_cm", "ความหนาแผ่นที่กำหนด (0 = ตามแผนภูมิ)", 0, 40, 0, " ซม.", 0),
                ("fc", "กำลังอัดคอนกรีต fc′ (ลูกบาศก์)", 150, 500, 0, " กก./ตร.ซม.", 280)):
            form.addRow(label, self._spin(("rn", key), lo, hi, dec, suf, rn.get(key, dflt)))
        self.rn_steel = QComboBox()
        self.rn_steel.addItem("ตะแกรงเหล็ก Wire mesh (fs = 2,750 กก./ตร.ซม.)", 2750.0)
        self.rn_steel.addItem("เหล็กเส้นกลม RB (fs = 1,200 กก./ตร.ซม.)", 1200.0)
        self.rn_steel.setCurrentIndex(1 if rn.get("fs") == 1200.0 else 0)
        self.rn_steel.currentIndexChanged.connect(lambda _i: self.refresh())
        form.addRow("เหล็กเสริม", self.rn_steel)
        self.rn_kind = QComboBox()
        self.rn_kind.addItem("คอนกรีตเสริมเหล็ก (JRCP)", True)
        self.rn_kind.addItem("คอนกรีตไม่เสริมเหล็ก (JPCP)", False)
        self.rn_kind.setCurrentIndex(0 if rn.get("reinforced", True) else 1)
        self.rn_kind.currentIndexChanged.connect(lambda _i: self.refresh())
        form.addRow("ชนิดผิว", self.rn_kind)
        self.rn_sub = QComboBox()
        self.rn_sub.addItem("รองพื้นทางลูกรัง + ทรายหยาบรองพื้นคอนกรีต 5 ซม.", "laterite")
        self.rn_sub.addItem("รองพื้นทางหินคลุก (ไม่ต้องใช้ทรายรองพื้น)", "crushed")
        self.rn_sub.setCurrentIndex(1 if rn.get("subbase_kind") == "crushed" else 0)
        self.rn_sub.currentIndexChanged.connect(lambda _i: self.refresh())
        form.addRow("ชั้นรองพื้นทาง", self.rn_sub)
        self.rn_ct = QComboBox()
        self.rn_ct.addItem("มีรถบรรทุกวิ่งบนรองพื้นทางระหว่างก่อสร้าง (+8 ซม.)", True)
        self.rn_ct.addItem("ไม่มี", False)
        self.rn_ct.setCurrentIndex(0 if rn.get("construction_traffic", True) else 1)
        self.rn_ct.currentIndexChanged.connect(lambda _i: self.refresh())
        form.addRow("ระหว่างก่อสร้าง", self.rn_ct)
        self.tabs.addTab(w, "ถนน คสล. (Road Note 29)")
        self.tabs.setCurrentIndex(1 if saved.get("method") == "rn29" else 0)
        self.tabs.currentChanged.connect(lambda _i: self.refresh())
        self.refresh()

    def _spin(self, key, lo, hi, dec, suf, value):
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setDecimals(dec)
        s.setSuffix(suf)
        s.setValue(float(value))
        s.valueChanged.connect(lambda _v: self.refresh())
        self.f[key] = s
        return s

    def _v(self, tab, key):
        return float(self.f[(tab, key)].value())

    # ---- the designs ---------------------------------------------------------------------
    def ai_input(self) -> V.AIInput:
        layers = None
        if self.ai_table.currentData() == "table":
            layers = [[n, t * 100.0] for n, t, _c in self.panel.layer_rows() if t > 0]
        return V.AIInput(idt=self._v("ai", "idt"), heavy_pct=self._v("ai", "heavy_pct"),
                         lanes=int(self._v("ai", "lanes")), gross_t=self._v("ai", "gross_t"),
                         growth_pct=self._v("ai", "growth_pct"), years=self._v("ai", "years"),
                         cbr=self._v("ai", "cbr"), layers=layers)

    def rn_input(self) -> V.RNInput:
        lt, ht = self._v("rn", "lt_pct"), self._v("rn", "ht_pct")
        trucks = (V.Truck("รถบรรทุก 6 ล้อ (LT)", lt, (4.0, 11.0)),
                  V.Truck("รถบรรทุก 10 ล้อ (HT)", ht, (5.0, 10.0, 10.0)))
        return V.RNInput(adt=self._v("rn", "adt"), lanes=int(self._v("rn", "lanes")),
                         width=self._v("rn", "width"), heavy_pct=self._v("rn", "heavy_pct"),
                         trucks=trucks, loaded_pct=self._v("rn", "loaded_pct"),
                         growth_pct=self._v("rn", "growth_pct"), years=self._v("rn", "years"),
                         cbr=self._v("rn", "cbr"), reinforced=bool(self.rn_kind.currentData()),
                         construction_traffic=bool(self.rn_ct.currentData()),
                         slab_length=self._v("rn", "slab_length"),
                         lane_width=self._v("rn", "lane_width"),
                         fs=float(self.rn_steel.currentData()),
                         slab_cm=self._v("rn", "slab_cm") or None, fc=self._v("rn", "fc"),
                         chart_mm=self._v("rn", "chart_mm") or None,
                         subbase_kind=str(self.rn_sub.currentData()))

    def method(self) -> str:
        return "rn29" if self.tabs.currentIndex() == 1 else "ai"

    def result(self):
        if self.method() == "ai":
            return V.design_ai(self.ai_input())
        return V.design_rn29(self.rn_input())

    def html(self) -> str:
        res = self.result()
        proj = self.project.text().strip()
        return V.ai_report(res, proj) if self.method() == "ai" else \
            V.rn29_report(res, proj, images=True)

    def document(self, width_px=1400):
        """The calculation sheet as a QTextDocument, with the Road Note 29
        chart (red reading lines) and the trucks as pictures in it."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QTextDocument
        doc = QTextDocument()
        if self.method() == "rn29":
            r = self.result()
            for name, img in rn29_pictures(r).items():
                doc.addResource(QTextDocument.ImageResource, QUrl(name), img)
        doc.setHtml(self.html())
        return doc

    def refresh(self):
        if not hasattr(self, "rn_sub"):
            return
        self.view.setDocument(self.document())
        self.remember()

    def remember(self):
        data = {"method": self.method(), "project": self.project.text(),
                "ai": {k: float(w.value()) for (t, k), w in self.f.items() if t == "ai"},
                "rn": {k: float(w.value()) for (t, k), w in self.f.items() if t == "rn"}}
        data["ai"]["source"] = self.ai_table.currentData()
        data["rn"].update({"subbase_kind": str(self.rn_sub.currentData()),
                           "fs": float(self.rn_steel.currentData()),
                           "reinforced": bool(self.rn_kind.currentData()),
                           "construction_traffic": bool(self.rn_ct.currentData())})
        self.panel.pave_design = data

    # ---- the buttons ---------------------------------------------------------------------
    def _put(self, key: str, layers: list, note: str):
        p = self.panel
        i = p.pavement.findData(key)
        if i >= 0:
            p.pavement.blockSignals(True)
            p.pavement.setCurrentIndex(i)
            p.pavement.blockSignals(False)
        p.set_layers([(n, t) for n, t in layers])
        p.analysis = None
        p.save()
        p._flash(note)

    def apply_layers(self):
        res = self.result()
        if self.method() == "ai":
            self._put("drr-ac", V.ai_layers(res), f"ใส่ชั้นทางตาม AI 1970 (DTN {res.dtn:,.0f}) แล้ว")
        else:
            self._put("drr-rc", V.rn29_layers(res),
                      f"ใส่ชั้นทาง คสล. หนา {res.slab_cm:g} ซม. ตาม Road Note 29 แล้ว")

    def apply_standard(self):
        if self.method() == "ai":
            i = self.ai_input()
            std = V.drr_ac_standard(i.idt, i.cbr, 10 if i.years >= 10 else 7)
            key = "drr-ac"
        else:
            i = self.rn_input()
            std = V.drr_rc_standard(i.adt, i.cbr, 1) or V.drr_rc_standard(i.adt, i.cbr, 2)
            key = "drr-rc"
        if not std:
            QMessageBox.information(self, "แบบมาตรฐาน ทช.",
                                    "ปริมาณจราจรเกินช่วงของตารางแบบมาตรฐาน ทช. — ใช้ผลการคำนวณแทน")
            return
        self._put(key, std["layers"], f"ใส่ชั้นทางตามแบบมาตรฐาน ทช. {std['sheet']} แล้ว")

    def save_pdf(self):
        name = "รายการคำนวณโครงสร้างทาง_" + ("AI1970" if self.method() == "ai" else "RoadNote29")
        path, _ = QFileDialog.getSaveFileName(self, "บันทึกรายการคำนวณ", f"{name}.pdf", "PDF (*.pdf)")
        if not path:
            return
        save_html_pdf(self.document(), path)
        self.panel._flash(f"บันทึก {path} แล้ว")


def rn29_pictures(res, px_per_mm: float = 6.0) -> dict:
    """{"rn29chart": QImage, "rn29trucks": QImage}: รูปที่ 3.16 with the
    reading in red, and the trucks with their axle loads — drawn by the
    same code as the SD-04 sheet."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QFont, QImage

    from core import wanic_drawings as D
    from core import wanic_road_detail as RD
    from core import wanic_road_sheets as RS
    from plugins.wanic_building import paint_sheet
    i = res.inp
    out = {}
    for name, (w, h), build in (
            ("rn29chart", (200.0, 150.0),
             lambda sh: RD.rn29_chart(sh, (0, 0, 200, 150), res.esa / 1e6, float(i.chart_mm or 0.0),
                                      res.slab_cm, i.cbr, i.reinforced)),
            ("rn29trucks", (130.0, 62.0),
             lambda sh: RD.trucks_block(sh, 8.0, 21.0, 52.0, i.trucks, 14.0))):
        sh = D.Sheet("img", name)
        sh.colors = dict(RS.COLORS)
        build(sh)
        img = QImage(int(w * px_per_mm), int(h * px_per_mm), QImage.Format_RGB32)
        img.fill(0xFFFFFF)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, True)
        fonts = {}

        def font(hh, bold, fonts=fonts):
            key = (round(hh, 2), bold)
            if key not in fonts:
                f = QFont("Tahoma")
                f.setPixelSize(max(1, int(round(hh * px_per_mm * 1.3))))
                f.setBold(bool(bold))
                fonts[key] = f
            return fonts[key]
        try:
            paint_sheet(p, sh, lambda x, y, h=h: QPointF(x * px_per_mm, (h - y) * px_per_mm),
                        px_per_mm, font)
        finally:
            p.end()
        out[name] = img
    return out


def save_html_pdf(doc, path: str):
    """A calculation sheet (HTML text or a QTextDocument) to an A4 PDF."""
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument
    wr = QPdfWriter(path)
    wr.setPageSize(QPageSize(QPageSize.A4))
    wr.setPageMargins(QMarginsF(18, 15, 15, 15), QPageLayout.Millimeter)
    wr.setResolution(150)
    if isinstance(doc, str):
        html, doc = doc, QTextDocument()
        doc.setHtml(html)
    doc.print_(wr)

class RoadSheetsDialog(QDialog):
    """Project data for the title column and the sheet families."""

    GROUPS = [("G", "G — ผังสังเขป ข้อมูลออกแบบ ตารางโค้งราบ/ดิ่ง หมุดหลักฐาน"),
              ("PP", "PP — แปลนและรูปตัดตามยาว พร้อมแถบระดับดิน/ออกแบบ/ขุด/ถม"),
              ("ST", "ST — รูปตัดขวางทุกสถานี พร้อมพื้นที่และปริมาตร"),
              ("VT", "VT — ตารางปริมาณดินขุด-ถมทุกสถานี"),
              ("SD", "SD — แบบมาตรฐานโครงสร้างทาง: รูปตัดชั้นทาง เหล็กเสริม/รอยต่อ รายการประกอบแบบ "
                     "รูปตัดดินตัด-ดินถม บัญชีปริมาณงาน"),
              ("DR", "DR — งานระบายน้ำ (ทถ-5): ท่อลอด คสล. ตำแหน่ง/ขนาด/ความยาว กำแพงปากท่อ รางระบายน้ำ"),
              ("TS", "TS — ป้ายและเครื่องหมายจราจร (ทถ-3): แผนผังป้าย หลัก กม. หลักนำโค้ง GUARD RAIL เส้นจราจร"),
              ("QS", "QS — สรุปปริมาณงานทั้งหมดของโครงการ (แผ่นสุดท้าย)")]

    def __init__(self, panel):
        super().__init__(panel)
        from PySide6.QtWidgets import QCheckBox
        self.setWindowTitle("แบบงานทาง A3 — WANIC ออกแบบถนน")
        f = QFormLayout(self)
        self.fields = {}
        for key, th, default in (("project", "ชื่อโครงการ", "งานออกแบบถนน"),
                                 ("owner", "เจ้าของงาน / หน่วยงาน", ""),
                                 ("location", "สถานที่", getattr(panel, "_place", "") or ""),
                                 ("office", "ชื่อสำนักงาน (หัวตาราง)", "WANICNSURVEY"),
                                 ("drawing_no", "เลขที่แบบ", "")):
            e = QLineEdit(default)
            if key == "location":
                e.setPlaceholderText("ต.… อ.… จ.… (ว่างไว้ = หาจากพิกัดให้เมื่อต่ออินเทอร์เน็ต)")
            self.fields[key] = e
            f.addRow(th, e)
        self.hscale = QComboBox()
        for v in (500, 1000, 2000):
            self.hscale.addItem(f"1:{v}", v)
        self.hscale.setCurrentIndex(1)
        f.addRow("มาตราส่วนราบ (แปลน/รูปตัดตามยาว)", self.hscale)
        self.checks = {}
        for g, th in self.GROUPS:
            c = QCheckBox(th)
            c.setChecked(True)
            self.checks[g] = c
            f.addRow(c)
        self.pipe = QComboBox()
        for d in (0.40, 0.60, 0.80, 1.00, 1.20, 1.50):
            self.pipe.addItem(f"ท่อลอด คสล. Ø {d:.2f} ม.", d)
        self.pipe.setCurrentIndex(1)
        self.pipe.setToolTip("DR: ขนาดท่อลอดที่จุดต่ำของพื้นดินตามแนวทาง (Ø 0.60 ม. ขนาดเล็กสุดที่ทำความสะอาดได้)")
        self.udrain = QComboBox()
        self.udrain.addItem("ไม่มีรางระบายน้ำ คสล.", "")
        for t in ("ก-30", "ข-30", "ค-30", "ง-30", "ก-50", "ข-50", "ค-50", "ง-50"):
            self.udrain.addItem(f"รางระบายน้ำ คสล. ย่านชุมชน แบบ {t} (ทถ-5-301) สองข้างทาง", t)
        row0 = QHBoxLayout()
        row0.addWidget(self.pipe)
        row0.addWidget(self.udrain, 1)
        f.addRow("งานระบายน้ำ (DR)", row0)
        self.speed = QComboBox()
        for v in (40, 50, 60, 70, 80, 90):
            self.speed.addItem(f"ความเร็วออกแบบ {v} กม./ชม.", v)
        self.speed.setCurrentIndex(2)
        self.urban = QCheckBox("ในเขตชุมชน (เส้นประ 1-3 ม.)")
        row1 = QHBoxLayout()
        row1.addWidget(self.speed)
        row1.addWidget(self.urban, 1)
        f.addRow("ป้าย/เครื่องหมาย (TS)", row1)
        self.site = QComboBox()
        for key, th in (("tiles", "แผนที่ตั้งโครงการ: ภาพถ่ายดาวเทียมดาวน์โหลดอัตโนมัติ (ต่ออินเทอร์เน็ต)"),
                        ("file", "แผนที่ตั้งโครงการ: ภาพที่บันทึกจาก Google Earth Pro…"),
                        ("none", "ไม่ใส่แผนที่ตั้งโครงการ")):
            self.site.addItem(th, key)
        self.site.setToolTip("แผ่นแรกของชุดแบบ: ภาพถ่ายดาวเทียม แนวทาง สถานี PI แผนที่บริเวณใกล้เคียง "
                             "และ ตำบล อำเภอ จังหวัด ที่ตั้งงาน")
        f.addRow(self.site)
        row = QHBoxLayout()
        self.site_file = QLineEdit()
        self.site_file.setPlaceholderText("ภาพ .jpg/.png — Google Earth Pro: เปิดแนวทางด้วยปุ่ม 🌏 "
                                          "แล้ว ไฟล์ ▸ บันทึก ▸ บันทึกภาพ…")
        row.addWidget(self.site_file, 1)
        b = QPushButton("เลือกภาพ…")
        b.clicked.connect(self._pick_image)
        row.addWidget(b)
        f.addRow(row)
        self.site_file.setEnabled(False)
        self.site.currentIndexChanged.connect(
            lambda _i: self.site_file.setEnabled(self.site.currentData() == "file"))
        self.pdf = QCheckBox("PDF")
        self.pdf.setChecked(True)
        self.paper = QComboBox()
        self.paper.addItem("PDF ขนาด A3 (แบบเต็มมาตราส่วน)", "A3")
        self.paper.addItem("PDF ขนาด A4 (ย่อทั้งแผ่นให้เห็นครบ — มาตราส่วน × 0.707)", "A4")
        self.paper.setToolTip("พิมพ์บนกระดาษ A4: ทั้งแผ่นแบบย่อลงพอดีหน้า ไม่มีส่วนใดถูกตัด "
                              "(มาตราส่วนที่เขียนในแบบคือของ A3)")
        self.dxf = QCheckBox("DXF ชุดแผ่นแบบ (ทุกแผ่นเรียงกัน)")
        self.dxf.setChecked(True)
        f.addRow(self.pdf, self.paper)
        f.addRow(self.dxf)
        row = QHBoxLayout()
        ok = QPushButton("📐 ส่งออก")
        ok.clicked.connect(self.accept)
        no = QPushButton("ยกเลิก")
        no.clicked.connect(self.reject)
        row.addStretch(1)
        row.addWidget(ok)
        row.addWidget(no)
        f.addRow(row)

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "ภาพจาก Google Earth Pro", "",
                                              "ภาพ (*.jpg *.jpeg *.png *.bmp)")
        if path:
            self.site_file.setText(path)
            self.site.setCurrentIndex(self.site.findData("file"))

    def info(self) -> dict:
        i = {k: e.text().strip() for k, e in self.fields.items()}
        i["site"] = self.site.currentData()
        i["site_file"] = self.site_file.text().strip()
        i["h_scale"] = self.hscale.currentData()
        i["groups"] = [g for g, c in self.checks.items() if c.isChecked()]
        i["pdf"] = self.pdf.isChecked()
        i["paper"] = self.paper.currentData() or "A3"
        ut = self.udrain.currentData() or ""
        i["drain"] = {"pipe_d": self.pipe.currentData(), "u_type": ut or None, "u_both": bool(ut)}
        i["signs"] = {"speed": self.speed.currentData(), "urban": self.urban.isChecked()}
        i["dxf"] = self.dxf.isChecked()
        return i


def _jpeg(img, quality: int = 88) -> bytes:
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    img.convertToFormat(QImage.Format_RGB32).save(buf, "JPEG", quality)
    buf.close()
    return bytes(data)


def stitch(view, tiles: dict):
    """The window of ``view`` (:class:`core.wanic_sitemap.View`) as one
    JPEG from its tiles; None without a single tile."""
    if not tiles:
        return None
    img = QImage(max(1, round(view.w_px)), max(1, round(view.h_px)), QImage.Format_RGB32)
    img.fill(QColor(226, 230, 222))
    p = QPainter(img)
    try:
        for (x, y), data in tiles.items():
            t = QImage.fromData(data)
            if t.isNull():
                continue
            dx, dy = view.tile_offset(x, y)
            p.drawImage(QPointF(dx, dy), t)
    finally:
        p.end()
    return _jpeg(img)


def setup(app) -> None:
    panel = RoadPanel(app)
    # the panel is taller than a laptop screen: it scrolls instead of squeezing
    scroll = QScrollArea()
    scroll.setWidget(panel)
    scroll.setWidgetResizable(True)
    dock = app.add_panel(TITLE, scroll)
    app.window._wanic_road = panel
    app.on_document_changed(lambda: QTimer.singleShot(0, lambda: _safe(panel, panel.load)))

    def show():
        app.show_panel(dock)
        dock.raise_()

    app.add_menu_action("WANIC ออกแบบถนน…", show,
                        tip="นำเข้าจุดสำรวจ วิเคราะห์รูปตัดตามยาว รูปตัดขวาง "
                            "ปริมาณดินตัด-ถม และสร้างโมเดลถนน 3 มิติ")
