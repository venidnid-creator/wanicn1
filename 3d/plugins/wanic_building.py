# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
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

from core.wanic_ui import safe as _safe

import copy
import os

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMenu, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from core import wanic_building as B
from core import wanic_catalog as CAT
from core.wanic_sign import label_html

TITLE = "ออกแบบอาคาร"
NAVY = QColor("#0F2A44")
ROOM = QColor(64, 170, 110, 70)
ROOM_EDGE = QColor(30, 120, 70)
SEL = QColor("#E8772E")
GHOST = QColor(120, 130, 140, 60)
FOOT = QColor(150, 120, 210, 90)
FOOT_EDGE = QColor(120, 90, 190)
AXIS = QColor(90, 120, 160)
AXIS_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"


def fixture_size(fx) -> tuple[float, float]:
    spec = CAT.SANITARY.get(fx.get("type"))
    w, d = (spec[3], spec[4]) if spec else (0.4, 0.4)
    return (d, w) if int(fx.get("dir", 0)) % 2 else (w, d)


def axis_name(i: int) -> str:
    """A, B, … Z, AA, AB … (I and O skipped, as on drawings)."""
    n = len(AXIS_LETTERS)
    out = ""
    i += 1
    while i > 0:
        i, r = divmod(i - 1, n)
        out = AXIS_LETTERS[r] + out
    return out


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
        self.selected = None                    # room / item id
        self.multi: set = set()                 # several selected rooms
        self._drag = None                       # ("rooms", …) or ("stair", …)
        self._band = None                       # rubber band (start, now)
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
    def is_selected(self, rid) -> bool:
        return rid == self.selected or rid in self.multi

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#FBFAF6"))
        data = self.panel.data()
        st = B.settings_of(data)
        lib = B.library_of(data)
        grid = float(st.get("grid", 0.5)) or 0.5
        x0, y1 = self.to_world(QPointF(0, 0))
        x1, y0 = self.to_world(QPointF(self.width(), self.height()))
        step = grid
        while step * self.scale < 8:
            step *= 2
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
        rooms = self.rooms()
        self._paint_axes(p, rooms)

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
        # Footings under the ground floor (purple, sized by their mark).
        if self.panel.floor == 0 and self.panel.show_footings():
            for x, y in B.nodes(rooms):
                fm = B.node_mark(data, lib, x, y, "F")
                fw, fl = float(lib[fm]["w"]), float(lib[fm]["l"])
                q = self.to_screen(x, y)
                r = QRectF(q.x() - fw * self.scale / 2,
                           q.y() - fl * self.scale / 2,
                           fw * self.scale, fl * self.scale)
                p.setPen(QPen(FOOT_EDGE, 1))
                p.setBrush(FOOT)
                p.drawRect(r)
                if self.scale >= 25:
                    p.setPen(FOOT_EDGE)
                    cm = B.node_mark(data, lib, x, y, "C")
                    p.drawText(r.topRight() + QPointF(2, 10), f"{fm}/{cm}")
        for rm in rooms:
            r = rect_of(rm)
            sel = self.is_selected(rm["id"])
            p.setPen(QPen(SEL if sel else ROOM_EDGE, 2.5 if sel else 1.5))
            p.setBrush(QColor(232, 119, 46, 40) if sel else ROOM)
            p.drawRect(r)
            p.setPen(NAVY)
            mark = B.slab_mark(lib, rm, self.panel.floor)
            p.drawText(r, Qt.AlignCenter,
                       f"{rm.get('name', '')}\n{rm['w']:g} × {rm['d']:g} ม."
                       f"\n{mark}")
        # Stairs: the flight's outline, its treads and the way up.
        for stp in self.panel.items("stairs"):
            pts = [self.to_screen(*q) for q in B.stair_rect(stp, st)]
            sel = stp["id"] == self.selected
            p.setPen(QPen(SEL if sel else NAVY, 2 if sel else 1.2))
            p.setBrush(QColor(255, 255, 255, 200))
            p.drawPolygon(QPolygonF(pts))
            n, _L, _H = B.stair_geometry(stp, st)
            a, b, c, d = pts
            for i in range(1, n):
                t = i / n
                p.drawLine(a + (b - a) * t, d + (c - d) * t)
            mid0 = (a + d) / 2
            mid1 = (b + c) / 2
            p.setPen(QPen(QColor("#B01E33"), 1.6))
            p.drawLine(mid0, mid1)
            p.drawText(mid1 + QPointF(4, -4), "ขึ้น")
        # Doors and windows on the walls.
        segs = B.segments(rooms)
        for op in self.panel.items("openings"):
            w, _h, _sill = B.opening_size(op, st)
            hit = B.snap_to_segment(op["x"], op["y"], segs, 0.1)
            if hit is None:
                continue
            (p0, p1) = hit[2]
            L = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) or 1.0
            ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
            a = self.to_screen(op["x"] - ux * w / 2, op["y"] - uy * w / 2)
            b = self.to_screen(op["x"] + ux * w / 2, op["y"] + uy * w / 2)
            sel = op["id"] == self.selected
            color = QColor("#3BA3D8") if op.get("type") == "window" \
                else QColor("#E8772E")
            p.setPen(QPen(SEL if sel else color,
                          max(5.0, st["wall_t"] * self.scale * 1.6),
                          Qt.SolidLine, Qt.FlatCap))
            p.drawLine(a, b)
            if self.scale >= 20:
                code, _spec = CAT.opening_type(op)
                p.setPen(QColor("#5A3A00") if op.get("type") != "window"
                         else QColor("#0B4F75"))
                mid = (a + b) / 2
                p.drawText(mid + QPointF(4, -6), code)
        # Sanitary ware.
        for fx in self.panel.items("fixtures"):
            w, d = fixture_size(fx)
            q = self.to_screen(fx["x"], fx["y"])
            r = QRectF(q.x() - w * self.scale / 2, q.y() - d * self.scale / 2,
                       max(w * self.scale, 4), max(d * self.scale, 4))
            sel = fx["id"] == self.selected
            p.setPen(QPen(SEL if sel else QColor("#2F6C8F"), 1.4))
            p.setBrush(QColor(255, 255, 255, 230))
            if fx.get("type", "").startswith(("WC", "LV", "BT", "SK")):
                p.drawRoundedRect(r, 3, 3)
            else:
                p.drawRect(r)
            if self.scale >= 25:
                p.drawText(r.bottomLeft() + QPointF(0, 10), fx.get("type", ""))
        # Columns where the build will put them, sized by their mark.
        p.setPen(Qt.NoPen)
        for x, y in B.nodes(rooms):
            cm = lib[B.node_mark(data, lib, x, y, "C")]
            cw = max(4.0, float(cm["b"]) * self.scale)
            ch = max(4.0, float(cm["h"]) * self.scale)
            q = self.to_screen(x, y)
            p.setBrush(SEL if self.selected == B.node_key(x, y) else NAVY)
            p.drawRect(QRectF(q.x() - cw / 2, q.y() - ch / 2, cw, ch))
        if self._band is not None:
            a, b = self._band
            p.setPen(QPen(QColor("#3B6FB6"), 1, Qt.DashLine))
            p.setBrush(QColor(59, 111, 182, 30))
            p.drawRect(QRectF(a, b).normalized())
        if self._hover is not None:
            p.setPen(QColor(85, 101, 122))
            extra = f" · เลือก {len(self.multi)} ห้อง" if self.multi else ""
            p.drawText(QPointF(6, self.height() - 6),
                       f"X {self._hover[0]:.2f} · Y {self._hover[1]:.2f} ม. · "
                       f"ชั้น {self.panel.floor + 1}{extra}")
        p.end()

    def _paint_axes(self, p, rooms):
        """Grid lines 1, 2, 3 … / A, B, C … through the column lines, with
        the spacing between them written along the top and the left."""
        pts = B.nodes(rooms)
        if not pts:
            return
        xs = sorted({x for x, _y in pts})
        ys = sorted({y for _x, y in pts}, reverse=True)
        f = QFont(self.font())
        f.setPointSizeF(8.0)
        p.setFont(f)
        top, left = 18.0, 24.0
        p.setPen(QPen(AXIS, 1, Qt.DashDotLine))
        for i, x in enumerate(xs):
            sx = self.to_screen(x, 0).x()
            p.drawLine(QPointF(sx, top + 14), QPointF(sx, self.height()))
        for j, y in enumerate(ys):
            sy = self.to_screen(0, y).y()
            p.drawLine(QPointF(left + 14, sy), QPointF(self.width(), sy))
        p.setPen(QPen(AXIS, 1))
        p.setBrush(QColor("#FFFFFF"))
        for i, x in enumerate(xs):
            sx = self.to_screen(x, 0).x()
            p.drawEllipse(QPointF(sx, top), 8, 8)
            p.drawText(QRectF(sx - 8, top - 8, 16, 16), Qt.AlignCenter,
                       str(i + 1))
            if i:
                px = self.to_screen(xs[i - 1], 0).x()
                p.drawText(QRectF(px, top + 10, sx - px, 14), Qt.AlignCenter,
                           f"{x - xs[i - 1]:.2f} m")
        for j, y in enumerate(ys):
            sy = self.to_screen(0, y).y()
            p.drawEllipse(QPointF(left, sy), 8, 8)
            p.drawText(QRectF(left - 8, sy - 8, 16, 16), Qt.AlignCenter,
                       axis_name(j))
            if j:
                py = self.to_screen(0, ys[j - 1]).y()
                p.save()
                p.translate(left + 18, (py + sy) / 2)
                p.rotate(-90)
                p.drawText(QRectF(-30, -7, 60, 14), Qt.AlignCenter,
                           f"{ys[j - 1] - y:.2f} m")
                p.restore()

    # ---- mouse ----------------------------------------------------------------
    def mousePressEvent(self, ev):
        x, y = self.to_world(ev.position())
        if ev.button() == Qt.MiddleButton:
            self._pan = (ev.position(), QPointF(self.origin))
            return
        rm = self.room_at(x, y)
        item = self.panel.item_at(x, y)
        node = self.panel.node_at(x, y)
        tool = self.panel.tool()
        ctrl = bool(ev.modifiers() & Qt.ControlModifier)
        if ev.button() == Qt.RightButton:
            if item is not None:
                self.selected = item["id"]
                self.update()
                self._item_menu(item, ev.globalPosition().toPoint())
            elif node is not None and (tool == "node" or rm is None):
                self.selected = B.node_key(*node)
                self.update()
                self._node_menu(node, ev.globalPosition().toPoint())
            elif rm is not None:
                if not self.is_selected(rm["id"]):
                    self.multi = set()
                self.selected = rm["id"]
                self.update()
                self._menu(rm, ev.globalPosition().toPoint())
            return
        if ev.button() != Qt.LeftButton:
            return
        if tool == "node":
            if node is not None:
                self.selected = B.node_key(*node)
                self.update()
                self.panel.edit_node(node)
            return
        if tool == "fixture" and item is None:
            self.selected = self.panel.place_fixture(x, y)
            self.update()
            return
        if item is not None and item["id"].startswith(("s", "x")):
            self.selected = item["id"]
            self._drag = ("stair", item["id"], x - item["x"], y - item["y"])
            self.update()
            return
        if tool in ("door", "window"):
            got = self.panel.place_opening(x, y, tool)
            if got:
                self.selected = got
            self.update()
            return
        if tool == "stair":
            self.selected = self.panel.place_stair(x, y)
            self.update()
            return
        if item is not None:
            self.selected = item["id"]
        elif rm is not None:
            if ctrl:                                # toggle in the selection
                ids = self.multi | ({self.selected} if self.selected and
                                    self.selected.startswith("r") else set())
                ids ^= {rm["id"]}
                self.multi = ids
                self.selected = rm["id"] if rm["id"] in ids else None
                self.update()
                return
            if rm["id"] not in self.multi:
                self.multi = set()
            self.selected = rm["id"]
            ids = self.multi | {rm["id"]}
            self._drag = ("rooms", rm["id"], ids, (x, y),
                          copy.deepcopy(self.rooms()))
            self._moved = None
        elif tool == "select" or ctrl:
            self.selected = None
            self.multi = set()
            self._band = (ev.position(), ev.position())
        else:
            self.multi = set()
            self.selected = self.panel.place_room(x, y)
        self.update()

    def mouseMoveEvent(self, ev):
        x, y = self.to_world(ev.position())
        self._hover = (x, y)
        if self._pan is not None:
            start, org = self._pan
            self.origin = org + (ev.position() - start)
        elif self._band is not None:
            self._band = (self._band[0], ev.position())
        elif self._drag is not None and self._drag[0] == "stair":
            _k, sid, dx, dy = self._drag
            g = float(B.settings_of(self.panel.data())["grid"]) or 0.5
            step = 0.05 if sid.startswith("x") else g / 2
            nx = round((x - dx) / step) * step
            ny = round((y - dy) / step) * step
            self.panel.preview_stair(sid, nx, ny)
        elif self._drag is not None:
            _k, anchor, ids, (sx, sy), rooms = self._drag
            orig = {r["id"]: (r["x"], r["y"]) for r in rooms}
            a = next(r for r in rooms if r["id"] == anchor)
            ax, ay = orig[anchor]
            others = [r for r in self.panel.rooms() if r["id"] not in ids]
            grid = B.settings_of(self.panel.data())["grid"]
            moved = dict(a, x=ax + x - sx, y=ay + y - sy)
            snapped = B.snap_room(moved, others, grid)
            dx, dy = snapped["x"] - ax, snapped["y"] - ay
            out = []
            for r in rooms:
                if r["id"] in ids:
                    ox, oy = orig[r["id"]]
                    r = dict(r, x=B._r(ox + dx), y=B._r(oy + dy))
                out.append(r)
            self._drag = ("rooms", anchor, ids, (sx, sy), rooms)
            self._moved = out
            self.panel.preview_rooms(out)
        self.update()

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MiddleButton:
            self._pan = None
            return
        if self._band is not None:
            a, b = self._band
            self._band = None
            ax, ay = self.to_world(a)
            bx, by = self.to_world(b)
            lo_x, hi_x = sorted((ax, bx))
            lo_y, hi_y = sorted((ay, by))
            self.multi = {rm["id"] for rm in self.rooms()
                          if rm["x"] < hi_x and rm["x"] + rm["w"] > lo_x
                          and rm["y"] < hi_y and rm["y"] + rm["d"] > lo_y}
            self.selected = next(iter(self.multi), None)
            self.update()
            return
        if self._drag is not None and self._drag[0] == "stair":
            self._drag = None
            self.panel.commit_stair()
        elif self._drag is not None:
            moved = getattr(self, "_moved", None)
            self._drag = None
            self._moved = None
            if moved is not None:
                self.panel.set_rooms(moved)
            else:
                self.panel.preview_rooms(None)

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.RightButton:          # cancel: back to select
            self.panel.set_tool("select")
            self.selected = None
            self.multi = set()
            self.update()
            return
        x, y = self.to_world(ev.position())
        item = self.panel.item_at(x, y)
        if item is not None:
            self.panel.edit_item(item["id"])
            return
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

    def selected_rooms(self) -> set:
        ids = set(self.multi)
        if self.selected and self.selected.startswith("r"):
            ids.add(self.selected)
        return ids

    def keyPressEvent(self, ev):
        sel = self.selected or ""
        ctrl = bool(ev.modifiers() & Qt.ControlModifier)
        key = ev.key()
        if ctrl and key == Qt.Key_Z:
            self.panel.undo()
        elif ctrl and key == Qt.Key_Y:
            self.panel.redo()
        elif ctrl and key == Qt.Key_C:
            self.panel.copy_rooms(self.selected_rooms())
        elif ctrl and key == Qt.Key_V:
            got = self.panel.paste_rooms(self._hover)
            if got:
                self.multi, self.selected = set(got), got[0]
        elif ctrl and key == Qt.Key_A:
            self.multi = {rm["id"] for rm in self.rooms()}
        elif key == Qt.Key_Escape:
            self.selected, self.multi = None, set()
            self.panel.set_tool("select")
        elif key in (Qt.Key_Delete, Qt.Key_Backspace) and (sel or self.multi):
            rooms = self.selected_rooms()
            if rooms:
                self.panel.delete_rooms(rooms)
            elif sel and not sel.startswith("N:"):
                self.panel.delete_item(sel)
            self.selected, self.multi = None, set()
        elif key == Qt.Key_R and sel:
            if sel.startswith("r"):
                self.panel.rotate_room(sel)
            elif sel.startswith(("s", "x")):
                self.panel.rotate_stair(sel)
        else:
            super().keyPressEvent(ev)
            return
        self.update()

    def _menu(self, rm, at):
        m = QMenu(self)
        ids = self.selected_rooms() or {rm["id"]}
        m.addAction("แก้ไขชื่อ/ขนาด/เบอร์พื้น…",
                    lambda: self.panel.edit_room(rm["id"]))
        m.addAction("หมุน 90° (R)", lambda: self.panel.rotate_room(rm["id"]))
        m.addAction("ทำสำเนา", lambda: self.panel.duplicate_room(rm["id"]))
        m.addAction(f"คัดลอก {len(ids)} ห้อง (Ctrl+C)",
                    lambda: self.panel.copy_rooms(ids))
        m.addSeparator()
        m.addAction(f"ลบ {len(ids)} ห้อง (Delete)",
                    lambda: self.panel.delete_rooms(ids))
        m.exec(at)

    def _node_menu(self, node, at):
        m = QMenu(self)
        m.addAction("กำหนดเบอร์ฐานราก / ตอม่อ / เสา…",
                    lambda: self.panel.edit_node(node))
        m.addAction("กลับเป็นค่าเริ่มต้น (F1 / PC1 / C1)",
                    lambda: self.panel.reset_node(node))
        m.exec(at)

    def _item_menu(self, item, at):
        m = QMenu(self)
        m.addAction("แก้ไขขนาด…", lambda: self.panel.edit_item(item["id"]))
        if item["id"].startswith(("s", "x")):
            m.addAction("หมุน 90° (R)", lambda: self.panel.rotate_stair(item["id"]))
        m.addSeparator()
        m.addAction("ลบ (Delete)", lambda: self.panel.delete_item(item["id"]))
        m.exec(at)


