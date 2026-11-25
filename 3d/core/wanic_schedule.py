# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""แผนงานก่อสร้าง by the critical path method, from the priced BOQ (ข12, from WanicnDesign).

A task's days come from the estimate itself: its labour (the ว480 amounts
of its หมวดงาน in the BOQ) over what its crew is paid a working day,

    days = ceil( labour (บาท) / (crew × daily wage) ),

so the plan follows the same quantities and rates as the price (a task
with no labour but a value takes one day). The crews, the wage and the
working days a week are the project's values — no law or CGD rule fixes
them (หลักเกณฑ์ 2569 lists a CPM plan only as a special cost).

The order is the usual one of a reinforced-concrete building: the site,
earthwork and footings, the frame floor by floor (its labour and value
shared by concrete volume), the roof after the top floor, the masonry after
the floor under the top, the services from half-way through the masonry,
openings, floors and ceilings, paint; the outside works after the masonry.
Each task's value (cost × Factor F) is spread evenly over its days for the
S-curve; monthly installments follow it (the period D of the Factor F
interest, หลักเกณฑ์งานอาคาร ข้อ 9.2), less the advance repaid and the
retention held by the given shares.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

#: (key, name, หมวดงาน numbers, finish-to-start, start-to-start at half, crew)
LOGIC = [
    ("site", "งานเตรียมพื้นที่", (1,), (), (), 4),
    ("earth", "งานดิน ฐานราก", (2, 3), ("site",), (), 6),
    ("frame", "งานโครงสร้าง ค.ส.ล. / เหล็ก", (4, 5), ("earth",), (), 10),
    ("roof", "งานหลังคา", (7,), ("frame",), (), 6),
    ("wall", "งานผนัง ก่อ ฉาบ", (6,), ("frame",), (), 8),
    ("mep", "งานระบบสุขาภิบาล ไฟฟ้า ปรับอากาศ", (11, 12, 13), (), ("wall",), 4),
    ("open", "งานประตู หน้าต่าง", (8,), ("wall",), (), 4),
    ("finish", "งานพื้น ฝ้า", (10,), ("wall", "roof"), (), 6),
    ("paint", "งานสี", (9,), ("finish", "open"), (), 4),
    ("outside", "งานภายนอก", (14,), ("wall",), (), 4),
    ("other", "งานอื่น ๆ", (15, 17), ("frame",), (), 4),
]


@dataclass
class Task:
    key: str
    name: str
    cats: tuple
    after: tuple = ()
    overlap: tuple = ()
    crew: int = 6
    labour: float = 0.0
    value: float = 0.0
    days: int = 0
    es: int = 0
    ef: int = 0
    ls: int = 0
    lf: int = 0

    @property
    def critical(self) -> bool:
        return self.days > 0 and self.ls == self.es

    @property
    def slack(self) -> int:
        return self.ls - self.es


@dataclass
class Plan:
    tasks: list
    days: int
    week: int
    wage: float
    curve: list = field(default_factory=list)          # [(week, % this week, cumulative %)]

    @property
    def weeks(self) -> int:
        return math.ceil(self.days / self.week) if self.days else 0

    @property
    def months(self) -> float:
        return round(self.days / (self.week * 52 / 12), 1)

    def progress(self, day: float) -> float:
        total = sum(t.value for t in self.tasks) or 1.0
        done = sum(t.value * max(0.0, min(t.ef, day) - t.es) / t.days for t in self.tasks if t.days and day > t.es)
        return min(100.0, 100 * done / total)

    def installments(self, value: float, advance: float = 0.0, retention: float = 0.0) -> list:
        if not self.days:
            return []
        per = self.week * 52 / 12
        months = max(1, math.ceil(self.days / per))
        out, done = [], 0.0
        for m in range(1, months + 1):
            end = min(self.days, round(m * per)) if m < months else self.days
            cum = self.progress(end)
            part, done = cum - done, cum
            amount = value * part / 100
            adv, ret = amount * advance / 100, amount * retention / 100
            out.append({"no": m, "day": end, "percent": round(part, 2), "cumulative": round(cum, 2),
                        "amount": round(amount, 2), "advance_back": round(adv, 2), "retention": round(ret, 2),
                        "pay": round(amount - adv - ret, 2)})
        return out


