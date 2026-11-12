# SPDX-License-Identifier: GPL-3.0-or-later
"""น้ำหนักเพิ่มบนคาน · คานยื่น · Checkload."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import wanic_building as B  # noqa: E402
from core import wanic_calc as C  # noqa: E402
from core import wanic_rc as R  # noqa: E402


def _house():
    d = B.default_data()
    R.apply_grid(d, [4.9, 4.9], [4.9, 2.0], 2)
    return d


def test_part_length_load_by_hand():
    r = C.solve_beam([C.Span(4, 0, U=[(0, 2, 1000)])])
    assert [round(x) for x in r.reactions] == [1500, 500]
    assert abs(r.Mmax - 1125) < 2
    full = C.solve_beam([C.Span(4, 0, U=[(0, 4, 1000)])])
    assert abs(full.Mmax - 2000) < 1


def test_cantilever_by_hand():
    r = C.solve_beam([C.Span(4, 0), C.Span(1, 0, [(1.0, 1000)], cant="R")])
    assert round(r.Mmin) == -1000 and [round(x) for x in r.reactions] == [-250, 1250]
    assert r.supports == [0.0, 4.0]
    lft = C.solve_beam([C.Span(1, 0, [(0.0, 1000)], cant="L"), C.Span(4, 0)])
    assert [round(x) for x in lft.reactions] == [1250, -250] and lft.supports == [1.0, 5.0]
    alone = C.solve_beam([C.Span(2, 1000, cant="R")])
    assert round(alone.Mmin) == -2000 and alone.reactions == [2000.0]


def test_cantilever_and_loads_in_the_building():
    d = _house()
    d["cantilevers"] = [{"level": 1, "x": 9.8, "y": 0.0, "dir": "+x", "L": 1.5}]
    d["beam_loads"] = [{"level": 1, "axis": "x", "line": 0.0, "a": 10.5, "b": 11.3, "w": 300, "type": "D"},
                       {"level": 1, "axis": "x", "line": 0.0, "a": 2.0, "b": 2.0, "P": 800, "type": "L"}]
    E = B.elements(d)
    cb = [b for b in E["beams"] if b.get("cant")]
    assert len(cb) == 1 and cb[0]["p1"] == (11.3, 0.0) and cb[0]["mark"] == "B1"
    res = C.analyse(d)
    m = next(m for m in res["members"] if "คานยื่น" in m.name)
    br = m.diagram
    assert br.spans[-1].cant == "R" and br.spans[0].P == [(2.0, 800 * 1.7)]
    assert len(br.reactions) == 3
    # the cantilever's load reaches the column at x = 9.8
    base = dict(C.analyse(_house())["columns"])
    now = dict(res["columns"])
    assert now[(9.8, 0.0)] > base[(9.8, 0.0)]


def test_checkload():
    d = _house()
    ck = C.checkload(d, C.analyse(d))
    assert len(ck["rows"]) == 9 and ck["area"] > 0
    assert 450 <= ck["mean"] <= 1600
    assert abs(sum(r["WA"] for r in ck["rows"]) - ck["total"]) < 1.0
    assert all("note" in r for r in ck["rows"])


def test_dialog_rows_round_trip():
    from core import wanic_beamload_view as V
    q = {"level": 1, "axis": "y", "line": 4.9, "a": 1.0, "b": 1.0, "P": 1100.0, "type": "D", "note": "ถังน้ำ"}
    assert V.row_to_load(V.load_to_row(q)) == q
    w = {"level": 0, "axis": "x", "line": 0.0, "a": 0.0, "b": 4.9, "w": 540.0, "type": "L", "note": ""}
    assert V.row_to_load(V.load_to_row(w)) == w
    c = {"level": 1, "x": 9.8, "y": 0.0, "dir": "-y", "L": 1.2}
    assert V.row_to_cant(V.cant_to_row(c)) == c
    assert V.row_to_load(["2", "x", "0", "1", "1", "จุด", "0", "คงที่", ""]) is None
    lines = V.beam_lines(_house())
    assert any(t.startswith("คานชั้น 2") for t, *_r in lines)
