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
    for p, q in B.stair_railing(st, s)["plan"]:       # ราวบันได on the open side
        sh.line(v(*p), v(*q), "door", 0.35)
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
    # ราวบันได: the hardwood rail 2"x4" on a baluster at every tread, 0.90 m above the nosings
    hr = B.RAIL_H
    up_to = L1 if len(fl) > 1 else L1 - g             # to the landing's edge: both flights meet level there
    z_up = (n1 + 1) * R_ if len(fl) > 1 else n1 * R_
    for dz in (0.0, 0.10):
        sh.line(vs(0.0, R_ + hr - dz), vs(up_to, z_up + hr - dz), "door", 0.25)
    if len(fl) > 1:
        sh.line(vs(L1, n1 * R_), vs(L1, z_up + hr), "door", 0.35)              # the post at the turn
    for i in range(n1):
        u = (i + 0.5) * g
        sh.line(vs(u, (i + 1) * R_), vs(u, (i + 1.5) * R_ + hr - 0.10), "door", 0.18)
    sh.line(vs(0.0, R_), vs(0.0, R_ + hr), "door", 0.35)                       # the newel at the foot
    if len(fl) > 1:
        z = n1 * R_
        u = L1
        for j in range(fl[1]["n"]):
            uu = u - 0.5 * g
            sh.line(vs(uu, z + (j + 1) * R_), vs(uu, z + (j + 1.5) * R_ + hr - 0.10), "door", 0.13, dash=True)
            u -= g
        n2 = fl[1]["n"]                               # its rail, behind: dashed, level at the top
        sh.line(vs(L1, z + R_ + hr), vs(L1 - (n2 - 1) * g, z + n2 * R_ + hr), "door", 0.18, dash=True)
        sh.line(vs(L1 - (n2 - 1) * g, z + n2 * R_ + hr), vs(L1 - n2 * g, z + n2 * R_ + hr), "door", 0.18,
                dash=True)
    lab = vs(-0.5, R_ + hr + 0.9)                     # the label to the left, with a leader to the rail
    tip = vs(L1 * 0.25, R_ + hr + L1 * 0.25 * R_ / g)
    sh.line(tip, (lab[0] + 1, lab[1] - 1), "dim", 0.13)
    sh.line((lab[0] + 1, lab[1] - 1), (lab[0] - 4, lab[1] - 1), "dim", 0.13)
    first, _sp, second = B.RAIL_TEXT.partition(" ลูกกรง")
    sh.text((lab[0] - 5, lab[1] + 1.6), first, 1.8, "right")
    sh.text((lab[0] - 5, lab[1] - 2.0), "ลูกกรง" + second, 1.8, "right")
    D.dim_chain(sh, vs, [n1 * R_ - g * 0, n1 * R_ + hr], L1 - g + 0.3, "y")
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
        f"5. {B.RAIL_TEXT} สูง {B.RAIL_H:.2f} ม. จากจมูกขั้น",
        "   ลูกกรงทุกขั้น ยาวรวม %.2f ม. (เส้นสีในแปลน = แนวราวบันได)" % B.stair_railing(st, s)["length"],
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