class ItemDialog(QDialog):
    """Size of a door, window or stair (blank = the panel's default)."""

    def __init__(self, item, s, parent=None):
        super().__init__(parent)
        f = QFormLayout(self)
        self.fields = {}
        self.choice = None
        if item["id"].startswith("x"):
            self.setWindowTitle("แก้ไขสุขภัณฑ์")
            self.choice = ("type", QComboBox())
            for code, spec in CAT.SANITARY.items():
                self.choice[1].addItem(f"{code} — {spec[0]}", code)
            self.choice[1].setCurrentIndex(max(
                self.choice[1].findData(item.get("type")), 0))
            f.addRow("ชนิด", self.choice[1])
            rows = []
        elif item["id"].startswith("s"):
            self.setWindowTitle("แก้ไขบันได")
            rows = [("w", "ความกว้างบันได", s["stair_w"])]
        else:
            win = item.get("type") == "window"
            self.setWindowTitle("แก้ไขหน้าต่าง" if win else "แก้ไขประตู")
            code, _spec = CAT.opening_type(item)
            self.choice = ("style", QComboBox())
            for c, spec in CAT.types_of("window" if win else "door"):
                self.choice[1].addItem(f"{c} — {spec['name']}", c)
            self.choice[1].setCurrentIndex(max(self.choice[1].findData(code),
                                               0))
            f.addRow("แบบ", self.choice[1])
            w, h, sill = B.opening_size(item, s)
            rows = [("w", "กว้าง", w), ("h", "สูง", h)]
            if win:
                rows.append(("sill", "ความสูงขอบล่าง", sill))
        for k, label, v in rows:
            sp = _spin(0.0 if k == "sill" else 0.3, 10.0,
                       float(item.get(k) if item.get(k) is not None else v))
            self.fields[k] = sp
            f.addRow(label, sp)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)


class RoomDialog(QDialog):
    def __init__(self, room, parent=None, slabs=()):
        super().__init__(parent)
        self.setWindowTitle("แก้ไขห้อง")
        f = QFormLayout(self)
        self.name = QComboBox()
        self.name.setEditable(True)
        self.name.addItems(B.ROOM_TYPES)
        self.name.setCurrentText(room.get("name", ""))
        self.w = QDoubleSpinBox()
        self.d = QDoubleSpinBox()
        for sp, v in ((self.w, room["w"]), (self.d, room["d"])):
            sp.setRange(0.5, 100.0)
            sp.setDecimals(2)
            sp.setSingleStep(0.5)
            sp.setSuffix(" ม.")
            sp.setValue(float(v))
        self.slab = QComboBox()
        self.slab.addItem("ตามชั้น (S1 ชั้นล่าง / S2 ชั้นบน)", "")
        for m in slabs:
            self.slab.addItem(m, m)
        self.slab.setCurrentIndex(max(self.slab.findData(room.get("slab", "")),
                                      0))
        f.addRow("ชื่อ/ประเภทห้อง", self.name)
        f.addRow("กว้าง X", self.w)
        f.addRow("ลึก Y", self.d)
        f.addRow("เบอร์พื้น", self.slab)
        # Finishes (default: by room type — ห้องน้ำ gets tiles to 2.00 m).
        from core import wanic_recipes2569 as RC
        own = room.get("finish") or {}
        fin = CAT.finish_of(room)
        self.floor_fin = QComboBox()
        self.floor_fin.addItem("ตามประเภทห้อง", None)
        self.tile = QComboBox()
        self.tile.addItem("ตามประเภทห้อง", None)
        self.tile.addItem("ไม่บุกระเบื้อง", "")
        for rc in RC.RECIPES:
            if rc["code"].startswith("9.") and rc["items"]:
                self.floor_fin.addItem(f"{rc['code']} {rc['name'][:60]}",
                                       rc["code"])
            if rc["code"].startswith("7.") and "บุ" in rc["name"] and \
                    rc["items"]:
                self.tile.addItem(f"{rc['code']} {rc['name'][:60]}",
                                  rc["code"])
        self.floor_fin.setCurrentIndex(max(self.floor_fin.findData(
            own.get("floor")), 0) if "floor" in own else 0)
        self.tile.setCurrentIndex(max(self.tile.findData(
            own.get("wall_tile")), 0) if "wall_tile" in own else 0)
        self.tile_h = _spin(0.0, 4.0, fin["tile_h"], 0.1)
        self.ceiling = QCheckBox("มีฝ้าเพดาน")
        self.ceiling.setChecked(fin["ceiling"])
        f.addRow("พื้นผิว", self.floor_fin)
        f.addRow("ผนังบุกระเบื้อง", self.tile)
        f.addRow("บุสูง", self.tile_h)
        f.addRow(self.ceiling)
        hint = QLabel(f"ตอนนี้: พื้น {fin['floor']} · กระเบื้องผนัง "
                      f"{fin['wall_tile'] or '-'} สูง {fin['tile_h']:g} ม. · "
                      f"ฝ้า {'มี' if fin['ceiling'] else 'ไม่มี'}")
        hint.setStyleSheet("color: palette(mid);")
        f.addRow(hint)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)


