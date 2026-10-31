# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""The road design (:mod:`core.wanic_road`) as a drawing set, sheet by
sheet — laid out like a road study's plan-and-profile and cross-section
sheets:

* **G** — ข้อมูลทั่วไป: key plan of the whole alignment with the sheet
  boxes, design data, horizontal and vertical curve tables, benchmark /
  control points (with latitude and longitude), legend;
* **PP** — แปลนและรูปตัดตามยาว: the plan of a stretch (contours from the
  survey, the road edges, shoulders, the toe of cut and fill, stations,
  PI / PC / PT, benchmarks, a north arrow and grid ticks) over its profile
  (ground, grade, vertical curves with PVI data, grades) and the bands
  (ground and design levels, cut and fill heights, horizontal and
  vertical alignment diagrams), with a key plan;
* **ST** — รูปตัดขวาง: every cross section on a grid, cut and fill
  shaded, with its areas, volumes and running totals, ground (CT) and
  design (CR) levels;
* **VT** — ตารางปริมาณดิน: the earthworks table, station by station, and
  the pavement layer quantities.

Sheets are :class:`core.wanic_drawings.Sheet` (A3, mm) with the same
title column, printed by the same PDF writer and DXF writer.  Pure
Python: no Qt.
"""
from __future__ import annotations

import math
import re

from core import wanic_drawings as D
from core.road import alignment as A
from core.road import profile as P

ROLES = [("วิศวกร", "สำรวจ", "วิศวกร"), ("วิศวกร", "ออกแบบทาง", "วิศวกร"),
         ("วิศวกร", "โครงสร้าง/ระบายน้ำ", "วิศวกร"), ("ผู้ตรวจ", "", ""),
         ("ผู้อนุมัติ", "", "")]
BM_CODES = re.compile(r"^(BM|CP|GPS|GNSS|PK|PRS|หมุด|RTK|PI|POT|PC\b|PT\b)", re.I)
#: The PDF pens of a road sheet (like a road study's coloured sheets).
COLORS = {"grid": (34, 139, 34), "roof": (200, 30, 30), "dim": (30, 70, 190),
          "hidden": (175, 175, 175), "wall": (60, 60, 60)}
CUT_RGB = (246, 190, 190)
FILL_RGB = (190, 228, 190)

W, H = D.PAPER
X0, Y0, X1, Y1 = D.drawing_area()          # 15, 15, 343, 282


def sta(s: float, dec: int = 2) -> str:
    return A.format_station(s, dec)


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------

def _rot(p, c, ang):
    """Rotate model point p about c by -ang (radians) — the stretch runs
    left to right on the sheet."""
    ca, sa = math.cos(-ang), math.sin(-ang)
    dx, dy = p[0] - c[0], p[1] - c[1]
    return (dx * ca - dy * sa, dx * sa + dy * ca)


def _seg_dist(p, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    L2 = vx * vx + vy * vy
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((p[0] - a[0]) * vx +
                                                  (p[1] - a[1]) * vy) / L2))
    return math.hypot(p[0] - a[0] - t * vx, p[1] - a[1] - t * vy)


def _near(p, line, d):
    return any(_seg_dist(p, a, b) <= d for a, b in zip(line, line[1:]))


def contours(tin, keep, interval):
    """[(level, ((x,y),(x,y)))] of the TIN's triangles that ``keep``."""
    out = []
    pts = tin.points
    for t in tin.triangles:
        a, b, c = (pts[i] for i in t)
        zs = (a[2], b[2], c[2])
        lo, hi = min(zs), max(zs)
        if hi - lo < 1e-9:
            continue
        if not keep(((a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3)):
            continue
        lvl = math.ceil(lo / interval) * interval
        while lvl < hi:
            seg = []
            for p, q in ((a, b), (b, c), (c, a)):
                if (p[2] - lvl) * (q[2] - lvl) < 0:
                    f = (lvl - p[2]) / (q[2] - p[2])
                    seg.append((p[0] + f * (q[0] - p[0]), p[1] + f * (q[1] - p[1])))
            if len(seg) == 2:
                out.append((lvl, (seg[0], seg[1])))
            lvl += interval
        _ = lo
    return out


def clip(a, b, box):
    """Liang–Barsky: the part of segment a-b inside box (x0,y0,x1,y1)."""
    x0, y0, x1, y1 = box
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0),
                 (dy, y1 - a[1])):
        if abs(p) < 1e-12:
            if q < 0:
                return None
            continue
        r = q / p
        if p < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return None
    return ((a[0] + t0 * dx, a[1] + t0 * dy), (a[0] + t1 * dx, a[1] + t1 * dy))


def edges_of(an, s0, s1, step=2.0):
    """Offset lines of the stretch: pavement, shoulder and the toe of the
    side slopes (from the sections) — {name: [(x, y)…]} for each side."""
    st = an.settings
    half = st.width / 2.0
    out = {"ep_l": [], "ep_r": [], "sh_l": [], "sh_r": [], "toe_l": [],
           "toe_r": []}
    s = s0
    while s <= s1 + 1e-6:
        p = A.point_at(an.axis, min(s, an.length))
        out["ep_l"].append(p.offset_point(-half))
        out["ep_r"].append(p.offset_point(half))
        if st.shoulder > 0:
            out["sh_l"].append(p.offset_point(-half - st.shoulder))
            out["sh_r"].append(p.offset_point(half + st.shoulder))
        s += step
    for sec in an.sections:
        if s0 - 1e-6 <= sec.s <= s1 + 1e-6 and sec.design:
            p = A.point_at(an.axis, sec.s)
            out["toe_l"].append(p.offset_point(sec.design[0][0]))
            out["toe_r"].append(p.offset_point(sec.design[-1][0]))
    return out


def bench_marks(shots):
    return [s for s in (shots or []) if BM_CODES.match((s.code or "").strip()) or
            BM_CODES.match(s.name or "")]


# ---------------------------------------------------------------------------
# G — general sheet: key plan, design data, curve tables, control points
# ---------------------------------------------------------------------------

def key_plan(sh, an, box, chunks=None, mark=None, bms=(), labels=True):
    """The whole alignment fitted into ``box`` with the sheet stretches."""
    xs = [p[0] for p in an.axis]
    ys = [p[1] for p in an.axis]
    bx0, by0, bx1, by1 = box
    w, h = max(xs) - min(xs) or 1.0, max(ys) - min(ys) or 1.0
    k = min((bx1 - bx0 - 10) / w, (by1 - by0 - 10) / h)
    ox = bx0 + (bx1 - bx0 - w * k) / 2
    oy = by0 + (by1 - by0 - h * k) / 2

    def v(x, y):
        return (ox + (x - min(xs)) * k, oy + (y - min(ys)) * k)
    sh.rect(bx0, by0, bx1, by1, "text", 0.25)
    sh.poly([v(*p) for p in an.axis], "roof", 0.5, closed=False)
    for i, (s0, s1) in enumerate(chunks or [], 1):
        a = A.point_at(an.axis, s0)
        b = A.point_at(an.axis, s1)
        pa, pb = v(a.x, a.y), v(b.x, b.y)
        sh.line((pa[0] - 1.5, pa[1]), (pa[0] + 1.5, pa[1]), "dim", 0.25)
        if mark == i:
            seg = [v(*p) for p in an.axis if s0 <= A.station_of(an.axis, p) <= s1]
            seg = [pa] + seg + [pb]
            sh.poly(seg, "cut", 1.4, closed=False)
        if labels:
            m = A.point_at(an.axis, (s0 + s1) / 2)
            q = v(m.x, m.y)
            sh.text((q[0] + 2, q[1] + 1), f"PP-{i:02d}", 1.8, "left", "dim")
    for b in bms:
        q = v(b.e, b.n)
        sh.poly([(q[0], q[1] + 1.4), (q[0] - 1.2, q[1] - 0.8),
                 (q[0] + 1.2, q[1] - 0.8)], "grid", 0.25)
    s = A.point_at(an.axis, 0.0)
    q = v(s.x, s.y)
    sh.text((q[0] + 1.5, q[1] - 3), "เริ่มต้น 0+000", 1.8, "left", "text")
    e = A.point_at(an.axis, an.length)
    q = v(e.x, e.y)
    sh.text((q[0] + 1.5, q[1] - 3), f"สิ้นสุด {sta(an.length)}", 1.8, "left")
    D.north(sh, (bx1 - 7, by1 - 9), 4)


