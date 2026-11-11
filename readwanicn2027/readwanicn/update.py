# SPDX-License-Identifier: GPL-3.0-or-later
"""A newer version, downloads and users, from the GitHub Releases of the
program's repository (no server of our own).

* Downloads: the installers' download counters, over every ReadWanicn
  release and for the latest one.
* Users: every release also carries two tiny files. The program downloads
  ``readwanicn-usage-install.txt`` once per computer (the first time it
  opens) and ``readwanicn-usage-open.txt`` each time it opens; GitHub counts
  those downloads like any other, so «computers that ever opened it» and
  «openings» are their counters. Nothing about the user is sent.

Counts are downloads, not people: GitHub does not tell people apart.
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.request
from dataclasses import dataclass

from . import REPO, TAG_PREFIX, VERSION

API = "https://api.github.com/repos/{repo}/releases?per_page=100"
INSTALL_FILE = "readwanicn-usage-install.txt"
OPEN_FILE = "readwanicn-usage-open.txt"
ASSET = "https://github.com/{repo}/releases/download/{tag}/{name}"
THAI_MONTHS = ("ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.",
               "พ.ย.", "ธ.ค.")
_PINGED = False


@dataclass
class ReleaseInfo:
    latest: str = ""                # version of the newest ReadWanicn release
    url: str = ""                   # its page, to download from
    downloads: int = 0              # installer downloads, every version
    newer: bool = False
    latest_downloads: int = 0       # installer downloads of the newest version
    users: int = 0                  # computers that ever opened the program
    opens: int = 0                  # openings
    published_th: str = ""          # the newest release's day, Thai style
    fetched: str = ""               # when these numbers were read


def _key(version: str) -> tuple:
    return tuple(int(p) if p.isdigit() else 0 for p in version.replace("-", ".").split("."))


def thai_day(iso: str) -> str:
    try:
        d = dt.date.fromisoformat(iso[:10])
    except ValueError:
        return ""
    return f"{d.day} {THAI_MONTHS[d.month - 1]} {d.year + 543}"


def _count(release, pred) -> int:
    return sum(int(a.get("download_count", 0)) for a in release.get("assets", [])
               if pred(str(a.get("name", ""))))


def parse(releases: list, current: str = VERSION, now: dt.datetime | None = None) -> ReleaseInfo:
    info = ReleaseInfo()
    ours = [r for r in releases if str(r.get("tag_name", "")).startswith(TAG_PREFIX)
            and not r.get("draft")]
    exe = lambda n: n.lower().endswith(".exe")
    for r in ours:
        info.downloads += _count(r, exe)
        info.users += _count(r, lambda n: n == INSTALL_FILE)
        info.opens += _count(r, lambda n: n == OPEN_FILE)
    if ours:
        best = max(ours, key=lambda r: _key(r["tag_name"][len(TAG_PREFIX):]))
        info.latest = best["tag_name"][len(TAG_PREFIX):]
        info.url = best.get("html_url", "")
        info.newer = _key(info.latest) > _key(current)
        info.latest_downloads = _count(best, exe)
        info.published_th = thai_day(str(best.get("published_at") or best.get("created_at") or ""))
    now = now or dt.datetime.now()
    info.fetched = f"{thai_day(now.date().isoformat())} {now:%H:%M}"
    return info


def fetch(timeout: float = 10.0) -> ReleaseInfo:
    req = urllib.request.Request(API.format(repo=REPO), headers={
        "Accept": "application/vnd.github+json", "User-Agent": f"ReadWanicn2027/{VERSION}"})
    with urllib.request.urlopen(req, timeout=timeout) as reply:
        return parse(json.loads(reply.read().decode("utf-8")))


def ping(settings, info: ReleaseInfo, opener=None) -> list:
    """Count this computer once and this opening once (per run), on the
    newest release's two usage files; ``usage/off`` in the settings stops it."""
    global _PINGED
    if _PINGED or not info.latest or str(settings.value("usage/off", "")) == "1":
        return []
    _PINGED = True
    tag = f"{TAG_PREFIX}{info.latest}"
    names = [OPEN_FILE]
    if not settings.value("usage/installed"):
        names.insert(0, INSTALL_FILE)
    hit = []
    for name in names:
        url = ASSET.format(repo=REPO, tag=tag, name=name)
        try:
            if opener:
                opener(url)
            else:
                req = urllib.request.Request(url, headers={"User-Agent": f"ReadWanicn2027/{VERSION}"})
                urllib.request.urlopen(req, timeout=8).read(64)
            hit.append(name)
            if name == INSTALL_FILE:
                settings.setValue("usage/installed", "1")
        except Exception:
            pass
    return hit
