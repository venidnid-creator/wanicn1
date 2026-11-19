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
from .materials import LABOUR_ONLY, READY_MIX
from .rates import Rates, q2

COVER = 0.025          # concrete cover to stirrups, m
HOOK = 0.10            # stirrup hooks, m per stirrup
BEDDING = 0.05         # sand under footings, m
LEAN = 0.05            # lean concrete under footings, m
BEAM_UNDERSIDE = 0.50  # default beam depth for column plaster, m

SECTIONS = [
    "งานดิน", "งานคอนกรีต", "งานไม้แบบ", "งานเหล็กเสริม", "งานก่อ ฉาบ",
    "งานทาสี", "งานประตู หน้าต่าง", "งานพื้น ผนัง ฝ้า", "งานสุขภัณฑ์", "งานหลังคา",
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
    materials: tuple = ()        # ((ref, qty per unit), …): "R:<recipe>", "FORM" or a price key

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

    def add(self, section, item, qty, unit, code="", note="", factor=1.0, mats=()) -> None:
        if qty and qty > 0:
            self.lines.append(Line(section, item, q2(qty), unit, code, note, factor, tuple(mats)))

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
                 f"สุทธิ {q2(net)} ลบ.ม. รวมเผื่อตามเกณฑ์ 2569", mats=LABOUR_ONLY)
        sand_w = sand * (1 + self.r.bedding_waste_pct.get("ทราย", 25.0) / 100)
        self.add("งานดิน", "ทรายรองก้นหลุม หนา 5 ซม.", sand_w, "ลบ.ม.", "1.5",
                 "เผื่อตามเกณฑ์ 2569", mats=[("ทรายหยาบ", 1.0)])
        self.add("งานดิน", "คอนกรีตหยาบรองก้นหลุม หนา 5 ซม.", lean, "ลบ.ม.", "1.6.1",
                 "สูตรวัสดุ 1.1", mats=[("R:1.1", 1.0)])
        backfill = net - conc - sand - lean
        self.add("งานดิน", "ถมดินกลับ", backfill, "ลบ.ม.", "1.4", "ดินเดิมจากการขุด", mats=LABOUR_ONLY)

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
            self.add("งานคอนกรีต", f"คอนกรีตผสมเสร็จ ({part})", v, "ลบ.ม.", code, mats=[(READY_MIX, 1.0)])
        fcode = "1.8.1a" if form >= 5000 else "1.8.1b"
        self.add("งานไม้แบบ", "ไม้แบบ", form, "ตร.ม.", fcode, "วัสดุ A(0.133)+B(0.774)+C(0.25)", mats=[("FORM", 1.0)])

    def rebar(self) -> None:
        total_kg = 0.0
        for size in sorted(self.bar_m, key=lambda s: (s[:2], int(s[2:]))):
            kg_m = float(self.r.rebar_kg_m.get(size, 0))
            waste = float(self.r.rebar_waste_pct.get(size, 0))
            kg = self.bar_m[size] * kg_m * (1 + waste / 100)
            total_kg += kg
            self.add("งานเหล็กเสริม", f"เหล็กเสริม {size}", kg, "กก.", rebar_labour_code(size),
                     f"ยาว {q2(self.bar_m[size])} ม. เผื่อ {waste:g}% ค่าแรงคิดต่อตัน", 0.001,
                     mats=[(size, 1.0)])
        self.add("งานเหล็กเสริม", "ลวดผูกเหล็ก", total_kg / 1000 * self.r.tie_wire_kg_per_tonne,
                 "กก.", "", "30 กก. ต่อเหล็ก 1 ตัน", mats=[("ลวดผูกเหล็ก", 1.0)])

    def walls(self) -> None:
        masonry = {"brick": ("ก่ออิฐมอญครึ่งแผ่น", "2.3.1a", "6.1"),
                   "qcon": ("ก่ออิฐมวลเบา", "2.3.1b", "6.10")}
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
        tiles = sum(f.area for f in self.p.finishes if f.kind == "wall_tile")
        paint_in = max(0.0, paint_in - tiles)              # no paint behind wall tiles
        for kind, area in laid.items():
            name, code, rc = masonry[kind]
            self.add("งานก่อ ฉาบ", name, area, "ตร.ม.", code, f"สูตรวัสดุ {rc}", mats=[(f"R:{rc}", 1.0)])
        self.add("งานก่อ ฉาบ", "เสาเอ็น คานทับหลัง", lintel, "เมตร", "2.3.1e",
                 "ตามภาคผนวกคู่มือ (ประตู 1 แถว+4 ม., หน้าต่าง 2 แถว+2.2 ม.)", mats=[("R:4.1", 1.0)])
        self.add("งานก่อ ฉาบ", "ฉาบปูนผนังภายใน", plaster_in, "ตร.ม.", "2.3.2a", "สูตรวัสดุ 7.2",
                 mats=[("R:7.2", 1.0)])
        self.add("งานก่อ ฉาบ", "ฉาบปูนผนังภายนอก", plaster_out, "ตร.ม.", "2.3.2b", "สูตรวัสดุ 7.2",
                 mats=[("R:7.2", 1.0)])
        col_plaster = sum(2 * (c.width + c.depth) * max(0.0, c.height - BEAM_UNDERSIDE) * c.count
                          for c in self.p.columns)
        self.add("งานก่อ ฉาบ", "ฉาบปูนโครงสร้าง (เสา 4 ด้าน)", col_plaster, "ตร.ม.", "2.3.2c", "สูตรวัสดุ 7.2",
                 mats=[("R:7.2", 1.0)])
        self.add("งานทาสี", "ทาสีน้ำอะครีลิค ภายใน", paint_in, "ตร.ม.", "2.8.1a",
                 mats=[("สีน้ำอะครีลิค ภายใน (ต่อ ตร.ม.)", 1.0)])
        self.add("งานทาสี", "ทาสีน้ำอะครีลิค ภายนอก", paint_out, "ตร.ม.", "2.8.1b",
                 mats=[("สีน้ำอะครีลิค ภายนอก (ต่อ ตร.ม.)", 1.0)])
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
                self.add("งานประตู หน้าต่าง", f"{label} — กระจก 5 มม.", area * 10.7639, "ตร.ฟ.", "2.5.7",
                         "พื้นที่บานหน้าต่าง", mats=[("กระจกใส 5 มม.", 1.0)])
        self.add("งานประตู หน้าต่าง", "อุปกรณ์ประตู (ลูกบิด กุญแจ)", door_sets, "ชุด", "2.5.4")

    def roof(self) -> None:
        r = self.p.roof
        if not r:
            return
        slope_area = r.plan_area / math.cos(math.radians(r.slope_deg))
        waste = float(self.r.roofing_waste_pct.get(r.shape, 3.0))
        hip = r.shape == "hip"
        # (roof item, ว480 code, ridge code, verge code)
        cover = {"concrete_tile": ("มุงกระเบื้องคอนกรีต", "2.1.3", "2.1.3r", "2.1.3v"),
                 "metal_sheet": ("มุงหลังคาเหล็กรีดลอน", "2.1.8", "2.1.8f", "2.1.8f"),
                 "ceramic_tile": ("มุงกระเบื้องดินเผาเคลือบเซรามิค", "2.1.7", "2.1.7r", "2.1.7v"),
                 "asbestos": ("มุงกระเบื้องลอนคู่ ลอนเล็ก" + (" (ทรงปั้นหยา)" if hip else ""),
                              "2.1.1h" if hip else "2.1.1", "2.1.1r", "2.1.1r")}
        name, code, ridge_code, verge_code = cover.get(r.material, cover["concrete_tile"])
        self.add("งานหลังคา", name, slope_area * (1 + waste / 100), "ตร.ม.", code,
                 f"พื้นที่ราบ {q2(r.plan_area)} ตร.ม. ลาด {r.slope_deg:g}° เผื่อ {waste:g}%",
                 mats=[("กระเบื้องคอนกรีต (รวมอุปกรณ์)", 1.0)] if r.material == "concrete_tile" else ())
        self.add("งานหลังคา", "ครอบสัน ครอบตะเข้สัน", r.ridge_length + r.hip_length, "เมตร",
                 ridge_code)
        self.add("งานหลังคา", "ครอบข้าง ครอบปั้นลม" + (" ครอบชนผนังด้านสูง" if r.shape == "shed" else ""),
                 r.verge_length, "เมตร", verge_code)
        self.add("งานหลังคา", "รางน้ำตะเข้", r.valley_length, "เมตร", "2.1.10c")
        self.add("งานหลังคา", "เชิงชาย ทับเชิงชาย", r.eave_length, "เมตร", "2.1.10a",
                 mats=[("เชิงชายไม้สำเร็จรูป 1\"×8\" + ทับเชิงชาย 1\"×6\"", 1.0)])
        if r.steel_kg:
            sw = {"gable": 3.0, "shed": 3.0, "hip": 5.0}.get(r.shape, 3.0)
            self.add("งานหลังคา", "โครงหลังคาเหล็กรูปพรรณ", r.steel_kg * (1 + sw / 100), "กก.",
                     "1.11.1", f"เผื่อ {sw:g}%", mats=[("เหล็กรูปพรรณ (ทั่วไป)", 1.0)])

    def finishes(self) -> None:
        from .structure.architecture import (CEILINGS, FINISH_RECIPES, FIXTURES, FLOOR_FINISHES,
                                             WALL_TILE)
        sums: "OrderedDict[tuple, float]" = OrderedDict()
        for f in self.p.finishes:
            sums[(f.kind,)] = sums.get((f.kind,), 0.0) + f.area
        for (kind,), area in sums.items():
            if kind == "wall_tile":
                name, code = WALL_TILE
            else:
                group, key = kind.split(":", 1)
                name, code = (FLOOR_FINISHES if group == "floor" else CEILINGS).get(key, ("", ""))
            mats = FINISH_RECIPES.get(kind, ())
            note = "ปริมาณสุทธิ (สูตรวัสดุรวมเผื่อแล้ว)" if any(m[0].startswith("R:") for m in mats) else \
                "ปริมาณสุทธิ ไม่รวมเผื่อเศษ"
            if name:
                self.add("งานพื้น ผนัง ฝ้า", name, area, "ตร.ม.", code, note, mats=mats)
        counts: "OrderedDict[str, int]" = OrderedDict()
        for fx in self.p.fixtures:
            counts[fx.name] = counts.get(fx.name, 0) + fx.count
        for key, n in counts.items():
            name, code = FIXTURES.get(key, (key, ""))
            self.add("งานสุขภัณฑ์", name, n, "ชุด", code)

    def run(self) -> list[Line]:
        self.earthwork()
        self.concrete_and_forms()
        self.rebar()
        self.walls()
        self.finishes()
        self.roof()
        order = {s: i for i, s in enumerate(SECTIONS)}
        self.lines.sort(key=lambda ln: order.get(ln.section, 99))
        return self.lines


def takeoff(project: Project, rates: Rates) -> list[Line]:
    return Takeoff(project, rates).run()
