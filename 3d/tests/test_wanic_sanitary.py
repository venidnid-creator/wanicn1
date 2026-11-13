# SPDX-License-Identifier: GPL-3.0-or-later
"""ระบบสุขาภิบาลตามจำนวนผู้ใช้ · แผ่น A-01/SN ที่เพิ่ม."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import wanic_building as B  # noqa: E402
from core import wanic_rc as R  # noqa: E402
from core import wanic_sanitary as S  # noqa: E402


def _house(beds=2, users=None):
    d = B.default_data()
    R.apply_grid(d, [4.9, 4.9], [4.9, 2.0], 2)
    names = ["ห้องนั่งเล่น", "ห้องครัว"] + [f"ห้องนอน {i + 1}" for i in range(beds)] + ["ห้องน้ำ 1", "ห้องน้ำ 2"]
    rooms = [rm for f in d["floors"] for rm in f["rooms"]]
    for rm, nm in zip(rooms, names):
        rm["name"] = nm
    if users:
        d["settings"]["users"] = users
    return d


def test_users_and_picks():
    assert S.users_of(_house(0)) == 4                   # at least four
    assert S.users_of(_house(3)) == 6
    assert S.users_of(_house(3, users=11)) == 11        # the setting wins
    assert S.septic_pick(6)["litres"] == 800 and S.septic_pick(5)["litres"] == 600
    big = S.septic_pick(45)
    assert big["litres"] == 2000 and big["count"] == 3
    assert S.grease_pick(6)["litres"] == 50 and S.grease_pick(4)["litres"] == 30


def test_design_from_the_inventory_too():
    d = _house(3)
    a = S.design(d)
    b = S.design(B.elements(d))
    assert a["users"] == b["users"] == 6 and a["septic"] == b["septic"]
    assert any("800" in ln for ln in S.design_lines(d))


def test_boq_follows_the_users():
    from core import wanic_quantities as Q
    d = _house(3)
    d["settings"]["mep"] = True
    lines = [ln["desc"] for ln in Q.compute(d)["lines"]]
    if any("ถังบำบัด" in t for t in lines):
        assert any("ถังบำบัดน้ำเสียสำเร็จรูป 800 ลิตร (ผู้อยู่อาศัย 6 คน)" in t for t in lines)
        assert any("บ่อพักตะแกรง" in t for t in lines)


def test_sheets():
    from core import wanic_drawings as D
    d = _house(3)
    d["floors"][0]["rooms"][3]["name"] = "ห้องน้ำ 1"
    sheets = D.build_set(d)
    titles = [s.title for s in sheets]
    assert "แบบขยายบ่อดักไขมัน บ่อพักตะแกรง" in titles
    E = B.elements(d)
    rm = next(sl["room"] for sl in E["slabs"] if (sl["room"].get("name") or "").startswith("ห้องน้ำ"))
    codes = D.room_codes(E, rm, D.finish_codes(E)).split()
    assert codes[0].startswith("พ") and codes[1] == "ผ3" and codes[2].startswith("ฝ")
