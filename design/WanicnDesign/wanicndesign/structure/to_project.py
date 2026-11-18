# -*- coding: utf-8 -*-
"""Turn a designed building into the quantity :class:`~wanicndesign.model.Project`,
so the BOQ uses the sizes and bars the design chose."""
from __future__ import annotations

from collections import Counter

from ..model import Beam, Column, Floor, Footing, Project, Roof, Slab, Wall
from .design import DesignResult

_SHAPE = {"hip": "hip", "gable": "gable"}


def to_project(res: DesignResult) -> Project:
    b = res.building
    p = Project(name=b.name, grid_x=list(b.grid_x), grid_y=list(b.grid_y))
    p.floors = [Floor("FL0", 0.0)] + [Floor(lv.name if lv.slab != "roof" else "ROOF", lv.elevation)
                                      for lv in b.levels]
    for (mark, w, l, t, piles, pile, bx), n in Counter(
            (f.mark, f.width, f.length, f.thickness, f.piles, f.pile, f.bars_x) for f in res.footings).items():
        nb, size = bx.split("-")
        spacing = max(0.10, round((l - 0.15) / max(int(nb) - 1, 1), 2))
        p.footings.append(Footing(mark, n, w, l, t, b.foundation.depth, f"{size}@{spacing}",
                                  piles, f"{pile} ยาว {b.foundation.pile_length:g} ม." if piles else ""))
    for (mark, seg, cw, ch, hgt, bars, ties), n in Counter(
            (c.mark, c.segment, c.b, c.h, round(c.height, 2), c.bars, c.ties) for c in res.columns).items():
        p.columns.append(Column(f"{mark} ({seg})", n, cw, ch, hgt, bars, ties))
    for (lvl, mark, bw, h, length, top, bot, stir, kind), n in Counter(
            (x.level, x.mark, x.b, x.h, round(x.length, 2), x.top, x.bottom, x.stirrup, x.kind)
            for x in res.beams).items():
        # clear length: a cantilever beam leaves one column face, a secondary beam sits between beam faces
        cut = {"cantilever": b.column_width / 2, "secondary": bw}.get(kind, b.column_width)
        clear = round(length - cut, 2)
        p.beams.append(Beam(mark, lvl, bw, h, clear, n, top, bot, stir))
    for s in res.slabs:
        p.slabs.append(Slab(f"{s.mark} {s.panel}", s.level, round(s.lx * s.ly, 3), s.thickness,
                            s.bars_short, s.kind == "on-ground", min(s.lx, s.ly)))
    from .stairs import concrete_volume
    for st in res.stairs:
        vol = concrete_volume(st)
        if vol > 0:
            p.slabs.append(Slab(f"บันได {st.name}", st.level, round(vol / st.thickness, 3), st.thickness,
                                st.bars_main, False, st.width))
    for li, lv in enumerate(b.levels):
        if li + 1 >= len(b.levels) or lv.walls == "none":
            continue
        above = b.levels[li + 1]
        for _d, run in b.beam_lines(lv.name):
            for a, c in zip(run, run[1:]):
                if lv.walls == "all" or b.is_perimeter(a, c, lv.name):
                    length = abs(b.xs[c[0]] - b.xs[a[0]]) + abs(b.ys[c[1]] - b.ys[a[1]])
                    p.walls.append(Wall(f"ผนัง {lv.name} {b.node_name(*a)}-{b.node_name(*c)}", lv.name,
                                        length, above.elevation - lv.elevation, b.column_width,
                                        above.beam_depth, lv.wall_type, "M2",
                                        "P1" if b.is_perimeter(a, c, lv.name) else "P0"))
    if res.roof:
        r = res.roof
        cover = b.roof.cover if b.roof.cover in ("concrete_tile", "metal_sheet", "ceramic_tile") \
            else "concrete_tile"
        p.roof = Roof(round(r.plan_area, 2), b.roof.slope_deg, _SHAPE.get(b.roof.shape, "hip"), cover,
                      round(r.ridge, 2), round(r.hips, 2), 0.0, round(r.eave, 2), round(r.steel_kg, 1))
    return p
