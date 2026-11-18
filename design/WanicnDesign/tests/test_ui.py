import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from conftest import ROOT  # noqa: E402
from wanicndesign.structure.building import Building  # noqa: E402
from wanicndesign.ui.pages import parse_spacings  # noqa: E402

BUILDING = os.path.join(ROOT, "examples", "building_2storey.json")


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def win(app):
    from wanicndesign.ui.main_window import MainWindow
    w = MainWindow(Building.load(BUILDING), BUILDING)
    w.show()
    app.processEvents()
    yield w
    w.close()


def test_parse_spacings():
    assert parse_spacings("4, 4, 3.5") == [4.0, 4.0, 3.5]
    assert parse_spacings("3*4; 2.5") == [4.0, 4.0, 4.0, 2.5]
    with pytest.raises(ValueError):
        parse_spacings("4, -1")


def test_plan_click_toggles_and_invalidates(win, app):
    win.calculate()
    assert win.result is not None
    win.level_box.setCurrentText("FL2")
    win.plan.toggle("beam", "FL2:2A-2B")
    app.processEvents()
    assert "FL2:2A-2B" in win.building.skip_beams
    assert win.result is None and win.dirty            # old result dropped
    res = win.calculate()
    assert not any(x.level == "FL2" and x.span == "2A-2B" for x in res.beams)


def test_grid_page_regenerates(win, app):
    grid = win.page_list[1]
    grid.gx.setText("2*5")
    grid.gy.setText("4")
    grid._apply()
    app.processEvents()
    assert win.building.grid_x == [5.0, 5.0] and len(win.building.nodes()) == 6
    res = win.calculate()
    assert len([f for f in res.footings]) == 6


def test_levels_page_round_trip(win):
    page = win.page_list[2]
    levels = page.levels_from_table()
    assert [lv.name for lv in levels] == ["GB", "FL2", "ROOF"]
    assert levels[2].slab == "roof"


def test_exports(win, tmp_path):
    res = win.calculate()
    for kind, name in (("report", "r.xlsx"), ("dxf", "p.dxf"), ("boq", "b.xlsx")):
        out = tmp_path / name
        win.export_to(kind, str(out), res)
        assert out.stat().st_size > 1000


def test_3d_faces_follow_result(win):
    from wanicndesign.ui.view3d import model_faces
    res = win.calculate()
    faces = model_faces(win.building, res)
    boxes = len(res.footings) + len(res.columns) + len(res.beams) + len(res.slabs)
    assert len(faces) == boxes * 6 + 4                 # six faces a box + hip roof


def test_undo_restores_removed_column(win, app):
    win.plan.toggle("node", "2B")
    assert "2B" in win.building.skip_nodes
    win.undo()
    app.processEvents()
    assert "2B" not in win.building.skip_nodes
    win.undo()                                          # nothing left: no error
