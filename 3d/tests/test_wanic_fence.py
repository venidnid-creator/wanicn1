"""รั้วและประตูรั้ว (owner, 27 Nov — studied from the DPT house set): one layout for the 3-D, the BOQ
and the drawings."""
from core import wanic_building as B
from core import wanic_fence as FE
from core import wanic_quantities as Q


def _house(kind="steel"):
    d = B.default_data()
    d["floors"][0]["rooms"] = [dict(name="ห้องนั่งเล่น", x=0, y=0, w=8, d=6)]
    d["settings"]["fence"] = kind
    return d


def test_no_fence_by_default():
    d = B.default_data()
    d["floors"][0]["rooms"] = [dict(name="a", x=0, y=0, w=8, d=6)]
    assert FE.fence_of(d) is None
    assert not any("รั้ว" in ln["desc"] for ln in Q.compute(d)["lines"])


def test_the_fence_round_the_lot_with_a_gate_in_front():
    fc = FE.fence_of(_house())
    x0, y0, x1, y1 = fc["lot"]
    assert (x0, y0, x1, y1) == (-3.0, -5.0, 11.0, 9.0)                     # the site plan's lot
    ga, gb, gy = fc["gate"]
    assert gy == y0 and abs((gb - ga) - 4.0) < 1e-9 and abs((ga + gb) / 2 - 4.0) < 1e-9
    L = sum(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 for a, b in fc["runs"])
    assert abs(L - (2 * (14 + 14) - 4.0)) < 1e-6
    # posts never further apart than the spacing
    for a, b in fc["runs"]:
        on = sorted(p for p in fc["posts"] if min(a[0], b[0]) - 1e-6 <= p[0] <= max(a[0], b[0]) + 1e-6
                    and min(a[1], b[1]) - 1e-6 <= p[1] <= max(a[1], b[1]) + 1e-6)
        gaps = [((q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2) ** 0.5 for p, q in zip(on, on[1:])]
        assert gaps and max(gaps) <= 3.0 + 1e-6


def test_the_fence_is_built_billed_and_drawn():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from core import wanic_drawings as D
    d = _house()
    gs, count = B.build(d, ("structure",))
    kinds = {g.ext[B.EXT_KEY]["kind"] for g in gs}
    assert {"fence", "gate"} <= kinds
    lines = [ln for ln in Q.compute(d)["lines"] if "รั้ว" in ln["desc"]]
    assert any("เสารั้ว" in ln["desc"] for ln in lines) and any("ประตูรั้ว" in ln["desc"] for ln in lines)
    assert all(ln["group"] == "external" for ln in lines)
    titles = [s.title for s in D.build_set(d, {"project": "ท"}, ("A",))]
    assert "แบบขยายรั้วและประตูรั้ว" in titles
    blk = _house("block")
    assert any("คอนกรีตบล็อก" in ln["desc"] for ln in Q.compute(blk)["lines"])
