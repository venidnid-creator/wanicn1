# -*- coding: utf-8 -*-
"""Construction drawing sheets — A3 sheets with a title block, built from a
design result and written to DXF (AutoCAD) and PDF.

Sheets:
    S-01  general notes: laws and standards, materials and allowable values,
          concrete covers, laps, development lengths and hooks, loads, fire
    S-02… structural plans per level (marks of beams, slabs, columns)
    S-xx  foundation plan
    S-xx  schedules with typical sections: footings, columns, beams,
          slabs and stairs

Everything is drawn on the sheet in millimetres of paper; drawings are put
on the sheet at a scale chosen from the usual ones. The sheet contents are
kept as simple primitives so the same sheet goes to DXF and to PDF.

Detailing values come from the standards: covers ประกาศ มท. 2567 ตาราง 13
[MI2567-29C]; tie sizes and spacing ข้อ 29 (11) [MI2567-29D]; development
and lap lengths ACI 318 12.2.2, 12.15, 12.16 (the basis of วสท. 1008)
[EIT1008-DEV]; standard hooks ACI 318 7.1 [EIT1008-HOOK].
"""
from __future__ import annotations

import datetime
import math
from dataclasses import dataclass, field

from ..standards import REFS
from .materials import FY
from .rules import (COVER_BEAM, COVER_COLUMN, COVER_EARTH, COVER_EXPOSED, COVER_EXPOSED_BIG, COVER_SLAB,
                    cover_factor, tie_bar)
from .sections import BAR_DIA

A3 = (420.0, 297.0)
MARGIN_L, MARGIN = 20.0, 8.0
TITLE_H = 32.0
SCALES = [20, 25, 50, 75, 100, 125, 150, 200, 250]
TXT, TXT_S, TXT_L = 2.5, 2.0, 4.0
MPA = 10.197                                  # ksc per MPa

LAYERS = {"FRAME": 7, "TEXT": 7, "GRID": 8, "BEAM": 5, "COLUMN": 1, "SLAB": 3, "FOOTING": 30, "BAR": 1,
          "DIM": 2, "HATCH": 9}


# ---------------------------------------------------------------------------
# Sheet model
# ---------------------------------------------------------------------------

@dataclass
class Sheet:
    number: str
    title: str
    scale: str = "-"
    items: list = field(default_factory=list)

    def line(self, x0, y0, x1, y1, layer="FRAME", dashed=False):
        self.items.append(("line", x0, y0, x1, y1, layer, dashed))

    def rect(self, x, y, w, h, layer="FRAME", filled=False):
        self.items.append(("rect", x, y, w, h, layer, filled))

    def circle(self, x, y, r, layer="FRAME", filled=False):
        self.items.append(("circle", x, y, r, layer, filled))

    def text(self, x, y, s, h=TXT, layer="TEXT", align="left"):
        self.items.append(("text", x, y, str(s), h, layer, align))

    def poly(self, pts, layer="FRAME", closed=True):
        self.items.append(("poly", list(pts), layer, closed))


def area(sheet_w=A3[0], sheet_h=A3[1]):
    """Drawing area inside the frame and above the title block: (x0, y0, x1, y1)."""
    return MARGIN_L + 4, MARGIN + TITLE_H + 4, sheet_w - MARGIN - 4, sheet_h - MARGIN - 4


def frame(sh: Sheet, project: str, total: int):
    W, H = A3
    sh.rect(MARGIN_L, MARGIN, W - MARGIN_L - MARGIN, H - 2 * MARGIN)
    x0, y0 = MARGIN_L, MARGIN
    w = W - MARGIN_L - MARGIN
    sh.line(x0, y0 + TITLE_H, x0 + w, y0 + TITLE_H)
    cols = [x0, x0 + 120, x0 + 230, x0 + 300, x0 + w]
    for c in cols[1:-1]:
        sh.line(c, y0, c, y0 + TITLE_H)
    sh.text(x0 + 3, y0 + TITLE_H - 7, "โครงการ", TXT_S)
    sh.text(x0 + 3, y0 + TITLE_H - 15, project, TXT_L)
    sh.text(x0 + 3, y0 + 4, "ออกแบบด้วย WanicnDesign — ผลคำนวณต้องให้วิศวกรผู้มีใบอนุญาตตรวจสอบและลงนาม", TXT_S)
    sh.text(cols[1] + 3, y0 + TITLE_H - 7, "ชื่อแผ่น", TXT_S)
    sh.text(cols[1] + 3, y0 + TITLE_H - 16, sh.title, TXT_L)
    sh.text(cols[1] + 3, y0 + 4, f"มาตราส่วน {sh.scale}", TXT_S)
    sh.text(cols[2] + 3, y0 + TITLE_H - 7, "วิศวกรผู้ออกแบบ / ภย.", TXT_S)
    sh.line(cols[2] + 3, y0 + 12, cols[3] - 3, y0 + 12)
    sh.text(cols[2] + 3, y0 + 4, "ลงชื่อ ........................", TXT_S)
    sh.text(cols[3] + 3, y0 + TITLE_H - 7, "แผ่นที่", TXT_S)
    sh.text(cols[3] + 3, y0 + TITLE_H - 17, f"{sh.number}", 6.0)
    sh.text(cols[3] + 35, y0 + TITLE_H - 17, f"/ {total}", TXT)
    sh.text(cols[3] + 3, y0 + 4, f"วันที่ {datetime.date.today():%d/%m/%Y}", TXT_S)


def table(sh: Sheet, x, y_top, headers, rows, widths, h=6.0, size=TXT_S):
    """A table whose top-left corner is (x, y_top); returns the y under it."""
    W = sum(widths)
    y = y_top
    sh.rect(x, y - h, W, h, "FRAME")
    cx = x
    for head, w in zip(headers, widths):
        sh.text(cx + 1.2, y - h + 1.8, head, size)
        cx += w
        sh.line(cx, y, cx, y - h * (len(rows) + 1))
    y -= h
    for r in rows:
        sh.line(x, y - h, x + W, y - h)
        cx = x
        for v, w in zip(r, widths):
            sh.text(cx + 1.2, y - h + 1.8, v, size)
            cx += w
        y -= h
    sh.line(x, y_top, x, y)
    return y


def pick_scale(width_m, height_m, box_w, box_h, scales=SCALES):
    for s in scales:
        if width_m * 1000 / s <= box_w and height_m * 1000 / s <= box_h:
            return s
    return scales[-1]


# ---------------------------------------------------------------------------
# Laps, development, hooks
# ---------------------------------------------------------------------------

def development(mat, bar: str) -> dict:
    """Tension development and lap lengths (cm) for deformed bars by
    ACI 318 12.2.2 with ψt = 1.3 for top bars, class B lap 1.3 ld (12.15),
    compression lap 0.071 fy db (MPa) ≥ 30 cm (12.16) [EIT1008-DEV]."""
    db = BAR_DIA[bar]
    fy = FY[mat.main_grade] / MPA
    fc = mat.fc_usd / MPA
    k = 2.1 if db <= 2.0 else 1.7
    ld = max(30.0, fy / (k * math.sqrt(fc)) * db)
    ld_top = max(30.0, 1.3 * ld)
    up = lambda v: math.ceil(v / 5.0 - 1e-9) * 5.0
    return {"ld": up(ld), "ld_top": up(ld_top), "lap": up(max(30.0, 1.3 * ld)),
            "lap_top": up(max(30.0, 1.3 * ld_top)), "lap_c": up(max(30.0, 0.071 * fy * db)),
            "hook90": up(12 * db), "hook180": max(6.5, 4 * db)}


# ---------------------------------------------------------------------------
# Sheets
# ---------------------------------------------------------------------------