def frame_stages(data) -> list:
    """[(label, concrete m³)] of the frame by floor: the footings, stumps, ground beams and the
    first floor's columns, beams and slab first; then each floor with the columns under it."""
    from core import wanic_building as B
    E = B.elements(data or {})
    lib, n = E["lib"], int(E["n"])
    if n < 1:
        return []
    vol = [0.0] * n

    def v(sp, *dims):
        return math.prod(float(sp.get(k, 0) or 0) for k in dims)
    for f in E["footings"]:
        vol[0] += v(lib.get(f["mark"], {}), "w", "l", "t")
    for s in E["stumps"]:
        vol[0] += v(lib.get(s["mark"], {}), "b", "h") * abs(s["z1"] - s["z0"])
    for c in E["columns"]:
        vol[min(int(c.get("floor", 0)), n - 1)] += v(lib.get(c["mark"], {}), "b", "h") * abs(c["z1"] - c["z0"])
    for b in E["beams"]:
        lv = max(int(b["level"]) - 1, 0)
        vol[min(lv, n - 1)] += v(lib.get(b["mark"], {}), "b", "h") * math.dist(b["p0"], b["p1"])
    for sl in E["slabs"]:
        rm = sl["room"]
        f = int(sl.get("floor", 0))
        vol[max(min(f - 1, n - 1), 0)] += float(rm["w"]) * float(rm["d"]) * float(lib.get(sl["mark"], {}).get("t", 0.1))
    return [("ฐานราก ตอม่อ คานคอดิน และโครงสร้างชั้น 1" if i == 0 else f"โครงสร้าง ค.ส.ล. ชั้น {i + 1}", x)
            for i, x in enumerate(vol) if x > 0]


def plan(result, data=None, wage: float = 400.0, week: int = 6, crews: dict | None = None) -> Plan:
    """The CPM plan of a priced BOQ (``wanic_quantities.priced``)."""
    crews = crews or {}
    F = float((result.get("totals") or {}).get("F") or 1.0)
    by: dict = {}
    for ln in result.get("lines") or []:
        lab, val = by.get(ln.get("cat"), (0.0, 0.0))
        by[ln.get("cat")] = (lab + float(ln.get("lab_total") or 0), val + float(ln.get("total") or 0))
    tasks = []
    for key, name, cats, after, overlap, crew in LOGIC:
        t = Task(key, name, cats, after, overlap, int(crews.get(key, crew)))
        t.labour = sum(by.get(c, (0, 0))[0] for c in cats)
        t.value = sum(by.get(c, (0, 0))[1] for c in cats) * F
        t.days = math.ceil(t.labour / (max(t.crew, 1) * wage)) if t.labour > 0 else (1 if t.value > 0 else 0)
        tasks.append(t)
    stages = frame_stages(data) if data is not None else []
    if len(stages) > 1:
        tasks = _split_frame(tasks, stages, wage)
    idx = {t.key: t for t in tasks}
    for t in tasks:                                     # forward pass (a topological order)
        start = 0
        for p in t.after:
            start = max(start, idx[p].ef)
        for p in t.overlap:
            start = max(start, idx[p].es + math.ceil(idx[p].days / 2))
        t.es, t.ef = start, start + t.days
    total = max((t.ef for t in tasks), default=0)
    for t in tasks:
        t.lf = total
    for t in reversed(tasks):                           # backward pass
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


def _split_frame(tasks, stages, wage):
    frame = next(t for t in tasks if t.key == "frame")
    total = sum(v for _l, v in stages) or 1.0
    parts, prev = [], frame.after
    for k, (label, v) in enumerate(stages):
        t = Task(f"frame{k}", label, frame.cats, prev, (), frame.crew)
        t.labour, t.value = frame.labour * v / total, frame.value * v / total
        t.days = math.ceil(t.labour / (max(t.crew, 1) * wage)) if t.labour > 0 else (1 if t.value > 0 else 0)
        parts.append(t)
        prev = (t.key,)
    top, below = parts[-1].key, parts[-2].key
    out = []
    for t in tasks:
        if t.key == "frame":
            out += parts
            continue
        t.after = tuple((below if t.key == "wall" else top) if a == "frame" else a for a in t.after)
        out.append(t)
    return out