class NodeDialog(QDialog):
    """The footing, stump and column marks at one column point."""

    def __init__(self, data, node, parent=None):
        super().__init__(parent)
        lib = B.library_of(data)
        x, y = node
        self.setWindowTitle(f"เสาที่ X {x:.2f} · Y {y:.2f} ม.")
        f = QFormLayout(self)
        self.box = {}
        for role, kind, th in (("F", "footing", "ฐานราก"),
                               ("PC", "stump", "เสาตอม่อ"),
                               ("C", "column", "เสา")):
            c = QComboBox()
            for m in B.marks_of(lib, kind):
                spec = lib[m]
                size = (f"{spec['w']:g}×{spec['l']:g}×{spec['t']:g} ม."
                        if kind == "footing" else
                        f"{spec['b']:g}×{spec['h']:g} ม.")
                c.addItem(f"{m}  ({size})", m)
            c.setCurrentIndex(max(c.findData(
                B.node_mark(data, lib, x, y, role)), 0))
            self.box[role] = c
            f.addRow(th, c)
        hint = QLabel("เพิ่ม/แก้เบอร์ได้ที่กลุ่ม «คลังชิ้นส่วน» ด้านล่าง")
        hint.setStyleSheet("color: palette(mid);")
        f.addRow(hint)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)

    def marks(self) -> dict:
        return {k: c.currentData() for k, c in self.box.items()}


def _spin(lo, hi, val, step=0.05, dec=2, suffix=" ม."):
    sp = QDoubleSpinBox()
    sp.setRange(lo, hi)
    sp.setDecimals(dec)
    sp.setSingleStep(step)
    sp.setSuffix(suffix)
    sp.setValue(val)
    return sp


class LibraryBox(QGroupBox):
    """คลังชิ้นส่วน: choose a mark, edit its sizes and bars, add new marks."""

    def __init__(self, panel):
        super().__init__("คลังชิ้นส่วน — ฐานราก เสาตอม่อ เสา คาน พื้น (เบอร์ F / PC / C / "
                         "GB / B / RB / S)")
        self.panel = panel
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.mark = QComboBox()
        self.mark.currentIndexChanged.connect(lambda _i: self._show())
        row.addWidget(self.mark, 1)
        self.kind = QComboBox()
        for k, th in B.LIB_KINDS.items():
            self.kind.addItem(th, k)
        row.addWidget(self.kind)
        add = QPushButton("＋ เบอร์ใหม่")
        add.setToolTip("เพิ่มเบอร์ใหม่ของชนิดที่เลือก (คัดลอกขนาดจากเบอร์แรก)")
        add.clicked.connect(lambda _=False: _safe(self, self.add_mark))
        row.addWidget(add)
        lay.addLayout(row)
        self.form = QFormLayout()
        lay.addLayout(self.form)
        self.edits = {}
        b = QPushButton("💾 บันทึกเบอร์นี้")
        b.clicked.connect(lambda _=False: _safe(self, self.save))
        lay.addWidget(b)
        hint = QLabel("เหล็กเสริมเขียนแบบ 4-DB12 (จำนวน-ขนาด) หรือ RB6@0.15 (ระยะห่าง ม.) "
                      "· ใช้คิดน้ำหนักเหล็กตามหลักเกณฑ์ (ยาวตามแนวเส้นตรง + เผื่อตามขนาด) "
                      "· กำหนดเบอร์รายต้น: เครื่องมือ «📍 กำหนดเบอร์เสา/ฐานราก» แล้วคลิกที่เสา")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(mid);")
        lay.addWidget(hint)

    def refresh(self):
        lib = B.library_of(self.panel.data())
        cur = self.mark.currentData()
        self.mark.blockSignals(True)
        self.mark.clear()
        for kind, th in B.LIB_KINDS.items():
            for m in B.marks_of(lib, kind):
                self.mark.addItem(f"{m} — {th}", m)
        i = self.mark.findData(cur)
        self.mark.setCurrentIndex(max(i, 0))
        self.mark.blockSignals(False)
        self._show()

    def _show(self):
        while self.form.rowCount():
            self.form.removeRow(0)
        self.edits = {}
        m = self.mark.currentData()
        lib = B.library_of(self.panel.data())
        if not m or m not in lib:
            return
        spec = lib[m]
        for key, th in B.LIB_FIELDS[spec["kind"]]:
            e = QLineEdit(str(spec.get(key, "")))
            self.edits[key] = e
            self.form.addRow(th, e)

    def save(self):
        m = self.mark.currentData()
        if not m:
            return
        lib = B.library_of(self.panel.data())
        spec = dict(lib[m])
        for key, e in self.edits.items():
            text = e.text().strip()
            if key in ("bars", "main", "tie", "top", "bot", "stir"):
                spec[key] = text
                continue
            try:
                spec[key] = float(text) if "." in text or key not in (
                    "piles", "ground") else int(text)
            except ValueError:
                QMessageBox.warning(self, TITLE, f"«{text}» ไม่ใช่ตัวเลข")
                return
        self.panel.set_library(m, spec)

    def add_mark(self):
        kind = self.kind.currentData()
        lib = B.library_of(self.panel.data())
        have = B.marks_of(lib, kind)
        prefix = {"footing": "F", "stump": "PC", "column": "C", "beam": "B",
                  "slab": "S"}[kind]
        n = 1
        while f"{prefix}{n}" in lib:
            n += 1
        new = f"{prefix}{n}"
        spec = dict(lib[have[0]]) if have else {"kind": kind}
        self.panel.set_library(new, spec)
        self.mark.setCurrentIndex(max(self.mark.findData(new), 0))


