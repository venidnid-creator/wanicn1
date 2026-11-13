# SPDX-License-Identifier: GPL-3.0-or-later
"""เสาเข็ม 2 ขนาด · กำลังเข็มจากผลทดสอบ."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import wanic_building as B  # noqa: E402
from core import wanic_calc as C  # noqa: E402
from core import wanic_pile as PL  # noqa: E402
from core import wanic_rc as R  # noqa: E402


def test_methods_by_hand():
    assert PL.capacity({"section": "I18", "method": "given", "Qa": 8})["Qa"] == 8
    st = PL.capacity({"section": "S30", "method": "static", "Qult": 60})
    assert abs(st["Qa"] - 30.0) < 1e-9 and st["FS"] == 2.0
    dy = PL.capacity({"section": "S30", "method": "dynamic", "Qult": 60})
    assert abs(dy["Qa"] - 24.0) < 1e-9
    # Hiley: 0.8 × 1.5 t × 500 mm / (10 + 25/2) mm = 26.67 t → / 3
    hi = PL.capacity({"section": "S30", "method": "hiley", "W": 1.5, "H": 0.5, "S": 10, "C": 25, "eff": 0.8})
    assert abs(hi["Qult"] - 26.6667) < 1e-3 and abs(hi["Qa"] - 26.6667 / 3) < 1e-3
    # soil: S30 perimeter 1.2 — 4 m × 1 t/m² + 4 m × 2 t/m², qb 100 × 0.09
    so = PL.capacity({"section": "S30", "len": 8, "method": "soil", "layers": [[4, 1.0], [4, 2.0]], "qb": 100})
    assert abs(so["Qult"] - (1.2 * 4 + 1.2 * 8 + 9.0)) < 1e-9 and abs(so["Qa"] - so["Qult"] / 2.5) < 1e-9


def test_structural_limit_governs():
    c = PL.capacity({"section": "I18", "method": "static", "Qult": 200})
    assert c["Qa"] == c["Q_struct"] and c["governs"] == "กำลังตัวเข็ม"


def _house():
    d = B.default_data()
    R.apply_grid(d, [4.9, 4.9], [4.9, 2.0], 2)
    return d


def test_old_documents_keep_the_basis_capacity():
    d = _house()
    d.setdefault("library", {})["F1"] = {"kind": "footing", "piles": 4}
    res = C.analyse(d)
    f = next(m for m in res["members"] if m.group == "footing")
    assert "4 × 8.00" in f.capacity and B.library_of(d)["F1"]["pile_b"] == 0.18


def test_two_sizes_in_the_building():
    d = _house()
    d["piles"] = {"P1": {"section": "I22", "len": 8, "method": "given", "Qa": 12},
                  "P2": {"section": "D30", "len": 12, "method": "static", "Qult": 60}}
    d["library"] = {"F1": {"kind": "footing", "piles": 2, "pile": "P1"},
                    "F2": {"kind": "footing", "piles": 2, "pile": "P2", "w": 1.2, "l": 1.2, "t": 0.4, "depth": 1.5,
                           "bars": "DB12@0.15"}}
    lib = B.library_of(d)
    assert lib["F2"]["pile_shape"] == "round" and lib["F2"]["pile_len"] == 12 and lib["F1"]["pile_b"] == 0.22
    assert PL.cap_of(lib["F2"], d, C.basis(d)) == 30.0
    d["assign"] = {B.node_key(4.9, 4.9): {"F": "F2"}}
    res = C.analyse(d)
    caps = {m.name.split(" ")[0]: m.capacity for m in res["members"] if m.group == "footing"}
    assert "12.00" in caps["F1"] and "30.00" in caps["F2"]
    from core import wanic_quantities as Q
    desc = [ln["desc"] for ln in Q.compute(d)["lines"] if "เข็ม" in ln["desc"]]
    assert any("สปัน" in t and "P2" in t for t in desc)


def test_dialog_round_trip():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from core.wanic_pile_view import PileDialog, parse_layers
    assert parse_layers("4:1, 6:2.5", 10) == [[4.0, 1.0], [6.0, 2.5]]
    d = _house()
    d["piles"] = {"P2": {"section": "S30", "len": 10, "method": "static", "Qult": 50, "FS": 2.2}}
    dlg = PileDialog(None, d)
    v = dlg.piles()
    assert v["P2"]["FS"] == 2.2 and v["P2"]["Qult"] == 50          # the FS is kept, not reset
    dlg.apply(d)
    assert d["piles"]["P1"]["method"] == "given" and "F1" in d["library"]
    dlg.deleteLater()
    QApplication.processEvents()
