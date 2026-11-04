# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""The start screen's corner: downloads from GitHub, users from the counter."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def ST():
    if not (ROOT / "launcher" / "stats.py").exists():
        pytest.skip("the launcher is not beside this checkout")
    sys.path.insert(0, str(ROOT / "launcher"))
    try:
        import stats
        yield stats
    finally:
        sys.path.pop(0)


class _Settings(dict):
    def value(self, k, default=None):
        return self.get(k, default)

    def setValue(self, k, v):
        self[k] = v


def test_downloads_and_users(ST):
    calls = []
    counts = {"usage-install.txt": 4, "usage-open.txt": 30}

    def opener(url, timeout):
        calls.append(url)
        if "api.github.com" in url:
            return [{"tag_name": "v2", "assets": [
                        {"name": "wanicnsurvey-setup-2.exe", "download_count": 7},
                        {"name": "usage-install.txt", "download_count": counts["usage-install.txt"]},
                        {"name": "usage-open.txt", "download_count": counts["usage-open.txt"]}]},
                    {"tag_name": "v1", "assets": [{"name": "a.exe", "download_count": 5},
                                                  {"name": "b.exe", "download_count": 1}]}]
        if "/releases/download/" in url:
            name = url.rsplit("/", 1)[1]
            counts[name] += 1
            return b"ok"
        assert "id=" in url and "e=open" in url
        return {"online": 3, "today": 9, "total": 41}
    s = _Settings()
    info = ST.fetch_all(s, "2", opener)
    # this computer counted once, this opening once; installer downloads only
    assert info["sent"] == ["usage-install.txt", "usage-open.txt"]
    assert info["downloads"]["total"] == 13 and info["downloads"]["latest"] == 7
    assert info["downloads"]["users"] == 5 and info["downloads"]["opens"] == 31
    assert any(c.endswith("/v2/usage-install.txt") for c in calls)
    info = ST.fetch_all(s, "2", opener)
    assert info["sent"] == ["usage-open.txt"]                  # not a new user
    assert info["downloads"]["users"] == 5 and info["downloads"]["opens"] == 32
    n = len(calls)
    info = ST.fetch_all(s, "2", opener, count=False)          # a refresh only reads
    assert len(calls) == n + 1 and "sent" not in info
    t = ST.text(info)
    assert "ดาวน์โหลดสะสม <b>13</b>" in t and "ผู้ใช้งานสะสม <b>5</b>" in t
    assert "ข้อมูล ณ" in t
    s.setValue("usage/url", "https://script.example/exec")
    info = ST.fetch_all(s, "2", opener)
    assert info["usage"] == {"online": 3, "today": 9, "total": 41}
    assert "ใช้งานอยู่ขณะนี้ <b>3</b>" in ST.text(info)
    s.setValue("usage/off", "1")
    n = len(calls)
    info = ST.fetch_all(s, "2", opener)
    assert info["sent"] == [] and len(calls) == n + 1         # downloads only

def test_offline_shows_the_last_numbers(ST):
    def opener(url, timeout):
        raise OSError("offline")
    info = ST.fetch_all(_Settings(), "x", opener)
    assert "downloads_error" in info
    t = ST.text(info, {"downloads": {"total": 5, "latest": 2, "tag": "v1"}})
    assert "<b>5</b>" in t
