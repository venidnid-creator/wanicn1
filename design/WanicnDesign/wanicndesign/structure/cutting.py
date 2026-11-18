# -*- coding: utf-8 -*-
"""Bar cutting list (stage 6) and the cutting plan from stock bars.

Every bar of the designed building is listed with its shape, cutting
length and number, then the pieces of each size are cut from 10 m stock
bars by first-fit decreasing, giving the number of stock bars to buy and
the offcut.

Rules
-----
* Laps, development lengths: ACI 318 12.2.2, 12.15, 12.16 (sheets.development)
  [EIT1008-DEV].
* Hooks and bends: ACI 318 7.1, 7.2 — 90° hook 12db, 180° hook 4db ≥ 65 mm,
  stirrup and tie 135° hook 6db ≥ 75 mm; inside bend diameter 6db (≤ DB25),
  8db (DB28–DB32), 4db for stirrups and ties ≤ 16 mm [EIT1008-HOOK]. The
  cutting length is measured along the bar centre line (straight parts to the
  tangent points plus the arcs plus the hook extensions).
* Covers: ประกาศ มท. 2567 ตาราง 13 [MI2567-29C].
* Beams: the top bars of a beam line are the largest top bars of its spans,
  continuous over the line and lapped near midspan when longer than a stock
  bar; the bottom bars of each span reach a full tension lap across interior
  supports and end in a 90° hook at the far face of an end column.
* Columns: bars lapped above every floor (class B tension lap, safe for
  wind and earthquake), a 90° foot on the footing mat, a 90° hook into the
  top beam; ties at the designed spacing (closer end zones of the
  earthquake check when present).
* Weights of bars: กรมบัญชีกลาง 2569 (data/labour_2569.json) [CGD2569].
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .materials import FY
from .rules import (COVER_BEAM, COVER_EARTH, COVER_EXPOSED, COVER_SLAB, cover_factor, tie_bar)
from .sections import BAR_DIA

STOCK = 10.0                     # m, stock bar length


@dataclass
class BarItem:
    element: str                 # "คาน FL2 แนว A", "เสา 1A", …
    mark: str                    # element mark (B1, C2 …)
    bar: str                     # bar mark within the element: "บน", "ล่าง 1A-2A", "ปลอก" …
    size: str
    shape: str
    length: float                # m, cutting length of one bar
    count: int                   # bars in one element
    times: int = 1               # elements alike
    note: str = ""

    @property
    def total_count(self) -> int:
        return self.count * self.times

    @property
    def total_length(self) -> float:
        return self.length * self.total_count


@dataclass
class StockPlan:
    size: str
    stock: float
    bars: int                    # stock bars to buy
    used: float                  # m of pieces
    pieces: int
    patterns: list = field(default_factory=list)   # (count, [piece lengths])

    @property
    def waste_pct(self) -> float:
        bought = self.bars * self.stock
        return 100 * (1 - self.used / bought) if bought else 0.0


# ---------------------------------------------------------------------------
# Bends and hooks (cm)
# ---------------------------------------------------------------------------

def bend_diameter(size: str, tie: bool = False) -> float:
    db = BAR_DIA[size]
    if tie and db <= 1.6:
        return 4 * db
    return 6 * db if db <= 2.5 else 8 * db


def hook_add(size: str, angle: int, tie: bool = False) -> float:
    """Centre-line length added beyond the tangent point of a hook, cm."""
    db = BAR_DIA[size]
    r = bend_diameter(size, tie) / 2 + db / 2
    arc = math.radians(angle) * r
    if angle == 90:
        ext = 12 * db
    elif angle == 180:
        ext = max(4 * db, 6.5)
    else:                                        # 135° stirrup / tie hook
        ext = max(6 * db, 7.5)
    return arc + ext


def hooked_to_face(size: str, angle: int = 90, tie: bool = False) -> float:
    """What a hook adds to a straight length measured to the outer face of
    the bend (cover line): the arc and extension, less the bend's set-back."""
    db = BAR_DIA[size]
    setback = bend_diameter(size, tie) / 2 + db
    return hook_add(size, angle, tie) - setback


def stirrup_length(size: str, b_cm: float, h_cm: float, cover_cm: float) -> float:
    """Closed stirrup or tie with two 135° hooks, cm."""
    db = BAR_DIA[size]
    D = bend_diameter(size, tie=True)
    w, h = b_cm - 2 * cover_cm - db, h_cm - 2 * cover_cm - db      # centre-line rectangle
    r = D / 2 + db / 2
    corners = 4 * (math.pi / 2 * r - 2 * r)                        # arcs replace the square corners
    return 2 * (w + h) + corners + 2 * hook_add(size, 135, tie=True)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_count(spec: str):
    """"3-DB16" → (3, "DB16"); "RB9@0.15" → (None, "RB9", 0.15)."""
    if "@" in spec:
        size, s = spec.split("@")
        return None, size.strip(), float(s)
    n, size = spec.split("-", 1)
    return int(n), size.strip(), None