class BoqDialog(QDialog):
    """BOQ ตามหลักเกณฑ์ 2569: the bill by หมวด, the price list, options."""

    COLS = ["ลำดับ", "รายการ", "ปริมาณสุทธิ", "เผื่อ %", "ปริมาณ", "หน่วย",
            "ค่าวัสดุ/หน่วย", "ค่าวัสดุ", "ค่าแรง/หน่วย", "ค่าแรง", "รวม (บาท)",
            "ที่มา / หมายเหตุ"]

    def __init__(self, panel):
        super().__init__(panel)
        from PySide6.QtWidgets import QTabWidget
        self.panel = panel
        self.setWindowTitle("BOQ ตามหลักเกณฑ์กรมบัญชีกลาง พ.ศ. 2569 — WANIC ออกแบบอาคาร")
        self.resize(1180, 760)
        from core import wanic_quantities as Q
        self.result = Q.compute(panel.data())
        lay = QVBoxLayout(self)
        self._province_bar(lay)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)
        self._bill_tab()
        self._price_tab()
        self._option_tab()
        row = QHBoxLayout()
        for text, color, fn in (
                ("📤 ส่งเข้า ถอดปริมาณ (ปร.1–ปร.4)", "#2E7D4F", self.send),
                ("📊 บันทึก Excel (ปร.1–ปร.4 + BOQ)", "#0F2A44",
                 self.save_xlsx),
                ("📄 บันทึก CSV", "#3B6FB6", self.save_csv)):
            b = QPushButton(text)
            b.setStyleSheet(f"QPushButton{{background:{color};color:white;"
                            "font-weight:bold;padding:6px;border-radius:6px}}")
            b.clicked.connect(lambda _=False, f=fn: _safe(self, f))
            row.addWidget(b)
        close = QPushButton("ปิด")
        close.clicked.connect(self.accept)
        row.addStretch(1)
        row.addWidget(close)
        lay.addLayout(row)
        sig = QLabel(label_html("WANIC ออกแบบอาคาร · BOQ ตามหลักเกณฑ์ 2569"))
        lay.addWidget(sig)
        self.recompute()

    # ---- province -----------------------------------------------------------
    def _province_bar(self, lay):
        from PySide6.QtWidgets import QFrame, QLineEdit
        from core import wanic_province as P
        box = QFrame()
        box.setStyleSheet("QFrame{background:rgba(46,125,79,0.12);"
                          "border-radius:6px}")
        g = QGridLayout(box)
        g.setContentsMargins(8, 6, 8, 6)
        d = self.panel.data()
        self.province = QComboBox()
        self.province.setMinimumWidth(190)
        self.province.setToolTip("ราคาวัสดุตามหลักเกณฑ์ราคากลาง: ใช้ราคาของสำนักงาน"
                                 "พาณิชย์จังหวัดที่ก่อสร้าง (เดือนก่อนหน้า)")
        self.province.addItem("— เลือกจังหวัด —", "")
        saved = set(P.books())
        for region, names in P.REGIONS.items():
            self.province.insertSeparator(self.province.count())
            for name in names:
                mark = "  ✓" if name in saved else ""
                self.province.addItem(f"{name}{mark}", name)
                self.province.setItemData(self.province.count() - 1, region,
                                          Qt.ToolTipRole)
        cur = d.get("province") or ""
        self.province.setCurrentIndex(max(self.province.findData(cur), 0))
        self.province.currentIndexChanged.connect(
            lambda _i: _safe(self, self.choose_province))
        self.month = QLineEdit(d.get("price_month") or P.last_month())
        self.month.setMaximumWidth(110)
        self.month.setToolTip("ประจำเดือนของราคา (ใช้เดือนล่าสุดที่ประกาศ)")
        self.month.editingFinished.connect(
            lambda: _safe(self, self._write, "price_month",
                          self.month.text().strip()))
        title = QLabel("<b>📍 จังหวัดที่ก่อสร้าง</b>")
        g.addWidget(title, 0, 0)
        g.addWidget(self.province, 0, 1)
        g.addWidget(QLabel("ราคา ณ เดือน"), 0, 2)
        g.addWidget(self.month, 0, 3)
        self.cover = QLabel()
        self.cover.setWordWrap(True)
        g.addWidget(self.cover, 0, 4, 1, 3)
        for col, (text, tip, fn) in enumerate((
                ("🔄 ดึงราคาจากกระทรวงพาณิชย์ (ออนไลน์)",
                 "ดึงราคาวัสดุก่อสร้างเฉลี่ยรายจังหวัดเดือนล่าสุด จาก MOC Open Data "
                 "(dataapi.moc.go.th) — ต้องต่ออินเทอร์เน็ต", self.fetch_prices),
                ("📥 นำเข้าราคาพาณิชย์จังหวัด (Excel/CSV)…",
                 "ไฟล์ตารางราคาวัสดุก่อสร้างของสำนักงานพาณิชย์จังหวัด (.xlsx/.csv) — "
                 "จับคู่ชื่อวัสดุกับรายการในใบ BOQ ให้อัตโนมัติ", self.import_prices),
                ("📋 วางตารางราคาที่คัดลอกจากเว็บ",
                 "คัดลอกตารางราคาจากหน้าเว็บกระทรวงพาณิชย์ (Ctrl+C) แล้วกดปุ่มนี้",
                 self.paste_prices),
                ("🌐 เปิดเว็บราคาจังหวัด (สนค.)", P.PRICE_SITE,
                 self.open_price_site))):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, f=fn: _safe(self, f))
            g.addWidget(b, 1, [0, 2, 4, 6][col], 1, 2 if col < 3 else 1)
        lay.addWidget(box)

    def _need_keys(self):
        from core import wanic_std2569 as S
        need = list((getattr(self, "result", {}) or {}).get("need") or {})
        return need + [k for k, _u in S.PRICE_KEYS if k not in need]

    def _show_cover(self):
        from core import wanic_province as P
        from core import wanic_quantities as Q
        d = self.panel.data()
        prov = d.get("province") or ""
        need = list((self.result or {}).get("need") or {})
        n, missing = P.coverage(Q.prices_of(d), need)
        if not prov:
            text = ("<span style='color:#B26A00'>ยังไม่ได้เลือกจังหวัด — "
                    "ราคาวัสดุต้องเป็นของจังหวัดที่ก่อสร้าง</span>")
        else:
            col = "#2E7D4F" if not missing else "#B26A00"
            text = (f"<span style='color:{col}'><b>มีราคา {n}/{len(need)} "
                    f"รายการ</b></span>")
            if missing:
                text += (" — ขาด: " + ", ".join(missing[:4]) +
                         (f" และอีก {len(missing) - 4}" if len(missing) > 4
                          else ""))
        self.cover.setText(text)

    def choose_province(self):
        from core import wanic_province as P
        prov = self.province.currentData() or ""
        d = self.panel.data()
        if prov == (d.get("province") or ""):
            return
        old = d.get("province") or ""
        if old and any(float(v or 0) for v in (d.get("prices") or {}).values()):
            P.save_book(old, d.get("prices") or {}, d.get("price_month", ""),
                        src=d.get("price_src"), item=d.get("price_item"))
        d["province"] = prov
        book = P.load_book(prov) if prov else None
        if book:
            d["prices"] = dict(book["prices"])
            d["price_src"] = dict(book.get("src") or {})
            d["price_item"] = dict(book.get("item") or {})
            d["price_month"] = book.get("month") or self.month.text().strip()
            msg = (f"ใช้ราคาวัสดุจังหวัด{prov} ประจำเดือน {d['price_month']} "
                   f"({len(d['prices'])} รายการ, บันทึกเมื่อ {book.get('updated')})")
        else:
            d["prices"], d["price_src"], d["price_item"] = {}, {}, {}
            d["price_month"] = self.month.text().strip() or P.last_month()
            msg = (f"ยังไม่มีราคาของจังหวัด{prov} ในเครื่องนี้ — กด «นำเข้าราคา"
                   "พาณิชย์จังหวัด» หรือคัดลอกตารางจากเว็บมาวาง" if prov else
                   "ยกเลิกการเลือกจังหวัด")
        self.month.setText(d["price_month"])
        self.panel._write(d)
        self.recompute()
        self._fill_prices()
        self.panel.status.setText(msg)
        # No prices yet, or older than last month: fetch them now.
        if prov and (not book or book.get("month") != P.last_month()):
            self.fetch_prices(auto=True)

    def fetch_prices(self, auto=False):
        """Latest average prices of the province from MOC Open Data."""
        from core import wanic_province as P
        prov = self.panel.data().get("province") or ""
        if not prov:
            QMessageBox.information(self, TITLE, "เลือกจังหวัดก่อน")
            return 0
        self.cover.setText(f"กำลังดึงราคาวัสดุจังหวัด{prov} จากกระทรวงพาณิชย์…")
        try:
            items, month, _url = self._fetch_in_background(prov)
        except P.FetchError as e:
            self._show_cover()
            text = (f"{e}\n\nบริการข้อมูลของกระทรวงพาณิชย์ไม่ตอบในขณะนี้ — ใช้ราคาจาก"
                    "เว็บ สนค. แทนได้:\n1) กด «🌐 เปิดเว็บราคาจังหวัด (สนค.)» "
                    f"แล้วเลือกจังหวัด{prov}\n2) กด «ดาวน์โหลดข้อมูล» เป็น Excel\n"
                    "3) กลับมากด «📥 นำเข้าราคาพาณิชย์จังหวัด» (หรือคัดลอกตารางจากเว็บ "
                    "แล้วกด «📋 วางตาราง»)\nโปรแกรมใช้เดือนที่อยู่ในไฟล์ให้เอง")
            if auto:
                self.panel.status.setText(str(e))
                book = P.load_book(prov)
                if book:
                    return 0                     # the saved book stays in use
            QMessageBox.warning(self, TITLE, text)
            return 0
        asked = self.month.text().strip()
        if month:
            self.month.setText(month)
        latest = month == asked
        origin = (f"กระทรวงพาณิชย์ จังหวัด{prov} ราคาเดือน {month}" +
                  ("" if latest else f" (เดือน {asked} ยังไม่ประกาศ — ใช้เดือน"
                   "ล่าสุดที่จังหวัดประกาศ)"))
        return self._apply_items(items, origin, quiet=auto)

    def _fetch_in_background(self, prov):
        """Run :func:`fetch_online` off the UI thread, with a cancellable
        progress box; the MOC server can take a minute or more."""
        import threading
        import time
        from PySide6.QtWidgets import QApplication, QProgressDialog
        from core import wanic_province as P
        from core import wanic_std2569 as S
        state = {"text": "เชื่อมต่อกระทรวงพาณิชย์ …", "done": False}
        keys = self._need_keys()
        need = dict((self.result or {}).get("need") or {})
        units = {k: need.get(k) or S.price_unit(k) for k in keys}
        target = P.parse_month(self.month.text()) or P.parse_month(
            P.last_month())

        def work():
            try:
                state["result"] = P.fetch_online(
                    prov, keys=keys, units=units, target=target,
                    progress=lambda t: state.__setitem__("text", t))
            except Exception as e:                      # noqa: BLE001
                state["error"] = e
            state["done"] = True
        th = threading.Thread(target=work, daemon=True)
        th.start()
        th.join(0.3)
        if not state["done"]:
            box = QProgressDialog(state["text"], "ยกเลิก", 0, 0, self)
            box.setWindowTitle("ดึงราคาวัสดุ — กระทรวงพาณิชย์")
            box.setWindowModality(Qt.WindowModal)
            box.setMinimumDuration(0)
            box.show()
            t0 = time.monotonic()
            while not state["done"]:
                if box.wasCanceled():
                    box.close()
                    raise P.FetchError("ยกเลิกการดึงราคาแล้ว")
                box.setLabelText(f"{state['text']}  ({time.monotonic() - t0:.0f} วินาที)"
                                 "\nเซิร์ฟเวอร์กระทรวงพาณิชย์อาจตอบช้า กรุณารอสักครู่")
                QApplication.processEvents()
                th.join(0.1)
            box.close()
        err = state.get("error")
        if isinstance(err, P.FetchError):
            raise err
        if err is not None:
            raise P.FetchError(f"ดึงราคาไม่สำเร็จ — {err}")
        return state["result"]

    def _apply_items(self, items, origin, quiet=False):
        from core import wanic_province as P
        from core import wanic_quantities as Q
        if not items:
            QMessageBox.warning(self, TITLE, "ไม่พบแถวราคาในข้อมูล — ต้องมีชื่อวัสดุ "
                                "และราคาต่อหน่วยในแต่ละแถว")
            return 0
        d = self.panel.data()
        from core import wanic_std2569 as S
        keys = self._need_keys() + [k for k in (d.get("prices") or {})]
        need = dict((self.result or {}).get("need") or {})
        units = {k: need.get(k) or S.price_unit(k) for k in keys}
        got = P.match(items, keys, units)
        prices = dict(d.get("prices") or {})
        src = dict(d.get("price_src") or {})
        item = dict(d.get("price_item") or {})
        for k, (price, name) in got.items():
            prices[k] = price
            src[k] = "พาณิชย์"
            item[k] = name
        d["prices"], d["price_src"], d["price_item"] = prices, src, item
        d["price_month"] = self.month.text().strip()
        self.panel._write(d)
        prov = d.get("province") or ""
        if prov:
            P.save_book(prov, prices, d["price_month"], src=src, item=item)
            i = self.province.findData(prov)
            if i >= 0 and "✓" not in self.province.itemText(i):
                self.province.setItemText(i, f"{prov}  ✓")
        self.recompute()
        self._fill_prices()
        need = list(self.result.get("need") or {})
        n, missing = P.coverage(Q.prices_of(d), need)
        lines = [f"{origin}: อ่านได้ {len(items)} แถว จับคู่กับวัสดุในใบ BOQ ได้ "
                 f"{len(got)} รายการ", f"มีราคาครบ {n}/{len(need)} รายการที่แบบนี้ใช้"]
        if missing:
            lines.append("ยังขาด (กรอกเองในแท็บ «ฐานข้อมูลราคา»): " +
                         ", ".join(missing[:12]) +
                         (" …" if len(missing) > 12 else ""))
        if not prov:
            lines.append("ยังไม่ได้เลือกจังหวัด — ราคานี้ใช้กับงานนี้เท่านั้น "
                         "(เลือกจังหวัดก่อนเพื่อเก็บไว้ใช้ครั้งต่อไป)")
        if quiet:
            self.panel.status.setText(" · ".join(lines[:2]))
        else:
            QMessageBox.information(self, TITLE, "\n".join(lines))
        return len(got)

    def paste_prices(self):
        from PySide6.QtWidgets import QApplication
        from core import wanic_province as P
        text = QApplication.clipboard().text() if QApplication.clipboard() \
            else ""
        if not text.strip():
            QMessageBox.information(
                self, TITLE, "คลิปบอร์ดว่าง — เปิดหน้าราคาวัสดุก่อสร้างของจังหวัด "
                "เลือกตาราง แล้วกด Ctrl+C ก่อน")
            return 0
        rows = P.rows_from_text(text)
        month = P.detect_month(rows)
        if month:
            self.month.setText(month)
        return self._apply_items(P.parse_rows(rows), "ตารางที่วาง")

    def open_price_site(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from core import wanic_province as P
        prov = self.panel.data().get("province") or ""
        if not os.environ.get("WANIC_OFFLINE"):
            QDesktopServices.openUrl(QUrl(P.PRICE_SITE))
        self.panel.status.setText(
            f"เลือกจังหวัด{prov or '…'} บนเว็บ → «ดาวน์โหลดข้อมูล» เป็น Excel → "
            "กลับมากด «📥 นำเข้าราคาพาณิชย์จังหวัด»")

    # ---- tabs ---------------------------------------------------------------
    def _bill_tab(self):
        from PySide6.QtWidgets import QTreeWidget
        w = QWidget()
        v = QVBoxLayout(w)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(len(self.COLS))
        self.tree.setHeaderLabels(self.COLS)
        self.tree.setAlternatingRowColors(True)
        widths = [52, 330, 90, 56, 90, 56, 90, 100, 90, 100, 110, 420]
        for i, px in enumerate(widths):
            self.tree.setColumnWidth(i, px)
        v.addWidget(self.tree, 1)
        self.total = QLabel()
        self.total.setWordWrap(True)
        v.addWidget(self.total)
        self.tabs.addTab(w, "ใบ BOQ")

    def _price_tab(self):
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem
        from core import wanic_std2569 as S
        w = QWidget()
        v = QVBoxLayout(w)
        note = QLabel("ราคาวัสดุ: ใช้ราคาจากสำนักงานพาณิชย์จังหวัด (ราคาไม่รวม VAT) · "
                      "ค่าแรง: บัญชีค่าแรงงาน ว480 ลงวันที่ 26 มิ.ย. 2569 (แก้ได้) · "
                      "ค่าวัสดุมวลรวมคิดจากสูตรต่อหน่วยในหลักเกณฑ์ (เผื่อเสียหายแล้ว)")
        note.setWordWrap(True)
        v.addWidget(note)
        h = QHBoxLayout()
        self.prices = QTableWidget(0, 5)
        self.prices.setHorizontalHeaderLabels(["วัสดุ (รายการที่ใช้ในแบบนี้อยู่บน)", "หน่วย",
                                               "ราคา/หน่วย (บาท)", "ที่มา",
                                               "แหล่งราคาท้องตลาด / หมายเหตุ"])
        self.prices.setColumnWidth(0, 330)
        self.prices.setColumnWidth(3, 150)
        self.prices.setColumnWidth(4, 220)
        self.labour = QTableWidget(0, 4)
        self.labour.setHorizontalHeaderLabels(["ข้อ ว480", "รายการ", "หน่วย",
                                               "ค่าแรง/หน่วย (บาท)"])
        self.labour.setColumnWidth(1, 300)
        h.addWidget(self.prices, 1)
        h.addWidget(self.labour, 1)
        v.addLayout(h, 1)
        row = QHBoxLayout()
        for text, fn in (("🔎 หาราคาท้องตลาด (แถวที่เลือก)", self.search_market),
                         ("ราคาตัวอย่าง (ทดลองใช้)", self.sample_prices),
                         ("ล้างราคาวัสดุ", self.clear_prices),
                         ("ค่าแรงตาม ว480", self.reset_labour),
                         ("ส่งออกราคา CSV…", self.export_prices),
                         ("💾 บันทึกราคาและคำนวณใหม่", self.save_prices)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, f=fn: _safe(self, f))
            row.addWidget(b)
        v.addLayout(row)
        self.tabs.addTab(w, "ฐานข้อมูลราคา")
        self._QTI = QTableWidgetItem
        self._S = S
        self._fill_prices()

    def _fill_prices(self):
        from core import wanic_quantities as Q
        S, QTI = self._S, self._QTI
        d = self.panel.data()
        prices = Q.prices_of(d)
        src = d.get("price_src") or {}
        where_note = d.get("price_note") or {}
        prov = d.get("province") or ""
        need = dict(getattr(self, "result", {}).get("need") or {})
        keys = list(need) + [k for k, _u in S.PRICE_KEYS if k not in need]
        keys += sorted(k for k in prices if k not in keys)
        self._units = {k: need.get(k) or S.price_unit(k) for k in keys}
        self._shown = {}
        self.prices.setRowCount(len(keys))
        warn = QColor(255, 179, 0, 60)
        for r, k in enumerate(keys):
            v = float(prices.get(k) or 0)
            self._shown[k] = v
            where = src.get(k, "ท้องตลาด") if v > 0 else (
                f"ไม่พบราคาที่จ.{prov}ประกาศ" if prov else "— ไม่มีราคา")
            if where == "พาณิชย์":
                where = f"พาณิชย์จ.{prov}" if prov else "ไฟล์พาณิชย์"
            elif where == "กรอกเอง":
                where = "ท้องตลาด"
            a, b, c = QTI(k), QTI(self._units.get(k, "")), QTI(where)
            for it in (a, b, c):
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            self.prices.setItem(r, 0, a)
            self.prices.setItem(r, 1, b)
            self.prices.setItem(r, 2, QTI(f"{v:g}"))
            if (d.get("price_item") or {}).get(k):
                c.setToolTip(d["price_item"][k])
            self.prices.setItem(r, 3, c)
            self.prices.setItem(r, 4, QTI(where_note.get(k, "")))
            if v <= 0 and k in need:
                for col in range(5):
                    self.prices.item(r, col).setBackground(warn)
        labour = Q.labour_of(d)
        codes = list(S.LABOUR)
        self.labour.setRowCount(len(codes))
        for r, c in enumerate(codes):
            desc, unit, _rate, cond = S.LABOUR[c]
            cells = [c, f"{desc} ({cond})", unit]
            for col, text in enumerate(cells):
                it = QTI(text)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.labour.setItem(r, col, it)
            self.labour.setItem(r, 3, QTI(f"{labour[c]:g}"))

    def _option_tab(self):
        from core import wanic_quantities as Q
        from core import wanic_recipes2569 as RC
        w = QWidget()
        f = QFormLayout(w)
        o = Q.options_of(self.panel.data())
        self.opt = {}
        for key, th in (("finishes", "คิดงานปูพื้นและฝ้าเพดาน"),
                        ("paint", "คิดงานทาสีผนัง"),
                        ("ready_mix", "คอนกรีตผสมเสร็จ (ไม่ติ๊ก = ผสมเองตามสูตร ค.3)")):
            c = QCheckBox(th)
            c.setChecked(bool(o[key]))
            self.opt[key] = c
            f.addRow(c)
        roof_note = QLabel("วัสดุมุงหลังคา เลือกที่กลุ่ม «หลังคา» ในแท็บออกแบบอาคาร")
        roof_note.setStyleSheet("color: palette(mid);")
        f.addRow(roof_note)
        self.recipe = {}
        for key, prefix, th in (("wall_recipe", "6.", "ผนัง (สูตรวัสดุ)"),
                                ("plaster_recipe", "7.", "ฉาบปูน (สูตรวัสดุ)"),
                                ("floor_recipe", "9.", "พื้นผิว (สูตรวัสดุ)")):
            c = QComboBox()
            for rc in RC.RECIPES:
                if rc["code"].startswith(prefix) and rc["items"]:
                    c.addItem(f"{rc['code']} {rc['name'][:70]}", rc["code"])
            c.setCurrentIndex(max(c.findData(o[key]), 0))
            self.recipe[key] = c
            f.addRow(th, c)
        self.sand = {}
        for key, th in (("slab_sand", "ทรายรองใต้พื้นวางบนดิน หนา (ม.)"),
                        ("gb_sand", "ทรายรองใต้คานคอดิน หนา (ม.)")):
            sp = _spin(0.0, 0.5, float(o[key]), 0.01)
            self.sand[key] = sp
            f.addRow(th, sp)
        b = QPushButton("💾 บันทึกตัวเลือกและคำนวณใหม่")
        b.clicked.connect(lambda _=False: _safe(self, self.save_options))
        f.addRow(b)
        src = QLabel("ที่มา: หลักเกณฑ์การคำนวณราคากลางงานก่อสร้าง พ.ศ. 2569 ส่วนที่ 4 "
                     "(การคำนวณปริมาณงาน การเผื่อ) และวัสดุมวลรวมของงานก่อสร้างอาคาร "
                     f"({len(RC.RECIPES)} สูตร แยกข้อความอัตโนมัติ — ตรวจทานกับเล่มก่อนใช้งานจริง)")
        src.setWordWrap(True)
        src.setStyleSheet("color: palette(mid);")
        f.addRow(src)
        self.tabs.addTab(w, "ตัวเลือก")

    # ---- data ---------------------------------------------------------------
    def recompute(self):
        from PySide6.QtWidgets import QTreeWidgetItem
        from core import wanic_quantities as Q
        self.result = Q.compute(self.panel.data())
        self.tree.clear()
        bold = QFont(self.font())
        bold.setBold(True)
        for gi, (_k, th, rows) in enumerate(self.result["groups"], 1):
            top = QTreeWidgetItem([str(gi), th])
            for c in range(2):
                top.setFont(c, bold)
            tm = sum(r["mat_total"] for r in rows)
            tl = sum(r["lab_total"] for r in rows)
            top.setText(7, f"{tm:,.2f}")
            top.setText(9, f"{tl:,.2f}")
            top.setText(10, f"{tm + tl:,.2f}")
            top.setFont(10, bold)
            self.tree.addTopLevelItem(top)
            for li, ln in enumerate(rows, 1):
                it = QTreeWidgetItem([
                    f"{gi}.{li}", ln["desc"], f"{ln['net']:,.3f}",
                    f"{ln['waste']:g}" if ln["waste"] else "",
                    f"{ln['qty']:,.2f}", ln["unit"], f"{ln['mat']:,.2f}",
                    f"{ln['mat_total']:,.2f}", f"{ln['lab']:,.2f}",
                    f"{ln['lab_total']:,.2f}", f"{ln['total']:,.2f}",
                    ln["ref"] + (f" · {ln['note']}" if ln["note"] else "")])
                tip = f"{ln['basis']}\n{ln['ref']}" + (
                    f"\n{ln['note']}" if ln["note"] else "")
                for c in range(len(self.COLS)):
                    it.setToolTip(c, tip)
                    if 2 <= c <= 10 and c != 5:
                        it.setTextAlignment(c, Qt.AlignRight | Qt.AlignVCenter)
                if ln["note"]:
                    it.setForeground(1, QColor("#B26A00"))
                if ln["mat_key"] and not ln["mat"]:
                    it.setForeground(6, QColor("#B26A00"))
                    it.setToolTip(6, f"ยังไม่มีราคา «{ln['mat_key']}» "
                                     "ของจังหวัดที่เลือก")
                top.addChild(it)
            top.setExpanded(True)
        t = self.result["totals"]
        notes = " · ".join(self.result["notes"])
        if hasattr(self, "cover"):
            self._show_cover()
        ref = self.result.get("price_ref") or ""
        self.total.setText(
            (f"<span style='color:#2E7D4F'>{ref}</span><br>" if ref else "") +
            f"<b>รวมค่างานต้นทุน {t['total']:,.2f} บาท</b> (ค่าวัสดุ {t['mat']:,.2f} + "
            f"ค่าแรง {t['lab']:,.2f}) — ยังไม่คูณ Factor F · ส่งเข้า «ถอดปริมาณ» "
            f"เพื่อคิด Factor F และพิมพ์แบบ ปร.<br><span style='color:#B26A00'>{notes}"
            "</span>")

    def _write(self, key, value):
        d = self.panel.data()
        d[key] = value
        self.panel._write(d)

    def save_prices(self):
        prices, labour = {}, {}
        for r in range(self.prices.rowCount()):
            k = self.prices.item(r, 0).text()
            try:
                prices[k] = float(self.prices.item(r, 2).text().replace(",", ""))
            except (ValueError, AttributeError):
                prices[k] = 0.0
        S = self._S
        for r in range(self.labour.rowCount()):
            c = self.labour.item(r, 0).text()
            try:
                v = float(self.labour.item(r, 3).text().replace(",", ""))
            except (ValueError, AttributeError):
                continue
            if abs(v - float(S.LABOUR[c][2])) > 1e-9:
                labour[c] = v
        d = self.panel.data()
        src = dict(d.get("price_src") or {})
        shown = getattr(self, "_shown", {})
        for k, v in prices.items():
            if abs(v - float(shown.get(k, 0) or 0)) > 1e-9:
                src[k] = "ท้องตลาด"
        notes = {}
        for r in range(self.prices.rowCount()):
            it = self.prices.item(r, 4)
            if it is not None and it.text().strip():
                notes[self.prices.item(r, 0).text()] = it.text().strip()
        d["prices"], d["labour"], d["price_src"] = prices, labour, src
        d["price_note"] = notes
        d["price_month"] = self.month.text().strip()
        self.panel._write(d)
        if d.get("province"):
            from core import wanic_province as P
            P.save_book(d["province"], prices, d["price_month"], src=src,
                        item=d.get("price_item"))
        self.recompute()
        self._fill_prices()

    def sample_prices(self):
        d = self.panel.data()
        keys = set(self._S.SAMPLE_PRICES) | set(self.result.get("need") or {})
        d["prices"] = {k: self._S.sample_price(k) for k in keys}
        d["price_src"] = {k: "ตัวอย่าง" for k in keys}
        self.panel._write(d)
        self.recompute()
        self._fill_prices()
        self.recompute()
        self.panel.status.setText("ใส่ราคาตัวอย่างแล้ว — ไม่ใช่ราคาทางราชการ "
                                  "ให้แทนด้วยราคาพาณิชย์จังหวัดก่อนใช้งานจริง")

    def clear_prices(self):
        d = self.panel.data()
        d["prices"], d["price_src"] = {}, {}
        self.panel._write(d)
        self._fill_prices()
        self.recompute()

    def reset_labour(self):
        self._write("labour", {})
        self._fill_prices()
        self.recompute()

    def search_market(self):
        """Open a web search for the selected material's shop price in the
        province (the criteria: no announced price → the market price)."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from core import wanic_province as P
        prov = self.panel.data().get("province") or ""
        r = self.prices.currentRow()
        if r < 0 or not prov:
            QMessageBox.information(self, TITLE, "เลือกจังหวัด แล้วคลิกแถววัสดุที่ต้องการ"
                                    "หาราคาท้องตลาดก่อน")
            return ""
        item = self.prices.item(r, 0).text()
        url = P.market_search_url(item, prov)
        if not os.environ.get("WANIC_OFFLINE"):
            QDesktopServices.openUrl(QUrl(url))
        self.panel.status.setText(
            f"หาราคา «{item}» ที่จังหวัด{prov} — ได้ราคาแล้วกรอกในช่องราคา และใส่"
            "ชื่อร้าน/แหล่งที่มาในช่อง «แหล่งราคาท้องตลาด» แล้วกดบันทึก")
        return url

    def import_prices(self):
        from PySide6.QtWidgets import QFileDialog
        from core import wanic_province as P
        start = os.path.join(os.path.expanduser("~"), "Downloads")
        path, _f = QFileDialog.getOpenFileName(
            self, "นำเข้าราคาวัสดุ สำนักงานพาณิชย์จังหวัด (ไฟล์ที่ดาวน์โหลดจากเว็บ)",
            start if os.path.isdir(start) else "",
            "ตารางราคา (*.xlsx *.csv *.txt);;ทุกไฟล์ (*)")
        if not path:
            return 0
        try:
            items, month = P.read_table(path)
        except (ValueError, OSError, KeyError) as e:
            QMessageBox.warning(self, TITLE, f"อ่านไฟล์ไม่ได้: {e}")
            return 0
        if month:
            self.month.setText(month)
        return self._apply_items(items, os.path.basename(path) +
                                 (f" (ราคาเดือน {month})" if month else ""))

    def export_prices(self):
        import csv
        import io
        from PySide6.QtWidgets import QFileDialog
        from core import wanic_quantities as Q
        path, _f = QFileDialog.getSaveFileName(self, "ส่งออกราคา",
                                               "ราคาวัสดุ.csv", "CSV (*.csv)")
        if not path:
            return
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["วัสดุ", "หน่วย", "ราคา/หน่วย"])
        for k, v in Q.prices_of(self.panel.data()).items():
            w.writerow([k, self._S.price_unit(k), f"{v:g}"])
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            fh.write(buf.getvalue())

    def save_options(self):
        o = {k: c.isChecked() for k, c in self.opt.items()}
        o.update({k: c.currentData() for k, c in self.recipe.items()})
        o.update({k: sp.value() for k, sp in self.sand.items()})
        self._write("boq_options", o)
        self.recompute()

    # ---- output -------------------------------------------------------------
    def send(self):
        from core import wanic_province as P
        from core import wanic_quantities as Q
        self.recompute()
        n = self.panel.send_standard_boq(self.result)
        d = self.panel.data()
        need = list(self.result.get("need") or {})
        have, missing = P.coverage(Q.prices_of(d), need)
        prov = d.get("province") or ""
        head = (f"ส่ง {n} รายการเข้าแท็บ «ถอดปริมาณ» แล้ว (แทนชุดเดิมที่ส่งจากหน้านี้)")
        info = (f"ราคาวัสดุจังหวัด{prov} ประจำเดือน {d.get('price_month', '')} — "
                f"มีราคา {have}/{len(need)} รายการ" if prov else
                "⚠ ยังไม่ได้เลือกจังหวัด — ราคากลางต้องใช้ราคาวัสดุของจังหวัดที่ก่อสร้าง")
        if prov and missing:
            info += f" (ขาด {len(missing)} รายการ ค่าวัสดุของรายการนั้นเป็น 0)"
        QMessageBox.information(
            self, TITLE, f"{head}\n{info}\n\nกด «ข้อมูลราคากลาง (ปร.)» ที่แท็บ "
            "ถอดปริมาณ เพื่อกำหนด Factor F แล้วส่งออก ปร.1–ปร.4")

    def save_xlsx(self):
        from PySide6.QtWidgets import QFileDialog
        from core import wanic_quantities as Q
        from core import wanic_takeoff as T
        path, _f = QFileDialog.getSaveFileName(
            self, "บันทึก Excel", "BOQ_ปร.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        td = self.panel.takeoff_data()
        td["rates"] = Q.to_rates(self.result)
        prov = self.result.get("province") or ""
        if prov:
            st = td.setdefault("settings", {})
            if not str(st.get("location") or "").strip():
                st["location"] = ("กรุงเทพมหานคร" if prov == "กรุงเทพมหานคร"
                                  else f"จังหวัด{prov}")
            st["price_ref"] = self.result.get("price_ref", "")
        res = T.compute([], td)
        with open(path, "wb") as fh:
            fh.write(T.boq_xlsx_bytes(res, T.settings_of(td)))
        self.panel.status.setText(f"บันทึก {path} แล้ว")

    def save_csv(self):
        from PySide6.QtWidgets import QFileDialog
        from core import wanic_quantities as Q
        path, _f = QFileDialog.getSaveFileName(self, "บันทึก CSV", "BOQ.csv",
                                               "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            fh.write(Q.csv_text(self.result))


class BuildingPanel(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.floor = 0
        self._preview = None
        self._stair_preview = None
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
            b.clicked.connect(lambda _=False, f=fn: _safe(self, f))
            fb.addWidget(b)
        lay.addLayout(fb)

        # Room palette: a room type and a standard size, chosen apart.
        rp = QGridLayout()
        self.room_name = QComboBox()
        self.room_name.setEditable(True)
        self.room_name.addItems(B.ROOM_TYPES)
        self.size_box = QComboBox()
        for w, d in B.ROOM_SIZES:
            self.size_box.addItem(f"{w:g} × {d:g} ม.", (w, d))
        self.size_box.addItem("กำหนดเอง", None)
        self.size_box.currentIndexChanged.connect(self._preset_changed)
        self.room_w = _spin(0.5, 100, 3.0, 0.5)
        self.room_d = _spin(0.5, 100, 3.0, 0.5)
        rot = QPushButton("↻ หมุน 90°")
        rot.setToolTip("สลับกว้าง/ลึก ของห้องที่จะวาง (ห้องที่เลือกบนผังกด R)")
        rot.clicked.connect(lambda _=False: _safe(self, self._swap_size))
        rp.addWidget(QLabel("ประเภทห้อง"), 0, 0)
        rp.addWidget(self.room_name, 0, 1, 1, 3)
        rp.addWidget(QLabel("ขนาดมาตรฐาน"), 1, 0)
        rp.addWidget(self.size_box, 1, 1, 1, 2)
        rp.addWidget(rot, 1, 3)
        rp.addWidget(QLabel("กว้าง X"), 2, 0)
        rp.addWidget(self.room_w, 2, 1)
        rp.addWidget(QLabel("ลึก Y"), 2, 2)
        rp.addWidget(self.room_d, 2, 3)
        lay.addLayout(rp)
        hint = QLabel("คลิกที่ว่าง = วางห้อง · ลากห้อง = ย้าย (ดูดติดขอบห้องอื่นและกริด) · "
                      "Ctrl+คลิก / ลากครอบ (เครื่องมือ «เลือก») = เลือกหลายห้อง · "
                      "Ctrl+C / Ctrl+V = คัดลอก/วาง · Ctrl+Z / Ctrl+Y = ย้อน/ทำซ้ำ · "
                      "ดับเบิลคลิก = แก้ขนาด · R = หมุน · Delete = ลบ · "
                      "ดับเบิลคลิกขวา/Esc = ยกเลิกคำสั่ง · ล้อเมาส์ = ซูม · "
                      "ปุ่มกลาง = เลื่อน")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(mid);")
        lay.addWidget(hint)

        tl = QHBoxLayout()
        tl.addWidget(QLabel("เครื่องมือ"))
        self.tool_box = QComboBox()
        for k, v in (("room", "🟩 วางห้อง"),
                     ("select", "↖ เลือก / ลากครอบ"),
                     ("node", "📍 กำหนดเบอร์เสา/ฐานราก (คลิกที่เสา)"),
                     ("door", "🚪 ประตู (คลิกที่แนวผนัง)"),
                     ("window", "🪟 หน้าต่าง (คลิกที่แนวผนัง)"),
                     ("stair", "🪜 บันได (คลิกวาง · ลากย้าย · R หมุน)"),
                     ("fixture", "🚽 สุขภัณฑ์ (คลิกวาง · ลากย้าย · R หมุน)")):
            self.tool_box.addItem(v, k)
        tl.addWidget(self.tool_box, 1)
        lay.addLayout(tl)
        # Door / window type and size for the next one placed.
        self.op_row = QWidget()
        og = QGridLayout(self.op_row)
        og.setContentsMargins(0, 0, 0, 0)
        self.op_style = QComboBox()
        self.op_style.currentIndexChanged.connect(lambda _i: self._style_changed())
        self.op_w = _spin(0.3, 6.0, 0.9)
        self.op_h = _spin(0.3, 4.0, 2.0)
        self.op_sill = _spin(0.0, 3.0, 0.9)
        og.addWidget(QLabel("แบบ"), 0, 0)
        og.addWidget(self.op_style, 0, 1, 1, 5)
        for c, (lab, sp) in enumerate((("กว้าง", self.op_w), ("สูง", self.op_h),
                                       ("ขอบล่าง", self.op_sill))):
            og.addWidget(QLabel(lab), 1, c * 2)
            og.addWidget(sp, 1, c * 2 + 1)
        lay.addWidget(self.op_row)
        # Sanitary ware.
        self.fx_row = QWidget()
        fg = QHBoxLayout(self.fx_row)
        fg.setContentsMargins(0, 0, 0, 0)
        self.fx_type = QComboBox()
        for code, spec in CAT.SANITARY.items():
            self.fx_type.addItem(f"{code} — {spec[0]}", code)
        fg.addWidget(self.fx_type, 1)
        bset = QPushButton("🛁 ชุดห้องน้ำ/ครัวมาตรฐาน")
        bset.setToolTip("วางสุขภัณฑ์ชุดมาตรฐานในห้องน้ำ (และซิงค์ในห้องครัว) ทุกห้องของชั้นนี้"
                        "ที่ยังไม่มี — ห้องที่เลือกอยู่จะถูกใส่ก่อน")
        bset.clicked.connect(lambda _=False: _safe(self, self.fill_standard_sets))
        fg.addWidget(bset)
        lay.addWidget(self.fx_row)
        self.tool_box.currentIndexChanged.connect(lambda _i: self._tool_changed())
        self.canvas = PlanCanvas(self)
        lay.addWidget(self.canvas, 1)
        cb = QHBoxLayout()
        for text, fn in (("⤢ พอดีหน้าจอ", self.canvas.fit),
                         ("↶ ย้อน", self.undo), ("↷ ทำซ้ำ", self.redo),
                         ("🗑 ล้างห้องชั้นนี้", self.clear_floor)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, f=fn: _safe(self, f))
            cb.addWidget(b)
        self.foot_chk = QCheckBox("แสดงฐานราก")
        self.foot_chk.setChecked(True)
        self.foot_chk.toggled.connect(lambda _v: self.canvas.update())
        cb.addWidget(self.foot_chk)
        cb.addStretch(1)
        lay.addLayout(cb)

        # Build buttons.
        bb = QGridLayout()

        def btn(text, tip, fn, r, c, color):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setStyleSheet(f"QPushButton{{background:{color};color:white;"
                            "font-weight:bold;padding:6px;border-radius:6px}}")
            b.clicked.connect(lambda _=False: _safe(self, fn))
            bb.addWidget(b, r, c)
        btn("🏗 สร้าง/อัปเดตโครงสร้าง", "ฐานราก ตอม่อ เสา คาน พื้น ผนัง ทุกชั้น",
            lambda: self.build(("structure",)), 0, 0, "#2E7D4F")
        btn("🏠 สร้าง/อัปเดตหลังคา", "โครงหลังคาเหล็กและแผ่นหลังคา",
            lambda: self.build(("roof",)), 0, 1, "#C46420")
        btn("✅ สร้างทั้งหมด", "โครงสร้าง + หลังคา",
            lambda: self.build(("structure", "roof")), 1, 0, "#0F2A44")
        btn("📊 BOQ ตามหลักเกณฑ์ 2569…",
            "ถอดปริมาณตามหลักเกณฑ์กรมบัญชีกลาง (เผื่อตามมาตรฐาน ค่าแรง ว480) "
            "แล้วส่งเข้า ปร.1–ปร.4", self.open_boq, 1, 1, "#7B3FA0")
        btn("💰 รายการราคาผูกชิ้นส่วนโมเดล",
            "เพิ่มรายการราคา (ราคาเริ่ม 0) ผูกตามชื่อชิ้นส่วน ในแท็บ ถอดปริมาณ "
            "(วัดจากโมเดล 3D)", self.send_rates, 2, 1, "#3B6FB6")
        lay.addLayout(bb)
        rm = QPushButton("ลบสิ่งที่สร้างโดย ออกแบบอาคาร")
        rm.clicked.connect(lambda _=False: _safe(self, self.remove_built))
        lay.addWidget(rm)
        self.status = QLabel()
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        # Settings.
        self.fields = {}
        st = QGroupBox("ชั้นและผนัง")
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
        num("floor_h", "ความสูงชั้น (พื้นถึงพื้น)", 2.0, 10.0, 0.1)
        num("grid", "ระยะกริดผัง", 0.05, 5.0, 0.05)
        self.walls = QCheckBox("สร้างผนังก่ออิฐรอบห้อง")
        self.walls.toggled.connect(lambda _v: self._save_settings())
        sf.addRow(self.walls)
        num("wall_t", "ผนังหนา", 0.05, 0.5, 0.01)
        num("band", "เสาเอ็น-ทับหลังรอบประตู/หน้าต่าง (0 = ไม่มี)", 0.0, 0.3, 0.01)
        lay.addWidget(st)
        self.library = LibraryBox(self)
        lay.addWidget(self.library)

        ow = QGroupBox("บันได (ค่าเริ่มต้น)")
        sf = QFormLayout(ow)
        num("stair_w", "บันได กว้าง", 0.6, 5.0)
        num("riser_max", "ลูกตั้งสูงไม่เกิน", 0.10, 0.25, 0.01)
        num("going", "ลูกนอน", 0.20, 0.40, 0.01)
        num("stair_t", "ท้องบันไดหนา", 0.08, 0.40, 0.01)
        lay.addWidget(ow)

        rf = QGroupBox("หลังคา")
        rff = QFormLayout(rf)
        self.roof = QComboBox()
        for k, v in (("hip", "ปั้นหยา"), ("gable", "จั่ว"),
                     ("none", "ไม่สร้างหลังคา")):
            self.roof.addItem(v, k)
        self.roof.currentIndexChanged.connect(lambda _i: self._save_settings())
        rff.addRow("แบบหลังคา", self.roof)
        self.roof_mode = QComboBox()
        self.roof_mode.addItem("ตามรูปผัง (ตัว L / T มีราง)", "plan")
        self.roof_mode.addItem("คลุมกรอบสี่เหลี่ยมทั้งหลัง", "bbox")
        self.roof_mode.currentIndexChanged.connect(
            lambda _i: self._save_settings())
        rff.addRow("รูปหลังคา", self.roof_mode)
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
            for i, (lab, fam, prm) in enumerate(B.steel_presets()):
                from core import wanic_profiles as P
                c.setItemData(i, f"{lab} — {P.weight_per_m(fam, prm):.2f} กก./ม.",
                              Qt.ToolTipRole)
            c.currentIndexChanged.connect(lambda _i: self._save_settings())
            self.steel[key] = c
            rff.addRow(th, c)
        self.skin = QCheckBox("สร้างแผ่นหลังคา (คิดพื้นที่มุงหลังคา)")
        self.skin.toggled.connect(lambda _v: self._save_settings())
        rff.addRow(self.skin)
        self.tile = QComboBox()
        for code, spec in CAT.ROOF_TILES.items():
            per = CAT.tiles_per_m2(spec)
            extra = "" if spec["unit"] == "ตร.ม." else f" (~{per:.1f} แผ่น/ตร.ม.)"
            self.tile.addItem(f"{code} {spec['name']}{extra}", code)
        self.tile.currentIndexChanged.connect(lambda _i: self._save_settings())
        rff.addRow("วัสดุมุง", self.tile)
        self.tile_color = QComboBox()
        for name, rgb in CAT.TILE_COLORS.items():
            self.tile_color.addItem(name, name)
            if rgb:
                from PySide6.QtGui import QPixmap
                pm = QPixmap(14, 14)
                pm.fill(QColor.fromRgbF(*rgb))
                from PySide6.QtGui import QIcon
                self.tile_color.setItemIcon(self.tile_color.count() - 1,
                                            QIcon(pm))
        self.tile_color.currentIndexChanged.connect(
            lambda _i: self._save_settings())
        rff.addRow("สีกระเบื้อง", self.tile_color)
        self.tiles_3d = QCheckBox("แสดงลอนกระเบื้องเป็นแผ่น ๆ ในโมเดล 3D")
        self.tiles_3d.toggled.connect(lambda _v: self._save_settings())
        rff.addRow(self.tiles_3d)
        self.caps = QCheckBox("ครอบสัน ครอบตะเข้สัน ครอบข้าง")
        self.caps.toggled.connect(lambda _v: self._save_settings())
        rff.addRow(self.caps)
        self.fascia = QCheckBox("สร้างเชิงชาย (และปั้นลมหน้าจั่ว)")
        self.fascia.toggled.connect(lambda _v: self._save_settings())
        rff.addRow(self.fascia)
        sf_keep = sf
        sf = rff
        num("tiles_m2", "จำนวนแผ่น/ตร.ม. ตามคู่มือผู้ผลิต (0 = คิดจากระยะซ้อน)",
            0.0, 40.0, 0.1, 1, "")
        num("fascia_h", "เชิงชาย หน้ากว้าง", 0.10, 0.40, 0.025)
        num("fascia_t", "เชิงชาย หนา", 0.01, 0.06, 0.005)
        sf = sf_keep
        lay.addWidget(rf)
        note = QLabel("ขนาดชิ้นส่วนและเหล็กเสริมเป็นค่าเริ่มต้น — วิศวกรผู้ออกแบบต้องกำหนด"
                      "ตามแบบจริง (โปรแกรมไม่ได้ออกแบบ/ตรวจกำลังโครงสร้าง) · "
                      "หลังคาตามรูปผังซ้อนกันตรงรางน้ำ · ชั้นที่ไม่มีห้องจะถูกข้าม")
        note.setWordWrap(True)
        note.setStyleSheet("color: palette(mid);")
        lay.addWidget(note)
        sig = QLabel(label_html("WANIC ออกแบบอาคาร"))
        sig.setWordWrap(True)
        lay.addWidget(sig)

        self._preset_changed()
        self._tool_changed()
        self.refresh()
        QTimer.singleShot(0, self.canvas.fit)

    # ---- document data -------------------------------------------------------
    def data(self) -> dict:
        d = self.app.document_data(None) or B.default_data()
        d.setdefault("floors", [B.new_floor()])
        if not d["floors"]:
            d["floors"] = [B.new_floor()]
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
        size = self.size_box.currentData()
        if size:
            self.room_w.setValue(size[0])
            self.room_d.setValue(size[1])

    def _swap_size(self):
        w, d = self.room_w.value(), self.room_d.value()
        self.room_w.setValue(d)
        self.room_d.setValue(w)

    def set_tool(self, key):
        self.tool_box.setCurrentIndex(max(self.tool_box.findData(key), 0))

    def show_footings(self) -> bool:
        return self.foot_chk.isChecked()

    def undo(self):
        h = self.app.viewport.history
        if getattr(h, "can_undo", lambda: True)():
            h.undo()
        self.app.viewport.update()
        self.refresh()

    def redo(self):
        h = self.app.viewport.history
        if getattr(h, "can_redo", lambda: True)():
            h.redo()
        self.app.viewport.update()
        self.refresh()

    def place_room(self, x, y):
        d = self.data()
        rooms = d["floors"][self.floor]["rooms"]
        w, dd = self.room_w.value(), self.room_d.value()
        rm = {"id": self._next_id(d), "name": self.room_name.currentText()
              .strip() or "ห้อง", "x": x - w / 2, "y": y - dd / 2, "w": w, "d": dd}
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
        lib = B.library_of(self.data())

        def fn(rooms, i, rm):
            dlg = RoomDialog(rm, self, B.marks_of(lib, "slab"))
            if dlg.exec() != QDialog.Accepted:
                return False
            rm.update(name=dlg.name.currentText().strip() or rm.get("name", ""),
                      w=dlg.w.value(), d=dlg.d.value())
            if dlg.slab.currentData():
                rm["slab"] = dlg.slab.currentData()
            else:
                rm.pop("slab", None)
            fin = {}
            if dlg.floor_fin.currentData() is not None:
                fin["floor"] = dlg.floor_fin.currentData()
            if dlg.tile.currentData() is not None:
                fin["wall_tile"] = dlg.tile.currentData()
            base = CAT.finish_of(dict(rm, finish={}))
            if abs(dlg.tile_h.value() - base["tile_h"]) > 1e-6:
                fin["tile_h"] = dlg.tile_h.value()
            if dlg.ceiling.isChecked() != base["ceiling"]:
                fin["ceiling"] = dlg.ceiling.isChecked()
            if fin:
                rm["finish"] = fin
            else:
                rm.pop("finish", None)
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

    def delete_rooms(self, ids):
        ids = set(ids)
        if not ids:
            return
        d = self.data()
        f = d["floors"][self.floor]
        f["rooms"] = [r for r in f["rooms"] if r["id"] not in ids]
        self._write(d)

    def copy_rooms(self, ids):
        rooms = [copy.deepcopy(r) for r in self.rooms() if r["id"] in set(ids)]
        self._clip = rooms
        if rooms:
            self.status.setText(f"คัดลอก {len(rooms)} ห้องแล้ว — Ctrl+V เพื่อวาง "
                                "(ที่ตำแหน่งเมาส์)")
        return len(rooms)

    def paste_rooms(self, at=None):
        rooms = getattr(self, "_clip", None) or []
        if not rooms:
            return []
        d = self.data()
        fp = B.footprint(rooms)
        if at is not None:
            dx, dy = at[0] - fp[0], at[1] - fp[1]
        else:
            dx, dy = fp[2] - fp[0], 0.0
        g = float(d["settings"]["grid"]) or 0.5
        dx, dy = round(dx / g) * g, round(dy / g) * g
        target = d["floors"][self.floor]["rooms"]
        out = []
        for r in rooms:
            nid = self._next_id(d)
            new = dict(copy.deepcopy(r), id=nid, x=B._r(r["x"] + dx),
                       y=B._r(r["y"] + dy))
            target.append(new)
            out.append(nid)
        self._write(d)
        return out

    def clear_floor(self):
        d = self.data()
        d["floors"][self.floor] = B.new_floor()
        self._write(d)

    # ---- doors, windows, stairs -------------------------------------------------
    def tool(self):
        return self.tool_box.currentData() or "room"

    def items(self, kind, floor=None):
        floor = self.floor if floor is None else floor
        floors = self.data()["floors"]
        if floor < 0 or floor >= len(floors):
            return []
        out = list(floors[floor].get(kind) or [])
        if kind in ("stairs", "fixtures") and self._stair_preview is not None:
            sid, x, y = self._stair_preview
            out = [dict(st, x=x, y=y) if st["id"] == sid else st for st in out]
        return out

    def item_at(self, x, y):
        s = self.data()["settings"]
        best = None
        for op in self.items("openings"):
            dist = ((op["x"] - x) ** 2 + (op["y"] - y) ** 2) ** 0.5
            w = B.opening_size(op, s)[0]
            if dist <= max(0.25, w / 2) and (best is None or dist < best[0]):
                best = (dist, op)
        if best:
            return best[1]
        for fx in self.items("fixtures"):
            w, d = fixture_size(fx)
            if abs(fx["x"] - x) <= max(w / 2, 0.12) and \
                    abs(fx["y"] - y) <= max(d / 2, 0.12):
                return fx
        for stp in self.items("stairs"):
            xs = [q[0] for q in B.stair_rect(stp, s)]
            ys = [q[1] for q in B.stair_rect(stp, s)]
            if min(xs) <= x <= max(xs) and min(ys) <= y <= max(ys):
                return stp
        return None

    def _item_id(self, d, prefix):
        n = 0
        for f in d["floors"]:
            for k in ("openings", "stairs", "fixtures"):
                for it in f.get(k) or []:
                    sid = str(it.get("id", ""))
                    if sid[1:].isdigit():
                        n = max(n, int(sid[1:]))
        return f"{prefix}{n + 1}"

    def place_opening(self, x, y, kind):
        d = self.data()
        f = d["floors"][self.floor]
        hit = B.snap_to_segment(x, y, B.segments(f.get("rooms") or []))
        if hit is None:
            self.status.setText("คลิกให้ใกล้แนวผนัง (ขอบห้อง) เพื่อวางประตู/หน้าต่าง")
            return None
        oid = self._item_id(d, "o")
        style = self.op_style.currentData() if self.tool() == kind else None
        if style is None or CAT.OPENING_TYPES[style]["kind"] != kind:
            style = CAT.DEFAULT_STYLE[kind]
            spec = CAT.OPENING_TYPES[style]
            w, h, sill = spec["w"], spec["h"], spec.get("sill", 0.0)
        else:
            w, h, sill = self.op_w.value(), self.op_h.value(), \
                self.op_sill.value()
        op = {"id": oid, "type": kind, "style": style, "x": hit[0],
              "y": hit[1], "w": w, "h": h}
        if kind == "window":
            op["sill"] = sill
        f.setdefault("openings", []).append(op)
        self._write(d)
        return oid

    def _tool_changed(self):
        t = self.tool()
        self.op_row.setVisible(t in ("door", "window"))
        self.fx_row.setVisible(t == "fixture")
        if t in ("door", "window"):
            self.op_style.blockSignals(True)
            self.op_style.clear()
            for code, spec in CAT.types_of(t):
                self.op_style.addItem(f"{code} — {spec['name']}", code)
            self.op_style.blockSignals(False)
            self._style_changed()
            self.op_sill.setEnabled(t == "window")

    def _style_changed(self):
        spec = CAT.OPENING_TYPES.get(self.op_style.currentData())
        if spec:
            self.op_w.setValue(spec["w"])
            self.op_h.setValue(spec["h"])
            self.op_sill.setValue(spec.get("sill", 0.0))

    def place_fixture(self, x, y, kind=None):
        d = self.data()
        f = d["floors"][self.floor]
        kind = kind or self.fx_type.currentData() or "WC1"
        fid = self._item_id(d, "x")
        f.setdefault("fixtures", []).append(
            {"id": fid, "type": kind, "x": B._r(round(x / 0.05) * 0.05),
             "y": B._r(round(y / 0.05) * 0.05), "dir": 0})
        self._write(d)
        return fid

    def fill_standard_sets(self):
        """Put the standard bathroom set into every bathroom (and a sink
        into every kitchen) on this floor that has no fittings yet."""
        d = self.data()
        f = d["floors"][self.floor]
        fx = f.setdefault("fixtures", [])
        added = 0
        for rm in f.get("rooms") or []:
            name = rm.get("name") or ""
            kit = CAT.BATHROOM_SET if name.startswith("ห้องน้ำ") else \
                CAT.KITCHEN_SET if name.startswith("ห้องครัว") else None
            if not kit:
                continue
            x0, y0 = float(rm["x"]), float(rm["y"])
            w, dd = float(rm["w"]), float(rm["d"])
            if any(x0 <= it["x"] <= x0 + w and y0 <= it["y"] <= y0 + dd
                   for it in fx):
                continue
            for code, fu, fv in kit:
                fx.append({"id": self._item_id(d, "x"), "type": code,
                           "x": B._r(x0 + w * fu), "y": B._r(y0 + dd * fv),
                           "dir": 0})
                added += 1
        if added:
            self._write(d)
        self.status.setText(f"วางสุขภัณฑ์ชุดมาตรฐาน {added} ชิ้น" if added else
                            "ไม่มีห้องน้ำ/ห้องครัวที่ยังว่าง (ตั้งชื่อห้องว่า «ห้องน้ำ» หรือ «ห้องครัว»)")
        return added

    def place_stair(self, x, y):
        d = self.data()
        f = d["floors"][self.floor]
        g = float(d["settings"]["grid"]) or 0.5
        sid = self._item_id(d, "s")
        f.setdefault("stairs", []).append(
            {"id": sid, "x": round(x / (g / 2)) * (g / 2),
             "y": round(y / (g / 2)) * (g / 2), "dir": 1})
        self._write(d)
        n, L, _H = B.stair_geometry({}, d["settings"])
        self.status.setText(f"บันได {n} ลูกตั้ง ระยะราบ {L:.2f} ม. — ลากเพื่อย้าย "
                            "กด R เพื่อหมุนทิศขึ้น")
        return sid

    def preview_stair(self, sid, x, y):
        self._stair_preview = (sid, x, y)
        self.canvas.update()

    def commit_stair(self):
        if self._stair_preview is None:
            return
        sid, x, y = self._stair_preview
        self._stair_preview = None
        d = self.data()
        f = d["floors"][self.floor]
        for st in (f.get("stairs") or []) + (f.get("fixtures") or []):
            if st["id"] == sid:
                st["x"], st["y"] = x, y
        self._write(d)

    def _with_item(self, iid, fn):
        d = self.data()
        f = d["floors"][self.floor]
        for kind in ("openings", "stairs", "fixtures"):
            lst = f.setdefault(kind, [])
            for i, it in enumerate(lst):
                if it["id"] == iid:
                    if fn(lst, i, it) is not False:
                        self._write(d)
                    return

    def delete_item(self, iid):
        def fn(lst, i, it):
            del lst[i]
        self._with_item(iid, fn)

    def rotate_stair(self, iid):
        def fn(lst, i, it):
            it["dir"] = (int(it.get("dir", 1)) + 1) % 4
        self._with_item(iid, fn)

    def edit_item(self, iid):
        s = self.data()["settings"]

        def fn(lst, i, it):
            dlg = ItemDialog(it, s, self)
            if dlg.exec() != QDialog.Accepted:
                return False
            for k, sp in dlg.fields.items():
                it[k] = sp.value()
            if dlg.choice is not None:
                it[dlg.choice[0]] = dlg.choice[1].currentData()
        self._with_item(iid, fn)

    # ---- column points and the member library ---------------------------------
    def node_at(self, x, y, reach=None):
        """The column point nearest (x, y) on this floor, or None."""
        reach = reach if reach is not None else max(0.25, 12.0 /
                                                     self.canvas.scale)
        best = None
        for nx, ny in B.nodes(self.rooms()):
            dist = ((nx - x) ** 2 + (ny - y) ** 2) ** 0.5
            if dist <= reach and (best is None or dist < best[0]):
                best = (dist, (nx, ny))
        return None if best is None else best[1]

    def set_node_marks(self, node, marks):
        d = self.data()
        assign = dict(d.get("assign") or {})
        key = B.node_key(*node)
        rec = {k: v for k, v in (marks or {}).items()
               if v and v != B.ROLE_DEFAULT[k]}
        if rec:
            assign[key] = rec
        else:
            assign.pop(key, None)
        d["assign"] = assign
        self._write(d)

    def edit_node(self, node):
        dlg = NodeDialog(self.data(), node, self)
        if dlg.exec() == QDialog.Accepted:
            self.set_node_marks(node, dlg.marks())

    def reset_node(self, node):
        self.set_node_marks(node, {})

    def set_library(self, mark, spec):
        d = self.data()
        lib = dict(d.get("library") or {})
        lib[mark] = dict(spec)
        d["library"] = lib
        self._write(d)
        self.status.setText(f"บันทึกเบอร์ {mark} แล้ว — กด «สร้าง/อัปเดต» เพื่อปรับโมเดล")

    # ---- standard BOQ -------------------------------------------------------------
    def open_boq(self):
        d = self.data()
        if not any(f.get("rooms") for f in d["floors"]):
            QMessageBox.information(self, TITLE, "ยังไม่มีห้องในผัง — วางห้องก่อน")
            return
        dlg = BoqDialog(self)
        dlg.exec()

    def takeoff_data(self) -> dict:
        import json
        from core.wanic_takeoff import default_data as tk_default
        cur = (getattr(self.app.scene, "plugin_data", {}) or {}).get(
            B.TAKEOFF_KEY)
        return json.loads(json.dumps(cur)) if cur else tk_default()

    def send_standard_boq(self, result=None) -> int:
        """Put the standard BOQ into WANIC ถอดปริมาณ, replacing the lines an
        earlier send made (ids ``std…``)."""
        from core import wanic_quantities as Q
        from core.history import SetPluginDataCommand
        result = result or Q.compute(self.data())
        tk = self.takeoff_data()
        tk["rates"] = [r for r in tk.get("rates", [])
                       if not str(r.get("id", "")).startswith("std")]
        new = Q.to_rates(result)
        tk["rates"] += new
        prov = result.get("province") or ""
        if prov:
            st = tk.setdefault("settings", {})
            if not str(st.get("location") or "").strip():
                st["location"] = ("กรุงเทพมหานคร" if prov == "กรุงเทพมหานคร"
                                  else f"จังหวัด{prov}")
            st["price_ref"] = result.get("price_ref", "")
        self.app.viewport.history.execute(
            SetPluginDataCommand(B.TAKEOFF_KEY, tk))
        n = getattr(self.app.viewport, "notify_scene_changed", None)
        if callable(n):
            n()
        self.status.setText(f"ส่ง BOQ ตามหลักเกณฑ์ {len(new)} รายการเข้า «ถอดปริมาณ» แล้ว")
        return len(new)

    # ---- floors -----------------------------------------------------------------
    def add_floor(self):
        d = self.data()
        d["floors"].append(B.new_floor())
        self.floor = len(d["floors"]) - 1
        self._write(d)

    def copy_floor(self):
        d = self.data()
        nid = int(self._next_id(d)[1:])
        new = []
        for rm in copy.deepcopy(d["floors"][self.floor]["rooms"]):
            new.append(dict(rm, id=f"r{nid}"))
            nid += 1
        d["floors"].insert(self.floor + 1, {"rooms": new, "openings": [],
                                            "stairs": []})
        self.floor += 1
        self._write(d)

    def delete_floor(self):
        d = self.data()
        if len(d["floors"]) <= 1:
            d["floors"] = [B.new_floor()]
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
        s["fascia"] = self.fascia.isChecked()
        s["caps"] = self.caps.isChecked()
        s["tile"] = self.tile.currentData()
        s["tile_color"] = self.tile_color.currentData()
        s["tiles_3d"] = self.tiles_3d.isChecked()
        s["roof"] = self.roof.currentData()
        s["roof_mode"] = self.roof_mode.currentData()
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
            self.fascia.setChecked(bool(s.get("fascia", True)))
            self.caps.setChecked(bool(s.get("caps", True)))
            self.tile.setCurrentIndex(max(self.tile.findData(
                s.get("tile", CAT.DEFAULT_TILE)), 0))
            self.tile_color.setCurrentIndex(max(self.tile_color.findData(
                s.get("tile_color", "ตามวัสดุ")), 0))
            self.tiles_3d.setChecked(bool(s.get("tiles_3d", True)))
            self.roof.setCurrentIndex(max(self.roof.findData(s["roof"]), 0))
            self.roof_mode.setCurrentIndex(
                max(self.roof_mode.findData(s.get("roof_mode", "plan")), 0))
            for k, c in self.steel.items():
                i = c.findText(s[k])
                c.setCurrentIndex(max(i, 0))
            self.library.refresh()
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
        stack, skipped = B.stacked(d)
        msg = (f"สร้างเสร็จ {len(stack)} ชั้น — {B.summary(count)}"
               + (f" (แทนของเดิม {len(old)} ชิ้น)" if old else ""))
        if skipped:
            msg += (f"\nหมายเหตุ: ข้ามชั้นที่ยังไม่มีห้อง {skipped} ชั้น — ชั้นที่มีห้อง"
                    "เรียงต่อกันจากพื้นดินขึ้นไป")
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
