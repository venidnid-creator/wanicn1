# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""เหล็กเสริมในโมเดล 3 มิติ — the owner (27 พ.ย. 69): «เพิ่มปุ่มแสดงเหล็กเสริมในอาคาร ให้วัสดุที่มีเหล็กเสริม
อยู่ด้านในคอนกรีตลดความเข้มของแสงลงให้เห็นเหล็กเสริม ใส่เหล็กเสริมตามโครงสร้างวิศวกรรม เช่น เสา ฐานราก คาน».

The bars come from the same marks the calc book, the S sheets, the BOQ and the cutting list use
(``wanic_rc``): the covers ``R.cover_of``, the main bars and ties of columns and stumps, the top and
bottom bars and the stirrups of beams (2h zones at ``R.end_stirrups``, counts by ``R.stirrup_count``),
the footing mesh (``R.mesh_count``) and the slab bars both ways. Each bar is a square prism of its
diameter; one group per member, tagged part «rebar» (built and removed by the button, never billed —
the BOQ counts the bars from the marks)."""
from __future__ import annotations

import math

from PySide6.QtGui import QVector3D

from core import wanic_building as B
from core import wanic_rc as R

PART = "rebar"
#: bar colours: main bars rust red, ties/stirrups dark orange, meshes brown
COLORS = {"main": (0.72, 0.16, 0.12), "tie": (0.90, 0.45, 0.10), "mesh": (0.55, 0.30, 0.15)}
#: the concrete's opacity while the bars show
CONCRETE_OPACITY = 0.22


def _frame(a, b):
    d = QVector3D(b[0] - a[0], b[1] - a[1], b[2] - a[2])
    L = d.length()
    if L < 1e-6:
        return None
    d /= L
    up = QVector3D(0, 0, 1) if abs(d.z()) < 0.9 else QVector3D(1, 0, 0)
    u = QVector3D.crossProduct(d, up).normalized()
    v = QVector3D.crossProduct(d, u).normalized()
    return u, v


def _bar(mesh, a, b, dia_mm):
    """A square prism of side ≈ the bar's diameter from a to b."""
    fr = _frame(a, b)
    if fr is None:
        return 0
    u, v = fr
    r = max(dia_mm, 6) / 2000.0
    A, Bp = QVector3D(*a), QVector3D(*b)
    ca = [A + u * (sx * r) + v * (sy * r) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    cb = [Bp + u * (sx * r) + v * (sy * r) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    mesh.add_face(list(reversed(ca)))
    mesh.add_face(cb)
    for i in range(4):
        j = (i + 1) % 4
        mesh.add_face([ca[i], ca[j], cb[j], cb[i]])
    return 1


def _ring(mesh, pts, dia_mm):
    """A closed tie / stirrup through the corner points."""
    n = 0
    for i in range(len(pts)):
        n += _bar(mesh, pts[i], pts[(i + 1) % len(pts)], dia_mm)
    return n


def _group(mesh, kind, mark, label, color):
    from core.group import Group
    for e in getattr(mesh, "edges", []) or []:
        try:
            e.soft = True                          # no black outline over every bar: its colour shows
        except AttributeError:
            pass
    g = Group(mesh, name=label)
    g.material = {"color": color}
    return B._tag(g, PART, kind, mark, [("ชนิด", label)], key=label)


def _col_bars(mesh_m, mesh_t, x, y, z0, z1, b, h, cover, main, tie, foot=None):
    """Main bars round the section, ties along the height. ``foot`` = (z of the footing mesh,
    hook length): the stump's bars run down into the footing onto its mesh and turn 90° outwards
    there (the standard footing detail — owner, 27 Nov), with ties inside the footing too."""
    n = 0
    cx, cy = b / 2 - cover, h / 2 - cover
    if main and main.n:
        nb = max(main.n, 4)
        per = []                                    # corners first, then the faces evenly
        corners = [(-cx, -cy), (cx, -cy), (cx, cy), (-cx, cy)]
        per += corners
        extra = nb - 4
        sides = [((-cx, -cy), (cx, -cy)), ((cx, cy), (-cx, cy)), ((cx, -cy), (cx, cy)), ((-cx, cy), (-cx, -cy))]
        k = 0
        while extra > 0:
            (ax, ay), (bx, by) = sides[k % 4]
            m_ = (k // 4) + 1
            t = m_ / (m_ + 1)
            per.append((ax + (bx - ax) * t, ay + (by - ay) * t))
            extra -= 1
            k += 1
        for px, py in per[:nb]:
            if foot is not None:
                zf, hook = foot
                zl = zf + main.d / 1000.0
                n += _bar(mesh_m, (x + px, y + py, zl), (x + px, y + py, z1 - 0.02), main.d)
                l_ = math.hypot(px, py) or 1.0
                n += _bar(mesh_m, (x + px, y + py, zl),
                          (x + px + px / l_ * hook, y + py + py / l_ * hook, zl), main.d)
            else:
                n += _bar(mesh_m, (x + px, y + py, z0 + 0.05), (x + px, y + py, z1 - 0.02), main.d)
    if tie:
        s = tie.s or 0.15
        z = (foot[0] + 0.10) if foot is not None else z0 + 0.05
        while z < z1 - 0.03:
            n += _ring(mesh_t, [(x - cx, y - cy, z), (x + cx, y - cy, z), (x + cx, y + cy, z),
                                (x - cx, y + cy, z)], tie.d)
            z += s
    return n


def rebar_groups(data) -> list:
    """The bars of every footing, stump, column, beam and slab as groups (part «rebar»)."""
    from core.mesh import Mesh
    E = B.elements(data)
    lib = E["lib"]
    out = []
    if not E["n"]:
        return out
    # columns and stumps
    for role, items in (("column", E["columns"]), ("stump", E["stumps"])):
        mm, mt = Mesh(), Mesh()
        n = 0
        feet = {(round(f["x"], 3), round(f["y"], 3)): f for f in E["footings"]}
        for c in items:
            sp = lib.get(c["mark"]) or {}
            b, h = float(sp.get("b", 0.2)), float(sp.get("h", sp.get("b", 0.2)))
            cv = R.cover_of(sp, "column" if role == "column" else "stump") + 0.006
            main = R.parse_bar(sp.get("main"))
            foot = None
            f = feet.get((round(c["x"], 3), round(c["y"], 3))) if role == "stump" else None
            if f is not None and main:
                fb = R.parse_bar((lib.get(f["mark"]) or {}).get("bars"))
                zf = float(f["z0"]) + R.COVER["footing"] + 2 * ((fb.d if fb else 12) / 1000.0)
                foot = (zf, max(12 * main.d / 1000.0, 0.15))         # 90° hook ≥ 12 d on the mesh
            n += _col_bars(mm, mt, c["x"], c["y"], float(c["z0"]), float(c["z1"]), b, h, cv,
                           main, R.parse_bar(sp.get("tie")), foot)
        if n:
            th = "เสา" if role == "column" else "ตอม่อ"
            out.append(_group(mm, role + "_main", th, f"เหล็กยืน{th}", COLORS["main"]))
            out.append(_group(mt, role + "_tie", th, f"เหล็กปลอก{th}", COLORS["tie"]))
    # beams: top and bottom bars the whole span, stirrups 2h at each end closer
    mm, mt = Mesh(), Mesh()
    n = 0
    for e in E["beams"]:
        sp = lib.get(e["mark"]) or {}
        b, h = float(sp.get("b", 0.2)), float(sp.get("h", 0.4))
        cv = R.cover_of(sp, "beam") + 0.006
        (x0, y0), (x1, y1) = e["p0"], e["p1"]
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 0.1:
            continue
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        nx, ny = -uy, ux
        zt = float(e["z"]) - cv
        zb = float(e["z"]) - h + cv
        for text, z in ((sp.get("top"), zt), (sp.get("bot"), zb)):
            bar = R.parse_bar(text)
            if not bar or not bar.n:
                continue
            for i in range(bar.n):
                off = -b / 2 + cv + (b - 2 * cv) * (i / (bar.n - 1) if bar.n > 1 else 0.5)
                n += _bar(mm, (x0 + nx * off, y0 + ny * off, z), (x1 + nx * off, y1 + ny * off, z), bar.d)
        st = R.parse_bar(sp.get("stir"))
        if st:
            zone, s_end = R.end_stirrups(sp)
            s_mid = st.s or 0.15
            zone = min(zone, L / 3)
            t = 0.05
            while t < L - 0.03:
                px, py = x0 + ux * t, y0 + uy * t
                hw = b / 2 - cv
                n += _ring(mt, [(px - nx * hw, py - ny * hw, zb), (px + nx * hw, py + ny * hw, zb),
                                (px + nx * hw, py + ny * hw, zt), (px - nx * hw, py - ny * hw, zt)], st.d)
                t += s_end if (t < zone or t > L - zone) else s_mid
    if n:
        out.append(_group(mm, "beam_main", "คาน", "เหล็กบน-ล่างคาน", COLORS["main"]))
        out.append(_group(mt, "beam_stir", "คาน", "เหล็กปลอกคาน", COLORS["tie"]))
    # footings: the mesh both ways, at the cover above the bottom
    mm = Mesh()
    n = 0
    for f in E["footings"]:
        sp = lib.get(f["mark"]) or {}
        w, l_ = float(sp.get("w", 1.0)), float(sp.get("l", sp.get("w", 1.0)))
        bar = R.parse_bar(sp.get("bars"))
        if not bar or not bar.s:
            continue
        cv = R.COVER["footing"]
        z = float(f["z0"]) + cv
        x, y = float(f["x"]), float(f["y"])
        nx_ = R.mesh_count(w, bar.s)
        ny_ = R.mesh_count(l_, bar.s)
        t_ = float(sp.get("t", 0.3))
        up = max(t_ - 2 * cv, 0.05)                 # the mesh bars turn up at the sides (standard detail)
        for i in range(nx_):
            px = x - w / 2 + cv + (w - 2 * cv) * (i / (nx_ - 1) if nx_ > 1 else 0.5)
            ya, yb = y - l_ / 2 + cv, y + l_ / 2 - cv
            n += _bar(mm, (px, ya, z), (px, yb, z), bar.d)
            n += _bar(mm, (px, ya, z), (px, ya, z + up), bar.d)
            n += _bar(mm, (px, yb, z), (px, yb, z + up), bar.d)
        z2 = z + bar.d / 1000.0
        for j in range(ny_):
            py = y - l_ / 2 + cv + (l_ - 2 * cv) * (j / (ny_ - 1) if ny_ > 1 else 0.5)
            xa, xb = x - w / 2 + cv, x + w / 2 - cv
            n += _bar(mm, (xa, py, z2), (xb, py, z2), bar.d)
            n += _bar(mm, (xa, py, z2), (xa, py, z2 + up), bar.d)
            n += _bar(mm, (xb, py, z2), (xb, py, z2 + up), bar.d)
        # เหล็กรัดรอบ (as S-09): a ring round the turned-up ends, half way up
        rc = cv - 0.012
        zr = z + up * 0.6
        n += _ring(mm, [(x - w / 2 + rc, y - l_ / 2 + rc, zr), (x + w / 2 - rc, y - l_ / 2 + rc, zr),
                        (x + w / 2 - rc, y + l_ / 2 - rc, zr), (x - w / 2 + rc, y + l_ / 2 - rc, zr)], 9)
    if n:
        out.append(_group(mm, "footing_mesh", "ฐานราก", "เหล็กตะแกรงฐานราก", COLORS["mesh"]))
    # slabs: both ways at the cover above the soffit
    mm = Mesh()
    n = 0
    for sl in E["slabs"]:
        sp = lib.get(sl["mark"]) or {}
        bar = R.parse_bar(sp.get("bars"))
        if not bar or not bar.s or B.is_precast(sp):
            continue
        rm = sl["room"]
        t = float(sp.get("t", 0.10))
        z = float(sl.get("z", 0.0)) - t + R.COVER["slab"] + bar.d / 2000.0
        x0, y0 = float(rm["x"]), float(rm["y"])
        x1, y1 = x0 + float(rm["w"]), y0 + float(rm["d"])
        c = 0.05
        k = 0
        x = x0 + c
        while x <= x1 - c + 1e-6 and k < 400:
            n += _bar(mm, (x, y0 + c, z), (x, y1 - c, z), bar.d)
            x += bar.s
            k += 1
        y = y0 + c
        while y <= y1 - c + 1e-6 and k < 800:
            n += _bar(mm, (x0 + c, y, z + bar.d / 1000.0), (x1 - c, y, z + bar.d / 1000.0), bar.d)
            y += bar.s
            k += 1
    if n:
        out.append(_group(mm, "slab_mesh", "พื้น", "เหล็กเสริมพื้น", COLORS["mesh"]))
    # the same lift as the built members (B.build: the ground at z = 0 in the model)
    B.lift_groups(out, B.floor_lift(B.settings_of(data)))
    return out


#: the built concrete kinds that hold bars (made see-through while the bars show)
CONCRETE_KINDS = ("footing", "stump", "column", "beam", "slab", "stair")