def curve_rows(an):
    rows = []
    for c in an.hcurves:
        if c.radius <= 0:
            rows.append((str(c.number), sta(c.s_pi), A.format_dms(c.delta) +
                         (" ขวา" if c.delta > 0 else " ซ้าย"), "มุมหักเห", "", "",
                         "", "", "", f"{c.pi[0]:,.3f}", f"{c.pi[1]:,.3f}"))
            continue
        rows.append((str(c.number), sta(c.s_pi), A.format_dms(c.delta) +
                     (" ขวา" if c.delta > 0 else " ซ้าย"), f"{c.radius:,.2f}",
                     f"{c.tangent:,.2f}", f"{c.length:,.2f}", f"{c.external:,.2f}",
                     sta(c.s_pc), sta(c.s_pt), f"{c.pi[0]:,.3f}", f"{c.pi[1]:,.3f}"))
    return rows


CURVE_COLS = [("โค้ง", 10, "center"), ("PI STA", 22, "center"),
              ("มุมเบี่ยง Δ", 30, "center"), ("R (ม.)", 18, "right"),
              ("T (ม.)", 16, "right"), ("L (ม.)", 16, "right"),
              ("E (ม.)", 14, "right"), ("PC", 22, "center"), ("PT", 22, "center"),
              ("PI ตะวันออก (E)", 30, "right"), ("PI เหนือ (N)", 30, "right")]


def vcurve_rows(an):
    rows = []
    for c in an.curves:
        a = c.g2 - c.g1
        k = c.length / abs(a) if abs(a) > 1e-9 else 0.0
        rows.append((sta(c.s), f"{c.z:,.3f}", f"{c.g1:+.2f}%", f"{c.g2:+.2f}%",
                     f"{a:+.2f}%", f"{c.length:,.2f}", f"{k:,.1f}",
                     "โค้งหงาย (Sag)" if a > 0 else "โค้งคว่ำ (Crest)",
                     sta(c.bvc), sta(c.evc)))
    return rows


VCURVE_COLS = [("PVI STA", 22, "center"), ("ระดับ PVI", 20, "right"),
               ("g1", 16, "right"), ("g2", 16, "right"), ("A", 16, "right"),
               ("L (ม.)", 16, "right"), ("K", 14, "right"),
               ("ชนิดโค้ง", 30, "center"), ("BVC", 22, "center"),
               ("EVC", 22, "center")]


def _val(v):
    return v() if callable(v) else v


def design_data(an, info):
    st = an.settings
    grades = P.grade_slopes([(s, z) for s, z, *_ in an.pvis]) if len(an.pvis) > 1 else []
    rmin = min((c.radius for c in an.hcurves if c.radius > 0), default=0)
    layers = ", ".join(f"{n} {t * 100:.0f} ซม." for n, t, _c in st.pavement_layers())
    return [
        ("ความยาวทาง", f"{an.length:,.2f} ม. (0+000 – {sta(an.length)})"),
        ("ความยาวที่ออกแบบระดับ", f"{_val(an.designed_length):,.2f} ม."),
        ("ความกว้างผิวจราจร", f"{st.width:.2f} ม."),
        ("ไหล่ทาง", f"{st.shoulder:.2f} ม. ข้างละ ลาด {st.shoulder_slope:.1f}%"),
        ("ความลาดขวางผิวทาง (หลังเต่า)", f"{st.crown:.2f}%"),
        ("ลาดดินตัด (H:V)", f"{st.cut_hv:g} : 1"),
        ("ลาดดินถม (H:V)", f"{st.fill_hv:g} : 1"),
        ("ความชันสูงสุด", f"{max((abs(g) for g in grades), default=0):.2f}%"),
        ("รัศมีโค้งราบต่ำสุด", f"{rmin:,.2f} ม." if rmin else "-"),
        ("จำนวนโค้งราบ / โค้งดิ่ง", f"{len(an.hcurves)} / {len(an.curves)}"),
        ("ชั้นโครงสร้างทาง", layers or "-"),
        ("ปริมาณดินขุดรวม", f"{an.cut_total:,.2f} ลบ.ม."),
        ("ปริมาณดินถมรวม", f"{an.fill_total:,.2f} ลบ.ม."),
        ("ระบบพิกัด", info.get("crs") or "UTM WGS84 โซน 47N · ระดับ MSL"),
        ("ช่วงตัดขวาง", f"ทุก {st.step:g} ม."),
    ]