def notes_sheet(res) -> Sheet:
    b, mat = res.building, res.concrete
    sh = Sheet("S-01", "หมายเหตุทั่วไปและข้อกำหนด")
    x0, y0, x1, y1 = area()
    y = y1 - 2
    k = cover_factor(mat)

    def para(x, lines, size=TXT):
        nonlocal y
        for ln in lines:
            sh.text(x, y, ln, size)
            y -= size * 1.75
        y -= 2

    sh.text(x0, y, "1. กฎหมายและมาตรฐานที่ใช้", TXT)
    y -= 5
    laws = ["กฎกระทรวง กำหนดการออกแบบโครงสร้างอาคาร ... พ.ศ. 2566 (น้ำหนัก การรวมน้ำหนัก ตัวคูณลดกำลัง แรงลม)",
            "ประกาศกระทรวงมหาดไทย เรื่อง การออกแบบโครงสร้างอาคาร ... (2567) (หน่วยแรง ระยะหุ้ม ระยะแอ่นตัว)",
            "มาตรฐาน วสท. 1007 (หน่วยแรงใช้งาน) และ วสท. 1008 / ACI 318 (วิธีกำลัง)"]
    if res.seismic:
        laws.append("กฎกระทรวงแผ่นดินไหว พ.ศ. 2564 และ มยผ. 1301/1302-61")
    if b.roof.solar_load:
        laws.append("กฎกระทรวง ฉบับที่ 72 (2568) แผงโซลาร์เซลล์บนหลังคา")
    para(x0 + 4, [f"- {t}" for t in laws], TXT_S)
    sh.text(x0, y, "2. วัสดุ", TXT)
    y -= 5
    qc = "มี" if b.quality_control else "ไม่มี"
    para(x0 + 4, [f"- คอนกรีต fc' = {b.fc_prime:g} ksc (ทรงกระบอก 15×30 ซม. อายุ 28 วัน) หน่วยน้ำหนัก 2,400 กก./ลบ.ม.",
                  f"- เหล็กข้ออ้อย {mat.main_grade} (มอก. 24) fy = {FY[mat.main_grade]:,} ksc, "
                  f"เหล็กเส้นกลม {mat.tie_grade} (มอก. 20) fy = {FY[mat.tie_grade]:,} ksc",
                  f"- หน่วยแรงใช้งาน fc = {mat.fc:.1f} ksc, fs = {mat.fs('DB'):,.0f} ksc (ข้ออ้อย), "
                  f"{mat.fs('RB'):,.0f} ksc (เส้นกลม)",
                  f"- {qc}การระบุมาตรฐานงานก่อสร้างและการควบคุมคุณภาพวัสดุ (ประกาศ มท. 2567 ข้อ 3 (7), ข้อ 29)"], TXT_S)
    sh.text(x0, y, "3. ระยะหุ้มคอนกรีต (ประกาศ มท. 2567 ตาราง 13" + (", เพิ่ม 20%)" if k > 1 else ")"), TXT)
    y -= 4
    y = table(sh, x0 + 4, y, ["ชิ้นส่วน", "ระยะหุ้ม (มม.)"],
              [["ฐานรากที่หล่อติดดิน", f"{COVER_EARTH * k * 10:.0f}"],
               ["คานคอดิน เสาตอม่อ (สัมผัสดิน) เหล็ก ≤ 16 มม. / > 16 มม.",
                f"{COVER_EXPOSED * k * 10:.0f} / {COVER_EXPOSED_BIG * k * 10:.0f}"],
               ["คาน (เหล็กหลักและเหล็กปลอก)", f"{COVER_BEAM * k * 10:.0f}"],
               ["เสา (ถึงเหล็กปลอก) ใช้ค่าของส่วนสัมผัสดินทั้งต้น", f"{COVER_EXPOSED * k * 10:.0f} (≥ {COVER_COLUMN * 10:.0f})"],
               ["พื้น ผนัง", f"{COVER_SLAB * k * 10:.0f}"]], [110, 40], 5.5) - 4
    sh.text(x0, y, "4. ระยะฝัง ระยะทาบ และของอ (ACI 318 / วสท. 1008, ซม.)", TXT)
    y -= 4
    rows = []
    for bar in ("DB12", "DB16", "DB20", "DB25"):
        d = development(mat, bar)
        rows.append([bar, f"{d['ld']:.0f}", f"{d['ld_top']:.0f}", f"{d['lap']:.0f}", f"{d['lap_top']:.0f}",
                     f"{d['lap_c']:.0f}", f"{d['hook90']:.0f}", f"{d['hook180']:.1f}"])
    y = table(sh, x0 + 4, y, ["เหล็ก", "ระยะฝัง ld", "ld เหล็กบน", "ทาบรับดึง", "ทาบเหล็กบน", "ทาบรับอัด (เสา)",
                              "ขอ 90° ยื่น", "ขอ 180° ยื่น"], rows, [16, 20, 20, 20, 22, 26, 20, 20], 5.5) - 6
    para(x0 + 4, ["- เหล็กเส้นกลมผิวเรียบต้องงอขอที่ปลายทุกเส้น; เหล็กปลอกงอขอ 135° ยื่น 6db ไม่น้อยกว่า 7.5 ซม.",
                  "- ไม่ทาบเหล็กบนในช่วงกลางเสา-ปลายคาน และไม่ทาบเหล็กล่างที่หน้าเสา; ทาบเหล็กยืนเสาเหนือพื้นแต่ละชั้น",
                  "- ขนาดและระยะเหล็กปลอกเสาตามตาราง (ประกาศ มท. 2567 ข้อ 29 (11) (จ))"], TXT_S)
    # right column: loads, foundations, fire
    xr = (x0 + x1) / 2 + 20
    y = y1 - 2
    sh.text(xr, y, "5. น้ำหนักบรรทุก (กฎกระทรวง พ.ศ. 2566 ข้อ 11)", TXT)
    y -= 5
    lines = [f"- {lv.name}: น้ำหนักจร {lv.live_load:g} กก./ตร.ม., วัสดุปูผิว {lv.finish_load:g} กก./ตร.ม."
             for lv in b.levels if lv.slab in ("suspended", "precast")]
    lines.append(f"- หลังคา: น้ำหนักจร {b.roof.live_load:g} กก./ตร.ม." +
                 (f", แผงโซลาร์เซลล์ {b.roof.solar_load:g} กก./ตร.ม." if b.roof.solar_load else ""))
    if res.wind:
        w = res.wind
        lines.append(f"- แรงลม (ข้อ 17): {', '.join(f'{t} {q:g}' for t, q in w.pressures)} กก./ตร.ม.")
    if res.seismic:
        q = res.seismic
        lines.append(f"- แผ่นดินไหว: SDS {q.sds:.3f} g, SD1 {q.sd1:.3f} g, ประเภท {q.category}, V = {q.base_shear:,.0f} กก.")
    lines.append(f"- การรวมน้ำหนักตามกฎกระทรวง พ.ศ. 2566 ข้อ 6–7, ตัวคูณลดกำลังตามข้อ 8")
    y_save = y
    for ln in lines:
        sh.text(xr + 4, y, ln, TXT_S)
        y -= 3.6
    y -= 3
    f = b.foundation
    sh.text(xr, y, "6. ฐานราก", TXT)
    y -= 5
    found = [f"- เสาเข็ม {f.pile} ยาว {f.pile_length:g} ม. รับน้ำหนักปลอดภัยตามตารางในโปรแกรม" if f.kind == "pile"
             else f"- ฐานแผ่บนดินรับน้ำหนักได้ {f.soil_qa:,.0f} กก./ตร.ม.",
             "- ต้องยืนยันด้วยผลเจาะสำรวจดินและทดสอบเสาเข็มของโครงการ",
             f"- ระดับใต้ฐานราก −{f.depth:.2f} ม. จากระดับพื้นดิน"]
    for ln in found:
        sh.text(xr + 4, y, ln, TXT_S)
        y -= 3.6
    y -= 3
    if res.fire and (res.fire.applies or res.fire.notes):
        sh.text(xr, y, "7. การทนไฟ (กฎกระทรวง พ.ศ. 2566 ข้อ 21–24)", TXT)
        y -= 5
        fl = [f"- {n}: เสา คาน {h:g} ชม. พื้น {s:g} ชม." for n, h, s in res.fire.floors] or ["- ไม่บังคับ"]
        for ln in fl:
            sh.text(xr + 4, y, ln, TXT_S)
            y -= 3.6
    _ = y_save
    return sh


