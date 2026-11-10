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


def state_file() -> Path:
    base = os.environ.get("APPDATA") or os.path.join(Path.home(), ".config")
    return Path(base) / "ReadWanicn2027" / "license.json"


def renewal_code(install_id: str, n: int, key: str | None = None) -> str:
    digest = hmac.new((key or _KEY).encode(), f"{install_id.upper()}:{n}".encode(),
                      hashlib.sha256).hexdigest()[:12].upper()
    return "-".join(digest[i:i + 4] for i in range(0, 12, 4))


def _clean(code: str) -> str:
    return "".join(c for c in code.upper() if c.isalnum())


class License:
    def __init__(self, path: Path | None = None, today: dt.date | None = None):
        self.path = path or state_file()
        self.today = today or dt.date.today()
        self.data = self._load()

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if {"id", "until", "n"} <= set(data):
                return data
        except (OSError, ValueError):
            pass
        data = {"id": secrets.token_hex(4).upper(), "start": self.today.isoformat(),
                "until": (self.today + dt.timedelta(days=PERIOD_DAYS)).isoformat(), "n": 0}
        self._save(data)
        return data

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=1), encoding="utf-8")

    @property
    def install_id(self) -> str:
        return self.data["id"]

    @property
    def until(self) -> dt.date:
        return dt.date.fromisoformat(self.data["until"])

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
