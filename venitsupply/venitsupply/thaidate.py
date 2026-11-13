# SPDX-License-Identifier: GPL-3.0-or-later
"""Thai dates and the government fiscal year (1 ต.ค. – 30 ก.ย.)."""
from __future__ import annotations

import datetime as _dt

MONTHS = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
          "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
MONTHS_SHORT = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
                "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]


def parse(s) -> _dt.date | None:
    """ISO 'YYYY-MM-DD' (ค.ศ.) → date; a date passes through; '' → None."""
    if not s:
        return None
    if isinstance(s, _dt.date):
        return s
    return _dt.date.fromisoformat(str(s)[:10])


def fiscal_year(d) -> int:
    """ปีงบประมาณ (พ.ศ.) of a date: Oct–Dec belong to the next year."""
    d = parse(d)
    return d.year + 543 + (1 if d.month >= 10 else 0)


def fiscal_range(fy_be: int) -> tuple[_dt.date, _dt.date]:
    """First and last day of fiscal year *fy_be* (พ.ศ.)."""
    y = fy_be - 543
    return _dt.date(y - 1, 10, 1), _dt.date(y, 9, 30)


def thai(d, short: bool = True) -> str:
    """'2026-11-13' → '13 พ.ย. 2569' (or the long month name)."""
    d = parse(d)
    if d is None:
        return ""
    m = (MONTHS_SHORT if short else MONTHS)[d.month - 1]
    return f"{d.day} {m} {d.year + 543}"


def today() -> _dt.date:
    return _dt.date.today()
