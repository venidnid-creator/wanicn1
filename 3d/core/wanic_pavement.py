"""Pavement thickness design — การออกแบบความหนาโครงสร้างชั้นทาง.

Two methods in use in Thailand, as the DOH / DRR manuals and the course
material give them:

* **Asphalt Institute (MS-1) 8th ed., 1970** for asphalt roads (ถนนลาดยาง),
  the method of the DOH manual «คู่มือการออกแบบโครงสร้างถนนลาดยางโดยวิธี
  Asphalt Institute Method ฉบับที่ 8 (1970)»: DTN from the traffic, the
  full-depth asphalt thickness TA from the subgrade CBR, the layers by the
  substitution ratios and TA checked over every layer.
* **TRRL Road Note 29** for concrete roads (ถนน คสล.), as the DRR
  calculation sheet does it: cumulative standard axles (ESA) of the
  6- and 10-wheel trucks, the slab from Fig. 3.16, the sub-base from
  Table 3.11 and the crack-control steel As = W·L·f / 2fs.

Beside them the DRR standard drawings for local roads (แบบมาตรฐานงานทาง
สำหรับ อปท., ทถ-2-201(1)/(2), ทถ-2-202, ทถ-2-302, ทถ-2-303) — their
recommended layer tables and the steel / dowel / tie-bar tables — so a
design can be checked against the standard sheet it will be built from.

Everything here is pure arithmetic (no Qt); the road panel shows it and
puts the result into the layer table. Thicknesses are in centimetres
unless a name says otherwise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

# --------------------------------------------------------------------------------------------
# 1. Asphalt Institute 1970
# --------------------------------------------------------------------------------------------

#: % of heavy trucks (6 wheels and over) when no count is at hand (ตารางที่ 1)
HEAVY_TRUCK_PCT = (("ถนนในเมืองอยู่ต่างจังหวัด", 5.0), ("ถนนในเมืองหลวง", 5.0, 15.0),
                   ("ถนนระหว่างจังหวัดสำคัญ", 10.0, 25.0))


def design_lane_pct(lanes: int) -> float:
    """% of the heavy trucks in the design lane (ตารางที่ 2): 2 lanes 50,
    4 lanes 45, 6 or more 40 (1 lane: all of them)."""
    if lanes <= 1:
        return 100.0
    if lanes <= 3:
        return 50.0
    if lanes <= 5:
        return 45.0
    return 40.0


#: Substitution ratios (ตารางที่ 4) — name, Sr, the CBR the layer has
SUBSTITUTION = (
    ("ผิวทางแอสฟัลต์คอนกรีต (AC)", 1.0, None),
    ("พื้นทาง Hot-mix Sand Asphalt", 1.3, None),
    ("พื้นทาง Emulsified Asphalt", 1.4, None),
    ("ชั้นพื้นทางหินคลุก", 2.0, 80.0),
    ("ชั้นรองพื้นทางวัสดุมวลรวม", 2.7, 25.0),
    ("ชั้นวัสดุคัดเลือก ก", 3.0, 10.0),
    ("ชั้นวัสดุคัดเลือก ข", 3.5, 6.0),
)


def substitution(name: str) -> tuple:
    """(Sr, CBR) of a layer by its name (the closest known material)."""
    for n, sr, cbr in SUBSTITUTION:
        if n == name:
            return sr, cbr
    keys = (("แอสฟัลต์", 1.0, None), ("AC", 1.0, None), ("Sand Asphalt", 1.3, None),
            ("Emulsified", 1.4, None), ("หินคลุก", 2.0, 80.0), ("มวลรวม", 2.7, 25.0),
            ("ลูกรัง", 2.7, 25.0), ("คัดเลือก ข", 3.5, 6.0), ("คัดเลือก", 3.0, 10.0),
            ("ทรายถม", 3.5, 10.0))
    for k, sr, cbr in keys:
        if k in name:
            return sr, cbr
    return 3.0, 10.0


def itn_of(single_axle_lb: float, gross_lb: float, trucks: float) -> float:
    """log ITN = −10.68 + 3.4 log S + 1.33 log W + 1.05 log N  (สมการที่ 1),
    S in 1,000 lb, W in lb, N trucks a day in the design lane."""
    if single_axle_lb <= 0 or gross_lb <= 0 or trucks <= 0:
        return 0.0
    return 10 ** (-10.68 + 3.4 * math.log10(single_axle_lb / 1000.0)
                  + 1.33 * math.log10(gross_lb) + 1.05 * math.log10(trucks))


def adjustment_factor(r_pct: float, years: float) -> float:
    """ITN adjustment factor [(1+r)^n − 1] / 20r (r = 0: n / 20)."""
    r = r_pct / 100.0
    if abs(r) < 1e-9:
        return years / 20.0
    return ((1 + r) ** years - 1) / (20 * r)


def ta_required(dtn: float, cbr: float) -> float:
    """Full-depth asphalt thickness TA (ซม.) over a layer of ``cbr`` %:
    TA = 2.54 (9.19 + 3.97 log DTN) / CBR^0.4  (สมการที่ 4)."""
    if dtn <= 0 or cbr <= 0:
        return 0.0
    return 2.54 * (9.19 + 3.97 * math.log10(dtn)) / cbr ** 0.4


def traffic_class(dtn: float) -> str:
    if dtn < 10:
        return "Light Traffic"
    if dtn <= 100:
        return "Medium Traffic"
    return "Heavy Traffic"


def ta_minimum(dtn: float) -> float:
    """The least TA (ซม.) AI sets by the traffic (ตารางที่ 5): 4/5/6/7 นิ้ว."""
    inch = 4 if dtn < 10 else 5 if dtn <= 100 else 6 if dtn <= 1000 else 7
    return inch * 2.54


def ac_thickness(dtn: float) -> float:
    """A surface for the trial structure (ซม.), as Thai practice sizes it:
    5 cm up to DTN 100, 7.5 cm to 1,000, 10 cm above."""
    return 5.0 if dtn <= 100 else 7.5 if dtn <= 1000 else 10.0


@dataclass
class AIInput:
    idt: float = 1000.0              # Initial Daily Traffic, both ways (คัน/วัน)
    heavy_pct: float = 10.0          # A: % heavy trucks (6 wheels and over)
    lanes: int = 2
    lane_pct: Optional[float] = None  # B: None → by the lanes
    gross_t: float = 21.0            # average gross weight of a heavy truck (ตัน)
    growth_pct: float = 5.0
    years: float = 15.0
    cbr: float = 5.0                 # design CBR of the subgrade (80th percentile)
    #: the structure, top first: [name, thickness ซม., Sr, CBR] (None: auto)
    layers: Optional[list] = None


@dataclass
class AIResult:
    inp: AIInput
    lane_pct: float
    trucks: float                    # N, heavy trucks a day in the design lane
    gross_lb: float
    axle_t: float
    axle_lb: float
    itn: float
    factor: float
    dtn: float
    ta: float                        # TA over the subgrade
    ta_min: float
    layers: list                     # [name, thickness, Sr, CBR, TA eq]
    checks: list                     # [(over, CBR, TA need, TA have, ok)]
    warnings: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c[4] for c in self.checks)

    @property
    def total(self) -> float:
        return sum(t for _n, t, *_r in self.layers)


def _roundup(v: float, step: float) -> float:
    return math.ceil(v / step - 1e-9) * step


def ai_auto_layers(dtn: float, cbr: float) -> list:
    """A trial structure (top first) sized layer by layer from the TA
    needed over each support: the AC surface by the traffic, crushed-rock
    base (CBR ≥ 80, at least 20 cm), soil-aggregate sub-base (CBR ≥ 25,
    at least 15 cm), selected material A (CBR ≥ 10) only where the
    subgrade needs it. Rounded up to 5 cm."""
    plan = [("ผิวทางแอสฟัลต์คอนกรีต (AC)", 1.0, None, ac_thickness(dtn)),
            ("ชั้นพื้นทางหินคลุก", 2.0, 80.0, 20.0 if dtn > 10 else 15.0),
            ("ชั้นรองพื้นทางวัสดุมวลรวม", 2.7, 25.0, 15.0)]
    if cbr < 10:
        plan.append(("ชั้นวัสดุคัดเลือก ก", 3.0, 10.0, 0.0))
    out, eq = [], 0.0
    for i, (name, sr, _own, least) in enumerate(plan):
        if i == 0:
            t = least
        else:
            # everything down to this layer must cover the TA over what it sits on
            support = plan[i + 1][2] if i + 1 < len(plan) else cbr
            need = ta_required(dtn, min(support, 80.0)) - eq
            t = max(least, _roundup(need * sr, 5.0) if need > 0 else 0.0)
        if t <= 0:
            continue
        out.append([name, t, sr, plan[i][2]])
        eq += t / sr
    return out


def design_ai(inp: AIInput) -> AIResult:
    """The whole AI 1970 design: DTN, TA, the layers and their checks."""
    warn = []
    B = inp.lane_pct if inp.lane_pct else design_lane_pct(inp.lanes)
    N = inp.idt * inp.heavy_pct / 100.0 * B / 100.0
    W = inp.gross_t * 2204.0                          # ปอนด์ (as the manual: 1 t = 2,204 lb)
    axle_t = inp.gross_t * 0.8 * 0.5                  # น้ำหนักเพลาเดี่ยว = W × 0.8 × 0.5
    S = axle_t * 2204.0
    itn = itn_of(S, W, N)
    if itn < 10:
        warn.append("ITN ต่ำกว่า 10 — คู่มือให้ปรับแก้ด้วยรูปที่ 4 ตามปริมาณรถยนต์และรถบรรทุกเล็ก "
                    "(ใช้ค่าที่คำนวณได้ ซึ่งให้ผลด้านปลอดภัยน้อยกว่าเล็กน้อย)")
    af = adjustment_factor(inp.growth_pct, inp.years)
    dtn = itn * af
    ta = ta_required(dtn, inp.cbr)
    if inp.layers:
        layers = []
        for row in inp.layers:
            name, t = str(row[0]), float(row[1])
            sr = float(row[2]) if len(row) > 2 and row[2] else substitution(name)[0]
            cb = row[3] if len(row) > 3 else substitution(name)[1]
            layers.append([name, t, sr, cb])
    else:
        layers = ai_auto_layers(dtn, inp.cbr)
    for row in layers:
        row[4:] = [row[1] / row[2]]
    # TA over every layer: everything above it against the CBR it has
    checks = []
    above = 0.0
    for i, (name, t, sr, cb, eq) in enumerate(layers):
        above += eq
        nxt = layers[i + 1] if i + 1 < len(layers) else None
        if nxt is None:
            over, cbr_s = "ดินคันทาง / ดินเดิม", inp.cbr
        else:
            if nxt[3] is None or float(nxt[3]) >= 80.0:
                # over the crushed-rock base the AC is set by the least
                # thickness (ตารางที่ 5), not by TA — as the manual checks
                continue
            over, cbr_s = nxt[0], float(nxt[3])
        need = ta_required(dtn, cbr_s)
        checks.append((over, cbr_s, need, above, above >= need - 1e-6))
    tmin = ta_minimum(dtn)
    if above < tmin:
        warn.append(f"TA รวม {above:.2f} ซม. น้อยกว่าความหนาขั้นต่ำของ AI {tmin:.1f} ซม.")
    if inp.cbr < 3:
        warn.append("CBR ดินคันทางต่ำกว่า 3% — แบบมาตรฐาน ทช. ให้ออกแบบปรับปรุงดินคันทางเป็นพิเศษ "
                    "(CBR < 4%)")
    return AIResult(inp, B, N, W, axle_t, S, itn, af, dtn, ta, tmin, layers, checks, warn)


# --------------------------------------------------------------------------------------------
# 2. Road Note 29 (concrete)
# --------------------------------------------------------------------------------------------

#: Equivalence factors of axle loads (tons, EF) — ตารางที่ 1 of the DRR sheet
EF_TABLE = ((0.91, 0.0002), (1.81, 0.0025), (2.72, 0.01), (3.63, 0.03), (4.54, 0.09),
            (4.60, 0.096), (5.44, 0.19), (6.35, 0.35), (7.26, 0.61), (8.16, 1.0),
            (8.20, 1.022), (9.07, 1.5), (9.98, 2.3), (10.89, 3.2), (11.79, 4.4),
            (12.70, 5.8), (13.61, 7.6), (14.62, 9.7), (15.42, 12.1), (16.32, 15.0),
            (17.23, 18.6), (18.14, 22.8))


def equivalence_factor(axle_t: float) -> float:
    """EF of one single axle of ``axle_t`` tons, interpolated in the table
    (beyond it: the fourth-power law from the last row)."""
    pts = EF_TABLE
    if axle_t <= pts[0][0]:
        return pts[0][1] * (axle_t / pts[0][0]) ** 4 if axle_t > 0 else 0.0
    for (a, ea), (b, eb) in zip(pts, pts[1:]):
        if axle_t <= b:
            return ea + (axle_t - a) / (b - a) * (eb - ea)
    a, ea = pts[-1]
    return ea * (axle_t / a) ** 4


def lane_factor(lanes: int, width: float) -> float:
    """Share of the trucks on the design lane, as the DRR sheet takes it:
    2 lanes of 4 m total (one lane each way) 1.0, wider 0.5; 4 lanes 0.45,
    6 or more 0.40."""
    if lanes <= 2:
        return 1.0 if width <= 4.0 + 1e-6 else 0.5
    if lanes <= 5:
        return 0.45
    return 0.40


#: Fig. 3.16 (Road Note 29): slab thickness (mm) on a normal subgrade
#: (CBR 2–15 %) against the cumulative standard axles (millions) — read
#: from the chart and checked against the DRR workshop's own readings
#: (3.05 × 10⁶ → 199 mm, 27.6 × 10⁶ → 250 mm).
RN29_REINFORCED = ((0.01, 123), (0.02, 124), (0.04, 127), (0.1, 132), (0.2, 140),
                   (0.4, 152), (1.0, 171), (2.0, 190), (3.0, 198.5), (4.0, 205),
                   (10.0, 226), (20.0, 243), (27.6, 250), (40.0, 262), (100.0, 297))
RN29_UNREINFORCED = ((0.01, 148), (0.04, 150), (0.1, 153), (0.2, 157), (0.4, 163),
                     (0.7, 169), (1.0, 172))
#: Fig. 3.17: crack-control steel, standard long mesh (kg/m²)
RN29_STEEL = ((0.01, 1.80), (0.1, 2.0), (0.2, 2.10), (0.4, 2.28), (1.0, 2.55),
              (1.5, 2.61), (2.0, 2.80), (4.0, 3.10), (7.5, 3.41), (10.0, 3.60),
              (20.0, 4.10), (30.0, 4.34), (40.0, 4.60), (60.0, 5.00), (100.0, 5.55))


def _log_interp(table, msa: float) -> float:
    msa = max(msa, table[0][0])
    for (a, va), (b, vb) in zip(table, table[1:]):
        if msa <= b:
            f = (math.log10(msa) - math.log10(a)) / (math.log10(b) - math.log10(a))
            return va + f * (vb - va)
    (a, va), (b, vb) = table[-2], table[-1]
    f = (math.log10(msa) - math.log10(a)) / (math.log10(b) - math.log10(a))
    return va + f * (vb - va)


def rn29_slab_mm(msa: float, cbr: float, reinforced: bool = True) -> float:
    """Slab thickness (mm) from Fig. 3.16; −25 mm on a very stable subgrade
    (CBR ≥ 15 %), +25 mm on a weak one (CBR ≤ 2 %)."""
    t = _log_interp(RN29_REINFORCED, msa)
    if not reinforced:
        if msa <= RN29_UNREINFORCED[-1][0]:
            t = max(t, _log_interp(RN29_UNREINFORCED, msa))
    if cbr >= 15:
        t -= 25
    elif cbr <= 2:
        t += 25
    return t


def rn29_steel_kg(msa: float) -> float:
    return _log_interp(RN29_STEEL, msa)


def subbase_min_cm(cbr: float) -> tuple:
    """(soil, least sub-base ซม.) — Table 3.11: weak (CBR ≤ 2) 15, normal
    (3–14) 8, stiff (≥ 15) 0."""
    if cbr <= 2:
        return "อ่อน", 15.0
    if cbr < 15:
        return "ปกติ", 8.0
    return "แข็ง", 0.0


@dataclass
class Truck:
    name: str
    pct: float                       # % of the heavy trucks
    axles: tuple                     # tons on each axle, front first


@dataclass
class RNInput:
    adt: float = 500.0
    lanes: int = 2
    width: float = 6.0               # carriageway (ม.)
    heavy_pct: float = 10.0
    trucks: tuple = (Truck("รถบรรทุก 6 ล้อ (LT)", 70.0, (4.0, 11.0)),
                     Truck("รถบรรทุก 10 ล้อ (HT)", 30.0, (5.0, 10.0, 10.0)))
    loaded_pct: float = 100.0        # trucks loaded : empty (100 = every one loaded)
    growth_pct: float = 4.0
    years: float = 20.0
    cbr: float = 4.0
    reinforced: bool = True
    construction_traffic: bool = True
    slab_length: float = 10.0        # ระยะรอยต่อตามขวาง (ม.)
    lane_width: float = 3.0          # สำหรับเหล็กตามขวาง
    fs: float = 2750.0               # 1,200 RB / 2,750 wire mesh (กก./ตร.ซม.)
    friction: float = 1.5
    slab_cm: Optional[float] = None  # chosen thickness (None: from the chart)
    subbase_cm: Optional[float] = None
    fc: float = 280.0                # กก./ตร.ซม. (ลูกบาศก์)
    chart_mm: Optional[float] = None  # the chart read by hand (None: from the curve)
    subbase_kind: str = "laterite"   # laterite → sand cushion 5 cm under the slab; crushed → none


SUBBASE_KINDS = {"laterite": "ชั้นรองพื้นทางลูกรัง", "crushed": "ชั้นรองพื้นทางหินคลุก"}


@dataclass
class RNResult:
    inp: RNInput
    lane_factor: float
    per_day: list                    # [(name, trucks/day)]
    growth_sum: float                # [(1+r)^n − 1]/r
    cumulative: list                 # [(name, vehicles)]
    vef: list                        # [(name, EF per axle list, VEF)]
    esa_rows: list                   # [(name, vehicles, VEF×loaded, ESA)]
    esa: float
    slab_chart_mm: float
    slab_cm: float
    soil: str
    subbase_need: float
    subbase_cm: float
    as_long: float                   # cm²/m
    as_trans: float
    steel_long: tuple                # (label, area cm²/m)
    steel_trans: tuple
    mesh_kg: float                   # Fig. 3.17
    joints: dict
    standard: Optional[dict]
    warnings: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (self.slab_cm * 10 >= self.slab_chart_mm - 0.5
                and self.subbase_cm >= self.subbase_need - 1e-6
                and self.steel_long[1] >= self.as_long - 1e-6
                and self.steel_trans[1] >= self.as_trans - 1e-6)


def steel_area(w_kg_m2: float, length: float, f: float, fs: float) -> float:
    """As = W·L·f / (2 fs)  (ตร.ซม. ต่อ ม.), W the slab's weight kg/m²."""
    return w_kg_m2 * length * f / (2.0 * fs)


