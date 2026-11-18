# -*- coding: utf-8 -*-
"""Structural plan per level (2D) and a 3D model of the frame, as DXF.

The 3D model draws every column, beam and slab as a box mesh, so AutoCAD
(3D Orbit) or any DXF viewer shows the frame the design was run on.
"""
from __future__ import annotations

import ezdxf

from .design import DesignResult

COLOURS = {"S-COLUMN": 1, "S-BEAM": 5, "S-SLAB": 8, "S-FOOTING": 30, "S-TEXT": 7, "S-GRID": 9}


def _box(msp, x0, y0, z0, x1, y1, z1, layer):
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mesh = msp.add_mesh(dxfattribs={"layer": layer})
    with mesh.edit_data() as data:
        data.vertices = v
        data.faces = faces


def write_dxf(res: DesignResult, path: str) -> None:
    b = res.building
    doc = ezdxf.new("R2007", setup=True)
    doc.units = ezdxf.units.M
    for name, color in COLOURS.items():
        doc.layers.add(name, color=color)
    msp = doc.modelspace()
    xs, ys = b.xs, b.ys
    width = xs[-1] + 6.0                         # plans side by side in X
    cols = {c.node: c for c in res.columns}
    # 2D plans, one per level, placed left to right; 3D model above them.
    for k, lv in enumerate(b.levels):
        ox = k * width
        msp.add_text(f"แปลนโครงสร้าง {lv.name} (+{lv.elevation:.2f})", height=0.35,
                     dxfattribs={"layer": "S-TEXT"}).set_placement((ox, ys[-1] + 2.0))
        for i, x in enumerate(xs):
            msp.add_line((ox + x, -1.0), (ox + x, ys[-1] + 1.0), dxfattribs={"layer": "S-GRID"})
            msp.add_text(b.x_name(i), height=0.25, dxfattribs={"layer": "S-GRID"}).set_placement(
                (ox + x, ys[-1] + 1.2))
        for j, y in enumerate(ys):
            msp.add_line((ox - 1.0, y), (ox + xs[-1] + 1.0, y), dxfattribs={"layer": "S-GRID"})
            msp.add_text(b.y_name(j), height=0.25, dxfattribs={"layer": "S-GRID"}).set_placement(
                (ox - 1.5, y))
        from .stairs import tread_lines
        for st in res.stairs:
            if st.geom is None or lv.name not in (st.level, b.levels[st.geom.li1].name):
                continue
            for (pa, pc) in tread_lines(b, st.geom):
                msp.add_line((ox + pa[0], pa[1]), (ox + pc[0], pc[1]), dxfattribs={"layer": "S-STAIR"})
            cx, cy = (b.xs[st.geom.i] + b.xs[st.geom.i + 1]) / 2, (b.ys[st.geom.j] + b.ys[st.geom.j + 1]) / 2
            msp.add_text(f"{st.mark} t={st.thickness:.2f} {st.bars_main}", height=0.15,
                         dxfattribs={"layer": "S-TEXT"}).set_placement((ox + cx, cy))
        for x in (bm for bm in res.beams if bm.level == lv.name):
            x0, y0, x1, y1 = x.line_xy
            pa, pc = (x0, y0), (x1, y1)
            msp.add_line((ox + pa[0], pa[1]), (ox + pc[0], pc[1]), dxfattribs={"layer": "S-BEAM"})
            mid = (ox + (pa[0] + pc[0]) / 2, (pa[1] + pc[1]) / 2 + 0.15)
            msp.add_text(f"{x.mark} {x.b:.2f}x{x.h:.2f}", height=0.15,
                         dxfattribs={"layer": "S-TEXT"}).set_placement(mid)
        for (i, j) in b.nodes():
            n = b.node_name(i, j)
            seg = next((c for c in res.columns if c.node == n and c.segment.endswith(lv.name)), cols.get(n))
            if seg is None:
                continue
            x, y = xs[i], ys[j]
            msp.add_lwpolyline([(ox + x - seg.b / 2, y - seg.h / 2), (ox + x + seg.b / 2, y - seg.h / 2),
                                (ox + x + seg.b / 2, y + seg.h / 2), (ox + x - seg.b / 2, y + seg.h / 2)],
                               close=True, dxfattribs={"layer": "S-COLUMN"})
            msp.add_text(seg.mark, height=0.15, dxfattribs={"layer": "S-TEXT"}).set_placement(
                (ox + x + 0.15, y + 0.15))
        for s in (s for s in res.slabs if s.level == lv.name):
            x0, y0, x1, y1 = s.rect
            if s.kind == "cantilever":
                msp.add_lwpolyline([(ox + x0, y0), (ox + x1, y0), (ox + x1, y1), (ox + x0, y1)], close=True,
                                   dxfattribs={"layer": "S-SLAB"})
            msp.add_text(s.mark, height=0.2, dxfattribs={"layer": "S-TEXT"}).set_placement(
                (ox + (x0 + x1) / 2, (y0 + y1) / 2))
    # 3D model, offset above the plans in Y.
    oy = ys[-1] + 6.0
    elev = [lv.elevation for lv in b.levels]
    df = b.foundation.depth
    for f in res.footings:
        i, j = _node_ij(b, f.node)
        x, y = xs[i], ys[j] + oy
        _box(msp, x - f.width / 2, y - f.length / 2, -df, x + f.width / 2, y + f.length / 2,
             -df + f.thickness, "S-FOOTING")
    for c in res.columns:
        i, j = _node_ij(b, c.node)
        x, y = xs[i], ys[j] + oy
        top = next(lv.elevation for lv in b.levels if c.segment.endswith(lv.name))
        _box(msp, x - c.b / 2, y - c.h / 2, top - c.height, x + c.b / 2, y + c.h / 2, top, "S-COLUMN")
    for x in res.beams:
        lv = next(l for l in b.levels if l.name == x.level)
        z = x.z_top if x.z_top is not None else lv.elevation
        x0, y0, x1, y1 = x.line_xy
        x0, x1, y0, y1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
        hw = x.b / 2
        if abs(y1 - y0) < 1e-9:
            _box(msp, x0, y0 - hw + oy, z - x.h, x1, y0 + hw + oy, z, "S-BEAM")
        else:
            _box(msp, x0 - hw, y0 + oy, z - x.h, x0 + hw, y1 + oy, z, "S-BEAM")
    from .stairs import flight_surfaces
    for st in res.stairs:
        if st.geom is None:
            continue
        for quad in flight_surfaces(b, st.geom, st.kind):
            msp.add_3dface([(x, y + oy, z) for x, y, z in quad], dxfattribs={"layer": "S-STAIR"})
    for s in res.slabs:
        lv = next(l for l in b.levels if l.name == s.level)
        x0, y0, x1, y1 = s.rect
        _box(msp, x0, y0 + oy, lv.elevation - s.thickness, x1, y1 + oy, lv.elevation, "S-SLAB")
    _ = elev
    doc.saveas(path)


def _node_ij(b, name: str):
    i = int("".join(ch for ch in name if ch.isdigit())) - 1
    j = ord("".join(ch for ch in name if ch.isalpha())) - ord("A")
    return i, j


def _node_xy(b, name: str):
    i, j = _node_ij(b, name)
    return b.xs[i], b.ys[j]


def _panel_ij(b, panel: str):
    xpart, ypart = panel.split("/")
    i0, i1 = (int(v) - 1 for v in xpart.split("-"))
    j0, j1 = (ord(v) - ord("A") for v in ypart.split("-"))
    return (i0, i1), (j0, j1)


def _panel_centre(b, panel: str):
    (i0, i1), (j0, j1) = _panel_ij(b, panel)
    return (b.xs[i0] + b.xs[i1]) / 2, (b.ys[j0] + b.ys[j1]) / 2
