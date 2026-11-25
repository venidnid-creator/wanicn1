# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ข12: แผนงานก่อสร้าง CPM, S-curve and the monthly installments from the BOQ."""
from __future__ import annotations

import math
import zipfile

from core import wanic_building as B
from core import wanic_quantities as Q
from core import wanic_rc as R
from core import wanic_schedule as SC
from core import wanic_std2569 as S


def _job(n=2):
    d = B.default_data()
    R.apply_grid(d, [4.0, 4.0], [4.0, 3.0], n)
    d["province"] = "ขอนแก่น"
    d["prices"] = {k: S.sample_price(k) for k in S.SAMPLE_PRICES}
    return d, Q.priced(d)


def test_days_from_the_labour_and_the_critical_path():
    d, r = _job()
    p = SC.plan(r, d, wage=400, week=6)
    wall = next(t for t in p.tasks if t.key == "wall")
    assert wall.days == math.ceil(wall.labour / (wall.crew * 400))
    crit = [t.key for t in p.tasks if t.critical]
    assert crit[0] == "earth" and crit[-1] == p.tasks[[t.key for t in p.tasks].index(crit[-1])].key
    assert p.days == max(t.ef for t in p.tasks)
    # every task starts after the ones before it
    idx = {t.key: t for t in p.tasks}
    for t in p.tasks:
        assert all(t.es >= idx[a].ef for a in t.after)
    # the frame by floor, the roof after the top one, the walls after the one under it
    assert [t.key for t in p.tasks if t.key.startswith("frame")] == ["frame0", "frame1"]
    assert idx["roof"].after == ("frame1",) and idx["wall"].after == ("frame0",)


def test_more_hands_shorter():
    d, r = _job()
    a = SC.plan(r, d, crews={"wall": 8})
    b = SC.plan(r, d, crews={"wall": 16})
    assert b.days < a.days


def test_s_curve_and_installments():
    d, r = _job()
    p = SC.plan(r, d)
    assert p.curve[-1][2] == 100.0 and all(x[2] <= y[2] for x, y in zip(p.curve, p.curve[1:]))
    V = r["totals"]["with_f"]
    pays = p.installments(V, advance=15, retention=5)
    assert pays[-1]["cumulative"] == 100.0
    assert abs(sum(x["amount"] for x in pays) - V) < 1.0
    assert all(abs(x["pay"] - x["amount"] * 0.80) < 0.02 for x in pays)


def test_workbook(tmp_path):
    d, r = _job()
    p = SC.plan(r, d)
    SC.write_xlsx(p, tmp_path / "plan.xlsx", value=r["totals"]["with_f"], advance=15, retention=5)
    names = zipfile.ZipFile(tmp_path / "plan.xlsx").namelist()
    assert sum(1 for n in names if n.startswith("xl/worksheets/")) == 2
