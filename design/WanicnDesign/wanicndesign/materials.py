# -*- coding: utf-8 -*-
"""Material cost of each BOQ line from the 2569 unit-material recipes and a
province price book.

A BOQ line names its materials as ``(ref, qty)`` pairs per one BOQ unit:

* ``"R:6.1"`` — a recipe of «วัสดุมวลรวมของงานก่อสร้างอาคาร» (กรมบัญชีกลาง
  2569, pp. 104–170), waste already included [CGD2569-MAT];
* ``"FORM"`` — formwork per m²: ไม้อัด 0.133 แผ่น + ไม้ยาง 0.774 ลบ.ฟ. +
  ตะปู 0.25 กก. (หลักเกณฑ์ 4.1 ข้อ 3.1.1) [CGD2569];
* anything else — a key of the price book, priced per its unit.

Prices are the user's: the province book saved by :mod:`.province` (the
same folder the WANICNSURVEY 3D program uses), or typed in. Nothing is
invented: a material without a price is reported as missing.
"""
from __future__ import annotations

import json
import os

from .rates import DATA_DIR

MATERIALS_FILE = os.path.join(DATA_DIR, "materials_2569.json")

with open(MATERIALS_FILE, encoding="utf-8") as _f:
    _DATA = json.load(_f)

SOURCE: str = _DATA["source"]
RECIPES: dict = {r["code"]: r for r in _DATA["recipes"]}
PRICE_UNITS: dict = {k: u for k, u in _DATA["price_keys"]}
FORMWORK = [(n, q, u) for n, q, u in _DATA["formwork_recipe"]]

#: Ready-mixed concrete key (the 3D program's name for the same material).
READY_MIX = "คอนกรีตผสมเสร็จ 240 กก./ตร.ซม. (ลูกบาศก์)"

#: A line with labour only (excavation, backfill with the dug soil): no material at all.
LABOUR_ONLY = (("", 0.0),)

#: Recipe item names that are a price-book key under another name.
ALIASES = {"เหล็กเสริม RB Ø 6 มม.": "RB6", "เหล็กเสริม RB Ø 9 มม.": "RB9", "ตะปู": "ตะปูตอกไม้ 3\""}

for _n, _q, _u in FORMWORK:
    PRICE_UNITS.setdefault(_n, _u)


def recipe(code: str) -> dict | None:
    return RECIPES.get(code)


def _price(name: str, prices: dict):
    v = prices.get(name)
    if not v and name in ALIASES:
        v = prices.get(ALIASES[name])
    return float(v) if v else None


def formwork_cost(prices: dict) -> tuple[float, list[str]]:
    total, missing = 0.0, []
    for n, q, _u in FORMWORK:
        p = _price(n, prices)
        if p is None:
            missing.append(n)
        else:
            total += q * p
    return total, missing


def recipe_cost(code: str, prices: dict) -> tuple[float, list[str]]:
    """Material cost of one unit of the recipe and the items with no price."""
    rc = RECIPES.get(code)
    if rc is None:
        return 0.0, [f"สูตร {code}"]
    total, missing = 0.0, []
    for it in rc["items"]:
        if it.get("qty") is None:                    # left to the maker's coverage
            missing.append(it["name"])
            continue
        if "price" in it:                            # water: priced in the source
            total += it["qty"] * float(it["price"])
            continue
        if it["name"].startswith("ไม้แบบ") and it["unit"] == "ตร.ม.":
            p, miss = formwork_cost(prices)
            total += it["qty"] * p
            missing += miss
            continue
        p = _price(it["name"], prices)
        if p is None:
            missing.append(it["name"])
        else:
            total += it["qty"] * p
    return total, missing


def material_rate(materials, prices: dict, fallback: str = "") -> tuple[float, list[str]]:
    """Baht per BOQ unit of a line's ``materials``; with none, the price of
    ``fallback`` (the line's own name) if the user typed one."""
    if not materials:
        p = _price(fallback, prices) if fallback else None
        return (p or 0.0), []
    total, missing = 0.0, []
    for ref, qty in materials:
        if not ref:
            continue
        if ref == "FORM":
            p, miss = formwork_cost(prices)
        elif ref.startswith("R:"):
            p, miss = recipe_cost(ref[2:], prices)
        else:
            v = _price(ref, prices)
            p, miss = (v or 0.0), ([] if v is not None else [ref])
        total += qty * p
        missing += miss
    return total, list(dict.fromkeys(missing))


def needed(materials) -> dict:
    """``{material name: unit}`` a line needs priced (for the province import)."""
    out = {}
    for ref, _q in materials or ():
        if not ref:
            continue
        if ref == "FORM":
            out.update({n: u for n, _q2, u in FORMWORK})
        elif ref.startswith("R:"):
            rc = RECIPES.get(ref[2:]) or {"items": []}
            for it in rc["items"]:
                if "price" in it or it.get("qty") is None:
                    continue
                if it["name"].startswith("ไม้แบบ") and it["unit"] == "ตร.ม.":
                    out.update({n: u for n, _q2, u in FORMWORK})
                    continue
                name = ALIASES.get(it["name"], it["name"])
                out[name] = PRICE_UNITS.get(name, it["unit"])
        else:
            out[ref] = PRICE_UNITS.get(ref, "")
    return out
