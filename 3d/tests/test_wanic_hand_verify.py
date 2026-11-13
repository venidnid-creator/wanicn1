# SPDX-License-Identifier: GPL-3.0-or-later
"""The program against hand calculations from the textbooks (tools/verify_hand_calc.py):
every compared value of the sample house within its tolerance."""
import importlib.util
import os


def test_program_matches_the_hand_calculations():
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "verify_hand_calc.py")
    spec = importlib.util.spec_from_file_location("verify_hand_calc", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert len(mod.rows) >= 25
    bad = [(r["item"], r["hand"], r["prog"]) for r in mod.rows if not r["ok"]]
    assert not bad, bad
