# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""How many times the program has been downloaded, for the corner of the
main window (top right, beside the menus).

GitHub counts every download of a release's installer, and its public API
gives the counts without a sign-in: the total over every release and the
latest release's own. Nothing about the user is sent — it is one plain
read of the public release list. Pure Python (urllib); the window calls
:func:`fetch` off its own thread and shows :func:`text`.
"""
from __future__ import annotations

import json
import urllib.request

REPO = "venidnid-creator/wanicn1"
RELEASES = f"https://api.github.com/repos/{REPO}/releases?per_page=100"
PAGE = f"https://github.com/{REPO}/releases"
AGENT = "WANICNSURVEY-3D"


def _get(url: str, timeout: float = 8.0):
    req = urllib.request.Request(url, headers={"User-Agent": AGENT,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def counts(data) -> dict:
    """{"total", "latest", "tag", "releases"} from GitHub's release list."""
    if not isinstance(data, list):
        raise ValueError("unexpected answer")
    total = sum(int(a.get("download_count") or 0)
                for r in data for a in r.get("assets") or [])
    latest = data[0] if data else {}
    return {"total": total,
            "latest": sum(int(a.get("download_count") or 0)
                          for a in latest.get("assets") or []),
            "tag": latest.get("tag_name", ""), "releases": len(data)}


def fetch(opener=None) -> dict:
    """The counts now (``opener(url)`` replaces the network in tests)."""
    return counts(opener(RELEASES) if opener else _get(RELEASES))


def text(info, offline: bool = False) -> str:
    """One short line for the corner (HTML)."""
    if not info:
        return "⬇ ยอดดาวน์โหลด — (ออฟไลน์)"
    tag = info.get("tag") or ""
    line = (f"⬇ ดาวน์โหลดสะสม <b>{int(info['total']):,}</b> ครั้ง · "
            f"รุ่นล่าสุด {tag} <b>{int(info['latest']):,}</b> ครั้ง")
    return line + (" (ข้อมูลล่าสุดที่บันทึกไว้)" if offline else "")


def tooltip(info) -> str:
    if not info:
        return "ต่ออินเทอร์เน็ตเพื่อดูยอดดาวน์โหลดจาก GitHub — คลิกเพื่อเปิดหน้าดาวน์โหลด"
    return (f"ยอดดาวน์โหลดตัวติดตั้งจาก GitHub ทุกรุ่น ({int(info.get('releases', 0))} รุ่น) "
            f"รวม {int(info['total']):,} ครั้ง\nรุ่นล่าสุด {info.get('tag', '')}: "
            f"{int(info['latest']):,} ครั้ง\nคลิกเพื่อเปิดหน้าดาวน์โหลด")
