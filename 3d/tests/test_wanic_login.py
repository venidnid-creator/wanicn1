"""The suite's sign-in: one module shipped three times, the account kept
as a hash, a session handed from the start screen to the programs."""
from pathlib import Path

from core import wanic_login as L

ROOT = Path(__file__).resolve().parents[2]


def test_the_three_copies_are_one():
    me = (ROOT / "3d" / "core" / "wanic_login.py").read_bytes()
    assert (ROOT / "launcher" / "wanic_login.py").read_bytes() == me
    assert (ROOT / "cad" / "core" / "wanic_login.py").read_bytes() == me


def test_the_account_and_the_session(monkeypatch):
    assert not L.check("someone@example.com", "x")
    assert not L.check("", "")
    src = (ROOT / "3d" / "core" / "wanic_login.py").read_text(encoding="utf-8")
    assert "อดใจรอ" in L.NOTICE and "อยู่ระหว่างการพัฒนา" in L.NOTICE
    assert "password" not in src.split("_ACCOUNTS")[1][:120].lower()      # only a hash is kept
    monkeypatch.setenv(L.ENV, L.session_token())
    assert L.signed_in()
    monkeypatch.setenv(L.ENV, "wrong")
    monkeypatch.setattr(L, "_remembered", lambda: False)
    assert not L.signed_in()
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "x")
    assert L.require()