#: bars / wires to choose from (mm) for each kind of steel
BARS_RB = (6, 9, 12)
WIRES = (4, 5, 6, 9)


def pick_steel(need_cm2: float, fs: float) -> tuple:
    """The lightest standard bar/wire @ a workable spacing (15–30 cm; 10 cm
    only when nothing else carries it) with As ≥ need: (label, cm²/m)."""
    dias = WIRES if fs >= 2000 else BARS_RB
    kind = "Wire mesh" if fs >= 2000 else "RB"
    for spacings in ((30, 25, 20, 15), (10,)):
        best = None
        for d in dias:
            a1 = math.pi * (d / 10.0) ** 2 / 4.0
            for s in spacings:
                area = a1 * 100.0 / s
                if area >= need_cm2 - 1e-9 and (best is None or area < best[1] - 1e-9):
                    best = (f"{kind} Ø{d} มม. @ {s / 100:.2f} ม.", area)
        if best:
            return best
    d = dias[-1]
    return (f"{kind} Ø{d} มม. @ 0.10 ม.", math.pi * (d / 10) ** 2 / 4 * 10)


#: ทถ-2-202 ตารางที่ 2: dowels by the slab (ซม.) — (Ø mm, length cm, @ cm)
DOWELS = ((15, 19, 50, 30), (18, 19, 50, 30), (20, 25, 50, 30), (23, 25, 50, 25),
          (25, 25, 50, 20))
