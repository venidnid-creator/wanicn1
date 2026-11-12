# SPDX-License-Identifier: GPL-3.0-or-later
"""รายการคำนวณแบบการ์ด: footings, slabs, Me, the critical-only book."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from core import wanic_building as B
from core import wanic_calc as C
from core import wanic_calc_cards as CC
from core import wanic_rc as R


def _d():
    d = R.apply_grid(B.default_data(), [4.9, 4.9], [4.9, 2.0], 2)
    d["settings"]["roof"] = "hip"
    return d


def test_slab_coefficients_both_spans():
    cn, cp, cd = CC.coef(1.0, 0)
    assert (cn, cp) == (0.033, 0.025)
    cn, cp, cd = CC.coef(0.75, 2)
    assert cn == pytest.approx((0.064 + 0.071) / 2)


def test_slab_rows_and_spacing():
    d = _d()
    rows = CC.slab_rows(C.analyse(d), d)
    big = max(rows, key=lambda r: r["S"] * r["L"])
    assert big["kind"] == "Two-way Slab" and big["M"]["s-"] > big["M"]["s+"] > 0
    assert all(0 < s <= 3 * big["t"] + 1e-9 for s in big["s"].values())
    one = [r for r in rows if r["kind"] == "One-way Slab"]
    assert one                                       # the 4.90 × 2.00 bay (m < 0.5)


def test_footing_rows_check_soil_and_shear():
    d = _d()
    res = C.analyse(d)
    rows = CC.footing_rows(res, d)
    r = max(rows, key=lambda r: r["P"])
    assert r["q"] > r["P"] / (r["w"] * r["l"])       # includes the footing and the soil on it
    assert r["Vc2"] > 0 and r["nbar"] >= 2
    d["library"] = {"F1": {"w": 2.4, "l": 2.4, "t": 0.40}}
    rows2 = CC.footing_rows(C.analyse(d), d)
    assert max(rows2, key=lambda r: r["P"])["ok"]    # a big enough footing passes


def test_critical_book_is_shorter(tmp_path):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from core.wanic_calc_book import make_book
    d = _d()
    d["lateral"] = {"eq_on": True}
    n_all = make_book(C.analyse(d), d, tmp_path / "a.pdf", {"project": "x"})
    n_crit = make_book(C.analyse(d), d, tmp_path / "c.pdf", {"project": "x"}, critical=True)
    assert n_crit < n_all
    res = C.analyse(d)
    CC.attach_lateral_moments(res, d)
    assert any(getattr(m.diagram, "me", 0) > 0 for m in res["members"] if m.group == "beam")


def test_advice_says_what_and_where_and_the_fixes_pass():
    from core import wanic_advice as AD
    d = _d()
    res = C.analyse(d)
    tips = AD.advise(res, d)
    assert tips
    text = " ".join(" ".join(t) for _n, t in tips)
    assert "กลางช่วง" in text and "เหนือหัวเสา" in text and "ขั้น" in text
    done = AD.apply_fixes(d)
    assert done
    res = C.analyse(d)
    assert all(m.ok for m in res["members"])
    assert all(r["ok"] for r in CC.slab_rows(res, d)) and all(r["ok"] for r in CC.footing_rows(res, d))
    assert all(r.ok for r in R.check_library(B.library_of(d)).values())


def test_bars_fit_in_the_beam():
    from core import wanic_advice as AD
    assert AD.fit_in_row(0.20, 12) == 4 and AD.fit_in_row(0.20, 16) == 3


def test_every_failing_row_has_advice_and_a_fix_that_passes_its_mark():
    from core import wanic_advice as AD
    from core.wanic_fix_view import apply
    d = _d()
    res = C.analyse(d)
    tips = AD.advice_by_member(res, d)
    bad = [m for m in res["members"] if not m.ok]
    assert bad and all(m.name in tips for m in bad)
    # fix one column row: every member of that mark passes afterwards
    col = next(m for m in bad if m.group == "column")
    fix = AD.member_fix(res, d, col)
    assert fix["target"] == "lib" and fix["key"] == "C1" and fix["changes"]
    apply(d, fix, fix["changes"])
    res2 = C.analyse(d)
    assert all(m.ok for m in res2["members"] if m.group == "column")
    # a footing row: the mark is sized from its most loaded footing
    ft = next(m for m in res2["members"] if m.group == "footing" and not m.ok)
    fix = AD.member_fix(res2, d, ft)
    apply(d, fix, fix["changes"])
    res3 = C.analyse(d)
    assert all(m.ok for m in res3["members"] if m.group == "footing")


def test_every_change_is_symmetric_and_balanced():
    from core import wanic_advice as AD
    col = AD.balance_spec({"kind": "column", "b": 0.25, "h": 0.20, "main": "6-DB12"})
    assert col["b"] == col["h"] == 0.25 and col["main"] == "8-DB12"
    rect = AD.balance_spec({"kind": "column", "b": 0.20, "h": 0.40, "main": "5-DB12"}, keep_shape=True)
    assert (rect["b"], rect["h"], rect["main"]) == (0.20, 0.40, "6-DB12")
    bm = AD.balance_spec({"kind": "beam", "b": 0.2, "h": 0.4, "top": "3-DB20", "bot": "3-DB16"})
    t, b = R.parse_bar(bm["top"]), R.parse_bar(bm["bot"])
    assert t.d == b.d and b.n * b.area >= 3 * R.parse_bar("1-DB16").area - 1e-9
    ft = AD.balance_spec({"kind": "footing", "w": 2.2, "l": 1.8, "piles": 0})
    assert ft["w"] == ft["l"] == 2.2
    d = _d()
    AD.apply_fixes(d)
    lib = B.library_of(d)
    for mark, sp in lib.items():
        if sp.get("kind") in ("column", "stump"):
            assert sp["b"] == sp["h"] and R.parse_bar(sp["main"]).n % 4 == 0, mark
        if sp.get("kind") == "beam":
            assert R.parse_bar(sp["top"]).d == R.parse_bar(sp["bot"]).d, mark
        if sp.get("kind") == "footing":
            assert sp["w"] == sp["l"], mark
    res = C.analyse(d)
    assert all(m.ok for m in res["members"])


def test_single_member_fix_meets_the_detailing_minimums():
    from core import wanic_advice as AD
    from core.wanic_fix_view import apply
    d = _d()
    res = C.analyse(d)
    col = next(m for m in res["members"] if m.group == "column" and not m.ok)
    fix = AD.member_fix(res, d, col)
    apply(d, fix, {**B.library_of(d)["C1"], **fix["changes"]})
    assert R.check("C1", B.library_of(d)["C1"]).ok
