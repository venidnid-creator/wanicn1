# SPDX-License-Identifier: GPL-3.0-or-later
"""ประมาณราคางานเอกชน 8 หมวด."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from core import wanic_building as B
from core import wanic_private_est as P
from core import wanic_rc as R


def _d():
    d = R.apply_grid(B.default_data(), [6, 6], [5, 5], 1)
    d["settings"]["roof"] = "gable"
    return d


def test_eight_categories_and_totals():
    d = _d()
    d["private_est"] = {"overhead": 10.0, "prices": {"เหล็กเสริม DB12": {"mat": 25.0}}}
    r = P.compute(d)
    assert [no for no, _t, _r in r["cats"]] == list(range(1, 9))
    assert r["direct"] == pytest.approx(sum(ln["total"] for ln in r["lines"]), abs=0.05)
    assert r["overhead"] == pytest.approx(r["direct"] * 0.10, abs=0.01)
    assert r["vat"] == pytest.approx((r["direct"] + r["overhead"]) * 0.07, abs=0.01)
    db = [ln for ln in r["lines"] if ln["desc"] == "เหล็กเสริม DB12"]
    assert db and db[0]["mat"] == 25.0 and db[0]["waste"] == 10.0


def test_waste_is_editable():
    d = _d()
    d["private_est"] = {"waste": {"concrete": 0.0}}
    r0 = P.compute(d)
    d["private_est"] = {"waste": {"concrete": 10.0}}
    r1 = P.compute(d)
    c0 = sum(ln["qty"] for ln in r0["lines"] if ln["kind"] == "concrete")
    c1 = sum(ln["qty"] for ln in r1["lines"] if ln["kind"] == "concrete")
    assert c1 == pytest.approx(c0 * 1.10, rel=0.01)


def test_designed_steel_is_added(tmp_path):
    d = _d()
    d["truss"] = {"kind": "howe", "spacing": 4.0}
    d["purlin"] = {}
    d["private_est"] = {"steel_price": 30.0}
    r = P.compute(d)
    st = [ln for ln in r["lines"] if ln["desc"].startswith(("โครง Truss", "แปเหล็ก"))]
    assert len(st) == 2 and all(ln["cat"] == 2 and ln["mat"] == 30.0 for ln in st)
    P.save_xlsx(r, tmp_path / "e.xlsx", {"project": "x"})
    assert (tmp_path / "e.xlsx").stat().st_size > 1000
