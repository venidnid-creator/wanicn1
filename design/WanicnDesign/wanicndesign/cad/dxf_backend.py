# -*- coding: utf-8 -*-
"""Write the drawing to a DXF file (AutoCAD 2007 format, R2007)."""
from __future__ import annotations

import ezdxf
from ezdxf.enums import TextEntityAlignment

from .base import Backend


class DxfBackend(Backend):
    def __init__(self, path: str):
        self.path = path
        self.doc = ezdxf.new("R2007", setup=True)
        self.doc.units = ezdxf.units.M
        self.msp = self.doc.modelspace()

    def layer(self, name: str, color: int = 7) -> None:
        if name not in self.doc.layers:
            self.doc.layers.add(name, color=color)

    def line(self, p1, p2, layer: str) -> None:
        self.msp.add_line(p1, p2, dxfattribs={"layer": layer})

    def circle(self, center, radius: float, layer: str) -> None:
        self.msp.add_circle(center, radius, dxfattribs={"layer": layer})

    def text(self, insert, value: str, height: float, layer: str, center: bool = False) -> None:
        t = self.msp.add_text(value, height=height, dxfattribs={"layer": layer})
        if center:
            t.set_placement(insert, align=TextEntityAlignment.MIDDLE_CENTER)
        else:
            t.set_placement(insert)

    def finish(self) -> None:
        self.doc.saveas(self.path)
