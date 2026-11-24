# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""Shear force and bending moment diagrams (SFD / BMD), on screen and in
the PDF calculation report (the ออกแบบโครงสร้าง คสล. panel uses it)."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

SFD_COLOR = QColor("#2563EB")
BMD_COLOR = QColor("#DC2626")



CAP_COLOR = QColor("#15803D")
DL_COLOR = QColor("#6B7280")         # dead load (grey)
LL_COLOR = QColor("#EA580C")         # live load (orange)
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


OFF_SCALE = 1.6                      # a capacity above 1.6 × the diagram goes on the edge


def _num(v: float) -> str:
    """1,912 / 61.5 / 3.5 — small values keep a decimal (a 3.5 กก.-ม. purlin is not «4»)."""
    return f"{v:,.0f}" if abs(v) >= 100 else f"{v:,.1f}"


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
    cases = getattr(res, "cases", None) or {}
    by = top + 46 + (30 if cases else 0)
    x = 0.0
    sup = [0.0]                    # the span ends
    for sp in res.spans:
        x += sp.L
        sup.append(x)
    supports = list(getattr(res, "supports", None) or sup)
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
        p.drawText(QRectF(xa, by - 26, xb - xa, 12), Qt.AlignCenter,
                   f"{'คานยื่น · ' if getattr(sp, 'cant', '') else ''}"
                   + (f"wu = {sp.w:,.0f} กก./ม. · " if sp.w or not getattr(sp, "U", None) else "")
                   + f"L = {sp.L:.2f} ม.")
        if cases and (getattr(sp, "wd", 0) or getattr(sp, "wl", 0)):
            # the service loads apart: dead (grey) and live (orange) as two bands
            for row_, (val, col_, lab) in enumerate(((sp.wd, DL_COLOR, "DL"), (sp.wl, LL_COLOR, "LL"))):
                yb = by - 56 + row_ * 14
                band = QColor(col_)
                band.setAlpha(60)
                p.setBrush(band)
                p.setPen(QPen(col_, 1))
                p.drawRect(QRectF(xa, yb, xb - xa, 10))
                p.setBrush(Qt.NoBrush)
                p.setPen(QColor("#111827"))
                p.drawText(QRectF(xa + 4, yb - 1, xb - xa - 8, 12), Qt.AlignCenter,
                           f"{lab} = {_num(val)} กก./ม.")
            p.setPen(QPen(QColor("#2563EB"), 1))
        for a_, b_, wu in getattr(sp, "U", []) or []:
            ua, ub = X(sup[i] + a_), X(sup[i] + b_)
            p.setPen(QPen(QColor("#7C3AED"), 1.4))
            p.setBrush(QColor(124, 58, 237, 40))
            p.drawRect(QRectF(ua, by - 22, max(ub - ua, 1.0), 9))
            p.setBrush(Qt.NoBrush)
            p.drawText(QRectF(ua, by - 44, max(ub - ua, 120), 12), Qt.AlignLeft, f"+{wu:,.0f} กก./ม.")
            p.setPen(QPen(QColor("#2563EB"), 1))
        for a_, P in getattr(sp, "P", []) or []:
            px = X(sup[i] + a_)
            p.setPen(QPen(QColor("#DC2626"), 1.6))
            p.drawLine(QPointF(px, by - 24), QPointF(px, by - 2))
            p.drawText(QRectF(px + 3, by - 44, 120, 12), Qt.AlignLeft, f"P = {P:,.0f} กก.")
            p.setPen(QPen(QColor("#2563EB"), 1))
    p.setPen(QPen(QColor("#374151"), 1.2))
    p.setBrush(QColor("#9CA3AF"))
    for i, xs_ in enumerate(supports):
        cx = X(xs_)
        p.drawPolygon(QPolygonF([QPointF(cx, by + 2), QPointF(cx - 6, by + 11), QPointF(cx + 6, by + 11)]))
        if i < len(res.reactions):
            p.setPen(QColor("#111827"))
            p.drawText(QRectF(cx - 45, by + 11, 90, 12), Qt.AlignCenter, f"R{i + 1} = {res.reactions[i]:,.0f}")
            if cases and i < len(cases["DL"].reactions):
                p.setPen(QColor("#6B7280"))
                bx = min(max(cx - 60, rect.left()), rect.right() - 120)       # inside the picture at the ends
                p.drawText(QRectF(bx, by + 23, 120, 12), Qt.AlignCenter,
                           f"DL {cases['DL'].reactions[i]:,.0f} · LL {cases['LL'].reactions[i]:,.0f}")
            p.setPen(QPen(QColor("#374151"), 1.2))
    p.setBrush(Qt.NoBrush)
    # ---- SFD and BMD
    if cases:                                         # the combination the reactions and diagrams use
        p.setPen(QColor("#374151"))
        p.drawText(QRectF(rect.left(), by - 60, 60, 30), Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap,
                   "น้ำหนักใช้งาน")
        p.drawText(QRectF(rect.left(), by - 26, 60, 24), Qt.AlignLeft | Qt.AlignVCenter,
                   f"{cases['fd']:g}DL+{cases['fl']:g}LL")
        by += 12
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
        # the scale follows the member's own diagram: a capacity far above
        # it (a light purlin: M 3.5 against Ma 153) would flatten the curve
        # into a line — such a capacity is drawn on the edge, marked off-scale
        own = max([abs(v) for v in vals] + [1e-6])
        capm = max([abs(c) for c, *_r in lines if c] + [0.0])
        big = max(own, min(capm, own * OFF_SCALE))
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
            off = abs(c) > big * 1.0001
            yy = mid + sgn * (c if not off else math.copysign(big, c)) * scale
            p.setPen(QPen(col, 1.1, style))
            p.drawLine(QPointF(left, yy), QPointF(right, yy))
            if lab:
                p.setPen(col)
                p.drawText(QRectF(right - 230, yy + (-13 if sgn * c < 0 else 1), 230, 12),
                           Qt.AlignRight | Qt.AlignVCenter,
                           f"{lab} = {_num(abs(c))}" + (" (เกินขอบภาพ)" if off else ""))
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
                       f"{tag} {_num(v)} @ x = {res.xs[i]:.2f} ม.")
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