TIE_BAR = (12, 50, 50)               # DB12 ยาว 50 ซม. @ 50 ซม.


def joints_for(slab_cm: float) -> dict:
    row = next((r for r in DOWELS if slab_cm <= r[0] + 1e-6), DOWELS[-1])
    return {"dowel": f"RB{row[1]} ยาว {row[2] / 100:.2f} ม. @ {row[3] / 100:.2f} ม.",
            "tie": f"DB{TIE_BAR[0]} ยาว {TIE_BAR[1] / 100:.2f} ม. @ {TIE_BAR[2] / 100:.2f} ม.",
            "contraction": "Sawed joint ทุก 10.00 ม. ลึก T/4 กว้าง 6–12 มม. ยาแนว Mastic",
            "expansion": "Expansion joint เฉพาะที่ชนสะพาน/โครงสร้าง หรือทุก 200–250 ม."}


def design_rn29(inp: RNInput) -> RNResult:
    warn = []
    lf = lane_factor(inp.lanes, inp.width)
    r = inp.growth_pct / 100.0
    gsum = inp.years if abs(r) < 1e-9 else ((1 + r) ** inp.years - 1) / r
    per_day, cum, vef_rows, esa_rows = [], [], [], []
    esa = 0.0
    for tr in inp.trucks:
        n = inp.adt * lf * inp.heavy_pct / 100.0 * tr.pct / 100.0
        per_day.append((tr.name, n))
        c = gsum * 365.0 * n
        cum.append((tr.name, c))
        efs = [equivalence_factor(a) for a in tr.axles]
        v = sum(efs)
        vef_rows.append((tr.name, efs, v))
        e = c * v * inp.loaded_pct / 100.0
        esa_rows.append((tr.name, c, v * inp.loaded_pct / 100.0, e))
        esa += e
    msa = esa / 1e6
    mm = rn29_slab_mm(msa, inp.cbr, inp.reinforced)
    if inp.chart_mm:
        # read off the chart by the designer (as the DRR sheet asks), with
        # the same ±25 mm for a very stable / weak subgrade
        mm = float(inp.chart_mm) - (25 if inp.cbr >= 15 else 0) + (25 if inp.cbr <= 2 else 0)
    chart_cm = _roundup(mm / 10.0, 1.0)
    slab = inp.slab_cm if inp.slab_cm else max(15.0, chart_cm)
    if inp.slab_cm and inp.slab_cm * 10 < mm - 0.5:
        warn.append(f"ความหนาที่เลือก {inp.slab_cm:g} ซม. น้อยกว่าจากแผนภูมิ {mm:.0f} มม.")
    if msa > 100:
        warn.append("ESA เกิน 100 ล้านเพลา — นอกขอบเขตแผนภูมิ Road Note 29")
    soil, sb = subbase_min_cm(inp.cbr)
    need = sb + (8.0 if inp.construction_traffic else 0.0)
    subbase = inp.subbase_cm if inp.subbase_cm else max(_roundup(need, 5.0), 10.0)
    W = 2400.0 * slab / 100.0
    as_l = steel_area(W, inp.slab_length, inp.friction, inp.fs)
    as_t = steel_area(W, inp.lane_width, inp.friction, inp.fs)
    st_l, st_t = pick_steel(as_l, inp.fs), pick_steel(as_t, inp.fs)
    if inp.fc < 280:
        warn.append("Road Note 29 กำหนดคอนกรีต fc′ ≥ 280 กก./ตร.ซม. (ลูกบาศก์)")
    return RNResult(inp, lf, per_day, gsum, cum, vef_rows, esa_rows, esa, mm, slab, soil,
                    need, subbase, as_l, as_t, st_l, st_t, rn29_steel_kg(msa),
                    joints_for(slab), drr_rc_standard(inp.adt, inp.cbr), warn)


