# SPDX-License-Identifier: GPL-3.0-or-later
"""A newer version and the download count, from the GitHub Releases of
the program's repository (no server of our own needed).

The count is the sum of the release assets' download counters: how many
times the installer was downloaded, not how many different people did --
GitHub does not tell those apart.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass

from . import REPO, TAG_PREFIX, VERSION

API = "https://api.github.com/repos/{repo}/releases?per_page=100"


@dataclass
class ReleaseInfo:
    latest: str = ""                # version of the newest ReadWanicn release
    url: str = ""                   # its page, to download from
    downloads: int = 0              # every ReadWanicn installer download, all versions
    newer: bool = False


def _key(version: str) -> tuple:
    out = []
    for part in version.replace("-", ".").split("."):
        out.append(int(part) if part.isdigit() else 0)
    return tuple(out)


def parse(releases: list, current: str = VERSION) -> ReleaseInfo:
    info = ReleaseInfo()
    ours = [r for r in releases if str(r.get("tag_name", "")).startswith(TAG_PREFIX)
            and not r.get("draft")]
    for r in ours:
        info.downloads += sum(int(a.get("download_count", 0)) for a in r.get("assets", []))
    if ours:
        best = max(ours, key=lambda r: _key(r["tag_name"][len(TAG_PREFIX):]))
        info.latest = best["tag_name"][len(TAG_PREFIX):]
        info.url = best.get("html_url", "")
        info.newer = _key(info.latest) > _key(current)
    return info


def fetch(timeout: float = 10.0) -> ReleaseInfo:
    req = urllib.request.Request(API.format(repo=REPO), headers={
        "Accept": "application/vnd.github+json", "User-Agent": f"ReadWanicn2027/{VERSION}"})
    with urllib.request.urlopen(req, timeout=timeout) as reply:
        return parse(json.loads(reply.read().decode("utf-8")))
