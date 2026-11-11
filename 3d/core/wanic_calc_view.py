# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""Shear force and bending moment diagrams (SFD / BMD), on screen and in
the PDF calculation report (the ออกแบบโครงสร้าง คสล. panel uses it)."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

SFD_COLOR = QColor("#2563EB")
BMD_COLOR = QColor("#DC2626")



def draw_diagrams(p: QPainter, rect: QRectF, res, title: str = "") -> None:
    """The beam, its supports, the SFD under it and the BMD under that."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    f = QFont(p.font())
    f.setPointSizeF(8.5)
    p.setFont(f)
    top = rect.top()
    if title:
        tf = QFont(f)
        tf.setBold(True)
        tf.setPointSizeF(10)
        p.setFont(tf)
        p.setPen(QColor("#111827"))
        p.drawText(QRectF(rect.left(), top, rect.width(), 18), Qt.AlignLeft | Qt.AlignVCenter, title)
        p.setFont(f)
        top += 22
    L = res.xs[-1] if res.xs else 1.0
    left, right = rect.left() + 60, rect.right() - 20
    W = right - left

    def X(x):
        return left + W * x / L if L else left
    # the beam and its supports
    by = top + 14
    p.setPen(QPen(QColor("#374151"), 3))
    p.drawLine(QPointF(left, by), QPointF(right, by))
    x = 0.0
    sup = [0.0]
    for sp in res.spans:
        x += sp.L
        sup.append(x)
    p.setPen(QPen(QColor("#374151"), 1.2))
    p.setBrush(QColor("#9CA3AF"))
    for i, xs in enumerate(sup):
        cx = X(xs)
        p.drawPolygon(QPolygonF([QPointF(cx, by + 2), QPointF(cx - 6, by + 12), QPointF(cx + 6, by + 12)]))
        if i < len(res.spans):
            sp = res.spans[i]
            p.setPen(QColor("#374151"))
            p.drawText(QRectF(X(xs), by - 16, X(sup[i + 1]) - X(xs), 12), Qt.AlignCenter,
                       f"w = {sp.w:,.0f} กก./ม. · L = {sp.L:.2f} ม.")
            p.setPen(QPen(QColor("#374151"), 1.2))
    h_ = (rect.bottom() - by - 30) / 2
    for k, (vals, color, name, unit) in enumerate(((res.V, SFD_COLOR, "SFD แรงเฉือน", "กก."),
                                                    (res.M, BMD_COLOR, "BMD โมเมนต์ดัด", "กก.-ม."))):
        y0 = by + 24 + k * (h_ + 6)
        mid = y0 + h_ / 2
        big = max((abs(v) for v in vals), default=1.0) or 1.0
        scale = (h_ / 2 - 12) / big
        p.setPen(QPen(QColor("#D1D5DB"), 1))
        p.drawLine(QPointF(left, mid), QPointF(right, mid))
        p.setPen(color)
        p.drawText(QRectF(rect.left(), y0, 56, h_), Qt.AlignVCenter | Qt.AlignLeft, name.split()[0])
        # BMD drawn sagging-down (the engineers' convention: on the tension side)
        sgn = -1 if k == 0 else 1
        pts = [QPointF(X(x), mid + sgn * v * scale * (1 if k == 0 else 1)) for x, v in zip(res.xs, vals)]
        poly = QPolygonF([QPointF(X(res.xs[0]), mid)] + pts + [QPointF(X(res.xs[-1]), mid)])
        fill = QColor(color)
        fill.setAlpha(45)
        p.setBrush(QBrush(fill))
        p.setPen(QPen(color, 1.6))
        p.drawPolygon(poly)
        # the extremes labelled
        for pick in (max, min):
            i = pick(range(len(vals)), key=lambda j: vals[j])
            v = vals[i]
            if abs(v) < big * 0.05:
                continue
            q = pts[i]
            p.setPen(color)
            p.drawText(QRectF(q.x() - 60, q.y() + (-16 if (sgn * v) < 0 else 2), 120, 14), Qt.AlignCenter,
                       f"{v:,.0f} {unit}")
    p.restore()


class DiagramWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.res = None
        self.title = ""
        self.setMinimumHeight(240)

    def show_result(self, res, title=""):
        self.res, self.title = res, title
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("white"))
        if self.res is None:
            p.setPen(QColor("#6B7280"))
            p.drawText(self.rect(), Qt.AlignCenter, "เลือกคานหรือชิ้นส่วนหลังคาในตาราง เพื่อดูแผนภาพแรงเฉือน (SFD) "
                                                    "และโมเมนต์ดัด (BMD)")
            return
        draw_diagrams(p, QRectF(self.rect()).adjusted(8, 6, -8, -6), self.res, self.title)
        p.end()


def report_pdf(res, data, path) -> None:
    """รายการคำนวณโครงสร้าง: the basis, every member's check, and the
    diagrams of every beam and roof member, on A4 pages."""
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter
    w = QPdfWriter(str(path))
    w.setResolution(150)
    w.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait,
                                QMarginsF(15, 15, 15, 15), QPageLayout.Millimeter))
    p = QPainter(w)
    page = QRectF(0, 0, w.width(), w.height())
    b_ = res["basis"]
    f = QFont("Laksaman")
    f.setFamilies(["TH Sarabun New", "TH SarabunPSK", "Laksaman", "Tahoma"])
    f.setPointSizeF(10)
    p.setFont(f)
    y = 0.0

    def text(t, bold=False, size=10.0, color="#111827"):
        nonlocal y
        ff = QFont(f)
        ff.setBold(bold)
        ff.setPointSizeF(size)
        p.setFont(ff)
        flags = int(Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap)
        box = p.boundingRect(QRectF(0, 0, page.width(), 10000), flags, t)
        if y + box.height() > page.height():
            w.newPage()
            y = 0.0
        p.setPen(QColor(color))
        p.drawText(QRectF(0, y, page.width(), box.height() + 2), flags, t)
        y += box.height() + 3
    text("รายการคำนวณโครงสร้าง (WANICNSURVEY · ออกแบบโครงสร้าง คสล.)", True, 14)
    text(f"วิธีออกแบบ {b_['method']} (คอนกรีต) · ASD (โครงหลังคาเหล็ก/ไม้) · fc′ {b_['fc']:g} กก./ตร.ซม. · "
         f"SD40 / SR24 · SS400 Fy {b_['fy_steel']:g}")
    text(f"น้ำหนักบรรทุกจร พื้น {b_['ll_floor']:g} · หลังคา {b_['ll_roof']:g} กก./ตร.ม. · ผนัง {b_['wall_kg_m2']:g} "
         f"กก./ตร.ม. · ดินรับได้ {b_['soil']:g} ตัน/ตร.ม. · เข็ม {b_['pile_cap']:g} ตัน/ต้น")
    text("U = 1.4D + 1.7L (SDM) · คานต่อเนื่องคำนวณด้วยวิธี stiffness · พื้นสองทางแบบแถบ (Marcus)")
    text("เอกสารนี้เป็นเครื่องมือช่วยคำนวณ ต้องให้วิศวกรโยธาผู้มีใบอนุญาตตรวจสอบและลงนามรับรองก่อนก่อสร้าง",
         color="#B45309")
    y += 8
    names = {"roof": "โครงหลังคา", "slab": "พื้น", "beam": "คาน", "column": "เสา", "footing": "ฐานราก / เสาเข็ม"}
    for g in ("roof", "slab", "beam", "column", "footing"):
        ms = [m for m in res["members"] if m.group == g]
        if not ms:
            continue
        text(names[g], True, 12)
        for m in ms:
            text(f"{'✓' if m.ok else '✗'} {m.name}: {m.demand} / {m.capacity} → {m.ratio:.2f} "
                 f"({'ผ่าน' if m.ok else 'ไม่ผ่าน'})", color="#15803D" if m.ok else "#B91C1C", size=9)
        y += 6
    for m in res["members"]:
        if m.diagram is None:
            continue
        hgt = page.height() * 0.30
        if y + hgt > page.height():
            w.newPage()
            y = 0.0
        p.setFont(f)
        draw_diagrams(p, QRectF(0, y, page.width(), hgt), m.diagram, m.name)
        y += hgt + 10
    p.end()
