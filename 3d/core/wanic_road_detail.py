# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""SD — แบบมาตรฐานโครงสร้างทาง drawn from the project's own design.

The DRR standard drawings for local roads (แบบมาตรฐานงานทางสำหรับ อปท.:
ทถ-2-201(1)/(2) ถนนคอนกรีตเสริมเหล็ก, ทถ-2-202 การเสริมเหล็กและรอยต่อ,
ทถ-2-302 D.B.S.T., ทถ-2-303 Asphalt Concrete) leave the widths and the
thicknesses «ตามที่ผู้ออกแบบระบุ»; here every sheet carries the project's
values, from the road panel's template and the pavement design
(:mod:`core.wanic_pavement`):

* **SD-01 รูปตัดโครงสร้างทาง** — the typical section to scale (vertical ×2)
  with the lanes, shoulders, crossfalls, each layer with its material and
  compaction as the standard words it, a true-scale layer column, the
  slope table, the design summary and the standard's recommended table
  with the row of this project marked;
* **SD-02 (concrete) แปลนเหล็กเสริมและรอยต่อ** — one slab bay in plan with
  the mesh, dowels and tie bars, the contraction / expansion /
  construction / longitudinal joint details, ทถ-2-202 tables 1–2 with the
  row marked, and the steel quantities a bay and for the road;
  **SD-02 (asphalt) แบบขยายชั้นทาง** — edge and shoulder detail, prime and
  tack coats, the DRR AC tables (7 and 10 years) with the row marked;
* **SD-03 รายการประกอบแบบ** — the general notes of the standard and a
  summary of the calculation.

