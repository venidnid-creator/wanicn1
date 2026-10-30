# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeCAD contributors.
"""The import options: column order, label choice and text height, with a
preview of the first points so a wrong order is seen before it lands."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from core.i18n import tr

from .actions import LabelStyle
from .points import ORDERS, parse_points

PREVIEW_ROWS = 5


class ImportOptionsDialog(QDialog):
    def __init__(self, parent, text: str, order: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Import points"))
        self._text = text
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.order_box = QComboBox(self)
        for name in ORDERS:
            self.order_box.addItem(name, name)
        self.order_box.setCurrentIndex(max(0, list(ORDERS).index(order)))
        form.addRow(tr("Column order:"), self.order_box)

        self.height = QDoubleSpinBox(self)
        self.height.setRange(0.001, 10000.0)
        self.height.setDecimals(3)
        self.height.setValue(1.0)
        form.addRow(tr("Text height:"), self.height)

        labels = QHBoxLayout()
        self.number = QCheckBox(tr("Number"), self)
        self.elevation = QCheckBox(tr("Elevation"), self)
        self.description = QCheckBox(tr("Description"), self)
        for box in (self.number, self.elevation, self.description):
            box.setChecked(True)
            labels.addWidget(box)
        form.addRow(tr("Labels:"), labels)

        self.decimals = QSpinBox(self)
        self.decimals.setRange(0, 6)
        self.decimals.setValue(2)
        form.addRow(tr("Elevation decimals:"), self.decimals)

        self.preview = QLabel(self)
        self.preview.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.preview)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.order_box.currentIndexChanged.connect(lambda _i: self._refresh())
        self._refresh()

    def order(self) -> str:
        return str(self.order_box.currentData())

    def style(self) -> LabelStyle:
        chosen = tuple(kind for kind, box in (("number", self.number),
                                              ("elevation", self.elevation),
                                              ("description", self.description))
                       if box.isChecked())
        return LabelStyle(text_height=float(self.height.value()), labels=chosen,
                          decimals=int(self.decimals.value()))

    def _refresh(self) -> None:
        try:
            points = parse_points(self._text, self.order())
        except ValueError:
            self.preview.setText(tr("No points parse with this order."))
            return
        lines = [tr("Preview (first {n} of {total}):",
                    n=min(PREVIEW_ROWS, len(points)), total=len(points))]
        for p in points[:PREVIEW_ROWS]:
            lines.append(f"{p.name}   N={p.north:.3f}   E={p.east:.3f}   "
                         f"Z={p.z:.3f}   {p.desc}")
        self.preview.setText("\n".join(lines))


class XSectionDialog(QDialog):
    """XSECTIONS: every choice of the cross sections on one page -- the
    centreline, the station interval, the design and its template, the
    elevation grid in metres above mean sea level, the volumes."""

    def __init__(self, parent, settings, has_surface: bool) -> None:
        from .xsections import FIT, LEVEL, SLOPE

        super().__init__(parent)
        self.setWindowTitle(tr("Cross sections"))
        self._settings = settings
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        def spin(value, low, high, decimals=2, suffix=""):
            box = QDoubleSpinBox(self)
            box.setRange(low, high)
            box.setDecimals(decimals)
            box.setValue(value)
            if suffix:
                box.setSuffix(suffix)
            return box

        self.axis = QComboBox(self)
        self.axis.addItem(tr("Centreline found from the points"), False)
        self.axis.addItem(tr("Pick a polyline drawn as centreline"), True)
        self.axis.setCurrentIndex(1 if settings.pick_axis else 0)
        form.addRow(tr("Centreline:"), self.axis)

        self.interval = spin(settings.interval, 0.1, 100000.0, 2, " m")
        form.addRow(tr("Station every:"), self.interval)
        self.start_ch = spin(settings.start_chainage, 0.0, 10000000.0, 3, " m")
        form.addRow(tr("First station chainage:"), self.start_ch)
        self.half = spin(settings.half_width, 0.0, 100000.0, 2, " m")
        self.half.setSpecialValueText(tr("Auto (as far as the points reach)"))
        form.addRow(tr("Width each side of the centreline:"), self.half)

        self.mode = QComboBox(self)
        self.mode.addItem(tr("Best-fit grade line through the ground"), FIT)
        self.mode.addItem(tr("Constant level (MSL)"), LEVEL)
        self.mode.addItem(tr("Start level and slope"), SLOPE)
        self.mode.setCurrentIndex([FIT, LEVEL, SLOPE].index(settings.design.mode))
        form.addRow(tr("Design level:"), self.mode)
        self.level = spin(settings.design.level, -10000.0, 100000.0, 3, " m")
        form.addRow(tr("Level (MSL):"), self.level)
        self.slope = spin(settings.design.slope, -100.0, 100.0, 3, " %")
        form.addRow(tr("Slope:"), self.slope)
        self.offset = spin(settings.design.offset, -1000.0, 1000.0, 3, " m")
        form.addRow(tr("Raise (+) / lower (-) the fitted line:"), self.offset)

        self.width = spin(settings.template.width, 0.0, 1000.0, 2, " m")
        form.addRow(tr("Formation width:"), self.width)
        self.cut = spin(settings.template.cut_hv, 0.01, 100.0, 2)
        form.addRow(tr("Cut slope H:V (1:x):"), self.cut)
        self.fill = spin(settings.template.fill_hv, 0.01, 100.0, 2)
        form.addRow(tr("Fill slope H:V (1:x):"), self.fill)

        self.method = QComboBox(self)
        self.method.addItem(tr("Average end areas"), "end-area")
        self.method.addItem(tr("Prismoidal"), "prismoidal")
        self.method.setCurrentIndex(0 if settings.method == "end-area" else 1)
        form.addRow(tr("Volume method:"), self.method)

        self.grid = spin(settings.grid, 0.01, 1000.0, 2, " m")
        form.addRow(tr("Elevation grid (MSL) every:"), self.grid)
        self.vscale = spin(settings.vscale, 0.1, 100.0, 2)
        form.addRow(tr("Vertical exaggeration:"), self.vscale)
        self.height = spin(settings.text_height, 0.0, 1000.0, 2)
        self.height.setSpecialValueText(tr("Auto"))
        form.addRow(tr("Text height:"), self.height)
        self.columns = QSpinBox(self)
        self.columns.setRange(1, 50)
        self.columns.setValue(settings.columns)
        form.addRow(tr("Sections per row:"), self.columns)

        self.contours = spin(settings.contour_interval, 0.0, 1000.0, 2, " m")
        self.contours.setSpecialValueText(tr("None"))
        form.addRow(tr("Contours on the plan every:"), self.contours)
        self.table = QCheckBox(tr("Earthworks table beside the sections"), self)
        self.table.setChecked(settings.table)
        form.addRow("", self.table)
        self.max_edge = spin(settings.max_edge, 0.0, 100000.0, 2, " m")
        self.max_edge.setSpecialValueText(tr("None"))
        self.max_edge.setEnabled(not has_surface)
        form.addRow(tr("Longest triangle edge (new surface):"), self.max_edge)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.mode.currentIndexChanged.connect(lambda _i: self._refresh())
        self._refresh()

    def _refresh(self) -> None:
        from .xsections import FIT, SLOPE

        mode = self.mode.currentData()
        self.level.setEnabled(mode != FIT)
        self.slope.setEnabled(mode == SLOPE)
        self.offset.setEnabled(mode == FIT)

    def settings(self):
        s = self._settings
        s.pick_axis = bool(self.axis.currentData())
        s.interval = float(self.interval.value())
        s.start_chainage = float(self.start_ch.value())
        s.half_width = float(self.half.value())
        s.design.mode = str(self.mode.currentData())
        s.design.level = float(self.level.value())
        s.design.slope = float(self.slope.value())
        s.design.offset = float(self.offset.value())
        s.template.width = float(self.width.value())
        s.template.cut_hv = float(self.cut.value())
        s.template.fill_hv = float(self.fill.value())
        s.method = str(self.method.currentData())
        s.grid = float(self.grid.value())
        s.vscale = float(self.vscale.value())
        s.text_height = float(self.height.value())
        s.columns = int(self.columns.value())
        s.contour_interval = float(self.contours.value())
        s.table = self.table.isChecked()
        s.max_edge = float(self.max_edge.value())
        return s
