# -*- coding: utf-8 -*-
"""Quantity takeoff for a :class:`~wanicndesign.model.Project`.

Each quantity becomes a :class:`Line` carrying the ว480 labour code that
prices it. Waste follows the 2569 criteria where the data has a rule
(rebar by diameter, excavation, bedding sand, roofing); everything else
is the net quantity, as the QuickDesign appendix also measures it.

Rules taken from the QuickDesign manual appendix (our reading of it,
not checked against its locked source):
  * lintel: plain wall wider than 2.80 m → one horizontal line;
    window → two horizontal lines + 2.2 m vertical;
    door → one horizontal line + 4.0 m vertical
  * structure plaster: columns, four sides, floor to beam underside
  * plaster sides by M0/M1/M2, paint sides by P0/P1/P2
"""
from __future__ import annotations

import math
import re
from collections import OrderedDict
from dataclasses import dataclass

from .model import Project
from .rates import Rates, q2

COVER = 0.025          # concrete cover to stirrups, m
HOOK = 0.10            # stirrup hooks, m per stirrup
BEDDING = 0.05         # sand under footings, m
LEAN = 0.05            # lean concrete under footings, m
BEAM_UNDERSIDE = 0.50  # default beam depth for column plaster, m

SECTIONS = [
    "งานดิน", "งานคอนกรีต", "งานไม้แบบ", "งานเหล็กเสริม", "งานก่อ ฉาบ",
    "งานทาสี", "งานประตู หน้าต่าง", "งานหลังคา",
]


@dataclass
class Line:
    section: str
    item: str
    qty: float
    unit: str
    labour_code: str = ""
    note: str = ""
    labour_factor: float = 1.0   # converts qty to the labour unit (kg → ตัน = 0.001)

    @property
    def price_key(self) -> str:
        return self.item


_BAR = re.compile(r"^\s*(?:(\d+)\s*[-x×]\s*)?(RB|DB)\s*(\d+)\s*(?:@\s*([\d.]+))?\s*$", re.I)


def parse_bar(spec: str):
    """``"4-DB12"`` → (4, "DB12", None); ``"RB6@0.15"`` → (None, "RB6", 0.15)."""
    m = _BAR.match(spec or "")
    if not m:
        return None
    n = int(m.group(1)) if m.group(1) else None
    size = f"{m.group(2).upper()}{int(m.group(3))}"
    sp = float(m.group(4)) if m.group(4) else None
    return n, size, sp


def bar_count(span: float, spacing: float) -> int:
    if not spacing or spacing <= 0:
        return 0
    return int(math.floor(span / spacing + 1e-9)) + 1


def rebar_labour_code(size: str) -> str:
    d = int(re.sub(r"\D", "", size) or 0)
    if d < 10:
        return "1.10.1"
    if d <= 16:
        return "1.10.2"
    return "1.10.3"


