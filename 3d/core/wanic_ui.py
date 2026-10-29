# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
# WANICNSURVEY 3D — ปุ่มของส่วนขยาย WANIC ไม่เงียบเมื่อเกิดข้อผิดพลาด
"""Every WANIC button runs through :func:`safe`: an error inside it shows
a message with what went wrong (and is printed for a bug report) instead
of the click silently doing nothing — Qt swallows exceptions in slots."""
from __future__ import annotations

import traceback

#: The last error a button met (tests read it).
LAST_ERROR: list = []


def safe(parent, fn, *args):
    try:
        return fn(*args)
    except Exception as e:                       # shown, never swallowed
        tb = traceback.format_exc()
        LAST_ERROR.append(tb)
        print(tb, flush=True)
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                parent, "WANIC — เกิดข้อผิดพลาด",
                f"คำสั่งนี้ทำงานไม่สำเร็จ:\n{type(e).__name__}: {e}\n\n"
                "รายละเอียด (ส่งให้ผู้พัฒนาได้):\n" + tb[-1500:])
        except Exception:
            pass
        return None
