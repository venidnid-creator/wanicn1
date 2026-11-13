# SPDX-License-Identifier: GPL-3.0-or-later
"""ค่าเสื่อมราคาครุภัณฑ์ — วิธีเส้นตรง ตามหลักเกณฑ์กรมบัญชีกลาง.

* (ราคาทุน − ราคาซาก) ÷ อายุการใช้งาน = ค่าเสื่อมต่อปี
* ปีที่ใช้งานเต็มปีคิดเท่ากับค่าเสื่อมต่อปี (ปี 366 วันก็เท่าเดิม)
* ปีแรกคิดตามจำนวนวันที่ใช้งานจริงในปีงบประมาณ (นับวันที่ได้มาเป็นวันแรก) ÷ 365
* ราคาซาก 1 บาท (ค่าเริ่มต้น) — ค่าเสื่อมสะสมไม่เกินราคาทุน − ราคาซาก
* ครุภัณฑ์ราคาต่อหน่วยต่ำกว่าเกณฑ์ (ค่าเริ่มต้น 10,000 บาท) ไม่คิดค่าเสื่อม (บันทึกเป็นค่าใช้จ่าย)
"""
from __future__ import annotations

import datetime as _dt

from . import thaidate as TD

THRESHOLD = 10000.0
SALVAGE = 1.0


def schedule(price: float, acquired, life_years: float, salvage: float = SALVAGE,
             until_fy: int | None = None, disposed=None,
             threshold: float = THRESHOLD) -> list[dict]:
    """Rows per fiscal year: fy, days, depreciation, accumulated, book value.

    Empty when the asset is below the capitalisation threshold or has no life.
    """
    acquired = TD.parse(acquired)
    disposed = TD.parse(disposed)
    price = float(price or 0)
    if acquired is None or price < threshold or not life_years or life_years <= 0:
        return []
    salvage = min(float(salvage or 0), price)
    base = price - salvage
    per_year = base / float(life_years)
    fy = TD.fiscal_year(acquired)
    last = until_fy if until_fy is not None else TD.fiscal_year(TD.today())
    if disposed:
        last = min(last, TD.fiscal_year(disposed))
    acc = 0.0
    rows = []
    while fy <= last and acc < base - 1e-9:
        start, end = TD.fiscal_range(fy)
        s = max(start, acquired)
        e = min(end, disposed - _dt.timedelta(days=1)) if disposed else end
        days = max(0, (e - s).days + 1)
        full = s == start and e == end           # a whole year: exactly one year's share
        dep = round(min(per_year if full else per_year * days / 365.0, base - acc), 2)
        acc = round(acc + dep, 2)
        rows.append(dict(fy=fy, days=days, dep=dep, acc=acc, book=round(price - acc, 2)))
        fy += 1
    return rows


def for_year(rows: list[dict], fy: int) -> dict:
    """Depreciation of fiscal year *fy* and the balances at its end."""
    dep = 0.0
    acc = 0.0
    for r in rows:
        if r["fy"] < fy:
            acc = r["acc"]
        elif r["fy"] == fy:
            dep, acc = r["dep"], r["acc"]
    return dict(dep=dep, acc=acc)