Pure Python (no Qt); sheets are :class:`core.wanic_drawings.Sheet`.
"""
from __future__ import annotations


import math

from core import wanic_drawings as D
from core import wanic_pavement as V

X0, Y0, X1, Y1 = D.drawing_area()
MARK_RGB = (255, 244, 170)            # the row of this project in a standard table
LAYER_GRAY = {"คอนกรีต": 0.80, "AC": 0.25, "แอสฟัลต์": 0.25, "DBST": 0.30, "ลาดยาง": 0.30,
              "ทราย": 0.93, "หินคลุก": 0.62, "มวลรวม": 0.74, "ลูกรัง": 0.70,
              "คัดเลือก": 0.84, "ซีเมนต์": 0.66}

#: How the standard words each material (and the standard it refers to).
SPEC = (("คอนกรีตเสริมเหล็ก", "ผิวจราจรคอนกรีตเสริมเหล็ก f'c >= {fc} กก./ตร.ซม. (ลูกบาศก์ 28 วัน)"),
        ("คอนกรีตไม่เสริมเหล็ก", "ผิวจราจรคอนกรีตไม่เสริมเหล็ก f'c >= {fc} กก./ตร.ซม. (ลูกบาศก์ 28 วัน)"),
        ("Binder", "ชั้นรองผิว ASPHALT CONCRETE (A.C. 60-70) ตาม มทถ. 230-2562"),
        ("แอสฟัลต์คอนกรีต", "ผิวจราจรลาดยางแบบ ASPHALT CONCRETE (A.C. 60-70) ตาม มทถ. 230-2562"),
        ("AC", "ผิวจราจรลาดยางแบบ ASPHALT CONCRETE (A.C. 60-70) ตาม มทถ. 230-2562"),
        ("DBST", "ผิวจราจรลาดยางแบบ DOUBLE BITUMINOUS SURFACE TREATMENT ตาม มทถ. 226-2562"),
        ("เคลือบผิว", "ผิวจราจรลาดยางแบบ SURFACE TREATMENT ตาม มทถ. 226-2562"),
        ("ทราย", "ทรายหยาบบดอัดแน่น (NON PLASTIC ขนาดโตสุด 3/8\" ผ่านตะแกรงเบอร์ 200 ไม่เกิน 10%)"),
        ("หินคลุก", "พื้นทางหินคลุก CBR >= 80% บดอัดแน่นไม่น้อยกว่า 95% MODIFIED PROCTOR DENSITY "
                    "(มทถ. 203-2562)"),
        ("ดินซีเมนต์", "พื้นทางดินซีเมนต์ ตาม มทถ. 244-2562"),
        ("มวลรวม", "รองพื้นทาง SOIL AGGREGATE CBR >= 25% บดอัดแน่นไม่น้อยกว่า 95% MODIFIED PROCTOR "
                   "DENSITY (มทถ. 202-2562)"),
        ("ลูกรัง", "รองพื้นทางลูกรัง CBR >= 25% บดอัดแน่นไม่น้อยกว่า 95% MODIFIED PROCTOR DENSITY "
                   "(มทถ. 202-2562)"),
        ("คัดเลือก", "วัสดุคัดเลือก CBR >= 10% บดอัดแน่นไม่น้อยกว่า 95% MODIFIED PROCTOR DENSITY "
                     "(มทถ. 204-2562)"),
        ("ทรายถม", "ทรายถม CBR >= 10% บดอัดแน่นไม่น้อยกว่า 95% MODIFIED PROCTOR DENSITY"))
EMBANKMENT = "ดินถมคันทาง CBR >= 4% บดอัดแน่นไม่น้อยกว่า 95% STANDARD PROCTOR DENSITY (มทถ. 201-2562)"
GROUND = "ดินเดิม ปรับเกลี่ยแต่งและบดอัดแน่นไม่น้อยกว่า 95% STANDARD PROCTOR DENSITY"

#: ตารางแสดงค่าลาดตัดคันทาง (BACK SLOPE) และลาดถมคันทาง (SIDE SLOPE) — ราบ : ดิ่ง
SLOPES = (("0.00 – 3.00", "2:1", "2:1", "1:1", "1.5:1", "0.25:1", "1:1"),)

#: kg per metre of the bars
BAR_KG = {6: 0.222, 9: 0.499, 12: 0.888, 16: 1.578, 19: 2.226, 20: 2.466, 25: 3.853}


def spec_of(name: str, fc: float = 280.0) -> str:
    for key, text in SPEC:
        if key in name:
            return text.format(fc=f"{fc:,.0f}")
    return name


def gray_of(name: str) -> float:
    for key, g in LAYER_GRAY.items():
        if key in name:
            return g
    return 0.78


def is_concrete(layers) -> bool:
    """A concrete (rigid) road: its surface is concrete, not asphalt concrete."""
    if not layers:
        return False
    n = layers[0][0]
    return "คอนกรีต" in n and not any(k in n for k in ("แอสฟัลต์", "AC", "ลาดยาง", "Asphalt"))


def _num(v, d=2):
    return f"{v:.{d}f}"


# ---------------------------------------------------------------------------
# the design behind the drawings
# ---------------------------------------------------------------------------

class Design:
    """The road's template and pavement as the sheets need them, with the
    pavement design re-run from its stored inputs (``pave`` = the road
    panel's ``pave_design``)."""

    def __init__(self, settings, pave=None, length=0.0):
        s = settings
        self.width = float(s.width)
        self.shoulder = float(s.shoulder)
        self.crown = float(s.crown)
        self.shoulder_slope = float(s.shoulder_slope)
        self.cut_hv = float(s.cut_hv)
        self.fill_hv = float(s.fill_hv)
        self.layers = [(n, float(t)) for n, t, _c in s.pavement_layers()]
        self.length = float(length or 0.0)
        self.concrete = is_concrete(self.layers)
        self.pave = dict(pave or {})
        self.res = None
        self.method = None
        try:
            if self.concrete and self.pave.get("rn"):
                rn_in = _rn_input(self.pave["rn"])
                # check the slab and sub-base as drawn (the layer table)
                rn_in.slab_cm = self.layers[0][1] * 100.0
                sub = [t for n, t in self.layers if "รองพื้นทาง" in n]
                rn_in.subbase_cm = sub[0] * 100.0 if sub else None
                self.res = V.design_rn29(rn_in)
                self.method = "rn29"
            elif not self.concrete and self.pave.get("ai"):
                self.res = V.design_ai(_ai_input(self.pave["ai"], self.layers))
                self.method = "ai"
        except (ValueError, ZeroDivisionError, KeyError, TypeError):
            self.res = None
        rn = self.pave.get("rn") or {}
        self.fc = float(rn.get("fc") or 280.0)
        self.slab_length = float(rn.get("slab_length") or 10.0)
        self.fs = float(rn.get("fs") or 2750.0)
        lanes = int(rn.get("lanes") or (2 if self.width > 4.5 else 1)) if self.concrete else 2
        self.lanes = max(1, lanes)

    @property
    def slab_cm(self) -> float:
        return self.layers[0][1] * 100.0 if self.layers else 0.0

    @property
    def lane_width(self) -> float:
        """Width of one slab between longitudinal joints."""
        n = 2 if self.width > 4.5 else 1
        return self.width / n

    @property
    def longitudinal_joint(self) -> bool:
        return self.concrete and self.width > 4.5

    @property
    def total(self) -> float:
        return sum(t for _n, t in self.layers)


def _ai_input(d, layers):
    src = d.get("source", "auto")
    lay = [[n, t * 100.0] for n, t in layers] if src == "table" or layers else None
    return V.AIInput(idt=float(d.get("idt", 1000)), heavy_pct=float(d.get("heavy_pct", 10)),
                     lanes=int(d.get("lanes", 2)), gross_t=float(d.get("gross_t", 21)),
                     growth_pct=float(d.get("growth_pct", 5)), years=float(d.get("years", 15)),
                     cbr=float(d.get("cbr", 5)), layers=lay)


def _rn_input(d):
    trucks = (V.Truck("รถบรรทุก 6 ล้อ (LT)", float(d.get("lt_pct", 70)), (4.0, 11.0)),
              V.Truck("รถบรรทุก 10 ล้อ (HT)", float(d.get("ht_pct", 30)), (5.0, 10.0, 10.0)))
    return V.RNInput(adt=float(d.get("adt", 500)), lanes=int(d.get("lanes", 2)),
                     width=float(d.get("width", 6)), heavy_pct=float(d.get("heavy_pct", 10)),
                     trucks=trucks, loaded_pct=float(d.get("loaded_pct", 100)),
                     growth_pct=float(d.get("growth_pct", 4)), years=float(d.get("years", 20)),
                     cbr=float(d.get("cbr", 4)), reinforced=bool(d.get("reinforced", True)),
                     construction_traffic=bool(d.get("construction_traffic", True)),
                     slab_length=float(d.get("slab_length", 10)),
                     lane_width=float(d.get("lane_width", 3)), fs=float(d.get("fs", 2750)),
                     slab_cm=float(d.get("slab_cm") or 0) or None, fc=float(d.get("fc", 280)),
                     chart_mm=float(d.get("chart_mm") or 0) or None,
                     subbase_kind=str(d.get("subbase_kind") or "laterite"))


# ---------------------------------------------------------------------------
# SD-01 — the typical section
# ---------------------------------------------------------------------------

def _surface(ds, x):
    """Finished level at offset x (m) from the centre line (crown 0)."""
    a = abs(x)
    half = ds.width / 2
    z = -ds.crown / 100.0 * min(a, half)
    if a > half:
        z -= ds.shoulder_slope / 100.0 * (a - half)
    return z


def _edge(ds, depth):
    """Offset where the line ``depth`` under the finish meets the fill slope."""
    B = ds.width / 2 + ds.shoulder
    k = 1.0 / max(ds.fill_hv, 0.1) - ds.shoulder_slope / 100.0
    return B + (depth / k if k > 1e-6 else depth * ds.fill_hv)


def _band(ds, d0, d1, x_lim=None):
    """The polygon (model x, z) between depths d0 and d1 under the finish,
    out to the fill slope (or to ±x_lim)."""
    e0 = _edge(ds, d0) if x_lim is None else x_lim
    e1 = _edge(ds, d1) if x_lim is None else x_lim
    half, B = ds.width / 2, ds.width / 2 + ds.shoulder

    def line(d, e):
        xs = sorted({x for x in (-e, -B, -half, 0.0, half, B, e) if abs(x) <= e + 1e-9})
        return [(x, _ext(ds, x) - d) for x in xs]
    return line(d0, e0) + line(d1, e1)[::-1]


def _ext(ds, x):
    """The finish carried on past the shoulder edge at the shoulder's fall."""
    B = ds.width / 2 + ds.shoulder
    a = abs(x)
    if a <= B:
        return _surface(ds, x)
    return _surface(ds, B) - ds.shoulder_slope / 100.0 * (a - B)


def section_sheet(ds: Design, info=None) -> D.Sheet:
    kind = "ถนนคอนกรีตเสริมเหล็ก" if ds.concrete else "ถนนลาดยาง"
    sh = D.Sheet("SD-01", f"รูปตัดโครงสร้างทาง {kind}", "ตามระบุ", "SD")
    fill_h = 0.80                                    # embankment under the layers, drawn
    B = ds.width / 2 + ds.shoulder
    gz = _surface(ds, 0) - ds.total - fill_h         # the natural ground
    toe = B + (_surface(ds, B) - gz) * ds.fill_hv
    span = 2 * toe + 1.5
    sc = D.fit_scale((span, 1.0), (215.0, 200.0), (20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 200))
    ve = 2.0                                         # vertical exaggeration of the layers
    k = 1000.0 / sc
    cx, cy = X0 + 6 + span / 2 * k, Y1 - 58

    def P(x, z):
        return (cx + x * k, cy + z * k * ve)
    # layers, top first
    d = 0.0
    pts_leader = []
    for i, (name, t) in enumerate(ds.layers):
        lim = ds.width / 2 if (i == 0 and ds.concrete) else None
        poly = [P(x, z) for x, z in _band(ds, d, d + t, lim)]
        sh.fill(poly, "hatch", gray_of(name))
        sh.poly(poly, "wall", 0.25)
        if i == 0 and ds.concrete:
            # the shoulders beside the slab: compacted laterite (ไหล่ทางลูกรัง)
            for sg in (-1, 1):
                xs = [ds.width / 2, B, _edge(ds, t)]
                q = [P(sg * xs[0], _ext(ds, xs[0])), P(sg * xs[1], _ext(ds, xs[1])),
                     P(sg * xs[2], _ext(ds, xs[2]) - t), P(sg * xs[0], _ext(ds, xs[0]) - t)]
                sh.fill(q, "hatch", 0.70)
                sh.poly(q, "wall", 0.25)
        xm = ds.width * 0.30 + i * 0.12 * ds.width / 2
        pts_leader.append((P(xm, _surface(ds, xm) - d - t / 2),
                           f"{spec_of(name, ds.fc)} หนา {t:.2f} ม."))
        d += t
    # the embankment down to the natural ground
    sh.line(P(-toe - 1.0, gz), P(toe + 1.0, gz), "wall", 0.35)
    for x in [(-toe - 0.8) + i * (2 * toe + 1.6) / 12 for i in range(13)]:
        a = P(x, gz)
        sh.line(a, (a[0] - 1.5, a[1] - 1.5), "wall", 0.13)
    # the side slopes from the shoulder edge to the ground
    for sg in (-1, 1):
        sh.line(P(sg * B, _surface(ds, B)), P(sg * toe, gz), "wall", 0.35)
        sh.text(P(sg * (B + toe) / 2 + sg * 0.3, (_surface(ds, B) + gz) / 2),
                f"SIDE SLOPE {ds.fill_hv:g}:1", 1.8, "left" if sg > 0 else "right", "dim")
        sh.line(P(sg * B, _surface(ds, B)), P(sg * (B + 0.30 * ds.fill_hv), _surface(ds, B) - 0.30),
                "hidden", 0.13, True)
    pts_leader.append((P(toe * 0.55, gz + (fill_h + 0.0) * 0.45), EMBANKMENT))
    pts_leader.append((P(toe + 0.6, gz), GROUND))
    pts_leader.append((P(-(B + toe) / 2, (_surface(ds, B) + gz) / 2 - 0.15),
                       "ปลูกหญ้าตามแนวลาดคันทาง ตามแบบ ทถ-2-601"))
    # the finish: centre line, crossfalls, widths
    top = P(0, _surface(ds, 0))
    sh.line((top[0], top[1] + 34), (top[0], P(0, gz)[1] - 4), "grid", 0.18, True)
    sh.text((top[0], top[1] + 35), "CL", 3.0, "center", "grid")
    sh.text((top[0] + 1.5, top[1] + 2.0), "ระดับก่อสร้าง", 1.8, "left", "dim")
    for sg in (-1, 1):
        a = P(sg * ds.width * 0.25, _surface(ds, ds.width * 0.25))
        sh.text((a[0], a[1] + 2.0), f"{ds.crown:.1f}%", 2.0, "center", "dim")
        sh.line((a[0] - 4, a[1] + 1.4), (a[0] + 4, a[1] + 1.4 - 0.4), "dim", 0.13)
        if ds.shoulder > 0:
            b = P(sg * (ds.width / 2 + ds.shoulder / 2), _surface(ds, ds.width / 2 + ds.shoulder / 2))
            sh.text((b[0], b[1] + 2.0), f"{ds.shoulder_slope:.1f}%", 2.0, "center", "dim")
    yd = top[1] + 10
    xs = [-B, -ds.width / 2, 0.0, ds.width / 2, B] if ds.shoulder > 0 else [-B, 0.0, B]
    names = (["ไหล่ทาง", "ครึ่งผิวจราจร", "ครึ่งผิวจราจร", "ไหล่ทาง"] if ds.shoulder > 0
             else ["ครึ่งผิวจราจร", "ครึ่งผิวจราจร"])
    for (a, b), nm in zip(zip(xs, xs[1:]), names):
        pa, pb = P(a, 0)[0], P(b, 0)[0]
        D._dim_h(sh, pa, pb, yd, f"{b - a:.2f}")
        sh.text(((pa + pb) / 2, yd + 4.0), nm, 1.8, "center", "dim")
    D._dim_h(sh, P(-ds.width / 2, 0)[0], P(ds.width / 2, 0)[0], yd + 9,
             f"ผิวจราจร {ds.width:.2f} ม.")
    D._dim_h(sh, P(-B, 0)[0], P(B, 0)[0], yd + 15, f"ความกว้างคันทาง {2 * B:.2f} ม.")
    if ds.longitudinal_joint:
        sh.text((top[0] + 1.0, top[1] - 4), "รอยต่อตามยาว (TIE BAR)", 1.6, "left", "dim")
    D.leaders(sh, pts_leader, X0 + 228, "right", 4.6, 1.7)
    D.caption(sh, (X0 + 110, Y1 - 118), f"รูปตัดโครงสร้าง{kind}",
              f"ราบ 1:{sc} ดิ่ง 1:{sc / ve:g} (ขยายชั้นทาง {ve:g} เท่า)")
    _layer_column(sh, ds, X0 + 4, Y1 - 135)
    _slope_table(sh, X0 + 62, Y1 - 135)
    _summary_box(sh, ds, X0 + 62, Y1 - 168)
    _standard_table(sh, ds, X0 + 188, Y1 - 135)
    sh.scale = f"1:{sc}"
    return sh


def _layer_column(sh, ds, x, ytop):
    """The layers at true scale (1:10 or 1:20) with their thicknesses."""
    tot = max(ds.total, 0.05)
    sc = 10 if tot <= 1.05 else 20
    k = 1000.0 / sc
    sh.text((x, ytop), "ชั้นโครงสร้างทาง (มาตราส่วนจริง)", 2.6, "left", "text", True)
    sh.text((x, ytop - 4.0), f"มาตราส่วน 1:{sc}", 2.0)
    y = ytop - 8
    w = 22.0
    for name, t in ds.layers:
        h = t * k
        sh.fill([(x, y - h), (x + w, y - h), (x + w, y), (x, y)], "hatch", gray_of(name))
        sh.rect(x, y - h, x + w, y, "wall", 0.25)
        D._dim_v(sh, x + w + 4, y - h, y, f"{t * 100:g}")
        sh.text((x + w + 7, y - h / 2 - 0.6), name.replace("ชั้น", ""), 1.6)
        y -= h
    sh.text((x, y - 4), f"รวม {ds.total * 100:g} ซม. (หน่วย: ซม.)", 1.9)


def _slope_table(sh, x, y):
    sh.text((x, y), "ตารางแสดงค่าลาดตัดคันทาง (BACK SLOPE) และลาดถมคันทาง (SIDE SLOPE)", 2.4,
            "left", "text", True)
    cols = [("สูงตัด/ถม (ม.)", 26, "center"), ("ดิน ตัด", 15, "center"), ("ดิน ถม", 15, "center"),
            ("หินผุ ตัด", 16, "center"), ("หินผุ ถม", 16, "center"), ("หินแข็ง ตัด", 18, "center"),
            ("หินแข็ง ถม", 18, "center")]
    yy = D.table(sh, x, y - 2.5, cols, SLOPES, 1.9, 5.2, 6.0)
    sh.text((x, yy - 3.5), "อัตราส่วน ราบ : ดิ่ง · สูงกว่า 3.00 ม. ให้ทำชานพัก (BERM) ตามแบบ ทถ-2-501", 1.8)


def _summary_box(sh, ds, x, y):
    sh.text((x, y), "สรุปผลการออกแบบความหนาโครงสร้างทาง", 2.6, "left", "text", True)
    lines = []
    r = ds.res
    if ds.method == "ai" and r is not None:
        i = r.inp
        lines = ["วิธี Asphalt Institute (1970) ตามคู่มือกรมทางหลวง",
                 f"IDT {i.idt:,.0f} คัน/วัน · รถบรรทุกหนัก {i.heavy_pct:g}% · {i.lanes} ช่องจราจร · "
                 f"อายุออกแบบ {i.years:g} ปี",
                 f"ITN {r.itn:,.1f} · DTN {r.dtn:,.0f} ({V.traffic_class(r.dtn)}) · CBR ดินคันทาง {i.cbr:g}%",
                 f"TA ที่ต้องการ {r.ta:.2f} ซม. · TA ที่ออกแบบ {sum(x[4] for x in r.layers):.2f} ซม. => "
                 + ("ผ่าน" if r.ok else "ไม่ผ่าน")]
    elif ds.method == "rn29" and r is not None:
        i = r.inp
        lines = ["วิธี Road Note 29 ตามรายการคำนวณของกรมทางหลวงชนบท",
                 f"ADT {i.adt:,.0f} คัน/วัน · รถบรรทุกหนัก {i.heavy_pct:g}% · อายุออกแบบ {i.years:g} ปี",
                 f"ESA สะสม {r.esa / 1e6:,.3f} × 10^6 · CBR ดินคันทาง {i.cbr:g}%",
                 f"ต้องการ (แผนภูมิ) {r.slab_chart_mm:.0f} มม. · ตามแบบ ผิว คสล. {r.slab_cm:g} ซม. · "
                 f"รองพื้นทาง {r.subbase_cm:g} ซม. (ต้องการ {r.subbase_need:g}) => "
                 + ("ผ่าน" if r.ok else "ไม่ผ่าน")]
    else:
        lines = ["ยังไม่ได้คำนวณความหนา (แผงออกแบบถนน ข้อ 3 «ออกแบบความหนาโครงสร้างทาง»)",
                 "ความหนาตามตารางชั้นทางที่กำหนด"]
    lines.append(f"ชั้นทางรวม {ds.total * 100:g} ซม.: " +
                 " / ".join(f"{t * 100:g}" for _n, t in ds.layers))
    yy = y - 5
    for ln in lines:
        for part in D._wrap(ln, 62):
            sh.text((x, yy), part, 2.0)
            yy -= 3.6


def _standard_rows(ds):
    """(sheet name, cols, rows, index of the project's row or None)."""
    cbr = 5.0
    traffic = 0.0
    if ds.res is not None:
        cbr = ds.res.inp.cbr
        traffic = ds.res.inp.adt if ds.method == "rn29" else ds.res.inp.idt
    c = V._cbr_class(cbr)
    if ds.concrete:
        base = any("หินคลุก" in n for n, _t in ds.layers)
        table = V.DRR_RC2 if base else V.DRR_RC1
        name = "ทถ-2-201(2) ชั้นพื้นทางหินคลุก" if base else "ทถ-2-201(1) ชั้นรองพื้นทางลูกรัง"
        cols = [("ผิว คสล. (ม.)", 18, "center"), ("CBR", 11, "center"), ("คัดเลือก", 15, "center"),
                ("รองพื้นทาง", 17, "center")] + ([("พื้นทาง", 15, "center")] if base else []) + \
            [("ADT", 22, "center")]
        rows, mark = [], None
        prev = 0
        for slab, upto, by in table:
            for cb, vals in sorted(by.items()):
                row = [f"{slab:.2f}", f"{cb}%"] + [f"{v:.2f}" if v else "-" for v in vals] + \
                    [f"{prev + 1:,}–{upto:,}" if prev else f"<= {upto:,}"]
                if mark is None and traffic and prev < traffic <= upto and cb == min(by, key=lambda q: abs(q - c)):
                    mark = len(rows)
                rows.append(row)
            prev = upto
        return name, cols, rows, mark
    ac = ds.layers and ("แอสฟัลต์" in ds.layers[0][0] or "AC" in ds.layers[0][0])
    if not ac:
        cols = [("CBR", 12, "center"), ("ADT <=", 16, "center"), ("คัดเลือก", 16, "center"),
                ("รองพื้นทาง", 18, "center"), ("พื้นทาง", 16, "center")]
        rows, mark = [], None
        for cb, upto, sel, sub, base in V.DRR_DBST:
            if mark is None and traffic and cb == c and traffic <= upto:
                mark = len(rows)
            rows.append([f"{cb}%", f"{upto:,}", f"{sel:.2f}" if sel else "-", f"{sub:.2f}", f"{base:.2f}"])
        return "ทถ-2-302 D.B.S.T. (ระยะออกแบบ 7 ปี)", cols, rows, mark
    years = int(ds.res.inp.years) if ds.res is not None else 10
    table = V.DRR_AC7 if years <= 7 else V.DRR_AC10
    cols = [("CBR", 11, "center"), ("AC (ซม.)", 14, "center"), ("ADT <=", 15, "center"),
            ("คัดเลือก", 15, "center"), ("รองพื้นทาง", 17, "center"), ("พื้นทาง", 15, "center")]
    rows, mark = [], None
    for cb, acm, upto, sel, sub, base in table:
        if mark is None and traffic and cb == c and traffic <= upto:
            mark = len(rows)
        rows.append([f"{cb}%", f"{acm:g}", f"{upto:,}", f"{sel:.2f}" if sel else "-", f"{sub:.2f}",
                     f"{base:.2f}"])
    return f"ทถ-2-303 Asphalt Concrete (ระยะออกแบบ {7 if years <= 7 else 10} ปี)", cols, rows, mark


def _marked_table(sh, x, y, cols, rows, mark, h=1.8, row_h=4.4):
    if mark is not None:
        W = sum(c[1] for c in cols)
        y0 = y - 6.0 - mark * row_h
        sh.fill([(x, y0 - row_h), (x + W, y0 - row_h), (x + W, y0), (x, y0)], "hatch", 0.9,
                MARK_RGB)
    return D.table(sh, x, y, cols, rows, h, row_h, 6.0)


def _standard_table(sh, ds, x, y):
    name, cols, rows, mark = _standard_rows(ds)
    sh.text((x, y), "ตารางแนะนำความหนาชั้นโครงสร้างทาง", 2.6, "left", "text", True)
    sh.text((x, y - 4), f"แบบมาตรฐาน กรมทางหลวงชนบท {name}", 1.9)
    yy = _marked_table(sh, x, y - 6, cols, rows, mark)
    sh.text((x, yy - 3.5), "แถบสีเหลือง = แถวที่ตรงกับปริมาณจราจรและ CBR ของโครงการ"
            if mark is not None else "ปริมาณจราจร/CBR ของโครงการอยู่นอกตาราง — ใช้ผลการคำนวณ", 1.7)


# ---------------------------------------------------------------------------
# SD-02 — reinforcement and joints (concrete) / layer details (asphalt)
# ---------------------------------------------------------------------------

def steel_choice(ds):
    """(longitudinal, transverse) steel: the design's pick, else ทถ-2-202."""
    t = V.temperature_steel(ds.slab_cm, ds.lane_width)
    if ds.method == "rn29" and ds.res is not None:
        return ds.res.steel_long, ds.res.steel_trans, t
    if t is not None:
        lo = (t["long"], t["long_area"] / 100.0)
        tr = (t["trans"], t["trans_area"] / 100.0)
        return lo, tr, t
    return ("RB9 @ 0.20 ม.", 3.18), ("RB6 @ 0.20 ม.", 1.41), None


def _dia_spacing(label):
    import re
    m = re.search(r"Ø?\s*(\d+)\s*มม\.?\s*@\s*([\d.]+)", label) or re.search(r"(\d+)\s*@\s*([\d.]+)", label)
    if not m:
        m = re.search(r"RB(\d+)\s*@\s*([\d.]+)", label)
    if not m:
        return 6, 0.20
    return int(m.group(1)), float(m.group(2))


def quantities(ds) -> dict:
    """Steel, joints and sealant of one slab bay and of the road."""
    L, w = ds.slab_length, ds.width
    lo, tr, _t = steel_choice(ds)
    d_l, s_l = _dia_spacing(lo[0])
    d_t, s_t = _dia_spacing(tr[0])
    n_long = int(w / s_l) + 1
    n_trans = int(L / s_t) + 1
    kg_long = n_long * (L - 0.10) * BAR_KG.get(d_l, 0.00617 * d_l ** 2)
    kg_trans = n_trans * (w - 0.10) * BAR_KG.get(d_t, 0.00617 * d_t ** 2)
    row = next((r for r in V.DOWELS if ds.slab_cm <= r[0] + 1e-6), V.DOWELS[-1])
    dd, dl, dsp = row[1], row[2] / 100.0, row[3] / 100.0
    n_dowel = (int((ds.lane_width - 0.30) / dsp) + 1) * (2 if ds.longitudinal_joint else 1)
    n_tie = int(L / 0.50) if ds.longitudinal_joint else 0
    bay = {"area": L * w, "steel_kg": kg_long + kg_trans, "dowels": n_dowel,
           "dowel_kg": n_dowel * dl * BAR_KG.get(dd, 0.00617 * dd ** 2),
           "ties": n_tie, "tie_kg": n_tie * 0.50 * BAR_KG[12],
           "sealant": w + (L if ds.longitudinal_joint else 0.0)}
    bays = ds.length / L if ds.length > 0 else 0.0
    road = {k: v * bays for k, v in bay.items()}
    return {"bay": bay, "road": road, "bays": bays, "long": lo, "trans": tr,
            "dowel": (dd, dl, dsp)}


def joints_sheet(ds: Design) -> D.Sheet:
    sh = D.Sheet("SD-02", "แปลนเหล็กเสริมและรอยต่อถนนคอนกรีต", "ตามระบุ", "SD")
    q = quantities(ds)
    lo, tr = q["long"], q["trans"]
    L, w = ds.slab_length, ds.width
    sc = D.fit_scale((L + 1.0, w + 1.0), (200.0, 100.0), (25, 30, 40, 50, 60, 75, 100))
    k = 1000.0 / sc
    ox, oy = X0 + 12, Y1 - 20 - w * k

    def P(x, y):
        return (ox + x * k, oy + y * k)
    sh.rect(*P(0, 0), *P(L, w), "wall", 0.5)
    for sg, yy in ((0, -0.5), (1, w)):
        sh.rect(*P(0, yy), *P(L, yy + 0.5), "hidden", 0.18)
        sh.text(P(L / 2, yy + 0.18), "ไหล่ทาง (ตามแบบ)", 1.7, "center", "hidden")
    _d_l, s_l = _dia_spacing(lo[0])
    _d_t, s_t = _dia_spacing(tr[0])
    y = 0.05
    while y <= w - 0.05 + 1e-6:                        # longitudinal steel
        sh.line(P(0.05, y), P(L - 0.05, y), "dim", 0.13)
        y += s_l
    x = 0.05
    while x <= L - 0.05 + 1e-6:                        # transverse steel
        sh.line(P(x, 0.05), P(x, w - 0.05), "dim", 0.13)
        x += s_t
    dd, dl, dsp = q["dowel"]
    lanes = [(0.0, ds.lane_width), (ds.lane_width, w)] if ds.longitudinal_joint else [(0.0, w)]
    for x in (0.0, L):                                 # dowels across both transverse joints
        for a, b in lanes:
            yy = a + 0.15
            while yy <= b - 0.15 + 1e-6:
                sh.line(P(x - dl / 2, yy), P(x + dl / 2, yy), "wall", 0.6)
                yy += dsp
    if ds.longitudinal_joint:
        sh.line(P(0, ds.lane_width), P(L, ds.lane_width), "grid", 0.35, True)
        xx = 0.25
        while xx < L:
            sh.line(P(xx, ds.lane_width - 0.25), P(xx, ds.lane_width + 0.25), "roof", 0.5)
            xx += 0.50
    D._dim_h(sh, P(0, 0)[0], P(L, 0)[0], P(0, -0.5)[1] - 5, f"{L:.2f}")
    D._dim_v(sh, P(0, 0)[0] - 6, P(0, 0)[1], P(0, w)[1], f"{w:.2f}")
    if ds.longitudinal_joint:
        D._dim_v(sh, P(L, 0)[0] + 6, P(0, 0)[1], P(0, ds.lane_width)[1], f"{ds.lane_width:.2f}")
    items = [(P(L * 0.30, w * 0.62), f"เหล็กตามยาว {lo[0]}"),
             (P(L * 0.42, w * 0.80), f"เหล็กตามขวาง {tr[0]}"),
             (P(L, 0.15 + dsp), f"DOWEL BAR RB{dd} ยาว {dl:.2f} ม. @ {dsp:.2f} ม."),
             (P(L * 0.5, w - 0.05), "ระยะหุ้มขอบ 0.05 ม.")]
    if ds.longitudinal_joint:
        items.append((P(L * 0.72, ds.lane_width), "TIE BAR DB12 ยาว 0.50 ม. @ 0.50 ม. (รอยต่อตามยาว)"))
    D.leaders(sh, items, P(L, 0)[0] + 14, "right", 4.5, 1.8)
    D.caption(sh, (P(L / 2, 0)[0], P(0, -0.5)[1] - 13), "แปลนแสดงการเสริมเหล็กถนน คสล. (1 แผ่น)",
              f"1:{sc}")
    # the joint details at 1:10
    t = ds.slab_cm / 100.0
    det = [("รอยต่อหดตัว CONTRACTION JOINT", "contraction"),
           ("รอยต่อขยายตัว EXPANSION JOINT", "expansion"),
           ("รอยต่อก่อสร้าง CONSTRUCTION JOINT", "construction"),
           ("รอยต่อตามยาว LONGITUDINAL JOINT", "longitudinal")]
    for j, (title, kind) in enumerate(det):
        bx = X0 + 4 + (j % 2) * 108
        by = Y1 - 160 - (j // 2) * 56
        _joint_detail(sh, ds, kind, bx, by, t, dd, dl, dsp)
        D.caption(sh, (bx + 50, by - 16), title, "1:10")
    _quantity_table(sh, ds, q, X0 + 222, Y1 - 4)
    _steel_tables(sh, ds, X0 + 222, Y1 - 62)
    return sh


def _joint_detail(sh, ds, kind, x, y, t, dd, dl, dsp):
    """One joint across the slab at 1:10: ``x, y`` the slab's bottom left."""
    k = 100.0                                          # 1:10 => 100 mm per metre
    wd = 1.0                                           # 1.00 m of slab drawn
    h = t * k
    jx = x + wd / 2 * k
    sh.rect(x, y, x + wd * k, y + h, "wall", 0.35)
    sh.fill([(x, y - 0.05 * k), (x + wd * k, y - 0.05 * k), (x + wd * k, y), (x, y)], "hatch", 0.93)
    sh.text((x + wd * k - 1, y - 0.03 * k - 0.6), "ทรายรองพื้น", 1.5, "right")
    sh.line((x, y + 0.05 * k), (x + wd * k, y + 0.05 * k), "dim", 0.13, True)   # mesh
    sh.text((x + 1, y + 0.05 * k + 0.8), "ตะแกรงเหล็ก", 1.5, "left", "dim")
    D._dim_v(sh, x - 3, y, y + h, f"{t * 100:g} ซม.")
    if kind != "longitudinal":
        bar_y = y + h / 2
        sh.line((jx - dl / 2 * k, bar_y), (jx + dl / 2 * k, bar_y), "wall", dd / 10.0)
        sh.line((jx, bar_y + 0.6), (jx + dl / 2 * k, bar_y + 0.6), "roof", 0.18, True)
        sh.text((jx + 2, bar_y - 3.2), f"DOWEL RB{dd} ยาว {dl:.2f} ม. @ {dsp:.2f} ม.", 1.6)
        sh.text((jx + 2, bar_y + 1.6), "ทาสีและทาน้ำมันหล่อลื่นครึ่งท่อน", 1.5, "left", "roof")
    else:
        bar_y = y + h / 2
        sh.line((jx - 0.25 * k, bar_y), (jx + 0.25 * k, bar_y), "wall", 1.2)
        sh.text((jx + 2, bar_y - 3.2), "TIE BAR DB12 ยาว 0.50 ม. @ 0.50 ม.", 1.6)
    if kind == "contraction":
        sh.line((jx, y + h), (jx, y + h - h / 4), "wall", 0.6)
        sh.text((jx + 1.5, y + h + 1.2), "ตัดร่อง (SAWED JOINT) ลึก T/4 กว้าง 6–12 มม. ยาแนว MASTIC", 1.5)
        sh.line((jx - 0.50 * k, y - 0.6), (jx + 0.50 * k, y - 0.6), "hidden", 0.35)
        sh.text((x + 1, y - 0.05 * k - 3.0), "แผ่นพลาสติกหนา 0.07 มม. กว้าง 1.20 ม. ใต้รอยต่อ", 1.5,
                "left", "hidden")
    elif kind == "expansion":
        sh.fill([(jx - 1.25, y), (jx + 1.25, y), (jx + 1.25, y + h - 2.5), (jx - 1.25, y + h - 2.5)],
                "hatch", 0.55)
        sh.rect(jx - 1.25, y + h - 2.5, jx + 1.25, y + h, "wall", 0.35)
        sh.rect(jx + dl / 2 * k - 5, y + h / 2 - 1.3, jx + dl / 2 * k + 1, y + h / 2 + 1.3, "wall", 0.25)
        sh.text((jx + 1.5, y + h + 1.2), "JOINT FILLER หนา 25 มม. + ยาแนว MASTIC · ปลอกโลหะ/พลาสติก",
                1.5)
    elif kind == "construction":
        sh.line((jx, y), (jx, y + h), "wall", 0.6)
        sh.line((jx, y + h), (jx, y + h - 0.0375 * k), "wall", 0.9)
        sh.text((jx + 1.5, y + h + 1.2), "หยุดเทคอนกรีตที่ตำแหน่งรอยต่อหดตัว · เซาะร่อง 10 มม. ยาแนว", 1.5)
    else:
        sh.line((jx, y + h), (jx, y + h - h / 3), "wall", 0.6)
        sh.text((jx + 1.5, y + h + 1.2), "ตัดร่องลึก T/3 กว้าง 6–10 มม. ยาแนว MASTIC", 1.5)


def _steel_tables(sh, ds, x, y):
    sh.text((x, y), "ตารางที่ 1 TEMPERATURE STEEL (ทถ-2-202)", 2.4, "left", "text", True)
    cols = [("หนา (ซม.)", 13, "center"), ("ตามยาว RB", 22, "center"), ("ช่อง (ม.)", 13, "center"),
            ("ตามขวาง RB", 22, "center"), ("มม.²/ม.", 14, "center")]
    t = V.temperature_steel(ds.slab_cm, ds.lane_width)
    rows, mark = [], None
    for slab, (lo, a, _m, trans) in sorted(V.TEMP_STEEL.items()):
        for lw, (tr, ta, _tm) in sorted(trans.items()):
            if t and t["slab"] == slab and t["lane"] == lw:
                mark = len(rows)
            rows.append([str(slab), lo.replace("RB", "").replace(" ม.", ""), f"{lw:.2f}",
                         tr.replace("RB", "").replace(" ม.", ""), f"{ta}"])
    yy = _marked_table(sh, x, y - 2.5, cols, rows, mark, 1.6, 3.4)
    sh.text((x, yy - 6), "ตารางที่ 2 TIE BARS / DOWEL BARS", 2.4, "left", "text", True)
    cols = [("หนา (ซม.)", 16, "center"), ("ชนิด", 22, "center"), ("Ø (มม.)", 14, "center"),
            ("ยาว (ซม.)", 16, "center"), ("@ (ซม.)", 16, "center")]
    rows = [["ทุกขนาด", "TIE BAR DB", "12", "50", "50"]]
    mark = None
    for slab, d, ln, sp in V.DOWELS:
        if mark is None and ds.slab_cm <= slab + 1e-6:
            mark = len(rows)
        rows.append([str(slab), "DOWEL RB", str(d), str(ln), str(sp)])
    _marked_table(sh, x, yy - 8.5, cols, rows, mark, 1.6, 3.6)


def _quantity_table(sh, ds, q, x, y):
    sh.text((x, y), "ปริมาณเหล็กและรอยต่อ", 2.4, "left", "text", True)
    b, r = q["bay"], q["road"]
    cols = [("รายการ", 46, "left"), ("ต่อแผ่น", 20, "right"), ("ทั้งสาย", 22, "right")]
    has = q["bays"] > 0

    def v(key, d=1):
        return f"{r[key]:,.{d}f}" if has else "-"
    rows = [["พื้นที่ผิว คสล. (ตร.ม.)", f"{b['area']:.1f}", v("area")],
            ["เหล็กตะแกรง/เหล็กเสริม (กก.)", f"{b['steel_kg']:.1f}", v("steel_kg")],
            [f"Dowel RB{q['dowel'][0]} (ท่อน)", f"{b['dowels']}", v("dowels", 0)],
            ["Dowel (กก.)", f"{b['dowel_kg']:.1f}", v("dowel_kg")],
            ["Tie bar DB12 (ท่อน)", f"{b['ties']}", v("ties", 0)],
            ["ยาแนวรอยต่อ (ม.)", f"{b['sealant']:.1f}", v("sealant")]]
    yy = D.table(sh, x, y - 2.5, cols, rows, 1.8, 4.4, 5.5)
    sh.text((x, yy - 3.2), (f"แผ่นยาว {ds.slab_length:g} ม. × กว้าง {ds.width:g} ม. · ถนนยาว "
                            f"{ds.length:,.1f} ม. = {q['bays']:,.1f} แผ่น") if has else
            "ความยาวถนน: วิเคราะห์แนวทางก่อนเพื่อคิดทั้งสาย", 1.6)


def asphalt_sheet(ds: Design) -> D.Sheet:
    sh = D.Sheet("SD-02", "แบบขยายชั้นทางลาดยางและริมขอบทาง", "ตามระบุ", "SD")
    B = ds.width / 2 + ds.shoulder
    span = min(B, 2.5)                                # the outer part, to the slope
    x0m = B - span
    fill_h = 0.40
    gz = _ext(ds, B) - ds.total - fill_h
    toe = B + (_ext(ds, B) - gz) * ds.fill_hv
    sc = D.fit_scale((toe - x0m + 0.3, 1.0), (170.0, 90.0), (10, 15, 20, 25, 30, 40, 50))
    k = 1000.0 / sc
    x, y = X0 + 18, Y1 - 40

    def P(xm, zm):
        return (x + (xm - x0m) * k, y + zm * k)
    items = []
    d = 0.0
    for i, (name, t) in enumerate(ds.layers):
        e0, e1 = _edge(ds, d), _edge(ds, d + t)
        top = [(xm, _ext(ds, xm) - d) for xm in sorted({x0m, ds.width / 2, B, e0}) if x0m <= xm <= e0]
        bot = [(xm, _ext(ds, xm) - d - t) for xm in sorted({x0m, ds.width / 2, B, e1}) if x0m <= xm <= e1]
        poly = [P(*p) for p in top + bot[::-1]]
        sh.fill(poly, "hatch", gray_of(name))
        sh.poly(poly, "wall", 0.25)
        xm = x0m + span * (0.20 + 0.12 * i)
        items.append((P(xm, _ext(ds, xm) - d - t / 2), f"{spec_of(name)} หนา {t * 100:g} ซม."))
        D._dim_v(sh, P(x0m, 0)[0] - 4, P(x0m, _ext(ds, x0m) - d - t)[1], P(x0m, _ext(ds, x0m) - d)[1],
                 f"{t * 100:g}")
        if i == 0:
            xm = x0m + span * 0.08
            items.append((P(xm, _ext(ds, xm) - t), "PRIME COAT ตาม มทถ. 225-2562"))
        elif "AC" in name or "แอสฟัลต์" in name or "Binder" in name:
            xm = x0m + span * 0.12
            items.append((P(xm, _ext(ds, xm) - d), "TACK COAT ตาม มทถ. 227-2562"))
        d += t
    sh.line(P(B, _ext(ds, B)), P(toe, gz), "wall", 0.35)
    sh.line(P(x0m, gz), P(toe + 0.3, gz), "wall", 0.35)
    sh.text(P((B + toe) / 2 + 0.1, (_ext(ds, B) + gz) / 2), f"SIDE SLOPE {ds.fill_hv:g}:1", 1.8, "left", "dim")
    items.append((P(B + (toe - B) * 0.25, gz + 0.12), EMBANKMENT))
    D.leaders(sh, items, P(toe + 0.3, 0)[0] + 6, "right", 5.0, 1.8)
    yd = P(0, _ext(ds, x0m))[1] + 10
    D._dim_h(sh, P(x0m, 0)[0], P(ds.width / 2, 0)[0], yd, "ผิวจราจร (ต่อ)")
    if ds.shoulder > 0:
        D._dim_h(sh, P(ds.width / 2, 0)[0], P(B, 0)[0], yd, f"ไหล่ทาง {ds.shoulder:.2f}")
        a = P(ds.width / 2 + ds.shoulder / 2, _ext(ds, ds.width / 2 + ds.shoulder / 2))
        sh.text((a[0], a[1] + 2.0), f"{ds.shoulder_slope:g}%", 2.0, "center", "dim")
    a = P(x0m + 0.3, _ext(ds, x0m + 0.3))
    sh.text((a[0], a[1] + 2.0), f"{ds.crown:g}%", 2.0, "center", "dim")
    D.caption(sh, (X0 + 90, Y1 - 128), "แบบขยายริมขอบทางและไหล่ทาง", f"1:{sc}")
    _standard_table(sh, ds, X0 + 188, Y1 - 140)
    D.notes_block(sh, X0 + 4, Y1 - 145, "ข้อกำหนดผิวทางลาดยาง", [
        "1. ผิว ASPHALT CONCRETE ใช้แอสฟัลต์ซีเมนต์ A.C. 60-70 ความหนาแต่ละชั้นไม่น้อยกว่า 0.04 ม. "
        "ตาม มทถ. 230-2562",
        "2. ก่อนปูผิวลาดยางต้องทำ PRIME COAT บนพื้นทางที่แห้งและสะอาด ตาม มทถ. 225-2562 "
        "และทิ้งไว้ให้แห้งก่อนปู",
        "3. ผิว AC สองชั้นขึ้นไป ให้ทำ TACK COAT ระหว่างชั้น ตาม มทถ. 227-2562",
        "4. ไหล่ทางลาดยางเช่นเดียวกับผิวจราจร หรือตามที่ระบุในแบบ ลาดออก "
        f"{ds.shoulder_slope:g}% ผิวจราจรลาด {ds.crown:g}%",
        "5. บดทับผิว AC ด้วยรถบดล้อเหล็กและล้อยาง จนได้ความแน่นตามข้อกำหนด อุณหภูมิขณะปูและบดตาม มทถ. 230-2562",
        "6. ตรวจระดับผิวด้วยไม้บรรทัดยาว 3.00 ม. ผิดได้ไม่เกิน 5 มม.",
    ], 2.0, 92)
    return sh


# ---------------------------------------------------------------------------
# SD-03 — notes and the calculation summary
# ---------------------------------------------------------------------------

def notes_sheet(ds: Design) -> D.Sheet:
    sh = D.Sheet("SD-03", "รายการประกอบแบบโครงสร้างทาง", "-", "SD")
    common = [
        "1. มิติต่างๆ มีหน่วยเป็นเมตร นอกจากระบุไว้เป็นอย่างอื่น",
        "2. คุณสมบัติวัสดุและวิธีก่อสร้าง นอกจากที่ระบุในแบบ ให้เป็นไปตามมาตรฐานงานทางหลวงท้องถิ่น "
        "มทถ. 101-2562 ถึง มทถ. 246-2562 และมาตรฐานทดสอบวัสดุงานทาง กรมทางหลวงชนบท เฉพาะส่วนที่เกี่ยวข้อง",
        "3. ดินเดิมหรือดินคันทางที่มีค่า CBR น้อยกว่า 4% ต้องออกแบบโครงสร้างคันทางเป็นพิเศษ "
        "วัสดุที่ใช้ทำคันทางต้องมี CBR ไม่น้อยกว่า CBR ของดินเดิม และไม่น้อยกว่า 4%",
        "4. ก่อสร้างคันทางบนลาดดินเดิม ให้ขุดเป็นขั้นบันได (BENCHING) กว้างไม่น้อยกว่า 0.50 ม. "
        "ตามรูปตัดการก่อสร้างลาดคันทางบนถนนเดิม",
        "5. ระดับน้ำใต้ดินต้องต่ำกว่าระดับโครงสร้างทาง (FORMATION LEVEL) ไม่น้อยกว่า 0.60 ม. "
        "จัดระบายน้ำทั้งผิวดินและใต้ดิน",
        f"6. ความลาดตัด/ถมคันทางตามตาราง หรือ SIDE SLOPE {ds.fill_hv:g}:1 BACK SLOPE {ds.cut_hv:g}:1 "
        "ตามแบบนี้ และปลูกหญ้าคลุมลาดคันทางตามแบบ ทถ-2-601",
        "7. ผู้รับจ้างต้องส่งตัวอย่างวัสดุและผลทดสอบให้คณะกรรมการตรวจรับพัสดุอนุมัติก่อนนำไปใช้",
    ]
    if ds.concrete:
        spec = [
            f"8. คอนกรีตผิวทาง กำลังอัดแท่งลูกบาศก์ 15×15×15 ซม. อายุ 28 วัน ไม่น้อยกว่า {ds.fc:,.0f} "
            "กก./ตร.ซม. ค่ายุบตัว (SLUMP) ไม่เกิน 7 ซม. ใช้ปูนซีเมนต์ปอร์ตแลนด์ประเภท 1 (มอก. 15)",
            "9. เหล็กเสริม มอก. 20 (เหล็กเส้นกลม) และ มอก. 24 (เหล็กข้ออ้อย) ตะแกรงเหล็กเชื่อมสำเร็จรูป "
            "(WIRE MESH) มอก. 737 กำลังครากไม่น้อยกว่า 5,500 กก./ตร.ซม. ใช้แทนเหล็กเส้นได้ตามตารางที่ 1 "
            "โดยต่อทาบไม่น้อยกว่า 1 ช่องตาราง + 5 ซม.",
            f"10. รอยต่อหดตัว (CONTRACTION JOINT) ตัดร่องด้วยเครื่องตัดคอนกรีต ลึก T/4 ทุกระยะ "
            f"{ds.slab_length:g} ม. ภายใน 4–24 ชม. หลังเท (ก่อนคอนกรีตแตกร้าวเอง)",
            "11. รอยต่อขยายตัว (EXPANSION JOINT) ทำเฉพาะที่ชนสะพาน โครงสร้าง ทางแยก "
            "หรือทุกระยะไม่เกิน 250 ม. ใช้ JOINT FILLER ชนิด NON-EXTRUDING (AASHTO M 153 / M 213)",
            "12. วัสดุยาแนวรอยต่อ ชนิดเทร้อน (CONCRETE JOINT SEALER HOT-POURED ELASTIC TYPE) ตาม มอก. 479",
            "13. เหล็กเดือย (DOWEL BAR) วางขนานแนวทางและผิวทาง ทาสีและทาน้ำมันหล่อลื่นครึ่งท่อน "
            "ด้านรอยต่อขยายตัวสวมปลอกโลหะหรือพลาสติก เว้นช่องว่างปลาย 25 มม.",
            "14. ผิวหน้าคอนกรีตทำให้หยาบโดยลากไม้กวาดหรือกระสอบตั้งฉากแนวทาง ร่องลึกไม่เกิน 2 มม.",
            "15. บ่มคอนกรีตต่อเนื่องไม่น้อยกว่า 7 วัน (ขังน้ำ คลุมกระสอบเปียก หรือสารเคมีบ่มคอนกรีต) "
            "เปิดการจราจรเมื่อกำลังอัดถึงร้อยละ 75 ของกำลังที่ออกแบบ",
            "16. แผ่นพลาสติกหนาไม่น้อยกว่า 0.07 มม. รองใต้แผ่นคอนกรีต ซ้อนทับกันไม่น้อยกว่า 0.30 ม.",
        ]
    else:
        spec = [
            "8. ผิวทาง ASPHALT CONCRETE ตาม มทถ. 230-2562 · PRIME COAT มทถ. 225-2562 · "
            "TACK COAT มทถ. 227-2562 · SURFACE TREATMENT มทถ. 226-2562",
            "9. พื้นทางหินคลุก มทถ. 203-2562 · รองพื้นทาง มทถ. 202-2562 · วัสดุคัดเลือก มทถ. 204-2562 · "
            "ไหล่ทาง มทถ. 205-2562 · คันทาง มทถ. 201-2562",
            "10. ความหนาผิวลาดยางแต่ละชั้นไม่น้อยกว่าที่ระบุในแบบ และผิว AC ไม่น้อยกว่า 0.04 ม.",
        ]
    D.notes_block(sh, X0 + 4, Y1 - 6, "รายการประกอบแบบ", common + spec, 2.2, 74)
    lines = _calc_lines(ds)
    yy = D.notes_block(sh, X0 + 170, Y1 - 6, "สรุปรายการคำนวณ", lines, 2.1, 70)
    _benching(sh, X0 + 178, min(yy - 12, Y0 + 70))
    return sh


def _benching(sh, x, y):
    """รูปตัดการก่อสร้างลาดคันทางบนถนนเดิม — the new fill keyed into the
    old slope in steps at least 0.50 m wide (not to scale)."""
    old = [(x, y + 40), (x + 30, y + 40), (x + 80, y + 5)]
    sh.poly(old, "hidden", 0.35, False, True)
    sh.text((x + 2, y + 41.5), "ระดับผิวจราจรเดิม", 1.7, "left", "hidden")
    new = [(x, y + 46), (x + 38, y + 46), (x + 108, y + 5)]
    sh.poly(new, "wall", 0.45, False)
    sh.text((x + 2, y + 47.5), "ระดับก่อสร้าง", 1.7)
    steps = []
    px, py = x + 30, y + 40
    for _i in range(4):
        steps += [(px, py), (px, py - 8.0), (px + 12.0, py - 8.0)]
        px, py = px + 12.0, py - 8.0
    sh.poly(steps, "wall", 0.35, False)
    for i in range(4):
        sx, sy = x + 30 + 12.0 * i, y + 40 - 8.0 * (i + 1)
        sh.fill([(sx, sy), (sx + 12.0, sy), (sx + 12.0, sy + 8.0 * (1 - (i + 1) / 5)),
                 (sx, sy + 8.0)], "hatch", 0.88)
    D._dim_h(sh, x + 30, x + 42, y + 29, "0.50 (MIN.)")
    D._dim_v(sh, x + 28, y + 32, y + 40, "n")
    sh.text((x + 46, y + 20), "ดินตัด (ขั้นบันได)", 1.7)
    sh.text((x + 84, y + 26), "ดินถมใหม่บดอัดเป็นชั้น", 1.7)
    sh.text((x + 55, y - 3), "รูปตัดการก่อสร้างลาดคันทางบนถนนเดิม (ไม่ตามมาตราส่วน)", 2.4, "center",
            "text", True)
    sh.text((x + 55, y - 7), "งานตัดได้แก่ งานตัดดิน งานตัดหินผุ งานตัดหินแข็ง · ขั้น n ตามดุลยพินิจผู้ควบคุมงาน",
            1.7, "center")


def _calc_lines(ds) -> list:
    r = ds.res
    if ds.method == "ai" and r is not None:
        i = r.inp
        out = ["วิธี Asphalt Institute ฉบับที่ 8 (1970) — คู่มือกรมทางหลวง",
               f"N = IDT × A × B = {i.idt:,.0f} × {i.heavy_pct / 100:.4f} × {r.lane_pct / 100:.2f} "
               f"= {r.trucks:,.1f} คัน/วัน",
               f"S = W × 0.8 × 0.5 = {r.axle_t:.2f} ตัน ({r.axle_lb:,.0f} ปอนด์) ; W = {r.gross_lb:,.0f} ปอนด์",
               f"log ITN = -10.68 + 3.4 log S + 1.33 log W + 1.05 log N => ITN = {r.itn:,.1f}",
               f"AF = [(1+r)^n - 1] / 20r = {r.factor:.3f} ; DTN = {r.dtn:,.0f}",
               f"TA = 2.54 (9.19 + 3.97 log DTN) / CBR^0.4 = {r.ta:.2f} ซม. (CBR {i.cbr:g}%)"]
        for name, t, sr, _c, eq in r.layers:
            out.append(f"   {name} {t:g} ซม. ÷ Sr {sr:g} = {eq:.2f} ซม.")
        for over, cbr, need, have, ok in r.checks:
            out.append(f"ตรวจเหนือ{over} (CBR {cbr:g}%): ต้องการ {need:.2f} มี {have:.2f} => "
                       + ("ผ่าน" if ok else "ไม่ผ่าน"))
        out += [f"(!) {w}" for w in r.warnings]
        return out
    if ds.method == "rn29" and r is not None:
        i = r.inp
        out = ["วิธี Road Note 29 — รายการคำนวณโครงสร้างถนน คสล. กรมทางหลวงชนบท"]
        out += [f"{n}: {d:,.2f} คัน/วัน (ปัจจัยช่องจราจร {r.lane_factor:g})" for n, d in r.per_day]
        out.append(f"[(1+r)^n - 1]/r = {r.growth_sum:.3f} (r {i.growth_pct:g}%, n {i.years:g} ปี)")
        for (n, c, v, e) in r.esa_rows:
            out.append(f"{n}: {c:,.0f} คัน × VEF {v:.3f} = {e:,.0f} ESA")
        out += [f"ESA สะสม {r.esa:,.0f} ({r.esa / 1e6:.3f} × 10^6)",
                f"แผนภูมิรูปที่ 3.16: {r.slab_chart_mm:.0f} มม. => ใช้ผิว คสล. {r.slab_cm:g} ซม.",
                f"ดินคันทาง{r.soil} => รองพื้นทางต้องการ {r.subbase_need:g} ซม. ใช้ {r.subbase_cm:g} ซม.",
                f"As = W·L·f/2fs: ตามยาว {r.as_long:.3f} => {r.steel_long[0]} ({r.steel_long[1]:.3f}) ซม.²/ม.",
                f"As ตามขวาง {r.as_trans:.3f} => {r.steel_trans[0]} ({r.steel_trans[1]:.3f}) ซม.²/ม.",
                f"Dowel {r.joints['dowel']} · Tie {r.joints['tie']}",
                "สรุป: " + ("ผ่าน" if r.ok else "ไม่ผ่าน")]
        out += [f"(!) {w}" for w in r.warnings]
        return out
    return ["ยังไม่ได้คำนวณความหนาโครงสร้างทางในโปรแกรม — แบบนี้ใช้ความหนาตามตารางชั้นทาง",
            "ใช้ปุ่ม «ออกแบบความหนาโครงสร้างทาง» ในแผงออกแบบถนนเพื่อใส่รายการคำนวณ"]


def detail_sheets(settings, pave=None, length=0.0, info=None) -> list:
    """SD-01 … SD-03 for the road's template and pavement."""
    ds = Design(settings, pave, length)
    if not ds.layers:
        return []
    out = [section_sheet(ds, info)]
    out.append(joints_sheet(ds) if ds.concrete else asphalt_sheet(ds))
    out.append(notes_sheet(ds))
    if ds.method == "rn29" and ds.res is not None:
        out.append(rn29_sheet(ds))
    cf = cutfill_sheet(ds)
    cf.code = f"SD-{len(out) + 1:02d}"
    out.append(cf)
    return out


# ---------------------------------------------------------------------------
# รูปตัดตามขวางแสดงดินตัดและดินถม (ทถ-2-201(1)) and the bill of quantities
# ---------------------------------------------------------------------------

#: The allowances of the bill (the CM+RDD way of the DRR price sheets):
#: sand and laterite are bought loose and compacted, concrete and steel
#: lose some on site.
ALLOW = {"sand": 0.15, "laterite": 0.30, "concrete": 0.05, "steel": 0.05, "plastic": 0.10}
WIRE_PER_KG = 0.02          # ลวดผูกเหล็ก 20 กก. ต่อเหล็ก 1 ตัน
SEAL_L_PER_M = 0.20         # ยาแนวร่อง 1 × 2 ซม. = 0.20 ลิตร/ม.


def _layer_t(ds, *words):
    for n, t in ds.layers[1:]:
        if any(w in n for w in words):
            return t
    return 0.0


def boq(ds) -> list:
    """[(item, unit, per bay, whole road)] — the road's bill of quantities.
    Concrete: per slab bay (slab length × road width) like the DRR / CM
    price sheets: grading, sand cushion, concrete, steel, dowels, ties, tie
    wire, plastic sheet, side forms, joint sealant, the sub-base; asphalt:
    per layer. ``whole road`` is None when the length is not known."""
    rows = []
    if ds.concrete:
        q = quantities(ds)
        b, n = q["bay"], q["bays"]
        L, w, t = ds.slab_length, ds.width, ds.slab_cm / 100.0
        sand = _layer_t(ds, "ทราย")
        sub = _layer_t(ds, "รองพื้นทาง")
        steel = b["steel_kg"] * (1 + ALLOW["steel"])
        rows += [("งานปรับเกลี่ยและบดอัดพื้นที่", "ตร.ม.", L * w),
                 (f"ทรายหยาบรองพื้น หนา {sand * 100:g} ซม. (เผื่อยุบตัว {ALLOW['sand']:.0%})", "ลบ.ม.",
                  L * w * sand * (1 + ALLOW["sand"])) if sand else None,
                 (f"รองพื้นทางลูกรัง/วัสดุ หนา {sub * 100:g} ซม. (เผื่อบดอัด {ALLOW['laterite']:.0%})",
                  "ลบ.ม.", L * w * sub * (1 + ALLOW["laterite"])) if sub else None,
                 ("แผ่นพลาสติกรองใต้แผ่นคอนกรีต (ซ้อนทับ 10%)", "ตร.ม.", L * w * (1 + ALLOW["plastic"])),
                 ("ไม้แบบข้าง 2 × L × t", "ตร.ม.", 2 * L * t),
                 (f"คอนกรีต fc' {ds.fc:,.0f} กก./ตร.ซม. หนา {t * 100:g} ซม. (เผื่อ {ALLOW['concrete']:.0%})",
                  "ลบ.ม.", L * w * t * (1 + ALLOW["concrete"])),
                 (f"เหล็กเสริม {q['long'][0]} / {q['trans'][0]} (เผื่อ {ALLOW['steel']:.0%})", "กก.", steel),
                 (f"เหล็กเดือย Dowel RB{q['dowel'][0]} ยาว {q['dowel'][1]:.2f} ม.", "ท่อน", b["dowels"]),
                 ("เหล็กเดือย Dowel (น้ำหนัก)", "กก.", b["dowel_kg"]),
                 ("เหล็กยึด Tie bar DB12 ยาว 0.50 ม. @0.50", "ท่อน", b["ties"]) if b["ties"] else None,
                 ("ลวดผูกเหล็ก (20 กก./ตัน)", "กก.", (steel + b["dowel_kg"] + b["tie_kg"]) * WIRE_PER_KG),
                 ("ยาแนวรอยต่อ (ร่อง 1 × 2 ซม.)", "ลิตร", b["sealant"] * SEAL_L_PER_M)]
        return [(a, u, v, v * n if n else None) for a, u, v in (r for r in rows if r)]
    # asphalt: per 1 m of road and for the whole length
    B = ds.width + 2 * ds.shoulder
    for name, t in ds.layers:
        if any(w in name for w in ("AC", "แอสฟัลต์", "DBST", "ลาดยาง")):
            rows.append((f"{name} หนา {t * 100:g} ซม.", "ตร.ม.", ds.width))
        else:
            rows.append((f"{name} หนา {t * 100:g} ซม. (เผื่อบดอัด {ALLOW['laterite']:.0%})", "ลบ.ม.",
                         B * t * (1 + ALLOW["laterite"])))
    rows.insert(1, ("PRIME COAT", "ตร.ม.", ds.width))
    return [(a, u, v, v * ds.length if ds.length else None) for a, u, v in rows]


CUTFILL_NOTES = [
    "1. คุณสมบัติของวัสดุ นอกจากที่ระบุในแบบให้เป็นไปตามมาตรฐานงานทางหลวงท้องถิ่น มทถ. 101–246 "
    "เฉพาะส่วนที่เกี่ยวข้อง",
    "2. จำนวนขั้นบันไดมากน้อยขึ้นอยู่กับความสูงของคันทางเดิม (รูปตัดการก่อสร้างลาดคันทางบนถนนเดิม)",
    "3. เขตทางขึ้นอยู่กับสภาพพื้นที่ — ระยะในรูปเป็นระยะต่ำสุดที่ต้องการของรูปตัดนี้",
    "4. ร่องน้ำข้างทางในเขตดินตัด ลึกจากระดับก่อสร้างไม่น้อยกว่า 1.25 ม. ท้องร่องกว้าง 0.00–1.00 ม. "
    "ตามปริมาณน้ำ และลาดท้องร่องตามแนวทางไม่น้อยกว่า 0.5% ลงสู่ทางน้ำหรือท่อลอด",
    "5. ความสูงตัดหรือถมเกิน 3.00 ม. ให้ใช้ลาดตามรูปตัดมาตรฐาน ทางที่ถมสูง หรือตัดลึกมาก (ทถ-2-501)",
    "6. ถ้าไม่ได้กำหนดเป็นอย่างอื่นในแบบรูปตัดตามขวาง ค่า BACK SLOPE และ SIDE SLOPE ใช้ตามตาราง (SD-01)",
    "7. วัสดุทรายหยาบต้องเป็นวัสดุ NON PLASTIC ขนาดใหญ่สุดไม่เกิน 3/8\" ผ่านตะแกรงเบอร์ 200 ไม่เกินร้อยละ 10",
]


def cutfill_sheet(ds: Design) -> D.Sheet:
    """รูปตัดตามขวางแสดงดินตัดและดินถม (as ทถ-2-201(1)): the left half on
    fill down to the ground at the SIDE SLOPE, the right half in cut with
    the side ditch (>= 1.25 m under the finish, bottom 0.00–1.00 m) and the
    BACK SLOPE up to the ground; the right-of-way lines; the bill of
    quantities and the notes."""
    sh = D.Sheet("SD-05", "รูปตัดตามขวางแสดงดินตัดและดินถม และบัญชีปริมาณงาน", "ตามระบุ", "SD")
    B = ds.width / 2 + ds.shoulder
    zB = _surface(ds, B)

    def g(x):                                     # the natural ground, rising to the right
        return -0.9 - 0.10 * B + 0.22 * x
    # fill side: from the shoulder edge down at SIDE SLOPE to the ground
    xf = -B
    while _surface(ds, B) - (-xf - B) / ds.fill_hv > g(xf) and xf > -B - 30:
        xf -= 0.05
    zf = g(xf)
    # cut side: side slope to the ditch, bottom 0.60 drawn, back slope up
    dz = 1.25
    xd0 = B + dz * ds.fill_hv
    zd = zB - dz
    xd1 = xd0 + 0.60
    xb = xd1
    while zd + (xb - xd1) / ds.cut_hv < g(xb) and xb < xd1 + 40:
        xb += 0.05
    zb = g(xb)
    row = (xf - 1.5, xb + 1.5)
    span = row[1] - row[0] + 2
    sc = D.fit_scale((span, 6.0), (300.0, 80.0), (25, 30, 40, 50, 60, 75, 100, 125, 150, 200))
    k = 1000.0 / sc
    cx = X0 + 10 + (-row[0] + 1) * k
    cy = Y1 - 72

    def P(x, z):
        return (cx + x * k, cy + z * k)
    # ground (dashed beyond the works) and the earthworks
    sh.line(P(row[0] - 1, g(row[0] - 1)), P(row[1] + 1, g(row[1] + 1)), "hidden", 0.3, True)
    fill = [P(xf, zf), P(-B, zB), P(-ds.width / 2, _surface(ds, ds.width / 2)), P(0, _surface(ds, 0))]
    sh.fill(fill + [P(0, g(0)) if g(0) < _surface(ds, 0) else P(0, _surface(ds, 0))], "hatch", 0.90)
    t = ds.total
    top = [P(x, _surface(ds, x)) for x in (-B, -ds.width / 2, 0.0, ds.width / 2, B)]
    bot = [P(x, _surface(ds, x) - t) for x in (B, ds.width / 2, 0.0, -ds.width / 2, -B)]
    sh.fill(top + bot, "hatch", 0.55)
    sh.poly(top + bot, "wall", 0.35)
    sh.poly([P(xf, zf), P(-B, zB)], "wall", 0.45, False)
    sh.poly([P(B, zB), P(xd0, zd), P(xd1, zd), P(xb, zb)], "wall", 0.45, False)
    sh.text(P((xf - B) / 2 - 0.4, (zf + zB) / 2), f"SIDE SLOPE {ds.fill_hv:g}:1", 1.9, "right", "dim")
    sh.text(P((B + xd0) / 2 + 0.3, (zB + zd) / 2 + 0.2), f"SIDE SLOPE {ds.fill_hv:g}:1", 1.9, "left", "dim")
    sh.text(P((xd1 + xb) / 2 + 0.5, (zd + zb) / 2), f"BACK SLOPE {ds.cut_hv:g}:1", 1.9, "left", "dim")
    sh.line(P(B + 0.2, zB), P(xd1 + 0.3, zB), "dim", 0.13, True)
    D._dim_v(sh, P(xd1, 0)[0] + 1.0, P(0, zd)[1], P(0, zB)[1], "1.25 (MIN)")
    D._dim_h(sh, P(xd0, 0)[0], P(xd1, 0)[0], P(0, zd)[1] - 4, "0.00-1.00")
    sh.text((P(xd0, 0)[0], P(0, zd)[1] - 9), "ท้องร่องกว้าง 0.00–1.00 ม.", 1.8)
    xm = (xf - B) / 2
    sh.text(P(xm, (g(xm) + zB - (-xm - B) / ds.fill_hv) / 2 - 0.1), "ดินถม", 2.4, "center", "text", True)
    xc = xd1 + 1.2
    sh.text(P(xc + 0.3, (zd + 1.2 / ds.cut_hv + g(xc)) / 2), "ดินตัด", 2.4, "center", "text", True)
    # the centre line, widths, crossfalls, the right of way
    yt = P(0, 0)[1]
    sh.line((P(0, 0)[0], yt + 26), (P(0, 0)[0], P(0, g(0))[1] - 6), "grid", 0.18, True)
    sh.text((P(0, 0)[0], yt + 27), "CL", 2.8, "center", "grid")
    sh.text((P(0, 0)[0] + 1.5, yt + 2.0), "ระดับก่อสร้าง", 1.8, "left", "dim")
    xs = [-B, -ds.width / 2, 0.0, ds.width / 2, B]
    names = ["ไหล่ทาง", "ครึ่งผิวจราจร", "ครึ่งผิวจราจร", "ไหล่ทาง"]
    for (a, b), nm in zip(zip(xs, xs[1:]), names):
        if b - a < 1e-6:
            continue
        D._dim_h(sh, P(a, 0)[0], P(b, 0)[0], yt + 9, f"{b - a:.2f}")
        sh.text(((P(a, 0)[0] + P(b, 0)[0]) / 2, yt + 13), nm, 1.8, "center", "dim")
    for sg in (-1, 1):
        a = P(sg * ds.width * 0.25, _surface(ds, ds.width * 0.25))
        sh.text((a[0], a[1] + 2.0), f"{ds.crown:.1f}%", 1.9, "center", "dim")
    for x in row:
        sh.line(P(x, g(x) - 0.3), (P(x, 0)[0], yt + 22), "hidden", 0.25, True)
        sh.text((P(x, 0)[0], yt + 23.5), "เขตทาง", 2.0, "center", "text", True)
    D._dim_h(sh, P(row[0], 0)[0], P(row[1], 0)[0], yt + 19, "ขึ้นอยู่กับสภาพพื้นที่")
    D.caption(sh, (X0 + 160, Y1 - 112), "รูปตัดตามขวางแสดงดินตัดและดินถม", f"1:{sc} (ทถ-2-201(1))")
    # the bill of quantities
    rows = boq(ds)
    per = "ต่อแผ่น" if ds.concrete else "ต่อ 1 ม."
    head = (f"บัญชีปริมาณงาน — แผ่นพื้น {ds.slab_length:g} × {ds.width:g} ม." if ds.concrete
            else "บัญชีปริมาณงานถนนลาดยาง")
    sh.text((X0 + 4, Y1 - 128), head, 2.8, "left", "text", True)
    cols = [("รายการ", 112, "left"), ("หน่วย", 14, "center"), (per, 22, "right"),
            (f"ทั้งสาย {ds.length:,.0f} ม." if ds.length else "ทั้งสาย", 30, "right")]
    tab = [[a, u, f"{v:,.2f}", f"{w:,.2f}" if w is not None else "-"] for a, u, v, w in rows]
    yy = D.table(sh, X0 + 4, Y1 - 131, cols, tab, 1.9, 4.6, 5.5)
    sh.text((X0 + 4, yy - 3.5), "ปริมาณสุทธิรวมค่าเผื่อตามที่ระบุ · ใช้ประกอบ ปร.4 / ปร.5 "
            "(ค่าดำเนินการและภาษี Factor F ตามตารางกรมบัญชีกลาง)", 1.7)
    D.notes_block(sh, X0 + 192, Y1 - 128, "หมายเหตุ", CUTFILL_NOTES, 2.0, 66)
    sh.scale = f"1:{sc}"
    return sh


# ---------------------------------------------------------------------------
# Road Note 29 — the design chart with its reading, and the trucks
# ---------------------------------------------------------------------------

#: The trucks of the DRR sheet with the gross weights the law allows today
#: (ประกาศกรมทางหลวง เรื่อง น้ำหนักรถบรรทุก: 6 ล้อ 2 เพลา ≤ 15 ตัน,
#: 10 ล้อ 3 เพลา ≤ 25 ตัน).
TRUCK_LEGAL = {"6": ("รถบรรทุก 6 ล้อ 2 เพลา", 15.0), "10": ("รถบรรทุก 10 ล้อ 3 เพลา", 25.0)}
RED = (210, 30, 30)
TRUCK_RGB = {"cab": (40, 70, 120), "body": (150, 150, 150), "wheel": (25, 25, 25),
             "tag": (40, 120, 220)}


def _lx(v):
    return math.log10(max(min(v, 100.0), 0.01))


def rn29_chart(sh, box, msa: float, chart_mm: float, slab_cm: float = 0.0,
               cbr: float = 5.0, reinforced: bool = True):
    """รูปที่ 3.16 drawn to scale in ``box`` (paper mm) with the reading in
    red: a vertical line at the project's ESA, a horizontal one at the
    thickness read off the curve, their crossing marked; the slab used
    dashed when it is thicker."""
    x0, y0, x1, y1 = box
    L, B, R, T = x0 + 13, y0 + 18, x1 - 9, y1 - 3

    def X(v):
        return L + (_lx(v) + 2.0) / 4.0 * (R - L)

    def Y(mm):
        return B + max(min(mm, 300.0), 0.0) / 300.0 * (T - B)
    for d in range(-2, 2):                                   # log grid
        for m in range(1, 10):
            v = m * 10.0 ** d
            sh.line((X(v), B), (X(v), T), "hidden", 0.25 if m == 1 else 0.10)
    sh.line((X(100), B), (X(100), T), "hidden", 0.25)
    for mm in range(0, 301, 10):
        sh.line((L, Y(mm)), (R, Y(mm)), "hidden", 0.25 if mm % 50 == 0 else 0.10)
    sh.rect(L, B, R, T, "wall", 0.35)
    for mm in range(0, 301, 50):
        sh.text((L - 1.5, Y(mm) - 0.8), f"{mm}", 2.0, "right")
        sh.text((R + 1.5, Y(mm) - 0.8), f"{mm}", 2.0, "left")
    for v, t in ((0.01, "0.01"), (0.02, "0.02"), (0.04, "0.04"), (0.1, "0.10"), (0.2, "0.20"),
                 (0.4, "0.40"), (1.0, "1.0"), (2.0, "2.0"), (4.0, "4.0"), (10.0, "10"),
                 (20.0, "20"), (40.0, "40"), (100.0, "100")):
        sh.text((X(v), B - 4.2), t, 2.0, "center")
    sh.text(((L + R) / 2, B - 9.5), "Cumulative number of standard axles (× 10^6)", 2.4, "center",
            "text", True)
    sh.text((L - 9.5, (B + T) / 2), "Slab thickness (mm)", 2.4, "center", "text", True, angle=90)
    # the curves
    pts = []
    for i in range(0, 161):
        v = 10 ** (-2 + 4 * i / 160)
        pts.append((X(v), Y(V._log_interp(V.RN29_REINFORCED, v))))
    sh.poly(pts, "wall", 0.5, False)
    un = [(X(v), Y(t)) for v, t in V.RN29_UNREINFORCED]
    sh.poly(un, "wall", 0.4, False)
    sh.line((X(0.01), Y(175)), (X(1.4), Y(175)), "wall", 0.3, True)
    sh.text((X(0.012), Y(176) + 1.0), "Alternative design for unreinforced concrete (heavy construction "
            "traffic)", 1.6)
    sh.text((X(0.012), Y(149) + 1.0), "Unreinforced concrete", 1.7)
    sh.text((X(0.012), Y(118)), "Reinforced concrete", 1.7)
    sh.text((X(12.0), Y(182)), "Normal subgrades (CBR 2–15 %)", 1.7)
    sh.text((X(0.012), Y(285)), "CBR 15% ขึ้นไป ลดความหนา 25 มม. · CBR 2% หรือน้อยกว่า เพิ่ม 25 มม.", 1.7)
    # the reading
    if msa > 0:
        on_curve = V.rn29_slab_mm(msa, 5.0, reinforced) if chart_mm <= 0 else chart_mm
        xv, yv = X(msa), Y(on_curve)
        sh.line((xv, B), (xv, T), "roof", 0.45)
        sh.line((L, yv), (R, yv), "roof", 0.45)
        sh.circle((xv, yv), 1.2, "roof", 0.4)
        sh.text((xv + 1.2, B + 2.0), f"ESA = {msa:,.3f} × 10^6", 2.0, "left", "roof", True)
        sh.text((L + 1.5, yv + 1.2), f"{on_curve:.1f} มม.", 2.2, "left", "roof", True)
        adj = (-25 if cbr >= 15 else 25 if cbr <= 2 else 0)
        # the value the program reads off the curve, unrounded, one line
        # under the chart (the designer compares it with his own reading)
        raw = V.rn29_slab_mm(msa, 5.0, reinforced)
        sh.text(((L + R) / 2, y0 + 1.5), reading_text(msa, raw, chart_mm, adj), 2.3, "center",
                "roof", True)
        if adj:
            sh.text((L + 1.5, yv - 3.4), f"ปรับตาม CBR {adj:+d} มม. = {on_curve + adj:.0f} มม.", 1.8, "left",
                    "roof")
        if slab_cm and slab_cm * 10 > on_curve + adj + 0.5:
            ys = Y(slab_cm * 10)
            sh.line((L, ys), (R, ys), "dim", 0.35, True)
            sh.text((R - 1.5, ys + 1.0), f"ใช้ผิวคอนกรีตหนา {slab_cm:g} ซม.", 2.0, "right", "dim", True)


def reading_text(msa: float, raw_mm: float, chart_mm: float = 0.0, adj: int = 0) -> str:
    """«ค่าที่โปรแกรมอ่านได้จากกราฟ …» — the curve's value at the ESA to
    0.1 mm (and in cm to 0.01), as the sheet and the calculation print it."""
    t = (f"ค่าที่โปรแกรมอ่านได้จากกราฟ ที่ ESA {msa:,.3f} × 10^6 = {raw_mm:.1f} มม. "
         f"({raw_mm / 10:.2f} ซม.)")
    if adj:
        t += f" ; ปรับตาม CBR {adj:+d} มม. = {raw_mm + adj:.1f} มม."
    if chart_mm:
        t += f" ; ผู้ออกแบบอ่านได้ {chart_mm:g} มม."
    return t


def truck_figure(sh, x, y, w, axles, efs, title, gross, n_wheels):
    """A truck seen from the side (facing left) at paper ``x, y`` (the
    ground, left end) ``w`` mm long: the load on every axle with its
    equivalence factor, single / tandem tags, and the legal gross weight."""
    h = w * 0.42
    r = w * 0.065
    n = len(axles)
    pos = [0.17] + ([0.78] if n == 2 else [0.70, 0.84])
    # body
    cab = [(x + 0.02 * w, y + 2 * r), (x + 0.27 * w, y + 2 * r), (x + 0.27 * w, y + 0.78 * h),
           (x + 0.12 * w, y + 0.78 * h), (x + 0.04 * w, y + 0.52 * h), (x + 0.02 * w, y + 0.50 * h)]
    sh.fill(cab, "hatch", 0.3, TRUCK_RGB["cab"])
    sh.poly(cab, "wall", 0.25)
    win = [(x + 0.13 * w, y + 0.52 * h), (x + 0.24 * w, y + 0.52 * h), (x + 0.24 * w, y + 0.72 * h),
           (x + 0.14 * w, y + 0.72 * h), (x + 0.07 * w, y + 0.52 * h)]
    sh.fill(win, "hatch", 0.9, (205, 225, 240))
    bx = [(x + 0.30 * w, y + 2 * r), (x + 0.98 * w, y + 2 * r), (x + 0.98 * w, y + h), (x + 0.30 * w, y + h)]
    sh.fill(bx, "hatch", 0.6, TRUCK_RGB["body"])
    sh.poly(bx, "wall", 0.25)
    sh.line((x + 0.02 * w, y + 1.6 * r), (x + 0.98 * w, y + 1.6 * r), "wall", 0.6)
    tags = []
    for i, (p, t) in enumerate(zip(pos, axles)):
        cx = x + p * w
        sh.fill([(cx + r * math.cos(a / 12 * 2 * math.pi), y + r + r * math.sin(a / 12 * 2 * math.pi))
                 for a in range(12)], "hatch", 0.1, TRUCK_RGB["wheel"])
        sh.circle((cx, y + r), r * 0.45, "hidden", 0.2)
        sh.line((cx, y - 1.0), (cx, y - 6.0), "roof", 0.35)                 # the load on the axle
        sh.poly([(cx, y - 0.6), (cx - 0.9, y - 2.4), (cx + 0.9, y - 2.4)], "roof", 0.3)
    # the loads: one per single axle, one for the tandem
    if n == 2:
        marks = [(pos[0], f"{axles[0]:g} ตัน", f"EF {efs[0]:.4f}"),
                 (pos[1], f"{axles[1]:g} ตัน", f"EF {efs[1]:.4f}")]
    else:
        marks = [(pos[0], f"{axles[0]:g} ตัน", f"EF {efs[0]:.4f}"),
                 ((pos[1] + pos[2]) / 2, f"{axles[1]:g} + {axles[2]:g} ตัน",
                  f"EF {efs[1]:.4f} × 2")]
    for p, a, b in marks:
        sh.text((x + p * w, y - 9.0), a, 2.2, "center", "roof", True)
        sh.text((x + p * w, y - 12.2), b, 1.8, "center", "dim")
    sh.line((x - 2, y), (x + w + 2, y), "wall", 0.35)
    # single / tandem tags
    groups = [("เพลาเดี่ยว", pos[0])]
    groups.append(("เพลาเดี่ยว", pos[1]) if n == 2 else ("เพลาคู่", (pos[1] + pos[2]) / 2))
    for i, (label, p) in enumerate(groups):
        tx = x + (p - 0.10 if i == 0 else p + 0.04) * w
        ty = y + h + 6.0
        tw = 15.0
        sh.fill([(tx - tw / 2, ty - 1.4), (tx + tw / 2, ty - 1.4), (tx + tw / 2, ty + 3.4), (tx - tw / 2, ty + 3.4)],
                "hatch", 0.5, TRUCK_RGB["tag"])
        sh.text((tx, ty), label, 2.4, "center", "title", True)
        tags.append(((tx, ty - 1.4), (x + p * w, y + 2 * r)))
    for a, b in tags:
        sh.line(a, b, "dim", 0.25)
    sh.text((x + w / 2, y + h + 17.0), title, 2.6, "center", "text", True)
    sh.text((x + w / 2, y + h + 12.8), f"น้ำหนักรวมไม่เกิน {gross:g} ตัน (ตามกฎหมาย)", 2.0, "center")
    sh.text((x + w / 2, y - 17.0), "EF = " + " + ".join(f"{e:.4f}" for e in efs)
            + f" = {sum(efs):.4f}", 2.0, "center")
    _ = n_wheels


def trucks_block(sh, x, y, w_each, trucks, gap=18.0):
    """The trucks of the design side by side (``trucks``: V.Truck list)."""
    for i, tr in enumerate(trucks):
        n = len(tr.axles)
        title, gross = TRUCK_LEGAL["6" if n == 2 else "10"]
        efs = [V.equivalence_factor(a) for a in tr.axles]
        truck_figure(sh, x + i * (w_each + gap), y, w_each, tr.axles, efs, title,
                     sum(tr.axles) if abs(sum(tr.axles) - gross) > 0.01 else gross, 6 if n == 2 else 10)


def rn29_sheet(ds: Design):
    """SD-04 กราฟออกแบบความหนาผิวคอนกรีต Road Note 29 — the chart read in
    red, the trucks with their axle loads, the ESA table."""
    r = ds.res
    sh = D.Sheet("SD-04", "กราฟออกแบบความหนาผิวคอนกรีต (Road Note 29)", "-", "SD")
    i = r.inp
    rn29_chart(sh, (X0 + 2, Y1 - 150, X0 + 210, Y1 - 4), r.esa / 1e6,
               float(i.chart_mm or 0.0), r.slab_cm, i.cbr, i.reinforced)
    sh.text((X0 + 106, Y1 - 160), "รูปที่ 3.16 แผนภูมิกำหนดความหนาผิวทางคอนกรีต ตามวิธี Road Note 29", 2.8,
            "center", "text", True)
    sh.text((X0 + 106, Y1 - 165), f"เส้นสีแดง: ESA สะสม {r.esa:,.0f} ({r.esa / 1e6:.3f} × 10^6) => "
            f"ความหนาจากแผนภูมิ {r.slab_chart_mm:.0f} มม. => ใช้ผิวคอนกรีต {r.slab_cm:g} ซม.", 2.2, "center")
    trucks_block(sh, X0 + 224, Y1 - 52, 44.0, i.trucks, 14.0)
    sh.text((X0 + 222, Y1 - 6), "น้ำหนักลงเพลารถบรรทุก (2.3)", 2.8, "left", "text", True)
    cols = [("ชนิด", 34, "left"), ("จำนวนสะสม (คัน)", 26, "right"), ("VEF × สัดส่วน", 22, "right"),
            ("ESA", 26, "right")]
    rows = [[n, f"{c:,.0f}", f"{v:.3f}", f"{e:,.0f}"] for n, c, v, e in r.esa_rows]
    rows.append(["รวม", "", "", f"{r.esa:,.0f}"])
    sh.text((X0 + 222, Y1 - 100), "Cumulative Equivalent Standard Axles (2.4)", 2.8, "left", "text", True)
    D.table(sh, X0 + 222, Y1 - 103, cols, rows, 2.0, 5.5, 6.5)
    D.notes_block(sh, X0 + 222, Y1 - 140, "หมายเหตุ", [
        f"1. ปัจจัยช่องจราจร {r.lane_factor:g} · Growth {i.growth_pct:g}% · อายุออกแบบ {i.years:g} ปี",
        f"2. สัดส่วนรถบรรทุกที่บรรทุกของ : รถเปล่า = {i.loaded_pct:g} : {100 - i.loaded_pct:g}",
        "3. น้ำหนักลงเพลาตามรายการคำนวณของกรมทางหลวงชนบท (6 ล้อ 4 + 11 ตัน · 10 ล้อ 5 + 10 + 10 ตัน) "
        "น้ำหนักรวมไม่เกินที่กฎหมายกำหนด",
        "4. Equivalence Factor จากตาราง Equivalent factor and damaging power of different axle loads "
        "(interpolate ระหว่างค่าในตาราง)",
    ], 2.0, 70)
    return sh