def g_sheets(an, info, chunks, shots):
    out = []
    sh = D.Sheet("G-01", "ผังสังเขป ข้อมูลการออกแบบ ตารางโค้ง หมุดหลักฐาน", "-", "G")
    out.append(sh)
    bms = bench_marks(shots)
    key_plan(sh, an, (X0, Y1 - 120, X0 + 150, Y1), chunks, None, bms)
    sh.text((X0 + 75, Y1 - 125), "ผังสังเขป (แผนที่แสดงตำแหน่งแผ่น PP)", 2.6,
            "center", "text", True)
    y = Y1 - 3
    sh.text((X0 + 160, y), "ข้อมูลการออกแบบ", 3.4, "left", "text", True)
    y = D.table(sh, X0 + 160, y - 3, [("รายการ", 52, "left"), ("ค่า", 116, "left")],
                design_data(an, info), 2.1, 5.0, 5.5)
    # benchmarks
    zone = int(info.get("zone") or 47)
    datum = info.get("datum") or "WGS84"
    rows = []
    for b in bms[:12]:
        try:
            from core import wanic_road as R
            lat, lon = R.utm_to_wgs84(b.e, b.n, zone, datum)
            ll = f"{lat:.6f}, {lon:.6f}"
        except Exception:                               # noqa: BLE001
            ll = ""
        rows.append((b.name, f"{b.n:,.3f}", f"{b.e:,.3f}", f"{b.z:,.3f}", b.code, ll))
    y = Y1 - 140
    sh.text((X0, y), "ตารางหมุดหลักฐาน / หมุดควบคุม (BM, PI, POT สนาม)", 3.2, "left",
            "text", True)
    D.table(sh, X0, y - 3, [("ชื่อ", 16, "center"), ("เหนือ (N)", 28, "right"),
                            ("ตะวันออก (E)", 26, "right"), ("ระดับ MSL", 20, "right"),
                            ("รหัส", 18, "center"), ("ละติจูด, ลองจิจูด", 46, "center")],
            rows or [("-", "", "", "", "", "")], 2.0, 5.0, 5.5)
    # legend
    lx, ly = X0 + 160, min(y, Y0 + 70)
    sh.text((lx, ly), "สัญลักษณ์", 3.2, "left", "text", True)
    items = [("แนวศูนย์กลางทาง (CL)", "roof", 0.5, False),
             ("ขอบผิวจราจร / ไหล่ทาง", "wall", 0.35, False),
             ("ตีนลาดดินตัด-ถม", "dim", 0.25, True),
             ("เส้นชั้นความสูง", "grid", 0.13, False)]
    for i, (t, layer, w, dash) in enumerate(items):
        yy = ly - 7 - i * 5.5
        sh.line((lx, yy + 1), (lx + 14, yy + 1), layer, w, dash)
        sh.text((lx + 17, yy), t, 2.2)
    yy = ly - 7 - len(items) * 5.5
    sh.poly([(lx + 7, yy + 2.4), (lx + 5.8, yy + 0.2), (lx + 8.2, yy + 0.2)],
            "grid", 0.25)
    sh.text((lx + 17, yy), "หมุดหลักฐาน BM", 2.2)
    # curve tables (more sheets when long)
    hrows, vrows = curve_rows(an), vcurve_rows(an)
    per = 34
    for i in range(0, max(len(hrows), 1), per):
        g = D.Sheet(f"G-{len(out) + 1:02d}", "ตารางองค์ประกอบโค้งราบ และโค้งดิ่ง", "-",
                    "G")
        out.append(g)
        g.text((X0, Y1 - 3), "ตารางองค์ประกอบโค้งราบ (Horizontal curves)", 3.4,
               "left", "text", True)
        yy = D.table(g, X0, Y1 - 6, CURVE_COLS, hrows[i:i + per] or
                     [("-",) + ("",) * 10], 2.0, 5.2, 6.0)
        if i == 0:
            g.text((X0, yy - 8), "ตารางโค้งดิ่ง (Vertical curves)", 3.4, "left",
                   "text", True)
            D.table(g, X0, yy - 11, VCURVE_COLS, vrows[:20] or
                    [("-",) + ("",) * 9], 2.0, 5.2, 6.0)
            g.text((X0, Y0 + 3), "Δ มุมเบี่ยง · R รัศมี · T ระยะสัมผัส · L ความยาวโค้ง · "
                   "E ระยะภายนอก · PC จุดเริ่มโค้ง · PT จุดสิ้นโค้ง · PI จุดตัดแนวสัมผัส · "
                   "A = g2 − g1 · K = L / |A|", 2.0)
    return out


# ---------------------------------------------------------------------------
# PP — plan and profile
# ---------------------------------------------------------------------------

PLAN_BOX = (X0, 172.0, X1, Y1)
PROF_BOX = (X0 + 32, 80.0, X1 - 2, 166.0)
BANDS = [("ระดับดินเดิม", "zg"), ("ระดับออกแบบ", "zd"), ("ความสูงขุด", "cut"),
         ("ความสูงถม", "fill"), ("แนวราบ", "hz"), ("แนวดิ่ง", "vt")]
BAND_H = 9.0
BAND_TOP = 76.0


def chunks_of(an, hscale):
    usable = (PROF_BOX[2] - PROF_BOX[0]) * hscale / 1000.0
    step = max(20.0, math.floor(usable / 20.0) * 20.0)
    out, s = [], 0.0
    while s < an.length - 1e-6:
        out.append((s, min(an.length, s + step)))
        s += step
    if len(out) > 1 and out[-1][1] - out[-1][0] < step * 0.15:
        a, _b = out[-2]
        out[-2:] = [(a, an.length)]
    return out


def pp_plan(sh, an, s0, s1, shots, chunks, idx):
    bx = PLAN_BOX
    st = an.settings
    part = [A.point_at(an.axis, s) for s in _range(s0, s1, 5.0)]
    a, b = part[0], part[-1]
    ang = math.atan2(b.y - a.y, b.x - a.x)
    cen = ((a.x + b.x) / 2, (a.y + b.y) / 2)
    rp = [_rot((p.x, p.y), cen, ang) for p in part]
    corridor = st.half_width + 10.0
    xs = [p[0] for p in rp]
    ys = [p[1] for p in rp]
    w = (max(xs) - min(xs)) + 20
    h = (max(ys) - min(ys)) + 2 * corridor
    scale = next((sc for sc in (500, 1000, 1500, 2000, 2500, 3000, 5000)
                  if w * 1000 / sc <= bx[2] - bx[0] - 8 and
                  h * 1000 / sc <= bx[3] - bx[1] - 8), 5000)
    k = 1000.0 / scale
    mx, my = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2

    def v(x, y):
        r = _rot((x, y), cen, ang)
        return (cx + (r[0] - mx) * k, cy + (r[1] - my) * k)
    inner = (bx[0] + 1, bx[1] + 1, bx[2] - 1, bx[3] - 1)
    sh.rect(*bx, "frame", 0.35)

    def seg(p, q, layer, wt, dash=False):
        c = clip(v(*p), v(*q), inner)
        if c:
            sh.line(c[0], c[1], layer, wt, dash)
    axis_part = [(p.x, p.y) for p in part]
    # contours from the survey surface
    relief = [pp[2] for pp in an.tin.points] or [0, 1]
    interval = 0.5 if max(relief) - min(relief) < 8 else \
        1.0 if max(relief) - min(relief) < 40 else 2.0
    for lvl, (p, q) in contours(an.tin, lambda c: _near(c, axis_part, corridor + 15),
                                interval):
        major = abs(lvl / (interval * 5) - round(lvl / (interval * 5))) < 1e-6
        seg(p, q, "grid", 0.25 if major else 0.1)
    # grid ticks every 50/100 m with coordinate labels on the box edge
    gstep = 50.0 if scale <= 1000 else 100.0
    lo = [min(pp[0] for pp in axis_part) - 200, min(pp[1] for pp in axis_part) - 200]
    hi = [max(pp[0] for pp in axis_part) + 200, max(pp[1] for pp in axis_part) + 200]
    e = math.ceil(lo[0] / gstep) * gstep
    while e <= hi[0]:
        c = clip(v(e, lo[1]), v(e, hi[1]), inner)
        if c:
            sh.line(c[0], c[1], "hidden", 0.1, True)
            end = c[1] if c[1][1] > c[0][1] else c[0]
            sh.text((end[0] + 0.8, end[1] - 3), f"E={e:,.0f}", 1.6, "left", "hidden")
        e += gstep
    n = math.ceil(lo[1] / gstep) * gstep
    while n <= hi[1]:
        c = clip(v(lo[0], n), v(hi[0], n), inner)
        if c:
            sh.line(c[0], c[1], "hidden", 0.1, True)
            end = c[0] if c[0][0] < c[1][0] else c[1]
            sh.text((end[0] + 0.8, end[1] + 0.8), f"N={n:,.0f}", 1.6, "left", "hidden")
        n += gstep
    # road
    ed = edges_of(an, s0, s1)
    for key, layer, wt, dash in (("ep_l", "wall", 0.35, False), ("ep_r", "wall", 0.35, False),
                                 ("sh_l", "wall", 0.18, False), ("sh_r", "wall", 0.18, False),
                                 ("toe_l", "dim", 0.25, True), ("toe_r", "dim", 0.25, True)):
        line = ed[key]
        for p, q in zip(line, line[1:]):
            seg(p, q, layer, wt, dash)
    for p, q in zip(axis_part, axis_part[1:]):
        seg(p, q, "roof", 0.5)
    # stations
    s = math.ceil(s0 / 20.0) * 20.0
    while s <= s1 + 1e-6:
        p = A.point_at(an.axis, s)
        big = abs(s / 100.0 - round(s / 100.0)) < 1e-6
        tl = st.width / 2 + st.shoulder + (2.0 if big else 1.0)
        a_, b_ = v(*p.offset_point(-tl)), v(*p.offset_point(tl))
        sh.line(a_, b_, "dim", 0.35 if big else 0.18)
        ang_t = math.degrees(math.atan2(b_[1] - a_[1], b_[0] - a_[0]))
        while ang_t <= -45:                 # read upwards, never flipping
            ang_t += 180
        while ang_t > 135:
            ang_t -= 180
        lab = v(*p.offset_point(-tl - 1.5))
        sh.text(lab, sta(s, 0), 2.2 if big else 1.8, "left", "dim", big, ang_t)
        s += 20.0
    # curves
    for c in an.hcurves:
        if c.s_pt < s0 - 1e-6 or c.s_pc > s1 + 1e-6:
            continue
        q = v(*c.pi)
        if inner[0] < q[0] < inner[2] and inner[1] < q[1] < inner[3]:
            sh.circle(q, 0.9, "roof", 0.25)
            txt = f"PI-{c.number}"
            sh.text((q[0] + 1.5, q[1] + 1.2), txt, 2.2, "left", "roof", True)
            if c.radius > 0:
                sh.text((q[0] + 1.5, q[1] - 1.8), f"R={c.radius:,.0f} Δ={A.format_dms(c.delta)}",
                        1.7, "left", "roof")
        for s_, t in ((c.s_pc, "PC"), (c.s_pt, "PT")):
            if c.radius > 0 and s0 <= s_ <= s1:
                p = A.point_at(an.axis, s_)
                a_ = v(*p.offset_point(-st.width / 2 - 3))
                b_ = v(*p.offset_point(st.width / 2 + 3))
                sh.line(a_, b_, "roof", 0.25)
                sh.text((b_[0] + 0.5, b_[1] + 0.5), t, 1.8, "left", "roof")
    for bm in bench_marks(shots):
        q = v(bm.e, bm.n)
        if inner[0] < q[0] < inner[2] and inner[1] < q[1] < inner[3]:
            sh.poly([(q[0], q[1] + 2.0), (q[0] - 1.7, q[1] - 1.0),
                     (q[0] + 1.7, q[1] - 1.0)], "grid", 0.35)
            sh.text((q[0] + 2.2, q[1] - 0.6), f"{bm.name} ±{bm.z:.3f}", 1.8, "left", "grid")
    # north arrow turned with the plan
    na = (bx[0] + 10, bx[3] - 12)
    r = 5.0
    north = math.pi / 2 - ang
    tip = (na[0] + r * math.cos(north), na[1] + r * math.sin(north))
    left = (na[0] + r * 0.45 * math.cos(north + 2.5), na[1] + r * 0.45 * math.sin(north + 2.5))
    right = (na[0] + r * 0.45 * math.cos(north - 2.5), na[1] + r * 0.45 * math.sin(north - 2.5))
    sh.circle(na, r, "text", 0.25)
    sh.fill([tip, left, na], "text", 0.0)
    sh.poly([tip, right, na], "text", 0.25)
    sh.text((tip[0] + 1.0 * math.cos(north), tip[1] + 1.5 * math.sin(north)), "N",
            2.6, "center", "text", True)
    # key plan in the corner
    key_plan(sh, an, (bx[2] - 52, bx[3] - 34, bx[2] - 1, bx[3] - 1), chunks, idx,
             labels=False)
    sh.text((bx[2] - 26, bx[3] - 37), "ผังสังเขป", 1.8, "center")
    # caption
    sh.text((bx[0] + 4, bx[1] + 3), f"แปลน  STA {sta(s0, 0)} – {sta(s1, 0)}   มาตราส่วน 1:{scale}",
            2.8, "left", "text", True)
    return scale


