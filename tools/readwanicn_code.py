# SPDX-License-Identifier: GPL-3.0-or-later
"""The developer's tool: the renewal code ReadWanicn2027 asks for when a
year of use is up.

    python tools/readwanicn_code.py <รหัสเครื่อง> <ครั้งที่ต่ออายุ> --key <คีย์ที่ใช้สร้างตัวติดตั้ง>

The key is the READWANICN_LICENSE_KEY secret the installer was built with
(without it, the development key of runs from source).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "readwanicn2027"))

from readwanicn.license import renewal_code  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="รหัสผ่านต่ออายุ ReadWanicn2027")
    ap.add_argument("install_id", help="รหัสเครื่องที่ผู้ใช้แจ้งมา")
    ap.add_argument("n", type=int, help="ครั้งที่ต่ออายุ (แสดงในหน้าต่างหมดอายุ)")
    ap.add_argument("--key", default=None, help="คีย์ที่ใช้ตอนสร้างตัวติดตั้ง")
    a = ap.parse_args()
    print(renewal_code(a.install_id, a.n, a.key))


if __name__ == "__main__":
    main()
