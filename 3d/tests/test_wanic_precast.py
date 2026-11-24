# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ข12: พื้นสำเร็จรูป — one way onto two beams, checked by the supplier's table."""
from __future__ import annotations

from core import wanic_building as B
from core import wanic_calc as C
from core import wanic_quantities as Q
from core import wanic_rc as R


def _house(**pc):
    d = B.default_data()
    R.apply_grid(d, [4.0, 4.0], [3.0, 3.0], 2)
    lib = dict(d.get("library") or {})
    lib["S2"] = dict(B.library_of(d)["S2"], precast=1, pc_weight=240, topping=0.05, **pc)
    d["library"] = lib
    return d


def _beam(res, name):
    return [round(sp.w) for sp in res["beams"][name].spans]


def test_planks_rest_on_two_beams_only():
    res = C.analyse(_house(pc_allow=350, pc_span=4.5))
    # rooms 4 × 3 m: the planks span the short way (y) onto the beams along x
    assert _beam(res, "B1 ชั้น 2 · แนวตั้ง x = 4.00 · 2 ช่วง")[0] < _beam(res, "B1 ชั้น 2 · แนวนอน y = 3.00 · 2 ช่วง")[0]
    slabs = [m for m in res["members"] if m.group == "slab" and "สำเร็จรูป" in m.name]
    assert slabs and all(m.ok for m in slabs) and "แนว Y" in slabs[0].name


def test_the_supplier_table_decides():
    res = C.analyse(_house())                                   # not filled in: fails until it is
    assert all(not m.ok for m in res["members"] if m.group == "slab" and "สำเร็จรูป" in m.name)
    res = C.analyse(_house(pc_allow=200, pc_span=4.5))          # 50 finish + 200 live > 200
    assert all(not m.ok for m in res["members"] if m.group == "slab" and "สำเร็จรูป" in m.name)
    res = C.analyse(_house(pc_allow=400, pc_span=2.5))          # 3.00 m span > 2.50
    assert all(not m.ok for m in res["members"] if m.group == "slab" and "สำเร็จรูป" in m.name)


def test_boq_planks_and_topping_no_formwork():
    r = Q.priced(_house(pc_allow=350, pc_span=4.5))
    descs = [ln["desc"] for ln in r["lines"]]
    assert any(d.startswith("แผ่นพื้นคอนกรีตสำเร็จรูป (S2)") for d in descs)
    assert not any(d.startswith("ไม้แบบ") and "พื้นชั้นบน" in d for d in descs)
    conc = next(ln for ln in r["lines"] if ln["desc"].startswith("คอนกรีต") and "พื้นชั้นบน" in ln["desc"])
    plank = next(ln for ln in r["lines"] if ln["desc"].startswith("แผ่นพื้นคอนกรีตสำเร็จรูป"))
    assert abs(conc["net"] - plank["net"] * 0.05) < 1e-6           # the topping only
