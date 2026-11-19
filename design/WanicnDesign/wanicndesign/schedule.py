# -*- coding: utf-8 -*-
"""Construction plan (แผนงานก่อสร้าง) by the critical path method, from the priced estimate.

Durations come from the estimate itself: a task's labour (ว480 amounts in
the BOQ) divided by what its crew is paid in a working day,

    days = ceil( labour (บาท) / (crew × daily wage) ),

so the plan follows the same quantities and labour rates as the price
(a task priced by a supplier's installed set, with no ว480 labour, takes one day). The
crew sizes, the daily wage and the working days per week are project
values the user sets; no Thai law or CGD rule fixes them (the 2569
building criteria only list a CPM plan as a special cost, ส่วนที่ 3 ข้อ 6).

The order is the usual one for a reinforced-concrete house: earthwork and
footings, the frame, then the roof and the masonry, the building services
during the masonry, the finishes, and the fixtures and paint last. Each
task's value (its construction cost × Factor F) is spread evenly over its
days for the S-curve (ผลงานสะสม).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Task:
    key: str
    name: str
    sections: tuple                 # BOQ sections priced in this task
    after: tuple = ()               # finish-to-start predecessors
    overlap: tuple = ()             # start-to-start predecessors: start when that task is half done
    crew: int = 6
    labour: float = 0.0             # บาท (ว480 amounts)
    value: float = 0.0              # ค่าก่อสร้าง (× Factor F)
    days: int = 0
    es: int = 0
    ef: int = 0
    ls: int = 0
    lf: int = 0

    @property
    def critical(self) -> bool:
        return self.ls == self.es

    @property
    def slack(self) -> int:
        return self.ls - self.es


#: (key, name, sections, finish-to-start, start-to-start at half, default crew)
LOGIC = [
    ("earth", "งานดิน ฐานราก", ("งานดิน",), (), (), 6),
    ("frame", "งานโครงสร้าง ค.ส.ล. (คอนกรีต ไม้แบบ เหล็กเสริม)", ("งานคอนกรีต", "งานไม้แบบ", "งานเหล็กเสริม"),
     ("earth",), (), 10),
    ("roof", "งานหลังคา", ("งานหลังคา",), ("frame",), (), 6),
    ("wall", "งานก่อ ฉาบ", ("งานก่อ ฉาบ",), ("frame",), (), 8),
    ("mep", "งานระบบไฟฟ้า ประปา สุขาภิบาล", ("งานระบบไฟฟ้า", "งานระบบประปา สุขาภิบาล"), (), ("wall",), 4),
    ("open", "งานประตู หน้าต่าง", ("งานประตู หน้าต่าง",), ("wall",), (), 4),
    ("finish", "งานพื้น ผนัง ฝ้า", ("งานพื้น ผนัง ฝ้า",), ("wall", "roof"), (), 6),
    ("sanitary", "งานสุขภัณฑ์", ("งานสุขภัณฑ์",), ("finish", "mep"), (), 2),
    ("paint", "งานทาสี", ("งานทาสี",), ("finish", "open"), (), 4),
]


@dataclass
class Plan:
    tasks: list
    days: int                       # total working days
    week: int                       # working days per week
    wage: float
    curve: list = field(default_factory=list)   # [(week, % this week, cumulative %)]

    @property
    def weeks(self) -> int:
        return math.ceil(self.days / self.week) if self.days else 0

    @property
    def months(self) -> float:
        return round(self.days / (self.week * 52 / 12), 1)

    def critical_path(self) -> list:
        return [t for t in self.tasks if t.days and t.critical]


def plan(est, wage: float = 400.0, week: int = 6, crews: dict | None = None) -> Plan:
    """CPM plan of an :class:`~wanicndesign.estimate.Estimate` (or a Contract's estimate)."""
    crews = crews or {}
    by_section: dict = {}
    for r in est.rows:
        lab, val = by_section.get(r.line.section, (0.0, 0.0))
        by_section[r.line.section] = (lab + r.labour_amount, val + r.total)
    factor = est.factor
    tasks = []
    for key, name, secs, after, overlap, crew in LOGIC:
        t = Task(key, name, secs, after, overlap, int(crews.get(key, crew)))
        t.labour = sum(by_section.get(s, (0, 0))[0] for s in secs)
        t.value = sum(by_section.get(s, (0, 0))[1] for s in secs) * factor
        t.days = math.ceil(t.labour / (max(t.crew, 1) * wage)) if t.labour > 0 else (1 if t.value > 0 else 0)
        tasks.append(t)
    known = {s for _k, _n, secs, *_ in LOGIC for s in secs}
    other = [s for s in by_section if s not in known]
    if other:                                   # sections not in the logic: last, after the structure
        t = Task("other", "งานอื่น ๆ", tuple(other), ("frame",), (), 4)
        t.labour = sum(by_section[s][0] for s in other)
        t.value = sum(by_section[s][1] for s in other) * factor
        t.days = math.ceil(t.labour / (t.crew * wage)) if t.labour > 0 else 0
        tasks.append(t)
    idx = {t.key: t for t in tasks}
    # forward pass (tasks are in a topological order)
    for t in tasks:
        start = 0
        for p in t.after:
            start = max(start, idx[p].ef)
        for p in t.overlap:
            start = max(start, idx[p].es + math.ceil(idx[p].days / 2))
        t.es, t.ef = start, start + t.days
    total = max((t.ef for t in tasks), default=0)
    # backward pass
    for t in tasks:
        t.lf = total
    for t in reversed(tasks):
        t.ls = t.lf - t.days
        for p in t.after:
            idx[p].lf = min(idx[p].lf, t.ls)
        for p in t.overlap:
            idx[p].lf = min(idx[p].lf, t.ls - math.ceil(idx[p].days / 2) + idx[p].days)
    for t in tasks:
        t.ls = t.lf - t.days
    p = Plan(tasks, total, week, wage)
    value = sum(t.value for t in tasks) or 1.0
    cum = 0.0
    for w in range(p.weeks):
        d0, d1 = w * week, (w + 1) * week
        part = sum(t.value * max(0, min(t.ef, d1) - max(t.es, d0)) / t.days for t in tasks if t.days)
        cum += part
        p.curve.append((w + 1, round(100 * part / value, 2), round(100 * cum / value, 2)))
    return p


def write_plan(p: Plan, ws, title: str) -> None:
    """The bar chart (one column per week) and the S-curve table on an openpyxl sheet."""
    from openpyxl.chart import LineChart, Reference
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    bold = Font(bold=True)
    red, blue = PatternFill("solid", fgColor="E06666"), PatternFill("solid", fgColor="6FA8DC")
    ws.append([title])
    ws.cell(1, 1).font = Font(bold=True, size=14)
    ws.append([f"ระยะเวลา {p.days} วันทำงาน ({p.weeks} สัปดาห์ ≈ {p.months:g} เดือน) · ทำงาน {p.week} วัน/สัปดาห์ · "
               f"ค่าแรงวันละ {p.wage:,.0f} บาท/คน · แถบสีแดง = งานวิกฤต (CPM)"])
    ws.append(["ระยะเวลาแต่ละงาน = ค่าแรงตาม ว480 ในใบประมาณราคา ÷ (จำนวนคนงาน × ค่าแรงต่อวัน) — "
               "จำนวนคนงานและค่าแรงเป็นค่าของโครงการ ปรับได้"])
    head = ["งาน", "ค่าแรง (บาท)", "คนงาน", "วัน", "เริ่มวันที่", "เสร็จวันที่", "เผื่อ (วัน)", "มูลค่างาน (บาท)", "%"]
    ws.append(head + [f"สัปดาห์ {w}" for w in range(1, p.weeks + 1)])
    for c in ws[ws.max_row]:
        c.font = bold
        c.alignment = Alignment(wrap_text=True, horizontal="center")
    total = sum(t.value for t in p.tasks) or 1.0
    for t in p.tasks:
        if not t.days:
            continue
        ws.append([t.name, round(t.labour, 2), t.crew, t.days, t.es + 1, t.ef, t.slack, round(t.value, 2),
                   round(100 * t.value / total, 2)])
        r = ws.max_row
        for w in range(p.weeks):
            if t.es < (w + 1) * p.week and t.ef > w * p.week:
                ws.cell(r, len(head) + 1 + w).fill = red if t.critical else blue
    ws.append([])
    ws.append(["ผลงานรายสัปดาห์ (%)", "", "", "", "", "", "", "", ""] + [c[1] for c in p.curve])
    ws.append(["ผลงานสะสม (%)", "", "", "", "", "", "", "", ""] + [c[2] for c in p.curve])
    cum_row = ws.max_row
    ws.column_dimensions["A"].width = 44
    for i in range(2, len(head) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 12
    for w in range(p.weeks):
        ws.column_dimensions[get_column_letter(len(head) + 1 + w)].width = 6
    if p.weeks:
        ch = LineChart()
        ch.title = "S-Curve ผลงานสะสม (%)"
        ch.y_axis.title = "%"
        ch.x_axis.title = "สัปดาห์"
        data = Reference(ws, min_col=len(head) + 1, max_col=len(head) + p.weeks, min_row=cum_row, max_row=cum_row)
        ch.add_data(data, from_rows=True, titles_from_data=False)
        ch.height, ch.width = 8, 22
        ws.add_chart(ch, f"A{cum_row + 2}")