# --------------------------------------------------------------------------------------------
# 3. DRR standard drawings for local roads (แบบมาตรฐานงานทางสำหรับ อปท.)
# --------------------------------------------------------------------------------------------

#: ทถ-2-201(1) ถนนคอนกรีตเสริมเหล็ก ประเภทที่ 1 (รองพื้นทางลูกรัง):
#: (slab m, ADT up to) → {CBR: (selected m, subbase m)}
DRR_RC1 = ((0.15, 250, {4: (0.0, 0.20)}),
           (0.18, 500, {4: (0.20, 0.20), 6: (0.10, 0.20), 8: (0.0, 0.20)}),
           (0.20, 1000, {4: (0.20, 0.20), 6: (0.10, 0.20), 8: (0.0, 0.20)}),
           (0.23, 1500, {4: (0.20, 0.20), 6: (0.10, 0.20), 8: (0.0, 0.20)}),
           (0.25, 3000, {4: (0.20, 0.20), 6: (0.10, 0.20), 8: (0.0, 0.20)}))
#: ทถ-2-201(2) ประเภทที่ 2 (พื้นทางหินคลุก): → {CBR: (selected, subbase, base)}
DRR_RC2 = ((0.15, 375, {4: (0.15, 0.15, 0.15)}),
           (0.18, 750, {4: (0.20, 0.20, 0.15), 6: (0.10, 0.20, 0.15), 8: (0.0, 0.20, 0.15)}),
           (0.20, 1500, {4: (0.20, 0.20, 0.15), 6: (0.10, 0.20, 0.15), 8: (0.0, 0.20, 0.15)}),
           (0.23, 2250, {4: (0.20, 0.20, 0.15), 6: (0.10, 0.20, 0.15), 8: (0.0, 0.20, 0.15)}),
           (0.25, 4500, {4: (0.20, 0.20, 0.15), 6: (0.10, 0.20, 0.15), 8: (0.0, 0.20, 0.15)}))
