# SPDX-License-Identifier: GPL-3.0-or-later
"""เขียนแบบอิสระ: คาน/เสา/ผนัง จากเส้นที่วาด (ตรง เอียง โค้ง)."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtGui import QVector3D  # noqa: E402

from core import wanic_building as B  # noqa: E402
from core import wanic_calc as C  # noqa: E402
from core import wanic_free as FR  # noqa: E402
from core import wanic_rc as R  # noqa: E402


class _V:
    def __init__(self, p):
        self.position = QVector3D(*p)


class _E:
    def __init__(self, a, b, curve=None):
        self.v0, self.v1, self.curve, self.soft = a, b, curve, False


def _edges(pts, curve=None, verts=None):
    verts = verts if verts is not None else {}
    vs = [verts.setdefault(p, _V(p)) for p in pts]
    return [_E(a, b, curve) for a, b in zip(vs, vs[1:])], verts


def _house():
    d = B.default_data()
    R.apply_grid(d, [4.9, 4.9], [4.9, 2.0], 2)
    return d


def test_chains_and_auto_split():
    verts = {}
    e1, verts = _edges([(9.8, 0, 3.0), (12.8, 0, 4.0)], verts=verts)
    e2, verts = _edges([(12.8, 0, 4.0), (12.8, 0, 0.0)], verts=verts)
    arc = [(5 + math.cos(t / 8 * math.pi), math.sin(t / 8 * math.pi), 3.0) for t in range(9)]
    e3, _ = _edges(arc, curve=3)
    chains = FR.chains_from_edges(e1 + e2 + e3)
    assert len(chains) == 2 and sum(c["curved"] for c in chains) == 1
    d = _house()
    n = FR.add_from_chains(d, chains, "auto")
    assert n == {"beams": 2, "columns": 1, "walls": 0}
    col = d["free"]["columns"][0]
    assert (col["x"], col["z0"], col["z1"]) == (12.8, 0.0, 4.0)
    assert any(b["curved"] for b in d["free"]["beams"])


def test_walls_and_model():
    d = _house()
    wall = [(2.45 + 2.45 * math.cos(math.pi - t * math.pi / 12), -1.0 - math.sin(t * math.pi / 12), 0.0)
            for t in range(13)]
    e, _ = _edges(wall, curve=1)
    FR.add_from_chains(d, FR.chains_from_edges(e), "wall", t=0.10)
    w = d["free"]["walls"][0]
    assert w["curved"] and 5.4 < FR.length2(w["pts"]) < 5.8          # half an ellipse 4.90 × 1.00 m
    d["free"]["beams"] = [{"pts": [[9.8, 0, 3.0], [12.8, 0, 4.0]], "mark": "B1"}]
    d["free"]["columns"] = [{"x": 12.8, "y": 0, "z0": 0, "z1": 4.0, "mark": "C1"}]
    _out, count = B.structure_members(d)
    base = B.structure_members(_house())[1]
    assert count["beam"] == base["beam"] + 1 and count["column"] == base["column"] + 1
    assert count["wall"] == base["wall"] + 1


def test_calculation_takes_the_load_to_the_columns():
    d = _house()
    d["free"] = {"beams": [{"pts": [[9.8, 0, 3.0], [12.8, 0, 4.0]], "mark": "B1", "w": 500}],
                 "columns": [{"x": 12.8, "y": 0, "z0": 0, "z1": 4.0, "mark": "C1"}], "walls": []}
    res = C.analyse(d)
    names = [m.name for m in res["members"]]
    assert any("คานเอียงอิสระ" in n for n in names) and any("อิสระ ที่ (12.80, 0.00)" in n for n in names)
    assert any("F1 ใต้เสาอิสระ" in n for n in names)
    base = dict(C.analyse(_house())["columns"])
    now = dict(res["columns"])
    assert now[(9.8, 0.0)] > base[(9.8, 0.0)]                 # its reaction reached the grid column
    beam = next(m for m in res["members"] if "คานเอียงอิสระ" in m.name)
    # self weight per horizontal metre on a slope: ÷ cos
    L3, Lh = math.hypot(3, 1), 3.0
    assert abs(beam.diagram.spans[0].w - (1.4 * 0.2 * 0.4 * 2400 * L3 / Lh + 1.4 * 500)) < 5


def test_boq_and_sheets():
    from core import wanic_drawings as D
    from core import wanic_quantities as Q
    d = _house()
    d["free"] = {"beams": [{"pts": [[9.8, 0, 3.0], [12.8, 0, 4.0]], "mark": "B1"}],
                 "columns": [{"x": 12.8, "y": 0, "z0": 0, "z1": 4.0, "mark": "C1"}],
                 "walls": [{"pts": [[0, -1], [2.45, -2], [4.9, -1]], "z": 0, "h": 0, "t": 0.1, "curved": True}]}
    desc = [ln["desc"] for ln in Q.compute(d)["lines"]]
    assert any("เขียนอิสระ" in t for t in desc)
    sheets = D.build_set(d)
    txt = " ".join(t for s in sheets for t in s.texts())
    assert "(อิสระ)" in txt and "เอียง" in txt
    D.dxf_bytes(sheets).decode("cp874")


def test_lines_drawn_on_the_model_keep_their_place():
    """The building stands lifted by its floor lift (±0.00 at z = lift in
    the model): a line drawn on the model at +3.60 is the +3.00 level."""
    d = _house()
    lift = B.floor_lift(B.settings_of(d))
    chains = [{"pts": [(9.8, 0.0, 3.0 + lift), (12.8, 0.0, 4.0 + lift)], "closed": False, "curved": False}]
    FR.model_to_building(chains, d)
    FR.add_from_chains(d, chains, "beam")
    assert d["free"]["beams"][0]["pts"][0][2] == 3.0
    g = FR.members(d)[0][0]
    B.lift_groups([g], lift)
    zs = [v.position.z() for v in g.mesh.vertices]
    if getattr(g, "xform", None) is not None:
        zs = [g.xform.map(v.position).z() for v in g.mesh.vertices]
    assert abs(max(zs) - (4.0 + lift)) < 0.05                      # its top back where it was drawn
