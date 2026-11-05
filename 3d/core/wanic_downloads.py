# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""Downloads and users of the program, for the corner of the main window
(top right, beside the menus) — the same numbers as the start screen's.

* Downloads: GitHub counts every download of a release's installer, and
  its public API gives the counts without a sign-in: the total over every
  release and the latest release's own.
* Users: every release carries two tiny files. The program downloads
  ``usage-install.txt`` once per computer (the first time it opens) and
  ``usage-open.txt`` each time it opens; GitHub counts them like any other
  download, so «users ever» is the install file's count over all releases.
  Nothing about the user is sent. The start screen and this window share
  the «already counted» mark, so a computer is one user however it starts.

Pure Python (urllib); the window calls :func:`fetch` off its own thread.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

REPO = "venidnid-creator/wanicn1"
RELEASES = f"https://api.github.com/repos/{REPO}/releases?per_page=100"
PAGE = f"https://github.com/{REPO}/releases"
AGENT = "WANICNSURVEY-3D"
INSTALL_FILE = "usage-install.txt"
OPEN_FILE = "usage-open.txt"
ASSET = f"https://github.com/{REPO}/releases/download/v{{version}}/{{name}}"
#: where the start screen keeps its marks (QSettings organisation, app)
SETTINGS = ("WANICNSURVEY", "launcher")


def _get(url: str, timeout: float = 8.0):
    req = urllib.request.Request(url, headers={"User-Agent": AGENT,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _count(rel, pred) -> int:
    return sum(int(a.get("download_count") or 0) for a in rel.get("assets") or []
               if pred(str(a.get("name") or "")))


def _installer(name: str) -> bool:
    return name.lower().endswith(".exe")


def counts(data) -> dict:
    """{"total", "latest", "tag", "releases", "users", "opens"} from
    GitHub's release list."""
    if not isinstance(data, list):
        raise ValueError("unexpected answer")
    rels = [r for r in data if any(_installer(str(a.get("name") or ""))
                                   for a in r.get("assets") or [])]
    latest = rels[0] if rels else {}
    return {"total": sum(_count(r, _installer) for r in data),
            "latest": _count(latest, _installer) if latest else 0,
            "tag": latest.get("tag_name", ""), "releases": len(rels),
            "users": sum(_count(r, lambda n: n == INSTALL_FILE) for r in data),
            "opens": sum(_count(r, lambda n: n == OPEN_FILE) for r in data),
            "at": time.strftime("%d/%m/%Y %H:%M")}


def fetch(opener=None) -> dict:
    """The counts now (``opener(url)`` replaces the network in tests)."""
    return counts(opener(RELEASES) if opener else _get(RELEASES))


def version() -> str:
    """The installed version (the installer writes it beside the start
    screen: ``…\\launcher\\VERSION``; this window is ``…\\3d\\``)."""
    exe = Path(sys.executable).resolve().parent
    for p in (exe / "VERSION", exe.parent / "launcher" / "VERSION"):
        try:
            return p.read_text(encoding="utf-8").strip()
        except OSError:
            continue
    return ""


def _hit(url: str, opener=None) -> bool:
    try:
        if opener is not None:
            opener(url)
            return True
        req = urllib.request.Request(url, headers={"User-Agent": AGENT})
        with urllib.request.urlopen(req, timeout=8.0) as r:
            r.read(256)
        return True
    except Exception:                                # noqa: BLE001 -- offline
        return False


def ping(settings, ver: str, opener=None, opening=True) -> list:
    """Count this computer once and (``opening``) this opening — the 3D
    window leaves the openings to the start screen, which counts them."""
    if not ver or ver == "dev" or (settings is not None and
                                   str(settings.value("usage/off") or "") in ("1", "true")):
        return []
    sent = []
    done = settings is not None and str(settings.value("usage/installed") or "") in ("1", "true")
    if not done and _hit(ASSET.format(version=ver, name=INSTALL_FILE), opener):
        sent.append(INSTALL_FILE)
        if settings is not None:
            settings.setValue("usage/installed", "1")
    if opening and _hit(ASSET.format(version=ver, name=OPEN_FILE), opener):
        sent.append(OPEN_FILE)
    return sent


def _newer(tag: str, version: str) -> bool:
    def key(v):
        try:
            return [int(x) for x in str(v).lstrip("v").split(".")]
        except ValueError:
            return None
    a, b = key(tag), key(version)
    return bool(a and b and a > b)


def text(info, offline: bool = False, version: str = "") -> str:
    """One short line for the corner (HTML); a warning when the program
    is older than the latest release."""
    if not info:
        return "⬇ ยอดดาวน์โหลด — (ออฟไลน์)"
    if version and _newer(info.get("tag", ""), version):
        return (f"⚠ คุณใช้เวอร์ชันที่ยังไม่ปรับปรุง (v{version}) — ให้ดาวน์โหลดเวอร์ชันใหม่ "
                f"<b>{info['tag']}</b> (คลิก) · ⬇ ดาวน์โหลดสะสม <b>{int(info['total']):,}</b> ครั้ง")
    tag = info.get("tag") or ""
    line = (f"⬇ ดาวน์โหลดสะสม <b>{int(info['total']):,}</b> ครั้ง · "
            f"รุ่นล่าสุด {tag} <b>{int(info['latest']):,}</b> ครั้ง")
    if "users" in info:
        line += f" · 👤 ผู้ใช้งานสะสม <b>{int(info['users']):,}</b> คน"
    return line + (" (ข้อมูลล่าสุดที่บันทึกไว้)" if offline else "")


def tooltip(info) -> str:
    if not info:
        return "ต่ออินเทอร์เน็ตเพื่อดูยอดดาวน์โหลดจาก GitHub — คลิกเพื่อเปิดหน้าดาวน์โหลด"
    return (f"ยอดดาวน์โหลดตัวติดตั้งจาก GitHub ทุกรุ่น ({int(info.get('releases', 0))} รุ่น) "
            f"รวม {int(info['total']):,} ครั้ง\nรุ่นล่าสุด {info.get('tag', '')}: "
            f"{int(info['latest']):,} ครั้ง\nผู้ใช้งานสะสม (เครื่องที่เคยเปิดโปรแกรม) "
            f"{int(info.get('users', 0)):,} คน · เปิดใช้งาน {int(info.get('opens', 0)):,} ครั้ง\n"
            f"ข้อมูล ณ {info.get('at', '')} · อัปเดตทุกครั้งที่เปิดโปรแกรมและทุก 10 นาที\n"
            "คลิกเพื่อเปิดหน้าดาวน์โหลด")
