# -*- coding: utf-8 -*-
"""Clickable structural plan of one level.

Click a column, beam or slab panel to remove it; click its dashed outline
to bring it back. Right-click a panel to add a secondary beam or a stair,
an edge beam to add a cantilever slab, or an edge column to add a
cantilever beam. After a calculation the elements are coloured by result
(green = passes, red = fails) and carry their marks.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QInputDialog, QMenu, QMessageBox

S = 60.0                      # pixels per metre
KIND, KEY = 0, 1              # item data slots

C_GRID = QColor("#9aa5b1")
C_PANEL = QColor(120, 170, 220, 70)
C_BEAM = QColor("#2b5797")
C_COL = QColor("#333333")
C_OK = QColor("#2e7d32")
C_NG = QColor("#c62828")
C_GONE = QColor("#b0b0b0")


class PlanView(QGraphicsView):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setBackgroundBrush(QColor("#fbfbfb"))
        self.building = None
        self.level = None
        self.result = None

    # -- data -------------------------------------------------------------------
    def set_model(self, building, level: str | None = None):
        self.building = building
        names = [lv.name for lv in building.levels]
        self.level = level if level in names else (names[0] if names else None)
        self.rebuild()

    def set_level(self, name: str):
        self.level = name
        self.rebuild()

    def set_result(self, result):
        self.result = result
        self.rebuild()

    # -- drawing ---------------------------------------------------------------
    @staticmethod
    def _p(x, y) -> QPointF:
        return QPointF(x * S, -y * S)

    def _status(self, kind: str, key: str):
        """(colour, mark) of an element from the last result, if any."""
        r = self.result
        if r is None:
            return None, ""
        lvl, _, name = key.partition(":")
        if kind == "beam":
            for x in r.beams:
                if x.level == lvl and f"{lvl}:{x.span}" == key:
                    return (C_OK if x.ok else C_NG), x.mark
        elif kind == "panel":
            parts = [s for s in r.slabs if s.level == lvl and (s.panel == name or s.panel.startswith(name + "·"))]
            if parts:
                return (C_OK if all(s.ok for s in parts) else C_NG), "/".join(dict.fromkeys(s.mark for s in parts))
        elif kind in ("sub", "cant"):
            for x in (r.beams if kind == "sub" else r.slabs):
                if x.level == lvl and (x.span if kind == "sub" else x.panel) == name:
                    return (C_OK if x.ok else C_NG), x.mark
        elif kind == "cbeam":
            for x in r.beams:
                if x.kind == "cantilever" and f"{x.level}:{x.span}" == key:
                    return (C_OK if x.ok else C_NG), x.mark
        elif kind == "stair":
            for st in r.stairs:
                if st.name == key:
                    return (C_OK if st.ok else C_NG), st.mark
        elif kind == "node":
            for c in r.columns:
                if c.node == key and c.segment.endswith(self.level or ""):
                    return (C_OK if c.ok else C_NG), c.mark
        return None, ""

    def rebuild(self):
        sc = self.scene()
        sc.clear()
        b = self.building
        if b is None or self.level is None:
            return
        xs, ys = b.xs, b.ys
        lvl = self.level
        font = QFont()
        font.setPointSizeF(8)
        # grid and bubbles
        pen = QPen(C_GRID, 1, Qt.DashDotLine)
        for i, x in enumerate(xs):
            sc.addLine(x * S, S * 0.8, x * S, -(ys[-1] + 0.8) * S, pen)
            sc.addEllipse(QRectF(x * S - 11, -(ys[-1] + 1.4) * S - 11, 22, 22), QPen(C_GRID))
            t = sc.addSimpleText(b.x_name(i), font)
            t.setPos(x * S - 4, -(ys[-1] + 1.4) * S - 8)
        for j, y in enumerate(ys):
            sc.addLine(-0.8 * S, -y * S, (xs[-1] + 0.8) * S, -y * S, pen)
            sc.addEllipse(QRectF(-1.4 * S - 11, -y * S - 11, 22, 22), QPen(C_GRID))
            t = sc.addSimpleText(b.y_name(j), font)
            t.setPos(-1.4 * S - 4, -y * S - 8)
        for a, c in zip(xs, xs[1:]):
            t = sc.addSimpleText(f"{c - a:.2f}", font)
            t.setPos((a + c) / 2 * S - 12, S * 0.9)
        for a, c in zip(ys, ys[1:]):
            t = sc.addSimpleText(f"{c - a:.2f}", font)
            t.setPos((xs[-1] + 0.9) * S, -(a + c) / 2 * S - 6)
        # panels
        present = set(b.panels(lvl))
        for j in range(len(ys) - 1):
            for i in range(len(xs) - 1):
                if not all(b.has_node(*n) for n in ((i, j), (i + 1, j), (i, j + 1), (i + 1, j + 1))):
                    continue
                key = b.panel_key(lvl, i, j)
                rect = QRectF(self._p(xs[i], ys[j + 1]), self._p(xs[i + 1], ys[j])).adjusted(6, 6, -6, -6)
                if (i, j) in present:
                    colour, mark = self._status("panel", key)
                    fill = QColor(colour) if colour else C_PANEL
                    fill.setAlpha(60)
                    it = sc.addRect(rect, QPen(Qt.NoPen), QBrush(fill))
                    if mark:
                        t = sc.addSimpleText(mark, font)
                        t.setPos(rect.center() - QPointF(8, 6))
                elif key in b.skip_panels:
                    it = sc.addRect(rect, QPen(C_GONE, 1, Qt.DashLine), QBrush(Qt.NoBrush))
                else:
                    continue
                it.setData(KIND, "panel")
                it.setData(KEY, key)
                it.setToolTip(f"พื้น {key}")
        # secondary beams and cantilever slabs
        lv = b.level(lvl)
        for i, j in present:
            sub = b.sub_beam(lv, i, j)
            if not sub:
                continue
            d, f = sub
            if d == "x":
                yy = ys[j] + f * (ys[j + 1] - ys[j])
                p1, p2 = self._p(xs[i], yy), self._p(xs[i + 1], yy)
            else:
                xx = xs[i] + f * (xs[i + 1] - xs[i])
                p1, p2 = self._p(xx, ys[j]), self._p(xx, ys[j + 1])
            key = f"{lvl}:{b.panel_name(i, j)}:{d}"
            colour, mark = self._status("sub", key)
            it = sc.addLine(p1.x(), p1.y(), p2.x(), p2.y(), QPen(colour or C_BEAM, 5, Qt.DashLine, Qt.FlatCap))
            it.setData(KIND, "sub")
            it.setData(KEY, key)
            it.setToolTip(f"คานซอย {key} (คลิกเพื่อลบ)")
            it.setZValue(2)
            if mark:
                t = sc.addSimpleText(mark, font)
                t.setPos((p1 + p2) / 2 + QPointF(4, 4))
        if lv is not None and lv.slab == "suspended":
            for a, c, length, (dx, dy) in b.cantilevers(lv):
                (x0, y0), (x1, y1) = (xs[a[0]], ys[a[1]]), (xs[c[0]], ys[c[1]])
                r0 = self._p(min(x0, x1, x0 + dx * length), max(y0, y1, y0 + dy * length))
                r1 = self._p(max(x0, x1, x0 + dx * length), min(y0, y1, y0 + dy * length))
                key = f"{lvl}:{b.node_name(*a)}-{b.node_name(*c)} ยื่น"
                colour, mark = self._status("cant", key)
                fill = QColor(colour) if colour else QColor(C_PANEL)
                fill.setAlpha(80)
                it = sc.addRect(QRectF(r0, r1), QPen(C_BEAM, 1, Qt.DashLine), QBrush(fill))
                it.setData(KIND, "cant")
                it.setData(KEY, f"{b.node_name(*a)}-{b.node_name(*c)}")
                it.setToolTip(f"พื้นยื่น {length:.2f} ม. (คลิกเพื่อลบ)")
                t = sc.addSimpleText(f"{mark}  ยื่น {length:.2f}".strip(), font)
                t.setPos(QRectF(r0, r1).center() - QPointF(18, 6))
        # stairs (on their bottom and top levels)
        from ..structure.stairs import geometry, tread_lines
        for st in b.stairs:
            g = geometry(b, st)
            if g is None or lvl not in (st.level, b.levels[g.li1].name):
                continue
            colour, mark = self._status("stair", st.name)
            pen = QPen(colour or QColor("#8d6e63"), 1.2)
            for pa, pc in tread_lines(b, g):
                it = sc.addLine(pa[0] * S, -pa[1] * S, pc[0] * S, -pc[1] * S, pen)
                it.setData(KIND, "stair")
                it.setData(KEY, st.name)
                it.setToolTip(f"บันได {st.name} (คลิกเพื่อลบ)")
                it.setZValue(1)
            cx, cy = (xs[g.i] + xs[g.i + 1]) / 2, (ys[g.j] + ys[g.j + 1]) / 2
            t = sc.addSimpleText(f"{st.name} {'ขึ้น' if lvl == st.level else 'ลง'}", font)
            t.setPos(self._p(cx, cy) - QPointF(14, 6))
            t.setZValue(1)
        # cantilever beams
        lv_obj = b.level(lvl)
        for node, (dx, dy), length, _p, _w in (b.cant_beams(lv_obj) if lv_obj else []):
            x0, y0 = xs[node[0]], ys[node[1]]
            p1, p2 = self._p(x0, y0), self._p(x0 + dx * length, y0 + dy * length)
            d_name = {(1, 0): "x", (-1, 0): "-x", (0, 1): "y", (0, -1): "-y"}[(dx, dy)]
            key = f"{lvl}:{b.node_name(*node)}{d_name}"
            colour, mark = self._status("cbeam", key)
            it = sc.addLine(p1.x(), p1.y(), p2.x(), p2.y(), QPen(colour or C_BEAM, 7, Qt.SolidLine, Qt.FlatCap))
            it.setData(KIND, "cbeam")
            it.setData(KEY, key)
            it.setToolTip(f"คานยื่น {length:.2f} ม. (คลิกเพื่อลบ)")
            it.setZValue(2)
            t = sc.addSimpleText(f"{mark} ยื่น {length:.2f}".strip(), font)
            t.setPos((p1 + p2) / 2 + QPointF(6, -6))
        # beams
        for j, y in enumerate(ys):
            for i in range(len(xs) - 1):
                self._beam(sc, (i, j), (i + 1, j), font)
        for i, x in enumerate(xs):
            for j in range(len(ys) - 1):
                self._beam(sc, (i, j), (i, j + 1), font)
        # columns
        cw, ch = b.column_width, b.column_depth
        for j, y in enumerate(ys):
            for i, x in enumerate(xs):
                name = b.node_name(i, j)
                w, h = max(cw, 0.25) * S, max(ch, 0.25) * S
                rect = QRectF(x * S - w / 2, -y * S - h / 2, w, h)
                if b.has_node(i, j):
                    colour, mark = self._status("node", name)
                    it = sc.addRect(rect, QPen(Qt.black), QBrush(colour or C_COL))
                    if mark:
                        t = sc.addSimpleText(mark, font)
                        t.setPos(rect.topRight() + QPointF(2, -12))
                else:
                    it = sc.addRect(rect, QPen(C_GONE, 1, Qt.DashLine), QBrush(Qt.NoBrush))
                it.setData(KIND, "node")
                it.setData(KEY, name)
                it.setToolTip(f"เสา {name}")
                it.setZValue(3)
        sc.setSceneRect(sc.itemsBoundingRect().adjusted(-20, -20, 20, 20))
        self.fitInView(sc.sceneRect(), Qt.KeepAspectRatio)

    def _beam(self, sc, a, c, font):
        b = self.building
        if not (b.has_node(*a) and b.has_node(*c)):
            return
        key = b.beam_key(self.level, a, c)
        p1, p2 = self._p(b.xs[a[0]], b.ys[a[1]]), self._p(b.xs[c[0]], b.ys[c[1]])
        if b.has_beam(self.level, a, c):
            colour, mark = self._status("beam", key)
            it = sc.addLine(p1.x(), p1.y(), p2.x(), p2.y(), QPen(colour or C_BEAM, 7, Qt.SolidLine, Qt.FlatCap))
            if mark:
                t = sc.addSimpleText(mark, font)
                mid = (p1 + p2) / 2
                t.setPos(mid + (QPointF(-8, -16) if p1.y() == p2.y() else QPointF(6, -6)))
        else:
            it = sc.addLine(p1.x(), p1.y(), p2.x(), p2.y(), QPen(C_GONE, 3, Qt.DashLine))
        it.setData(KIND, "beam")
        it.setData(KEY, key)
        it.setToolTip(f"คาน {key}")
        it.setZValue(2)

    # -- interaction -----------------------------------------------------------
    def item_at(self, pos):
        for it in self.items(pos):
            if it.data(KIND):
                return it
        return None

    def toggle(self, kind: str, key: str):
        b = self.building
        lv = b.level(self.level)
        if kind == "sub":
            panel = key.split(":")[1]
            i, j = self._panel_ij(panel)
            b.toggle_sub_beam(lv, i, j, "")
        elif kind == "cant":
            na, nc = key.split("-")
            b.toggle_cantilever(lv, b.parse_node(na), b.parse_node(nc), None)
        elif kind == "stair":
            b.stairs[:] = [st for st in b.stairs if st.name != key]
        elif kind == "cbeam":
            spec = key.split(":", 1)[1]
            k = next(n for n, ch in enumerate(spec) if ch in "-xy" and n > 0)
            b.toggle_cant_beam(lv, b.parse_node(spec[:k]), spec[k:], None)
        else:
            b.toggle(kind, key)
        self._done()

    def _done(self):
        self.result = None
        self.rebuild()
        self.changed.emit()

    def _panel_ij(self, panel: str):
        xpart, ypart = panel.split("/")
        return int(xpart.split("-")[0]) - 1, ord(ypart.split("-")[0]) - ord("A")

    def add_sub_beam(self, i: int, j: int, direction: str, fraction: float = 0.5):
        self.building.toggle_sub_beam(self.building.level(self.level), i, j, direction, fraction)
        self._done()

    def add_cantilever(self, a, c, length: float):
        self.building.toggle_cantilever(self.building.level(self.level), a, c, length)
        self._done()

    def add_stair(self, i: int, j: int, kind: str = "landing", direction: str = "y", tread: float = 0.25):
        from ..structure.building import Stair
        b = self.building
        n = 1
        while any(st.name == f"ST{n}" for st in b.stairs):
            n += 1
        b.stairs[:] = [st for st in b.stairs if not (b.stair_ij(st) == (i, j) and st.level == self.level)]
        b.stairs.append(Stair(f"ST{n}", b.panel_name(i, j), self.level, direction, kind, tread))
        self._done()

    def add_cant_beam(self, node, direction: str, length: float, tip: float = 0.0, wall: bool = False):
        self.building.toggle_cant_beam(self.building.level(self.level), node, direction, length, tip, wall)
        self._done()

    def _ask_stair(self, i, j):
        kinds = ["สองช่วงมีชานพัก (คานบันได BT)", "ช่วงเดียว"]
        k, ok = QInputDialog.getItem(self, "บันได", "ชนิด", kinds, 0, False)
        if not ok:
            return
        dirs = {"ขึ้นไปทาง +Y": "y", "ขึ้นไปทาง −Y": "-y", "ขึ้นไปทาง +X": "x", "ขึ้นไปทาง −X": "-x"}
        d, ok = QInputDialog.getItem(self, "บันได", "ทิศทางช่วงแรก", list(dirs), 0, False)
        if not ok:
            return
        t, ok = QInputDialog.getDouble(self, "บันได", "ลูกนอน (ม.)", 0.25, 0.20, 0.40, 3)
        if ok:
            self.add_stair(i, j, "landing" if k == kinds[0] else "straight", dirs[d], t)

    def _ask_cant_beam(self, node, direction):
        length, ok = QInputDialog.getDouble(self, "คานยื่น", "ยื่นจากศูนย์เสา (ม.)", 1.5, 0.3, 4.0, 2)
        if not ok:
            return
        tip, ok = QInputDialog.getDouble(self, "คานยื่น", "แรงจุดที่ปลาย (กก.) เช่นคานขอบ", 0.0, 0.0, 20000, 0)
        if not ok:
            return
        wall = QMessageBox.question(self, "คานยื่น", "มีผนังบนคานยื่นหรือไม่") == QMessageBox.Yes
        self.add_cant_beam(node, direction, length, tip, wall)

    def contextMenuEvent(self, event):
        it = self.item_at(event.pos())
        b = self.building
        if it is None or b is None:
            return
        kind, key = it.data(KIND), it.data(KEY)
        menu = QMenu(self)
        lv = b.level(self.level)
        if kind == "panel" and key not in b.skip_panels:
            i, j = self._panel_ij(key.split(":")[1])
            menu.addAction("เพิ่มคานซอยแนว X (กลางแผ่น)", lambda: self.add_sub_beam(i, j, "x"))
            menu.addAction("เพิ่มคานซอยแนว Y (กลางแผ่น)", lambda: self.add_sub_beam(i, j, "y"))
            if b.sub_beam(lv, i, j):
                menu.addAction("ลบคานซอย", lambda: self.add_sub_beam(i, j, ""))
            if self.level != b.levels[-1].name:
                menu.addAction("เพิ่มบันไดขึ้นชั้นถัดไป…", lambda: self._ask_stair(i, j))
            menu.addAction("ลบแผ่นพื้น (ช่องเปิด)", lambda: self.toggle("panel", key))
        elif kind == "beam" and lv is not None and lv.slab == "suspended":
            na, nc = key.split(":")[1].split("-")
            a, c = b.parse_node(na), b.parse_node(nc)
            if b.has_beam(lv.name, a, c) and b.is_perimeter(a, c, lv.name):
                def ask():
                    length, ok = QInputDialog.getDouble(self, "พื้นยื่น", "ยื่นออกจากคาน (ม.)", 1.5, 0.3, 3.0, 2)
                    if ok:
                        self.add_cantilever(a, c, length)
                menu.addAction("เพิ่มพื้นยื่น (ระเบียง)…", ask)
                menu.addAction("ลบพื้นยื่น", lambda: self.add_cantilever(a, c, None))
            menu.addAction("ลบคาน", lambda: self.toggle("beam", key))
        elif kind == "stair":
            menu.addAction("ลบบันได", lambda: self.toggle("stair", key))
        elif kind == "node":
            node = b.parse_node(key)
            if lv is not None and lv.slab in ("suspended", "roof") and b.has_node(*node):
                names = {"x": "+X", "-x": "−X", "y": "+Y", "-y": "−Y"}
                for d in b.outward_dirs(node):
                    menu.addAction(f"เพิ่มคานยื่นทาง {names[d]}…", lambda d=d: self._ask_cant_beam(node, d))
            menu.addAction("ลบ/คืนเสา", lambda: self.toggle("node", key))
        if not menu.isEmpty():
            menu.exec(event.globalPos())

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        it = self.item_at(event.position().toPoint())
        if it is not None and self.building is not None:
            self.toggle(it.data(KIND), it.data(KEY))
            return
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        f = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(f, f)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.scene() and not self.scene().sceneRect().isEmpty():
            self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)