def _grid(sh, b, ox, oy, s, ext=6.0):
    """Grid lines with bubbles and dimensions; s = paper mm per metre."""
    xs, ys = b.xs, b.ys
    for i, x in enumerate(xs):
        X = ox + x * s
        sh.line(X, oy - ext, X, oy + ys[-1] * s + ext, "GRID", True)
        sh.circle(X, oy + ys[-1] * s + ext + 3.5, 3.5, "GRID")
        sh.text(X, oy + ys[-1] * s + ext + 2.6, b.x_name(i), TXT, "GRID", "center")
    for j, y in enumerate(ys):
        Y = oy + y * s
        sh.line(ox - ext, Y, ox + xs[-1] * s + ext, Y, "GRID", True)
        sh.circle(ox - ext - 3.5, Y, 3.5, "GRID")
        sh.text(ox - ext - 3.5, Y - 0.9, b.y_name(j), TXT, "GRID", "center")
    yd = oy - ext - 4
    for a, c in zip(xs, xs[1:]):
        sh.line(ox + a * s, yd, ox + c * s, yd, "DIM")
        sh.text(ox + (a + c) / 2 * s, yd + 1, f"{(c - a):.2f}", TXT_S, "DIM", "center")
    xd = ox + xs[-1] * s + ext + 4
    for a, c in zip(ys, ys[1:]):
        sh.line(xd, oy + a * s, xd, oy + c * s, "DIM")
        sh.text(xd + 1, oy + (a + c) / 2 * s, f"{(c - a):.2f}", TXT_S, "DIM")


def plan_sheets(res, start: int) -> list[Sheet]:
    b = res.building
    out = []
    x0, y0, x1, y1 = area()
    for k, lv in enumerate(b.levels):
        sh = Sheet(f"S-{start + k:02d}", f"แปลนโครงสร้าง {lv.name} (+{lv.elevation:.2f})")
        s_ = pick_scale(b.xs[-1] + 4, b.ys[-1] + 4, x1 - x0 - 30, y1 - y0 - 30)
        s = 1000 / s_
        sh.scale = f"1:{s_}"
        ox = x0 + (x1 - x0 - b.xs[-1] * s) / 2
        oy = y0 + (y1 - y0 - b.ys[-1] * s) / 2
        _grid(sh, b, ox, oy, s)
        for x in res.beams:
            if x.level != lv.name or not x.line_xy:
                continue
            a0, b0, a1, b1 = x.line_xy
            hw = x.b / 2 * s
            P0, P1 = (ox + a0 * s, oy + b0 * s), (ox + a1 * s, oy + b1 * s)
            if abs(b1 - b0) < 1e-9:
                sh.line(P0[0], P0[1] - hw, P1[0], P1[1] - hw, "BEAM", x.kind == "secondary")
                sh.line(P0[0], P0[1] + hw, P1[0], P1[1] + hw, "BEAM", x.kind == "secondary")
                sh.text((P0[0] + P1[0]) / 2, P0[1] + hw + 1, f"{x.mark}", TXT_S, "BEAM", "center")
            else:
                sh.line(P0[0] - hw, P0[1], P1[0] - hw, P1[1], "BEAM", x.kind == "secondary")
                sh.line(P0[0] + hw, P0[1], P1[0] + hw, P1[1], "BEAM", x.kind == "secondary")
                sh.text(P0[0] + hw + 1, (P0[1] + P1[1]) / 2, f"{x.mark}", TXT_S, "BEAM")
        from .architecture import openings_on
        segs = [((i, j), (i + 1, j)) for j in range(len(b.ys)) for i in range(len(b.xs) - 1)] + \
               [((i, j), (i, j + 1)) for i in range(len(b.xs)) for j in range(len(b.ys) - 1)]
        for a, c in segs:
            if not (b.has_node(*a) and b.has_node(*c)):
                continue
            ops = openings_on(b, lv, a, c)
            if ops:
                X = ox + (b.xs[a[0]] + b.xs[c[0]]) / 2 * s
                Y = oy + (b.ys[a[1]] + b.ys[c[1]]) / 2 * s
                sh.text(X + (0 if a[1] == c[1] else 3), Y + (-5 if a[1] == c[1] else 0), " ".join(ops), TXT_S,
                        "DIM", "center")
        for bay in lv.wet_bays:
            xpart, ypart = bay.split("/")
            i, j = int(xpart.split("-")[0]) - 1, ord(ypart.split("-")[0]) - ord("A")
            sh.text(ox + (b.xs[i] + b.xs[i + 1]) / 2 * s, oy + (b.ys[j] + b.ys[j + 1]) / 2 * s - 5, "ห้องน้ำ",
                    TXT_S, "SLAB", "center")
        for sl in res.slabs:
            if sl.level != lv.name or not sl.rect:
                continue
            a0, b0, a1, b1 = sl.rect
            if sl.kind == "cantilever":
                sh.rect(ox + a0 * s, oy + b0 * s, (a1 - a0) * s, (b1 - b0) * s, "SLAB")
            sh.text(ox + (a0 + a1) / 2 * s, oy + (b0 + b1) / 2 * s, f"{sl.mark} t={sl.thickness * 100:.0f}",
                    TXT_S, "SLAB", "center")
        for c in res.columns:
            if not c.segment.endswith(lv.name) and not (lv is b.levels[0] and c.segment.startswith("ฐานราก")):
                continue
            i, j = b.parse_node(c.node)
            X, Y = ox + b.xs[i] * s, oy + b.ys[j] * s
            sh.rect(X - c.b * s / 2, Y - c.h * s / 2, c.b * s, c.h * s, "COLUMN", True)
            sh.text(X + c.b * s / 2 + 0.8, Y + c.h * s / 2 + 0.6, c.mark, TXT_S, "COLUMN")
        for st in res.stairs:
            if st.geom is None or lv.name not in (st.level, b.levels[st.geom.li1].name):
                continue
            from .stairs import tread_lines
            for pa, pc in tread_lines(b, st.geom):
                sh.line(ox + pa[0] * s, oy + pa[1] * s, ox + pc[0] * s, oy + pc[1] * s, "SLAB")
            g = st.geom
            sh.text(ox + (b.xs[g.i] + b.xs[g.i + 1]) / 2 * s, oy + (b.ys[g.j] + b.ys[g.j + 1]) / 2 * s,
                    f"{st.mark} {'ขึ้น' if lv.name == st.level else 'ลง'}", TXT_S, "SLAB", "center")
        out.append(sh)
    return out


