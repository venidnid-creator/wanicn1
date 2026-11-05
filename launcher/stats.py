# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""How many people downloaded the program and how many use it, for the
start screen's corner (and the 3D window's).

* Downloads: GitHub counts every download of a release's installer; the
  public API gives them (no sign-in): the total over every release, and
  the latest release's own. Read fresh every time the program opens.
* Users — on GitHub too, no server of our own: every release carries two
  tiny files, ``usage-install.txt`` and ``usage-open.txt``. The program
  downloads the first ONCE per computer (the first time it is opened) and
  the second each time it opens; GitHub counts those downloads like any
  other, so «users ever» is the sum of the install file's count over every
  release, and «opens» the open file's. Nothing about the user is sent —
  just two plain downloads (GitHub sees the address, as for any download).
  ``usage/off`` in the settings turns it off.
* Optional: a counter web app of the developer's own
  (``tools/usage_counter/Code.gs``) adds «online now» and «today».

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
INSTALL_FILE = "usage-install.txt"
OPEN_FILE = "usage-open.txt"
ASSET = f"https://github.com/{REPO}/releases/download/v{{version}}/{{name}}"


def _get(url: str, timeout: float = 8.0, opener=None):
    if opener is not None:
        return opener(url, timeout)
    req = urllib.request.Request(url, headers={"User-Agent": AGENT,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _count(rel, pred) -> int:
    return sum(int(a.get("download_count") or 0) for a in rel.get("assets") or []
               if pred(str(a.get("name") or "")))


def _installer(name: str) -> bool:
    return name.lower().endswith(".exe")


def summary(data) -> dict:
    """{"total", "latest", "tag", "releases", "users", "opens"} from
    GitHub's release list: installer downloads, and the usage files'."""
    if not isinstance(data, list):
        raise ValueError("unexpected answer")
    rels = [r for r in data if any(_installer(str(a.get("name") or ""))
                                   for a in r.get("assets") or [])]
    latest = rels[0] if rels else {}
    return {"published": str(latest.get("published_at") or latest.get("created_at") or ""),
            "url": str(latest.get("html_url") or
                       f"https://github.com/{REPO}/releases/latest"),
            "total": sum(_count(r, _installer) for r in data),
            "latest": _count(latest, _installer) if latest else 0,
            "tag": latest.get("tag_name", ""), "releases": len(rels),
            "users": sum(_count(r, lambda n: n == INSTALL_FILE) for r in data),
            "opens": sum(_count(r, lambda n: n == OPEN_FILE) for r in data)}


def downloads(opener=None) -> dict:
    """{"total", "latest", "tag", "releases", "users", "opens"}."""
    return summary(_get(RELEASES, opener=opener))


def _hit(url: str, opener=None, timeout: float = 8.0) -> bool:
    """Download one usage file (GitHub counts it); True when it was there."""
    try:
        if opener is not None:
            opener(url, timeout)
            return True
        req = urllib.request.Request(url, headers={"User-Agent": AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read(256)
        return True
    except Exception:                                # noqa: BLE001 -- offline / old release
        return False


def ping(settings, version: str, opener=None) -> list:
    """Count this computer once (the first time it opens the program) and
    this opening; the files of the running version's release. Returns the
    files sent. Nothing when switched off or the version is unknown."""
    if not version or version == "dev" or (settings is not None and
                       str(settings.value("usage/off") or "") in ("1", "true")):
        return []
    sent = []
    done = settings is not None and str(settings.value("usage/installed") or "") in ("1", "true")
    if not done and _hit(ASSET.format(version=version, name=INSTALL_FILE), opener):
        sent.append(INSTALL_FILE)
        if settings is not None:
            settings.setValue("usage/installed", "1")
    if _hit(ASSET.format(version=version, name=OPEN_FILE), opener):
        sent.append(OPEN_FILE)
    return sent


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


def fetch_all(settings, version: str, opener=None, count=True) -> dict:
    """Everything the corner shows; each part fails on its own. ``count``:
    also count this opening (once per start; a later refresh only reads)."""
    out = {}
    if count:
        out["sent"] = ping(settings, version, opener)
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
        out["usage_off"] = "ปิดการนับไว้" if opted_out else ""
    import time
    out["at"] = time.strftime("%d/%m/%Y %H:%M")
    return out


_MONTHS = ("ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.",
           "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.")


def thai_day(iso: str) -> str:
    """«4 พ.ย. 2569» from GitHub's ``2026-11-04T07:30:00Z`` (the Thai
    calendar day, UTC+7)."""
    import datetime as _dt
    try:
        t = _dt.datetime.strptime(str(iso)[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return ""
    t += _dt.timedelta(hours=7)
    return f"{t.day} {_MONTHS[t.month - 1]} {t.year + 543}"


def newer(tag: str, version: str) -> bool:
    """Whether the release ``tag`` (v2026.11.04.2) is newer than the
    installed ``version`` (2026.11.04.1)."""
    def key(v):
        out = []
        for part in str(v).lstrip("v").split("."):
            try:
                out.append(int(part))
            except ValueError:
                return None
        return out
    a, b = key(tag), key(version)
    return bool(a and b and a > b)


def latest_line(d: dict, version: str = "") -> str:
    """The link to the newest release: its version and day; «มีรุ่นใหม่»
    when it is newer than the one installed."""
    if not d or not d.get("tag"):
        return ""
    day = thai_day(d.get("published", ""))
    url = d.get("url") or f"https://github.com/{REPO}/releases/latest"
    new = newer(d["tag"], version)
    label = (f"🆕 มีรุ่นใหม่ {d['tag']}" if new else f"ปรับปรุงล่าสุด {d['tag']}") + \
        (f" ({day})" if day else "")
    tail = " — คลิกเพื่อดาวน์โหลด" if new else " — หน้าดาวน์โหลด"
    color = "#C0392B" if new else "#1F7A8C"
    line = f"<a href='{url}' style='color:{color}'><b>{label}</b>{tail}</a>"
    if version and version != "dev":
        line += f"<br>รุ่นที่ใช้อยู่: v{str(version).lstrip('v')}"
        if new:
            line += (f"<br><a href='{url}' style='color:#C0392B'><b>⚠ คุณใช้เวอร์ชันที่ยังไม่ปรับปรุง "
                     f"(v{str(version).lstrip('v')}) — ให้ดาวน์โหลดเวอร์ชันใหม่ {d['tag']}</b></a>")
        else:
            line += " <span style='color:#2E7D32'>✓ เป็นรุ่นล่าสุดแล้ว</span>"
    return line


def text(info: dict, cached: dict | None = None, version: str = "") -> str:
    """The corner's lines (Thai, HTML)."""
    d = info.get("downloads") or (cached or {}).get("downloads")
    lines = []
    if d and latest_line(d, version):
        lines.append(latest_line(d, version))
    if d:
        lines.append(f"ดาวน์โหลดสะสม <b>{d['total']:,}</b> ครั้ง")
        lines.append(f"รุ่นล่าสุด {d.get('tag', '')}: <b>{d['latest']:,}</b> ครั้ง")
        if "users" in d:
            lines.append(f"ผู้ใช้งานสะสม <b>{d['users']:,}</b> คน (เครื่องที่เคยเปิดใช้)")
            lines.append(f"เปิดใช้งานสะสม {d.get('opens', 0):,} ครั้ง")
    else:
        lines.append("ดาวน์โหลดสะสม — (ออฟไลน์)")
    u = info.get("usage") or (cached or {}).get("usage")
    if u:
        lines.append(f"ใช้งานอยู่ขณะนี้ <b>{u['online']:,}</b> คน · วันนี้ {u['today']:,} คน")
    elif info.get("usage_off"):
        lines.append(f"ผู้ใช้งาน — ({info['usage_off']})")
    at = info.get("at") if info.get("downloads") else (cached or {}).get("at")
    if at:
        lines.append(f"<span style='color:#888'>ข้อมูล ณ {at}"
                     f"{'' if info.get('downloads') else ' (ออฟไลน์)'}</span>")
    return "<br>".join(lines)
