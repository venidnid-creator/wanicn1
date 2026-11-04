# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""How many people downloaded the program and how many use it, for the
start screen's corner.

* Downloads: GitHub counts every download of a release's installer; the
  public API gives them (no sign-in): the total over every release, and
  the latest release's own.
* Users: GitHub cannot know who runs a program, so the start screen sends
  one anonymous «opened» ping to a small counter of the developer's own
  (``tools/usage_counter/Code.gs``, a Google Apps Script web app) — only a
  random install id, the version and the day; no name, no file, no IP
  is stored by the script. It answers with the users online now (opened
  within 15 minutes), today, and in all. No counter address configured,
  or the user said no: nothing is sent and the corner says so.

Pure Python (urllib); the window calls :func:`fetch_all` off its thread.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
import uuid

REPO = "venidnid-creator/wanicn1"
RELEASES = f"https://api.github.com/repos/{REPO}/releases?per_page=100"
#: The counter web app's address (Apps Script ``…/exec``); empty until the
#: developer deploys it. A QSettings value ``usage/url`` overrides it.
USAGE_URL = ""
AGENT = "WANICNSURVEY-launcher"


def _get(url: str, timeout: float = 8.0, opener=None):
    if opener is not None:
        return opener(url, timeout)
    req = urllib.request.Request(url, headers={"User-Agent": AGENT,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def downloads(opener=None) -> dict:
    """{"total", "latest", "tag", "releases"} from GitHub's release list."""
    data = _get(RELEASES, opener=opener)
    if not isinstance(data, list):
        raise ValueError("unexpected answer")
    total = sum(int(a.get("download_count") or 0) for r in data for a in r.get("assets") or [])
    latest = data[0] if data else {}
    return {"total": total,
            "latest": sum(int(a.get("download_count") or 0) for a in latest.get("assets") or []),
            "tag": latest.get("tag_name", ""), "releases": len(data)}


def install_id(settings) -> str:
    """A random id for this install (made once, kept in the settings)."""
    v = settings.value("usage/id") if settings is not None else None
    if not v:
        v = uuid.uuid4().hex
        if settings is not None:
            settings.setValue("usage/id", v)
    return str(v)


def usage(url: str, iid: str, version: str, opener=None) -> dict:
    """Ping the counter («opened») and read {"online", "today", "total"}."""
    q = urllib.parse.urlencode({"id": iid, "v": version, "e": "open"})
    data = _get(f"{url}?{q}", opener=opener)
    return {k: int(data.get(k) or 0) for k in ("online", "today", "total")}


def fetch_all(settings, version: str, opener=None) -> dict:
    """Everything the corner shows; each part fails on its own."""
    out = {}
    try:
        out["downloads"] = downloads(opener)
    except Exception as e:                        # noqa: BLE001 -- offline
        out["downloads_error"] = str(e)
    url = (settings.value("usage/url") if settings is not None else None) or USAGE_URL
    opted_out = settings is not None and str(settings.value("usage/off") or "") in ("1", "true")
    if url and not opted_out:
        try:
            out["usage"] = usage(url, install_id(settings), version, opener)
        except Exception as e:                    # noqa: BLE001
            out["usage_error"] = str(e)
    else:
        out["usage_off"] = "ยังไม่ได้ตั้งตัวนับผู้ใช้" if not url else "ปิดการนับไว้"
    return out


def text(info: dict, cached: dict | None = None) -> str:
    """The corner's lines (Thai, HTML)."""
    d = info.get("downloads") or (cached or {}).get("downloads")
    lines = []
    if d:
        lines.append(f"ดาวน์โหลดสะสม <b>{d['total']:,}</b> ครั้ง")
        lines.append(f"รุ่นล่าสุด {d.get('tag', '')}: <b>{d['latest']:,}</b> ครั้ง")
    else:
        lines.append("ดาวน์โหลดสะสม — (ออฟไลน์)")
    u = info.get("usage") or (cached or {}).get("usage")
    if u:
        lines.append(f"ใช้งานอยู่ขณะนี้ <b>{u['online']:,}</b> คน")
        lines.append(f"ผู้ใช้วันนี้ {u['today']:,} · สะสม <b>{u['total']:,}</b> คน")
    else:
        lines.append(f"ผู้ใช้งาน — ({info.get('usage_off') or 'ติดต่อตัวนับไม่ได้'})")
    return "<br>".join(lines)