#: ทถ-2-303 ถนนผิวจราจร Asphalt Concrete, 7-year design:
#: (CBR, AC cm, ADT up to, selected m, subbase m, base m)
DRR_AC7 = ((4, 4, 500, 0.0, 0.20, 0.20), (4, 4, 1000, 0.20, 0.20, 0.20),
           (4, 5, 1500, 0.20, 0.20, 0.20), (4, 5, 2000, 0.20, 0.25, 0.25),
           (6, 4, 1000, 0.10, 0.20, 0.20), (6, 5, 1500, 0.10, 0.20, 0.20),
           (6, 5, 2000, 0.10, 0.25, 0.25),
           (8, 4, 1000, 0.0, 0.20, 0.20), (8, 5, 1500, 0.0, 0.20, 0.20),
           (8, 5, 2000, 0.0, 0.25, 0.25))
#: … 10-year design
DRR_AC10 = ((4, 5, 1000, 0.20, 0.25, 0.20), (4, 6, 2000, 0.20, 0.25, 0.25),
            (4, 8, 3000, 0.20, 0.25, 0.25), (4, 10, 4000, 0.20, 0.25, 0.25),
            (6, 5, 1000, 0.10, 0.25, 0.20), (6, 6, 2000, 0.10, 0.25, 0.25),
            (6, 8, 3000, 0.10, 0.25, 0.25), (6, 10, 4000, 0.10, 0.25, 0.25),
            (8, 5, 1000, 0.0, 0.25, 0.20), (8, 6, 2000, 0.0, 0.25, 0.25),
            (8, 8, 3000, 0.0, 0.25, 0.25), (8, 10, 4000, 0.0, 0.25, 0.25))
#: ทถ-2-302 D.B.S.T. (7 ปี): (CBR, ADT up to, selected, subbase, base)
DRR_DBST = ((4, 200, 0.20, 0.15, 0.15), (4, 500, 0.20, 0.20, 0.20), (4, 1000, 0.20, 0.25, 0.25),
            (6, 200, 0.10, 0.15, 0.15), (6, 500, 0.10, 0.20, 0.20), (6, 1000, 0.10, 0.25, 0.25),
            (8, 200, 0.0, 0.15, 0.15), (8, 500, 0.0, 0.20, 0.20), (8, 1000, 0.0, 0.25, 0.25))


def _cbr_class(cbr: float) -> int:
    """The table's CBR column for a subgrade: 4 (4–5.9), 6 (6–7.9), 8 (≥ 8)."""
    return 8 if cbr >= 8 else 6 if cbr >= 6 else 4


def drr_rc_standard(adt: float, cbr: float, kind: int = 1) -> Optional[dict]:
    """The DRR standard concrete road for the traffic and subgrade —
    ประเภท 1 (ทถ-2-201(1)) or 2 (ทถ-2-201(2)): {"sheet", "slab", "layers"}."""
    table = DRR_RC1 if kind == 1 else DRR_RC2
    row = next((r for r in table if adt <= r[1]), None)
    if row is None:
        return None
    slab, _adt, by_cbr = row
    c = _cbr_class(cbr)
    vals = by_cbr.get(c) or by_cbr.get(min(by_cbr, key=lambda k: abs(k - c)))
    layers = [("ผิวทางคอนกรีตเสริมเหล็ก", slab), ("ชั้นทรายรองพื้น", 0.10 if kind == 1 else 0.05)]
    if kind == 2:
        sel, sub, base = vals
        layers.append(("ชั้นพื้นทางหินคลุก", base))
    else:
        sel, sub = vals
    layers.append(("ชั้นรองพื้นทางวัสดุมวลรวม" if kind == 2 else "ชั้นรองพื้นทางลูกรัง", sub))
    if sel > 0:
        layers.append(("ชั้นวัสดุคัดเลือก ก", sel))
    return {"sheet": "ทถ-2-201(1)" if kind == 1 else "ทถ-2-201(2)", "slab": slab,
            "adt": _adt, "cbr": c, "layers": layers}


def drr_ac_standard(adt: float, cbr: float, years: int = 10) -> Optional[dict]:
    """The DRR standard asphalt-concrete road (ทถ-2-303)."""
    table = DRR_AC7 if years <= 7 else DRR_AC10
    c = _cbr_class(cbr)
    rows = [r for r in table if r[0] == c and adt <= r[2]]
    if not rows:
        return None
    _c, ac, upto, sel, sub, base = rows[0]
    layers = [("ผิวทางแอสฟัลต์คอนกรีต (AC)", ac / 100.0), ("ชั้นพื้นทางหินคลุก", base),
              ("ชั้นรองพื้นทางวัสดุมวลรวม", sub)]
    if sel > 0:
        layers.append(("ชั้นวัสดุคัดเลือก ก", sel))
    return {"sheet": "ทถ-2-303", "years": 7 if years <= 7 else 10, "adt": upto, "cbr": c,
            "layers": layers}


