# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""เข้าสู่ระบบ WANICNSURVEY — the sign-in every program of the suite asks for.

While the programs are being completed and checked, they open only for the
developer's account. The window tells everyone else so (อยู่ระหว่างการ
พัฒนาให้สมบูรณ์ …). The account is kept as a salted PBKDF2 hash, never as
text. One sign-in serves the whole suite: the start screen hands its
session to the CAD and 3D programs it starts (``WANIC_SESSION``), and
«จดจำการเข้าสู่ระบบ» keeps it for this Windows user.

The same file is shipped in launcher/, cad/core/ and 3d/core/ (the three
programs are frozen apart); a test keeps the copies identical.

Note: this is a gate in the program on the user's own computer — it keeps
an unfinished release from being used, it is not a security boundary.
"""
from __future__ import annotations

import hashlib
import hmac
import os

NOTICE_TITLE = "อยู่ระหว่างการพัฒนา"
NOTICE = ("โปรแกรม WANICNSURVEY อยู่ระหว่างการพัฒนาให้สมบูรณ์ และตรวจสอบความถูกต้อง\n"
          "อดใจรอนะครับท่าน")
_SALT = bytes.fromhex("5741 4e49 4353 5552 5645 5932 3536 39".replace(" ", ""))
_ROUNDS = 120_000
#: PBKDF2-SHA256 of "user\npassword" (the user lower-cased, trimmed)
_ACCOUNTS = ("becd479cc22608d1e032260b0556e15c546d6206448100d3374f1f3d7e9bf51d",)
ENV = "WANIC_SESSION"
_ORG, _APP = "WANICNSURVEY", "Login"


def _digest(user: str, password: str) -> str:
    # a space typed or pasted before / after either one is not counted
    text = f"{user.strip().lower()}\n{password.strip()}".encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", text, _SALT, _ROUNDS).hex()


def check(user: str, password: str) -> bool:
    d = _digest(user, password)
    return any(hmac.compare_digest(d, a) for a in _ACCOUNTS)


def session_token() -> str:
    """What a signed-in program hands on (not the password)."""
    return hashlib.sha256(("wanic-session:" + _ACCOUNTS[0]).encode()).hexdigest()


def _remembered() -> bool:
    try:
        from PySide6.QtCore import QSettings
        return QSettings(_ORG, _APP).value("session", "") == session_token()
    except Exception:                                   # noqa: BLE001
        return False


def _remember(on: bool):
    try:
        from PySide6.QtCore import QSettings
        s = QSettings(_ORG, _APP)
        if on:
            s.setValue("session", session_token())
        else:
            s.remove("session")
    except Exception:                                   # noqa: BLE001
        pass


def signed_in() -> bool:
    return os.environ.get(ENV) == session_token() or _remembered()


def sign_out():
    _remember(False)
    os.environ.pop(ENV, None)


def require(parent=None) -> bool:
    """Ask for the account unless this session is already signed in.
    True when the program may go on (the session is then handed to the
    programs this one starts)."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    if signed_in():
        os.environ[ENV] = session_token()
        return True
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (QCheckBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
                                   QLineEdit, QPushButton, QVBoxLayout)

    dlg = QDialog(parent)
    dlg.setWindowTitle("เข้าสู่ระบบ — WANICNSURVEY")
    dlg.setMinimumWidth(460)
    lay = QVBoxLayout(dlg)
    head = QLabel("<div style='font-size:16px;font-weight:bold;color:#0F2A44'>WANICNSURVEY</div>"
                  "<div style='color:#55657A'>สำรวจ · เขียนแบบ 2 มิติ · ขึ้นโมเดล 3 มิติ</div>")
    lay.addWidget(head)
    note = QLabel("<div style='background:#FFF7E0;border:1px solid #E0B44C;padding:8px;"
                  "color:#7A4B00'><b>📢 " + NOTICE_TITLE + "</b><br>"
                  + NOTICE.replace("\n", "<br>") + "</div>")
    note.setWordWrap(True)
    lay.addWidget(note)
    form = QFormLayout()
    user = QLineEdit()
    user.setPlaceholderText("อีเมลผู้ใช้")
    pw = QLineEdit()
    pw.setEchoMode(QLineEdit.Password)
    pw.setPlaceholderText("รหัสผ่าน")
    form.addRow("ผู้ใช้", user)
    form.addRow("รหัสผ่าน", pw)
    lay.addLayout(form)
    show = QCheckBox("แสดงรหัสผ่าน")
    show.toggled.connect(lambda on: pw.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
    lay.addWidget(show)
    keep = QCheckBox("จดจำการเข้าสู่ระบบบนเครื่องนี้")
    lay.addWidget(keep)
    msg = QLabel("")
    msg.setStyleSheet("color:#B01E33")
    lay.addWidget(msg)
    row = QHBoxLayout()
    row.addStretch(1)
    ok = QPushButton("เข้าสู่ระบบ")
    ok.setDefault(True)
    no = QPushButton("ปิด")
    row.addWidget(ok)
    row.addWidget(no)
    lay.addLayout(row)
    tries = {"n": 0}

    def attempt():
        if check(user.text(), pw.text()):
            dlg.accept()
            return
        tries["n"] += 1
        pw.clear()
        msg.setText("ผู้ใช้หรือรหัสผ่านไม่ถูกต้อง (ตรวจตัวพิมพ์ใหญ่-เล็ก และแป้นพิมพ์ภาษาอังกฤษ)"
                    + (" — โปรแกรมยังไม่เปิดให้ใช้งานทั่วไป" if tries["n"] >= 2 else ""))
    ok.clicked.connect(attempt)
    pw.returnPressed.connect(attempt)
    no.clicked.connect(dlg.reject)
    dlg.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
    if dlg.exec() != QDialog.Accepted:
        return False
    os.environ[ENV] = session_token()
    _remember(keep.isChecked())
    return True
