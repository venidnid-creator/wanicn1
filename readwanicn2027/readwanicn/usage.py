# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ — ReadWanicn2027
"""Usage statistics of every feature, kept on this computer only
(``usage.jsonl`` beside the program's settings): one line per use with the
time, the user and the feature. :func:`summary` counts them per day, week,
month or year; :func:`report_xlsx` writes the report."""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
from pathlib import Path

PERIODS = {"day": "รายวัน", "week": "รายสัปดาห์", "month": "รายเดือน", "year": "รายปี"}
TH_MONTHS = ("มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม",
             "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม")


def default_path() -> Path:
    base = os.environ.get("APPDATA") or os.path.join(Path.home(), ".config")
    return Path(base) / "ReadWanicn2027" / "usage.jsonl"


class Usage:
    def __init__(self, path: Path | None = None, user: str = ""):
        self.path = Path(path) if path else default_path()
        self.user = user

    def record(self, feature: str, when: dt.datetime | None = None) -> None:
        when = when or dt.datetime.now()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": when.isoformat(timespec="seconds"), "u": self.user, "f": feature},
                                   ensure_ascii=False) + "\n")
        except OSError:
            pass                                # statistics never stop the work

    def events(self):
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out = []
        for line in lines:
            try:
                e = json.loads(line)
                out.append((dt.datetime.fromisoformat(e["t"]), e.get("u", ""), e["f"]))
            except (ValueError, KeyError):
                continue
        return out


def period_key(t: dt.datetime, period: str) -> str:
    """The label of the day / week / month / year ``t`` falls in (Buddhist era)."""
    be = t.year + 543
    if period == "day":
        return f"{t.day:02d}/{t.month:02d}/{be}"
    if period == "week":
        start = t.date() - dt.timedelta(days=t.weekday())
        end = start + dt.timedelta(days=6)
        return f"{start.day:02d}/{start.month:02d}/{start.year + 543} – {end.day:02d}/{end.month:02d}/{end.year + 543}"
    if period == "month":
        return f"{TH_MONTHS[t.month - 1]} {be}"
    return f"พ.ศ. {be}"


def _sort_key(t: dt.datetime, period: str):
    if period == "day":
        return t.date()
    if period == "week":
        return t.date() - dt.timedelta(days=t.weekday())
    if period == "month":
        return (t.year, t.month)
    return t.year


def summary(events, period: str = "day", user: str | None = None):
    """``[(label, Counter{feature: n}), …]`` newest first, and the totals per feature."""
    buckets: dict = {}
    labels = {}
    total = collections.Counter()
    for t, u, f in events:
        if user and u != user:
            continue
        k = _sort_key(t, period)
        buckets.setdefault(k, collections.Counter())[f] += 1
        labels[k] = period_key(t, period)
        total[f] += 1
    rows = [(labels[k], buckets[k]) for k in sorted(buckets, reverse=True)]
    return rows, total


def report_xlsx(events, path, family="TH SarabunPSK") -> None:
    """One sheet per period (days, weeks, months, years) plus the totals."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    head = Font(name=family, size=16, bold=True, color="FFFFFF")
    body = Font(name=family, size=16)
    fill = PatternFill("solid", fgColor="0F2A44")
    ws = wb.active
    ws.title = "สรุปรวม"
    rows, total = summary(events, "year")
    ws.append(["รายงานสถิติการใช้งาน ReadWanicn2027"])
    ws["A1"].font = Font(name=family, size=20, bold=True)
    ws.append([f"จัดทำเมื่อ {period_key(dt.datetime.now(), 'day')}   ใช้งานทั้งหมด {sum(total.values())} ครั้ง"])
    ws["A2"].font = body
    ws.append([])
    ws.append(["ลำดับ", "รายการ", "จำนวนครั้ง"])
    for c in ws[4]:
        c.font, c.fill = head, fill
    for i, (f, n) in enumerate(total.most_common(), 1):
        ws.append([i, f, n])
        for c in ws[ws.max_row]:
            c.font = body
    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 48
    ws.column_dimensions["C"].width = 14
    for period, name in PERIODS.items():
        sh = wb.create_sheet(name)
        sh.append(["ช่วงเวลา", "รายการ", "จำนวนครั้ง"])
        for c in sh[1]:
            c.font, c.fill = head, fill
        prows, _ = summary(events, period)
        for label, counts in prows:
            first = True
            for f, n in counts.most_common():
                sh.append([label if first else "", f, n])
                for c in sh[sh.max_row]:
                    c.font = body
                first = False
            sh.append(["", "รวม", sum(counts.values())])
            for c in sh[sh.max_row]:
                c.font = Font(name=family, size=16, bold=True)
                if c.column == 2:
                    c.alignment = Alignment(horizontal="right")
        sh.column_dimensions["A"].width = 34
        sh.column_dimensions["B"].width = 48
        sh.column_dimensions["C"].width = 14
    wb.save(path)