def drr_dbst_standard(adt: float, cbr: float) -> Optional[dict]:
    c = _cbr_class(cbr)
    rows = [r for r in DRR_DBST if r[0] == c and adt <= r[1]]
    if not rows:
        return None
    _c, upto, sel, sub, base = rows[0]
    layers = [("ผิวทางลาดยางเคลือบผิว 2 ชั้น (DBST)", 0.025), ("ชั้นพื้นทางหินคลุก", base),
              ("ชั้นรองพื้นทางวัสดุมวลรวม", sub)]
    if sel > 0:
        layers.append(("ชั้นวัสดุคัดเลือก ก", sel))
    return {"sheet": "ทถ-2-302", "adt": upto, "cbr": c, "layers": layers}


#: ทถ-2-202 ตารางที่ 1 Temperature steel: slab cm → (longitudinal RB, area mm²/m,
#: wire mesh mm²/m, {lane width: (transverse RB, area, mesh)})
TEMP_STEEL = {
    15: ("RB9 @ 0.28 ม.", 227, 99, {2.5: ("RB6 @ 0.25 ม.", 113, 49), 3.0: ("RB6 @ 0.20 ม.", 141, 62),
                                    3.5: ("RB6 @ 0.18 ม.", 157, 69), 4.0: ("RB6 @ 0.15 ม.", 188, 82)}),
    18: ("RB9 @ 0.23 ม.", 277, 121, {2.5: ("RB6 @ 0.20 ม.", 141, 62), 3.0: ("RB6 @ 0.18 ม.", 157, 69),
                                     3.5: ("RB6 @ 0.15 ม.", 188, 82), 4.0: ("RB6 @ 0.13 ม.", 217, 95)}),
    20: ("RB9 @ 0.20 ม.", 318, 139, {2.5: ("RB6 @ 0.18 ม.", 157, 69), 3.0: ("RB6 @ 0.15 ม.", 188, 82),
                                     3.5: ("RB6 @ 0.13 ม.", 217, 95), 4.0: ("RB6 @ 0.10 ม.", 283, 123)}),
    23: ("RB9 @ 0.18 ม.", 353, 154, {2.5: ("RB9 @ 0.38 ม.", 167, 73), 3.0: ("RB9 @ 0.30 ม.", 212, 93),
                                     3.5: ("RB9 @ 0.25 ม.", 254, 111), 4.0: ("RB9 @ 0.23 ม.", 277, 121)}),
    25: ("RB9 @ 0.15 ม.", 424, 185, {2.5: ("RB9 @ 0.35 ม.", 182, 79), 3.0: ("RB9 @ 0.25 ม.", 254, 111),
                                     3.5: ("RB9 @ 0.23 ม.", 277, 121), 4.0: ("RB9 @ 0.20 ม.", 318, 139)}),
}


def temperature_steel(slab_cm: float, lane_w: float) -> Optional[dict]:
    key = next((k for k in sorted(TEMP_STEEL) if slab_cm <= k + 1e-6), None)
    if key is None:
        return None
    lo, a, mesh, trans = TEMP_STEEL[key]
    w = next((k for k in sorted(trans) if lane_w <= k + 1e-6), max(trans))
    t = trans[w]
    return {"slab": key, "long": lo, "long_area": a, "long_mesh": mesh, "lane": w,
            "trans": t[0], "trans_area": t[1], "trans_mesh": t[2]}


# --------------------------------------------------------------------------------------------
# 4. The calculation sheet (รายการคำนวณ) as HTML — the panel prints it to PDF
# --------------------------------------------------------------------------------------------

def _f(v, d=2) -> str:
    return f"{v:,.{d}f}"


def _ok(b: bool) -> str:
    return "<b style='color:#15803d'>ผ่าน</b>" if b else "<b style='color:#b91c1c'>ไม่ผ่าน</b>"


SIGNER = ("นายเวนิช ธัมมะวงษ์", "วิศวกรสำรวจ")


def _head(title: str, project: str) -> str:
    return (f"<h2 style='margin:0'>{title}</h2>"
            f"<p style='margin:2px 0 10px 0'>โครงการ: {project or '……………………………………………'}</p>")


def _sign(signer=SIGNER) -> str:
    name, role = signer
    return ("<br><table width='100%'><tr><td width='50%'></td><td align='center'>"
            "ลงชื่อ ……………………………… ผู้คำนวณ<br>"
            f"( {name} )<br>{role}</td></tr></table>")


_CSS = ("<style>body{font-family:'Tahoma','Leelawadee UI',sans-serif;font-size:10pt}"
        "table.t{border-collapse:collapse}table.t td,table.t th{border:1px solid #555;"
        "padding:2px 6px}th{background:#e5e7eb}h3{margin:12px 0 4px 0}</style>")


