# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""DR — งานระบายน้ำ (ทถ-5) and TS — ป้ายจราจร เครื่องหมายจราจร และ
อุปกรณ์อำนวยความปลอดภัย (ทถ-3), drawn from the road's own design.

The DRR standard drawings for local roads give the details and leave the
sizes, stations and lengths «ตามที่ผู้ออกแบบระบุ»; here they come from the
analysed road (:func:`core.wanic_road.analyse`):

* **DR-01 ท่อลอดเหลี่ยม/กลม — ท่อระบายน้ำ คสล. ชนิดกลม** (ทถ-5-101): the
  culverts of the road — found at the low points of the ground under the
  grade line (or as given) — each with its station, size, rows, cover and
  length in 1.00 m pipes; the pipe drawn across the embankment to scale;
  ทถ-5-101 tables 1–2 with the row used marked; the pipe's capacity
  (Manning, better than the standard which gives none);
* **DR-02 กำแพงปากท่อ และรางระบายน้ำ คสล.** (ทถ-5-103, ทถ-5-301/302): the
  headwall of the size used with its table row, the U-drain of the type
  chosen with the cover grating and its table row, the bill;
* **TS-01 แผนผังป้ายและเครื่องหมายจราจร**: the road as a straight line
  diagram with the project signs, kilometre posts, curve warning signs,
  guide posts at the spacing of ทถ-3-112 (or GUARD RAIL where ทถ-3-201 note
  5 asks: R < 150 m or fill over 6.00 m), and the lines on the pavement
  (ทถ-3-110: broken 3–9 m, solid on curves, no centre line at 5 m wide or
  less), with the quantities;
* **TS-02 แบบขยายการติดตั้ง**: sign post, kilometre post, guide post and
  guard rail, the line dimensions and the tables.

