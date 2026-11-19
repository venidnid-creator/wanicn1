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
           "stair": QColor("#b39b7d"), "ng": QColor("#d32f2f")}


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
    foot = {}
    for f in (res.footings if res else []):
        for n in (f.nodes or [f.node]):
            foot[n] = f
        if f.cx is not None:
            faces.extend((face, COLOURS["footing"]) for face in _box(
                f.cx - f.width / 2, f.cy - f.length / 2, -b.foundation.depth,
                f.cx + f.width / 2, f.cy + f.length / 2, -b.foundation.depth + f.thickness))
    top = b.levels[-1].elevation if b.levels else 3.0
    for i, j in b.nodes():
        name = b.node_name(i, j)
        x, y = xs[i], ys[j]
        f = foot.get(name)
        fw, fl, ft = (f.width, f.length, f.thickness) if f else (0.6, 0.6, 0.4)
        if f is None or f.cx is None:
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
    if res:
        lv_z = {lv.name: lv.elevation for lv in b.levels}
        for x in res.beams:
            x0, y0, x1, y1 = x.line_xy
            z, hw = (x.z_top if x.z_top is not None else lv_z[x.level]), x.b / 2
            box = _box(min(x0, x1), y0 - hw, z - x.h, max(x0, x1), y0 + hw, z) if abs(y1 - y0) < 1e-9 else \
                _box(x0 - hw, min(y0, y1), z - x.h, x0 + hw, max(y0, y1), z)
            colour = COLOURS["beam"] if x.ok else COLOURS["ng"]
            faces.extend((face, colour) for face in box)
        for s in res.slabs:
            x0, y0, x1, y1 = s.rect
            z = lv_z[s.level]
            colour = COLOURS["slab"] if s.ok else COLOURS["ng"]
            faces.extend((face, colour) for face in _box(x0, y0, z - s.thickness, x1, y1, z))
        for st in res.stairs:
            if st.geom is not None:
                faces.extend(_stair_faces(b, st.geom, st.kind, st.thickness,
                                          COLOURS["stair"] if st.ok else COLOURS["ng"]))
        for lv in b.levels:
            if lv.slab == "roof":
                faces.extend(_roof_faces(b, lv.elevation))
        for t in res.trusses:
            faces.extend(_truss_faces(b, t, lv_z[b.levels[-1].name]))
        return faces
    for lv in b.levels:
        z = lv.elevation
        hw = lv.beam_width / 2
        for _d, run in b.beam_lines(lv.name):
            for a, c in zip(run, run[1:]):
                (x0, y0), (x1, y1) = (xs[a[0]], ys[a[1]]), (xs[c[0]], ys[c[1]])
                box = _box(x0, y0 - hw, z - lv.beam_depth, x1, y0 + hw, z) if abs(y1 - y0) < 1e-9 else \
                    _box(x0 - hw, y0, z - lv.beam_depth, x0 + hw, y1, z)
                faces.extend((face, COLOURS["beam"]) for face in box)
        if lv.slab in ("suspended", "precast", "on_ground", "deck"):
            from ..structure.design import slab_parts
            for i, j in b.panels(lv.name):
                for _n, x0, y0, x1, y1, _f in slab_parts(b, lv, i, j):
                    faces.extend((face, COLOURS["slab"]) for face in
                                 _box(x0, y0, z - lv.slab_thickness, x1, y1, z))
                sub = b.sub_beam(lv, i, j)
                if sub:
                    d, f = sub
                    if d == "x":
                        yy = ys[j] + f * (ys[j + 1] - ys[j])
                        box = _box(xs[i], yy - hw, z - lv.beam_depth, xs[i + 1], yy + hw, z)
                    else:
                        xx = xs[i] + f * (xs[i + 1] - xs[i])
                        box = _box(xx - hw, ys[j], z - lv.beam_depth, xx + hw, ys[j + 1], z)
                    faces.extend((face, COLOURS["beam"]) for face in box)
        if lv.slab in ("suspended", "deck"):
            for a, c, length, (dx, dy) in b.cantilevers(lv):
                (x0, y0), (x1, y1) = (xs[a[0]], ys[a[1]]), (xs[c[0]], ys[c[1]])
                faces.extend((face, COLOURS["slab"]) for face in _box(
                    min(x0, x1, x0 + dx * length), min(y0, y1, y0 + dy * length), z - lv.slab_thickness,
                    max(x0, x1, x0 + dx * length), max(y0, y1, y0 + dy * length), z))
        for node, (dx, dy), length, _p, _w in b.cant_beams(lv):
            x0, y0 = xs[node[0]], ys[node[1]]
            x1, y1 = x0 + dx * length, y0 + dy * length
            box = _box(min(x0, x1), y0 - hw, z - lv.beam_depth, max(x0, x1), y0 + hw, z) if dx else \
                _box(x0 - hw, min(y0, y1), z - lv.beam_depth, x0 + hw, max(y0, y1), z)
            faces.extend((face, COLOURS["beam"]) for face in box)
        if lv.slab == "roof":
            faces.extend(_roof_faces(b, z))
    from ..structure.stairs import geometry
    for st in b.stairs:
        g = geometry(b, st)
        if g is not None:
            faces.extend(_stair_faces(b, g, st.kind, st.thickness, COLOURS["stair"]))
    return faces


