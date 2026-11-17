# -*- coding: utf-8 -*-
"""Drive a running AutoCAD on Windows through COM (needs ``pywin32``).

Not testable outside Windows with AutoCAD; it uses only the long-standing
ActiveX calls (AddLine, AddCircle, AddText, Layers.Add) that AutoCAD 2007
already had.
"""
from __future__ import annotations

from .base import Backend

AC_ALIGN_MIDDLE_CENTER = 10


class AcadBackend(Backend):
    def __init__(self):
        try:
            import pythoncom
            import win32com.client
        except ImportError as e:  # pragma: no cover - Windows only
            raise RuntimeError("ต้องติดตั้ง pywin32 และใช้บน Windows ที่มี AutoCAD") from e
        self._pythoncom = pythoncom
        self._win32 = win32com.client
        try:
            self.app = win32com.client.GetActiveObject("AutoCAD.Application")
        except Exception as e:  # pragma: no cover
            raise RuntimeError("ไม่พบ AutoCAD ที่เปิดอยู่ ให้เปิด AutoCAD ก่อน") from e
        self.doc = self.app.ActiveDocument
        self.space = self.doc.ModelSpace

    def _pt(self, p):
        x, y = p[0], p[1]
        return self._win32.VARIANT(self._pythoncom.VT_ARRAY | self._pythoncom.VT_R8,
                                   (float(x), float(y), 0.0))

    def layer(self, name: str, color: int = 7) -> None:
        lay = self.doc.Layers.Add(name)
        lay.color = color

    def _on(self, ent, layer: str):
        ent.Layer = layer
        return ent

    def line(self, p1, p2, layer: str) -> None:
        self._on(self.space.AddLine(self._pt(p1), self._pt(p2)), layer)

    def circle(self, center, radius: float, layer: str) -> None:
        self._on(self.space.AddCircle(self._pt(center), float(radius)), layer)

    def text(self, insert, value: str, height: float, layer: str, center: bool = False) -> None:
        t = self.space.AddText(value, self._pt(insert), float(height))
        if center:
            t.Alignment = AC_ALIGN_MIDDLE_CENTER
            t.TextAlignmentPoint = self._pt(insert)
        self._on(t, layer)

    def finish(self) -> None:
        self.app.ZoomExtents()
