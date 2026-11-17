# -*- coding: utf-8 -*-
"""The drawing interface and the plan drawings built on it."""
from __future__ import annotations

import string

BUBBLE_R = 0.25        # grid bubble radius, m
BUBBLE_GAP = 1.5       # bubble distance outside the grid, m
COLUMN_MARK_R = 0.15   # column draft circle radius, m

LAYERS = {             # name: AutoCAD colour index
    "grid": 8, "griddim": 3, "columncopy": 1, "column": 7, "beam": 5, "text": 7,
}


class Backend:
    """Minimal drawing calls; coordinates in metres (1 unit = 1 m)."""

    def layer(self, name: str, color: int = 7) -> None: ...
    def line(self, p1, p2, layer: str) -> None: ...
    def circle(self, center, radius: float, layer: str) -> None: ...
    def text(self, insert, value: str, height: float, layer: str, center: bool = False) -> None: ...
    def rect(self, x1, y1, x2, y2, layer: str) -> None:
        for a, b in (((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)),
                     ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))):
            self.line(a, b, layer)
    def finish(self) -> None: ...


def grid_names(n: int, letters: bool) -> list[str]:
    if letters:
        abc = string.ascii_uppercase
        return [abc[i] if i < 26 else abc[i // 26 - 1] + abc[i % 26] for i in range(n)]
    return [str(i + 1) for i in range(n)]


def grid_coords(spacings: list[float]) -> list[float]:
    xs = [0.0]
    for s in spacings:
        xs.append(xs[-1] + float(s))
    return xs


def draw_grid(project, b: Backend) -> dict:
    """Gridlines with bubbles, overall and bay dimensions, and a column
    draft circle at every intersection (the QuickDesign "GridDim" step).
    Returns the gridline coordinates by name."""
    for name, color in LAYERS.items():
        b.layer(name, color)
    xs, ys = grid_coords(project.grid_x), grid_coords(project.grid_y)
    nx, ny = grid_names(len(xs), True), grid_names(len(ys), False)
    x0, x1, y0, y1 = xs[0], xs[-1], ys[0], ys[-1]
    ext = BUBBLE_GAP - BUBBLE_R
    for x, n in zip(xs, nx):
        b.line((x, y0 - 0.5), (x, y1 + ext), "grid")
        b.circle((x, y1 + BUBBLE_GAP), BUBBLE_R, "grid")
        b.text((x, y1 + BUBBLE_GAP), n, 0.25, "grid", center=True)
    for y, n in zip(ys, ny):
        b.line((x0 - ext, y), (x1 + 0.5, y), "grid")
        b.circle((x0 - BUBBLE_GAP, y), BUBBLE_R, "grid")
        b.text((x0 - BUBBLE_GAP, y), n, 0.25, "grid", center=True)
    dim_y = y1 + 0.8
    for a, c in zip(xs, xs[1:]):
        b.line((a, dim_y), (c, dim_y), "griddim")
        b.text(((a + c) / 2, dim_y + 0.15), f"{c - a:.2f}", 0.18, "griddim", center=True)
    dim_x = x0 - 0.8
    for a, c in zip(ys, ys[1:]):
        b.line((dim_x, a), (dim_x, c), "griddim")
        b.text((dim_x - 0.3, (a + c) / 2), f"{c - a:.2f}", 0.18, "griddim", center=True)
    for x in xs:
        for y in ys:
            b.circle((x, y), COLUMN_MARK_R, "columncopy")
    return {"x": dict(zip(nx, xs)), "y": dict(zip(ny, ys))}