def s_stair_flight(sh, E, e, fi, no=1):
    """รายละเอียดบันได คสล. one flight a sheet, as the standard (S-14, S-15):
    the flight from its support to the landing (or the floor) at 1:20 — the
    waist slab and landing, the beams carrying them, the main bars hooked
    into the beams, the top bars over the supports (L/4), the bars of every
    step and the bar at each nosing, the distribution bars; the run
    «n@g = L», the rise «n @ R = H», the waist thickness, the levels."""
    from core import wanic_drawings as D
    from core import wanic_std_sheets as STD
    s = E["settings"]
    st = e["st"]
    lay = B.stair_layout(st, s)
    p = ST.params(s)
    fl = lay["flights"]
    R_, g = lay["R"], lay["g"]
    n = fl[fi]["n"]
    wl = lay["w"]
    land_lo = fi > 0                                       # the flight starts on a landing
    land_hi = fi < len(fl) - 1                             # and ends on one
    ts = float(st.get("t") or s.get("stair_t") or 0.15)
    ang = math.atan2(R_, g)
    off = ts / math.cos(ang)
    bs = ST.beam_spec(p["stair_beam"])
    lib = E["lib"]
    fb = next((lib[b["mark"]] for b in E["beams"] if b["mark"] in lib), {"b": 0.2, "h": 0.4})
    fbb, fbh = float(fb.get("b", 0.2)), float(fb.get("h", 0.4))
    bars = st.get("bars") or p["stair_bars"]
    temp = st.get("temp") or p["stair_temp"]
    _n, bname, _d, bsp = D._bars(bars)
    _n, tname, _d, tsp = D._bars(temp)
    tsp = tsp or 0.15
    H = n * R_
    u_top = (n - 1) * g                                    # the last riser: the landing / floor begins
    u_lo = -wl if land_lo else 0.0
    u_hi = u_top + g + wl if land_hi else u_top
    x0, y0, x1, y1 = D.drawing_area()
    span = (u_hi - u_lo) + (fbb if not land_lo else 0) + 0.6
    k = 1000.0 / next(sc for sc in (20, 25, 30, 40, 50) if span * 1000 / sc <= (x1 - x0) - 118
                      and (H + 1.0) * 1000 / sc <= (y1 - y0) - 70)
    sc = round(1000 / k)
    ox = x0 + 44 + (-u_lo + (fbb if not land_lo else 0.0) + 0.5) * k
    oy = max(y0 + 75 + 0.6 * k, (y0 + y1) / 2 - H * k / 2 + 6)

    def P(u, z):
        return (ox + u * k, oy + z * k)
    # -- concrete outline: the steps, the landing(s), the soffit
    top = [P(u_lo, 0.0), P(0.0, 0.0)] if land_lo else [P(0.0, 0.0)]
    for i in range(n):
        top += [P(i * g, (i + 1) * R_), P(min((i + 1) * g, u_top) if i == n - 1 else (i + 1) * g, (i + 1) * R_)]
    top.append(P(u_hi, H))
    sh.poly(top, "cut", 0.55, closed=False)
    ux_lo = (off - ts) * g / R_ if land_lo else 0.0          # the soffit meets the landing's underside
    ux_hi = (H - ts + off) * g / R_
    bot = []
    if land_lo:
        bot.append(P(u_lo + bs["b"], -ts))
        bot.append(P(ux_lo, -ts))
    else:
        bot.append(P(0.0, -off))
    if land_hi:
        bot += [P(ux_hi, H - ts), P(u_hi - bs["b"], H - ts)]
    else:
        bot.append(P(u_top, u_top * R_ / g - off))
    sh.poly(bot, "cut", 0.55, closed=False)
    # the beams: the landing beam(s) with the post under, the floor beams
    def beam(ua, ub, ztop, h, name, post=False):
        sh.poly([P(ua, ztop), P(ua, ztop - h), P(ub, ztop - h), P(ub, ztop), P(ua, ztop)], "cut", 0.55, closed=False)
        sh.text((P(ub, 0)[0] + 1.2, P(0, ztop - h)[1] - 3.2) if post else
                ((P(ua, 0)[0] + P(ub, 0)[0]) / 2, P(0, ztop - h)[1] - 4.0), name, 2.5, "left" if post else "center")
        if post:
            sh.line(P(ua + 0.02, ztop - h), P(ua + 0.02, ztop - h - 0.5), "cut", 0.4)
            sh.line(P(ub - 0.02, ztop - h), P(ub - 0.02, ztop - h - 0.5), "cut", 0.4)
            STD._break_h(sh, P(0, ztop - h - 0.5)[1], P(ua + 0.02, 0)[0], P(ub - 0.02, 0)[0])
    if land_lo:
        beam(u_lo, u_lo + bs["b"], 0.0, bs["h"], "BS1", True)
        sh.line(P(u_lo, 0.0), P(u_lo, -bs["h"]), "cut", 0.55)
    else:
        beam(-fbb, 0.0, 0.0, fbh, "คานพื้น")
        sh.line(P(-fbb - 0.5, 0.0), P(-fbb, 0.0), "cut", 0.55)                # the floor beyond, to a break
        STD._break_v(sh, P(-fbb - 0.5, 0)[0], P(0, -0.12)[1], P(0, 0)[1])
    if land_hi:
        beam(u_hi - bs["b"], u_hi, H, bs["h"], "BS1", True)
    else:
        beam(u_top, u_top + fbb, H, fbh, "คานพื้น")
        sh.line(P(u_top + fbb, H), P(u_top + fbb + 0.5, H), "cut", 0.55)
        sh.line(P(u_top + fbb, H - 0.12), P(u_top + fbb + 0.5, H - 0.12), "cut", 0.55)
        STD._break_v(sh, P(u_top + fbb + 0.5, 0)[0], P(0, H - 0.12)[1], P(0, H)[1])
    # -- the bars
    c = 0.025
    cs = c / math.cos(ang)
    main = []                                              # the main bars along the soffit, hooked into the beams
    if land_lo:
        main += [P(u_lo + 0.05, -ts + c + 0.12), P(u_lo + 0.05, -ts + c), P(ux_lo + c * 0.4, -ts + c)]
    else:
        main += [P(-fbb + 0.05, -fbh + 0.08), P(-fbb + 0.05, -off + cs - 0.02), P(0.0, -off + cs)]
    if land_hi:
        main += [P(ux_hi - c * 0.4, H - ts + c), P(u_hi - 0.05, H - ts + c), P(u_hi - 0.05, H - ts + c + 0.12)]
    else:
        main += [P(u_top, u_top * R_ / g - off + cs), P(u_top + fbb - 0.05, H - fbh + 0.12),
                 P(u_top + fbb - 0.05, H - fbh + 0.06)]
    sh.poly(main, "rebar", 0.5, closed=False)
    l4 = max(0.6, (n * g) / 4)                              # the top bars over the supports
    if land_lo:
        sh.poly([P(u_lo + 0.08, -c - 0.12), P(u_lo + 0.08, -c), P(0.0, -c), P(l4 * math.cos(0), l4 * R_ / g - cs)],
                "rebar", 0.45, closed=False)
    else:
        sh.poly([P(-fbb + 0.08, -0.15), P(-fbb + 0.08, -c), P(0.0, -c), P(l4, l4 * R_ / g - cs)],
                "rebar", 0.45, closed=False)
    ue = u_hi - 0.08 if land_hi else u_top + fbb - 0.08
    uk = u_top + g - c * g / R_                             # the slab's top meets the landing / floor
    sh.poly([P(uk - l4, (uk - l4) * R_ / g - cs), P(uk, H - c), P(ue, H - c),
             P(ue, H - c - 0.15)], "rebar", 0.45, closed=False)
    for i in range(n - 1):                                 # each step: its bar and the nosing bar
        a = P(i * g + c, i * R_ + R_ * 0.25)
        nz = P((i + 1) * g - c, (i + 1) * R_ - c)
        sh.poly([a, P(i * g + c, (i + 1) * R_ - c), nz, P((i + 1) * g - c, (i + 1) * R_ - R_ * 0.75)],
                "rebar", 0.3, closed=False)
        STD._dot(sh, (nz[0] - 0.6, nz[1] - 0.6), 0.5)
    u = 0.08
    while u < u_top - 0.05:                                # the distribution bars on the main bars
        q = P(u, u * R_ / g - off + cs + 0.02)
        STD._dot(sh, q, 0.45)
        u += tsp * math.cos(ang)
    # -- labels at the right, kept apart
    tx = P(u_hi, 0)[0] + (fbb * k if not land_hi else 0) + 20
    pts = [(P(uk - l4 * 0.5, (uk - l4 * 0.5) * R_ / g - cs), f"เหล็กบน {bname} มม.@{bsp:.2f} ยาว L/4"),
           (P(u_top * 0.55 + g * 0.5 - c, (int(u_top * 0.55 / g) + 1) * R_ - c), f"{tname} มม. ทุกมุม (ขั้นบันได)"),
           (P(u_top * 0.6, u_top * 0.6 * R_ / g - off + cs), f"เหล็กหลัก {bname} มม.@{bsp:.2f} (ล่าง)"),
           (P(u_top * 0.4, u_top * 0.4 * R_ / g - off + cs + 0.02), f"เหล็กกันร้าว {tname} มม.@{tsp:.2f}"),
           (P(u_top * 0.3, u_top * 0.3 * R_ / g - off / 2), f"ท้องบันไดหนา {ts:.2f} ม.")]
    last = None
    for q, lab in sorted(pts, key=lambda t: -t[0][1]):
        ty = q[1] if last is None else min(q[1], last - 6.0)
        last = ty
        sh.circle(q, 0.45, "text", 0.2)
        sh.line(q, (tx - 2, ty), "text", 0.15)
        sh.line((tx - 2, ty), (tx + len(lab) * 1.3, ty), "text", 0.15)
        sh.text((tx + 0.5, ty + 0.9), lab, 2.5)
    # -- sizes and levels
    yb = P(0, -max(fbh, bs["h"]) - 0.6)[1] - 8
    chain = ([u_lo] if land_lo else []) + [0.0, u_top] + ([u_hi] if land_hi else [])
    for a, b_ in zip(chain, chain[1:]):
        txt = f"{n - 1}@{g:.2f} = {u_top:.2f}" if (a, b_) == (0.0, u_top) else f"{b_ - a:.2f}"
        STD._hdim(sh, P(a, 0)[0], P(b_, 0)[0], yb, txt)
    STD._hdim(sh, P(chain[0], 0)[0], P(chain[-1], 0)[0], yb - 7, f"{chain[-1] - chain[0]:.2f}")
    for xq in (chain[0], chain[-1]):
        sh.line(P(xq, -0.05), (P(xq, 0)[0], yb - 8.4), "dim", 0.12, True)
    xv = P(u_hi, 0)[0] + (fbb * k if not land_hi else 0) + 9                 # the rise, beside the flight
    STD._vdim(sh, xv, P(0, 0)[1], P(0, H)[1], "")
    sh.text((xv - 1.2, (P(0, 0)[1] + P(0, H)[1]) / 2), f"{n} @ {R_ * 100:.2f} ซม. = {H:.2f} ม.",
            2.5, "center", "dim", angle=90)
    z_base = float(fl[fi].get("z0", 0.0))
    fl_no = int(e.get("floor", 0)) + 1
    names = (f"ระดับพื้นชั้น {fl_no}" if not land_lo else "ระดับชานพัก",
             f"ระดับพื้นชั้น {fl_no + 1}" if not land_hi else "ระดับชานพัก")
    for zz, nm, uu, side in ((0.0, names[0], u_lo - (0 if land_lo else fbb + 0.5), -1),
                             (H, names[1], u_hi + (0 if land_hi else fbb + 0.5), 1)):
        q = P(uu, zz)
        q = (q[0] + side * 3.0, q[1])
        sh.line((q[0] - side * 3.0, q[1]), (q[0] + side * 2.0, q[1]), "dim", 0.15)
        sh.poly([q, (q[0] - 1.4, q[1] + 2.2), (q[0] + 1.4, q[1] + 2.2)], "dim", 0.2)
        lv = z_base + zz + int(e.get("floor", 0)) * float(E["H"])
        lab = f"{nm} {'±0.00' if abs(lv) < 0.005 else f'{lv:+.2f}'}"
        if side < 0:
            sh.text((q[0] - 2.0, q[1] + 0.8), lab, 2.4, "right", "dim")
        else:
            sh.text((q[0] + 2.0, q[1] + 3.0), lab, 2.4, "left", "dim")
    STD._title(sh, P((chain[0] + chain[-1]) / 2, 0)[0], yb - 22, f"ST.{no}", f"1:{sc}",
               f"({names[0]} – {names[1]})")
    D.notes_block(sh, x1 - 96, y1 - 10, "หมายเหตุ", [
        f"1. ท้องบันไดหนา {ts * 100:.0f} ซม. ออกแบบเป็นพื้นทางเดียวพาดตามแนวบันได",
        f"2. ลูกตั้ง {R_ * 100:.2f} ซม. ลูกนอน {g * 100:.0f} ซม. (กฎกระทรวง ฉบับที่ 55)",
        f"3. คานรับชานพัก BS1 {p['stair_beam']}" if (land_lo or land_hi) else "3. ปลายบันไดฝากคานพื้น",
        "4. ระยะหุ้มเหล็ก 2.0 ซม. ทาบเหล็ก 40 เท่า (DB) / 48 เท่า (RB)",
        f"5. น้ำหนักจรบันได {float(p['stair_ll']):,.0f} กก./ตร.ม. ดูรายการคำนวณ",
    ], 2.4, 92)
    sh.scale = f"1:{sc}"
    return sc
