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


def test_latest_release_link(ST):
    d = ST.summary([{"tag_name": "v2026.11.04.3", "published_at": "2026-11-04T17:30:00Z",
                     "html_url": "https://github.com/x/y/releases/tag/v2026.11.04.3",
                     "assets": [{"name": "s.exe", "download_count": 1}]}])
    assert ST.newer("v2026.11.04.3", "2026.11.04.2") and not ST.newer("v2026.11.04.3", "2026.11.04.3")
    assert ST.thai_day(d["published"]) == "5 พ.ย. 2569"          # 17:30 UTC is the next day in Thailand
    line = ST.latest_line(d, "2026.11.04.2")
    assert "มีรุ่นใหม่ v2026.11.04.3" in line and "ดาวน์โหลดได้จากหน้าต่างแจ้งเวอร์ชันใหม่" in line
    assert "href" not in line                  # the corner tells; the update window downloads
    assert "คุณใช้เวอร์ชันที่ยังไม่ปรับปรุง (v2026.11.04.2)" in line
    assert "ปรับปรุงล่าสุด v2026.11.04.3" in ST.latest_line(d, "2026.11.04.3")
    assert "เป็นรุ่นล่าสุดแล้ว" in ST.latest_line(d, "2026.11.04.3")
    assert "href" not in ST.text({"downloads": d}, version="dev")


def test_the_update_window_like_readwanicn(ST, monkeypatch):
    """The owner (25 พ.ย. 69): «มีเวอร์ชันใหม่» opens a window with the notes,
    the installer to download, and the year of use carried on; ReadWanicn's
    releases in the same repository are not WANICNSURVEY's."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("WANIC_OFFLINE", "1")
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    data = [
        {"tag_name": "readwanicn-v2027.4.11", "published_at": "2026-11-24T05:00:00Z",
         "assets": [{"name": "readwanicn2027-setup.exe", "download_count": 9}]},
        {"tag_name": "v2026.11.25.1", "published_at": "2026-11-25T03:00:00Z", "body": "## ใหม่\n- ทางโค้ง",
         "html_url": "https://github.com/x/y/releases/tag/v2026.11.25.1",
         "assets": [{"name": "wanicnsurvey-setup-2026.11.25.1.exe", "download_count": 3,
                     "browser_download_url": "https://github.com/x/y/releases/download/v2026.11.25.1/s.exe"}]},
        {"tag_name": "v2026.11.12.1", "assets": [{"name": "w.exe", "download_count": 5}]},
    ]
    d = ST.summary(data)
    assert d["tag"] == "v2026.11.25.1" and d["installer"].endswith("/s.exe") and "ทางโค้ง" in d["notes"]
    import update_dialog as UD
    s = _Settings()
    assert UD.should_show(d, "2026.11.12.1", s) and not UD.should_show(d, "2026.11.25.1", s)
    assert not UD.should_show(d, "dev", s)
    dlg = UD.UpdateDialog(d, "2026.11.12.1", None, None, s)
    dlg.skip.setChecked(True)
    dlg.go.click()
    assert dlg.opened == [d["installer"]] and s["update/skip"] == "v2026.11.25.1"
    assert not UD.should_show(d, "2026.11.12.1", s)                 # «ไม่ต้องเตือนรุ่นนี้อีก»
