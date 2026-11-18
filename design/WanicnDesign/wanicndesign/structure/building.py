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
#: Live load by use, kg/m² — กฎกระทรวง ฉบับที่ 6 ข้อ 15 (see standards.py).
from ..standards import LIVE_LOAD  # noqa: E402,F401


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
    sub_beams: list = field(default_factory=list)    # ["1-2/A-B:x@0.5"] secondary beam in a panel
    cantilevers: list = field(default_factory=list)  # ["1A-2A@1.50"] cantilever slab off an edge beam


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
    skip_beams: list = field(default_factory=list)  # e.g. ["FL2:1A-2A"] — no beam on that level
    skip_panels: list = field(default_factory=list)  # e.g. ["FL2:1-2/A-B"] — opening, no slab
    roof: Roof = field(default_factory=Roof)
    foundation: Foundation = field(default_factory=Foundation)
    fc_prime: float = 210.0
    design_code: str = "EIT1007"   # "EIT1007" (วสท. 1007-34) or "MR6" (กฎกระทรวง ฉบับที่ 6)
    occupancy: str = "house"       # standards.LIVE_LOADS key
    ll_reduction: bool = True      # กฎกระทรวง ฉบับที่ 6 ข้อ 16, columns and footings

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
    def beam_key(self, level: str, a, c) -> str:
        a, c = sorted([a, c], key=lambda n: (n[1], n[0]))
        return f"{level}:{self.node_name(*a)}-{self.node_name(*c)}"

    def has_beam(self, level, a, c) -> bool:
        if not (self.has_node(*a) and self.has_node(*c)):
            return False
        return level is None or self.beam_key(level, a, c) not in set(self.skip_beams)

    def beam_lines(self, level: str | None = None):
        """Every beam line on ``level`` as a list of consecutive nodes:
        X-direction lines (along each Y gridline) then Y-direction lines.
        A missing column or a removed beam breaks the line."""
        lines = []
        nx, ny = len(self.xs), len(self.ys)
        for direction, outer, inner in (("x", ny, nx), ("y", nx, ny)):
            for o in range(outer):
                run = []
                for k in range(inner):
                    node = (k, o) if direction == "x" else (o, k)
                    if not self.has_node(*node):
                        if len(run) > 1:
                            lines.append((direction, run))
                        run = []
                        continue
                    if run and not self.has_beam(level, run[-1], node):
                        if len(run) > 1:
                            lines.append((direction, run))
                        run = []
                    run.append(node)
                if len(run) > 1:
                    lines.append((direction, run))
        return lines

    def panel_key(self, level: str, i: int, j: int) -> str:
        return f"{level}:{self.x_name(i)}-{self.x_name(i + 1)}/{self.y_name(j)}-{self.y_name(j + 1)}"

    def panels(self, level: str | None = None):
        """Slab panels: grid bays whose four corners have columns and, on a
        given level, whose four edge beams exist and which are not removed."""
        out = []
        skip = set(self.skip_panels)
        for j in range(len(self.ys) - 1):
            for i in range(len(self.xs) - 1):
                c = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
                if not all(self.has_node(*n) for n in c):
                    continue
                if level is not None:
                    if self.panel_key(level, i, j) in skip:
                        continue
                    if not all(self.has_beam(level, c[k], c[(k + 1) % 4]) for k in range(4)):
                        continue
                out.append((i, j))
        return out

    def is_perimeter(self, a, b, level: str | None = None) -> bool:
        """True when the beam segment a–b has slab on fewer than two sides."""
        (i1, j1), (i2, j2) = a, b
        panels = set(self.panels(level))
        if j1 == j2:   # along X
            i = min(i1, i2)
            sides = [(i, j1 - 1), (i, j1)]
        else:
            j = min(j1, j2)
            sides = [(i1 - 1, j), (i1, j)]
        return sum(1 for p in sides if p in panels) < 2

    # -- secondary beams and cantilever slabs ----------------------------------
    def level(self, name: str) -> Level | None:
        return next((lv for lv in self.levels if lv.name == name), None)

    def parse_node(self, name: str) -> tuple[int, int]:
        digits = "".join(ch for ch in name if ch.isdigit())
        letters = "".join(ch for ch in name if ch.isalpha())
        return int(digits) - 1, ord(letters.upper()) - ord("A")

    def panel_name(self, i: int, j: int) -> str:
        return f"{self.x_name(i)}-{self.x_name(i + 1)}/{self.y_name(j)}-{self.y_name(j + 1)}"

    def sub_beam(self, level: Level, i: int, j: int):
        """``(direction, fraction)`` of the secondary beam in panel (i, j):
        ``"x"`` runs parallel to X at ``fraction`` of the bay depth in Y."""
        name = self.panel_name(i, j)
        for entry in level.sub_beams:
            panel, _, rest = entry.partition(":")
            if panel == name:
                d, _, frac = rest.partition("@")
                return d, float(frac or 0.5)
        return None

    def toggle_sub_beam(self, level: Level, i: int, j: int, direction: str, fraction: float = 0.5):
        name = self.panel_name(i, j)
        level.sub_beams[:] = [e for e in level.sub_beams if not e.startswith(name + ":")]
        if direction:
            level.sub_beams.append(f"{name}:{direction}@{fraction:g}")

    def cantilevers(self, level: Level):
        """``(a, c, length, outward)`` per cantilever slab; ``outward`` is the
        unit direction (dx, dy) away from the building."""
        out = []
        panels = set(self.panels(level.name))
        for entry in level.cantilevers:
            seg, _, length = entry.partition("@")
            na, nc = seg.split("-")
            a, c = self.parse_node(na), self.parse_node(nc)
            if not self.has_beam(level.name, a, c):
                continue
            if a[1] == c[1]:                       # along X
                i, j = min(a[0], c[0]), a[1]
                outward = (0, -1) if (i, j) in panels else (0, 1)
            else:
                i, j = a[0], min(a[1], c[1])
                outward = (-1, 0) if (i, j) in panels else (1, 0)
            out.append((a, c, float(length or 1.0), outward))
        return out

    def toggle_cantilever(self, level: Level, a, c, length: float | None):
        key = self.beam_key(level.name, a, c).split(":", 1)[1]
        level.cantilevers[:] = [e for e in level.cantilevers if not e.startswith(key + "@")]
        if length:
            level.cantilevers.append(f"{key}@{length:.2f}")

    def toggle(self, kind: str, key: str) -> bool:
        """Remove or restore one element; returns True when it now exists."""
        lst = {"node": self.skip_nodes, "beam": self.skip_beams, "panel": self.skip_panels}[kind]
        if key in lst:
            lst.remove(key)
            return True
        lst.append(key)
        return False

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
            skip_beams=list(d.get("skip_beams", [])),
            skip_panels=list(d.get("skip_panels", [])),
            roof=Roof(**d.get("roof", {})),
            foundation=Foundation(**d.get("foundation", {})),
            fc_prime=d.get("fc_prime", 210.0),
            design_code=d.get("design_code", "EIT1007"),
            occupancy=d.get("occupancy", "house"),
            ll_reduction=d.get("ll_reduction", True),
        )

    @classmethod
    def load(cls, path: str) -> "Building":
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=1)
