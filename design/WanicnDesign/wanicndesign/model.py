# -*- coding: utf-8 -*-
"""The building as WanicnDesign keeps it: floors, structure, walls, openings
and roof. Saved as JSON in the project folder (the role QuickDesign gives
to DrawExcel.xls). Units are metres unless a field says otherwise.

Wall finishing codes follow the QuickDesign workflow:
    mortar  M0 = no plaster, M1 = one side, M2 = both sides
    paint   P0 = interior both sides, P1 = exterior one side + interior one,
            P2 = exterior both sides
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field


@dataclass
class Floor:
    name: str            # "FL0" (ground), "FL1", ..., "ROOF"
    level: float         # elevation, m


@dataclass
class Footing:
    name: str
    count: int
    width: float
    length: float
    thickness: float
    depth: float                 # ground to underside of footing
    bars: str = "DB12@0.15"      # both ways
    piles: int = 0               # piles per footing (0 = spread footing)
    pile_type: str = ""          # e.g. "I-Pile 22x16 m."


@dataclass
class Column:
    name: str
    count: int
    width: float
    depth: float
    height: float
    main_bars: str = "4-DB12"
    stirrup: str = "RB6@0.20"


@dataclass
class Beam:
    name: str
    floor: str
    width: float
    depth: float
    length: float                # clear length, support to support
    count: int = 1
    top_bars: str = "2-DB12"
    bottom_bars: str = "2-DB12"
    stirrup: str = "RB6@0.15"


@dataclass
class Slab:
    name: str
    floor: str
    area: float
    thickness: float = 0.10
    bars: str = "RB9@0.20"       # both ways
    on_ground: bool = False
    short_span: float = 0.0      # for the bar count; 0 = sqrt(area)


@dataclass
class Opening:
    kind: str                    # "door" or "window"
    name: str
    width: float
    height: float
    count: int = 1
    material: str = "wood"       # "wood", "aluminium"


@dataclass
class Wall:
    name: str
    floor: str
    length: float                # centre to centre of columns
    height: float                # floor to floor
    column_width: float = 0.20
    beam_depth: float = 0.50
    wall_type: str = "brick"     # brick, qcon, gypsum, concrete, metal
    mortar: str = "M2"
    paint: str = "P0"
    openings: list = field(default_factory=list)   # opening names in ONE span; repeat a name for two
    count: int = 1               # identical spans


@dataclass
class Roof:
    plan_area: float             # horizontal area, m²
    slope_deg: float = 30.0
    shape: str = "hip"           # gable, shed, hip
    material: str = "concrete_tile"   # concrete_tile, metal_sheet, ceramic_tile
    ridge_length: float = 0.0
    hip_length: float = 0.0
    valley_length: float = 0.0
    eave_length: float = 0.0     # roof circumference
    steel_kg: float = 0.0        # roof steel frame, kg


@dataclass
class Finish:
    """Floor finish, ceiling or wall tiles of an area (stage 7)."""
    name: str
    floor: str
    kind: str                    # "floor:<key>", "ceiling:<key>", "wall_tile"
    area: float


@dataclass
class Fixture:
    name: str                    # architecture.FIXTURES key
    count: int
    room: str = ""


@dataclass
class Project:
    name: str
    floors: list = field(default_factory=list)
    grid_x: list = field(default_factory=list)   # spacings A-B, B-C, ... (m)
    grid_y: list = field(default_factory=list)   # spacings 1-2, 2-3, ... (m)
    footings: list = field(default_factory=list)
    columns: list = field(default_factory=list)
    beams: list = field(default_factory=list)
    slabs: list = field(default_factory=list)
    walls: list = field(default_factory=list)
    openings: list = field(default_factory=list)
    roof: Roof | None = None
    finishes: list = field(default_factory=list)
    fixtures: list = field(default_factory=list)

    @property
    def storeys(self) -> int:
        return max(1, len([f for f in self.floors if f.name not in ("FL0", "ROOF")]))

    def opening(self, name: str) -> Opening | None:
        for o in self.openings:
            if o.name == name:
                return o
        return None

    # -- JSON -------------------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        return cls(
            name=d["name"],
            floors=[Floor(**x) for x in d.get("floors", [])],
            grid_x=list(d.get("grid_x", [])),
            grid_y=list(d.get("grid_y", [])),
            footings=[Footing(**x) for x in d.get("footings", [])],
            columns=[Column(**x) for x in d.get("columns", [])],
            beams=[Beam(**x) for x in d.get("beams", [])],
            slabs=[Slab(**x) for x in d.get("slabs", [])],
            walls=[Wall(**x) for x in d.get("walls", [])],
            openings=[Opening(**x) for x in d.get("openings", [])],
            roof=Roof(**d["roof"]) if d.get("roof") else None,
            finishes=[Finish(**x) for x in d.get("finishes", [])],
            fixtures=[Fixture(**x) for x in d.get("fixtures", [])],
        )

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=1)

    @classmethod
    def load(cls, path: str) -> "Project":
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))