def _range(a, b, step):
    out, s = [], a
    while s < b - 1e-9:
        out.append(s)
        s += step
    out.append(b)
    return out


V_SCALES = (50, 100, 200, 250, 500, 1000)


def need_vscale(an, s0, s1):
    """The largest vertical scale whose profile of s0–s1 fits the box."""
    zs = [p.z for p in an.profile if s0 - 1e-6 <= p.s <= s1 + 1e-6 and p.z is not None]
    zs += [z for s, z in an.grade if s0 - 1e-6 <= s <= s1 + 1e-6]
    zs = zs or [0.0, 1.0]
    height = PROF_BOX[3] - PROF_BOX[1] - 6
    return next((v for v in V_SCALES if (max(zs) - min(zs) + 2) * 1000 / v <= height),
                V_SCALES[-1])


def pp_profile(sh, an, s0, s1, hscale, vscale=None):
    bx = PROF_BOX
    k = 1000.0 / hscale
    gz = [(p.s, p.z) for p in an.profile if s0 - 1e-6 <= p.s <= s1 + 1e-6 and p.z is not None]
    dz = [(s, z) for s, z in an.grade if s0 - 1e-6 <= s <= s1 + 1e-6]
    zs = [z for _s, z in gz + dz] or [0.0, 1.0]
    zmin, zmax = min(zs), max(zs)
    vscale = vscale or need_vscale(an, s0, s1)
    kv = 1000.0 / vscale
    zstep = next(s_ for s_ in (0.5, 1, 2, 5, 10, 20) if (zmax - zmin + 2) / s_ <= 12)
    zb = math.floor(zmin / zstep) * zstep - zstep

    def P_(s, z):
        return (bx[0] + (s - s0) * k, bx[1] + 3 + (z - zb) * kv)
    right = bx[0] + (s1 - s0) * k
    sh.rect(bx[0], bx[1], right, bx[3], "frame", 0.35)
    z = zb
    while P_(s0, z)[1] < bx[3] - 0.5:
        p = P_(s0, z)
        sh.line(p, (right, p[1]), "hidden", 0.1)
        sh.text((p[0] - 1.2, p[1] - 0.8), f"{z:,.1f}" if zstep < 1 else f"{z:,.0f}",
                1.8, "right", "dim")
        z += zstep
    s = math.ceil(s0 / 20.0) * 20.0
    while s <= s1 + 1e-6:
        x = P_(s, zb)[0]
        sh.line((x, bx[1]), (x, bx[3]), "hidden", 0.1)
        s += 20.0
    for a, b in zip(gz, gz[1:]):
        sh.line(P_(*a), P_(*b), "grid", 0.35)
    for a, b in zip(dz, dz[1:]):
        sh.line(P_(*a), P_(*b), "roof", 0.5)
    # PVIs and vertical curves
    lab_y = bx[3] - 4
    for c in an.curves:
        if not s0 <= c.s <= s1:
            continue
        p = P_(c.s, c.z)
        sh.circle(p, 0.8, "roof", 0.25)
        for s_ in (c.bvc, c.evc):
            if s0 <= s_ <= s1:
                q = P_(s_, c.z_at(s_))
                sh.line((q[0], q[1] - 2), (q[0], q[1] + 6), "roof", 0.18)
        a = c.g2 - c.g1
        kk = c.length / abs(a) if abs(a) > 1e-9 else 0.0
        kind = "โค้งหงาย" if a > 0 else "โค้งคว่ำ"
        lines = [kind, f"PVI {sta(c.s)}", f"ระดับ {c.z:,.3f}", f"L = {c.length:,.0f} ม.",
                 f"A = {a:+.2f}%  K = {kk:,.1f}"]
        tx = min(max(p[0] - 14, bx[0] + 1), right - 30)
        ty = lab_y
        sh.rect(tx, ty - len(lines) * 3.0 - 0.5, tx + 29, ty + 2.5, "roof", 0.18)
        for i, t in enumerate(lines):
            sh.text((tx + 1, ty - i * 3.0), t, 1.8, "left", "roof", i == 0)
        sh.line((p[0], p[1] + 1), (p[0], ty - len(lines) * 3.0 - 0.5), "roof", 0.1, True)
        lab_y = bx[3] - 4 if lab_y < bx[3] - 10 else bx[3] - 22
    # grades
    pv = [(s_, z_) for s_, z_, *_ in an.pvis]
    for (sa, za), (sb, zb_) in zip(pv, pv[1:]):
        lo, hi = max(sa, s0), min(sb, s1)
        if hi - lo < 30:
            continue
        g = (zb_ - za) / (sb - sa) * 100 if sb > sa else 0
        mid = (lo + hi) / 2
        z_mid = za + (zb_ - za) * (mid - sa) / (sb - sa)
        q = P_(mid, z_mid)
        sh.text((q[0], q[1] + 2.5), f"{g:+.2f}%", 2.2, "center", "roof", True)
    sh.text((bx[0], bx[3] + 1.5), f"รูปตัดตามยาว  มาตราส่วน ราบ 1:{hscale}  ดิ่ง 1:{vscale}",
            2.8, "left", "text", True)
    sh.text((right - 1, bx[3] + 1.5), "— ระดับดินเดิม   — ระดับออกแบบ", 2.0, "right")
    sh.text((bx[0] - 2, bx[3] - 3), "ระดับ (ม.รทก.)", 1.8, "right", "dim")
    return vscale


