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


def frame_stages(project) -> list[tuple[str, float]]:
    """Concrete volume of the frame by stage, in building order: the footings with the columns up to the
    first level and that level's beams and slabs, then each higher level with the columns below it."""
    floors = [f.name for f in project.floors if f.name != "FL0"]
    if not floors:
        return []
    vol = {f: 0.0 for f in floors}
    vol[floors[0]] += sum(f.width * f.length * f.thickness * f.count for f in project.footings)
    for c in project.columns:
        top = c.name.rsplit("–", 1)[-1].rstrip(")").strip() if "–" in c.name else floors[0]
        vol[top if top in vol else floors[0]] += c.width * c.depth * c.height * c.count
    for b in project.beams:
        vol[b.floor if b.floor in vol else floors[-1]] += b.width * b.depth * b.length * b.count
    for sl in project.slabs:
        vol[sl.floor if sl.floor in vol else floors[0]] += sl.area * sl.thickness
    out = []
    for i, f in enumerate(floors):
        if vol[f] > 0:
            label = f"ฐานราก เสาตอม่อ คานคอดิน ({f})" if i == 0 else f"โครงสร้าง ค.ส.ล. ชั้น {f}"
            out.append((label, vol[f]))
    return out


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

    def installments(self, value: float, advance: float = 0.0, retention: float = 0.0) -> list[dict]:
        """Monthly installments (the payment period D of the Factor F interest, หลักเกณฑ์งานอาคาร 2569 ข้อ 9.2):
        the work done in each month by the S-curve × the contract value; the advance (``advance`` % of the
        contract, paid at the start) is repaid by the same share of every installment, and ``retention`` %
        is held and returned under the contract."""
        if not self.days:
            return []
        per_month = self.week * 52 / 12
        months = max(1, math.ceil(self.days / per_month))
        out, done = [], 0.0
        for m in range(1, months + 1):
            end = min(self.days, round(m * per_month))
            cum = self.progress(end)
            part = cum - done
            done = cum
            amount = value * part / 100
            adv = amount * advance / 100
            ret = amount * retention / 100
            out.append({"no": m, "day": end, "percent": round(part, 2), "cumulative": round(cum, 2),
                        "amount": round(amount, 2), "advance_back": round(adv, 2), "retention": round(ret, 2),
                        "pay": round(amount - adv - ret, 2)})
        return out

    def progress(self, day: float) -> float:
        """Cumulative % of the work value done by the end of working day ``day``."""
        total = sum(t.value for t in self.tasks) or 1.0
        done = sum(t.value * max(0.0, min(t.ef, day) - t.es) / t.days for t in self.tasks if t.days and day > t.es)
        return min(100.0, 100 * done / total)


def plan(est, wage: float = 400.0, week: int = 6, crews: dict | None = None, stages=None) -> Plan:
    """CPM plan of an :class:`~wanicndesign.estimate.Estimate` (or a Contract's estimate). ``stages``
    (:func:`frame_stages`, taken from ``est.project`` when it has one) splits the frame by floor, its
    labour and value shared by concrete volume; each stage follows the one below it."""
    crews = crews or {}
    if stages is None and getattr(est, "project", None) is not None:
        stages = frame_stages(est.project)
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
    if stages and len(stages) > 1:
        tasks = _split_frame(tasks, stages, wage)
    known = {s for _k, _n, secs, *_ in LOGIC for s in secs}
    other = [s for s in by_section if s not in known]
    if other:                                   # sections not in the logic: last, after the structure
        last_frame = [t.key for t in tasks if t.key.startswith("frame")][-1]
        t = Task("other", "งานอื่น ๆ", tuple(other), (last_frame,), (), 4)
        t.labour = sum(by_section[s][0] for s in other)
        t.value = sum(by_section[s][1] for s in other) * factor
        t.days = math.ceil(t.labour / (t.crew * wage)) if t.labour > 0 else 0
        tasks.append(t)
    idx = {t.key: t for t in tasks}
    tasks = [t for t in tasks if t.key in idx]
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


def write_plan(p: Plan, ws, title: str, value: float = 0.0, advance: float = 0.0, retention: float = 0.0) -> None:
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
    if value > 0 and p.days:
        r0 = cum_row + 20                     # below the chart
        ws.cell(r0, 1, f"งวดงานรายเดือน (ตามผลงานจาก S-Curve) มูลค่าสัญญา {value:,.2f} บาท · "
                       f"หักเงินล่วงหน้า {advance:g}% · เงินประกันผลงาน {retention:g}% (คืนตามสัญญา)").font = bold
        heads = ["งวดที่", "ถึงวันทำงานที่", "ผลงานงวดนี้ (%)", "ผลงานสะสม (%)", "ค่างานงวดนี้", "หักคืนเงินล่วงหน้า",
                 "หักเงินประกันผลงาน", "จ่ายสุทธิ"]
        for k, h in enumerate(heads, 1):
            ws.cell(r0 + 1, k, h).font = bold
        rows = p.installments(value, advance, retention)
        for i, it in enumerate(rows):
            r = r0 + 2 + i
            for k, key in enumerate(("no", "day", "percent", "cumulative", "amount", "advance_back", "retention",
                                     "pay"), 1):
                ws.cell(r, k, it[key])
        r = r0 + 2 + len(rows)
        ws.cell(r, 1, "รวม").font = bold
        for k, key in ((5, "amount"), (6, "advance_back"), (7, "retention"), (8, "pay")):
            ws.cell(r, k, round(sum(it[key] for it in rows), 2)).font = bold
        ws.cell(r + 1, 1, "งวดงานแบ่งตามเดือน (ช่วงเวลาการรับเงิน D ในสูตรค่าดอกเบี้ยของ Factor F หลักเกณฑ์งานอาคาร "
                          "ข้อ 9.2) — ปรับงวดและเงื่อนไขการจ่ายตามสัญญาจริง")


def _split_frame(tasks: list, stages, wage: float) -> list:
    """Replace the single frame task by one task per stage, chained; the roof follows the top stage and
    the masonry the stage below the top (the walls of the lower floors go up while the top is cast)."""
    frame = next(t for t in tasks if t.key == "frame")
    total = sum(v for _l, v in stages) or 1.0
    parts, prev = [], frame.after
    for k, (label, v) in enumerate(stages):
        t = Task(f"frame{k}", label, frame.sections, prev, (), frame.crew)
        t.labour, t.value = frame.labour * v / total, frame.value * v / total
        t.days = math.ceil(t.labour / (max(t.crew, 1) * wage)) if t.labour > 0 else 0
        parts.append(t)
        prev = (t.key,)
    top, below = parts[-1].key, parts[-2].key
    out = []
    for t in tasks:
        if t.key == "frame":
            out += parts
            continue
        if "frame" in t.after:
            t.after = tuple((below if t.key == "wall" else top) if a == "frame" else a for a in t.after)
        out.append(t)
    return out