def write_xlsx(p: Plan, path, title: str = "แผนงานก่อสร้าง", value: float = 0.0,
               advance: float = 0.0, retention: float = 0.0) -> None:
    """The bar chart (one column a week, critical red), the S-curve rows and the installments."""
    from pathlib import Path
    from core.wanic_takeoff import _Sheet, _xlsx
    sh = _Sheet("แผนงาน CPM", landscape=True)
    head = ["งาน", "ค่าแรง (บาท)", "คนงาน", "วัน", "เริ่มวันที่", "เสร็จวันที่", "เผื่อ (วัน)", "มูลค่างาน (บาท)", "%"]
    sh.widths = [40, 14, 8, 7, 9, 9, 9, 16, 8] + [4] * p.weeks
    sh.add([title], style=2)
    sh.add([f"ระยะเวลา {p.days} วันทำงาน ({p.weeks} สัปดาห์ ≈ {p.months:g} เดือน) · ทำงาน {p.week} วัน/สัปดาห์ · "
            f"ค่าแรงวันละ {p.wage:,.0f} บาท/คน · แถบสีแดง = งานวิกฤต (CPM)"])
    sh.add(["ระยะเวลาแต่ละงาน = ค่าแรงตาม ว480 ในใบ BOQ ÷ (คนงาน × ค่าแรงต่อวัน) — คนงานและค่าแรงเป็นค่าของโครงการ ปรับได้"])
    sh.add(head + [str(w) for w in range(1, p.weeks + 1)], style=3)
    total = sum(t.value for t in p.tasks) or 1.0
    for t in p.tasks:
        if not t.days:
            continue
        cells = [t.name, round(t.labour, 2), t.crew, t.days, t.es + 1, t.ef, t.slack, round(t.value, 2),
                 round(100 * t.value / total, 2)]
        styles = [4, 5, 8, 8, 8, 8, 8, 5, 5]
        for w in range(p.weeks):
            on = t.es < (w + 1) * p.week and t.ef > w * p.week
            cells.append("")
            styles.append((12 if t.critical else 13) if on else 4)
        sh.add(cells, styles=styles)
    sh.add([])
    sh.add(["ผลงานรายสัปดาห์ (%)"] + [""] * 8 + [c[1] for c in p.curve], style=0)
    sh.add(["ผลงานสะสม S-Curve (%)"] + [""] * 8 + [c[2] for c in p.curve], style=1)
    sheets = [sh]
    if value > 0 and p.days:
        s2 = _Sheet("งวดงานรายเดือน", landscape=True)
        s2.widths = [8, 12, 14, 14, 18, 18, 18, 18]
        s2.add([f"งวดงานรายเดือนตามผลงานจาก S-Curve · มูลค่าสัญญา {value:,.2f} บาท · หักเงินล่วงหน้า {advance:g}% · "
                f"เงินประกันผลงาน {retention:g}%"], style=1)
        s2.add(["งวดที่", "ถึงวันทำงานที่", "ผลงานงวดนี้ (%)", "ผลงานสะสม (%)", "ค่างานงวดนี้", "หักคืนเงินล่วงหน้า",
                "หักเงินประกันผลงาน", "จ่ายสุทธิ"], style=3)
        rows = p.installments(value, advance, retention)
        for it in rows:
            s2.add([it[k] for k in ("no", "day", "percent", "cumulative", "amount", "advance_back", "retention",
                                    "pay")], styles=[8, 8, 5, 5, 5, 5, 5, 5])
        s2.add(["รวม", "", "", "", *(round(sum(it[k] for it in rows), 2)
                                     for k in ("amount", "advance_back", "retention", "pay"))], style=7)
        s2.add(["งวดงานแบ่งตามเดือน (ช่วงเวลารับเงิน D ในสูตรดอกเบี้ยของ Factor F หลักเกณฑ์งานอาคาร ข้อ 9.2) — "
                "ปรับงวดและเงื่อนไขการจ่ายตามสัญญาจริง"])
        sheets.append(s2)
    Path(path).write_bytes(_xlsx(sheets))