def pp_bands(sh, an, s0, s1, hscale):
    k = 1000.0 / hscale
    bx0 = PROF_BOX[0]
    right = bx0 + (s1 - s0) * k
    top = BAND_TOP
    for i, (name, _key) in enumerate(BANDS):
        y = top - i * BAND_H
        sh.line((X0, y), (right, y), "text", 0.25)
        sh.text((X0 + 1, y - BAND_H / 2 - 0.8), name, 2.1, "left", "text", True)
    bottom = top - len(BANDS) * BAND_H
    sh.line((X0, bottom), (right, bottom), "text", 0.35)
    sh.line((X0, top), (X0, bottom), "text", 0.25)
    sh.line((bx0, top), (bx0, bottom), "text", 0.25)
    sh.line((right, top), (right, bottom), "text", 0.25)
    zg = {round(p.s, 2): p.z for p in an.profile}
    s = math.ceil(s0 / 20.0) * 20.0
    while s <= s1 + 1e-6:
        x = bx0 + (s - s0) * k
        z_g = zg.get(round(s, 2))
        if z_g is None:
            z_g = an.tin.z_at(*_xy(an, s))
        z_d = P.grade_at(an.grade, s) if an.grade else None
        vals = [f"{z_g:,.3f}" if z_g is not None else "-",
                f"{z_d:,.3f}" if z_d is not None else "-",
                f"{max(0, z_g - z_d):.2f}" if z_g is not None and z_d is not None else "",
                f"{max(0, z_d - z_g):.2f}" if z_g is not None and z_d is not None else ""]
        for i, t in enumerate(vals):
            y = top - i * BAND_H - BAND_H + 0.8
            if t and t != "0.00":
                sh.text((x + 0.7, y), t, 1.7, "left", "dim", False, 90)
        sh.line((x, bottom), (x, bottom - 1.5), "dim", 0.18)
        sh.text((x, bottom - 4.5), sta(s, 0), 1.7, "center", "dim")
        s += 20.0
    # horizontal alignment diagram
    yh = top - 4 * BAND_H - BAND_H / 2
    sh.line((bx0, yh), (right, yh), "roof", 0.25)
    for c in an.hcurves:
        if c.s_pt < s0 or c.s_pc > s1:
            continue
        a = bx0 + (max(c.s_pc, s0) - s0) * k
        b = bx0 + (min(c.s_pt, s1) - s0) * k
        up = 2.8 if c.delta > 0 else -2.8
        if c.radius <= 0 or b - a < 0.6:
            sh.line((a, yh - 2.5), (a, yh + 2.5), "roof", 0.35)
            sh.text((a + 0.6, yh + (1 if up > 0 else -3.2)), f"PI-{c.number}", 1.6,
                    "left", "roof")
            continue
        sh.poly([(a, yh), (a, yh + up), (b, yh + up), (b, yh)], "roof", 0.35, False)
        sh.text(((a + b) / 2, yh + up + (0.6 if up > 0 else -2.6)),
                f"{c.number}: R={c.radius:,.0f}", 1.6, "center", "roof")
    # vertical alignment diagram
    yv = top - 5 * BAND_H - BAND_H / 2
    sh.line((bx0, yv), (right, yv), "roof", 0.25)
    for c in an.curves:
        if c.evc < s0 or c.bvc > s1:
            continue
        a = bx0 + (max(c.bvc, s0) - s0) * k
        b = bx0 + (min(c.evc, s1) - s0) * k
        up = -2.6 if c.g2 > c.g1 else 2.6
        sh.poly([(a, yv), ((a + b) / 2, yv + up), (b, yv)], "roof", 0.35, False)
        sh.text(((a + b) / 2, yv + (up + 0.6 if up > 0 else up - 2.6)),
                f"L={c.length:,.0f}", 1.6, "center", "roof")


def _xy(an, s):
    p = A.point_at(an.axis, s)
    return p.x, p.y


def pp_sheets(an, info, chunks, shots, hscale):
    out = []
    # one vertical scale for the whole set, so the sheets read alike
    vs = max(need_vscale(an, a, b) for a, b in chunks)
    for i, (s0, s1) in enumerate(chunks, 1):
        sh = D.Sheet(f"PP-{i:02d}", f"แปลนและรูปตัดตามยาว STA {sta(s0, 0)} – {sta(s1, 0)}",
                     f"1:{hscale}", "PP")
        pscale = pp_plan(sh, an, s0, s1, shots, chunks, i)
        vscale = pp_profile(sh, an, s0, s1, hscale, vs)
        pp_bands(sh, an, s0, s1, hscale)
        sh.scale = f"1:{pscale}  V 1:{vscale}"
        out.append(sh)
    return out


# ---------------------------------------------------------------------------
# ST — cross sections, VT — earthworks table
# ---------------------------------------------------------------------------

def _rows_by_s(an):
    return {round(r.s, 3): r for r in an.rows}


def section_scale(an, cell_w, cell_h):
    span = max((abs(o) for sec in an.sections for o, _z in (sec.ground or [])), default=15.0)
    zr = max(((max(z for _o, z in (sec.ground + (sec.design or []))) -
               min(z for _o, z in (sec.ground + (sec.design or []))))
              for sec in an.sections if sec.ground), default=5.0)
    for sc in (100, 200, 250, 500, 1000):
        if 2 * span * 1000 / sc <= cell_w and (zr + 2) * 1000 / sc <= cell_h:
            return sc, span
    return 1000, span


