# SPDX-License-Identifier: GPL-3.0-or-later
"""ข้อตรวจตามหลักวิศวกรรมที่เพิ่ม: โมเมนต์ลบปลายคานริม (wL²/16), เสาชะลูด (ACI 10.12),
ความลึก/ความหนาขั้นต่ำกันแอ่น (ACI 9.5) — เทียบกับการคำนวณมือ."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import wanic_building as B  # noqa: E402
from core import wanic_calc as C  # noqa: E402
from core import wanic_rc as R  # noqa: E402


def test_exterior_negative_moment():
    left, right = C.ext_neg_moments([C.Span(4.0, 1000.0), C.Span(4.0, 1000.0)])
    assert abs(left - 1000.0) < 1e-9 and abs(right - 1000.0) < 1e-9          # 1000 × 4² / 16
    l2, r2 = C.ext_neg_moments([C.Span(4.0, 1000.0), C.Span(1.5, 500.0, cant="R")])
    assert l2 > 0 and r2 == 0.0                                                # a cantilever end has its own moment


def test_minimum_depths():
    f = 0.4 + 4000 * 14.2233 / 100000
    assert abs(C.beam_hmin(4.0, False, False, False, 4000) - 4.0 / 16 * f) < 1e-9
    assert abs(C.beam_hmin(4.0, True, True, False, 4000) - 4.0 / 21 * f) < 1e-9
    assert abs(C.beam_hmin(1.5, False, False, True, 4000) - 1.5 / 8 * f) < 1e-9
    assert abs(C.slab_tmin(4.0, 5.0, False, 2, 2400) - 0.10) < 1e-9          # (4 + 5) × 2 / 180
    assert C.slab_tmin(2.0, 2.0, False, 0, 2400) == 0.09                       # never under 9 cm


def test_deflection_uncracked_matches_the_textbook():
    b_ = C.basis({})
    spec = {"b": 0.3, "h": 0.6, "bot": "3-DB16", "top": "2-DB12"}
    w, L = 500.0, 4.0                                                          # kg/m, m — below cracking
    Mm = w * L * L / 8
    dd = C.beam_deflection(L, spec, b_, Mm, 0.0, 0.0)
    Ec = 15100 * math.sqrt(b_["fc"]) * 1e4                                     # kg/m²
    Ig = 0.3 * 0.6 ** 3 / 12
    di = 5 * w * L ** 4 / (384 * Ec * Ig)
    d = (60 - 3 - 1.2) / 100
    As2 = 2 * math.pi * 1.2 ** 2 / 4
    lam = 2 / (1 + 50 * As2 / (30 * d * 100))
    assert abs(dd - di * (1 + lam)) / dd < 1e-6


def test_slender_column_magnifier():
    b_ = C.basis({})
    spec = {"b": 0.25, "h": 0.25}
    slender, delta = C.column_magnifier(spec, b_, 50000.0, 2.6)
    assert abs(slender - 2.6 / (0.3 * 0.25)) < 1e-9
    Ec = 15100 * math.sqrt(b_["fc"]) * 1e4
    Pc = math.pi ** 2 * (0.4 * Ec * 0.25 ** 4 / 12 / 1.6) / 2.6 ** 2
    assert abs(delta - 1 / (1 - 50000 / (0.75 * Pc))) < 1e-9
    assert C.column_magnifier({"b": 0.4, "h": 0.4}, b_, 50000.0, 2.6)[1] == 1.0   # kLu/r ≤ 22
    assert C.column_magnifier(spec, b_, 1e7, 2.6)[1] == 9.9                       # buckles


def test_in_the_calculation():
    d = B.default_data()
    R.apply_grid(d, [4.9, 4.9], [4.9, 2.0], 2)
    res = C.analyse(d)
    beam = next(m for m in res["members"] if m.group == "beam" and "2 ช่วง" in m.name)
    assert "wL²/16" in beam.note and beam.diagram.Mmin <= -max(beam.diagram.Mext)
    col = next(m for m in res["members"] if m.group == "column")
    assert "kLu/r" in col.note
    slab = next(m for m in res["members"] if m.group == "slab" and "4.90×4.90" in m.name)
    assert "หนาขั้นต่ำ" in slab.note and slab.ratio >= 10.9 / 10 - 1e-6       # 10 cm < 10.9 cm
    from core import wanic_advice as AD
    AD.apply_fixes(d)
    assert all(m.ok for m in C.analyse(d)["members"])                         # «แก้ตามคำแนะนำ» fixes them all


def test_stumps_are_checked_and_never_smaller_than_the_column():
    d = B.default_data()
    R.apply_grid(d, [4.9, 4.9], [4.9, 2.0], 2)
    res = C.analyse(d)
    st = [m for m in res["members"] if "ตอม่อ" in m.name]
    assert st and any(not m.ok for m in st)                        # 20×20 cm 4-DB12 under ~70 t fails
    col = next(m for m in res["members"] if m.name.startswith("C1 ที่ (4.90, 4.90)"))
    stm = next(m for m in st if "(4.90, 4.90)" in m.name)
    assert float(stm.demand.split("Pu = ")[1].split(" ")[0]) > float(col.demand.split("Pu = ")[1].split(" ")[0])
    from core import wanic_advice as AD
    AD.apply_fixes(d)
    lib = B.library_of(d)
    assert float(lib["PC1"]["b"]) >= float(lib["C1"]["b"]) and float(lib["PC1"]["h"]) >= float(lib["C1"]["h"])
    assert all(m.ok for m in C.analyse(d)["members"])
