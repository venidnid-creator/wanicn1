# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ข12: ตารางตัดเหล็ก and the cutting plan from 10 m stock."""
from __future__ import annotations

import math
import zipfile

from core import wanic_building as B
from core import wanic_cutting as CT
from core import wanic_rc as R


def _E():
    d = B.default_data()
    R.apply_grid(d, [4.0, 4.0], [4.0, 3.0], 2)
    return B.elements(d)


def test_every_member_has_its_bars_and_the_totals_agree_with_the_takeoff():
    E = _E()
    rows = CT.items(E)
    groups = {it.group for it in rows}
    assert {"ฐานราก", "ตอม่อ", "เสา", "คาน", "พื้น"} <= groups
    T = R.takeoff(E)
    for size in ("DB12", "RB9"):
        mine = sum(it.total for it in rows if it.size == size)
        theirs = T["bars"][size]["m"] / (1 + R.WASTE)
        assert abs(mine - theirs) / theirs < 0.12                     # same structure, own detailing
    assert all(it.length <= CT.STOCK + 1e-9 for it in rows)


def test_a_long_bar_is_cut_and_lapped():
    bar = R.parse_bar("2-DB16")
    k, L = CT._split(17.0, bar)
    assert k == 2 and math.isclose(L, (17.0 + R.lap_length(bar)) / 2)


def test_first_fit_decreasing_uses_every_piece():
    rows = [CT.Item("คาน", "B1", "x", "DB12", "ตรง", 4.4, 5), CT.Item("คาน", "B1", "y", "DB12", "ตรง", 3.0, 3)]
    p = CT.plans(rows)[0]
    assert p.pieces == 8 and math.isclose(p.used, 4.4 * 5 + 9.0)
    assert sum(n * len(c) for n, c in p.patterns) == 8
    assert all(sum(c) <= CT.STOCK + 1e-9 for _n, c in p.patterns)
    assert p.bars == 4                                                # 4.4+4.4 / 4.4+4.4 / 4.4+3+... (FFD)
    assert CT.cuts_text([4.4, 4.4, 1.1]) == "4.40 × 2 + 1.10"


def test_the_workbook(tmp_path):
    out = CT.write_xlsx(_E(), tmp_path / "cut.xlsx")
    assert out["bars"] > 0 and out["kg"] > 0
    names = zipfile.ZipFile(tmp_path / "cut.xlsx").namelist()
    assert sum(1 for n in names if n.startswith("xl/worksheets/")) == 3
