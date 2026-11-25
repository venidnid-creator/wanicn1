# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ฉ3: the A0–A4 paper blocks — frame, title block of attributes, the «เวนิช»
font (Venit, from Charm, OFL) shipped with the program and found by name."""
from __future__ import annotations

import ezdxf
import pytest

from core import paper_blocks as PB


def test_every_size_and_its_title_block():
    doc = ezdxf.new("R2018", setup=True)
    for size, (w, h) in PB.SIZES.items():
        name = PB.define(doc, size)
        blk = doc.blocks[name]
        outer = next(e for e in blk.query("LWPOLYLINE"))
        xs = [p[0] for p in outer.get_points("xy")]
        ys = [p[1] for p in outer.get_points("xy")]
        assert (max(xs) - min(xs), max(ys) - min(ys)) == pytest.approx((w, h)), size
        tags = {a.dxf.tag for a in blk.query("ATTDEF")}
        assert tags == {t for t, _l, _d in PB.FIELDS}, size
        assert all(t.dxf.style in (PB.STYLE, PB.STYLE_BOLD) for t in blk.query("TEXT ATTDEF"))
    assert doc.styles.get(PB.STYLE).dxf.font == "Venit-Regular.ttf"
    assert doc.styles.get(PB.STYLE_BOLD).dxf.font == "Venit-Bold.ttf"
    w, h = PB.SIZES["A4"]
    blk = doc.blocks[PB.define(doc, "A4", portrait=True)]
    xs = [p[0] for p in next(iter(blk.query("LWPOLYLINE"))).get_points("xy")]
    assert max(xs) - min(xs) == pytest.approx(h)                       # portrait: 210 wide


def test_inserted_at_the_drawing_scale_with_its_fields():
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 4                                           # mm
    ref = PB.insert(doc, "A3", scale=100, values={"PROJECT": "บ้านพักอาศัย 2 ชั้น"})
    assert ref.dxf.xscale == 100
    att = {a.dxf.tag: a.dxf.text for a in ref.attribs}
    assert att["PROJECT"] == "บ้านพักอาศัย 2 ชั้น" and att["SCALE"] == "1:100" and att["DATE"].split()[-1].isdigit()
    doc6 = ezdxf.new("R2018", setup=True)
    doc6.header["$INSUNITS"] = 6                                          # metres
    assert PB.insert(doc6, "A1", scale=500).dxf.xscale == pytest.approx(0.5)


def test_the_venit_font_is_the_programs_own():
    from core import ezdxf_patches as P
    from core.paths import app_root
    P._register_bundled_fonts()
    from ezdxf.fonts import fonts
    assert (app_root() / "resources" / "fonts" / "Venit-Regular.ttf").exists()
    assert (app_root() / "resources" / "fonts" / "Venit-OFL.txt").exists()
    assert fonts.font_manager.has_font("Venit-Regular.ttf") and fonts.font_manager.has_font("Venit-Bold.ttf")
    from fontTools.ttLib import TTFont
    names = TTFont(str(app_root() / "resources" / "fonts" / "Venit-Regular.ttf"))["name"]
    assert names.getDebugName(1) == "Venit"
    assert any(r.toUnicode() == "เวนิช" for r in names.names if r.nameID == 1 and r.langID == 0x041E)


def test_the_menu_command_inserts_and_undoes(qtbot=None):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from views.main_window import MainWindow
    win = MainWindow()
    if win.document is None:
        win.new_document()
    ent = win._paper_frame("A2", 50)
    assert ent is not None and ent.dxftype() == "INSERT" and ent.dxf.name == "WANIC_A2"
    msp = win.document.doc.modelspace()
    assert any(e.dxftype() == "INSERT" for e in msp)
    win.history.undo(win.document) if _takes_doc(win.history.undo) else win.history.undo()
    assert not any(e.dxftype() == "INSERT" and e.is_alive for e in msp)
    win.document.dirty = False                     # no «save changes?» on close
    win.close()


def _takes_doc(fn):
    import inspect
    return len(inspect.signature(fn).parameters) >= 1