def ai_report(res: AIResult, project: str = "", signer=SIGNER) -> str:
    i = res.inp
    h = [_CSS, _head("รายการคำนวณโครงสร้างถนนลาดยาง โดยวิธี Asphalt Institute (1970)", project)]
    h.append("<h3>1. ข้อมูลการออกแบบ</h3><table class='t'>")
    for k, v in (("(1) Initial Daily Traffic (IDT)", f"{_f(i.idt, 0)} คัน/วัน"),
                 ("(2) ร้อยละรถบรรทุกหนัก (A)", f"{_f(i.heavy_pct)} %"),
                 ("(3) ร้อยละรถบรรทุกใน Design Lane (B)", f"{_f(res.lane_pct)} % ({i.lanes} ช่องจราจร)"),
                 ("(5) น้ำหนักเฉลี่ยรถบรรทุกหนัก (W)", f"{_f(i.gross_t, 1)} ตัน = {_f(res.gross_lb, 0)} ปอนด์"),
                 ("(6) น้ำหนักเพลาเดี่ยว (S = W×0.8×0.5)", f"{_f(res.axle_t)} ตัน = {_f(res.axle_lb, 0)} ปอนด์"),
                 ("(9) อัตราการเพิ่มปริมาณจราจร (r)", f"{_f(i.growth_pct)} %"),
                 ("อายุการออกแบบ (n)", f"{_f(i.years, 0)} ปี"),
                 ("CBR ดินคันทาง (ค่าออกแบบ)", f"{_f(i.cbr, 1)} %")):
        h.append(f"<tr><td>{k}</td><td>{v}</td></tr>")
    h.append("</table><h3>2. Design Traffic Number</h3>")
    h.append(f"(4) N = IDT × A × B = {_f(i.idt, 0)} × {_f(i.heavy_pct / 100, 4)} × "
             f"{_f(res.lane_pct / 100, 2)} = <b>{_f(res.trucks, 1)}</b> คัน/วัน<br>")
    h.append("(7) log ITN = −10.68 + 3.4 log S + 1.33 log W + 1.05 log N "
             f"→ ITN = <b>{_f(res.itn, 1)}</b><br>")
    h.append(f"(10) Adjustment Factor = [(1+r)<sup>n</sup> − 1] / 20r = <b>{_f(res.factor, 3)}</b><br>")
    h.append(f"(11) DTN = ITN × AF = {_f(res.itn, 1)} × {_f(res.factor, 3)} = <b>{_f(res.dtn, 0)}</b> "
             f"({traffic_class(res.dtn)})")
    h.append("<h3>3. ความหนา TA และการแปลงความหนา</h3>")
    h.append(f"TA = 2.54 × (9.19 + 3.97 log DTN) / CBR<sup>0.4</sup> = <b>{_f(res.ta)}</b> ซม. "
             f"(ขั้นต่ำตาม AI {_f(res.ta_min, 1)} ซม.)<br><br>")
    h.append("<table class='t'><tr><th>ชั้น</th><th>หนา (ซม.)</th><th>Substitution Ratio</th>"
             "<th>Equivalent AC (ซม.)</th></tr>")
    for name, t, sr, _c, eq in res.layers:
        h.append(f"<tr><td>{name}</td><td align='right'>{_f(t, 1)}</td><td align='right'>{_f(sr, 1)}</td>"
                 f"<td align='right'>{_f(eq)}</td></tr>")
    h.append(f"<tr><td><b>รวม</b></td><td align='right'><b>{_f(res.total, 1)}</b></td><td></td>"
             f"<td align='right'><b>{_f(sum(r[4] for r in res.layers))}</b></td></tr></table>")
    h.append("<h3>4. ตรวจสอบความหนา TA เหนือแต่ละชั้น</h3><table class='t'><tr><th>เหนือชั้น</th>"
             "<th>CBR (%)</th><th>TA ที่ต้องการ</th><th>TA ที่ออกแบบ</th><th>ผล</th></tr>")
    for over, cbr, need, have, ok in res.checks:
        h.append(f"<tr><td>{over}</td><td align='right'>{_f(cbr, 0)}</td><td align='right'>{_f(need)}</td>"
                 f"<td align='right'>{_f(have)}</td><td>{_ok(ok)}</td></tr>")
    h.append("</table>")
    std = drr_ac_standard(i.idt, i.cbr, 10 if i.years >= 10 else 7)
    if std:
        h.append(f"<h3>5. เทียบแบบมาตรฐาน ทช. {std['sheet']} (ระยะออกแบบ {std['years']} ปี)</h3>")
        h.append(" · ".join(f"{n} {t * 100:g} ซม." for n, t in std["layers"]))
    for w in res.warnings:
        h.append(f"<p style='color:#b45309'>⚠ {w}</p>")
    h.append(f"<p><b>สรุป: โครงสร้างชั้นทาง {_ok(res.ok)}</b></p>")
    h.append(_sign(signer))
    return "".join(h)


