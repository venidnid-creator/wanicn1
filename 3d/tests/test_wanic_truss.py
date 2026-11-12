# SPDX-License-Identifier: GPL-3.0-or-later
"""Truss: the stiffness solver against hand results, the forms, the design."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import wanic_truss as T  # noqa: E402


def test_triangle_by_hand():
    # a simple triangle: span 6, rise 2, 1000 kg at the apex
    t = T.custom([(0, 0), (6, 0), (3, 2)], [(0, 1, "bottom"), (0, 2, "top"), (2, 1, "top")],
                 {0: "pin", 1: "roller"})
    r = T.solve(t, {2: (0.0, -1000.0)})
    th = math.atan2(2, 3)
    assert abs(r["force"][0] - 500 / math.tan(th)) < 1e-6          # tie in tension
    assert abs(r["force"][1] + 500 / math.sin(th)) < 1e-6          # rafter in compression
    assert abs(r["reactions"][0][1] - 500) < 1e-6
    assert abs(r["reactions"][1][1] - 500) < 1e-6


def test_every_form_is_stable_and_in_equilibrium():
    for kind in ("howe", "pratt", "fink", "warren", "kingpost", "parallel", "arch"):
        t = T.make(kind, 12.0, 2.0, 8, 0.8)
        d = T.design(t, 12.0, 4.0, 40.0, 30.0, "pipe")
        down = -sum(f[1] for f in d.loads.values())
        up = sum(r[1] for r in d.result["reactions"].values())
        assert abs(down - up) < 1e-6 * down, kind
        assert max(r[6] for r in d.rows) <= 1.0 + 1e-9, kind
        assert d.weight > 0 and d.plate["t"] >= 6


def test_parallel_chords_follow_beam_analogy():
    t = T.make("parallel", 12.0, 0.0, 12, 1.0)
    loads = T.roof_loads(t, 12.0, 4.0, 40.0, 30.0)
    r = T.solve(t, loads)
    W = -sum(f[1] for f in loads.values())
    bot = max(N for (a, b, g), N in zip(t.members, r["force"]) if g == "bottom")
    top = min(N for (a, b, g), N in zip(t.members, r["force"]) if g == "top")
    M = W * 12 / 8
    assert abs(bot - M / 1.0) / bot < 0.05 and abs(-top - M / 1.0) / M < 0.05   # chords ≈ M/h


def test_unstable_raises():
    t = T.custom([(0, 0), (4, 0), (4, 2), (0, 2)], [(0, 1, "bottom"), (1, 2, "web"), (2, 3, "top"), (3, 0, "web")],
                 {0: "pin", 1: "roller"})
    try:
        T.solve(t, {2: (0.0, -100.0)})
    except ValueError:
        return
    raise AssertionError("a square without a diagonal must be unstable")


def test_compression_allowable_drops_with_length():
    s = T.CATALOG["pipe"][5]
    a1, _ = T.allowable(s, 0.5, True)
    a2, _ = T.allowable(s, 3.0, True)
    at, _ = T.allowable(s, 3.0, False)
    assert a2 < a1 < at


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v()
    print("ok")