def _detail_spacing(text: str):
    """"ปลอกปลายเสา RB9@0.1 ยาว 0.45 ม." → (0.10, 0.45)."""
    m = re.search(r"@([\d.]+).*?ยาว ([\d.]+)", text or "")
    return (float(m.group(1)), float(m.group(2))) if m else None


def _pieces(length_m: float, lap_m: float) -> tuple[int, float]:
    """Split a bar longer than a stock bar into pieces lapped by ``lap_m``."""
    if length_m <= STOCK + 1e-9:
        return 1, length_m
    k = math.ceil((length_m - lap_m) / (STOCK - lap_m) - 1e-9)
    return k, (length_m + (k - 1) * lap_m) / k


# ---------------------------------------------------------------------------
# Elements
# ---------------------------------------------------------------------------

def _support_width(res, level: str, node: str, along_x: bool) -> float:
    for c in res.columns:
        if c.node == node and c.segment.endswith(level):
            return c.b if along_x else c.h
    return res.building.column_width


def beam_runs(res):
    """Primary beams grouped into continuous lines: {(level, axis, coord): [spans in order]}."""
    runs: dict = {}
    for x in res.beams:
        if x.kind != "beam" or not x.line_xy:
            continue
        x0, y0, x1, y1 = x.line_xy
        along_x = abs(y1 - y0) < 1e-9
        key = (x.level, "x" if along_x else "y", round(y0 if along_x else x0, 4))
        runs.setdefault(key, []).append(x)
    out = {}
    for key, spans in runs.items():
        axis = key[1]
        spans.sort(key=lambda s: s.line_xy[0] if axis == "x" else s.line_xy[1])
        group = [spans[0]]
        for s in spans[1:]:
            prev = group[-1].line_xy
            end = prev[2] if axis == "x" else prev[3]
            start = s.line_xy[0] if axis == "x" else s.line_xy[1]
            if abs(start - end) < 1e-6:
                group.append(s)
            else:
                out[(key, len(out))] = group
                group = [s]
        out[(key, len(out))] = group
    return out


def beam_items(res, dev) -> list[BarItem]:
    b, mat = res.building, res.concrete
    k = cover_factor(mat)
    items = []
    for (key, _n), spans in beam_runs(res).items():
        level, axis, coord = key
        exposed = b.level(level) is not None and b.level(level).slab == "on_ground"
        cover = (COVER_EXPOSED if exposed else COVER_BEAM) * k
        along_x = axis == "x"
        name = f"คาน {level} แนว {spans[0].line}"
        first, last = spans[0].span.split("-")[0], spans[-1].span.split("-")[1]
        w0 = _support_width(res, level, first, along_x)
        w1 = _support_width(res, level, last, along_x)
        run_cc = sum(s.length for s in spans)
        # top bars: the largest of the spans, continuous, hooked at both ends
        top = max(spans, key=lambda s: _area(s.top))
        nt, st, _ = parse_count(top.top)
        L = run_cc + (w0 / 2 - cover / 100) + (w1 / 2 - cover / 100) + 2 * hooked_to_face(st) / 100
        npc, piece = _pieces(L, dev(st)["lap_top"] / 100)
        items.append(BarItem(name, "/".join(dict.fromkeys(s.mark for s in spans)), "เหล็กบนต่อเนื่อง", st,
                             "ขอ 90° สองปลาย" + (f", ทาบ {npc - 1} จุดกลางช่วง" if npc > 1 else ""),
                             round(piece, 3), nt * npc))
        # bottom bars per span
        for i, s in enumerate(spans):
            nb, sb, _ = parse_count(s.bottom)
            lap = dev(sb)["lap"] / 100
            left = (w0 / 2 - cover / 100 + hooked_to_face(sb) / 100) if i == 0 else lap / 2
            right = (w1 / 2 - cover / 100 + hooked_to_face(sb) / 100) if i == len(spans) - 1 else lap / 2
            L = s.length + left + right
            npc, piece = _pieces(L, lap)
            shape = "ตรง" if 0 < i < len(spans) - 1 else ("ขอ 90° สองปลาย" if len(spans) == 1 else "ขอ 90° ปลายเดียว")
            items.append(BarItem(name, s.mark, f"เหล็กล่าง {s.span}", sb, shape, round(piece, 3), nb * npc))
            # stirrups
            _, ss, sp = parse_count(s.stirrup)
            wa = _support_width(res, level, s.span.split("-")[0], along_x)
            wb = _support_width(res, level, s.span.split("-")[1], along_x)
            clear = s.length - wa / 2 - wb / 2
            count = _stirrup_count(res, s, clear, sp)
            items.append(BarItem(name, s.mark, f"ปลอก {s.span}", ss, "ปลอกปิด ขอ 135°",
                                 round(stirrup_length(ss, s.b * 100, s.h * 100, cover) / 100, 3), count))
    # secondary, cantilever and stair beams: one span each
    for s in res.beams:
        if s.kind == "beam":
            continue
        cover = COVER_BEAM * k
        nt, st, _ = parse_count(s.top)
        nb, sb, _ = parse_count(s.bottom)
        name = {"secondary": "คานซอย", "cantilever": "คานยื่น", "stair": "คานบันได"}.get(s.kind, "คาน")
        name = f"{name} {s.level} {s.span}"
        if s.kind == "cantilever":
            top_len = s.length + dev(st)["ld_top"] / 100 + hooked_to_face(st) / 100     # back-span anchorage
            bot_len = s.length + dev(sb)["ld"] / 100
        else:
            top_len = s.length + 2 * hooked_to_face(st) / 100
            bot_len = s.length + 2 * hooked_to_face(sb) / 100
        items.append(BarItem(name, s.mark, "เหล็กบน", st, "ขอ 90°", round(top_len, 3), nt))
        items.append(BarItem(name, s.mark, "เหล็กล่าง", sb, "ขอ 90°" if s.kind != "cantilever" else "ตรง",
                             round(bot_len, 3), nb))
        _, ss, sp = parse_count(s.stirrup)
        items.append(BarItem(name, s.mark, "ปลอก", ss, "ปลอกปิด ขอ 135°",
                             round(stirrup_length(ss, s.b * 100, s.h * 100, cover) / 100, 3),
                             _stirrup_count(res, s, s.length - b.column_width, sp)))
    return items