def foundation_sheet(res, number: str) -> Sheet:
    b = res.building
    sh = Sheet(number, "แปลนฐานรากและเสาเข็ม")
    x0, y0, x1, y1 = area()
    s_ = pick_scale(b.xs[-1] + 4, b.ys[-1] + 4, x1 - x0 - 30, y1 - y0 - 30)
    s = 1000 / s_
    sh.scale = f"1:{s_}"
    ox = x0 + (x1 - x0 - b.xs[-1] * s) / 2
    oy = y0 + (y1 - y0 - b.ys[-1] * s) / 2
    _grid(sh, b, ox, oy, s)
    from .sections import load_piles
    piles = load_piles()
    for f in res.footings:
        cx, cy = f.center(b)
        X, Y = ox + cx * s, oy + cy * s
        sh.rect(X - f.width * s / 2, Y - f.length * s / 2, f.width * s, f.length * s, "FOOTING")
        if f.piles and f.pile in piles:
            from .seismic import _pile_points
            size = piles[f.pile]["size_m"]
            pts = _pile_points(f.piles, size) if f.kind != "combined" else []
            for px, py in pts:
                sh.circle(X + px * s, Y + py * s, max(0.6, size / 2 * s), "FOOTING")
        sh.text(X, Y - f.length * s / 2 - 3, f.mark, TXT_S, "FOOTING", "center")
    for c in res.columns:
        if not c.segment.startswith("ฐานราก"):
            continue
        i, j = b.parse_node(c.node)
        X, Y = ox + b.xs[i] * s, oy + b.ys[j] * s
        sh.rect(X - c.b * s / 2, Y - c.h * s / 2, c.b * s, c.h * s, "COLUMN", True)
    return sh


def _bar_dots(sh, x, y, w, n, r, layer="BAR"):
    if n <= 1:
        sh.circle(x + w / 2, y, r, layer, True)
        return
    for k in range(n):
        sh.circle(x + w * k / (n - 1), y, r, layer, True)


def beam_section(sh, x, y, beam, s):
    """Section of a beam with its bottom-left corner at (x, y); s = mm per metre."""
    w, h = beam.b * s, beam.h * s
    sh.rect(x, y, w, h, "BEAM")
    cov = (beam.d_off - 0.6 - 0.8) / 100 * s
    sh.rect(x + cov, y + cov, w - 2 * cov, h - 2 * cov, "BAR")
    nt, st = beam.top.split("-")
    nb, sb = beam.bottom.split("-")
    r_t, r_b = BAR_DIA[st] / 200 * s, BAR_DIA[sb] / 200 * s
    inset = cov + 0.6 / 100 * s
    _bar_dots(sh, x + inset + r_t, y + h - inset - r_t, w - 2 * (inset + r_t), int(nt), r_t)
    _bar_dots(sh, x + inset + r_b, y + inset + r_b, w - 2 * (inset + r_b), int(nb), r_b)


def column_section(sh, x, y, col, s):
    w, h = col.b * s, col.h * s
    sh.rect(x, y, w, h, "COLUMN")
    from . import seismic
    cov = seismic.COVER / 100 * s
    sh.rect(x + cov, y + cov, w - 2 * cov, h - 2 * cov, "BAR")
    n, size = col.bars.split("-")
    n = int(n)
    r = BAR_DIA[size] / 200 * s
    inset = cov + BAR_DIA[tie_bar(size)] / 100 * s + r
    per_face = 2 + (n - 4) // 4
    left = (n - 4) % 4
    xs = [x + inset + (w - 2 * inset) * k / (per_face - 1) for k in range(per_face)]
    for X in xs:
        sh.circle(X, y + inset, r, "BAR", True)
        sh.circle(X, y + h - inset, r, "BAR", True)
    side = per_face - 2 + (1 if left else 0)
    for k in range(1, side + 1):
        Y = y + inset + (h - 2 * inset) * k / (side + 1)
        sh.circle(x + inset, Y, r, "BAR", True)
        sh.circle(x + w - inset, Y, r, "BAR", True)


def footing_drawing(sh, x, y, f, col, s, piles):
    """Plan of a single footing with piles; (x, y) its centre."""
    sh.rect(x - f.width * s / 2, y - f.length * s / 2, f.width * s, f.length * s, "FOOTING")
    if col is not None:
        sh.rect(x - col.b * s / 2, y - col.h * s / 2, col.b * s, col.h * s, "COLUMN", True)
    if f.piles and f.pile in piles and f.kind != "combined":
        from .seismic import _pile_points
        size = piles[f.pile]["size_m"]
        for px, py in _pile_points(f.piles, size):
            sh.circle(x + px * s, y + py * s, size / 2 * s, "FOOTING")


def _natural(mark: str):
    head = mark.rstrip("0123456789")
    tail = mark[len(head):]
    return head, int(tail) if tail else 0


def footing_section(sh, x, y, f, col, s, piles):
    """Section through a footing; (x, y) the centre of its underside."""
    w, t = f.width * s, f.thickness * s
    sh.rect(x - w / 2, y, w, t, "FOOTING")
    if col is not None:
        sh.rect(x - col.b * s / 2, y + t, col.b * s, 0.25 * s, "COLUMN")
    cov = 0.075 * s
    sh.line(x - w / 2 + cov, y + cov, x + w / 2 - cov, y + cov, "BAR")
    if f.piles and f.pile in piles and f.kind != "combined":
        from .seismic import _pile_points
        size = piles[f.pile]["size_m"] * s
        for px in sorted({round(p[0], 3) for p in _pile_points(f.piles, piles[f.pile]["size_m"])}):
            sh.rect(x + px * s - size / 2, y - 0.4 * s, size, 0.4 * s, "FOOTING")
    sh.text(x + w / 2 + 2, y + t / 2, f"หนา {f.thickness:.2f}", TXT_S)


