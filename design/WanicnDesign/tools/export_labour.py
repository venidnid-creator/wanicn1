# -*- coding: utf-8 -*-
"""Export the ว480 (2569) labour table and the 2569 measuring constants
from the WANICNSURVEY 3D core into WanicnDesign's data folder.

The 3D core (3d/core/wanic_std2569.py) is the one place the official rates
are kept and cited. WanicnDesign reads a JSON copy so it runs on its own,
and a user can update a rate by editing the JSON without touching code.

Run from the repository root:
    python design/WanicnDesign/tools/export_labour.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "3d"))

from core import wanic_std2569 as S  # noqa: E402

OUT = os.path.join(HERE, "..", "data", "labour_2569.json")


def main():
    data = {
        "source": S.LABOUR_SOURCE,
        "note": "ค่าแรงต่อหน่วย (บาท) แก้ไขค่า rate ได้โดยตรงเพื่ออัปเดตค่าแรง",
        "labour": {code: {"name": n, "unit": u, "rate": r, "condition": c}
                   for code, (n, u, r, c) in S.LABOUR.items()},
        "rebar_kg_m": S.REBAR_KG_M,
        "rebar_waste_pct": S.REBAR_WASTE,
        "tie_wire_kg_per_tonne": S.TIE_WIRE_PER_TONNE,
        "excavation_waste_pct": S.EXCAVATION_WASTE,
        "excavation_deep_m": S.EXCAVATION_DEEP,
        "excavation_side_m": S.EXCAVATION_SIDE,
        "bedding_waste_pct": S.BEDDING_WASTE,
        "roofing_waste_pct": S.ROOFING_WASTE,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"wrote {len(data['labour'])} labour items to {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
