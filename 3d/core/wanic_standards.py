# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""Whether the government documents the price estimate is built on are
still the current ones: the labour list (บัญชีค่าแรงงาน ว480), the Factor F
table (ว481) and the 2569 rules.

This copy of the program knows the ones it was built with (:data:`BUNDLED`).
The developer keeps ``standards.json`` in the program's repository up to
date; the BOQ window reads it (one small public file, nothing sent) and,
when a document has been replaced or cancelled, says so — which document,
the new one, and that the program should be updated to it.
"""
from __future__ import annotations

import json
import urllib.request

URL = ("https://raw.githubusercontent.com/venidnid-creator/wanicn1/"
       "claude/youthful-pascal-ctgtr0/standards.json")
NAMES = {"labour": "บัญชีค่าแรงงาน", "factor_f": "ตาราง Factor F",
         "rules": "หลักเกณฑ์การคำนวณราคากลาง"}
#: what this build of the program uses
BUNDLED = {"labour": {"id": "ว480", "date": "2569-06-26"},
           "factor_f": {"id": "ว481", "date": "2569-06-26"},
           "rules": {"id": "2569", "date": "2569-06-08"}}


def fetch(opener=None, timeout: float = 6.0) -> dict:
    if opener is not None:
        return opener(URL)
    req = urllib.request.Request(URL, headers={"User-Agent": "WANICNSURVEY-3D"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def changes(current: dict) -> list[str]:
    """One Thai line per document that is no longer the one this build
    uses (or that the developer marked cancelled)."""
    out = []
    for key, mine in BUNDLED.items():
        now = (current or {}).get(key) or {}
        if not now:
            continue
        cancelled = str(now.get("status") or "") in ("cancelled", "ยกเลิก")
        if now.get("id") != mine["id"] or now.get("date") != mine["date"] or cancelled:
            what = "ถูกยกเลิก" if cancelled and now.get("id") == mine["id"] else \
                f"เปลี่ยนเป็น {now.get('title') or now.get('id')}"
            out.append(f"{NAMES[key]} {mine['id']} ที่โปรแกรมรุ่นนี้ใช้ {what} — "
                       "กรุณาอัปเดตโปรแกรมเป็นรุ่นล่าสุด (ราคาที่คำนวณอาจไม่เป็นปัจจุบัน)")
    return out
