# -*- coding: utf-8 -*-
"""Material constants for working stress design (units: kg, cm, ksc)."""
from __future__ import annotations

import math
from dataclasses import dataclass

ES = 2.04e6            # steel modulus, ksc
CONCRETE_KG_M3 = 2400

#: Allowable tensile stress fs (ksc) by grade — วสท. WSD.
FS = {"SR24": 1200, "SD30": 1500, "SD40": 1700, "SD50": 1700}
FY = {"SR24": 2400, "SD30": 3000, "SD40": 4000, "SD50": 5000}


@dataclass
class Concrete:
    fc_prime: float = 210.0      # cylinder strength, ksc (≈ 240 ksc cube)
    main_grade: str = "SD40"     # deformed bars DB
    tie_grade: str = "SR24"      # round bars RB (stirrups, slab RB9)

    @property
    def fc(self) -> float:
        return 0.45 * self.fc_prime

    @property
    def n(self) -> int:
        ec = 15100 * math.sqrt(self.fc_prime)
        return max(6, round(ES / ec))

    def k(self, fs: float) -> float:
        return 1.0 / (1.0 + fs / (self.n * self.fc))

    def j(self, fs: float) -> float:
        return 1.0 - self.k(fs) / 3.0

    def R(self, fs: float) -> float:
        """Resisting moment coefficient, ksc: M = R b d²."""
        return 0.5 * self.fc * self.k(fs) * self.j(fs)

    def fs(self, bar: str) -> float:
        return FS[self.tie_grade if bar.upper().startswith("RB") else self.main_grade]

    @property
    def vc_beam(self) -> float:
        """Allowable shear on concrete in beams, ksc."""
        return 0.29 * math.sqrt(self.fc_prime)

    @property
    def vc_punch(self) -> float:
        """Allowable punching shear (two-way), ksc."""
        return 0.53 * math.sqrt(self.fc_prime)

    @property
    def fs_column(self) -> float:
        """Steel stress in tied columns: 0.4 fy (≤ 2100 ksc)."""
        return min(0.4 * FY[self.main_grade], 2100.0)
