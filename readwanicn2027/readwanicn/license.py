# SPDX-License-Identifier: GPL-3.0-or-later
"""One year of use from the first start; after that the program asks for
a renewal code from the developer, which opens another year.

The code is bound to this installation's ID and to the renewal number, so
a code given to one office does not open another or open a second year.
It is ``HMAC-SHA256(key, "<id>:<n>")`` cut to 12 hex digits; the key is
written into ``_license_key.py`` when the installer is built (from a
secret of the build, not from the repository), and the developer makes
codes with ``tools/readwanicn_code.py`` and the same key.

This is a reminder to renew, not copy protection: someone who deletes the
program's settings, or edits it, can get round it.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path

PERIOD_DAYS = 365
WARN_DAYS = 30
CONTACT_PHONE = "093-5838348"
CONTACT_LINE = "https://line.me/ti/p/E-p-C9tCEx"

try:                                   # written by the build
    from ._license_key import KEY as _KEY
except ImportError:                    # running from source
    _KEY = "readwanicn-development-key"


THAI_MONTHS = ("มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม",
               "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม")
THAI_MONTHS_SHORT = ("ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.")


def thai_date(d: dt.date | None, short: bool = False) -> str:
    """18 พฤศจิกายน 2570 / 18 พ.ย. 70"""
    if d is None:
        return "—"
    if short:
        return f"{d.day} {THAI_MONTHS_SHORT[d.month - 1]} {(d.year + 543) % 100:02d}"
    return f"{d.day} {THAI_MONTHS[d.month - 1]} {d.year + 543}"


def state_file() -> Path:
    base = os.environ.get("APPDATA") or os.path.join(Path.home(), ".config")
    return Path(base) / "ReadWanicn2027" / "license.json"


def backup_files(path: Path) -> list:
    """Other places the year is kept, so that an update, a reinstall or a cleaned settings folder
    never starts a new year: beside the local application data, and the registry on Windows."""
    base = os.environ.get("LOCALAPPDATA") or os.path.join(Path.home(), ".local", "share")
    out = [Path(base) / "ReadWanicn2027" / "license-backup.json"]
    return [b for b in out if b.resolve() != Path(path).resolve()]


REG_KEY = r"Software\ReadWanicn2027"


def _reg_read() -> dict | None:
    if os.name != "nt" or os.environ.get("READWANICN_NO_REGISTRY"):
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
            return json.loads(winreg.QueryValueEx(k, "license")[0])
    except (OSError, ValueError):
        return None


def _reg_write(data: dict) -> None:
    if os.name != "nt" or os.environ.get("READWANICN_NO_REGISTRY"):
        return
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
            winreg.SetValueEx(k, "license", 0, winreg.REG_SZ, json.dumps(data))
    except OSError:
        pass


def _valid(data) -> bool:
    return isinstance(data, dict) and {"id", "until", "n"} <= set(data)


def _best(records: list) -> dict | None:
    """The record to keep: the most renewals, then the earliest start (a fresh year made by a lost
    file never wins over the real first installation)."""
    good = [r for r in records if _valid(r)]
    if not good:
        return None
    return max(good, key=lambda r: (int(r.get("n", 0)), [-ord(c) for c in str(r.get("start", "9999"))]))


def renewal_code(install_id: str, n: int, key: str | None = None) -> str:
    digest = hmac.new((key or _KEY).encode(), f"{install_id.upper()}:{n}".encode(),
                      hashlib.sha256).hexdigest()[:12].upper()
    return "-".join(digest[i:i + 4] for i in range(0, 12, 4))


def _clean(code: str) -> str:
    return "".join(c for c in code.upper() if c.isalnum())


class License:
    def __init__(self, path: Path | None = None, today: dt.date | None = None, backups: list | None = None,
                 registry: bool | None = None):
        # the real settings file keeps backup copies (and the registry on Windows); a file given
        # explicitly (tests) keeps only the backups given with it
        self.backups = backups if backups is not None else (backup_files(state_file()) if path is None else [])
        self.registry = (path is None) if registry is None else registry
        self.path = path or state_file()
        self.today = today or dt.date.today()
        self.data = self._load()

    def _load(self) -> dict:
        """The year as first installed: from the settings file, or — when it was lost in an update,
        a reinstall or a clean-up — from its backup copies. Only a computer with none of them
        starts a new year."""
        records = []
        for f in [self.path] + list(self.backups):
            try:
                records.append(json.loads(Path(f).read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass
        if self.registry:
            records.append(_reg_read())
        data = _best(records)
        if data is None:
            data = {"id": secrets.token_hex(4).upper(), "start": self.today.isoformat(),
                    "until": (self.today + dt.timedelta(days=PERIOD_DAYS)).isoformat(), "n": 0}
        self._save(data)
        return data

    def _save(self, data: dict) -> None:
        text = json.dumps(data, indent=1)
        for f in [self.path] + list(self.backups):
            try:
                Path(f).parent.mkdir(parents=True, exist_ok=True)
                Path(f).write_text(text, encoding="utf-8")
            except OSError:
                pass
        if self.registry:
            _reg_write(data)

    @property
    def install_id(self) -> str:
        return self.data["id"]

    @property
    def until(self) -> dt.date:
        return dt.date.fromisoformat(self.data["until"])

    @property
    def start(self) -> dt.date | None:
        try:
            return dt.date.fromisoformat(self.data.get("start", ""))
        except ValueError:
            return None

    @property
    def renewals(self) -> int:
        return int(self.data.get("n", 0))

    @property
    def status(self) -> str:
        if self.expired:
            return "หมดอายุการใช้งาน"
        if self.days_left <= WARN_DAYS:
            return "ใกล้หมดอายุ"
        return "ใช้งานได้"

    @property
    def days_left(self) -> int:
        return (self.until - self.today).days

    @property
    def expired(self) -> bool:
        return self.days_left < 0

    def renew(self, code: str) -> bool:
        """Another year (from today, or from the old end when it is still
        ahead) when ``code`` is the next renewal code of this installation."""
        n = int(self.data["n"]) + 1
        if not hmac.compare_digest(_clean(code), _clean(renewal_code(self.install_id, n))):
            return False
        start = max(self.today, self.until)
        self.data.update(n=n, until=(start + dt.timedelta(days=PERIOD_DAYS)).isoformat())
        self._save(self.data)
        return True
