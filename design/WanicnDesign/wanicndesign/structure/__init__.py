# -*- coding: utf-8 -*-
"""Structural design from the building model, roof down to the piles.

Order of the chain (each step passes its loads to the next):
    roof (purlin, rafter) → slabs → beams (continuous) → columns
    (accumulated floor by floor) → footings → piles

Method: working stress design (WSD) as in the วสท. (EIT) standard the
QuickDesign manual follows — fc = 0.45 fc', n = Es/Ec, two-way slab
coefficients (case 5), column P = 0.85 Ag (0.25 fc' + fs pg).
Every result must be checked and signed by a licensed engineer.
"""