def draw_section(sh, sec, row, box, sc, span):
    x0, y0, x1, y1 = box
    k = 1000.0 / sc
    pts = sec.ground + (sec.design or [])
    zs = [z for _o, z in pts]
    zmin, zmax = min(zs), max(zs)
    zc = (zmin + zmax) / 2
    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2

    def P_(o, z):
        return (cx + o * k, cy + (z - zc) * k)
    sh.rect(x0, y0, x1, y1, "text", 0.18)
    # grid
    zstep = 1.0 if (zmax - zmin) * k < 60 else 2.0
    z = math.floor((zc - (y1 - y0) / 2 / k) / zstep) * zstep
    while z <= zc + (y1 - y0) / 2 / k:
        y = P_(0, z)[1]
        if y0 < y < y1:
            sh.line((x0, y), (x1, y), "hidden", 0.08)
            sh.text((x0 - 0.6, y - 0.6), f"{z:,.0f}", 1.3, "right", "dim")
        z += zstep
    o = -math.floor(span / 2) * 2
    while o <= span:
        x = P_(o, 0)[0]
        if x0 < x < x1:
            sh.line((x, y0), (x, y1), "hidden", 0.08)
            sh.text((x, y0 - 2.4), f"{o:g}", 1.3, "center", "dim")
        o += 2.0 if span <= 16 else 5.0
    # cut / fill shading between ground and design
    if sec.design:
        lo = max(sec.ground[0][0], sec.design[0][0])
        hi = min(sec.ground[-1][0], sec.design[-1][0])
        n = max(2, int((hi - lo) / 0.25))
        prev = None
        for i in range(n + 1):
            o = lo + (hi - lo) * i / n
            g = _z_on(sec.ground, o)
            d = _z_on(sec.design, o)
            if prev and g is not None and d is not None and prev[1] is not None and \
                    prev[2] is not None:
                po, pg, pd = prev
                if (g - d) * (pg - pd) >= 0 and abs(g - d) + abs(pg - pd) > 0.01:
                    cut = g > d or pg > pd
                    sh.fill([P_(po, pg), P_(o, g), P_(o, d), P_(po, pd)], "hatch",
                            0.82 if cut else 0.62, CUT_RGB if cut else FILL_RGB)
            prev = (o, g, d)
        sh.poly([P_(*p) for p in sec.design], "roof", 0.45, False)
    sh.poly([P_(*p) for p in sec.ground], "grid", 0.3, False)
    sh.line(P_(0, zc - (y1 - y0) / 2 / k), P_(0, zc + (y1 - y0) / 2 / k), "dim", 0.13, True)
    top = P_(0, zc + (y1 - y0) / 2 / k)
    sh.text((top[0], y1 - 3), "CL", 1.6, "center", "dim")
    # info
    sh.text(((x0 + x1) / 2, y1 + 2.0), f"STA {sta(sec.s)}", 2.6, "center", "text", True)
    lines = [f"CT {sec.z_ground:,.3f}" if sec.z_ground is not None else "CT -",
             f"CR {sec.z_design:,.3f}" if sec.z_design is not None else "CR -"]
    sh.text((x0 + 1, y0 - 5.5), "   ".join(lines), 1.8, "left", "text", True)
    info = [("พื้นที่ขุด", f"{sec.cut:,.2f} ตร.ม."), ("พื้นที่ถม", f"{sec.fill:,.2f} ตร.ม.")]
    if row is not None:
        info += [("ปริมาตรขุด", f"{row.cut_volume:,.2f}"), ("ปริมาตรถม", f"{row.fill_volume:,.2f}"),
                 ("ขุดสะสม", f"{row.cut_total:,.2f}"), ("ถมสะสม", f"{row.fill_total:,.2f}"),
                 ("สุทธิ", f"{row.mass:,.2f}")]
    for i, (a, b) in enumerate(info):
        y = y0 - 9 - i * 2.6
        sh.text((x0 + 1, y), a, 1.6)
        sh.text((x1 - 1, y), b, 1.6, "right")


def _z_on(line, o):
    for (a, za), (b, zb) in zip(line, line[1:]):
        if a - 1e-9 <= o <= b + 1e-9:
            if b - a < 1e-12:
                return za
            return za + (zb - za) * (o - a) / (b - a)
    return None


def st_sheets(an, info):
    cols, rows_ = 4, 3
    cw = (X1 - X0) / cols
    ch = (Y1 - Y0) / rows_
    plot_w, plot_h = cw - 14, ch - 30
    sc, span = section_scale(an, plot_w, plot_h)
    by = _rows_by_s(an)
    secs = [s for s in an.sections if s.ground]
    out = []
    per = cols * rows_
    for i in range(0, len(secs), per):
        sh = D.Sheet(f"ST-{len(out) + 1:02d}", f"รูปตัดขวาง STA {sta(secs[i].s, 0)} – "
                     f"{sta(secs[min(i + per, len(secs)) - 1].s, 0)}", f"1:{sc}", "ST")
        for j, sec in enumerate(secs[i:i + per]):
            c, r = j % cols, j // cols
            bx0 = X0 + c * cw + 8
            by1 = Y1 - r * ch - 6
            box = (bx0, by1 - plot_h, bx0 + plot_w, by1)
            draw_section(sh, sec, by.get(round(sec.s, 3)), box, sc, span)
        sh.text((X0, Y0 - 4.5 + 1), f"มาตราส่วน 1:{sc} (ราบ = ดิ่ง) · พื้นที่ ตร.ม. · ปริมาตร ลบ.ม. · "
                "CT ระดับดินเดิม · CR ระดับออกแบบ · สีแดง = ขุด  สีเขียว = ถม", 1.8, "left", "title")
        out.append(sh)
    return out


VT_COLS = [("STA", 24, "center"), ("ระดับดิน", 22, "right"), ("ระดับออกแบบ", 24, "right"),
           ("พื้นที่ขุด", 24, "right"), ("พื้นที่ถม", 24, "right"),
           ("ปริมาตรขุด", 28, "right"), ("ปริมาตรถม", 28, "right"),
           ("ขุดสะสม", 30, "right"), ("ถมสะสม", 30, "right"), ("สุทธิสะสม", 30, "right")]


def vt_sheets(an, info):
    rows = [(sta(r.s), f"{r.z_ground:,.3f}" if r.z_ground is not None else "-",
             f"{r.z_design:,.3f}" if r.z_design is not None else "-",
             f"{r.cut_area:,.2f}", f"{r.fill_area:,.2f}", f"{r.cut_volume:,.2f}",
             f"{r.fill_volume:,.2f}", f"{r.cut_total:,.2f}", f"{r.fill_total:,.2f}",
             f"{r.mass:,.2f}") for r in an.rows]
    out = []
    per = 42
    for i in range(0, max(len(rows), 1), per):
        sh = D.Sheet(f"VT-{len(out) + 1:02d}", "ตารางปริมาณงานดินขุด-ถม", "-", "VT")
        sh.text((X0, Y1 - 3), "ตารางปริมาณงานดินขุด-ถม (ลบ.ม.)  วิธี "
                f"{'Prismoidal' if an.settings.method == 'prismoidal' else 'Average end area'}",
                3.2, "left", "text", True)
        y = D.table(sh, X0, Y1 - 6, VT_COLS, rows[i:i + per] or [("-",) + ("",) * 9],
                    1.9, 5.6, 6.0)
        out.append(sh)
    last = out[-1]
    tot = [("รวม", "", "", "", "", f"{sum(r.cut_volume for r in an.rows):,.2f}",
            f"{sum(r.fill_volume for r in an.rows):,.2f}", f"{an.cut_total:,.2f}",
            f"{an.fill_total:,.2f}", f"{an.cut_total - an.fill_total:,.2f}")]
    y = D.table(last, X0, y - 2, VT_COLS, tot, 2.0, 6.0, 6.0)
    q = an.layer_quantities() if callable(an.layer_quantities) else an.layer_quantities
    if q:
        y0 = max(y - 10, Y0 + 40)
        last.text((X0, y0), "ปริมาณงานโครงสร้างทาง", 3.0, "left", "text", True)
        D.table(last, X0, y0 - 3, [("ชั้นทาง", 70, "left"), ("หนา (ม.)", 24, "right"),
                                   ("กว้าง (ม.)", 24, "right"), ("ปริมาตร ลบ.ม.", 34, "right"),
                                   ("พื้นที่ ตร.ม.", 34, "right")],
                [(n, f"{t:.3f}", f"{w:.2f}", f"{v:,.2f}", f"{a:,.2f}") for n, t, w, v, a in q],
                2.0, 5.4, 6.0)
    return out