def rn29_report(res: RNResult, project: str = "", signer=SIGNER, images: bool = False) -> str:
    """The calculation sheet; ``images`` puts in the truck figures and the
    Fig. 3.16 chart with its red reading lines (resources ``rn29trucks``
    and ``rn29chart`` that the caller adds to its document)."""
    i = res.inp
    h = [_CSS, _head("รายการคำนวณโครงสร้างถนน คสล. โดยวิธี Road Note 29", project)]
    h.append("<h3>1. ข้อมูลการออกแบบ</h3><table class='t'>")
    rows = [("ความกว้างผิวจราจร", f"{_f(i.width)} ม. ({i.lanes} ช่องจราจร)"),
            ("ปริมาณการจราจร (ADT)", f"{_f(i.adt, 0)} คัน/วัน"),
            ("ร้อยละรถบรรทุกหนักทั้งหมด", f"{_f(i.heavy_pct)} %"),
            ("Growth Rate (r)", f"{_f(i.growth_pct)} %"), ("อายุการออกแบบ (n)", f"{_f(i.years, 0)} ปี"),
            ("Design CBR Subgrade", f"{_f(i.cbr, 1)} %")]
    rows += [(f"ร้อยละ{t.name}", f"{_f(t.pct)} %") for t in i.trucks]
    for k, v in rows:
        h.append(f"<tr><td>{k}</td><td>{v}</td></tr>")
    h.append("</table><h3>2.1 ปริมาณรถบรรทุกในทิศทางเดียวต่อวัน (ADHV)</h3>")
    for name, n in res.per_day:
        h.append(f"{name} = ADT × {_f(res.lane_factor, 2)} × %HV × %ชนิด = <b>{_f(n, 2)}</b> คัน/วัน<br>")
    h.append("<h3>2.2 ปริมาณจราจรตลอดอายุการออกแบบ</h3>"
             f"[(1+r)<sup>n</sup> − 1] / r × 365 × ADHV ; [(1+r)<sup>n</sup> − 1]/r = {_f(res.growth_sum, 3)}<br>")
    for name, c in res.cumulative:
        h.append(f"{name} = <b>{_f(c, 0)}</b> คัน<br>")
    h.append("<h3>2.3 Equivalence Factor (เพลามาตรฐาน 18,000 ปอนด์)</h3>")
    if images:
        h.append("<p><img src='rn29trucks' width='640'></p>")
    h.append("<table class='t'>"
             "<tr><th>ชนิด</th><th>น้ำหนักเพลา (ตัน)</th><th>EF แต่ละเพลา</th><th>VEF</th></tr>")
    for (name, efs, v), tr in zip(res.vef, i.trucks):
        h.append(f"<tr><td>{name}</td><td>{' + '.join(f'{a:g}' for a in tr.axles)}</td>"
                 f"<td>{' + '.join(_f(e, 4) for e in efs)}</td><td align='right'>{_f(v, 3)}</td></tr>")
    h.append("</table><h3>2.4 Cumulative Equivalent Standard Axles</h3>"
             f"สัดส่วนรถบรรทุกที่บรรทุกของ : รถเปล่า = {_f(i.loaded_pct, 0)} : {_f(100 - i.loaded_pct, 0)}"
             "<table class='t'><tr><th>ชนิด</th><th>จำนวนสะสม</th><th>VEF × สัดส่วน</th><th>ESA</th></tr>")
    for name, c, v, e in res.esa_rows:
        h.append(f"<tr><td>{name}</td><td align='right'>{_f(c, 0)}</td><td align='right'>{_f(v, 3)}</td>"
                 f"<td align='right'>{_f(e, 0)}</td></tr>")
    h.append(f"<tr><td colspan='3'><b>รวม</b></td><td align='right'><b>{_f(res.esa, 0)}</b> "
             f"({_f(res.esa / 1e6, 3)} × 10<sup>6</sup>)</td></tr></table>")
    kind = "คอนกรีตเสริมเหล็ก" if i.reinforced else "คอนกรีตไม่เสริมเหล็ก"
    h.append("<h3>2.5 ความหนาแผ่นคอนกรีต (รูปที่ 3.16)</h3>")
    if images:
        h.append("<p><img src='rn29chart' width='640'></p>")
    h.append(f"{kind} ดินคันทาง CBR {_f(i.cbr, 1)}% → จากแผนภูมิ {_f(res.slab_chart_mm, 0)} มม."
             + (" (อ่านจากกราฟโดยผู้ออกแบบ)" if i.chart_mm else "") + "<br>"
             f"กำหนดความหนาผิวคอนกรีต = <b>{_f(res.slab_cm, 0)} ซม.</b> "
             f"(fc′ ≥ {_f(i.fc, 0)} กก./ตร.ซม. ลูกบาศก์) "
             f"{_ok(res.slab_cm * 10 >= res.slab_chart_mm - 0.5)}")
    h.append("<h3>2.6 ความหนาชั้นรองพื้นทาง (ตารางที่ 3.11)</h3>"
             f"ดินคันทางประเภท <b>{res.soil}</b>"
             + (" + รถบรรทุกวิ่งบนรองพื้นทางระหว่างก่อสร้าง 8 ซม." if i.construction_traffic else "")
             + f" → ต้องการ {_f(res.subbase_need, 0)} ซม. ; กำหนด <b>{_f(res.subbase_cm, 0)} ซม.</b> "
             f"{_ok(res.subbase_cm >= res.subbase_need - 1e-6)}<br>"
             + ("รองพื้นทางลูกรัง: ใช้ทรายหยาบรองพื้นคอนกรีตหนาประมาณ 5–10 ซม."
                if i.subbase_kind != "crushed" else
                "รองพื้นทางหินคลุก: ไม่จำเป็นต้องใช้ทรายหยาบรองพื้นคอนกรีต"))
    h.append("<h3>2.7 เหล็กเสริมกันร้าว As = W·L·f / 2fs</h3>"
             f"W = 2,400 × {_f(res.slab_cm / 100)} = {_f(2400 * res.slab_cm / 100, 0)} กก./ตร.ม. ; "
             f"f = {_f(i.friction, 1)} ; fs = {_f(i.fs, 0)} กก./ตร.ซม.<br>"
             f"ตามยาว L = {_f(i.slab_length)} ม. → As = {_f(res.as_long, 3)} ตร.ซม./ม. ; ใช้ "
             f"<b>{res.steel_long[0]}</b> = {_f(res.steel_long[1], 3)} {_ok(res.steel_long[1] >= res.as_long)}<br>"
             f"ตามขวาง L = {_f(i.lane_width)} ม. → As = {_f(res.as_trans, 3)} ตร.ซม./ม. ; ใช้ "
             f"<b>{res.steel_trans[0]}</b> = {_f(res.steel_trans[1], 3)} {_ok(res.steel_trans[1] >= res.as_trans)}<br>"
             f"เทียบรูปที่ 3.17: ตะแกรงเหล็กมาตรฐาน ≈ {_f(res.mesh_kg)} กก./ตร.ม.")
    h.append("<h3>2.8 รอยต่อ เหล็กเดือย และเหล็กยึด (ทถ-2-202)</h3>"
             f"Dowel bar {res.joints['dowel']} · Tie bar {res.joints['tie']}<br>"
             f"{res.joints['contraction']}<br>{res.joints['expansion']}")
    ts = temperature_steel(res.slab_cm, i.lane_width)
    if ts:
        h.append(f"<br>ตาราง Temperature steel (หนา {ts['slab']} ซม.): ตามยาว {ts['long']} "
                 f"({ts['long_area']} มม.²/ม.) · ตามขวาง ช่องกว้าง {ts['lane']:g} ม. {ts['trans']} "
                 f"({ts['trans_area']} มม.²/ม.)")
    if res.standard:
        s = res.standard
        h.append(f"<h3>3. เทียบแบบมาตรฐาน ทช. {s['sheet']}</h3>ADT ≤ {s['adt']:,} คัน/วัน, CBR {s['cbr']}% → "
                 + " · ".join(f"{n} {t * 100:g} ซม." for n, t in s["layers"]))
    for w in res.warnings:
        h.append(f"<p style='color:#b45309'>⚠ {w}</p>")
    h.append(f"<p><b>สรุป: {_ok(res.ok)}</b></p>")
    h.append(_sign(signer))
    return "".join(h)


def rn29_layers(res: RNResult) -> list:
    """The concrete road's layer table (name, thickness m), top first."""
    out = [("ผิวทางคอนกรีตเสริมเหล็ก" if res.inp.reinforced else "ผิวทางคอนกรีตไม่เสริมเหล็ก",
            res.slab_cm / 100.0)]
    if res.inp.subbase_kind != "crushed":
        # on laterite a coarse-sand cushion (5–10 cm) under the slab; on
        # crushed rock none is needed (the DRR sheet, 2.6)
        out.append(("ชั้นทรายรองพื้น", 0.05))
    out.append((SUBBASE_KINDS.get(res.inp.subbase_kind, "ชั้นรองพื้นทางลูกรัง"), res.subbase_cm / 100.0))
    return out


def ai_layers(res: AIResult) -> list:
    return [(n, t / 100.0) for n, t, *_r in res.layers]