def _stair_faces(b, g, kind, t, colour):
    from ..structure.stairs import flight_surfaces
    out = []
    for quad in flight_surfaces(b, g, kind):
        out.append((quad, colour))
        out.append(([(x, y, z - t) for x, y, z in reversed(quad)], colour))
    return out


def _roof_faces(b, z):
    from ..structure.roofs import faces
    c = QColor(COLOURS["roof"])
    return [(f, c) for f in faces(b, z)]


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
        top = max(q[2] for pts, _c in self._faces for q in pts)          # includes the roof
        cz = (top - b.foundation.depth) / 2
        # fit the projected model (roof included) into the widget
        unit = [self._project(q, cx, cy, cz, 1.0)[0] for pts, _c in self._faces for q in pts]
        xs = [q.x() - self.width() / 2 for q in unit]
        ys = [q.y() - self.height() / 2 for q in unit]
        bw, bh = (max(xs) - min(xs)) or 1.0, (max(ys) - min(ys)) or 1.0
        scale = 0.88 * min(self.width() / bw, (self.height() - 24) / bh) * self.zoom
        off = QPointF(-(max(xs) + min(xs)) / 2 * scale, -(max(ys) + min(ys)) / 2 * scale - 8)
        drawn = []
        for pts, colour in self._faces:
            proj = [(q + off, d) for q, d in (self._project(v, cx, cy, cz, scale) for v in pts)]
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


def _truss_faces(b, t, z0):
    """Truss members as thin boxes standing on the grid line of the truss."""
    (i0, j0), (i1, j1) = t.supports
    x0, y0, x1, y1 = b.xs[i0], b.ys[j0], b.xs[i1], b.ys[j1]
    ux, uy = (x1 - x0) / t.span, (y1 - y0) / t.span
    out = []
    c = QColor("#5d6d7e")
    for m in t.members:
        (a, za), (e, ze) = t.nodes[m.i], t.nodes[m.j]
        p0 = (x0 + ux * a, y0 + uy * a, z0 + za)
        p1 = (x0 + ux * e, y0 + uy * e, z0 + ze)
        w = 0.03
        nx, ny = -uy * w, ux * w
        out.append(([(p0[0] - nx, p0[1] - ny, p0[2]), (p1[0] - nx, p1[1] - ny, p1[2]),
                     (p1[0] + nx, p1[1] + ny, p1[2]), (p0[0] + nx, p0[1] + ny, p0[2])], c))
    return out
