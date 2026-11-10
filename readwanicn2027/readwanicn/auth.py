# SPDX-License-Identifier: GPL-3.0-or-later
"""Sign-in: user names and salted PBKDF2 password hashes in a JSON file
beside the user's settings. The password itself is never stored.

This keeps casual users out of a desktop program; it is not a server
login -- anyone who can replace the program's files can bypass it.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path

ITERATIONS = 200_000
#: The first account, created when no user file exists yet.
DEFAULT_USER = "Wanicn"
_DEFAULT_SALT = bytes.fromhex("7a1c4e9f0b2d6a83c5e1f40d9b7a2c66")
#: PBKDF2 of the first account's password: the source carries no password.
DEFAULT_HASH = "f7bb126423a50e6fe31b86119a9dc454de6f2fdbfe56350d544ee708af09f19b"


def _hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS).hex()


def users_file() -> Path:
    base = os.environ.get("APPDATA") or os.path.join(Path.home(), ".config")
    return Path(base) / "ReadWanicn2027" / "users.json"


def _default_users() -> dict:
    return {DEFAULT_USER: {"salt": _DEFAULT_SALT.hex(), "hash": DEFAULT_HASH}}


def load_users(path: Path | None = None) -> dict:
    path = path or users_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data:
            return data
    except (OSError, ValueError):
        pass
    return _default_users()


def save_users(users: dict, path: Path | None = None) -> None:
    path = path or users_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(users, indent=2), encoding="utf-8")


def check(user: str, password: str, path: Path | None = None) -> bool:
    record = load_users(path).get(user.strip())
    if not record:
        return False
    got = _hash(password, bytes.fromhex(record["salt"]))
    return hmac.compare_digest(got, record["hash"])


def set_password(user: str, password: str, path: Path | None = None) -> None:
    users = load_users(path)
    salt = os.urandom(16)
    users[user.strip()] = {"salt": salt.hex(), "hash": _hash(password, salt)}
    save_users(users, path)

