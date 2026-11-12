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



CAP_COLOR = QColor("#15803D")
VC_COLOR = QColor("#B45309")


def _zero_points(xs, vals, tol=1e-6):
    """x where the values change sign (linear between stations)."""
    out = []
    for i in range(1, len(vals)):
        a, b = vals[i - 1], vals[i]
        if (a > tol and b < -tol) or (a < -tol and b > tol):
            x = xs[i - 1] + (xs[i] - xs[i - 1]) * a / (a - b)
            out.append(x)
    return out


def draw_diagrams(p: QPainter, rect: QRectF, res, title: str = "") -> None:
    """Load diagram (loads, supports, reactions), SFD and BMD drawn as the
    engineers do: shear positive above the axis; the bending moment on the
    tension side (sagging below, hogging above); the maxima with their
    positions, the points of zero shear and of contraflexure; and the
    member's capacity — φMn (bottom bars / top bars) and φVn, φVc — as
    dashed lines, so the diagram shows where the material carries it."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    f = QFont(p.font())
    f.setPointSizeF(8.0)
    p.setFont(f)
    top = rect.top()
    caps = getattr(res, "caps", None) or {}
    if title:
        tf = QFont(f)
        tf.setBold(True)
        tf.setPointSizeF(9.5)
        p.setFont(tf)
        p.setPen(QColor("#111827"))
        p.drawText(QRectF(rect.left(), top, rect.width(), 16), Qt.AlignLeft | Qt.AlignVCenter, title)
        p.setFont(f)
        top += 18
    if caps:
        p.setPen(QPen(CAP_COLOR, 1.2, Qt.DashLine))
        lx = rect.right() - 330
        p.drawLine(QPointF(lx, top + 6), QPointF(lx + 22, top + 6))
        p.setPen(CAP_COLOR)
        p.drawText(QRectF(lx + 26, top, 160, 12), Qt.AlignLeft | Qt.AlignVCenter,
                   f"กำลังที่รับได้ ({caps.get('lab_M', 'φMn')} / {caps.get('lab_V', 'φVn')})" if "V" in caps
                   else f"กำลังที่รับได้ ({caps.get('lab_M', 'Ma')})")
        if "Vc" in caps:
            p.setPen(QPen(VC_COLOR, 1.0, Qt.DotLine))
            p.drawLine(QPointF(lx + 190, top + 6), QPointF(lx + 212, top + 6))
            p.setPen(VC_COLOR)
            p.drawText(QRectF(lx + 216, top, 120, 12), Qt.AlignLeft | Qt.AlignVCenter,
                       f"{caps.get('lab_Vc', 'φVc')} คอนกรีตรับเฉือน")
        top += 14
    L = res.xs[-1] if res.xs else 1.0
    left, right = rect.left() + 62, rect.right() - 24
    W = right - left

    def X(x):
        return left + W * x / L if L else left
    # ---- load diagram: the uniform loads, the point loads, the supports, the reactions
    by = top + 34
    x = 0.0
    sup = [0.0]
    for sp in res.spans:
        x += sp.L
        sup.append(x)
    p.setPen(QPen(QColor("#374151"), 3))
    p.drawLine(QPointF(left, by), QPointF(right, by))
    p.setPen(QPen(QColor("#2563EB"), 1))
    for i, sp in enumerate(res.spans):
        xa, xb = X(sup[i]), X(sup[i + 1])
        p.drawLine(QPointF(xa, by - 12), QPointF(xb, by - 12))
        n = max(2, int((xb - xa) / 18))
        for k in range(n + 1):
            ax = xa + (xb - xa) * k / n
            p.drawLine(QPointF(ax, by - 12), QPointF(ax, by - 2))
            p.drawLine(QPointF(ax, by - 2), QPointF(ax - 2, by - 5))
            p.drawLine(QPointF(ax, by - 2), QPointF(ax + 2, by - 5))
        p.drawText(QRectF(xa, by - 26, xb - xa, 12), Qt.AlignCenter, f"w = {sp.w:,.0f} กก./ม. · L = {sp.L:.2f} ม.")
        for a_, P in getattr(sp, "P", []) or []:
            px = X(sup[i] + a_)
            p.setPen(QPen(QColor("#DC2626"), 1.6))
            p.drawLine(QPointF(px, by - 24), QPointF(px, by - 2))
            p.drawText(QRectF(px + 2, by - 36, 90, 12), Qt.AlignLeft, f"P = {P:,.0f} กก.")
            p.setPen(QPen(QColor("#2563EB"), 1))
    p.setPen(QPen(QColor("#374151"), 1.2))
    p.setBrush(QColor("#9CA3AF"))
    for i, xs_ in enumerate(sup):
        cx = X(xs_)
        p.drawPolygon(QPolygonF([QPointF(cx, by + 2), QPointF(cx - 6, by + 11), QPointF(cx + 6, by + 11)]))
        if i < len(res.reactions):
            p.setPen(QColor("#111827"))
            p.drawText(QRectF(cx - 45, by + 11, 90, 12), Qt.AlignCenter, f"R{i + 1} = {res.reactions[i]:,.0f}")
            p.setPen(QPen(QColor("#374151"), 1.2))
    p.setBrush(Qt.NoBrush)
    # ---- SFD and BMD
    h_ = (rect.bottom() - by - 50) / 2
    rows = ((res.V, SFD_COLOR, "SFD", "แรงเฉือน (กก.)", -1, "V"),
            (res.M, BMD_COLOR, "BMD", "โมเมนต์ดัด (กก.-ม.)", 1, "M"))
    for k, (vals, color, name, unit, sgn, key) in enumerate(rows):
        y0 = by + 28 + k * (h_ + 6)
        mid = y0 + h_ / 2
        lines = []
        if key == "V" and "V" in caps:
            lines = [(caps["V"], CAP_COLOR, Qt.DashLine, caps.get("lab_V", "φVn")),
                     (-caps["V"], CAP_COLOR, Qt.DashLine, ""),
                     (caps.get("Vc", 0), VC_COLOR, Qt.DotLine, caps.get("lab_Vc", "φVc")),
                     (-caps.get("Vc", 0), VC_COLOR, Qt.DotLine, "")]
        elif key == "M" and "M+" in caps:
            lines = [(caps["M+"], CAP_COLOR, Qt.DashLine, f"{caps.get('lab_M', 'φMn')} ล่าง"),
                     (-caps["M-"], CAP_COLOR, Qt.DashLine, f"{caps.get('lab_M', 'φMn')} บน")]
        big = max([abs(v) for v in vals] + [abs(c) for c, *_r in lines if c] + [1.0])
        scale = (h_ / 2 - 10) / big
        p.setPen(QPen(QColor("#9CA3AF"), 1))
        p.drawLine(QPointF(left, mid), QPointF(right, mid))
        p.setPen(color)
        p.drawText(QRectF(rect.left(), y0, 58, h_ / 2), Qt.AlignBottom | Qt.AlignLeft, name)
        sf = QFont(f)
        sf.setPointSizeF(7)
        p.setFont(sf)
        p.drawText(QRectF(rect.left(), mid + 2, 60, h_ / 2), Qt.AlignTop | Qt.AlignLeft, unit)
        p.setFont(f)
        pts = [QPointF(X(x_), mid + sgn * v * scale) for x_, v in zip(res.xs, vals)]
        poly = QPolygonF([QPointF(X(res.xs[0]), mid)] + pts + [QPointF(X(res.xs[-1]), mid)])
        fill = QColor(color)
        fill.setAlpha(45)
        p.setBrush(QBrush(fill))
        p.setPen(QPen(color, 1.6))
        p.drawPolygon(poly)
        p.setBrush(Qt.NoBrush)
        for c, col, style, lab in lines:
            if not c:
                continue
            yy = mid + sgn * c * scale
            p.setPen(QPen(col, 1.1, style))
            p.drawLine(QPointF(left, yy), QPointF(right, yy))
            if lab:
                p.setPen(col)
                p.drawText(QRectF(right - 150, yy + (-13 if sgn * c < 0 else 1), 150, 12),
                           Qt.AlignRight | Qt.AlignVCenter, f"{lab} = {abs(c):,.0f}")
        # extremes with their positions
        for pick in (max, min):
            i = pick(range(len(vals)), key=lambda j: vals[j])
            v = vals[i]
            if abs(v) < big * 0.03:
                continue
            q = pts[i]
            p.setPen(color)
            tag = ("Vmax" if key == "V" else ("M+max" if v > 0 else "M−max"))
            lx_ = min(max(q.x() - 75, left - 40), right - 150)
            p.drawText(QRectF(lx_, q.y() + (-14 if (sgn * v) < 0 else 2), 150, 12), Qt.AlignCenter,
                       f"{tag} {v:,.0f} @ x = {res.xs[i]:.2f} ม.")
        # zero shear (the maximum moment) / contraflexure (moment changes sign)
        p.setPen(QPen(QColor("#6B7280"), 1))
        for zx in _zero_points(res.xs, vals):
            cx = X(zx)
            p.drawLine(QPointF(cx, mid - 4), QPointF(cx, mid + 4))
            p.drawText(QRectF(cx - 40, mid + 4 if key == "V" else mid - 16, 80, 11), Qt.AlignCenter,
                       f"{'V = 0' if key == 'V' else 'M = 0'} @ {zx:.2f}")
    # the check line under the diagrams
    if caps:
        msgs = []
        if "M+" in caps and caps["M+"]:
            msgs.append(f"M+u / {caps.get('lab_M', 'φMn')} = {max(res.Mmax, 0) / caps['M+']:.2f}")
        if "M-" in caps and caps["M-"] and res.Mmin < 0:
            msgs.append(f"M−u / {caps.get('lab_M', 'φMn')} = {-res.Mmin / caps['M-']:.2f}")
        if "V" in caps and caps["V"]:
            msgs.append(f"Vu / {caps.get('lab_V', 'φVn')} = {res.Vmax / caps['V']:.2f}")
        if "defl" in caps:
            dd, lim = caps["defl"]
            msgs.append(f"แอ่น {dd * 1000:.1f} / {lim * 1000:.1f} มม.")
        okk = all(float(m.split("= ")[-1]) <= 1.0 for m in msgs if "/" in m and "แอ่น" not in m)
        p.setPen(QColor("#15803D") if okk else QColor("#B91C1C"))
        p.drawText(QRectF(left, rect.bottom() - 12, W, 12), Qt.AlignLeft | Qt.AlignVCenter,
                   ("✓ " if okk else "✗ ") + "   ·   ".join(msgs) + "   (≤ 1.00 ผ่าน — แผนภาพต้องอยู่ภายในเส้นกำลัง)"
                   + (f"   ·   {res.reserve}" if getattr(res, "reserve", "") else ""))
    p.restore()


def draw_pm(p: QPainter, rect: QRectF, res, title: str = "") -> None:
    """A column's P-M interaction curve and the load point (Mu, Pu)."""
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
        p.drawText(QRectF(rect.left(), top, rect.width(), 18), Qt.AlignLeft | Qt.AlignVCenter,
                   title + " — แผนภาพ P-M")
        p.setFont(f)
        top += 22
    Mx = max(max(m for m, _ in res.curve), abs(res.Mu)) * 1.15 or 1.0
    Px = max(max(q for _, q in res.curve), res.Pu) * 1.10 or 1.0
    left, bottom = rect.left() + 70, rect.bottom() - 26
    W, H = rect.right() - 20 - left, bottom - top - 6

    def P(m, q):
        return QPointF(left + W * m / Mx, bottom - H * q / Px)
    p.setPen(QPen(QColor("#9CA3AF"), 1))
    p.drawLine(P(0, 0), P(Mx, 0))
    p.drawLine(P(0, 0), P(0, Px))
    p.setPen(QColor("#374151"))
    p.drawText(QRectF(left, bottom + 4, W, 16), Qt.AlignRight, "φMn (กก.-ม.)")
    p.drawText(QRectF(rect.left(), top, 66, 16), Qt.AlignLeft, "φPn (ตัน)")
    for k in range(1, 5):
        q = Px * k / 5
        p.drawText(QRectF(rect.left(), P(0, q).y() - 8, 64, 16), Qt.AlignRight | Qt.AlignVCenter, f"{q / 1000:,.0f}")
        m = Mx * k / 5
        p.drawText(QRectF(P(m, 0).x() - 30, bottom + 4, 60, 16), Qt.AlignCenter, f"{m:,.0f}")
    fill = QColor(BMD_COLOR)
    fill.setAlpha(35)
    p.setBrush(fill)
    p.setPen(QPen(BMD_COLOR, 1.8))
    p.drawPolygon(QPolygonF([P(0, 0)] + [P(m, q) for m, q in res.curve]))
    pt = P(abs(res.Mu), res.Pu)
    p.setPen(QPen(SFD_COLOR, 1.2, Qt.DashLine))
    p.drawLine(P(0, 0), pt)
    p.setBrush(SFD_COLOR)
    p.setPen(Qt.NoPen)
    p.drawEllipse(pt, 5, 5)
    p.setPen(SFD_COLOR)
    p.drawText(QRectF(pt.x() + 8, pt.y() - 16, 220, 16), Qt.AlignLeft,
               f"(Mu {abs(res.Mu):,.0f} กก.-ม., Pu {res.Pu / 1000:,.2f} ตัน)")
    p.restore()


