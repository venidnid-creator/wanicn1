# SPDX-License-Identifier: GPL-3.0-or-later
"""อายุการใช้งาน WANICNSURVEY: one year from the first start, kept through a
reinstall, renewed by the developer's code."""
import datetime as dt
from pathlib import Path

from core import wanic_license as L

ROOT = Path(__file__).resolve().parents[2]


def test_the_three_copies_are_the_same():
    me = (ROOT / "3d" / "core" / "wanic_license.py").read_bytes()
    assert (ROOT / "launcher" / "wanic_license.py").read_bytes() == me
    assert (ROOT / "cad" / "core" / "wanic_license.py").read_bytes() == me


def test_one_year_from_the_first_start(tmp_path):
    start = dt.date(2026, 11, 19)
    lic = L.License(tmp_path / "a.json", today=start)
    assert not lic.expired and lic.days_left == 365
    later = L.License(tmp_path / "a.json", today=start + dt.timedelta(days=366))
    assert later.expired and later.install_id == lic.install_id
    text, _c = L.badge_text(L.License(tmp_path / "a.json", today=start + dt.timedelta(days=7)))
    assert text == "🔑 ใช้ได้ถึง 19 พ.ย. 70 · เหลือ 358 วัน"


def test_a_reinstall_goes_on_counting(tmp_path):
    """The settings file lost (reinstall / clean-up): the backup keeps the first year."""
    start = dt.date(2026, 1, 1)
    main, bak = tmp_path / "s" / "license.json", tmp_path / "b" / "license-backup.json"
    lic = L.License(main, today=start, backups=[bak], registry=False)
    main.unlink()
    again = L.License(main, today=start + dt.timedelta(days=200), backups=[bak], registry=False)
    assert again.install_id == lic.install_id and again.until == lic.until and again.days_left == 165
    assert main.exists()                                   # written back


def test_the_renewal_code(tmp_path):
    start = dt.date(2026, 1, 1)
    lic = L.License(tmp_path / "a.json", today=start + dt.timedelta(days=400))
    lic.data["until"] = (start + dt.timedelta(days=365)).isoformat()
    assert not lic.renew("0000-0000-0000")
    code = L.renewal_code(lic.install_id, 1)
    assert lic.renew(code) and not lic.expired and lic.renewals == 1
    assert not lic.renew(code)                             # a code opens one year only
    import hashlib
    import hmac
    rw = hmac.new(L._KEY.encode(), f"{lic.install_id}:1".encode(), hashlib.sha256).hexdigest()[:12].upper()
    assert L._clean(code) != rw                            # not ReadWanicn2027's code