def _stirrup_count(res, beam, clear, spacing):
    clear = max(clear, 0.1)
    zone = None
    if res.seismic:
        for c in res.seismic.checks:
            if c.kind == "beam" and c.where == f"{beam.level} {beam.span}":
                zone = _detail_spacing(c.detail)
    if zone and zone[0] < spacing:
        s_end, l_end = zone
        l_end = min(l_end, clear / 2)
        n_end = 2 * (math.floor(l_end / s_end) + 1)
        mid = max(0.0, clear - 2 * l_end)
        return n_end + max(0, math.ceil(mid / spacing) - 1)
    return math.floor(clear / spacing + 1e-9) + 1


def _area(spec: str) -> float:
    from .sections import bar_area
    n, size, _ = parse_count(spec)
    return (n or 0) * bar_area(size)


def column_items(res, dev) -> list[BarItem]:
    b, mat = res.building, res.concrete
    k = cover_factor(mat)
    from . import seismic
    cover = seismic.COVER
    names = [lv.name for lv in b.levels]
    foots = {}
    for f in res.footings:
        for n in (f.nodes or [f.node]):
            foots[n] = f
    items = []
    stacks: dict = {}
    for c in res.columns:
        stacks.setdefault(c.node, []).append(c)
    for node, segs in stacks.items():
        segs = sorted(segs, key=lambda c: (0 if c.segment.startswith("ฐานราก") else
                                             1 + names.index(c.segment.split("–")[1])))
        for i, c in enumerate(segs):
            n, size, _ = parse_count(c.bars)
            lap = dev(size)["lap"] / 100                     # class B tension lap
            L = c.height
            shape = "ตรง"
            if i == 0:                                       # foot on the footing mat
                f = foots.get(node)
                t = f.thickness if f else 0.4
                L += t - (COVER_EARTH * k) / 100 - 2 * BAR_DIA["DB16"] / 100 + hooked_to_face(size) / 100
                shape = "ขางอ 90° ที่ฐานราก"
            if i < len(segs) - 1:
                L += lap
            else:                                            # up to the top beam's cover, then a 90° hook
                L += hooked_to_face(size) / 100 - (COVER_BEAM * k) / 100
                shape = (shape + " / " if i == 0 else "") + "ขอ 90° เข้าคานบนสุด"
            npc, piece = _pieces(L, lap)
            items.append(BarItem(f"เสา {node}", c.mark, f"เหล็กยืน {c.segment}", size, shape, round(piece, 3),
                                 n * npc))
            ts, tsp = c.ties.split("@")
            tsp = float(tsp)
            count = math.floor(c.height / tsp + 1e-9) + 1
            if res.seismic:
                for ch in res.seismic.checks:
                    if ch.kind == "column" and ch.where == f"{node} {c.segment}":
                        z = _detail_spacing(ch.detail)
                        if z and z[0] < tsp:
                            l_end = min(z[1], c.height / 2)
                            count = 2 * (math.floor(l_end / z[0]) + 1) + \
                                max(0, math.ceil((c.height - 2 * l_end) / tsp) - 1)
            items.append(BarItem(f"เสา {node}", c.mark, f"ปลอก {c.segment}", ts.strip(), "ปลอกปิด ขอ 135°",
                                 round(stirrup_length(ts.strip(), c.b * 100, c.h * 100, cover) / 100, 3), count))
    return items


