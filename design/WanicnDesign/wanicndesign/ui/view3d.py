# -*- coding: utf-8 -*-
"""A light 3D view of the frame, drawn with QPainter (no OpenGL needed).

Footings, columns, beams, slabs and the roof are boxes or polygons sorted
back to front. Drag to orbit, wheel to zoom. Colours follow the result
when there is one (red = fails).
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

COLOURS = {"footing": QColor("#c8a165"), "column": QColor("#a9a9a9"), "beam": QColor("#7f9fbf"),
           "slab": QColor(170, 200, 230, 150), "roof": QColor(190, 80, 60, 170),
           "ng": QColor("#d32f2f")}


def _box(x0, y0, z0, x1, y1, z1):
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    idx = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return [[v[k] for k in f] for f in idx]


def model_faces(b, res=None):
    """Faces as (points, colour) for the building, using designed sizes
    when a result is given."""
    faces = []
    xs, ys = b.xs, b.ys
    df = b.foundation.depth
    ng_beams = {(x.level, x.span) for x in res.beams if not x.ok} if res else set()
    beam_h = {(x.level, x.span): x.h for x in res.beams} if res else {}
    col = {}
    if res:
        for c in res.columns:
            col.setdefault(c.node, []).append(c)
    foot = {f.node: f for f in res.footings} if res else {}
    top = b.levels[-1].elevation if b.levels else 3.0
    for i, j in b.nodes():
        name = b.node_name(i, j)
        x, y = xs[i], ys[j]
        f = foot.get(name)
        fw, fl, ft = (f.width, f.length, f.thickness) if f else (0.6, 0.6, 0.4)
        for face in _box(x - fw / 2, y - fl / 2, -df, x + fw / 2, y + fl / 2, -df + ft):
            faces.append((face, COLOURS["footing"]))
        segs = col.get(name)
        if segs:
            for c in segs:
                ztop = next((lv.elevation for lv in b.levels if c.segment.endswith(lv.name)), top)
                colour = COLOURS["column"] if c.ok else COLOURS["ng"]
                for face in _box(x - c.b / 2, y - c.h / 2, ztop - c.height, x + c.b / 2, y + c.h / 2, ztop):
                    faces.append((face, colour))
        else:
            cw, cd = b.column_width, b.column_depth
            for face in _box(x - cw / 2, y - cd / 2, -df + ft, x + cw / 2, y + cd / 2, top):
                faces.append((face, COLOURS["column"]))
    for lv in b.levels:
        z = lv.elevation
        for _d, run in b.beam_lines(lv.name):
            for a, c in zip(run, run[1:]):
                span = f"{b.node_name(*a)}-{b.node_name(*c)}"
                h = beam_h.get((lv.name, span), lv.beam_depth)
                hw = lv.beam_width / 2
                (x0, y0), (x1, y1) = (xs[a[0]], ys[a[1]]), (xs[c[0]], ys[c[1]])
                if abs(y1 - y0) < 1e-9:
                    box = _box(x0, y0 - hw, z - h, x1, y0 + hw, z)
                else:
                    box = _box(x0 - hw, y0, z - h, x0 + hw, y1, z)
                colour = COLOURS["ng"] if (lv.name, span) in ng_beams else COLOURS["beam"]
                faces.extend((face, colour) for face in box)
        if lv.slab in ("suspended", "on_ground"):
            for i, j in b.panels(lv.name):
                faces.extend((face, COLOURS["slab"]) for face in
                             _box(xs[i], ys[j], z - lv.slab_thickness, xs[i + 1], ys[j + 1], z))
        if lv.slab == "roof":
            faces.extend(_roof_faces(b, z))
    return faces


def _roof_faces(b, z):
    r = b.roof
    e = r.overhang
    x0, y0, x1, y1 = -e, -e, b.xs[-1] + e, b.ys[-1] + e
    w, d = x1 - x0, y1 - y0
    t = math.tan(math.radians(r.slope_deg))
    c = QColor(COLOURS["roof"])
    if r.shape == "gable":
        if w >= d:
            rise, ym = d / 2 * t, (y0 + y1) / 2
            return [([(x0, y0, z), (x1, y0, z), (x1, ym, z + rise), (x0, ym, z + rise)], c),
                    ([(x0, y1, z), (x0, ym, z + rise), (x1, ym, z + rise), (x1, y1, z)], c)]
        rise, xm = w / 2 * t, (x0 + x1) / 2
        return [([(x0, y0, z), (xm, y0, z + rise), (xm, y1, z + rise), (x0, y1, z)], c),
                ([(x1, y0, z), (x1, y1, z), (xm, y1, z + rise), (xm, y0, z + rise)], c)]
    half = min(w, d) / 2
    rise = half * t
    if w >= d:
        ra, rb = (x0 + half, (y0 + y1) / 2, z + rise), (x1 - half, (y0 + y1) / 2, z + rise)
    else:
        ra, rb = ((x0 + x1) / 2, y0 + half, z + rise), ((x0 + x1) / 2, y1 - half, z + rise)
    p00, p10, p11, p01 = (x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)
    if w >= d:
        return [([p00, p10, rb, ra], c), ([p11, p01, ra, rb], c), ([p01, p00, ra], c), ([p10, p11, rb], c)]
    return [([p10, p11, rb, ra], c), ([p01, p00, ra, rb], c), ([p00, p10, ra], c), ([p11, p01, rb], c)]


class View3D(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 240)
        self.yaw, self.pitch, self.zoom = -35.0, 28.0, 1.0
        self.building = None
        self.result = None
        self._faces = []
        self._drag = None

    def set_model(self, building, result=None):
        self.building, self.result = building, result
        self._faces = model_faces(building, result) if building else []
        self.update()

    def _project(self, p, cx, cy, cz, scale):
        x, y, z = p[0] - cx, p[1] - cy, p[2] - cz
        a, e = math.radians(self.yaw), math.radians(self.pitch)
        x1 = x * math.cos(a) - y * math.sin(a)
        y1 = x * math.sin(a) + y * math.cos(a)
        y2 = y1 * math.cos(e) - z * math.sin(e)      # depth (into the screen)
        z2 = y1 * math.sin(e) + z * math.cos(e)
        return QPointF(self.width() / 2 + x1 * scale, self.height() / 2 - z2 * scale), y2

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#eef1f4"))
        b = self.building
        if not b or not self._faces:
            p.drawText(self.rect(), Qt.AlignCenter, "ยังไม่มีโมเดล")
            return
        cx, cy = b.xs[-1] / 2, b.ys[-1] / 2
        top = b.levels[-1].elevation if b.levels else 3.0
        cz = (top - b.foundation.depth) / 2
        span = max(b.xs[-1], b.ys[-1], top + b.foundation.depth) or 1.0
        scale = 0.75 * min(self.width(), self.height()) / span * self.zoom
        drawn = []
        for pts, colour in self._faces:
            proj = [self._project(q, cx, cy, cz, scale) for q in pts]
            depth = sum(d for _q, d in proj) / len(proj)
            drawn.append((depth, [q for q, _d in proj], colour, pts))
        drawn.sort(key=lambda t: -t[0])
        edge = QPen(QColor(60, 60, 60, 120), 0.6)
        for _d, poly, colour, pts in drawn:
            shade = _shade(pts)
            c = QColor(colour)
            c.setRed(int(c.red() * shade))
            c.setGreen(int(c.green() * shade))
            c.setBlue(int(c.blue() * shade))
            p.setPen(edge)
            p.setBrush(QBrush(c))
            p.drawPolygon(QPolygonF(poly))
        p.setPen(QColor("#555"))
        p.drawText(8, self.height() - 8, "ลากเมาส์เพื่อหมุน • ล้อเมาส์เพื่อซูม")

    def mousePressEvent(self, e):
        self._drag = e.position()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            d = e.position() - self._drag
            self.yaw += d.x() * 0.4
            self.pitch = max(-5.0, min(85.0, self.pitch + d.y() * 0.4))
            self._drag = e.position()
            self.update()

    def mouseReleaseEvent(self, _e):
        self._drag = None

    def wheelEvent(self, e):
        self.zoom *= 1.1 if e.angleDelta().y() > 0 else 1 / 1.1
        self.update()


def _shade(pts) -> float:
    """Simple light: faces turned up are brightest."""
    if len(pts) < 3:
        return 1.0
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = pts[0], pts[1], pts[2]
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    n = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    light = (0.3, -0.5, 0.8)
    dot = abs((nx * light[0] + ny * light[1] + nz * light[2]) / n)
    return 0.55 + 0.45 * dot
