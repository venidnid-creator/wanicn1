# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""The start screen shows the developer, free use and the support account."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_start_screen_support_panel(monkeypatch):
    if not (ROOT / "launcher" / "launcher.py").exists():
        pytest.skip("the launcher is not beside this checkout")
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton
    app = QApplication.instance() or QApplication([])
    sys.path.insert(0, str(ROOT / "launcher"))
    try:
        import launcher as L
    finally:
        sys.path.pop(0)
    win = L.StartWindow()
    texts = " ".join(w.text() for w in win.findChildren(QLabel))
    for want in ("โปรแกรมใช้ได้ฟรี ไม่มีค่าลิขสิทธิ์", "สนับสนุนผู้พัฒนา", "กรุงศรี",
                 "โลตัส ถลาง ภูเก็ต", "นายเวนิช ธัมมะวงษ์", "666-1-32472-1",
                 "บัญชีออมทรัพย์"):
        assert want in texts, want
    photo = [w for w in win.findChildren(QLabel)
             if w.pixmap() is not None and not w.pixmap().isNull()
             and w.pixmap().width() == 260]
    assert photo, "the developer's photo is on the start screen"
    # the contact QR (it dials the developer) and the number in Thai script
    assert "ติดต่อผู้พัฒนาระบบ" in texts and "093-5838348" in texts
    qr = [w for w in win.findChildren(QLabel)
          if w.pixmap() is not None and not w.pixmap().isNull()
          and w.pixmap().width() == 120]
    assert qr, "the contact QR code is under the photo"
    contact = [w for w in win.findChildren(QLabel) if "093-5838348" in w.text()][0]
    assert contact.font().family() == "Charm"
    copy = [b for b in win.findChildren(QPushButton) if "คัดลอก" in b.text()][0]
    copy.click()
    assert app.clipboard().text() in ("666132472", "6661324721")
    shots = os.environ.get("WANIC_SHOTS")
    if shots:
        Path(shots).mkdir(parents=True, exist_ok=True)
        win.resize(1220, 720)
        win.grab().save(str(Path(shots) / "start-screen.png"))
