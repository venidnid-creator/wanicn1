# -*- coding: utf-8 -*-
"""Bar areas, bar choice and the steel section tables."""
from __future__ import annotations

import json
import math
import os

from ..rates import DATA_DIR

#: Nominal bar diameter, cm.
BAR_DIA = {"RB6": 0.6, "RB9": 0.9, "RB12": 1.2, "DB10": 1.0, "DB12": 1.2, "DB16": 1.6,
           "DB20": 2.0, "DB25": 2.5, "DB28": 2.8, "DB32": 3.2}


def bar_area(bar: str) -> float:
    """Area of one bar, cm²."""
    d = BAR_DIA[bar]
    return math.pi * d * d / 4


def pick_bars(as_req: float, width_cm: float, sizes=("DB12", "DB16", "DB20", "DB25"),
              min_count: int = 2, cover_cm: float = 4.0, gap_cm: float = 2.5):
    """Fewest bars in one layer meeting ``as_req``: (count, size).
    Falls back to two layers of the largest size if one layer will not do."""
    for size in sizes:
        n = max(min_count, math.ceil(as_req / bar_area(size) - 1e-9))
        fit = int((width_cm - 2 * cover_cm + gap_cm) // (BAR_DIA[size] + gap_cm))
        if n <= max(fit, min_count):
            return n, size
    size = sizes[-1]
    return max(min_count, math.ceil(as_req / bar_area(size))), size


def pick_spacing(as_req_per_m: float, bar: str, max_cm: float, step_cm: float = 2.5) -> float:
    """Bar spacing (m) giving ``as_req_per_m`` cm²/m, rounded down to the step."""
    if as_req_per_m <= 0:
        s = max_cm
    else:
        s = min(max_cm, bar_area(bar) * 100 / as_req_per_m)
    s = math.floor(s / step_cm + 1e-9) * step_cm
    return max(step_cm * 2, s) / 100


def load_c_sections() -> list[dict]:
    with open(os.path.join(DATA_DIR, "steel_sections.json"), encoding="utf-8") as f:
        return json.load(f)["c_sections"]


def load_piles() -> dict:
    with open(os.path.join(DATA_DIR, "piles.json"), encoding="utf-8") as f:
        return json.load(f)["piles"]
