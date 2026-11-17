import ezdxf

from conftest import EXAMPLE
from wanicndesign.cad.base import draw_grid
from wanicndesign.cad.dxf_backend import DxfBackend
from wanicndesign.model import Project


def test_grid_dxf(tmp_path):
    out = tmp_path / "plan.dxf"
    b = DxfBackend(str(out))
    names = draw_grid(Project.load(EXAMPLE), b)
    b.finish()
    assert names["x"] == {"A": 0.0, "B": 4.0, "C": 8.0, "D": 12.0}
    assert names["y"] == {"1": 0.0, "2": 4.0, "3": 8.0}
    doc = ezdxf.readfile(out)
    msp = doc.modelspace()
    marks = [e for e in msp.query("CIRCLE") if e.dxf.layer == "columncopy"]
    assert len(marks) == 12                     # 4 × 3 intersections
    texts = {e.dxf.text for e in msp.query("TEXT")}
    assert {"A", "D", "1", "3", "4.00"} <= texts
