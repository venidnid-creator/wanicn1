# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""มีเวอร์ชันใหม่ (the owner, 25 พ.ย. 69 — like ReadWanicn2027): what is new,
a direct download of the installer, and the promise that the year of use
carries on from the first installation (an update never starts a new year)."""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton,
                               QTextBrowser, QVBoxLayout)

SKIP_KEY = "update/skip"


def should_show(d: dict, version: str, settings) -> bool:
    """A newer release, not skipped by «ไม่ต้องเตือนรุ่นนี้อีก»."""
    import stats as ST
    if not d or not d.get("tag") or not version or version == "dev":
        return False
    if not ST.newer(d["tag"], version):
        return False
    return settings is None or str(settings.value(SKIP_KEY) or "") != d["tag"]


class UpdateDialog(QDialog):
    def __init__(self, d: dict, version: str, lic=None, logo=None, settings=None, parent=None):
        super().__init__(parent)
        import stats as ST
        self.d, self.settings = d, settings
        tag = d.get("tag", "")
        self.setWindowTitle("WANICNSURVEY — มีเวอร์ชันใหม่")
        if logo:
            self.setWindowIcon(QIcon(str(logo)))
        self.setMinimumWidth(500)
        self.setStyleSheet("QDialog, QLabel, QCheckBox { background: white; color: #0F2A44; }"
                           "QTextBrowser { background:#F6F8FB; color:#0F2A44; border:1px solid #DDE3EA; }"
                           "QPushButton { background:#EEF2F8; color:#0F2A44; border:1px solid #C9CED6;"
                           " border-radius:6px; padding:7px 14px; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 16)
        if logo:
            pic = QLabel()
            pm = QPixmap(str(logo))
            if not pm.isNull():
                pic.setPixmap(pm.scaledToWidth(64, Qt.SmoothTransformation))
            pic.setAlignment(Qt.AlignCenter)
            lay.addWidget(pic)
        day = ST.thai_day(d.get("published", ""))
        head = QLabel(f"<span style='font-size:17pt; font-weight:bold; color:#1D4ED8'>มีเวอร์ชันใหม่ "
                      f"{tag}</span><br>รุ่นที่ใช้อยู่ v{str(version).lstrip('v')}"
                      + (f" · ออกเมื่อ {day}" if day else ""))
        head.setAlignment(Qt.AlignCenter)
        lay.addWidget(head)
        if str(d.get("notes") or "").strip():
            notes = QTextBrowser()
            notes.setMarkdown(d["notes"])
            notes.setMaximumHeight(170)
            lay.addWidget(notes)
        if lic is not None:
            import wanic_license as WL
            first = f"วันที่ติดตั้งครั้งแรก {WL.thai_date(lic.start)}" if lic.start else "วันที่ติดตั้งครั้งแรก"
            keep = QLabel(f"✔ อัปเดตแล้วยังใช้งานได้ถึง <b>{WL.thai_date(lic.until)}</b> เหมือนเดิม "
                          f"(นับ 1 ปีจาก{first} ไม่เริ่มนับใหม่) · งานและการตั้งค่าที่บันทึกไว้อยู่ครบ")
        else:
            keep = QLabel("✔ อัปเดตแล้วอายุการใช้งานนับต่อจากวันที่ติดตั้งครั้งแรก ไม่เริ่มนับใหม่ "
                          "· งานและการตั้งค่าที่บันทึกไว้อยู่ครบ")
        keep.setWordWrap(True)
        keep.setStyleSheet("background:#ECFDF5; color:#065F46; border-radius:6px; padding:8px;")
        lay.addWidget(keep)
        how = QLabel("วิธีอัปเดต: กด «ดาวน์โหลดตัวติดตั้ง» → ปิดโปรแกรม → "
                     "เปิดไฟล์ที่ดาวน์โหลดแล้วกดติดตั้งทับได้เลย")
        how.setWordWrap(True)
        lay.addWidget(how)
        self.skip = QCheckBox(f"ไม่ต้องเตือนรุ่น {tag} อีก")
        lay.addWidget(self.skip)
        row = QHBoxLayout()
        self.go = QPushButton("⬇ ดาวน์โหลดตัวติดตั้ง")
        self.go.setStyleSheet("background:#C9A14A; color:white; border:none; border-radius:6px;"
                              " padding:8px 16px; font-weight:bold;")
        self.go.clicked.connect(self.download)
        row.addWidget(self.go)
        page = QPushButton("หน้ารายละเอียด")
        page.clicked.connect(lambda: self._open(d.get("url", "")))
        row.addWidget(page)
        row.addStretch(1)
        later = QPushButton("ภายหลัง")
        later.clicked.connect(self.reject)
        row.addWidget(later)
        lay.addLayout(row)
        self.finished.connect(self._remember)
        self.opened = []

    def _open(self, url: str):
        if url:
            self.opened.append(url)
            import os
            if not os.environ.get("WANIC_OFFLINE"):
                QDesktopServices.openUrl(QUrl(url))

    def download(self):
        self._open(self.d.get("installer") or self.d.get("url", ""))
        self.accept()

    def _remember(self, *_a):
        if self.skip.isChecked() and self.settings is not None:
            self.settings.setValue(SKIP_KEY, self.d.get("tag", ""))