def draw_any(p, rect, res, title=""):
    if hasattr(res, "curve"):
        draw_pm(p, rect, res, title)
    else:
        draw_diagrams(p, rect, res, title)


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
            p.drawText(self.rect(), Qt.AlignCenter, "เลือกคาน ชิ้นส่วนหลังคา หรือเสาในตาราง เพื่อดูแผนภาพแรงเฉือน (SFD) "
                                                    "โมเมนต์ดัด (BMD) หรือแผนภาพ P-M ของเสา")
            return
        draw_any(p, QRectF(self.rect()).adjusted(8, 6, -8, -6), self.res, self.title)
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
    text("U = 1.4D + 1.7L (SDM) · คานต่อเนื่อง: วิธี stiffness · พื้น: วิธีสัมประสิทธิ์ วสท. (Method 2) · "
         "เสา: แรงอัดร่วมโมเมนต์ (แผนภาพ P-M, emin = 15 มม. + 0.03h) · หลังคา: D+L และ D+W (Cp 0.7, × 4/3)")
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
                 f"({'ผ่าน' if m.ok else 'ไม่ผ่าน'})" + (f" · {m.reserve_text()}" if m.qty else ""), color="#15803D" if m.ok else "#B91C1C", size=9)
        y += 6
    for m in res["members"]:
        if m.diagram is None:
            continue
        hgt = page.height() * 0.30
        if y + hgt > page.height():
            w.newPage()
            y = 0.0
        p.setFont(f)
        draw_any(p, QRectF(0, y, page.width(), hgt), m.diagram, m.name)
        y += hgt + 10
    p.end()
