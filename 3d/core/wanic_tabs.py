# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""แท็บของแผง WANIC: an icon of its own for each panel (drawn in the
tools' ink, so it follows the theme like the others) and a short Thai name
written beside it — the side tray's tabs show only an icon, and five
WANIC panels whose names all start with «อ» could not be told apart.

``register()`` adds the drawings to ``views.icons`` (keys ``wanic_*``);
``SHORT`` is what ``views.main_window._IconTabStyle`` writes beside the
icon of a tab of that title."""
from __future__ import annotations

#: panel title → the name its tab shows
SHORT = {
    "ออกแบบอาคาร": "อาคาร",
    "ออกแบบโครงสร้าง คสล.": "คสล.",
    "ออกแบบถนน": "ถนน",
    "ถอดปริมาณ": "ถอดปริมาณ",
    "โปรไฟล์": "โปรไฟล์",
}

#: panel title → its icon key
ICON = {
    "ออกแบบอาคาร": "wanic_building",
    "ออกแบบโครงสร้าง คสล.": "wanic_rc",
    "ออกแบบถนน": "wanic_road",
    "ถอดปริมาณ": "wanic_takeoff",
    "โปรไฟล์": "wanic_profiles",
}


def short_name(title: str) -> str | None:
    return SHORT.get(title)


# ---- the drawings (48 × 48, as views.icons; pen already set to the ink) -----

def _building(p, ink):
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QPolygonF
    from views.icons import _accent_fill
    roof = QPolygonF([QPointF(8, 23), QPointF(24, 9), QPointF(40, 23)])
    _accent_fill(p, roof, 170)
    p.drawPolyline(roof)
    p.drawRect(QRectF(12, 23, 24, 17))
    p.drawRect(QRectF(21, 30, 6, 10))                 # the door


def _rc(p, ink):
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QPolygonF
    from views.icons import _accent_fill
    beam = QPolygonF([QPointF(7, 11), QPointF(41, 11), QPointF(41, 17), QPointF(7, 17)])
    _accent_fill(p, beam, 170)
    p.drawPolygon(beam)
    p.drawRect(QRectF(11, 17, 6, 20))                 # two columns
    p.drawRect(QRectF(31, 17, 6, 20))
    p.drawLine(QPointF(7, 40), QPointF(41, 40))       # their footings
    p.drawLine(QPointF(9, 37), QPointF(19, 37))
    p.drawLine(QPointF(29, 37), QPointF(39, 37))


def _road(p, ink):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QPolygonF
    from views.icons import _accent_fill
    road = QPolygonF([QPointF(19, 8), QPointF(29, 8), QPointF(42, 40), QPointF(6, 40)])
    _accent_fill(p, road, 90)
    p.drawLine(QPointF(19, 8), QPointF(6, 40))
    p.drawLine(QPointF(29, 8), QPointF(42, 40))
    for y0, y1 in ((11, 16), (21, 27), (32, 39)):     # the centre line, dashed
        p.drawLine(QPointF(24, y0), QPointF(24, y1))


def _takeoff(p, ink):
    from PySide6.QtCore import QPointF, QRectF
    from views.icons import _dot
    p.drawRoundedRect(QRectF(11, 9, 26, 31), 3, 3)    # a sheet with its rows
    p.drawRect(QRectF(19, 6, 10, 6))
    for y in (19, 26, 33):
        _dot(p, 16.5, y, 2.2)
        p.drawLine(QPointF(21, y), QPointF(32, y))


def _profiles(p, ink):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QPolygonF
    from views.icons import _accent_fill
    i_beam = QPolygonF([QPointF(10, 9), QPointF(38, 9), QPointF(38, 15), QPointF(27, 15),
                        QPointF(27, 33), QPointF(38, 33), QPointF(38, 39), QPointF(10, 39),
                        QPointF(10, 33), QPointF(21, 33), QPointF(21, 15), QPointF(10, 15)])
    _accent_fill(p, i_beam, 140)
    p.drawPolygon(i_beam)


_DRAWINGS = {"wanic_building": _building, "wanic_rc": _rc, "wanic_road": _road,
             "wanic_takeoff": _takeoff, "wanic_profiles": _profiles}


def register() -> None:
    """Put the WANIC panels' drawings among the application's icons."""
    try:
        from views import icons
    except Exception:                                 # noqa: BLE001 - no icons, the tab shows its initial
        return
    for key, draw in _DRAWINGS.items():
        icons._DRAW.setdefault(key, draw)


def icon_key(title: str) -> str | None:
    """The icon key of a WANIC panel (registered first), or None."""
    key = ICON.get(title)
    if key is not None:
        register()
    return key
