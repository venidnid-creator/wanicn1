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
    # the owner: as the calc book — every bar of the settings at L, M and R, through the span
    assert "4-DB16 ตลอดแนว" in texts and "3-DB16 ตลอดแนว" in texts and "L/4" not in texts
    assert texts.count("4-DB16") == 6 and texts.count("3-DB16") == 6     # the six sections
    from core import wanic_rc as R
    zone, es = R.end_stirrups(E["lib"]["B1"])
    assert any(t == f"ป.RB6 ปลายคาน 2h @{R.spacing(es)} · กลางช่วง @0.15" for t in texts)
    assert sh.count("circle", "rebar") >= 6 * 4    # six sections with their bars


def test_the_set_has_the_new_structural_sheets():
    titles = [s.title for s in D.build_set(_house(), {"project": "ทดสอบ"}) if s.group == "S"]
    for t in ("รายละเอียดพื้น รอยต่อเสา ครีบ คสล.", "รายละเอียดคาน",
              "รายละเอียดการเสริมเหล็กคานทั่วไป"):
        assert t in titles, t
    assert any(t.startswith("รายละเอียดฐานราก F") for t in titles)      # named by its footings


def test_beam_plan_shows_levels():
    sh = [s for s in D.build_set(_house(), {"project": "x"}) if s.title == "แปลนคาน พื้นชั้น 2"][0]
    assert any("+3.00" in t for t in sh.texts())


def test_the_drawings_show_what_the_calc_book_checked():
    """The owner (25 พ.ย. 69): what passed in the calc book is what the S sheets
    (PDF and DXF: one list of items) show — the same bars, counts and
    spacings, written the same (0.125 never rounded to 0.12)."""
    import re
    from core import wanic_rc as R
    d = R.apply_grid(B.default_data(), [4.9, 4.9], [4.9, 2.0], 2)
    d["settings"]["roof"] = "hip"
    lib = {k: dict(v) for k, v in B.elements(d)["lib"].items()}
    lib["F1"].update(w=1.5, l=1.5, t=0.4, bars="DB16@0.125")
    for k in ("PC1", "C1"):
        lib[k].update(b=0.25, h=0.25, main="6-DB16", tie="RB9@0.175")
    for k in ("GB1", "B1", "RB1"):
        lib[k].update(b=0.25, h=0.5, top="3-DB16", bot="4-DB16", stir="RB9@0.125")
    for k in ("S1", "S2"):
        lib[k].update(t=0.12, bars="RB12@0.175")
    d["library"] = lib
    t = " | ".join(x for s in D.build_set(d, {"project": "x"}, ("S",)) for x in s.texts())
    for want in ("DB16@0.125", "RB9 มม.@0.125", "กลางช่วง @0.125", "RB9 มม.@0.175", "RB12 มม.@0.175",
                 "3-DB16", "4-DB16", "6 DB16"):
        assert want in t, want
    zone, es = R.end_stirrups(lib["B1"])
    assert f"@{R.spacing(es)}" in t and f"2h = {zone:.2f}" in t
    assert not re.search(r"@0\.12(?!5)|@0\.17(?!5)|@0\.062", t)          # never rounded