class Takeoff:
    """Collects bar lengths and lines while it walks the project."""

    def __init__(self, project: Project, rates: Rates):
        self.p = project
        self.r = rates
        self.bar_m: "OrderedDict[str, float]" = OrderedDict()
        self.lines: list[Line] = []

    # -- helpers ----------------------------------------------------------
    def _bars(self, size: str, metres: float) -> None:
        if metres > 0:
            self.bar_m[size] = self.bar_m.get(size, 0.0) + metres

    def _stirrups(self, spec: str, run: float, b: float, h: float, times: int) -> None:
        bar = parse_bar(spec)
        if not bar or not bar[2]:
            return
        _n, size, sp = bar
        each = 2 * ((b - 2 * COVER) + (h - 2 * COVER)) + HOOK
        self._bars(size, bar_count(run, sp) * each * times)

    def _mesh(self, spec: str, a: float, b: float, times: int = 1, trim: float = 0.0) -> None:
        """Bars both ways over an ``a`` × ``b`` panel."""
        bar = parse_bar(spec)
        if not bar or not bar[2]:
            return
        _n, size, sp = bar
        run = bar_count(a, sp) * max(0.0, b - trim) + bar_count(b, sp) * max(0.0, a - trim)
        self._bars(size, run * times)

    def add(self, section, item, qty, unit, code="", note="", factor=1.0) -> None:
        if qty and qty > 0:
            self.lines.append(Line(section, item, q2(qty), unit, code, note, factor))

    # -- groups ---------------------------------------------------------------
    def earthwork(self) -> None:
        net = total = sand = lean = conc = 0.0
        deepest = 0.0
        for f in self.p.footings:
            area = f.width * f.length
            if f.depth <= self.r.excavation_deep_m:
                pit = area * f.depth
                pit_total = pit * (1 + self.r.excavation_waste_pct / 100)
            else:
                side = 2 * self.r.excavation_side_m
                pit = pit_total = (f.width + side) * (f.length + side) * f.depth
            net += pit * f.count
            total += pit_total * f.count
            sand += area * BEDDING * f.count
            lean += area * LEAN * f.count
            conc += area * f.thickness * f.count
            deepest = max(deepest, f.depth)
        if not net:
            return
        if deepest > 1.5 or total < 25:
            code = "1.3.1c"
        elif deepest > 1.0 or total <= 100:
            code = "1.3.1b"
        else:
            code = "1.3.1a"
        self.add("งานดิน", "ขุดดินฐานราก", total, "ลบ.ม.", code,
                 f"สุทธิ {q2(net)} ลบ.ม. รวมเผื่อตามเกณฑ์ 2569")
        sand_w = sand * (1 + self.r.bedding_waste_pct.get("ทราย", 25.0) / 100)
        self.add("งานดิน", "ทรายรองก้นหลุม หนา 5 ซม.", sand_w, "ลบ.ม.", "1.5",
                 "เผื่อตามเกณฑ์ 2569")
        self.add("งานดิน", "คอนกรีตหยาบรองก้นหลุม หนา 5 ซม.", lean, "ลบ.ม.", "1.6.1")
        backfill = net - conc - sand - lean
        self.add("งานดิน", "ถมดินกลับ", backfill, "ลบ.ม.", "1.4")

    def concrete_and_forms(self) -> None:
        vol = OrderedDict()
        form = 0.0
        for f in self.p.footings:
            vol["ฐานราก"] = vol.get("ฐานราก", 0) + f.width * f.length * f.thickness * f.count
            form += 2 * (f.width + f.length) * f.thickness * f.count
            self._mesh(f.bars, f.width, f.length, f.count, trim=0.15)
        for c in self.p.columns:
            vol["เสา"] = vol.get("เสา", 0) + c.width * c.depth * c.height * c.count
            form += 2 * (c.width + c.depth) * c.height * c.count
            bar = parse_bar(c.main_bars)
            if bar and bar[0]:
                self._bars(bar[1], bar[0] * c.height * c.count)
            self._stirrups(c.stirrup, c.height, c.width, c.depth, c.count)
        for b in self.p.beams:
            vol["คาน"] = vol.get("คาน", 0) + b.width * b.depth * b.length * b.count
            form += (b.width + 2 * b.depth) * b.length * b.count
            for spec in (b.top_bars, b.bottom_bars):
                bar = parse_bar(spec)
                if bar and bar[0]:
                    self._bars(bar[1], bar[0] * b.length * b.count)
            self._stirrups(b.stirrup, b.length, b.width, b.depth, b.count)
        for s in self.p.slabs:
            vol["พื้น"] = vol.get("พื้น", 0) + s.area * s.thickness
            if not s.on_ground:
                form += s.area
            short = s.short_span or math.sqrt(s.area)
            long_ = s.area / short if short else 0
            self._mesh(s.bars, short, long_)
        code = "1.7a" if self.p.storeys <= 1 else "1.7b"
        for part, v in vol.items():
            self.add("งานคอนกรีต", f"คอนกรีตผสมเสร็จ ({part})", v, "ลบ.ม.", code)
        fcode = "1.8.1a" if form >= 5000 else "1.8.1b"
        self.add("งานไม้แบบ", "ไม้แบบ", form, "ตร.ม.", fcode)

    def rebar(self) -> None:
        total_kg = 0.0
        for size in sorted(self.bar_m, key=lambda s: (s[:2], int(s[2:]))):
            kg_m = float(self.r.rebar_kg_m.get(size, 0))
            waste = float(self.r.rebar_waste_pct.get(size, 0))
            kg = self.bar_m[size] * kg_m * (1 + waste / 100)
            total_kg += kg
            self.add("งานเหล็กเสริม", f"เหล็กเสริม {size}", kg, "กก.", rebar_labour_code(size),
                     f"ยาว {q2(self.bar_m[size])} ม. เผื่อ {waste:g}% ค่าแรงคิดต่อตัน", 0.001)
        self.add("งานเหล็กเสริม", "ลวดผูกเหล็ก", total_kg / 1000 * self.r.tie_wire_kg_per_tonne,
                 "กก.", "", "30 กก. ต่อเหล็ก 1 ตัน")

    def walls(self) -> None:
        masonry = {"brick": ("ก่ออิฐมอญครึ่งแผ่น", "2.3.1a"),
                   "qcon": ("ก่ออิฐมวลเบา", "2.3.1b")}
        lintel = plaster_in = plaster_out = paint_in = paint_out = 0.0
        laid = OrderedDict()
        door_sets = 0
        for w in self.p.walls:
            clear = max(0.0, w.length - w.column_width)
            gross = clear * max(0.0, w.height - w.beam_depth)
            holes = span_lintel = 0.0
            ops = [o for o in (self.p.opening(n) for n in w.openings) if o is not None]
            for o in ops:                       # one span; each name = one piece
                holes += o.width * o.height
                span_lintel += (2 * o.width + 2.2) if o.kind == "window" else (o.width + 4.0)
            if not ops and clear > 2.80:
                span_lintel += clear
            lintel += span_lintel * w.count
            area = max(0.0, gross - holes) * w.count
            if w.wall_type in masonry:
                laid[w.wall_type] = laid.get(w.wall_type, 0.0) + area
            sides_out = {"P0": 0, "P1": 1, "P2": 2}.get(w.paint, 0)
            sides_in = 2 - sides_out
            plastered = {"M0": 0, "M1": 1, "M2": 2}.get(w.mortar, 2)
            out_pl = min(plastered, sides_out)
            plaster_out += area * out_pl
            plaster_in += area * (plastered - out_pl)
            paint_out += area * sides_out
            paint_in += area * sides_in
        for kind, area in laid.items():
            name, code = masonry[kind]
            self.add("งานก่อ ฉาบ", name, area, "ตร.ม.", code)
        self.add("งานก่อ ฉาบ", "เสาเอ็น คานทับหลัง", lintel, "เมตร", "2.3.1e",
                 "ตามภาคผนวกคู่มือ (ประตู 1 แถว+4 ม., หน้าต่าง 2 แถว+2.2 ม.)")
        self.add("งานก่อ ฉาบ", "ฉาบปูนผนังภายใน", plaster_in, "ตร.ม.", "2.3.2a")
        self.add("งานก่อ ฉาบ", "ฉาบปูนผนังภายนอก", plaster_out, "ตร.ม.", "2.3.2b")
        col_plaster = sum(2 * (c.width + c.depth) * max(0.0, c.height - BEAM_UNDERSIDE) * c.count
                          for c in self.p.columns)
        self.add("งานก่อ ฉาบ", "ฉาบปูนโครงสร้าง (เสา 4 ด้าน)", col_plaster, "ตร.ม.", "2.3.2c")
        self.add("งานทาสี", "ทาสีน้ำอะครีลิค ภายใน", paint_in, "ตร.ม.", "2.8.1a")
        self.add("งานทาสี", "ทาสีน้ำอะครีลิค ภายนอก", paint_out, "ตร.ม.", "2.8.1b")
        for o in self.p.openings:
            area = o.width * o.height * o.count
            label = f"{'ประตู' if o.kind == 'door' else 'หน้าต่าง'} {o.name} {o.width:.2f}x{o.height:.2f} ม."
            if o.material == "aluminium":
                self.add("งานประตู หน้าต่าง", f"{label} (ชุดอลูมิเนียม)", o.count, "ชุด", "",
                         "ค่าแรงรวมในราคาติดตั้งของผู้ขาย")
                continue
            if o.kind == "door":
                self.add("งานประตู หน้าต่าง", f"{label} — วงกบ", area, "ตร.ม.", "2.5.2a")
                self.add("งานประตู หน้าต่าง", f"{label} — บาน", area, "ตร.ม.", "2.5.3")
                door_sets += o.count
            else:
                self.add("งานประตู หน้าต่าง", f"{label} — วงกบ", area, "ตร.ม.", "2.5.2b")
                self.add("งานประตู หน้าต่าง", f"{label} — บาน", area, "ตร.ม.", "2.5.3c")
        self.add("งานประตู หน้าต่าง", "อุปกรณ์ประตู (ลูกบิด กุญแจ)", door_sets, "ชุด", "2.5.4")

    def roof(self) -> None:
        r = self.p.roof
        if not r:
            return
        slope_area = r.plan_area / math.cos(math.radians(r.slope_deg))
        waste = float(self.r.roofing_waste_pct.get(r.shape, 3.0))
        cover = {"concrete_tile": ("มุงกระเบื้องคอนกรีต", "2.1.3", "2.1.3r"),
                 "metal_sheet": ("มุงหลังคาเหล็กรีดลอน", "2.1.8", "2.1.8f"),
                 "ceramic_tile": ("มุงกระเบื้องดินเผาเคลือบเซรามิค", "2.1.7", "2.1.7r")}
        name, code, ridge_code = cover.get(r.material, cover["concrete_tile"])
        self.add("งานหลังคา", name, slope_area * (1 + waste / 100), "ตร.ม.", code,
                 f"พื้นที่ราบ {q2(r.plan_area)} ตร.ม. ลาด {r.slope_deg:g}° เผื่อ {waste:g}%")
        self.add("งานหลังคา", "ครอบสัน ครอบตะเข้สัน", r.ridge_length + r.hip_length, "เมตร",
                 ridge_code)
        self.add("งานหลังคา", "รางน้ำตะเข้", r.valley_length, "เมตร", "2.1.10c")
        self.add("งานหลังคา", "เชิงชาย ทับเชิงชาย", r.eave_length, "เมตร", "2.1.10a")
        if r.steel_kg:
            sw = {"gable": 3.0, "shed": 3.0, "hip": 5.0}.get(r.shape, 3.0)
            self.add("งานหลังคา", "โครงหลังคาเหล็กรูปพรรณ", r.steel_kg * (1 + sw / 100), "กก.",
                     "1.11.1", f"เผื่อ {sw:g}%")

    def run(self) -> list[Line]:
        self.earthwork()
        self.concrete_and_forms()
        self.rebar()
        self.walls()
        self.roof()
        order = {s: i for i, s in enumerate(SECTIONS)}
        self.lines.sort(key=lambda ln: order.get(ln.section, 99))
        return self.lines


def takeoff(project: Project, rates: Rates) -> list[Line]:
    return Takeoff(project, rates).run()