# ---------------------------------------------------------------------------
# the set
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# แผนที่ตั้งโครงการ — the site on a satellite picture
# ---------------------------------------------------------------------------

#: The satellite picture and the vicinity map on the location sheet.
SITE_BOX = (X0, Y0 + 16.0, X1 - 100.0, Y1 - 9.0)
VICINITY_BOX = (X1 - 95.0, Y1 - 95.0, X1, Y1 - 9.0)
SAT_COLORS = {"sat": (255, 214, 0), "halo": (20, 20, 20), "sattext": (255, 255, 255),
              "satpi": (0, 215, 255), "satred": (230, 30, 30)}


def axis_lat_lon(an, zone=47, datum="WGS84") -> list:
    """(station, lat, lon) of every vertex of the axis."""
    from core import wanic_road as R
    pts = []
    run = 0.0
    for k, p in enumerate(an.axis):
        if k:
            run += math.dist(an.axis[k - 1], p)
        pts.append((run, *R.utm_to_wgs84(p[0], p[1], zone, datum)))
    return pts


def site_views(an, info=None):
    """The satellite windows (:class:`core.wanic_sitemap.View`) of the
    location sheet: the site, and the vicinity three zooms further out."""
    from core import wanic_sitemap as M
    info = info or {}
    ll = [(la, lo) for _s, la, lo in axis_lat_lon(an, int(info.get("zone") or 47),
                                                    info.get("datum") or "WGS84")]
    bw, bh = SITE_BOX[2] - SITE_BOX[0], SITE_BOX[3] - SITE_BOX[1]
    vw, vh = VICINITY_BOX[2] - VICINITY_BOX[0], VICINITY_BOX[3] - VICINITY_BOX[1]
    return (M.fit_view(ll, bw, bh, max_px=2400),
            M.fit_view(ll, vw, vh, max_px=700, zoom_out=3))


def _label(sh, p, text, h=2.0, align="left"):
    """White text on a dark plate, readable over a photograph."""
    w = len(text) * h * 0.56 + 1.2
    x = p[0] - (w / 2 if align == "center" else w - 0.6 if align == "right" else 0.6)
    sh.fill([(x, p[1] - 0.8), (x + w, p[1] - 0.8), (x + w, p[1] + h + 0.2),
             (x, p[1] + h + 0.2)], "halo", 0.1, (25, 25, 25))
    sh.text(p, text, h, align, "sattext", True)


def _site_overlay(sh, an, view, box, zone, datum):
    """The alignment, its stations, PIs, start and end over the picture."""
    from core import wanic_road as R
    bx, by = box[0], box[1]

    def v(e, n):
        la, lo = R.utm_to_wgs84(e, n, zone, datum)
        x, y = view.to_box(la, lo)
        return (bx + x, by + y)
    line = [v(*p) for p in an.axis]
    sh.poly(line, "halo", 1.5, closed=False)
    sh.poly(line, "sat", 0.75, closed=False)
    per_100 = 100.0 / view.ground_per_mm()             # paper mm of 100 m
    step = 100.0 if per_100 >= 9 else 200.0 if per_100 >= 4.5 else 500.0 \
        if per_100 >= 1.8 else 1000.0
    s = 0.0
    while s <= an.length + 1e-6:
        st = A.point_at(an.axis, s)
        a = v(st.x, st.y)
        b = v(*st.offset_point(10.0))
        d = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
        nx, ny = (b[0] - a[0]) / d, (b[1] - a[1]) / d
        sh.line((a[0] - nx * 1.6, a[1] - ny * 1.6), (a[0] + nx * 1.6, a[1] + ny * 1.6),
                "sat", 0.35)
        _label(sh, (a[0] + nx * 3.0, a[1] + ny * 3.0 - 1.0), sta(s, 0), 1.8,
               "left" if nx >= 0 else "right")
        s += step
    for c in an.hcurves:
        q = v(*c.pi)
        sh.fill([(q[0], q[1] + 2.4), (q[0] - 2.0, q[1] - 1.2), (q[0] + 2.0, q[1] - 1.2)],
                "satpi", 0.5, SAT_COLORS["satpi"])
        sh.poly([(q[0], q[1] + 2.4), (q[0] - 2.0, q[1] - 1.2), (q[0] + 2.0, q[1] - 1.2)],
                "halo", 0.2)
        _label(sh, (q[0] - 3.0, q[1] + 0.2), f"PI-{c.number}", 2.0, "right")
    for s, word in ((0.0, "เริ่มต้น"), (an.length, "สิ้นสุด")):
        st = A.point_at(an.axis, s)
        q = v(st.x, st.y)
        b = v(*st.offset_point(10.0))
        d = math.hypot(b[0] - q[0], b[1] - q[1]) or 1.0
        nx, ny = (b[0] - q[0]) / d, (b[1] - q[1]) / d
        sh.circle(q, 1.4, "satred", 0.6)
        # the station labels are on the right: these go on the left
        _label(sh, (q[0] - nx * 4.0, q[1] - ny * 4.0 - 1.1), f"{word} {sta(s)}", 2.3,
               "right" if nx >= 0 else "left")


