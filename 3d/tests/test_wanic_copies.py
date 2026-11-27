"""วัตถุที่คัดลอกในโมเดล: flagged, kept by a rebuild, switched by the toggles, billed in the BOQ."""
import copy

from core import wanic_building as B
from core import wanic_copies as CP
from core import wanic_quantities as Q


class _V:
    def __init__(self, x, y, z):
        from PySide6.QtGui import QVector3D
        self.position = QVector3D(x, y, z)


class _M:
    def __init__(self, pts):
        self.vertices = [_V(*p) for p in pts]


class _G:
    def __init__(self, ext, pts):
        self.ext, self.mesh, self.hidden, self.children, self.xform = ext, _M(pts), False, [], None


class _S:
    def __init__(self, groups):
        self.groups = groups


def _box(x0, y0, z0, x1, y1, z1):
    return [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]


def _house():
    d = B.default_data()
    d["floors"][0]["rooms"] = [dict(name="a", x=0, y=0, w=4, d=4), dict(name="b", x=4, y=0, w=4, d=4)]
    d["settings"]["roof"] = "gable"
    return d


def test_the_copies_are_found_and_the_built_one_is_kept():
    ext = {CP.EXT_KEY: {"part": "structure", "kind": "beam", "mark": "RB1", "key": "RB1", "uid": "u1"}}
    g0 = _G(ext, _box(0, 0, 3, 4, 0.2, 3.4))
    g1 = _G(copy.deepcopy(ext), _box(0, 5, 3, 8, 5.2, 3.4))      # copied and stretched to 8 m
    g2 = _G(copy.deepcopy(g1.ext), _box(0, 9, 3, 4, 9.2, 3.4))   # a copy of the copy
    sc = _S([g0, g1, g2])
    assert CP.mark_copies(sc) == [g1, g2]
    assert not CP.is_copy(g0) and CP.is_copy(g1) and CP.is_copy(g2)
    assert len({CP._rec(g)["uid"] for g in (g0, g1, g2)}) == 3
    assert B.generated(sc, copies=False) == [g0] and B.generated(sc) == [g0, g1, g2]
    recs = CP.records(sc)
    assert [r["length"] for r in recs] == [8.0, 4.0]
    assert abs(recs[0]["volume"] - 8 * 0.2 * 0.4) < 1e-6


def test_the_boq_bills_the_copies_at_the_prices_of_the_original():
    d = _house()
    base = Q.compute(d)
    roof_c = next(ln for ln in base["lines"] if ln["desc"].endswith("— คานหลังคา") and ln["unit"] == "ลบ.ม.")
    d["copies"] = [{"kind": "beam", "mark": "RB1", "key": "RB1", "part": "structure",
                    "volume": roof_c["net"] / 2, "length": 4.0},
                   {"kind": "rafter", "mark": "จันทัน", "key": "จันทัน C 150×65×20×3.2", "part": "roof",
                    "volume": 0.01, "length": 5.0},
                   {"kind": "fixture", "mark": "โต๊ะ", "key": "โต๊ะ", "part": "structure",
                    "volume": 0.5, "length": 1.2}]
    res = Q.compute(d)
    extra = [ln for ln in res["lines"] if "คัดลอก" in ln["desc"]]
    conc = next(ln for ln in extra if ln["desc"].startswith("คอนกรีตโครงสร้าง") and "คานหลังคา" in ln["desc"])
    assert abs(conc["net"] - roof_c["net"] / 2) < 1e-6 and conc["mat"] == roof_c["mat"]
    assert any(ln["desc"].startswith("ไม้แบบหล่อคอนกรีต — คานหลังคา") for ln in extra)
    assert any(ln["group"] == "rebar" for ln in extra)               # steel in proportion
    steel = next(ln for ln in extra if ln["desc"].startswith("โครงหลังคาเหล็ก C 150×65×20×3.2"))
    assert steel["unit"] == "กก." and steel["net"] > 5 * 5
    other = next(ln for ln in extra if "โต๊ะ" in ln["desc"])
    assert other["qty"] == 1 and other["missing"]                     # orange until priced
    assert res["totals"] != base["totals"]


def test_copies_do_not_ask_for_a_new_calculation():
    d = _house()
    s0 = B.struct_stamp(d)
    d["copies"] = [{"kind": "beam", "mark": "RB1", "key": "RB1", "part": "structure", "volume": 0.1, "length": 4}]
    assert B.struct_stamp(d) == s0