def schedule_sheets(res, start: int) -> list[Sheet]:
    out = []
    x0, y0, x1, y1 = area()
    from .sections import load_piles
    piles = load_piles()
    n = start

    # --- footings ---------------------------------------------------------
    sh = Sheet(f"S-{n:02d}", "ตารางฐานรากและเสา", "1:25, 1:10")
    groups = {}
    for f in res.footings:
        groups.setdefault(f.mark, f)
    base = {c.node: c for c in res.columns if c.segment.startswith("ฐานราก")}
    rows = [[m, f"{f.width:.2f}×{f.length:.2f}×{f.thickness:.2f}", f"{f.piles} × {f.pile}" if f.piles else "-",
             f.bars_x, f.bars_y, str(sum(1 for g in res.footings if g.mark == m))]
            for m, f in sorted(groups.items())]
    sh.text(x0, y1 - 2, "ตารางฐานราก (ระยะหุ้ม 75 มม.)", TXT)
    yb = table(sh, x0, y1 - 6, ["Mark", "กว้าง×ยาว×หนา (ม.)", "เสาเข็ม", "เหล็ก X", "เหล็ก Y", "จำนวน"],
               rows, [14, 36, 26, 20, 20, 14])
    s = 1000 / 25
    xx = x0 + 10
    for m, f in sorted(groups.items(), key=lambda kv: _natural(kv[0])):
        node = (f.nodes or [f.node])[0]
        w, ln = f.width * s, f.length * s
        if xx + w > x0 + 170:
            break
        footing_drawing(sh, xx + w / 2, yb - 8 - ln / 2, f, base.get(node), s, piles)
        sh.text(xx + w / 2, yb - 13 - ln, f"{m} แปลน", TXT_S, "TEXT", "center")
        footing_section(sh, xx + w / 2, yb - 50 - ln, f, base.get(node), s, piles)
        sh.text(xx + w / 2, yb - 50 - ln - 0.4 * s - 5, f"{m} รูปตัด", TXT_S, "TEXT", "center")
        xx += w + 30
    # columns on the right half
    cols = {}
    for c in res.columns:
        cols.setdefault(c.mark, c)
    xr = x0 + 190
    sh.text(xr, y1 - 2, "ตารางเสา (ระยะหุ้มถึงเหล็กปลอก "
            f"{__import__('wanicndesign.structure.seismic', fromlist=['COVER']).COVER * 10:.0f} มม.)", TXT)
    rows = [[m, f"{c.b:.2f}×{c.h:.2f}", c.bars, c.ties, ", ".join(sorted({x.segment for x in res.columns
                                                                         if x.mark == m}))[:34]]
            for m, c in sorted(cols.items(), key=lambda kv: _natural(kv[0]))]
    yc = table(sh, xr, y1 - 6, ["Mark", "ขนาด (ม.)", "เหล็กยืน", "เหล็กปลอก", "ช่วงเสา"], rows, [14, 22, 20, 22, 92])
    s = 1000 / 10
    xx = xr + 6
    for m, c in sorted(cols.items()):
        if xx + c.b * s > x1 - 5:
            break
        column_section(sh, xx, yc - 10 - c.h * s, c, s)
        sh.text(xx + c.b * s / 2, yc - 15 - c.h * s, f"{m} {c.bars}", TXT_S, "TEXT", "center")
        sh.text(xx + c.b * s / 2, yc - 19 - c.h * s, c.ties, TXT_S, "TEXT", "center")
        xx += c.b * s + 22
    if res.seismic:
        det = sorted({ch.detail for ch in res.seismic.checks if ch.kind == "column" and ch.detail})
        yy = yc - 60
        for d in det[:4]:
            sh.text(xr, yy, f"แผ่นดินไหว: {d}", TXT_S)
            yy -= 3.6
    out.append(sh)
    n += 1

    # --- beams ------------------------------------------------------------
    beams = {}
    for x in res.beams:
        beams.setdefault((x.level, x.mark), x)
    li = {lv.name: k for k, lv in enumerate(res.building.levels)}
    items = sorted(beams.items(), key=lambda kv: (-li.get(kv[0][0], 0), _natural(kv[0][1])))
    per_sheet = 18
    for p in range(0, len(items), per_sheet):
        chunk = items[p:p + per_sheet]
        sh = Sheet(f"S-{n:02d}", "ตารางคานและรูปตัด", "1:10")
        sh.text(x0, y1 - 2, "ตารางคาน (เหล็กบนต่อเนื่องตลอดช่วง ทาบนอกบริเวณปลายคาน)", TXT)
        rows = [[f"{lvl}", m, f"{x.b:.2f}×{x.h:.2f}", x.top, x.bottom, x.stirrup,
                 str(sum(1 for y in res.beams if (y.level, y.mark) == (lvl, m)))]
                for (lvl, m), x in chunk]
        yt = table(sh, x0, y1 - 6, ["ชั้น", "Mark", "b×h (ม.)", "เหล็กบน", "เหล็กล่าง", "เหล็กปลอก", "จำนวนช่วง"],
                   rows, [14, 14, 24, 20, 20, 24, 18])
        s = 1000 / 10
        xx, yy = x0 + 175, y1 - 10
        row_h = 0.0
        for (lvl, m), x in chunk:
            w, h = x.b * s, x.h * s
            if xx + w > x1 - 5:
                xx = x0 + 175
                yy -= row_h + 18
                row_h = 0.0
            if yy - h < y0 + 5:
                break
            beam_section(sh, xx, yy - h, x, s)
            sh.text(xx + w / 2, yy - h - 4, f"{lvl} {m}", TXT_S, "TEXT", "center")
            sh.text(xx + w / 2, yy - h - 7.5, x.stirrup, TXT_S, "TEXT", "center")
            xx += w + 16
            row_h = max(row_h, h)
        _ = yt
        out.append(sh)
        n += 1

    # --- slabs and stairs ---------------------------------------------------
    sh = Sheet(f"S-{n:02d}", "ตารางพื้นและบันได")
    b_ = res.building
    used: dict = {}
    for lv in b_.levels:
        for e in lv.openings:
            used[e.split(":", 1)[1]] = used.get(e.split(":", 1)[1], 0) + 1
    if used:
        rows = [[o.name, "ประตู" if o.kind == "door" else "หน้าต่าง", f"{o.width:.2f}×{o.height:.2f}",
                 "ไม้" if o.material == "wood" else "อลูมิเนียม", str(used[o.name])]
                for o in b_.opening_types if o.name in used]
        sh.text(x0 + 230, y1 - 90, "ตารางประตู หน้าต่าง", TXT)
        table(sh, x0 + 230, y1 - 94, ["ชื่อ", "ชนิด", "กว้าง×สูง (ม.)", "วัสดุ", "จำนวน"], rows, [14, 20, 28, 26, 16])
    slabs = {}
    for sl in res.slabs:
        slabs.setdefault(sl.mark, sl)
    rows = [[m, sl.kind, f"{sl.thickness * 100:.0f}", sl.bars_short, sl.bars_long, sl.bars_top,
             str(sum(1 for t in res.slabs if t.mark == m))] for m, sl in sorted(slabs.items(),
                                                                                key=lambda kv: _natural(kv[0]))]
    sh.text(x0, y1 - 2, "ตารางพื้น (ระยะหุ้ม 20 มม.; เหล็กบนยื่นจากขอบคาน L/4 ของช่วงสั้น)", TXT)
    y = table(sh, x0, y1 - 6, ["Mark", "ชนิด", "หนา (ซม.)", "เหล็กล่างช่วงสั้น", "เหล็กล่างช่วงยาว", "เหล็กบน",
                               "จำนวน"], rows, [16, 30, 18, 32, 32, 26, 16])
    slab_detail(sh, x0 + 230, y1 - 30)
    if res.stairs:
        stair_section(sh, res, x0 + 10, y - 115)
        sh.text(x0, y - 8, "ตารางบันได", TXT)
        rows = [[st.mark, st.level, st.panel, f"{st.risers}×{st.riser * 100:.1f}/{st.tread * 100:.0f}",
                 f"{st.thickness * 100:.0f}", st.bars_main, st.bars_top, st.bars_temp] for st in res.stairs]
        table(sh, x0, y - 12, ["Mark", "จากชั้น", "ช่อง", "ลูกตั้ง×สูง/ลูกนอน (ซม.)", "หนา (ซม.)", "เหล็กหลัก",
                               "เหล็กบน", "เหล็กกันร้าว"], rows, [14, 16, 22, 40, 18, 26, 26, 26])
    out.append(sh)
    return out


def slab_detail(sh, x, y):
    """Typical slab between two beams (not to scale): bottom bars over the span,
    top bars over the beams reaching L/4 of the short span into the slab."""
    L, t, bw, hb = 120.0, 10.0, 12.0, 30.0
    sh.text(x, y + 12, "รายละเอียดพื้นทั่วไป (ไม่ตามมาตราส่วน)", TXT)
    sh.rect(x, y - hb, bw, hb, "BEAM")
    sh.rect(x + bw + L, y - hb, bw, hb, "BEAM")
    sh.rect(x + bw, y - t, L, t, "SLAB")
    sh.line(x + 4, y - t + 2, x + 2 * bw + L - 4, y - t + 2, "BAR")
    for xa, xb in ((x + 2, x + bw + L / 4), (x + bw + 3 * L / 4, x + 2 * bw + L - 2)):
        sh.line(xa, y - 2, xb, y - 2, "BAR")
        sh.line(xb, y - 2, xb, y - 5, "BAR")
    sh.text(x + bw + L / 8, y + 2, "L/4", TXT_S, "DIM", "center")
    sh.text(x + bw + 7 * L / 8, y + 2, "L/4", TXT_S, "DIM", "center")
    sh.text(x + bw + L / 2, y - t - 5, "เหล็กล่างต่อเนื่อง ทาบที่หัวคาน; ระยะหุ้ม 20 มม.", TXT_S, "TEXT", "center")


