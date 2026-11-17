# -*- coding: utf-8 -*-
"""Labour rates (ว480, พ.ศ. 2569) and material prices.

Labour rates come from ``data/labour_2569.json`` (exported from the
WANICNSURVEY 3D core by ``tools/export_labour.py``). A user updates a rate
with :meth:`Rates.set_labour` or by editing that JSON; updates are saved
to a separate override file so the official table stays intact.

Material prices are the user's own (สำนักงานพาณิชย์จังหวัด or a supplier)
and start empty, keyed by the BOQ item name.
"""
from __future__ import annotations

import json
import math
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
LABOUR_FILE = os.path.join(DATA_DIR, "labour_2569.json")


def q2(v: float) -> float:
    """Round half up to 2 decimals, as the price forms print quantities."""
    return math.floor(abs(float(v)) * 100 + 0.5 + 1e-9) / 100 * (1 if v >= 0 else -1)


class Rates:
    """The labour table, the measuring constants and a material price list."""

    def __init__(self, labour_file: str = LABOUR_FILE, override_file: str | None = None,
                 prices: dict | None = None):
        with open(labour_file, encoding="utf-8") as f:
            data = json.load(f)
        self.source = data["source"]
        self.labour = {k: dict(v) for k, v in data["labour"].items()}
        self.rebar_kg_m = data["rebar_kg_m"]
        self.rebar_waste_pct = data["rebar_waste_pct"]
        self.tie_wire_kg_per_tonne = data["tie_wire_kg_per_tonne"]
        self.excavation_waste_pct = data["excavation_waste_pct"]
        self.excavation_deep_m = data["excavation_deep_m"]
        self.excavation_side_m = data["excavation_side_m"]
        self.bedding_waste_pct = data["bedding_waste_pct"]
        self.roofing_waste_pct = data["roofing_waste_pct"]
        self.override_file = override_file
        if override_file and os.path.exists(override_file):
            with open(override_file, encoding="utf-8") as f:
                for code, rate in json.load(f).items():
                    if code in self.labour:
                        self.labour[code]["rate"] = rate
        self.prices = dict(prices or {})

    # -- labour ---------------------------------------------------------
    def labour_rate(self, code: str) -> float:
        item = self.labour.get(code)
        return float(item["rate"]) if item else 0.0

    def set_labour(self, code: str, rate: float, save: bool = True) -> None:
        """Update one labour rate (บาท/หน่วย); saved to the override file."""
        if code not in self.labour:
            raise KeyError(f"ไม่มีรหัสค่าแรง {code}")
        self.labour[code]["rate"] = float(rate)
        if save and self.override_file:
            current = {}
            if os.path.exists(self.override_file):
                with open(self.override_file, encoding="utf-8") as f:
                    current = json.load(f)
            current[code] = float(rate)
            with open(self.override_file, "w", encoding="utf-8") as f:
                json.dump(current, f, ensure_ascii=False, indent=1)

    def scale_labour(self, percent: float) -> None:
        """Raise (or lower) every labour rate by ``percent`` (not saved)."""
        for item in self.labour.values():
            item["rate"] = round(float(item["rate"]) * (1 + percent / 100.0), 2)

    # -- materials ------------------------------------------------------
    def price(self, key: str) -> float:
        return float(self.prices.get(key) or 0.0)

    @staticmethod
    def load_prices(path: str) -> dict:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
