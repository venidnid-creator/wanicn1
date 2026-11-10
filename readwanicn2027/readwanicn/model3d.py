# SPDX-License-Identifier: GPL-3.0-or-later
"""A 3D model to turn round: STL (binary or text) and OBJ files read into
triangles, drawn shaded with the painter's algorithm (no OpenGL needed,
so it opens on any office PC). Drag to rotate, wheel to zoom, right-drag
to pan."""
from __future__ import annotations

import math
import struct
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

MAX_TRIANGLES = 60_000


def load_stl(path) -> list:
    data = Path(path).read_bytes()
    if len(data) >= 84:
        n = struct.unpack_from("<I", data, 80)[0]
        if 84 + n * 50 == len(data):
            tris = []
            for i in range(n):
                v = struct.unpack_from("<12f", data, 84 + i * 50)
                tris.append(((v[3], v[4], v[5]), (v[6], v[7], v[8]), (v[9], v[10], v[11])))
            return tris
    pts, tris = [], []
    for line in data.decode("utf-8", "ignore").splitlines():
        line = line.strip()
        if line.startswith("vertex"):
            pts.append(tuple(float(x) for x in line.split()[1:4]))
            if len(pts) == 3:
                tris.append(tuple(pts))
                pts = []
    return tris


def load_obj(path) -> list:
    verts, tris = [], []
    for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "v":
            verts.append(tuple(float(x) for x in parts[1:4]))
        elif parts[0] == "f":
            idx = [int(p.split("/")[0]) for p in parts[1:]]
            idx = [i - 1 if i > 0 else len(verts) + i for i in idx]
            for k in range(1, len(idx) - 1):
                tris.append((verts[idx[0]], verts[idx[k]], verts[idx[k + 1]]))
    return tris


def load_model(path) -> list:
    ext = Path(path).suffix.lower()
    if ext == ".stl":
        return load_stl(path)
    if ext == ".obj":
        return load_obj(path)
    raise ValueError("รองรับไฟล์ .stl และ .obj")


def demo_house() -> list:
    """A small house (walls and a pitched roof) to show before a file is opened."""
    def quad(a, b, c, d):
        return [(a, b, c), (a, c, d)]
    w, d, h, r = 8.0, 6.0, 3.0, 5.0
    p = [(0, 0, 0), (w, 0, 0), (w, d, 0), (0, d, 0), (0, 0, h), (w, 0, h), (w, d, h), (0, d, h)]
    ridge = [(0, d / 2, r), (w, d / 2, r)]
    tris = []
    tris += quad(p[0], p[1], p[5], p[4]) + quad(p[1], p[2], p[6], p[5])
    tris += quad(p[2], p[3], p[7], p[6]) + quad(p[3], p[0], p[4], p[7])
    tris += quad(p[0], p[3], p[2], p[1])
    tris += quad(p[4], p[5], ridge[1], ridge[0]) + quad(p[6], p[7], ridge[0], ridge[1])
    tris += [(p[5], p[6], ridge[1]), (p[7], p[4], ridge[0])]
    return tris


class ModelView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.yaw, self.pitch, self.zoom = -35.0, 25.0, 1.0
        self.pan = QPointF(0, 0)
        self._last = None
        self.bg = QColor("#0B1F33")
        self.face = QColor("#C9D6E3")
        self.edge = QColor("#33506E")
        self.name = "บ้านตัวอย่าง"
        self.set_triangles(demo_house())

    def set_colors(self, bg: str, face: str, edge: str):
        self.bg, self.face, self.edge = QColor(bg), QColor(face), QColor(edge)
        self.update()

    def set_triangles(self, tris: list, name: str = ""):
        if len(tris) > MAX_TRIANGLES:
            step = math.ceil(len(tris) / MAX_TRIANGLES)
            tris = tris[::step]
        self.tris = tris
        if name:
            self.name = name
        pts = [v for t in tris for v in t] or [(0, 0, 0)]
        lo = [min(p[i] for p in pts) for i in range(3)]
        hi = [max(p[i] for p in pts) for i in range(3)]
        self.centre = [(a + b) / 2 for a, b in zip(lo, hi)]
        self.radius = max(1e-9, math.dist(lo, hi) / 2)
        self.update()

    def reset_view(self):
        self.yaw, self.pitch, self.zoom, self.pan = -35.0, 25.0, 1.0, QPointF(0, 0)
        self.update()

    def rotate(self, dyaw: float, dpitch: float = 0.0):
        self.yaw += dyaw
        self.pitch = max(-89.0, min(89.0, self.pitch + dpitch))
        self.update()

    # -- interaction
    def mousePressEvent(self, e):
        self._last = (e.position(), e.button())

    def mouseMoveEvent(self, e):
        if self._last is None:
            return
        pos, button = self._last
        d = e.position() - pos
        if button == Qt.RightButton:
            self.pan += d
        else:
            self.rotate(d.x() * 0.5, d.y() * 0.5)
        self._last = (e.position(), button)
        self.update()

    def mouseReleaseEvent(self, e):
        self._last = None

    def wheelEvent(self, e):
        self.zoom *= 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        self.update()

    # -- drawing
    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), self.bg)
        p.setRenderHint(QPainter.Antialiasing)
        cy, sy = math.cos(math.radians(self.yaw)), math.sin(math.radians(self.yaw))
        cp, sp = math.cos(math.radians(self.pitch)), math.sin(math.radians(self.pitch))
        scale = min(self.width(), self.height()) * 0.42 / self.radius * self.zoom
        ox, oy = self.width() / 2 + self.pan.x(), self.height() / 2 + self.pan.y()
        cx, cy0, cz = self.centre
        light = (0.35, -0.45, 0.82)

        def view(v):
            x, y, z = v[0] - cx, v[1] - cy0, v[2] - cz
            x1, y1 = x * cy - y * sy, x * sy + y * cy        # turn about Z (up)
            y2, z2 = y1 * cp - z * sp, y1 * sp + z * cp      # tilt about X
            return x1, y2, z2

        faces = []
        for t in self.tris:
            a, b, c = (view(v) for v in t)
            ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
            vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
            nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
            n = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            shade = abs(nx * light[0] + ny * light[1] + nz * light[2]) / n
            depth = (a[1] + b[1] + c[1]) / 3.0
            faces.append((depth, shade, a, b, c))
        faces.sort(key=lambda f: -f[0])                      # far first
        pen = QPen(self.edge, 0.6)
        for _d, shade, a, b, c in faces:
            k = 0.35 + 0.65 * shade
            col = QColor(int(self.face.red() * k), int(self.face.green() * k), int(self.face.blue() * k))
            poly = QPolygonF([QPointF(ox + v[0] * scale, oy - v[2] * scale) for v in (a, b, c)])
            p.setPen(pen)
            p.setBrush(col)
            p.drawPolygon(poly)
        p.setPen(QColor("#9FB3C8"))
        p.drawText(12, 22, f"{self.name} · {len(self.tris):,} สามเหลี่ยม · ลากเมาส์ซ้ายเพื่อหมุน "
                           "· ล้อเมาส์ย่อ/ขยาย · ลากขวาเพื่อเลื่อน")
