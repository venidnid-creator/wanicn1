# -*- coding: utf-8 -*-
"""Drawing backends. Both draw the same plan through one small interface:

* :class:`~wanicndesign.cad.dxf_backend.DxfBackend` writes a DXF file
  (opens in AutoCAD 2007 and later) — works anywhere, no AutoCAD needed.
* :class:`~wanicndesign.cad.acad_backend.AcadBackend` drives a running
  AutoCAD on Windows through COM (needs ``pywin32``).
"""