def footing_items(res) -> list[BarItem]:
    mat = res.concrete
    k = cover_factor(mat)
    items = []
    groups: dict = {}
    for f in res.footings:
        groups.setdefault(f.mark, []).append(f)
    for mark, fs in groups.items():
        f = fs[0]
        for spec, length, label in ((f.bars_x, f.width, "เหล็กแนว X"), (f.bars_y, f.length, "เหล็กแนว Y")):
            n, size, _ = parse_count(spec)
            L = length - 2 * COVER_EARTH * k / 100 + 2 * hooked_to_face(size) / 100
            items.append(BarItem(f"ฐานราก {mark}", mark, label, size, "ขอ 90° สองปลาย", round(L, 3), n,
                                 len(fs)))
    return items


def slab_items(res) -> list[BarItem]:
    mat = res.concrete
    k = cover_factor(mat)
    items = []
    for s in res.slabs:
        if not s.rect:
            continue
        x0, y0, x1, y1 = s.rect
        lx, ly = x1 - x0, y1 - y0
        short_x = lx <= ly
        S, Lg = (lx, ly) if short_x else (ly, lx)
        for spec, span, across, label in ((s.bars_short, S, Lg, "ล่างช่วงสั้น"), (s.bars_long, Lg, S, "ล่างช่วงยาว")):
            if not spec or spec == "-" or "@" not in spec:
                continue
            _, size, sp = parse_count(spec)
            hook = 180 if size.startswith("RB") else 90
            L = span + 2 * hooked_to_face(size, hook) / 100
            n = math.floor(across / sp + 1e-9) + 1
            npc, piece = _pieces(L, 0.40)
            items.append(BarItem(f"พื้น {s.level} {s.panel}", s.mark, label, size,
                                 f"ขอ {hook}° สองปลาย", round(piece, 3), n * npc))
        if s.bars_top and "@" in s.bars_top and s.kind != "on-ground":
            _, size, sp = parse_count(s.bars_top)
            hook = 180 if size.startswith("RB") else 90
            reach = S / 4 if s.kind != "cantilever" else s.lx + 0.3
            L = reach + 0.20 + 2 * hooked_to_face(size, 90) / 100
            n = math.floor((2 * (lx + ly) if s.kind != "cantilever" else s.ly) / sp + 1e-9)
            items.append(BarItem(f"พื้น {s.level} {s.panel}", s.mark, "เหล็กบนที่ขอบ", size,
                                 "ขอ 90° สองปลาย (ขาตั้ง)", round(L, 3), n))
    for st in res.stairs:
        if st.geom is None:
            continue
        g = st.geom
        for f in g.flights:
            incl = math.hypot(min(f.going, g.length), f.z_to - f.z_from) + max(0.0, g.length - f.going)
            _, size, sp = parse_count(st.bars_main)
            n = math.floor(f.width / sp + 1e-9) + 1
            items.append(BarItem(f"บันได {st.mark}", st.mark, "เหล็กหลัก", size, "พับตามช่วงลาด/ชานพัก",
                                 round(incl + 2 * hooked_to_face(size) / 100, 3), n))
            _, tsz, tsp = parse_count(st.bars_temp)
            items.append(BarItem(f"บันได {st.mark}", st.mark, "เหล็กกันร้าว", tsz, "ขอ 180° สองปลาย",
                                 round(f.width + 2 * hooked_to_face(tsz, 180) / 100, 3),
                                 math.floor(incl / tsp + 1e-9) + 1))
    return items


def cutting_list(res) -> list[BarItem]:
    from .sheets import development
    cache: dict = {}

    def dev(size):
        if size not in cache:
            cache[size] = development(res.concrete, size) if size.startswith("DB") else \
                {k: v for k, v in development(res.concrete, "DB12").items()}
        return cache[size]

    return beam_items(res, dev) + column_items(res, dev) + footing_items(res) + slab_items(res)