def stair_section(sh, res, x, y):
    """Section along the first stair (scale 1:50): flights, landing, BT."""
    st = next((t for t in res.stairs if t.geom is not None), None)
    if st is None:
        return
    g = st.geom
    s = 1000 / 50
    sh.text(x, y + (g.z1 - g.z0) * s + 8, f"รูปตัดบันได {st.mark} (1:50)", TXT)
    for k, f in enumerate(g.flights):
        going = min(f.going, g.length)
        za, zb = (f.z_from, f.z_to) if not (st.kind == "landing" and k == 1) else (f.z_to, f.z_from)
        pts = [(x, y + (za - g.z0) * s)]
        for t in range(f.risers - 1 if going else 0):
            ux = x + t * g.tread * s
            zz = y + (za - g.z0 + (zb - za) * (t + 1) / f.risers) * s
            pts += [(ux, zz), (ux + g.tread * s, zz)]
        pts.append((x + going * s, y + (zb - g.z0) * s))                 # last riser
        pts.append((x + g.length * s, y + (zb - g.z0) * s))              # landing / upper floor
        sh.poly(pts, "SLAB" if k == 0 else "GRID", closed=False)
    if g.landing_z is not None:
        zl = y + (g.landing_z - g.z0) * s
        sh.rect(x + g.length * s - 0.2 * s, zl - 0.4 * s, 0.2 * s, 0.4 * s, "BEAM")
        sh.text(x + g.length * s + 2, zl - 3, "BT", TXT_S, "BEAM")
    sh.line(x - 5, y, x + g.length * s + 10, y, "GRID")
    sh.line(x - 5, y + (g.z1 - g.z0) * s, x + g.length * s + 10, y + (g.z1 - g.z0) * s, "GRID")
    sh.text(x + g.length * s / 2, y - 6, f"ช่วง {g.length:.2f} ม., หนา {st.thickness * 100:.0f} ซม., "
            f"ลูกตั้ง {g.riser * 100:.1f} ซม., ลูกนอน {g.tread * 100:.0f} ซม.", TXT_S, "TEXT", "center")


