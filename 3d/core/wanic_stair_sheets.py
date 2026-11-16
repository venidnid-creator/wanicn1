# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""แบบขยายบันได — as the standard house plans draw it (A-08 of บ้านครอบครัว
ไทยเป็นสุข ๓): the plan at 1:50 with every step numbered, the way up and the
overall sizes; the section at 1:50 with both flights (the second returning
above the first), the landing, the waist slab, the handrail 0.90 m and the
levels; a detail of the steps at 1:10; the notes with the law's checks.
And the structural sheet: the waist slab and landing with their bars."""
from __future__ import annotations

import math

from core import wanic_building as B
from core import wanic_stair as ST


def stairs_to_detail(E) -> list:
    """The distinct stairs (the ground floor's; a stair repeated on every
    floor is drawn once)."""
    seen, out = set(), []
    for e in sorted(E["stairs"], key=lambda e: e["floor"]):
        st = e["st"]
        key = (round(float(st["x"]), 2), round(float(st["y"]), 2), B.stair_type(st), st.get("dir"), st.get("w"))
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out[:3]


def a_stair_detail(sh, E, e):
    from core import wanic_drawings as D
    s = E["settings"]
    st = e["st"]
    lay = B.stair_layout(st, s)
    pl = B.stair_plan(st, s)
    x0, y0, x1, y1 = D.drawing_area()
    n, R_, g, w, H = lay["n"], lay["R"], lay["g"], lay["w"], lay["H"]
    fl = lay["flights"]
    # ---- the plan, 1:50 -----------------------------------------------------------
    xs = [p[0] for p in lay["rect"]]
    ys = [p[1] for p in lay["rect"]]
    mx, my = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    v = D.View(sh, 50, (mx, my), (x0 + 70, y1 - 95))
    t = float(s.get("wall_t") or 0.1)
    rx0, rx1, ry0, ry1 = min(xs) - t, max(xs) + t, min(ys) - t, max(ys) + t
    for a, b in (((rx0, ry0), (rx1, ry0)), ((rx1, ry0), (rx1, ry1)), ((rx1, ry1), (rx0, ry1)),
                 ((rx0, ry1), (rx0, ry0))):
        sh.line(v(*a), v(*b), "wall", 0.25, dash=True)
    for poly in pl["polys"]:
        sh.poly([v(*p) for p in poly], "wall", 0.35)
    for a, b in pl["treads"]:
        sh.line(v(*a), v(*b), "wall", 0.18)
    walk = [v(*p) for p in pl["walk"]]
    for a, b in zip(walk, walk[1:]):
        sh.line(a, b, "dim", 0.25)
    sh.circle(walk[0], 0.9, "dim", 0.25)
    sh.text((walk[0][0], walk[0][1] - 4.0), "ขึ้น", 2.4, "center", "dim", True)
    k = 0
    for f in fl:
        for i in range(f["n"]):
            k += 1
            u = (i + 0.5) * g
            p = v(f["p0"][0] + f["d"][0] * u, f["p0"][1] + f["d"][1] * u)
            sh.text((p[0] + 2.2, p[1] - 0.8), str(k), 1.8, "center")
    D.dim_chain(sh, v, [min(xs), max(xs)], min(ys) - t - 0.5, "x")
    D.dim_chain(sh, v, [min(ys), max(ys)], min(xs) - t - 0.5, "y")
    D.caption(sh, (x0 + 70, y1 - 175), "แปลนขยายบันได", "1:50")
    # ---- the section, 1:50 (both flights; the second returns above the first) --------
    n1 = fl[0]["n"]
    L1 = n1 * g
    land = w if len(fl) > 1 else 0.0
    vs = D.View(sh, 50, (0.0, 0.0), (x0 + 170, y1 - 160))
    pts = [(0.0, 0.0)]
    for i in range(n1):
        pts += [(i * g, (i + 1) * R_), ((i + 1) * g, (i + 1) * R_)]
    pts.append((L1 + land, n1 * R_))
    sh.poly([vs(*p) for p in pts], "wall", 0.35, closed=False)
    ts = float(st.get("t") or s.get("stair_t") or 0.15)
    ang = math.atan2(R_, g)
    off = ts / math.cos(ang)
    sh.line(vs(0.0, -off + 0.0), vs(L1 - g, (n1 - 1) * R_ - off + R_), "wall", 0.35)
    sh.line(vs(L1 - g, n1 * R_ - off), vs(L1 + land, n1 * R_ - off), "wall", 0.35)
    if len(fl) > 1:
        n2 = fl[1]["n"]
        z = n1 * R_
        p2 = [(L1 + land, z), (L1, z)]
        u = L1
        for j in range(n2):
            p2 += [(u, z + (j + 1) * R_), (u - g, z + (j + 1) * R_)]
            u -= g
        p2.append((u - 0.6, H))
        sh.poly([vs(*p) for p in p2], "wall", 0.35, closed=False)
        sh.line(vs(L1, z + R_ - off), vs(L1 - n2 * g, H - off), "wall", 0.25, dash=True)
    # the floors and levels
    sh.line(vs(-0.8, 0.0), vs(0.0, 0.0), "wall", 0.5)
    sh.line(vs(-0.8, H), vs(0.6 if len(fl) > 1 else L1 + 0.6, H), "wall", 0.5)
    for z, lab in ((0.0, "±0.00"), (H, f"+{H:.2f}")) + (((n1 * R_, f"+{n1 * R_:.2f} ชานพัก"),) if len(fl) > 1 else ()):
        q = vs(L1 + land + 0.3, z)
        sh.line((q[0], q[1]), (q[0] + 6, q[1]), "dim", 0.13)
        sh.text((q[0] + 7, q[1] - 0.6), lab, 2.0)
    # the handrail 0.90 m above the nosings
    hr = 0.90
    sh.line(vs(0.0, R_ + hr), vs(L1 - g, n1 * R_ + hr), "door", 0.25)
    sh.text(vs(0.1, R_ + hr + 0.15), "ราวจับ สูง 0.90 ม.", 1.8)
    k = 0
    for i in range(n1):
        k += 1
        p = vs((i + 0.5) * g, (i + 1) * R_ + 0.06)
        sh.text(p, str(k), 1.6, "center")
    if len(fl) > 1:
        u = L1
        for j in range(fl[1]["n"]):
            k += 1
            p = vs(u - 0.5 * g, n1 * R_ + (j + 1) * R_ + 0.06)
            sh.text(p, str(k), 1.6, "center")
            u -= g
    D.caption(sh, (x0 + 210, y1 - 175), "รูปตัดบันได", "1:50")
    # ---- the steps, 1:10 ---------------------------------------------------------------
    vd = D.View(sh, 10, (0.0, 0.0), (x0 + 205, y0 + 30))
    sp = [(-g, 0.0), (0.0, 0.0), (0.0, R_), (g, R_), (g, 2 * R_), (2 * g, 2 * R_)]
    sh.poly([vd(*p) for p in sp], "wall", 0.35, closed=False)
    sh.line(vd(-g, -off), vd(2 * g, 2 * R_ - off + 0.0), "wall", 0.35)
    D.dim_chain(sh, vd, [0.0, g], 2 * R_ + 0.08, "x")
    D.dim_chain(sh, vd, [0.0, R_], 2 * g + 0.08, "y")
    sh.text(vd(-g, 2 * R_ + 0.05), "ผิวขั้นตามรายการวัสดุ (กระเบื้อง/ไม้) จมูกขั้นกันลื่น", 1.8)
    D.caption(sh, (x0 + 230, y0 + 8), "แบบขยายขั้นบันได", "1:10")
    # ---- notes -------------------------------------------------------------------------------
    flights = " / ".join(str(f["n"]) for f in fl)
    D.notes_block(sh, x0, y0 + 75, "รายละเอียดบันได", [
        f"1. ความสูงชั้น {H:.2f} ม. ลูกตั้ง {n} ขั้น สูงขั้นละ {R_ * 100:.2f} ซม. ลูกนอน {g * 100:.0f} ซม.",
        f"2. กว้าง {w:.2f} ม. แบบ {B.STAIR_TYPES[lay['type']]} ช่วงละ {flights} ขั้น",
        f"3. 2R+G = {2 * R_ + g:.3f} ม. (เดินสบาย 0.60-0.65 ม.)",
        "4. กฎกระทรวง ฉบับที่ 55: ลูกตั้งไม่เกิน 20 ซม. ลูกนอนไม่น้อยกว่า 22 ซม.",
        "   กว้างไม่น้อยกว่า 80 ซม. ทุกช่วงสูงไม่เกิน 3.00 ม. ต้องมีชานพัก",
        "5. ราวจับ/ราวกันตกสูงไม่น้อยกว่า 0.90 ม. จากจมูกขั้น",
        f"6. ท้องบันได ค.ส.ล. หนา {ts * 100:.0f} ซม. เหล็กเสริมตามแบบโครงสร้าง",
    ], 2.2, 80)


def s_stair_detail(sh, E, e):
    """รายละเอียดบันได คสล.: the waist slab and landing in section with the
    main and distribution bars, and the landing beam."""
    from core import wanic_drawings as D
    s = E["settings"]
    st = e["st"]
    lay = B.stair_layout(st, s)
    p = ST.params(s)
    x0, y0, x1, y1 = D.drawing_area()
    R_, g = lay["R"], lay["g"]
    fl = lay["flights"]
    n1 = fl[0]["n"]
    L1 = n1 * g
    ts = float(st.get("t") or s.get("stair_t") or 0.15)
    ang = math.atan2(R_, g)
    off = ts / math.cos(ang)
    land = lay["w"] if len(fl) > 1 else 0.0
    v = D.View(sh, 20, (0.0, 0.0), (x0 + 30, y0 + 70))
    pts = [(0.0, 0.0)]
    for i in range(n1):
        pts += [(i * g, (i + 1) * R_), ((i + 1) * g, (i + 1) * R_)]
    pts.append((L1 + land, n1 * R_))
    sh.poly([v(*q) for q in pts], "wall", 0.35, closed=False)
    sh.line(v(0.0, -off), v(L1 - g, n1 * R_ - off), "wall", 0.35)
    sh.line(v(L1 - g, n1 * R_ - off), v(L1 + land, n1 * R_ - off), "wall", 0.35)
    c = 0.025 / math.cos(ang)
    sh.line(v(0.0, -off + c), v(L1 - g, n1 * R_ - off + c), "rebar", 0.5)            # main bars, bottom
    sh.line(v(L1 - g, n1 * R_ - off + 0.025), v(L1 + land, n1 * R_ - off + 0.025), "rebar", 0.5)
    sh.line(v(0.4, 0.4 * R_ / g - off + ts - c), v(L1 - g, n1 * R_ - c), "rebar", 0.35)  # top bars at the supports
    for i in range(1, int(L1 / 0.15)):
        u = i * 0.15
        q = v(u, u * R_ / g - off + c + 0.012)
        sh.circle(q, 0.35, "rebar", 0.25)
    # what the bars are, with leaders
    um = L1 * 0.45
    for (u, dz, text) in ((um, -off + c, f"เหล็กหลัก {st.get('bars') or p['stair_bars']} (ล่าง)"),
                          (um * 0.6, -off + c + 0.012, f"เหล็กกันร้าว {st.get('temp') or p['stair_temp']}"),
                          (L1 * 0.8, ts - c - off, "เหล็กบนช่วงรองรับ ยาว L/4")):
        a = v(u, u * R_ / g + dz)
        b = (a[0] + 25, a[1] - 18 - (8 if "กันร้าว" in text else 0))
        sh.line(a, b, "dim", 0.13)
        sh.line(b, (b[0] + 4, b[1]), "dim", 0.13)
        sh.text((b[0] + 5, b[1] - 0.8), text, 2.4)
    if land:
        bs = ST.beam_spec(p["stair_beam"])
        bx = L1 + land
        sh.rect(*v(bx - bs["b"], n1 * R_ - bs["h"]), *v(bx, n1 * R_), "struct", 0.35)
        sh.text(v(bx - bs["b"] / 2, n1 * R_ - bs["h"] - 0.12), "BS1", 2.2, "center", "struct", True)
    D.notes_block(sh, x0 + 200, y1 - 10, "รายละเอียดบันได ค.ส.ล.", [
        f"ท้องบันไดหนา {ts * 100:.0f} ซม. ออกแบบเป็นพื้นทางเดียวพาดตามแนวบันได",
        f"เหล็กหลัก {st.get('bars') or p['stair_bars']} (ล่าง ตามแนวบันได)",
        f"เหล็กกันร้าว {st.get('temp') or p['stair_temp']} (ตามขวาง)",
        f"คานรับชานพัก BS1 {p['stair_beam']}" if land else "ไม่มีชานพัก",
        f"น้ำหนักจรบันได {float(p['stair_ll']):,.0f} กก./ตร.ม.",
        "ระยะหุ้มเหล็ก 2.0 ซม. ทาบเหล็ก 40d (DB) / 48d (RB)",
        "รายการคำนวณ: ดูรูปเล่มรายการคำนวณหน้าบันได",
    ], 2.4, 80)
    D.caption(sh, ((x0 + x1) / 2, y0 + 4), "รายละเอียดบันได ค.ส.ล.", "1:20")
