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

    def opener(url, timeout):
        calls.append(url)
        if "api.github.com" in url:
            return [{"tag_name": "v2", "assets": [{"download_count": 7}]},
                    {"tag_name": "v1", "assets": [{"download_count": 5}, {"download_count": 1}]}]
        assert "id=" in url and "e=open" in url
        return {"online": 3, "today": 9, "total": 41}
    s = _Settings()
    info = ST.fetch_all(s, "2026.11.04", opener)
    assert info["downloads"] == {"total": 13, "latest": 7, "tag": "v2", "releases": 2}
    assert "usage" not in info and info["usage_off"]          # no counter yet: nothing sent
    assert len(calls) == 1
    s.setValue("usage/url", "https://script.example/exec")
    info = ST.fetch_all(s, "2026.11.04", opener)
    assert info["usage"] == {"online": 3, "today": 9, "total": 41}
    iid = s["usage/id"]
    ST.fetch_all(s, "2026.11.04", opener)
    assert s["usage/id"] == iid and len(iid) == 32            # one random id per install
    t = ST.text(info)
    assert "ดาวน์โหลดสะสม <b>13</b>" in t and "ใช้งานอยู่ขณะนี้ <b>3</b>" in t and "<b>41</b>" in t
    s.setValue("usage/off", "1")
    n = len(calls)
    ST.fetch_all(s, "x", opener)
    assert len(calls) == n + 1                                 # downloads only


def test_offline_shows_the_last_numbers(ST):
    def opener(url, timeout):
        raise OSError("offline")
    info = ST.fetch_all(_Settings(), "x", opener)
    assert "downloads_error" in info
    t = ST.text(info, {"downloads": {"total": 5, "latest": 2, "tag": "v1"}})
    assert "<b>5</b>" in t
