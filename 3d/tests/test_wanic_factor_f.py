# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""Factor F from the ว 481 tables (26 มิ.ย. 2569) and the lookup rule."""
from __future__ import annotations

import pytest

from core import wanic_factor_f as FF
from core import wanic_takeoff as T


def test_every_table_of_the_letter():
    assert len(FF.TABLES) == 4
    for kind, tables in FF.TABLES.items():
        assert sorted(tables) == [(a, r) for a in FF.ADVANCE for r in FF.RETENTION]
        for rows in tables.values():
            xs = [x for _s, x, _v in rows]
            assert xs == sorted(xs) and rows[0][0] == "≤"
    # spot values read off the pages
    assert FF.TABLES["building"][(0, 0)][0] == ("≤", 0.5, (1.2218, 1.3073))
    assert FF.TABLES["building"][(0, 0)][-1] == (">", 500, (1.1016, 1.1787))
    assert FF.TABLES["bridge"][(0, 0)][-1] == ("≥", 200, (1.0747, 1.1499))
    assert FF.TABLES["road"][(0, 0)][0] == ("≤", 5, (1.2733, 1.3624, 1.3821, 1.4018))


def test_lookup_rule_9_3():
    # on a row, below the first, above the last
    assert FF.lookup(10e6).value == 1.2942
    assert FF.lookup(0.2e6).value == 1.3073
    assert FF.lookup(800e6).value == 1.1787
    # between rows: F = D - (D - E)(A - B)/(C - B)
    r = FF.lookup(2.35e6)
    assert r.value == round(1.3034 - (1.3034 - 1.3002) * (2.35 - 2) / (5 - 2), 4)
    assert "2 ล้านบาท" in r.note() and "ว 481" in r.note()
    assert FF.lookup(2.35e6, vat=False).value < r.value          # รวมในรูป Factor
    assert FF.lookup(12e6, "road", rain=2).value > FF.lookup(12e6, "road").value
    assert FF.lookup(5e6, advance=10, retention=5).value == \
        FF.TABLES["building"][(10, 5)][3][2][1]
    with pytest.raises(ValueError):
        FF.lookup(5e6, advance=3)
    v, note = FF.blended(400e6, 60)
    assert v == round(FF.lookup(400e6, vat=False).value * 0.6 +
                      FF.lookup(400e6).value * 0.4, 4) and "9.3" in note


def test_the_takeoff_looks_it_up():
    data = T.default_data()
    data["rates"] = [T.new_rate(qty="manual", manual_qty=1, mat=2_350_000)]
    r = T.compute([], data)
    assert r["factor_f"] == FF.lookup(2.35e6).value and "ว 481" in r["ff_note"]
    assert abs(r["grand"] - 2_350_000 * r["factor_f"]) < 1e-6
    # a Factor F typed by hand in an older job stays as it was
    old = {"rates": data["rates"], "settings": {"factor_f": 1.25}}
    assert T.compute([], old)["factor_f"] == 1.25
    # conditions not in the tables: the typed value, and why
    data["settings"].update(adv_pay=3, factor_f=1.3, ff_auto=True)
    r = T.compute([], data)
    assert r["factor_f"] == 1.3 and "ว 481" in r["ff_note"]