def beam_elevation_sheets(res, start: int) -> list[Sheet]:
    """Elevation of every primary beam line at 1:50: supports, top bars with
    their hooks and laps, bottom bars per span lapped over interior
    supports, stirrup spacing and end zones [EIT1008-DEV], [EIT1008-HOOK]."""
    from .cutting import _pieces, _stirrup_count, beam_runs, parse_count
    out = []
    x0, y0, x1, y1 = area()
    runs = list(beam_runs(res).items())
    longest = max((sum(sp.length for sp in spans) for _k, spans in runs), default=1.0)
    scale = pick_scale(longest + 1.0, 1.0, x1 - x0 - 40, 999, [25, 50, 75, 100, 125, 150, 200])
    s = 1000 / scale
    band = 36.0
    per = max(1, int((y1 - y0 - 6) // band))
    n = start
    for p in range(0, len(runs), per):
        sh = Sheet(f"S-{n:02d}", "รูปด้านคานและการต่อเหล็ก", f"1:{scale}")
        y = y1 - 8
        for (key, _i), spans in runs[p:p + per]:
            level, axis, _c = key
            h = max(sp.h for sp in spans) * s
            ox = x0 + 18
            base = y - h - 6
            sh.text(x0, y, f"{level} แนว {spans[0].line}: " + " / ".join(dict.fromkeys(sp.mark for sp in spans)), TXT)
            pos = ox
            supports = [pos]
            for sp in spans:
                pos += sp.length * s
                supports.append(pos)
            sh.line(ox, base + h, pos, base + h, "BEAM")
            sh.line(ox, base, pos, base, "BEAM")
            for k_, X in enumerate(supports):
                node = spans[0].span.split("-")[0] if k_ == 0 else spans[k_ - 1].span.split("-")[1]
                w = 0.2 * s
                for c in res.columns:
                    if c.node == node and c.segment.endswith(level):
                        w = (c.b if axis == "x" else c.h) * s
                sh.rect(X - w / 2, base - 4, w, h + 8, "COLUMN")
                sh.text(X, base - 8.5, node, TXT_S, "GRID", "center")
            cov = 1.5
            nt, st, _ = parse_count(max(spans, key=lambda q: _area_spec(q.top)).top)
            d = development(res.concrete, st)
            L = (pos - ox) / s
            npc, _piece = _pieces(L + 0.4, d["lap_top"] / 100)
            yt = base + h - cov
            sh.line(ox - 2, yt, pos + 2, yt, "BAR")
            for X in (ox - 2, pos + 2):
                sh.line(X, yt, X, yt - min(h - 2 * cov, 12 * BAR_DIA[st] / 100 * s), "BAR")
            if npc > 1:
                mid = spans[len(spans) // 2]
                xm = supports[len(spans) // 2] + mid.length * s / 2
                lap = d["lap_top"] / 100 * s
                sh.line(xm - lap / 2, yt - 0.8, xm + lap / 2, yt - 0.8, "BAR")
                sh.text(xm + lap / 2 + 1, base + h / 2 - 1, f"ทาบเหล็กบน {d['lap_top']:.0f} ซม.", TXT_S, "BAR")
            sh.text(ox - 16, yt - 1, f"{nt}-{st}", TXT_S, "BAR")
            for k_, sp in enumerate(spans):
                nb, sb, _ = parse_count(sp.bottom)
                db = development(res.concrete, sb)
                lap = db["lap"] / 100 * s
                a = supports[k_] - (2 if k_ == 0 else lap / 2)
                b_ = supports[k_ + 1] + (2 if k_ == len(spans) - 1 else lap / 2)
                yb = base + cov + (0.8 if k_ % 2 else 0)
                sh.line(a, yb, b_, yb, "BAR")
                if k_ == 0:
                    sh.line(a, yb, a, yb + min(h - 2 * cov, 12 * BAR_DIA[sb] / 100 * s), "BAR")
                if k_ == len(spans) - 1:
                    sh.line(b_, yb, b_, yb + min(h - 2 * cov, 12 * BAR_DIA[sb] / 100 * s), "BAR")
                xm = (supports[k_] + supports[k_ + 1]) / 2
                _, ss, sps = parse_count(sp.stirrup)
                count = _stirrup_count(res, sp, sp.length - 0.2, sps)
                ticks = min(count, 40)
                for t in range(ticks):
                    X = supports[k_] + 2 + (supports[k_ + 1] - supports[k_] - 4) * t / max(1, ticks - 1)
                    sh.line(X, base + 0.6, X, base + h - 0.6, "GRID")
                sh.text(xm, base + h + 1.5, f"{sp.mark} {sp.b:.2f}×{sp.h:.2f} ยาว {sp.length:.2f}", TXT_S, "BEAM",
                        "center")
                sh.text(xm, base - 5, f"ล่าง {nb}-{sb} ทาบ {db['lap']:.0f} · {ss}@{sps:g} ({count})", TXT_S, "TEXT",
                        "center")
            y -= band
        out.append(sh)
        n += 1
    return out


def _area_spec(spec: str) -> float:
    from .sections import bar_area
    n_, size = spec.split("-", 1)
    return int(n_) * bar_area(size)


def column_elevation_sheet(res, number: str) -> Sheet:
    """Column stacks of each distinct arrangement at 1:50: footing, floors,
    laps above each floor, tie spacing and the end zones."""
    b = res.building
    sh = Sheet(number, "รูปด้านเสาและการต่อเหล็ก", "1:50")
    x0, y0, x1, y1 = area()
    s = 1000 / 50
    names = [lv.name for lv in b.levels]
    stacks: dict = {}
    for c in res.columns:
        stacks.setdefault(c.node, []).append(c)
    kinds: dict = {}
    for node, segs in stacks.items():
        segs = sorted(segs, key=lambda c: (0 if c.segment.startswith("ฐานราก") else
                                             1 + names.index(c.segment.split("–")[1])))
        sig = tuple((c.mark, c.bars, c.ties) for c in segs)
        kinds.setdefault(sig, (segs, []))[1].append(node)
    zbase = b.levels[0].elevation - (b.foundation.depth - 0.40 + b.levels[0].elevation)
    top = b.levels[-1].elevation
    oy = y0 + 18
    ox = x0 + 30
    for lv in b.levels:
        Y = oy + (lv.elevation - zbase) * s
        sh.line(x0 + 5, Y, x1 - 5, Y, "GRID", True)
        sh.text(x0 + 2, Y + 1, f"{lv.name} +{lv.elevation:.2f}", TXT_S, "GRID")
    for segs, nodes in kinds.values():
        if ox > x1 - 40:
            break
        w = max(c.b for c in segs) * s
        sh.rect(ox - 0.6 * s / 2, oy - 0.4 * s, 0.6 * s, 0.4 * s, "FOOTING")
        z = zbase
        for c in segs:
            ztop = z + c.height
            Y0, Y1 = oy + (z - zbase) * s, oy + (ztop - zbase) * s
            sh.rect(ox - c.b * s / 2, Y0, c.b * s, Y1 - Y0, "COLUMN")
            size = c.bars.split("-")[1]
            d = development(res.concrete, size)
            if c is not segs[-1]:
                lap = d["lap"] / 100 * s
                sh.line(ox + c.b * s / 2 - 1.2, Y1, ox + c.b * s / 2 - 1.2, Y1 + lap, "BAR")
                sh.text(ox + c.b * s / 2 + 1.5, Y1 + lap / 2, f"ทาบ {d['lap']:.0f}", TXT_S, "BAR")
            sh.line(ox - c.b * s / 2 + 1.2, Y0, ox - c.b * s / 2 + 1.2, Y1, "BAR")
            sh.text(ox - c.b * s / 2 - 2, (Y0 + Y1) / 2, f"{c.mark} {c.bars}", TXT_S, "COLUMN", "right_hint")
            sh.text(ox - c.b * s / 2 - 2, (Y0 + Y1) / 2 - 3.5, c.ties, TXT_S, "TEXT", "right_hint")
            z = ztop
        sh.text(ox, oy - 0.4 * s - 5, ", ".join(nodes), TXT_S, "TEXT", "center")
        ox += max(w, 10) + 48
    _ = top
    return sh


def truss_sheet(res, number: str) -> Sheet:
    """Elevation of each truss type with its members and forces."""
    sh = Sheet(number, "โครงถักหลังคาเหล็ก")
    x0, y0, x1, y1 = area()
    kinds: dict = {}
    for t in res.trusses:
        kinds.setdefault(t.mark, t)
    span = max(t.span for t in kinds.values())
    scale = pick_scale(span + 1, 3, x1 - x0 - 40, (y1 - y0) / max(1, len(kinds)) - 30, [25, 50, 75, 100])
    s = 1000 / scale
    sh.scale = f"1:{scale}"
    y = y1 - 10
    for mark, t in sorted(kinds.items()):
        lines = ", ".join(x.line for x in res.trusses if x.mark == mark)
        sh.text(x0, y, f"{mark} (แนว {lines}) ช่วง {t.span:.2f} ม. สูงที่ฐาน {t.depth:.2f} ม.: บน {t.sections['top'].name} "
                f"ล่าง {t.sections['bottom'].name} ค้ำ {t.sections['web'].name}", TXT)
        top = max(z for _x, z in t.nodes)
        base = y - 8 - top * s
        ox = x0 + 20
        for m in t.members:
            (a, za), (e, ze) = t.nodes[m.i], t.nodes[m.j]
            sh.line(ox + a * s, base + za * s, ox + e * s, base + ze * s,
                    {"top": "BEAM", "bottom": "BEAM", "web": "FRAME"}[m.group])
            if m.group == "web" and abs(m.force) > 1:
                sh.text(ox + (a + e) / 2 * s + 1, base + (za + ze) / 2 * s, f"{m.force / 1000:+.2f}", 1.6, "DIM")
        for k in (0, t.panels):
            sh.poly([(ox + t.nodes[k][0] * s, base), (ox + t.nodes[k][0] * s - 2, base - 3),
                     (ox + t.nodes[k][0] * s + 2, base - 3)], "FRAME")
        sh.text(ox, base - 7, f"แรง (ตัน) + ดึง − อัด · ปฏิกิริยา {t.reaction:,.0f} กก.", TXT_S)
        for k_, part in enumerate(t.note.split(" ; ")[:3]):
            sh.text(ox + t.span * s + 8, y - 22 - 4 * k_, part, TXT_S)
        weld = ", ".join(f"{g} เชื่อมรอบ ขา {max(3, t.sections[g].t):g} มม." for g in ("top", "bottom", "web"))
        sh.text(ox + t.span * s + 8, y - 6, f"ฐานรองรับ: {t.seat['plate']} สลัก {t.seat['bolts']} ฝังในหัวเสา", TXT_S)
        sh.text(ox + t.span * s + 8, y - 10, f"ถอน {t.seat['tension']:,.0f} กก. / รับได้ {t.seat['bolt_cap']:,.0f} กก.",
                TXT_S)
        sh.text(ox + t.span * s + 8, y - 14, weld.replace("top", "บน").replace("bottom", "ล่าง").replace("web", "ค้ำ"),
                TXT_S)
        y = min(base - 16, y - 40)
    sh.text(x0, y0 + 4, "เหล็กท่อสี่เหลี่ยม มอก. 107 Fy ≤ 2,400 ksc (ประกาศ มท. 2567 ข้อ 27) · รอยเชื่อมเต็มรอบ "
            "ไม่น้อยกว่าความหนาท่อ · ทาสีกันสนิม", TXT_S)
    return sh


def cutting_sheet(res, number: str) -> Sheet:
    from ..rates import Rates
    from .cutting import cutting_list, stock_plan
    sh = Sheet(number, "สรุปตารางตัดเหล็ก")
    x0, y0, x1, y1 = area()
    items = cutting_list(res)
    plans = stock_plan(items)
    rates = Rates()
    sh.text(x0, y1 - 2, "สรุปการตัดจากเหล็กเส้นยาว 10 ม. (รายละเอียดทุกท่อนในไฟล์ ตารางตัดเหล็ก.xlsx)", TXT)
    rows = [[p.size, str(p.pieces), f"{p.used:,.1f}", str(p.bars), f"{p.waste_pct:.1f}",
             f"{p.bars * p.stock * float(rates.rebar_kg_m.get(p.size, 0)):,.0f}"] for p in plans]
    y = table(sh, x0, y1 - 6, ["ขนาด", "จำนวนท่อน", "ยาวรวมใช้ (ม.)", "ซื้อ 10 ม. (เส้น)", "เศษ (%)", "น้ำหนักซื้อ (กก.)"],
              rows, [18, 24, 30, 30, 18, 30])
    sh.text(x0, y - 8, "ตัวอย่างรายการตัด (เรียงตามชิ้นส่วน)", TXT)
    rows = [[it.element[:22], it.mark[:8], it.bar[:20], it.size, it.shape[:24], f"{it.length:.2f}",
             str(it.total_count)] for it in items[:28]]
    table(sh, x0, y - 12, ["ชิ้นส่วน", "Mark", "เหล็ก", "ขนาด", "รูปร่าง", "ยาวตัด (ม.)", "จำนวน"], rows,
          [52, 18, 44, 14, 56, 22, 16], 5.2)
    return sh


def build_sheets(res) -> list[Sheet]:
    sheets = [notes_sheet(res)]
    sheets += plan_sheets(res, 2)
    sheets.append(foundation_sheet(res, f"S-{len(sheets) + 1:02d}"))
    sheets += schedule_sheets(res, len(sheets) + 1)
    sheets += beam_elevation_sheets(res, len(sheets) + 1)
    sheets.append(column_elevation_sheet(res, f"S-{len(sheets) + 1:02d}"))
    if res.trusses:
        sheets.append(truss_sheet(res, f"S-{len(sheets) + 1:02d}"))
    sheets.append(cutting_sheet(res, f"S-{len(sheets) + 1:02d}"))
    total = len(sheets)
    for sh in sheets:
        frame(sh, res.building.name, total)
    return sheets


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def write_sheets_dxf(res, path: str) -> list[Sheet]:
    """All sheets side by side in model space, paper millimetres (plot 1:1)."""
    import ezdxf
    sheets = build_sheets(res)
    doc = ezdxf.new("R2007", setup=True)
    doc.units = ezdxf.units.MM
    doc.styles.add("THAI", font="tahoma.ttf")
    for name, colour in LAYERS.items():
        doc.layers.add(f"S-{name}", color=colour)
    if "DASHED" not in doc.linetypes:
        doc.linetypes.add("DASHED", pattern=[5.0, 3.0, -2.0])
    msp = doc.modelspace()
    gap = 30.0
    for k, sh in enumerate(sheets):
        ox = k * (A3[0] + gap)
        for it in sh.items:
            kind = it[0]
            if kind == "line":
                _, x0, y0, x1, y1, layer, dashed = it
                att = {"layer": f"S-{layer}"}
                if dashed:
                    att["linetype"] = "DASHED"
                msp.add_line((ox + x0, y0), (ox + x1, y1), dxfattribs=att)
            elif kind == "rect":
                _, x, y, w, h, layer, filled = it
                pts = [(ox + x, y), (ox + x + w, y), (ox + x + w, y + h), (ox + x, y + h)]
                msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": f"S-{layer}"})
                if filled:
                    hatch = msp.add_hatch(color=LAYERS.get(layer, 7), dxfattribs={"layer": f"S-{layer}"})
                    hatch.paths.add_polyline_path(pts, is_closed=True)
            elif kind == "circle":
                _, x, y, r, layer, filled = it
                msp.add_circle((ox + x, y), r, dxfattribs={"layer": f"S-{layer}"})
                if filled:
                    hatch = msp.add_hatch(color=LAYERS.get(layer, 7), dxfattribs={"layer": f"S-{layer}"})
                    hatch.paths.add_edge_path().add_arc((ox + x, y), r, 0, 360)
            elif kind == "text":
                _, x, y, s, h, layer, align = it
                t = msp.add_text(s, height=h, dxfattribs={"layer": f"S-{layer}", "style": "THAI"})
                if align == "center":
                    t.set_placement((ox + x, y), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)
                elif align == "right_hint":
                    t.set_placement((ox + x, y), align=ezdxf.enums.TextEntityAlignment.BOTTOM_RIGHT)
                else:
                    t.set_placement((ox + x, y))
            elif kind == "poly":
                _, pts, layer, closed = it
                msp.add_lwpolyline([(ox + px, py) for px, py in pts], close=closed,
                                   dxfattribs={"layer": f"S-{layer}"})
    doc.saveas(path)
    return sheets


def paint(sheet: Sheet, painter, scale: float, colour=True):
    """Draw a sheet with a QPainter; ``scale`` device units per paper mm."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QBrush, QColor, QFont, QPen, QPolygonF
    H = A3[1]
    cols = {"GRID": "#8a8a8a", "BEAM": "#1f4e9a", "COLUMN": "#b00020", "SLAB": "#2e7d32", "FOOTING": "#8d5a00",
            "BAR": "#b00020", "DIM": "#a07800"}

    def P(x, y):
        return QPointF(x * scale, (H - y) * scale)

    def pen(layer, dashed=False, width=0.18):
        c = QColor(cols.get(layer, "#000000") if colour else "#000000")
        p = QPen(c, max(0.5, width * scale))
        if dashed:
            p.setStyle(Qt.DashLine)
        return p

    font = QFont("Tahoma")
    font.setStyleHint(QFont.SansSerif)
    for it in sheet.items:
        kind = it[0]
        if kind == "line":
            _, x0, y0, x1, y1, layer, dashed = it
            painter.setPen(pen(layer, dashed, 0.25 if layer == "FRAME" else 0.18))
            painter.drawLine(P(x0, y0), P(x1, y1))
        elif kind == "rect":
            _, x, y, w, h, layer, filled = it
            painter.setPen(pen(layer, False, 0.35 if layer == "FRAME" else 0.25))
            painter.setBrush(QBrush(QColor(cols.get(layer, "#000"))) if filled else Qt.NoBrush)
            painter.drawRect(QRectF(P(x, y + h), P(x + w, y)))
            painter.setBrush(Qt.NoBrush)
        elif kind == "circle":
            _, x, y, r, layer, filled = it
            painter.setPen(pen(layer))
            painter.setBrush(QBrush(QColor(cols.get(layer, "#000"))) if filled else Qt.NoBrush)
            painter.drawEllipse(P(x, y), r * scale, r * scale)
            painter.setBrush(Qt.NoBrush)
        elif kind == "text":
            _, x, y, s, h, layer, align = it
            font.setPixelSize(max(1, int(h * scale * 1.35)))
            painter.setFont(font)
            painter.setPen(QColor(cols.get(layer, "#000000") if colour else "#000000"))
            p = P(x, y)
            if align in ("center", "right_hint"):
                w = painter.fontMetrics().horizontalAdvance(s)
                p = QPointF(p.x() - (w / 2 if align == "center" else w), p.y())
            painter.drawText(p, s)
        elif kind == "poly":
            _, pts, layer, closed = it
            painter.setPen(pen(layer))
            poly = QPolygonF([P(px, py) for px, py in pts])
            painter.drawPolygon(poly) if closed else painter.drawPolyline(poly)


def write_sheets_pdf(res, path: str) -> list[Sheet]:
    """A3 landscape PDF, one page per sheet (Qt, no extra dependency)."""
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QGuiApplication, QPageLayout, QPageSize, QPainter, QPdfWriter
    app = QGuiApplication.instance()
    if app is None:                                   # command line use
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QGuiApplication([])
    sheets = build_sheets(res)
    pdf = QPdfWriter(path)
    pdf.setResolution(300)
    pdf.setPageLayout(QPageLayout(QPageSize(QPageSize.A3), QPageLayout.Landscape, QMarginsF(0, 0, 0, 0)))
    painter = QPainter(pdf)
    scale = 300 / 25.4
    for k, sh in enumerate(sheets):
        if k:
            pdf.newPage()
        paint(sh, painter, scale)
    painter.end()
    return sheets


def render_png(sheet: Sheet, path: str, dpi: int = 100):
    from PySide6.QtGui import QColor, QImage, QPainter
    scale = dpi / 25.4
    img = QImage(int(A3[0] * scale), int(A3[1] * scale), QImage.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    paint(sheet, p, scale)
    p.end()
    img.save(path)


_ = REFS
