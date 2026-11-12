# SPDX-License-Identifier: GPL-3.0-or-later
"""แบบโครงสร้างจากผลออกแบบ: beam lines, profiles, footings, columns, slabs."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core import wanic_building as B
from core import wanic_drawings as D
from core import wanic_rc as R
from core import wanic_struct_sheets as SS


def _house():
    d = R.apply_grid(B.default_data(), [4.9, 4.9], [4.9], 2)
    d["settings"]["roof"] = "hip"
    d["library"] = {"B1": {"top": "4-DB16", "bot": "3-DB16", "h": 0.5}}
    return d


def test_beam_lines_join_the_spans_of_a_grid_line():
    E = B.elements(_house())
    lines = SS.beam_lines(E)
    ga = [ln for ln in lines if ln["level"] == 1 and ln["dir"] == "x"]
    assert ga and all(len(ln["spans"]) == 2 for ln in ga)
    assert SS.line_name(E, ga[0]).startswith("แนวแกน")
    assert sum(len(x) for x in SS.beam_sheets(E)) == len(lines)


def test_profile_shows_extra_bars_and_sections():
    E = B.elements(_house())
    ln = next(ln for ln in SS.beam_lines(E) if ln["level"] == 1 and len(ln["spans"]) == 2)
    sh = D.Sheet("S-99", "x", "1:30", "S")
    SS.beam_profile(sh, E, ln, 20, 270, 330)
    texts = sh.texts()
    assert "4-DB16" in texts                       # the extra top bars over the supports
    assert "3-DB16" in texts and "L/4" in texts
    assert any(t.startswith("ป.RB6@") for t in texts)
    assert sh.count("circle", "rebar") >= 6 * 4    # six sections with their bars


def test_the_set_has_the_new_structural_sheets():
    titles = [s.title for s in D.build_set(_house(), {"project": "ทดสอบ"}) if s.group == "S"]
    for t in ("รายละเอียดฐานราก", "รายละเอียดเสา", "รายละเอียดพื้น", "รายละเอียดคาน",
              "รายละเอียดการเสริมเหล็กคานทั่วไป"):
        assert t in titles, t


def test_beam_plan_shows_levels():
    sh = [s for s in D.build_set(_house(), {"project": "x"}) if s.title == "แปลนคาน พื้นชั้น 2"][0]
    assert any("+3.00" in t for t in sh.texts())