def _title(p, rect, title, f):
    tf = QFont(f)
    tf.setBold(True)
    tf.setPointSizeF(9.5)
    p.setFont(tf)
    p.setPen(QColor("#111827"))
    p.drawText(QRectF(rect.left(), rect.top(), rect.width(), 16), Qt.AlignLeft | Qt.AlignVCenter, title)
    p.setFont(f)
    return rect.top() + 20


def _arrow(p, x, y0, y1, color, width=1.4):
    """A load arrow from y0 to y1 (the head at y1)."""
    p.setPen(QPen(color, width))
    p.drawLine(QPointF(x, y0), QPointF(x, y1))
    s_ = 4 if y1 > y0 else -4
    p.drawLine(QPointF(x, y1), QPointF(x - 3, y1 - s_))
    p.drawLine(QPointF(x, y1), QPointF(x + 3, y1 - s_))


def _lines(p, x, y, rows, width=330):
    """Text rows (text, colour) from (x, y) down; returns the y under them."""
    for t, col in rows:
        p.setPen(QColor(col))
        p.drawText(QRectF(x, y, width, 14), Qt.AlignLeft | Qt.AlignVCenter, t)
        y += 15
    return y


def draw_slab(p: QPainter, rect: QRectF, pic: dict, title: str = "") -> None:
    """พฤติกรรมพื้น: the plan with the load shared to its beams (45° lines —
    triangles to the short sides, trapezoids to the long sides; one-way:
    all to the long sides), the strip under DL and LL, its bending, and the
    check."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    f = QFont(p.font())
    f.setPointSizeF(8.0)
    p.setFont(f)
    top = _title(p, rect, title or f"พื้น {pic.get('mark', '')}", f)
    a, b = float(pic["a"]), float(pic["b"])
    # the plan (b across, a down), fitted in the left half
    box = QRectF(rect.left() + 26, top + 6, rect.width() * 0.40, min(rect.bottom() - top - 30, 260))
    sc = min(box.width() / b, box.height() / a)
    W, H = b * sc, a * sc
    x0, y0 = box.left() + (box.width() - W) / 2, box.top() + (box.height() - H) / 2
    p.setPen(QPen(QColor("#374151"), 2.2))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(x0, y0, W, H))
    tri = QColor("#0EA5E9")                               # to the short-side beams
    tri.setAlpha(50)
    tra = QColor("#22C55E")                               # to the long-side beams
    tra.setAlpha(50)
    p.setPen(QPen(QColor("#9CA3AF"), 1, Qt.DashLine))
    if pic.get("one_way"):
        mid = y0 + H / 2
        p.setBrush(tra)
        p.drawRect(QRectF(x0, y0, W, H / 2))
        p.setBrush(tri)
        p.drawRect(QRectF(x0, mid, W, H / 2))
        note = "พื้นทางเดียว: ถ่ายน้ำหนักลงคานด้านยาว 2 ข้าง (ครึ่งละ a/2, เขียว/ฟ้า)"
    else:
        h2 = H / 2
        L_, R_ = QPointF(x0 + h2, y0 + h2), QPointF(x0 + W - h2, y0 + h2)
        p.setBrush(tra)
        p.drawPolygon(QPolygonF([QPointF(x0, y0), QPointF(x0 + W, y0), R_, L_]))
        p.drawPolygon(QPolygonF([QPointF(x0, y0 + H), QPointF(x0 + W, y0 + H), R_, L_]))
        p.setBrush(tri)
        p.drawPolygon(QPolygonF([QPointF(x0, y0), QPointF(x0, y0 + H), L_]))
        p.drawPolygon(QPolygonF([QPointF(x0 + W, y0), QPointF(x0 + W, y0 + H), R_]))
        note = "พื้นสองทาง: คานด้านสั้นรับรูปสามเหลี่ยม (ฟ้า) · คานด้านยาวรับรูปสี่เหลี่ยมคางหมู (เขียว) · เส้น 45°"
    p.setBrush(Qt.NoBrush)
    p.setPen(QColor("#111827"))
    p.drawText(QRectF(x0, y0 + H + 2, W, 14), Qt.AlignCenter, f"ด้านยาว b = {b:.2f} ม.")
    p.save()
    p.translate(x0 - 6, y0 + H / 2)
    p.rotate(-90)
    p.drawText(QRectF(-H / 2, -14, H, 12), Qt.AlignCenter, f"ด้านสั้น a = {a:.2f} ม.")
    p.restore()
    # the strip across the short side: DL / LL bands, the deflected shape
    sx0 = rect.left() + rect.width() * 0.50
    sx1 = rect.right() - 16
    sy = top + 70
    for row_, (val, col_, lab) in enumerate(((pic["qd"], DL_COLOR, "DL"), (pic["ql"], LL_COLOR, "LL"))):
        yb = sy - 48 + row_ * 14
        band = QColor(col_)
        band.setAlpha(60)
        p.setBrush(band)
        p.setPen(QPen(col_, 1))
        p.drawRect(QRectF(sx0, yb, sx1 - sx0, 10))
        p.setBrush(Qt.NoBrush)
        p.setPen(QColor("#111827"))
        p.drawText(QRectF(sx0, yb - 1, sx1 - sx0, 12), Qt.AlignCenter, f"{lab} = {_num(val)} กก./ตร.ม.")
    n = 10
    for k in range(n + 1):
        _arrow(p, sx0 + (sx1 - sx0) * k / n, sy - 18, sy - 2, QColor("#2563EB"), 1)
    p.setPen(QPen(QColor("#374151"), 3))
    p.drawLine(QPointF(sx0, sy), QPointF(sx1, sy))
    p.setPen(QPen(QColor("#374151"), 1.2))
    p.setBrush(QColor("#9CA3AF"))
    for cx in (sx0, sx1):
        p.drawPolygon(QPolygonF([QPointF(cx, sy + 2), QPointF(cx - 6, sy + 11), QPointF(cx + 6, sy + 11)]))
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(BMD_COLOR, 1.6, Qt.DashLine))           # the strip sags in the middle
    pts = [QPointF(sx0 + (sx1 - sx0) * k / 20, sy + 26 * math.sin(math.pi * k / 20)) for k in range(21)]
    p.drawPolyline(QPolygonF(pts))
    p.setPen(BMD_COLOR)
    p.drawText(QRectF(sx0, sy + 28, sx1 - sx0, 12), Qt.AlignCenter, "แอ่นตัวกลางช่วง → เหล็กล่างรับแรงดึง")
    ok = pic["Mu"] <= pic["cap"] + 1e-9 if pic["cap"] else False
    _lines(p, sx0, sy + 48, [
        (f"wu = {pic['fd']:g}×{_num(pic['qd'])} + {pic['fl']:g}×{_num(pic['ql'])} = {_num(pic['qu'])} กก./ตร.ม.",
         "#111827"),
        (f"Mu = {_num(pic['Mu'])} กก.-ม./ม.  เทียบ  φMn = {_num(pic['cap'])} กก.-ม./ม.",
         "#15803D" if ok else "#B91C1C"),
        (("✓ ผ่าน" if ok else "✗ ไม่ผ่าน") + f" · ใช้ไป {pic['Mu'] / pic['cap'] * 100 if pic['cap'] else 999:,.0f} %",
         "#15803D" if ok else "#B91C1C"),
        (note, "#374151")], width=sx1 - sx0)
    p.restore()


def draw_footing(p: QPainter, rect: QRectF, pic: dict, title: str = "") -> None:
    """พฤติกรรมฐานราก: the column load down, the footing's own weight, and
    the soil pushing back evenly (q against qa) — or each pile's share
    against its capacity."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    f = QFont(p.font())
    f.setPointSizeF(8.0)
    p.setFont(f)
    top = _title(p, rect, title or f"ฐานราก {pic.get('mark', '')}", f)
    w_ = max(float(pic.get("w") or 1.0), 0.3)
    t_ = max(float(pic.get("t") or 0.3), 0.15)
    piles = int(pic.get("n") or 0) if pic["kind"] == "pile" else 0
    area = QRectF(rect.left() + 20, top + 10, rect.width() * 0.48, rect.bottom() - top - 20)
    depth = t_ + 0.9 + (1.2 if piles else 0.6)
    sc = min(area.width() / (w_ * 1.5), area.height() / depth)
    cx = area.left() + area.width() / 2
    fy0 = area.top() + 0.9 * sc                            # top of the footing
    W, T = w_ * sc, t_ * sc
    # ground line, stump, footing
    p.setPen(QPen(QColor("#92400E"), 1, Qt.DashLine))
    p.drawLine(QPointF(area.left(), area.top() + 0.35 * sc), QPointF(area.right(), area.top() + 0.35 * sc))
    col = max(float(pic.get("col") or 0.2), 0.15) * sc
    p.setPen(QPen(QColor("#374151"), 1.4))
    p.setBrush(QColor("#E5E7EB"))
    p.drawRect(QRectF(cx - col / 2, area.top() + 0.1 * sc, col, fy0 - area.top() - 0.1 * sc))
    p.setBrush(QColor("#D1D5DB"))
    p.drawRect(QRectF(cx - W / 2, fy0, W, T))
    p.setBrush(Qt.NoBrush)
    P = float(pic["P"])
    _arrow(p, cx, area.top() - 6, area.top() + 0.08 * sc, QColor("#B91C1C"), 2.2)
    p.setPen(QColor("#B91C1C"))
    p.drawText(QRectF(cx + 8, area.top() - 8, 200, 14), Qt.AlignLeft,
               f"P = {P / 1000:,.2f} ตัน (รวมน้ำหนักฐาน {pic.get('self', 0) / 1000:,.2f})")
    yb = fy0 + T
    rows = []
    if piles:
        n_show = min(piles, 6)
        share = P / piles
        ok = share <= float(pic["pc"]) + 1e-6
        for k in range(n_show):
            px = cx - W / 2 + W * (k + 0.5) / n_show
            p.setPen(QPen(QColor("#374151"), 1.2))
            p.setBrush(QColor("#F3F4F6"))
            p.drawRect(QRectF(px - 4, yb, 8, 1.1 * sc))
            p.setBrush(Qt.NoBrush)
            _arrow(p, px, yb + 1.1 * sc + 14, yb + 1.1 * sc + 2, QColor("#15803D"))
        rows = [(f"เข็ม {piles} ต้น · แรงต่อต้น P/n = {share / 1000:,.2f} ตัน", "#111827"),
                (f"กำลังเข็มต่อต้น = {float(pic['pc']) / 1000:,.2f} ตัน",
                 "#15803D" if ok else "#B91C1C"),
                (("✓ ผ่าน" if ok else "✗ ไม่ผ่าน") + f" · ใช้ไป {share / float(pic['pc']) * 100 if pic['pc'] else 999:,.0f} %",
                 "#15803D" if ok else "#B91C1C"),
                ("ฐานถ่ายน้ำหนักลงเข็มเท่ากันทุกต้น (ฐานแข็ง น้ำหนักตรงศูนย์)", "#374151")]
    else:
        q, qa = float(pic["q"]), float(pic["qa"])
        ok = q <= qa + 1e-9
        hq = min(36.0, 36.0 * q / max(qa, q, 1e-9))           # the soil pressure block, scaled to qa
        p.setPen(QPen(QColor("#15803D" if ok else "#B91C1C"), 1))
        fill = QColor("#15803D" if ok else "#B91C1C")
        fill.setAlpha(40)
        p.setBrush(fill)
        p.drawRect(QRectF(cx - W / 2, yb + 4, W, hq))
        p.setBrush(Qt.NoBrush)
        for k in range(7):
            _arrow(p, cx - W / 2 + W * k / 6, yb + 4 + hq, yb + 5, QColor("#15803D" if ok else "#B91C1C"), 1)
        p.setPen(QPen(QColor("#15803D"), 1, Qt.DashLine))
        ya = yb + 4 + 36.0 * qa / max(qa, q, 1e-9)
        p.drawLine(QPointF(cx - W / 2 - 10, ya), QPointF(cx + W / 2 + 10, ya))
        p.setPen(QColor("#15803D"))
        p.drawText(QRectF(cx - W / 2 - 10, ya + 1, W + 20, 12), Qt.AlignCenter, f"qa = {qa:g} ตัน/ตร.ม.")
        rows = [(f"ฐาน {pic['w']:.2f} × {pic['l']:.2f} ม. หนา {pic['t']:.2f} ม. · พื้นที่ "
                 f"{pic['w'] * pic['l']:.2f} ตร.ม.", "#111827"),
                (f"แรงดันดิน q = P / A = {q:,.2f} ตัน/ตร.ม.  เทียบ  qa = {qa:g}", "#15803D" if ok else "#B91C1C"),
                (("✓ ผ่าน" if ok else "✗ ไม่ผ่าน") + f" · ใช้ไป {q / qa * 100 if qa else 999:,.0f} %",
                 "#15803D" if ok else "#B91C1C"),
                ("ดินดันกลับเท่ากันทั้งฐาน (น้ำหนักตรงศูนย์) — ฐานงอขึ้น เหล็กตะแกรงล่างรับแรงดึง", "#374151")]
    p.setPen(QColor("#111827"))
    p.drawText(QRectF(cx - W / 2, fy0 + T / 2 - 7, W, 14), Qt.AlignCenter, f"{pic.get('mark', '')}")
    _lines(p, rect.left() + rect.width() * 0.54, top + 20, rows, width=rect.width() * 0.45)
    p.restore()


