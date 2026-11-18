# -*- coding: utf-8 -*-
"""Material constants for working stress design (units: kg, cm, ksc)."""
from __future__ import annotations

import math
from dataclasses import dataclass

ES = 2.04e6            # steel modulus, ksc
CONCRETE_KG_M3 = 2400

#: Allowable tensile stress fs (ksc) by grade — วสท. 1007-34 [EIT1007].
FS = {"SR24": 1200, "SD30": 1500, "SD40": 1700, "SD50": 1700}
FY = {"SR24": 2400, "SD30": 3000, "SD40": 4000, "SD50": 5000}

#: Cube (150 mm) to cylinder (150 × 300 mm) strength at 28 days, ksc —
#: ประกาศกระทรวงมหาดไทย พ.ศ. 2567 ข้อ 29 (2) ตาราง 12 [MI2567-29].
CUBE_TO_CYLINDER = [(180, 150), (210, 180), (240, 210), (280, 240), (300, 250), (320, 280), (350, 300),
                    (380, 320), (400, 350), (420, 380), (450, 400), (500, 450), (550, 500)]

#: Limits of ประกาศกระทรวงมหาดไทย พ.ศ. 2567 ข้อ 29 (4)–(5) when the drawings do not state a
#: construction standard and quality control.
FC_WSD_CAP = 65.0        # allowable concrete stress, ksc
FC_USD_CAP = 150.0       # specified strength usable in strength design, ksc


def cube_to_cylinder(cube: float) -> float:
    """Cylinder strength for a cube strength, by table 12 (linear between rows)."""
    t = CUBE_TO_CYLINDER
    if cube <= t[0][0]:
        return cube * t[0][1] / t[0][0]
    for (c0, y0), (c1, y1) in zip(t, t[1:]):
        if cube <= c1:
            return y0 + (y1 - y0) * (cube - c0) / (c1 - c0)
    return cube * t[-1][1] / t[-1][0]


#: Design criteria the user can choose (standards.REFS codes).
CODES = {"EIT1007": "วสท. 1007-34 (fc = 0.45 fc') ภายใต้ข้อจำกัดของประกาศ มท. 2567",
         "MI2567": "ประกาศกระทรวงมหาดไทย 2567 ข้อ 29 (fs เหล็ก SD40 ถึง 2,000 ksc)",
         "MR6": "กฎกระทรวง ฉบับที่ 6 (ยกเลิกแล้ว ใช้เฉพาะอาคารตามบทเฉพาะกาล ข้อ 25 ของกฎกระทรวง พ.ศ. 2566)"}


@dataclass
class Concrete:
    fc_prime: float = 210.0      # cylinder strength, ksc (≈ 240 ksc cube)
    main_grade: str = "SD40"     # deformed bars DB
    tie_grade: str = "SR24"      # round bars RB (stirrups, slab RB9)
    code: str = "EIT1007"        # "EIT1007", "MI2567" or "MR6"
    qc: bool = True              # construction standard and quality control stated on the drawings

    @property
    def ref(self) -> str:
        return {"MR6": "MR6-21", "MI2567": "MI2567-29"}.get(self.code, "EIT1007")

    @property
    def fc(self) -> float:
        if self.code == "MR6":
            return min(0.375 * self.fc_prime, 65.0)
        fc = 0.45 * self.fc_prime                                  # ข้อ 29 (4) (ก)
        return fc if self.qc else min(fc, FC_WSD_CAP)               # ข้อ 29 (4) (ข)

    @property
    def fc_usd(self) -> float:
        """Specified strength for strength design — ข้อ 29 (5) (ก)–(ข)."""
        return self.fc_prime if self.qc else min(self.fc_prime, FC_USD_CAP)

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
        grade = self.tie_grade if bar.upper().startswith("RB") else self.main_grade
        if self.code == "MR6":
            return min(0.5 * FY[grade], 1500.0)
        if self.code == "MI2567":                                   # ข้อ 29 (4) (ค) 1)
            fy = FY[grade]
            if grade.startswith("SR"):
                return 1200.0
            return min(0.5 * fy, 1500.0) if fy < 4000 else 2000.0
        return FS[grade]

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
