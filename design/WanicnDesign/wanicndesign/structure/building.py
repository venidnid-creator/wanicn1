# -*- coding: utf-8 -*-
"""The building model: grid, levels and the elements placed on them.

The model is built first (grid → levels → auto-generated columns, beams,
slab panels and footings, as in the SM-3D-STRUCTURE workflow) and the
structural design runs on it afterwards.

Coordinates: grid lines in X are named 1, 2, 3 …; in Y A, B, C …
A node is ``(i, j)``: X line i, Y line j. Lengths in metres, loads in kg.
"""
from __future__ import annotations

import json
import string
from dataclasses import asdict, dataclass, field

#: Wall dead load, kg/m² of wall (QuickDesign appendix / Draw Wall menu).
WALL_LOAD = {"brick": 180, "qcon": 90, "gypsum": 40, "concrete": 240, "metal": 0}
#: Roof covering dead load, kg/m² of roof slope (QuickDesign appendix).
ROOF_COVER_LOAD = {"concrete_tile": 50, "ceramic_tile": 50, "asbestos": 30, "metal_sheet": 20}
#: Live load by building type, kg/m² (QuickDesign Draft ▸ Live Load).
LIVE_LOAD = {"house": 150, "condominium": 200, "office": 250, "plaza": 300, "school": 300,
             "factory": 500}


@dataclass
class Level:
    name: str                      # "GB" (ground beams), "FL2", "ROOF"
    elevation: float               # m, ±0.00 = ground beam top
    slab: str = "suspended"        # "suspended", "on_ground", "none", "roof"
    slab_thickness: float = 0.10
    live_load: float = 150.0       # kg/m²
    finish_load: float = 50.0      # topping / finishes, kg/m²
    beam_width: float = 0.20
    beam_depth: float = 0.40
    beam_mark: str = "B"           # mark prefix: GB, B, RB
    walls: str = "perimeter"       # "perimeter", "all", "none" — walls standing on this level
    wall_type: str = "brick"


@dataclass
class Roof:
    shape: str = "hip"             # hip, gable
    cover: str = "concrete_tile"
    slope_deg: float = 30.0
    overhang: float = 1.0          # eave beyond the outer grid, m
    live_load: float = 30.0        # kg/m² plan
    frame_load: float = 15.0       # purlins + rafters, kg/m² slope
    purlin_spacing: float = 0.32   # battens for tiles
    rafter_spacing: float = 1.00


@dataclass
class Foundation:
    depth: float = 1.50            # Df, ground to footing underside
    kind: str = "pile"             # "pile" or "spread"
    pile: str = "I22"
    pile_length: float = 16.0
    soil_qa: float = 15000.0       # kg/m², spread footings only


@dataclass
class Building:
    name: str
    grid_x: list = field(default_factory=list)     # spacings 1-2, 2-3, … (m)
    grid_y: list = field(default_factory=list)     # spacings A-B, B-C, … (m)
    levels: list = field(default_factory=list)     # bottom to top
    column_width: float = 0.20
    column_depth: float = 0.20
    skip_nodes: list = field(default_factory=list)  # e.g. ["4C"] — no column there
    roof: Roof = field(default_factory=Roof)
    foundation: Foundation = field(default_factory=Foundation)
    fc_prime: float = 210.0

    # -- grid ---------------------------------------------------------------
    @property
    def xs(self) -> list[float]:
        out = [0.0]
        for s in self.grid_x:
            out.append(round(out[-1] + float(s), 6))
        return out

    @property
    def ys(self) -> list[float]:
        out = [0.0]
        for s in self.grid_y:
            out.append(round(out[-1] + float(s), 6))
        return out

    @staticmethod
    def x_name(i: int) -> str:
        return str(i + 1)

    @staticmethod
    def y_name(j: int) -> str:
        return string.ascii_uppercase[j]

    def node_name(self, i: int, j: int) -> str:
        return f"{self.x_name(i)}{self.y_name(j)}"

    def nodes(self) -> list[tuple[int, int]]:
        skip = {s.upper() for s in self.skip_nodes}
        return [(i, j) for j in range(len(self.ys)) for i in range(len(self.xs))
                if self.node_name(i, j) not in skip]

    def has_node(self, i: int, j: int) -> bool:
        return 0 <= i < len(self.xs) and 0 <= j < len(self.ys) and \
            self.node_name(i, j) not in {s.upper() for s in self.skip_nodes}

    # -- auto-generated elements -------------------------------------------------
    def beam_lines(self):
        """Every beam line as a list of consecutive nodes: X-direction lines
        (along each Y gridline) then Y-direction lines. A missing node
        breaks the line into separate continuous beams."""
        lines = []
        for j in range(len(self.ys)):
            run = []
            for i in range(len(self.xs)):
                if self.has_node(i, j):
                    run.append((i, j))
                else:
                    if len(run) > 1:
                        lines.append(("x", run))
                    run = []
            if len(run) > 1:
                lines.append(("x", run))
        for i in range(len(self.xs)):
            run = []
            for j in range(len(self.ys)):
                if self.has_node(i, j):
                    run.append((i, j))
                else:
                    if len(run) > 1:
                        lines.append(("y", run))
                    run = []
            if len(run) > 1:
                lines.append(("y", run))
        return lines

    def panels(self):
        """Slab panels: every grid bay whose four corners have columns."""
        out = []
        for j in range(len(self.ys) - 1):
            for i in range(len(self.xs) - 1):
                if all(self.has_node(a, b) for a, b in ((i, j), (i + 1, j), (i, j + 1), (i + 1, j + 1))):
                    out.append((i, j))
        return out

    def is_perimeter(self, a, b) -> bool:
        """True when the beam segment a–b lies on the outer edge of the slab."""
        (i1, j1), (i2, j2) = a, b
        panels = set(self.panels())
        if j1 == j2:   # along X
            i = min(i1, i2)
            sides = [(i, j1 - 1), (i, j1)]
        else:
            j = min(j1, j2)
            sides = [(i1 - 1, j), (i1, j)]
        return sum(1 for p in sides if p in panels) < 2

    def plan_size(self) -> tuple[float, float]:
        return self.xs[-1], self.ys[-1]

    # -- JSON -----------------------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Building":
        return cls(
            name=d["name"],
            grid_x=list(d.get("grid_x", [])),
            grid_y=list(d.get("grid_y", [])),
            levels=[Level(**x) for x in d.get("levels", [])],
            column_width=d.get("column_width", 0.20),
            column_depth=d.get("column_depth", 0.20),
            skip_nodes=list(d.get("skip_nodes", [])),
            roof=Roof(**d.get("roof", {})),
            foundation=Foundation(**d.get("foundation", {})),
            fc_prime=d.get("fc_prime", 210.0),
        )

    @classmethod
    def load(cls, path: str) -> "Building":
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=1)