def draw_any(p, rect, res, title=""):
    if isinstance(res, dict):
        if res.get("kind") == "slab":
            draw_slab(p, rect, res, title)
        elif res.get("kind") in ("footing", "pile"):
            draw_footing(p, rect, res, title)
        return
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
            p.drawText(self.rect(), Qt.AlignCenter, "เลือกชิ้นส่วนในตาราง เพื่อดูพฤติกรรมแรง: คาน/หลังคา (DL LL แรงปฏิกิริยา "
                                                    "SFD BMD) · เสา (P-M) · พื้น · ฐานราก/เข็ม")
            return
        draw_any(p, QRectF(self.rect()).adjusted(8, 6, -8, -6), self.res, self.title)
        p.end()


def report_pdf(res, data, path) -> None:
    """รายการคำนวณโครงสร้าง: the basis, every member's check, and the
    diagrams of every beam and roof member, on A4 pages."""
    from core import wanic_pile as PL
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
         f"กก./ตร.ม. · ดินรับได้ {b_['soil']:g} ตัน/ตร.ม. · "
         f"{PL.pile_text(data, b_)}")
    text("U = 1.4D + 1.7L (SDM) · คานต่อเนื่อง: วิธี stiffness · พื้น: วิธีสัมประสิทธิ์ วสท. (Method 2) · "
         "เสา: แรงอัดร่วมโมเมนต์ (แผนภาพ P-M, emin = 15 มม. + 0.03h) · หลังคา: D+L และ D+W (Cp 0.7, × 4/3)")
    text("เอกสารนี้เป็นเครื่องมือช่วยคำนวณ ต้องให้วิศวกรโยธาผู้มีใบอนุญาตตรวจสอบและลงนามรับรองก่อนก่อสร้าง",
         color="#B45309")
    y += 8
    names = {"roof": "โครงหลังคา", "slab": "พื้น", "beam": "คาน", "column": "เสา", "footing": "ฐานราก / เสาเข็ม",
             "stair": "บันได คสล."}
    for g in ("roof", "slab", "beam", "column", "footing", "stair"):
        ms = [m for m in res["members"] if m.group == g]
        if not ms:
            continue
        text(names[g], True, 12)
        for m in ms:
            text(f"{'✓' if m.ok else '✗'} {m.name}: {m.demand} / {m.capacity} → {m.ratio:.2f} "
                 f"({'ผ่าน' if m.ok else 'ไม่ผ่าน'})", color="#15803D" if m.ok else "#B91C1C", size=9)
            text("      อธิบายง่าย: " + m.plain_text(), color="#15803D" if m.ok else "#B91C1C", size=8)
        y += 6
    for m in res["members"]:
        if m.diagram is None and getattr(m, "picture", None) is None:
            continue
        hgt = page.height() * 0.30
        if y + hgt > page.height():
            w.newPage()
            y = 0.0
        p.setFont(f)
        draw_any(p, QRectF(0, y, page.width(), hgt), m.diagram if m.diagram is not None else m.picture, m.name)
        y += hgt + 10
    p.end()