Pure Python (no Qt); sheets are :class:`core.wanic_drawings.Sheet`.
"""
from __future__ import annotations

import math

from core import wanic_drawings as D

X0, Y0, X1, Y1 = D.drawing_area()
MARK_RGB = (255, 244, 170)

# ---------------------------------------------------------------------------
# the standard's tables
# ---------------------------------------------------------------------------

#: ทถ-5-101 ตารางที่ 1: D (mm) → wall T, t, a, b, c (mm)
PIPE_T1 = {400: (60, 30, 23, 10, 27), 600: (75, 40, 28, 15, 32), 800: (95, 45, 38, 15, 42),
           1000: (110, 45, 43, 20, 47), 1200: (125, 50, 48, 25, 52), 1500: (150, 60, 57, 30, 63)}
#: ทถ-5-101 ตารางที่ 2: D → steel inner, outer (cm²/m), crushing load (N/m, 0.5 mm crack)
PIPE_T2 = {400: (1.5, None, 26000), 600: (1.5, None, 39000), 800: (4.0, None, 52000),
           1000: (4.2, 3.2, 65000), 1200: (5.1, 3.8, 78000), 1500: (7.5, 5.5, 97500)}
COVER_MIN, COVER_MAX = 0.30, 3.00          # ดินถมบนหลังท่อ ไม่น้อยกว่า 0.30 แต่ไม่เกิน 3.00 ม.
#: ทถ-5-103: D (cm) → T (cm), θ, single B, L, two rows B, L, three rows B, L (cm)
HEADWALL = {30: (5.0, 30, 160, 130, 215, 130, 270, 130), 40: (6.0, 30, 172, 152, 244, 152, 316, 152),
            50: (7.0, 30, 184, 174, 258, 174, 362, 174), 60: (7.5, 30, 195, 195, 300, 195, 405, 195),
            80: (9.5, 30, 219, 239, 358, 239, 497, 239), 100: (11.0, 30, 242, 282, 414, 282, 586, 282),
            120: (12.5, 30, 265, 325, 470, 325, 675, 325), 135: (14.0, 30, 283, 358, 513.5, 358, 744, 358),
            150: (15.0, 30, 300, 390, 555, 390, 810, 390)}
#: ทถ-5-301 รางระบายน้ำ คสล. ย่านชุมชน: type → W, H, T1, T2 (cm), steel A, B, C, D (Ø mm, @ cm)
UDRAIN = {"ก-30": (30, 30, 10, 12.5, (9, 20), (9, 20), (9, 15), (9, 15)),
          "ข-30": (30, 50, 10, 12.5, (9, 15), (9, 15), (9, 15), (9, 15)),
          "ค-30": (30, 70, 12, 12.5, (9, 10), (9, 10), (9, 15), (9, 15)),
          "ง-30": (30, 100, 15, 12.5, (12, 10), (12, 10), (9, 15), (9, 15)),
          "ก-50": (50, 30, 10, 15, (9, 20), (9, 20), (9, 10), (9, 10)),
          "ข-50": (50, 50, 10, 15, (9, 15), (9, 15), (9, 10), (9, 10)),
          "ค-50": (50, 70, 12, 15, (9, 10), (9, 10), (9, 10), (9, 10)),
          "ง-50": (50, 100, 15, 15, (12, 10), (12, 10), (9, 10), (9, 10))}
#: ทถ-3-112 ระยะห่างหลักนำโค้ง: R up to (m) → ในโค้ง ส, นอกโค้ง ส1, ส2, ส3 (m)
GUIDE_POST = ((75, 4, 7, 12, 24), (99, 6, 11, 18, 36), (149, 7, 13, 21, 42), (199, 8, 14, 24, 48),
              (299, 9, 16, 27, 54), (500, 10, 18, 30, 60), (1e9, 15, 27, 45, 60))
GUIDE_ROWS = ("น้อยกว่า 75", "75 - 99", "100 - 149", "150 - 199", "200 - 299", "300 - 500",
              "มากกว่า 500")
#: ทถ-3-201 ระยะห่างเสา GUARD RAIL: R from (m) → S (m)
RAIL_POST = ((50, 4.00), (25, 3.00), (15, 2.50), (0, 2.00))
RAIL_R, RAIL_FILL = 150.0, 6.00            # ทถ-3-201 หมายเหตุ 5
#: ทถ-3-110(1) ระยะมองเห็นต่ำสุดสำหรับการแซง: km/h → m
NO_PASS = ((50, 160), (60, 180), (70, 210), (80, 240), (90, 275), (100, 315))
LINE_W = 0.10                               # เส้นจราจรกว้าง 10 ซม.
BROKEN = {"rural": (3.0, 9.0), "urban": (1.0, 3.0)}
N_MANNING = 0.013


def guide_spacing(radius: float):
    for r, s, s1, s2, s3 in GUIDE_POST:
        if radius <= r:
            return s, s1, s2, s3
    return GUIDE_POST[-1][1:]


def guide_row(radius: float) -> int:
    for i, row in enumerate(GUIDE_POST):
        if radius <= row[0]:
            return i
    return len(GUIDE_POST) - 1


def rail_spacing(radius: float) -> float:
    for r, s in RAIL_POST:
        if radius >= r:
            return s
    return RAIL_POST[-1][1]


def no_pass_distance(speed: float) -> float:
    for v, d in NO_PASS:
        if speed <= v:
            return d
    return NO_PASS[-1][1]


def pipe_capacity(d_m: float, slope: float = 0.005, n: float = N_MANNING) -> tuple:
    """Manning, the pipe running full: (Q m³/s, V m/s)."""
    A = math.pi * d_m ** 2 / 4.0
    R = d_m / 4.0
    v = R ** (2.0 / 3.0) * math.sqrt(max(slope, 1e-6)) / n
    return A * v, v


def rational_q(c: float, i_mm_h: float, area_rai: float) -> float:
    """Q = 0.278 C I A (A km²), A in rai (1 rai = 1,600 m²)."""
    return 0.278 * c * i_mm_h * area_rai * 1600.0 / 1e6


# ---------------------------------------------------------------------------
# the road's culverts
# ---------------------------------------------------------------------------

class Culvert:
    def __init__(self, s, z_ground, z_design, d, rows=1):
        self.s, self.zg, self.zd = float(s), float(z_ground), float(z_design)
        self.d, self.rows = float(d), int(rows)
        self.length = 0.0
        self.cover = 0.0
        self.dig = 0.0
        self.notes = []

    @property
    def d_mm(self) -> int:
        return int(round(self.d * 1000))

    @property
    def wall(self) -> float:
        return PIPE_T1.get(self.d_mm, (max(60, self.d_mm * 0.1),))[0] / 1000.0

    @property
    def pipes(self) -> int:
        return int(math.ceil(self.length - 1e-6)) * self.rows


def _z_on(sec, which):
    return getattr(sec, which, None)


def find_culverts(an, drain=None) -> list:
    """The culverts: ``drain["culverts"]`` = [(station, D m, rows)] as
    given, else one at each low point of the ground along the axis (at
    least 0.30 m under the ground 50 m either side, 150 m apart), sized
    ``drain["pipe_d"]`` (default Ø 0.60 m, the smallest a man can clean)."""
    drain = dict(drain or {})
    d0 = float(drain.get("pipe_d") or 0.60)
    secs = [s for s in getattr(an, "sections", []) if s.z_ground is not None and s.z_design is not None]
    out = []
    given = drain.get("culverts")
    if given:
        for item in given:
            s, d, n = (list(item) + [d0, 1])[:3]
            near = min(secs, key=lambda x: abs(x.s - s)) if secs else None
            if near is None:
                continue
            out.append(Culvert(s, near.z_ground, near.z_design, d or d0, n or 1))
    else:
        last = -1e9
        for i, sc in enumerate(secs):
            around = [x for x in secs if 0 < abs(x.s - sc.s) <= 50.0]
            if not (any(x.s < sc.s for x in around) and any(x.s > sc.s for x in around)) \
                    or sc.s - last < 150.0:
                continue
            if all(x.z_ground >= sc.z_ground for x in around) and \
                    max(x.z_ground for x in around) - sc.z_ground >= 0.30:
                out.append(Culvert(sc.s, sc.z_ground, sc.z_design, d0, 1))
                last = sc.s
    st = an.settings
    B = float(st.width) / 2 + float(st.shoulder)
    total = sum(float(t) for _n, t, _c in st.pavement_layers())
    for c in out:
        # the invert at the ground, lowered (a channel dug in the old
        # ground) until the pipe has its 0.30 m of earth under the layers
        need = c.zd - total - COVER_MIN - c.d - 2 * c.wall
        c.dig = max(c.zg - need, 0.0)
        c.zg -= c.dig
        top = c.zg + c.d + 2 * c.wall
        c.cover = c.zd - total - top                   # earth over the pipe (under the layers)
        if c.dig > 0:
            c.notes.append(f"ขุดลดท้องท่อจากดินเดิม {c.dig:.2f} ม. ให้มีดินถมบนหลังท่อ {COVER_MIN:.2f} ม. "
                           "และปรับร่องน้ำต้นทาง/ท้ายทางให้ไหลได้")
        # out to where the side slope comes down to the pipe's top, + 0.30
        # a side for the headwall seat, in whole 1.00 m pipes
        c.length = math.ceil(2 * (B + float(st.fill_hv) * max(c.zd - top, 0.0)) + 0.6 - 1e-6)
        if c.cover < COVER_MIN - 1e-6:
            c.notes.append(f"ดินถมบนหลังท่อ {c.cover:.2f} ม. น้อยกว่า {COVER_MIN:.2f} ม. — "
                           "ยกระดับทาง หรือใช้ท่อหลายแถวขนาดเล็กลง หรือท่อลอดเหลี่ยม")
        elif c.cover > COVER_MAX:
            c.notes.append(f"ดินถมบนหลังท่อ {c.cover:.2f} ม. เกิน {COVER_MAX:.2f} ม. — "
                           "วางท่อตามแบบ ทถ-5-102 (TRENCH METHOD)")
    return out


# ---------------------------------------------------------------------------
# DR sheets
# ---------------------------------------------------------------------------

def _mark_table(sh, x, y, cols, rows, mark, h=1.8, row_h=4.4, head_h=6.0):
    if mark is not None:
        W = sum(c[1] for c in cols)
        y0 = y - head_h - mark * row_h
        sh.fill([(x, y0 - row_h), (x + W, y0 - row_h), (x + W, y0), (x, y0)], "hatch", 0.9, MARK_RGB)
    return D.table(sh, x, y, cols, rows, h, row_h, head_h)


def _pipe_section(sh, an, c, box):
    """The culvert across the road to scale: the embankment, the layers,
    the pipe (cut lengthwise) on its bedding, the headwalls."""
    st = an.settings
    B = float(st.width) / 2 + float(st.shoulder)
    total = sum(float(t) for _n, t, _c in st.pavement_layers())
    wall = c.wall
    half = c.length / 2
    x0, y0, x1, y1 = box
    span = c.length + 3.0
    h = max(c.zd - c.zg, 0.5) + 1.2
    sc = D.fit_scale((span, h), (x1 - x0, y1 - y0 - 14), (25, 30, 40, 50, 60, 75, 100, 125, 150, 200))
    k = 1000.0 / sc
    cx, cy = (x0 + x1) / 2, (y0 + 14 + y1) / 2 - (h - 1.2) / 2 * k

    def P(x, z):
        return (cx + x * k, cy + (z - c.zg) * k)
    zd, zg = c.zd, c.zg
    zgr = zg + c.dig                                     # the old ground
    toe = B + (zd - zgr) * float(st.fill_hv)
    emb = [P(-toe, zgr), P(-B, zd), P(B, zd), P(toe, zgr)]
    sh.fill(emb, "hatch", 0.88)
    sh.poly(emb, "wall", 0.4, False)
    lay = [P(-B, zd), P(B, zd), P(B, zd - total), P(-B, zd - total)]
    sh.fill(lay, "hatch", 0.55)
    sh.poly(lay, "wall", 0.3)
    sh.line(P(-toe - 1.4, zgr), P(toe + 1.4, zgr), "wall", 0.35)
    if c.dig > 0:
        sh.text((P(-toe - 1.4, zgr)[0], P(0, zgr)[1] + 1.0), "ดินเดิม", 1.7, "left", "dim")
        D._dim_v(sh, P(half, 0)[0] + 5, P(0, zg)[1], P(0, zgr)[1], f"ขุดลด {c.dig:.2f}")
    # bedding and the pipe (outside wall and bore)
    bed = 0.15 * c.d + 0.10
    sh.fill([P(-half, zg - bed), P(half, zg - bed), P(half, zg), P(-half, zg)], "hatch", 0.70)
    sh.rect(*P(-half, zg - bed), *P(half, zg), "wall", 0.25)
    sh.rect(*P(-half, zg), *P(half, zg + c.d + 2 * wall), "cut", 0.45)
    sh.rect(*P(-half, zg + wall), *P(half, zg + wall + c.d), "hidden", 0.25, True)
    for sg in (-1, 1):                                   # headwalls and aprons
        xw = sg * half
        hw = [P(xw, zg - 0.4), P(xw + sg * 0.20, zg - 0.4), P(xw + sg * 0.20, zg + c.d + 2 * wall + 0.30),
              P(xw, zg + c.d + 2 * wall + 0.30)]
        sh.fill(hw, "hatch", 0.45)
        sh.poly(hw, "wall", 0.35)
        ap = [P(xw + sg * 0.20, zg - 0.2), P(xw + sg * 1.20, zg - 0.2), P(xw + sg * 1.20, zg),
              P(xw + sg * 0.20, zg)]
        sh.fill(ap, "hatch", 0.6)
        sh.poly(ap, "wall", 0.25)
    D._dim_h(sh, P(-half, 0)[0], P(half, 0)[0], P(0, zg - bed)[1] - 5,
             f"ความยาวท่อ {c.length:.2f} ม. ({int(math.ceil(c.length))} ท่อน × {c.rows} แถว)")
    D._dim_v(sh, P(half, 0)[0] + 13, P(0, zg + c.d + 2 * wall)[1], P(0, zd - total)[1],
             f"Hc {max(c.cover, 0):.2f}")
    sh.text(P(0, zd + 0.15), f"ระดับผิวจราจร +{zd:.3f}", 1.8, "center", "dim")
    sh.text((P(-half, 0)[0] - 3, P(0, zg)[1] - 0.6), f"ท้องท่อ +{zg:.3f}", 1.8, "right", "dim")
    sh.text((P(0, 0)[0], P(0, zg - bed)[1] - 11), f"ท่อ คสล. Ø {c.d:.2f} ม. มอก. 128 ชั้น 3 บนทรายหยาบบดอัด "
            "+ กำแพงปากท่อและคอนกรีตลาดทั้งสองด้าน", 1.9, "center", "text", True)
    D.caption(sh, ((x0 + x1) / 2, y0 + 2), f"รูปตัดท่อลอดที่ กม. {_sta(c.s)}", f"1:{sc}")


def _sta(s: float) -> str:
    km = int(s // 1000)
    return f"{km}+{s - km * 1000:06.2f}"


DR_NOTES = [
    "1. ท่อระบายน้ำ คสล. เป็นไปตาม มอก. 128 คุณภาพชั้น 3 «ผลิตภัณฑ์อุตสาหกรรมท่อคอนกรีตเสริมเหล็ก"
    "สำหรับงานระบายน้ำ»",
    "2. กำลังอัดคอนกรีต (ลูกบาศก์ 28 วัน) ไม่น้อยกว่า 350 กก./ตร.ซม. ปูนซีเมนต์ไม่น้อยกว่า 350 กก./ลบ.ม.",
    "3. ดินเดิม CBR >= 4% วางท่อแบบ ORDINARY บนทรายหยาบบดอัด ; CBR < 4% วางบนแบบ CONCRETE CRADLE "
    "(คอนกรีตหยาบ 1:3:5) ; ดินอ่อนมาก วางบนเสาเข็ม (ON PILE)",
    "4. ดินถมข้างและบนหลังท่อ บดอัดเป็นชั้นไม่เกิน 0.15 ม. ไม่น้อยกว่า 95% STANDARD PROCTOR DENSITY "
    "ถึงระดับหลังท่อ 0.30 ม. ก่อนให้เครื่องจักรหนักผ่าน",
    "5. ดินถมบนหลังท่อไม่น้อยกว่า 0.30 ม. และไม่เกิน 3.00 ม. ; เกิน 3.00 ม. ให้วางท่อตามแบบ ทถ-5-102",
    "6. รอยต่อท่อยาแนวด้วยปูนทราย 1:2 ให้เรียบร้อยทั้งด้านในและด้านนอก ทิ้งไว้ 48 ชม. ก่อนถมกลับ",
    "7. ปากท่อทั้งสองด้านทำกำแพงปากท่อและคอนกรีตลาดกันกัดเซาะ ตามแบบ ทถ-5-103",
    "8. ลาดท้องท่อตามแนวทางน้ำไม่น้อยกว่า 0.5% และระดับท้องท่อไม่สูงกว่าท้องร่องน้ำเดิม",
]


def dr_sheets(an, info=None) -> list:
    info = dict(info or {})
    drain = dict(info.get("drain") or {})
    culverts = find_culverts(an, drain)
    out = [_dr01(an, culverts, drain), _dr02(an, culverts, drain)]
    return out


def _dr01(an, culverts, drain):
    sh = D.Sheet("DR-01", "ท่อระบายน้ำ คสล. ชนิดกลม (ท่อลอด)", "ตามระบุ", "DR")
    d_mm = culverts[0].d_mm if culverts else int(round(float(drain.get("pipe_d") or 0.60) * 1000))
    if culverts:
        worst = max(culverts, key=lambda c: c.zd - c.zg)
        _pipe_section(sh, an, worst, (X0 + 2, Y1 - 112, X0 + 200, Y1 - 4))
    else:
        sh.text((X0 + 100, Y1 - 50), "ไม่พบจุดต่ำของพื้นดินตามแนวทาง — กำหนดตำแหน่งท่อลอดเองได้", 2.6,
                "center", "text", True)
    # the culvert schedule
    sh.text((X0 + 4, Y1 - 126), "ตารางท่อลอด (คำนวณจากแนวทางและระดับออกแบบ)", 2.8, "left", "text", True)
    cols = [("ที่", 8, "center"), ("กม.", 22, "center"), ("Ø (ม.)", 14, "center"), ("แถว", 10, "center"),
            ("ท้องท่อ", 18, "right"), ("ผิวทาง", 18, "right"), ("Hc (ม.)", 15, "right"),
            ("ขุดลด", 14, "right"),
            ("ยาว (ม.)", 15, "right"), ("ท่อน", 12, "right"), ("กำแพงปากท่อ", 22, "center")]
    rows = [[str(i), _sta(c.s), f"{c.d:.2f}", str(c.rows), f"{c.zg:.3f}", f"{c.zd:.3f}", f"{c.cover:.2f}",
             f"{c.dig:.2f}", f"{c.length:.2f}", str(c.pipes), "2 ชุด"] for i, c in enumerate(culverts, 1)]
    if not rows:
        rows = [["-"] * 11]
    yy = D.table(sh, X0 + 4, Y1 - 129, cols, rows[:12], 1.8, 4.4, 5.5)
    if len(rows) > 12:
        sh.text((X0 + 4, yy - 3), f"… และอีก {len(rows) - 12} แห่ง (ดูแผ่น PP)", 1.7)
        yy -= 4
    warn = [f"กม. {_sta(c.s)}: {n}" for c in culverts for n in c.notes]
    for w in warn[:6]:
        yy -= 3.6
        sh.text((X0 + 4, yy), "(!) " + w, 1.7, "left", "roof")
    # the capacity (Manning) — the standard gives none
    sl = float(drain.get("slope") or 0.005)
    yc = yy - 10
    sh.text((X0 + 4, yc), f"ความสามารถระบายน้ำของท่อ (Manning n = {N_MANNING}, ลาดท่อ {sl * 100:g}%, "
            "ไหลเต็มท่อ)", 2.4, "left", "text", True)
    cols2 = [("Ø (มม.)", 18, "center")] + [(f"{d}", 20, "right") for d in PIPE_T1]
    q = [pipe_capacity(d / 1000.0, sl) for d in PIPE_T1]
    D.table(sh, X0 + 4, yc - 2.5, cols2, [["Q (ลบ.ม./วินาที)"] + [f"{a:.3f}" for a, _v in q],
                                          ["V (ม./วินาที)"] + [f"{v:.2f}" for _a, v in q]], 1.8, 4.4, 5.5)
    if drain.get("area_rai"):
        Q = rational_q(float(drain.get("c") or 0.5), float(drain.get("i") or 100.0),
                       float(drain["area_rai"]))
        sh.text((X0 + 4, yc - 20), f"Q ออกแบบ = 0.278 C I A = {Q:.3f} ลบ.ม./วินาที (พื้นที่รับน้ำ "
                f"{float(drain['area_rai']):g} ไร่)", 1.9, "left", "roof", True)
    # ทถ-5-101 tables 1–2, the size used marked
    x = X0 + 206
    keys = list(PIPE_T1)
    mark = keys.index(d_mm) if d_mm in keys else None
    sh.text((x, Y1 - 6), "ตารางที่ 1 ขนาดเส้นผ่านศูนย์กลางภายในและของท่อ (ทถ-5-101)", 2.3, "left", "text", True)
    cols = [("D (มม.)", 18, "center"), ("T (มม.)", 16, "center"), ("t", 12, "center"), ("a", 12, "center"),
            ("b", 12, "center"), ("c", 12, "center")]
    yy = _mark_table(sh, x, Y1 - 9, cols, [[str(d)] + [str(v) for v in PIPE_T1[d]] for d in keys], mark)
    sh.text((x, yy - 6), "ตารางที่ 2 เหล็กเสริมตามขวาง แรงที่ทำให้ท่อแตก", 2.3, "left", "text", True)
    cols = [("D (มม.)", 18, "center"), ("วงใน ตร.ซม./ม.", 26, "center"), ("วงนอก", 18, "center"),
            ("แรงทำให้แตก N/ม.", 30, "right")]
    yy = _mark_table(sh, x, yy - 9, cols, [[str(d), f"{a:g}", f"{b:g}" if b else "-", f"{p:,}"]
                                           for d, (a, b, p) in PIPE_T2.items()], mark)
    sh.text((x, yy - 3.5), "แถบสีเหลือง = ขนาดท่อที่ใช้ในโครงการ · ดินถมบนหลังท่อ 0.30–3.00 ม.", 1.7)
    D.notes_block(sh, x, yy - 10, "รายการประกอบแบบ", DR_NOTES, 1.9, 62)
    return sh


def _dr02(an, culverts, drain):
    sh = D.Sheet("DR-02", "กำแพงปากท่อ และรางระบายน้ำ คสล.", "ตามระบุ", "DR")
    d_cm = int(round((culverts[0].d if culverts else float(drain.get("pipe_d") or 0.60)) * 100))
    rows_n = max([c.rows for c in culverts] or [1])
    keys = list(HEADWALL)
    dk = min(keys, key=lambda k: abs(k - d_cm))
    T, th, b1, l1, b2, l2, b3, l3 = HEADWALL[dk]
    Bw, Lw = ((b1, l1), (b2, l2), (b3, l3))[min(rows_n, 3) - 1]
    # front view to 1:25
    k = 1000.0 / 25 / 100.0                              # mm per cm
    ox, oy = X0 + 14, Y1 - 70
    H = dk + 2 * T + 30 + 20
    sh.rect(ox, oy, ox + Bw * k, oy + H * k, "wall", 0.45)
    sh.rect(ox, oy - 40 * k, ox + Bw * k, oy, "hidden", 0.25, True)
    gap = dk / 2
    xs = [60 + dk / 2 + T + i * (dk + 2 * T + gap) for i in range(rows_n)]
    for xc in xs:
        c = (ox + xc * k, oy + (20 + T + dk / 2) * k)
        sh.circle(c, (dk / 2 + T) * k, "cut", 0.4)
        sh.circle(c, dk / 2 * k, "wall", 0.3)
    D._dim_h(sh, ox, ox + Bw * k, oy + H * k + 4, f"B = {Bw / 100:.2f}")
    D._dim_h(sh, ox, ox + 60 * k, oy - 40 * k - 4, "0.60")
    D._dim_v(sh, ox - 4, oy - 40 * k, oy, "0.40")
    sh.text((ox + Bw * k / 2, oy + H * k + 9), "ระดับขอบไหล่ทาง", 1.8, "center", "dim")
    D.caption(sh, (ox + Bw * k / 2, oy - 40 * k - 13), "รูปด้านหน้ากำแพงปากท่อ",
              f"1:25 (Ø {dk / 100:.2f} ม. {rows_n} แถว)")
    # side view: the wall, the sloping wing over the apron, the cut-off
    sx, sy = X0 + 108, oy
    sh.fill([(sx, sy - 20 * k), (sx + 20 * k, sy - 20 * k), (sx + 20 * k, sy + H * k), (sx, sy + H * k)],
            "hatch", 0.55)
    sh.rect(sx, sy - 20 * k, sx + 20 * k, sy + H * k, "wall", 0.45)
    ap = [(sx + 20 * k, sy - 20 * k), (sx + (20 + Lw) * k, sy - 20 * k), (sx + (20 + Lw) * k, sy),
          (sx + 20 * k, sy)]
    sh.fill(ap, "hatch", 0.7)
    sh.poly(ap, "wall", 0.35)
    co = [(sx + Lw * k, sy - 60 * k), (sx + (20 + Lw) * k, sy - 60 * k), (sx + (20 + Lw) * k, sy - 20 * k),
          (sx + Lw * k, sy - 20 * k)]
    sh.fill(co, "hatch", 0.55)
    sh.poly(co, "wall", 0.35)
    sh.line((sx + 20 * k, sy + H * k), (sx + (20 + Lw) * k, sy + 15 * k), "wall", 0.4)
    sh.line((sx - 25 * k, sy), (sx, sy), "wall", 0.3)
    D._dim_h(sh, sx + 20 * k, sx + (20 + Lw) * k, sy + H * k + 4, f"L = {Lw / 100:.2f}")
    D._dim_h(sh, sx, sx + 20 * k, sy - 60 * k - 4, "0.20")
    D._dim_v(sh, sx + (20 + Lw) * k + 4, sy - 60 * k, sy - 20 * k, "0.40")
    sh.text((sx + 24 * k, sy + 3 * k), "คอนกรีตลาดกันกัดเซาะ หนา 0.20", 1.6)
    D.caption(sh, (sx + (20 + Lw) * k / 2, oy - 40 * k - 13), "รูปด้านข้าง", "1:25")
    # the ทถ-5-103 table
    x = X0 + 4
    sh.text((x, Y1 - 128), "ตารางขนาดคอนกรีตกันการกัดเซาะที่ปลายท่อระบายน้ำ (ทถ-5-103) หน่วย ซม.", 2.3, "left",
            "text", True)
    cols = [("D", 12, "center"), ("T", 12, "center"), ("มุม", 10, "center"), ("B 1 แถว", 16, "center"),
            ("L", 12, "center"), ("B 2 แถว", 16, "center"), ("L", 12, "center"), ("B 3 แถว", 16, "center"),
            ("L", 12, "center")]
    yy = _mark_table(sh, x, Y1 - 131, cols, [[str(d)] + [f"{v:g}" for v in HEADWALL[d]] for d in keys],
                     keys.index(dk), 1.7, 4.0)
    # the U-drain (ทถ-5-301)
    typ = drain.get("u_type") or "ข-50"
    W, Hh, T1, T2, A, Bs, C, Ds = UDRAIN[typ]
    k2 = 1000.0 / 20 / 100.0                              # 1:20, mm per cm
    ux, uy = X0 + 236, Y1 - 80
    tw = T1
    outer = [(ux, uy), (ux + (W + 2 * tw) * k2, uy), (ux + (W + 2 * tw) * k2, uy + (Hh + T1) * k2),
             (ux + (W + tw) * k2, uy + (Hh + T1) * k2), (ux + (W + tw) * k2, uy + T1 * k2),
             (ux + tw * k2, uy + T1 * k2), (ux + tw * k2, uy + (Hh + T1) * k2), (ux, uy + (Hh + T1) * k2)]
    sh.fill(outer, "hatch", 0.55)
    sh.poly(outer, "wall", 0.4)
    sh.rect(ux + tw * k2, uy + (Hh + T1) * k2 - T2 * k2, ux + (W + tw) * k2, uy + (Hh + T1) * k2,
            "hidden", 0.3, True)
    sh.fill([(ux - 5 * k2, uy - 10 * k2), (ux + (W + 2 * tw + 5) * k2, uy - 10 * k2),
             (ux + (W + 2 * tw + 5) * k2, uy), (ux - 5 * k2, uy)], "hatch", 0.8)
    D._dim_h(sh, ux + tw * k2, ux + (W + tw) * k2, uy + (Hh + T1) * k2 + 4, f"W {W}")
    D._dim_v(sh, ux + (W + 2 * tw) * k2 + 4, uy + T1 * k2, uy + (Hh + T1) * k2, f"H {Hh}")
    D._dim_v(sh, ux - 4, uy, uy + T1 * k2, f"T1 {T1}")
    sh.text((ux - 5 * k2, uy - 10 * k2 - 3.5), "คอนกรีตหยาบ 1:3:5 บนทรายหยาบบดอัดแน่น", 1.7)
    D.caption(sh, (ux + (W + 2 * tw) * k2 / 2, uy - 14 * k2 - 12), f"รางระบายน้ำ คสล. แบบ {typ}",
              "1:20 (ทถ-5-301) หน่วย ซม.")
    sh.text((X0 + 175, Y1 - 128), "ตารางรางระบายน้ำ คสล. ย่านชุมชน (ทถ-5-301)", 2.3, "left", "text", True)
    cols = [("แบบ", 12, "center"), ("W", 9, "center"), ("H", 9, "center"), ("T1", 9, "center"),
            ("T2", 10, "center"), ("A", 16, "center"), ("B", 16, "center"), ("C", 16, "center"),
            ("D", 16, "center")]
    uk = list(UDRAIN)
    yy2 = _mark_table(sh, X0 + 175, Y1 - 131, cols,
                      [[t, f"{v[0]}", f"{v[1]}", f"{v[2]}", f"{v[3]:g}"] +
                       [f"Ø{d}@{s}" for d, s in v[4:]] for t, v in UDRAIN.items()],
                      uk.index(typ), 1.7, 4.0)
    sh.text((X0 + 175, yy2 - 3.5), "ฝาตะแกรงเหล็ก 0.79 × 0.79 ม. แผ่นเหล็ก 0.050 × 0.005 @0.035 · "
            "บ่อพักทุก 10 ม. (ทถ-5-302)", 1.7)
    # the bill
    ud_len = float(drain.get("u_length") or 0.0)
    pipes = sum(c.pipes for c in culverts)
    rows = [["ท่อระบายน้ำ คสล. มอก.128 ชั้น 3 ขนาดต่างๆ", "ท่อน", f"{pipes:,}"],
            ["ทรายหยาบรองท่อ / คอนกรีตหยาบ", "แห่ง", f"{len(culverts)}"],
            ["กำแพงปากท่อและคอนกรีตลาดกันกัดเซาะ (ทถ-5-103)", "ชุด", f"{2 * len(culverts)}"]]
    if ud_len:
        conc = ((W + 2 * T1) * (Hh + T1) - W * Hh) / 1e4 * ud_len
        rows += [[f"รางระบายน้ำ คสล. แบบ {typ} พร้อมฝา", "ม.", f"{ud_len:,.1f}"],
                 ["  คอนกรีตราง (โดยประมาณ)", "ลบ.ม.", f"{conc:,.2f}"],
                 ["  ฝาตะแกรงเหล็ก (บ่อพักทุก 10 ม.)", "ฝา", f"{int(ud_len // 10) + 1}"]]
    sh.text((X0 + 4, min(yy, yy2) - 10), "ปริมาณงานระบายน้ำ", 2.6, "left", "text", True)
    D.table(sh, X0 + 4, min(yy, yy2) - 13, [("รายการ", 90, "left"), ("หน่วย", 14, "center"),
                                           ("จำนวน", 20, "right")], rows, 1.8, 4.4, 5.5)
    return sh


# ---------------------------------------------------------------------------
# TS — signs, markings and safety
# ---------------------------------------------------------------------------

class Furniture:
    """Where the signs, posts and lines go along the road."""

    def __init__(self, an, info=None):
        info = dict(info or {})
        ts = dict(info.get("signs") or {})
        st = an.settings
        self.length = float(an.designed_length or getattr(an, "length", 0.0) or 0.0)
        self.s0 = float(an.grade[0][0]) if getattr(an, "grade", None) else 0.0
        self.width = float(st.width)
        self.speed = float(ts.get("speed") or 60.0)
        self.urban = bool(ts.get("urban"))
        self.secs = [s for s in getattr(an, "sections", []) if s.z_ground is not None
                     and s.z_design is not None]
        self.curves = [c for c in getattr(an, "hcurves", []) or [] if c.radius > 0]
        self.items = []                      # (s, side +1 right/-1 left, kind, label)
        self.rail = []                       # (s0, s1, side, spacing, n posts)
        self.guide = []                      # (curve number, n posts, spacing)
        self.solid = []                      # (s0, s1) no-passing
        self._place()

    def fill_at(self, s0, s1):
        h = [x.z_design - x.z_ground for x in self.secs if s0 - 1 <= x.s <= s1 + 1]
        return max(h) if h else 0.0

    def _place(self):
        s0, s1 = self.s0, self.s0 + self.length
        self.items.append((s0, 1, "น-1", "ป้ายโครงการ น-1"))
        self.items.append((s1, -1, "น-1", "ป้ายโครงการ น-1"))
        km = math.ceil(s0 / 1000.0) * 1000.0
        while km <= s1 + 1e-6:
            self.items.append((km, 1, "km", f"หลัก กม. {int(km // 1000)}"))
            km += 1000.0
        adv = min(150.0, max(50.0, 1.5 * self.speed))
        for c in self.curves:
            left = c.delta < 0
            sharp = " (รัศมีแคบ)" if c.radius < 150 else ""
            name = "ป้ายเตือนทางโค้ง" + ("ซ้าย" if left else "ขวา") + sharp
            back = "ป้ายเตือนทางโค้ง" + ("ขวา" if left else "ซ้าย") + sharp
            self.items.append((max(s0, c.s_pc - adv), 1, "warn", name))
            self.items.append((min(s1, c.s_pt + adv), -1, "warn", back))
            outside = -1 if c.delta > 0 else 1         # right-hand curve: the outside is left
            if c.radius < RAIL_R or self.fill_at(c.s_pc, c.s_pt) > RAIL_FILL:
                S = rail_spacing(c.radius)
                a, b = c.s_pc - 4.0 * 2, c.s_pt + 4.0 * 2
                self.rail.append((a, b, outside, S, int(math.ceil((b - a) / S)) + 1))
            else:
                s, s_1, s_2, s_3 = guide_spacing(c.radius)
                n_in = int(c.length // s) + 1
                n_out = 2 * 3                              # ส1 ส2 ส3 before and after
                self.guide.append((c.number, n_in + n_out, s, (s_1, s_2, s_3), c.radius))
            if self.width > 5.0:
                self.solid.append((max(s0, c.s_pc), min(s1, c.s_pt)))

    def markings(self) -> dict:
        """Lengths (m) and areas (m²) of the lines."""
        L = self.length
        edge = 2 * L
        if self.width <= 5.0:
            return {"edge": edge, "solid": 0.0, "broken": 0.0, "area": edge * LINE_W, "centre": False}
        solid = sum(b - a for a, b in self.solid)
        on, off = BROKEN["urban" if self.urban else "rural"]
        broken = max(L - solid, 0.0) * on / (on + off)
        return {"edge": edge, "solid": solid, "broken": broken,
                "area": (edge + solid + broken) * LINE_W, "centre": True}


def _strip(sh, fu, box, s_a, s_b):
    """The road from s_a to s_b as a straight band in ``box``."""
    x0, y0, x1, y1 = box
    k = (x1 - x0) / max(s_b - s_a, 1.0)
    yc = (y0 + y1) / 2
    hw = 4.0

    def X(s):
        return x0 + (s - s_a) * k
    sh.line((X(s_a), yc + hw), (X(s_b), yc + hw), "wall", 0.4)
    sh.line((X(s_a), yc - hw), (X(s_b), yc - hw), "wall", 0.4)
    if fu.markings()["centre"]:
        on, off = BROKEN["urban" if fu.urban else "rural"]
        step = max((on + off) * k, 1.2)
        x = X(s_a)
        while x < X(s_b):
            sh.line((x, yc), (min(x + step * on / (on + off), X(s_b)), yc), "dim", 0.25)
            x += step
        for a, b in fu.solid:
            if b > s_a and a < s_b:
                sh.line((X(max(a, s_a)), yc + 0.35), (X(min(b, s_b)), yc + 0.35), "roof", 0.45)
                sh.line((X(max(a, s_a)), yc - 0.35), (X(min(b, s_b)), yc - 0.35), "roof", 0.45)
    s = math.ceil(s_a / 100.0) * 100.0
    while s <= s_b + 1e-6:
        big = abs(s % 1000.0) < 1e-6
        sh.line((X(s), yc - hw - (2.5 if big else 1.2)), (X(s), yc - hw), "grid", 0.25 if big else 0.13)
        if big or (s_b - s_a) <= 1200:
            sh.text((X(s), yc - hw - 5.2), _sta(s)[:-3], 1.6, "center", "grid")
        s += 100.0
    for c in fu.curves:
        if c.s_pt < s_a or c.s_pc > s_b:
            continue
        a, b = X(max(c.s_pc, s_a)), X(min(c.s_pt, s_b))
        sh.line((a, yc + hw + 3.4), (b, yc + hw + 3.4), "door", 0.35)
        sh.text(((a + b) / 2, yc + hw + 4.2), f"โค้ง {c.number} R {c.radius:,.0f}", 1.6, "center", "door")
    for a, b, side, S, n in fu.rail:
        if b < s_a or a > s_b:
            continue
        y = yc + side * (hw + 1.4)
        sh.line((X(max(a, s_a)), y), (X(min(b, s_b)), y), "cut", 0.7)
    lanes = {1: [], -1: []}
    for s, side, kind, label in sorted(fu.items):
        if not (s_a - 1e-6 <= s <= s_b + 1e-6):
            continue
        y = yc + (hw + 8.0 if side > 0 else -(hw + 10.0))
        x = X(s)
        if kind == "km":
            sh.rect(x - 0.8, y - 1.2, x + 0.8, y + 1.2, "wall", 0.3)
        else:
            sh.poly([(x, y + 1.6), (x + 1.6, y), (x, y - 1.6), (x - 1.6, y)], "roof", 0.3)
        lane = lanes[side]
        lvl = 0
        while any(abs(x - px) < 18 and pl == lvl for px, pl in lane):
            lvl += 1
        lane.append((x, lvl))
        ty = y + side * (3.5 + 3.0 * lvl)
        sh.line((x, y + side * 1.6), (x, ty - side * 0.4), "dim", 0.13)
        sh.text((x, ty + (0 if side > 0 else -1.6)), label, 1.6, "center")


def ts_sheets(an, info=None) -> list:
    fu = Furniture(an, info)
    if fu.length <= 0:
        return []
    return [_ts01(fu), _ts02(fu)]


def _ts01(fu):
    sh = D.Sheet("TS-01", "แผนผังป้ายจราจร เครื่องหมายจราจรบนผิวทาง และอุปกรณ์อำนวยความปลอดภัย", "ไม่ตามมาตราส่วน",
                 "TS")
    s0, L = fu.s0, fu.length
    nrows = max(1, min(4, int(math.ceil(L / 1500.0))))
    part = L / nrows
    for i in range(nrows):
        y1 = Y1 - 8 - i * 38
        _strip(sh, fu, (X0 + 14, y1 - 34, X1 - 14, y1), s0 + i * part, s0 + (i + 1) * part)
    yl = Y1 - 12 - nrows * 38
    # legend and quantities
    sh.text((X0 + 4, yl), "สัญลักษณ์", 2.6, "left", "text", True)
    lg = [("สี่เหลี่ยมข้าวหลามตัด = ป้ายจราจร (แบบตามคู่มือเครื่องหมายควบคุมการจราจร)", "roof"),
          ("สี่เหลี่ยมเล็ก = หลักกิโลเมตร แบบที่ 2 (ทถ-3-111)", "wall"),
          ("เส้นแดงคู่ = เส้นทึบห้ามแซงบริเวณโค้ง (สีเหลือง)", "roof"),
          ("เส้นแดงหนาข้างทาง = GUARD RAIL (ทถ-3-201)", "cut")]
    for j, (t, lay) in enumerate(lg):
        sh.text((X0 + 6, yl - 4.5 - j * 4.0), t, 1.8, "left", lay)
    m = fu.markings()
    n_sign = sum(1 for it in fu.items if it[2] != "km")
    n_km = sum(1 for it in fu.items if it[2] == "km")
    rows = [["ป้ายโครงการ น-1 (ทถ-3-107)", "ป้าย", f"{sum(1 for it in fu.items if it[2] == 'น-1')}"],
            ["ป้ายเตือนทางโค้ง 60 × 60 ซม. พร้อมเสา (ทถ-3-108)", "ป้าย",
             f"{n_sign - sum(1 for it in fu.items if it[2] == 'น-1')}"],
            ["หลักกิโลเมตร แบบที่ 2 (ทถ-3-111)", "หลัก", f"{n_km}"],
            ["หลักนำโค้ง GUIDE POST (ทถ-3-112)", "ต้น", f"{sum(g[1] for g in fu.guide)}"],
            ["GUARD RAIL ชั้นที่ 2 ชนิดที่ 1 (ทถ-3-201)", "ม.", f"{sum(b - a for a, b, *_r in fu.rail):,.1f}"],
            ["  เสา GUARD RAIL", "ต้น", f"{sum(r[4] for r in fu.rail)}"],
            ["เส้นขอบทาง สีขาว กว้าง 10 ซม.", "ม.", f"{m['edge']:,.1f}"],
            ["เส้นแบ่งทิศทางจราจร เส้นประ สีขาว", "ม.", f"{m['broken']:,.1f}"],
            ["เส้นทึบห้ามแซง สีเหลือง", "ม.", f"{m['solid']:,.1f}"],
            ["รวมพื้นที่เครื่องหมายจราจร (THERMOPLASTIC)", "ตร.ม.", f"{m['area']:,.2f}"]]
    sh.text((X0 + 120, yl), "ปริมาณงานป้ายและเครื่องหมายจราจร", 2.6, "left", "text", True)
    D.table(sh, X0 + 120, yl - 3, [("รายการ", 92, "left"), ("หน่วย", 14, "center"), ("จำนวน", 22, "right")],
            rows, 1.8, 4.2, 5.5)
    notes = [f"1. ความเร็วออกแบบ {fu.speed:g} กม./ชม. — ป้ายเตือนติดตั้งก่อนถึงโค้ง (PC/PT) ประมาณ "
             f"{min(150.0, max(50.0, 1.5 * fu.speed)):.0f} ม. ปรับตามสภาพหน้างาน",
             "2. โค้ง R < 150 ม. หรือคันทางสูงเกิน 6.00 ม. ใช้ GUARD RAIL ด้านนอกโค้งแทนหลักนำโค้ง "
             "(ทถ-3-201 หมายเหตุ 5)",
             "3. ผิวจราจรกว้าง 5 ม. หรือน้อยกว่า ไม่ต้องตีเส้นแบ่งทิศทางจราจร (ทถ-3-110(1) ข้อ 2.5)" if
             not m["centre"] else
             f"3. เส้นประ {'1.00/3.00' if fu.urban else '3.00/9.00'} ม. ; บริเวณโค้งเส้นทึบห้ามแซง "
             f"ตรวจระยะมองเห็นไม่น้อยกว่า {no_pass_distance(fu.speed):.0f} ม. (ทถ-3-110(1))",
             "4. หลักกิโลเมตร ติดตั้งด้านซ้ายทาง ตามทิศทางการนับระยะ ห่างขอบไหล่ทาง ไม่น้อยกว่า 0.30 ม.",
             "5. ตำแหน่งในแผนผังเป็นตำแหน่งตามแนวทาง ผู้ควบคุมงานปรับได้ตามสภาพพื้นที่"]
    D.notes_block(sh, X0 + 252, yl, "หมายเหตุ", notes, 1.8, 50)
    return sh


def _ts02(fu):
    sh = D.Sheet("TS-02", "แบบขยายการติดตั้งป้าย หลักกิโลเมตร หลักนำโค้ง และ GUARD RAIL", "ตามระบุ", "TS")
    k = 20.0                                        # 1:50 — paper mm per metre
    # single sign post (ทถ-3-108)
    gx, gy = X0 + 40, Y1 - 118
    sh.line((gx - 30, gy), (gx + 34, gy), "wall", 0.4)
    sh.text((gx + 33, gy + 1), "ระดับขอบไหล่ทาง", 1.6, "right", "dim")
    sh.rect(gx - 0.06 * k, gy - 1.20 * k, gx + 0.06 * k, gy + 1.50 * k + 0.30 * k, "wall", 0.4)
    sh.fill([(gx - 0.20 * k, gy - 1.35 * k), (gx + 0.20 * k, gy - 1.35 * k), (gx + 0.20 * k, gy),
             (gx - 0.20 * k, gy)], "hatch", 0.82)
    sh.poly([(gx, gy + 1.80 * k), (gx + 0.30 * k, gy + 2.10 * k), (gx, gy + 2.40 * k),
             (gx - 0.30 * k, gy + 2.10 * k)], "roof", 0.4)
    D._dim_v(sh, gx - 0.45 * k, gy, gy + 1.50 * k, "1.50 (MIN)")
    D._dim_v(sh, gx + 0.45 * k, gy - 1.20 * k, gy, "1.20")
    D._dim_h(sh, gx + 0.06 * k, gx + 0.66 * k, gy + 0.3 * k, "0.60 (MIN)")
    sh.text((gx + 0.75 * k, gy - 0.6 * k), "ฐานคอนกรีต 0.40 × 0.40 ม.", 1.6)
    sh.text((gx + 0.75 * k, gy + 1.0 * k), "เสา คสล. 0.12 × 0.12 ม. (ไม่เกิน 6.00 ม.)", 1.6)
    D.caption(sh, (gx + 6, gy - 1.35 * k - 8), "การติดตั้งป้ายเตือน", "1:50 (ทถ-3-108)")
    # kilometre post type 2 (ทถ-3-111)
    kx, ky = X0 + 125, gy
    sh.line((kx - 22, ky), (kx + 22, ky), "wall", 0.4)
    sh.rect(kx - 0.125 * k, ky - 0.50 * k, kx + 0.125 * k, ky + 0.80 * k, "wall", 0.4)
    sh.text((kx, ky + 0.45 * k), "กม.", 2.4, "center", "text", True)
    sh.text((kx, ky + 0.25 * k), "1", 2.6, "center", "text", True)
    D._dim_v(sh, kx - 0.30 * k, ky, ky + 0.80 * k, "0.80")
    D._dim_v(sh, kx - 0.30 * k, ky - 0.50 * k, ky, "0.50")
    D._dim_h(sh, kx - 0.125 * k, kx + 0.125 * k, ky + 0.80 * k + 4, "0.25")
    D.caption(sh, (kx, gy - 1.35 * k - 8), "หลัก กม. แบบที่ 2", "1:50 (ทถ-3-111)")
    # guide post (ทถ-3-112)
    px, py = X0 + 190, gy
    sh.line((px - 20, py), (px + 24, py), "wall", 0.4)
    sh.rect(px - 0.075 * k, py - 0.50 * k, px + 0.075 * k, py + 0.80 * k, "wall", 0.4)
    yb = py + 0.80 * k
    for z0, z1 in ((0.05, 0.30), (0.45, 0.60)):
        sh.fill([(px - 0.075 * k, yb - z1 * k), (px + 0.075 * k, yb - z1 * k), (px + 0.075 * k, yb - z0 * k),
                 (px - 0.075 * k, yb - z0 * k)], "hatch", 0.15)
    sh.text((px + 0.15 * k, yb - 0.17 * k), "แถบสะท้อนแสงสีขาว / ทาสีดำ", 1.5)
    D._dim_v(sh, px - 0.25 * k, py, py + 0.80 * k, "0.80")
    D._dim_v(sh, px - 0.25 * k, py - 0.50 * k, py, "0.50 (MIN)")
    D._dim_h(sh, px - 0.075 * k, px + 0.075 * k, yb + 4, "0.15")
    D.caption(sh, (px, gy - 1.35 * k - 8), "หลักนำโค้ง", "1:50 (ทถ-3-112)")
    # guard rail section (ทถ-3-201)
    rx, ry = X0 + 262, gy
    sh.line((rx - 18, ry), (rx + 22, ry), "wall", 0.4)
    sh.rect(rx - 0.05 * k, ry - 1.10 * k, rx + 0.05 * k, ry + 0.60 * k, "wall", 0.4)
    wave = [(rx + 0.05 * k + 0.08 * k * math.sin(t / 10 * math.pi * 2), ry + 0.29 * k + 0.31 * k * t / 10)
            for t in range(11)]
    sh.poly(wave, "cut", 0.5, False)
    D._dim_v(sh, rx - 0.25 * k, ry, ry + 0.60 * k, "0.60")
    D._dim_v(sh, rx - 0.25 * k, ry - 1.10 * k, ry, "1.10")
    sh.text((rx + 0.30 * k, ry + 0.45 * k), "แผ่นเหล็กลูกฟูก หนา 2.5 มม.", 1.5)
    sh.text((rx + 0.30 * k, ry - 0.40 * k), "เสาเหล็ก Ø 100 มม. หนา 4 มม.", 1.5)
    D.caption(sh, (rx, gy - 1.35 * k - 8), "รูปตัด GUARD RAIL", "1:50 (ทถ-3-201)")
    # the tables
    x, y = X0 + 4, Y1 - 6
    used = {guide_row(g[4]) for g in fu.guide}
    sh.text((x, y), "ตารางระยะเครื่องหมายนำทาง (GUIDE POST) ทถ-3-112 (เมตร)", 2.3, "left", "text", True)
    cols = [("รัศมีโค้ง (ม.)", 26, "center"), ("ในโค้ง ส", 18, "center"), ("ส1", 14, "center"),
            ("ส2", 14, "center"), ("ส3", 14, "center")]
    rows = [[GUIDE_ROWS[i]] + [f"{v:g}" for v in r[1:]] for i, r in enumerate(GUIDE_POST)]
    yy = y - 2.5
    for i in sorted(used):
        W = sum(c[1] for c in cols)
        y0 = yy - 5.5 - i * 4.0
        sh.fill([(x, y0 - 4.0), (x + W, y0 - 4.0), (x + W, y0), (x, y0)], "hatch", 0.9, MARK_RGB)
    yy = D.table(sh, x, yy, cols, rows, 1.7, 4.0, 5.5)
    sh.text((x + 95, y), "ระยะห่างเสา GUARD RAIL (ทถ-3-201)", 2.3, "left", "text", True)
    D.table(sh, x + 95, y - 2.5, [("รัศมีโค้ง R (ม.)", 32, "center"), ("S (ม.)", 14, "center")],
            [["ทางตรง หรือ R >= 50", "4.00"], ["25 <= R < 50", "3.00"], ["15 <= R < 25", "2.50"],
             ["R < 15", "2.00"]], 1.7, 4.0, 5.5)
    sh.text((x + 150, y), "ระยะมองเห็นต่ำสุดสำหรับการแซง (ทถ-3-110(1))", 2.3, "left", "text", True)
    D.table(sh, x + 150, y - 2.5, [("ความเร็ว (กม./ชม.)", 30, "center"), ("ระยะ (ม.)", 18, "center")],
            [[f"{v}", f"{d}"] for v, d in NO_PASS], 1.7, 4.0, 5.5)
    # the lines
    lx, ly = x + 210, y - 6
    sh.text((lx, y), "ขนาดและระยะเครื่องหมายจราจรบนผิวทาง", 2.3, "left", "text", True)
    kk = 5.0
    for j, (t, a, b) in enumerate((("เส้นประ นอกเขตชุมชน", 3.0, 9.0), ("เส้นประ ในเขตชุมชน", 1.0, 3.0))):
        yy2 = ly - 4 - j * 9
        sh.text((lx, yy2 + 1.5), t, 1.6)
        xx = lx
        for _n in range(2):
            sh.rect(xx, yy2 - 1.6, xx + a * kk, yy2 - 0.9, "wall", 0.3)
            xx += (a + b) * kk
        D._dim_h(sh, lx, lx + a * kk, yy2 - 4.0, f"{a:.2f}")
        D._dim_h(sh, lx + a * kk, lx + (a + b) * kk, yy2 - 4.0, f"{b:.2f}")
    sh.text((lx, ly - 24), "เส้นทึบ เส้นขอบทาง กว้าง 0.10 ม. · เส้นคู่ห่าง 0.10 ม.", 1.6)
    D.notes_block(sh, X0 + 4, Y0 + 50, "รายการประกอบแบบ", [
        "1. มิติต่างๆ มีหน่วยเป็นเมตร นอกจากระบุเป็นอย่างอื่น",
        "2. แผ่นป้ายเหล็กอาบสังกะสีหนาไม่น้อยกว่า 1.2 มม. ติดแผ่นสะท้อนแสงตาม มอก. 606 ; โครงเหล็กกล่อง "
        "50 × 25 × 1.6 มม. ; เสา คสล. 0.12 × 0.12 ม. คอนกรีตชนิด ค.2",
        "3. สีจราจร มอก. 415 ชนิดที่ 2 ความหนาเปียกไม่น้อยกว่า 0.2 มม. ; วัสดุเทอร์โมพลาสติก มอก. 542 "
        "หนาไม่น้อยกว่า 3.0 มม. โรยลูกแก้ว มอก. 543 (ทถ-3-110(4))",
        "4. หลักนำโค้งคอนกรีต 0.15 × 0.15 ม. เหล็กเสริม 4-RB6 ปลอก RB6 @0.15 ทาสีขาว-ดำ "
        "ติดแผ่นสะท้อนแสงสีขาว",
        "5. GUARD RAIL มอก. 248 ชั้นที่ 2 ชนิดที่ 1 เสาเหล็กอาบสังกะสี Ø 100 มม. หนา 4 มม. ฝังลึก 1.10 ม. "
        "ติดตั้งที่ขอบไหล่ทาง ปลายทั้งสองด้านพับและยึดลงดิน",
    ], 1.8, 150)
    return sh
