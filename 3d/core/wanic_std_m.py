# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""แบบระบบเครื่องกล (M) laid out as the standard house plans do (M-01, M-02):
per floor, the recommended places of the exhaust fans (ceiling fans in the
bathrooms, a propeller fan in the kitchen, with their air grilles through
the outer wall) and of the split air-conditioners. Sizes come from the
rooms: the fans from 10 air changes an hour of the room's volume, the AC
from wanic_mep.plan (the same units the 3-D model and the BOQ use)."""
from __future__ import annotations

import math

from core import wanic_drawings as D

FAN_CFM = (40, 80, 120, 200)
KITCHEN_CFM = 400


def fan_cfm(area: float, height: float, ach: float = 10.0) -> int:
    """The bathroom fan for ``ach`` air changes an hour (m³/h → CFM)."""
    need = area * height * ach / 1.699
    return next((c for c in FAN_CFM if c >= need), FAN_CFM[-1])


def _grill(sh, p, n):
    """An exhaust grille on the outer wall: a box with the outward arrows."""
    sh.rect(p[0] - 1.6, p[1] - 1.6, p[0] + 1.6, p[1] + 1.6, "mech", 0.35)
    for i in (-0.8, 0.0, 0.8):
        a = (p[0] + n[1] * i * 1.4, p[1] - n[0] * i * 1.4)
        sh.line(a, (a[0] + n[0] * 3.4, a[1] + n[1] * 3.4), "mech", 0.25)
        q = (a[0] + n[0] * 3.4, a[1] + n[1] * 3.4)
        sh.fill([q, (q[0] - n[0] * 1.0 - n[1] * 0.5, q[1] - n[1] * 1.0 + n[0] * 0.5),
                 (q[0] - n[0] * 1.0 + n[1] * 0.5, q[1] - n[1] * 1.0 - n[0] * 0.5)], "mech", 0.0)


def _ceiling_fan(sh, p, r=2.2):
    """A ceiling exhaust fan: a square with the four blades."""
    sh.rect(p[0] - r, p[1] - r, p[0] + r, p[1] + r, "mech", 0.4)
    for a in (45, 135, 225, 315):
        c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
        sh.poly([p, (p[0] + c * r * 0.9 - s * 0.6, p[1] + s * r * 0.9 + c * 0.6),
                 (p[0] + c * r * 0.9 + s * 0.6, p[1] + s * r * 0.9 - c * 0.6)], "mech", 0.25)
    sh.circle(p, 0.5, "mech", 0.3)


def _prop_fan(sh, p, n):
    """A propeller fan set in the wall: a thick bar with its blade mark."""
    t = (-n[1], n[0])
    a, b = (p[0] - t[0] * 2.6, p[1] - t[1] * 2.6), (p[0] + t[0] * 2.6, p[1] + t[1] * 2.6)
    sh.fill([(a[0] - n[0] * 0.8, a[1] - n[1] * 0.8), (b[0] - n[0] * 0.8, b[1] - n[1] * 0.8),
             (b[0] + n[0] * 0.8, b[1] + n[1] * 0.8), (a[0] + n[0] * 0.8, a[1] + n[1] * 0.8)], "mech", 0.0)
    q = (p[0] + n[0] * 3.0, p[1] + n[1] * 3.0)
    sh.line(p, q, "mech", 0.3)
    sh.fill([q, (q[0] - n[0] * 1.2 - n[1] * 0.6, q[1] - n[1] * 1.2 + n[0] * 0.6),
             (q[0] - n[0] * 1.2 + n[1] * 0.6, q[1] - n[1] * 1.2 - n[0] * 0.6)], "mech", 0.0)


def _ac_unit(sh, p, n):
    """A wall-type indoor unit against the wall (outward normal ``n``)."""
    t = (-n[1], n[0])
    c = (p[0] - n[0] * 1.2, p[1] - n[1] * 1.2)
    pts = [(c[0] + t[0] * s * 4.2 + n[0] * u * 1.1, c[1] + t[1] * s * 4.2 + n[1] * u * 1.1)
           for s, u in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    sh.fill(pts, "mask", 0.0)
    sh.poly(pts, "mech", 0.45)
    for s in (-0.5, 0.0, 0.5):
        sh.line((c[0] + t[0] * s * 4.2 - n[0] * 0.9, c[1] + t[1] * s * 4.2 - n[1] * 0.9),
                (c[0] + t[0] * s * 4.2 - n[0] * 2.4, c[1] + t[1] * s * 4.2 - n[1] * 2.4), "mech", 0.25)


def _outer(E, k, rm):
    """The room's edge on the building's outside nearest to it: (point on the
    wall at the edge's middle, outward normal), or None."""
    from core import wanic_std_sn as SNS
    box = SNS._outline(E, k)
    side, wall, n = SNS._side(rm, box, ("E", "N", "W", "S"))
    edge = {"W": rm["x"], "E": rm["x"] + rm["w"], "S": rm["y"], "N": rm["y"] + rm["d"]}[side]
    if abs(edge - wall) > 0.05:
        return None
    if n[0]:
        return (wall, rm["y"] + rm["d"] * 0.5), n
    return (rm["x"] + rm["w"] * 0.5, wall), n


def _labels_left(sh, notes, col_x, ytop, ybot, size=2.4):
    """The notes in a column ending at ``col_x`` (text right-aligned), each
    on a level leader with one turn to its item, arrowhead at the item."""
    items = sorted(notes, key=lambda t: -t[0][1])
    last = ytop + 8
    for p, lines in items:
        ty = max(min(p[1], ytop, last - 6.4), ybot)
        last = ty - 4.6 * (len(lines) - 1)
        knee = (p[0] - 4.0, ty) if abs(ty - p[1]) > 0.4 else None
        sh.line((col_x + 1.2, ty), knee or p, "text", 0.18)
        if knee:
            sh.line(knee, p, "text", 0.18)
        from core import wanic_std_sn as SNS
        SNS._ahead(sh, p, knee or (col_x, ty), 2.0, "text")
        for j, ln in enumerate(lines):
            sh.text((col_x, ty - 0.9 - j * 4.6), ln, size, "right")


def m_plan_std(sh, E, k):
    """ตำแหน่งติดตั้งเครื่องปรับอากาศและพัดลมระบายอากาศที่แนะนำ ชั้น k+1."""
    from core import wanic_building as B
    from core import wanic_mep as MEP
    from core import wanic_std_ee as EES
    from core import wanic_std_sheets as STD
    from core import wanic_std_sn as SNS
    x0, y0, x1, y1 = D.drawing_area()
    v, sc = EES._base(sh, E, k, colw=86.0, left=44.0)
    H = float(E["H"])
    boxes = D.stair_boxes(E, k)
    notes = []
    n_ac = n_fan = 0
    for rec in MEP.plan({}, E):
        if rec["floor"] != k:
            continue
        rm = rec["room"]
        name = rm.get("name") or ""
        inner = B.room_inner(E, rm, k)
        ix0, iy0, ix1, iy1 = inner
        taken = []
        out = _outer(E, k, rm)
        if rec["kind"] == "wet" or "น้ำ" in name:
            cfm = fan_cfm(rec["area"], max(H - 0.6, 2.4))
            if out:
                (wx, wy), n = out
                if n[0]:
                    fp = (wx - n[0] * 0.45, min(max(wy, iy0 + 0.4), iy1 - 0.4))
                else:
                    fp = (min(max(wx, ix0 + 0.4), ix1 - 0.4), wy - n[1] * 0.45)
                pf, pw = v(*fp), v(wx, wy)
                _ceiling_fan(sh, pf)
                sh.line(pf, pw, "mech", 0.3, True)
                _grill(sh, pw, n)
                gsz = '6"x6"' if cfm >= 80 else '4"x4"'
                notes.append((pw, ["EXHAUST AIR GRILL W/INS " + gsz]))
                taken.append(fp)
            else:
                fp = ((ix0 + ix1) / 2, (iy0 + iy1) / 2)
                pf = v(*fp)
                _ceiling_fan(sh, pf)
                taken.append(fp)
            notes.append((pf, ["CEILING FAN", f"({cfm} CFM.)"]))
            n_fan += 1
        elif "ครัว" in name and out:
            (wx, wy), n = out
            pw = v(wx, wy)
            _prop_fan(sh, pw, n)
            notes.append((pw, ["PROPELLER FAN TYPE", f"({KITCHEN_CFM} CFM.)"]))
            taken.append((wx, wy))
            n_fan += 1
        if rec["ac"] and rec.get("ac_wall"):
            wl = rec["ac_wall"]
            mx, my = (wl["p0"][0] + wl["p1"][0]) / 2, (wl["p0"][1] + wl["p1"][1]) / 2
            cx, cy = (ix0 + ix1) / 2, (iy0 + iy1) / 2
            if abs(wl["p0"][0] - wl["p1"][0]) < 1e-6:                  # a wall along y
                n = (1, 0) if mx > cx else (-1, 0)
                ap = (ix1 if n[0] > 0 else ix0, min(max(my, iy0 + 0.6), iy1 - 0.6))
            else:
                n = (0, 1) if my > cy else (0, -1)
                ap = (min(max(mx, ix0 + 0.6), ix1 - 0.6), iy1 if n[1] > 0 else iy0)
            pa = v(*ap)
            _ac_unit(sh, pa, n)
            notes.append(((pa[0] - n[0] * 2.4, pa[1] - n[1] * 2.4), ["WALL TYPE", f"ขนาด {rec['ac']:,} BTU."]))
            taken.append(ap)
            n_ac += 1
        spot = EES._free_spot(rm, taken, boxes)
        for q in taken:                                         # never on a unit
            if abs(spot[0] - q[0]) < 1.8 and abs(spot[1] - q[1]) < 0.7:
                spot = (spot[0], spot[1] + (-0.8 if q[1] > (iy0 + iy1) / 2 else 0.8))
        EES._room_label(sh, v, E, k, rm, spot)
    mid = v((B.bbox_floor(E) if hasattr(B, "bbox_floor") else D.bbox(E))[0] / 2 +
            (D.bbox(E))[2] / 2, 0)[0]
    col_x = x1 - 90
    right = [n_ for n_ in notes if n_[0][0] >= mid]
    left_ = [n_ for n_ in notes if n_[0][0] < mid]
    SNS._labels(sh, right, col_x, y1 - 10, y0 + 102, 2.4)
    _labels_left(sh, left_, x0 + 30, y1 - 10, y0 + 30, 2.4)
    EES._side_notes(sh, col_x, y0 + 96, [
        "1. พัดลมระบายอากาศห้องน้ำ ไม่น้อยกว่า 10 เท่าของปริมาตรห้องต่อชั่วโมง ต่อท่อออกนอกอาคาร",
        "2. ครัวติดพัดลมระบายอากาศชนิดใบพัดในผนัง ระบายออกสู่ภายนอก",
        "3. เครื่องปรับอากาศแบบแยกส่วน ติดผนังใต้ฝ้า 0.15 ม. ท่อน้ำทิ้งลงรางระบาย",
        "4. ตำแหน่งเป็นตำแหน่งที่แนะนำ ปรับตามหน้างานได้"], "หมายเหตุ")
    STD.caption_marks(sh, (x0 + 74, y0 + 12),
                      f"ตำแหน่งติดตั้งเครื่องปรับอากาศและพัดลมระบายอากาศที่แนะนำ ชั้น {k + 1}", f"1:{sc}",
                      None, None, 130.0)
    return n_ac, n_fan