def location_sheet(an, info, site) -> "D.Sheet":
    """แผนที่ตั้งโครงการ: the site on a satellite picture (downloaded, or
    one saved from Google Earth Pro), a vicinity map, and the ตำบล
    อำเภอ จังหวัด and coordinates of the job.

    ``site``: {"mode": "tiles" | "file" | "none", "main": View,
    "image": bytes, "size": (w, h) of a file's picture, "vicinity": View,
    "vicinity_image": bytes, "credit": text}."""
    from core import wanic_road as R
    from core import wanic_sitemap as M
    zone = int(info.get("zone") or 47)
    datum = info.get("datum") or "WGS84"
    sh = D.Sheet("G-01", "แผนที่ตั้งโครงการ", "-", "G")
    sh.text((X0, Y1 - 5), "แผนที่ตั้งโครงการ (ภาพถ่ายดาวเทียม)", 4.0, "left", "text", True)
    bx0, by0, bx1, by1 = SITE_BOX
    mode = site.get("mode", "tiles")
    main = site.get("main")
    if mode == "file" and site.get("image"):
        iw, ih = site.get("size") or (4, 3)
        k = min((bx1 - bx0) / iw, (by1 - by0) / ih)
        w, h = iw * k, ih * k
        x0, y0 = bx0 + (bx1 - bx0 - w) / 2, by0 + (by1 - by0 - h) / 2
        sh.image((x0, y0, x0 + w, y0 + h), site["image"])
        sh.text((bx0, by0 - 4.5), "ภาพจาก Google Earth Pro (บันทึกภาพโดยผู้ออกแบบ) "
                "— ลิขสิทธิ์ภาพตามที่ปรากฏบนภาพ", 2.0)
    else:
        if site.get("image"):
            sh.image(SITE_BOX, site["image"])
        else:
            sh.fill([(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)], "hatch", 0.9,
                    (226, 230, 222))
            sh.text(((bx0 + bx1) / 2, (by0 + by1) / 2 + 4), "ยังไม่มีภาพถ่ายดาวเทียม", 3.0,
                    "center", "text", True)
            sh.text(((bx0 + bx1) / 2, (by0 + by1) / 2 - 2),
                    "ต่ออินเทอร์เน็ตแล้วส่งออกใหม่ หรือแนบภาพที่บันทึกจาก Google Earth Pro", 2.2,
                    "center")
        if main is not None:
            _site_overlay(sh, an, main, SITE_BOX, zone, datum)
            # scale bar and north (Web Mercator: north is up)
            g = main.ground_per_mm()
            bar = M.nice_bar(g, 50.0)
            L = bar / g
            x, y = bx0 + 5, by0 + 5
            sh.fill([(x - 2, y - 2), (x + L + 14, y - 2), (x + L + 14, y + 6.5),
                     (x - 2, y + 6.5)], "halo", 0.1, (255, 255, 255))
            for i in range(4):
                xa, xb = x + L * i / 4, x + L * (i + 1) / 4
                sh.fill([(xa, y), (xb, y), (xb, y + 1.4), (xa, y + 1.4)], "text",
                        0.0 if i % 2 == 0 else 1.0, (0, 0, 0) if i % 2 == 0 else (255, 255, 255))
            sh.rect(x, y, x + L, y + 1.4, "text", 0.2)
            sh.text((x, y + 2.4), "0", 1.8, "center")
            sh.text((x + L, y + 2.4), f"{bar:,.0f} ม.", 1.8, "center")
            sh.fill([(bx1 - 15, by1 - 17), (bx1 - 2, by1 - 17), (bx1 - 2, by1 - 2),
                     (bx1 - 15, by1 - 2)], "halo", 0.1, (255, 255, 255))
            D.north(sh, (bx1 - 8.5, by1 - 11.5), 4)
        sh.text((bx0, by0 - 4.5), site.get("credit") or M.SOURCES["esri"][2], 2.0)
    sh.rect(bx0, by0, bx1, by1, "text", 0.35)
    # vicinity
    vx0, vy0, vx1, vy1 = VICINITY_BOX
    sh.text((vx0, vy1 + 2.5), "แผนที่บริเวณใกล้เคียง", 3.0, "left", "text", True)
    vic = site.get("vicinity")
    if vic is not None and site.get("vicinity_image"):
        sh.image(VICINITY_BOX, site["vicinity_image"])

        def vv(e, n):
            la, lo = R.utm_to_wgs84(e, n, zone, datum)
            x, y = vic.to_box(la, lo)
            return (vx0 + x, vy0 + y)
        sh.poly([vv(*p) for p in an.axis], "satred", 0.9, closed=False)
        if main is not None:
            corners = [M.lat_lon(main.x0 + dx, main.y0 + dy, main.z)
                       for dx, dy in ((0, 0), (main.w_px, 0), (main.w_px, main.h_px),
                                      (0, main.h_px))]
            box = []
            for la, lo in corners:
                x, y = vic.to_box(la, lo)
                box.append((min(max(vx0 + x, vx0), vx1), min(max(vy0 + y, vy0), vy1)))
            sh.poly(box, "sat", 0.5)
        sh.rect(vx0, vy0, vx1, vy1, "text", 0.35)
    else:
        key_plan(sh, an, VICINITY_BOX, None, None, (), labels=False)
    # the place and the coordinates
    y = vy0 - 8
    sh.text((vx0, y), "ที่ตั้งโครงการ", 3.4, "left", "text", True)
    place = info.get("location") or ""
    parts = M.place_parts(place)
    if any(n for _l, n in parts):
        for label, name in parts:
            y -= 6.5
            sh.text((vx0 + 2, y), label, 3.0)
            sh.text((vx0 + 22, y), name or "-", 3.4, "left", "text", True)
    else:
        y -= 6.5
        sh.text((vx0 + 2, y), place or "ยังไม่ทราบ (กด «📍 จังหวัด อำเภอ ตำบล» ในแผงออกแบบถนน)",
                2.6 if place else 2.0, "left", "text", bool(place))
    y -= 9
    if info.get("project"):
        sh.text((vx0, y), "โครงการ", 2.4, "left", "text", True)
        for ln in D._wrap(str(info["project"]), 40)[:2]:
            y -= 4.5
            sh.text((vx0 + 2, y), ln, 2.4)
        y -= 7
    rows = []
    for s, word in ((0.0, "เริ่มต้น"), (an.length, "สิ้นสุด")):
        st = A.point_at(an.axis, s)
        la, lo = R.utm_to_wgs84(st.x, st.y, zone, datum)
        rows += [(f"{word} {sta(s)}", f"N {st.y:,.3f}  E {st.x:,.3f}"),
                 ("", f"{la:.6f}°N  {lo:.6f}°E")]
    y = D.table(sh, vx0, y, [("ตำแหน่ง", 28, "left"), ("พิกัด", 67, "left")],
                rows, 2.0, 4.6, 5.0)
    y -= 6
    sh.text((vx0, y), f"ความยาวทาง {an.length:,.3f} ม.", 2.4, "left", "text", True)
    y -= 5
    sh.text((vx0, y), f"ระบบพิกัด UTM {datum} โซน {zone}N", 2.2)
    # legend under the picture
    lx, ly = bx0 + 2, Y0 + 3
    sh.line((lx, ly + 1), (lx + 12, ly + 1), "halo", 1.4)
    sh.line((lx, ly + 1), (lx + 12, ly + 1), "sat", 0.7)
    sh.text((lx + 14, ly), "แนวศูนย์กลางทาง พร้อมสถานี", 2.2)
    lx += 62
    sh.fill([(lx + 4, ly + 2.6), (lx + 2.2, ly - 0.4), (lx + 5.8, ly - 0.4)], "satpi", 0.5,
            SAT_COLORS["satpi"])
    sh.text((lx + 8, ly), "จุดตัดแนวสัมผัส (PI)", 2.2)
    lx += 48
    sh.circle((lx + 4, ly + 1), 1.4, "satred", 0.6)
    sh.text((lx + 8, ly), "จุดเริ่มต้น / สิ้นสุดโครงการ", 2.2)
    return sh


def build_road_set(an, info=None, shots=None,
                   groups=("G", "PP", "ST", "VT"), site=None) -> list:
    """Every sheet of the road drawing set, numbered, with its title
    column.  ``an`` is :func:`core.wanic_road.analyse`'s result; with
    ``site`` (:func:`location_sheet`) the set opens with the site map."""
    info = dict(info or {})
    if an is None or len(an.axis) < 2:
        return []
    hscale = int(info.get("h_scale") or 1000)
    chunks = chunks_of(an, hscale)
    sheets = []
    if site is not None:
        sheets.append(location_sheet(an, info, site))
    if "G" in groups:
        sheets += g_sheets(an, info, chunks, shots)
    for i, s in enumerate([s for s in sheets if s.group == "G"], 1):
        s.code = f"G-{i:02d}"
    if "PP" in groups:
        sheets += pp_sheets(an, info, chunks, shots, hscale)
    if "ST" in groups and an.sections:
        sheets += st_sheets(an, info)
    if "VT" in groups and an.rows:
        sheets += vt_sheets(an, info)
    for i, s in enumerate(sheets, 1):
        s.number = i
    info.setdefault("project", "งานออกแบบถนน")
    for s in sheets:
        D.frame(s, info, len(sheets), ROLES)
        s.colors = dict(COLORS, **SAT_COLORS)
    return sheets
