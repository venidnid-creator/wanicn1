# SPDX-License-Identifier: GPL-3.0-or-later
"""แบบงานเหล็กรูปพรรณ."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core import wanic_building as B
from core import wanic_drawings as D
from core import wanic_rc as R
from core import wanic_steel_sheets as ST


def _steel_house():
    d = R.apply_grid(B.default_data(), [4.9, 4.9], [4.9], 2)
    d["settings"]["roof"] = "hip"
    d["steel"] = {"beams": True}
    d["truss"] = {"kind": "howe", "spacing": 4.0}
    d["purlin"] = {}
    return d


def test_min_fillet_and_angles():
    assert [ST.min_fillet(t) for t in (5, 10, 16, 25)] == [3, 5, 6, 8]
    assert ST.clip_angle(250) == "L 50×50×6" and ST.clip_angle(400) == "L 65×65×6"


def test_connection_welds_carry_the_web_shear():
    rows = ST.connection_rows(_steel_house())
    assert rows and all(cap >= vw for *_x, vw, cap in rows)


def test_sheets_only_with_steel():
    plain = R.apply_grid(B.default_data(), [4, 4], [4], 1)
    titles = [s.title for s in D.build_set(plain, {"project": "x"})]
    assert "มาตรฐานงานเชื่อม" not in titles
    S = {s.title: s for s in D.build_set(_steel_house(), {"project": "x"})}
    assert "มาตรฐานงานเชื่อม" in S
    sh = S["รอยต่อเหล็กรูปพรรณ แผ่นรองเสา ส้นโครง Truss"]
    texts = " ".join(sh.texts())
    assert "Base Plate" in texts and "Turnbuckle" in texts and "ส้นโครง Truss" in texts