# ---------------------------------------------------------------------------
# Cutting from stock bars
# ---------------------------------------------------------------------------

def stock_plan(items: list[BarItem], stock: float = STOCK, kerf: float = 0.0) -> list[StockPlan]:
    """First-fit decreasing of the pieces of each size into stock bars."""
    by_size: dict = {}
    for it in items:
        by_size.setdefault(it.size, []).extend([it.length] * it.total_count)
    plans = []
    for size, pieces in sorted(by_size.items(), key=lambda kv: (kv[0][:2], BAR_DIA[kv[0]])):
        pieces.sort(reverse=True)
        bins: list[list[float]] = []
        free: list[float] = []
        for p in pieces:
            p = min(p, stock)
            for i, f in enumerate(free):
                if p + kerf <= f + 1e-9:
                    bins[i].append(p)
                    free[i] -= p + kerf
                    break
            else:
                bins.append([p])
                free.append(stock - p - kerf)
        patterns: dict = {}
        for b_ in bins:
            key = tuple(round(x, 2) for x in b_)
            patterns[key] = patterns.get(key, 0) + 1
        plans.append(StockPlan(size, stock, len(bins), sum(pieces), len(pieces),
                               sorted(((n, list(p)) for p, n in patterns.items()), key=lambda t: -t[0])))
    return plans


def weights(items, kg_m: dict) -> dict:
    out: dict = {}
    for it in items:
        out[it.size] = out.get(it.size, 0.0) + it.total_length * float(kg_m.get(it.size, 0.0))
    return out


def write_cutting_xlsx(res, path: str, rates=None):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from ..rates import Rates
    rates = rates or Rates()
    items = cutting_list(res)
    plans = stock_plan(items)
    wb = Workbook()
    ws = wb.active
    ws.title = "ตารางตัดเหล็ก"
    ws.append([f"ตารางตัดเหล็ก — {res.building.name}"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append(["ความยาวตัดวัดตามแนวศูนย์กลางเหล็ก รวมขอและส่วนโค้งตาม ACI 318 ข้อ 7.1–7.2, ระยะทาบตามข้อ 12.15–12.16, "
               "ระยะหุ้มตามประกาศ มท. 2567 ตาราง 13; ตรวจสอบกับแบบก่อสร้างก่อนตัดจริง"])
    head = ["ชิ้นส่วน", "Mark", "เหล็ก", "ขนาด", "รูปร่าง", "ยาวตัด (ม.)", "จำนวน/ชิ้น", "จำนวนชิ้น", "รวมเส้น",
            "รวมยาว (ม.)", "น้ำหนัก (กก.)"]
    ws.append(head)
    for c in ws[3]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="DDEBF7")
    for it in items:
        kg = it.total_length * float(rates.rebar_kg_m.get(it.size, 0))
        ws.append([it.element, it.mark, it.bar, it.size, it.shape, it.length, it.count, it.times, it.total_count,
                   round(it.total_length, 2), round(kg, 2)])
    for col, w in zip("ABCDEFGHIJK", (26, 10, 24, 8, 30, 10, 10, 10, 9, 11, 11)):
        ws.column_dimensions[col].width = w
    ws2 = wb.create_sheet("ตัดจากเหล็กเส้น 10 ม.")
    ws2.append(["ขนาด", "จำนวนท่อน", "ยาวรวมที่ใช้ (ม.)", "ซื้อเหล็กเส้น 10 ม. (เส้น)", "เศษ (%)", "น้ำหนักซื้อ (กก.)",
                "เผื่อตามเกณฑ์กรมบัญชีกลาง (%)", "รูปแบบการตัดที่ใช้มาก (จำนวนเส้น × ความยาวท่อน)"])
    for c in ws2[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="DDEBF7")
    for p in plans:
        kg = p.bars * p.stock * float(rates.rebar_kg_m.get(p.size, 0))
        pats = "; ".join(f"{n} × [{', '.join(f'{x:.2f}' for x in pat)}]" for n, pat in p.patterns[:4])
        ws2.append([p.size, p.pieces, round(p.used, 2), p.bars, round(p.waste_pct, 1), round(kg, 1),
                    rates.rebar_waste_pct.get(p.size, ""), pats])
    for col, w in zip("ABCDEFGH", (8, 11, 15, 20, 9, 16, 22, 90)):
        ws2.column_dimensions[col].width = w
    wb.save(path)
    return items, plans


_ = FY, COVER_SLAB, tie_bar
