# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""แผนที่ตั้งโครงการ: the satellite window, its tiles and the location sheet."""
from __future__ import annotations

import math

from core import wanic_drawings as D
from core import wanic_road_sheets as RS
from core import wanic_sitemap as M
from tests.test_wanic_road_sheets import _analysis

#: the tiny JPEG every fake tile is
JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c140d0c0b0b0c1912"
    "130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432ffc0000b080001"
    "000101011100ffc4001f0000010501010101010100000000000000000102030405060708090a0bffc400b5100002010303"
    "020403050504040000017d01020300041105122131410613516107227114328191a1082342b1c11552d1f02433627282"
    "090a161718191a25262728292a3435363738393a434445464748494a535455565758595a636465666768696a7374757677"
    "78797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3"
    "d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffda0008010100003f00fbd3ffd9")


def test_web_mercator():
    assert M.world_px(0.0, 0.0, 0) == (128.0, 128.0)
    x, y = M.world_px(13.7563, 100.5018, 10)
    # the slippy-map formula, written the other way: y = (1 − asinh(tan φ) / π) / 2 · 2^z
    ty = (1 - math.asinh(math.tan(math.radians(13.7563))) / math.pi) / 2 * 2 ** 10
    assert (int(x // 256), int(y // 256)) == (797, int(ty)) == (797, 472)   # Bangkok's tile
    lat, lon = M.lat_lon(x, y, 10)
    assert abs(lat - 13.7563) < 1e-9 and abs(lon - 100.5018) < 1e-9
    assert abs(M.metres_per_px(0, 0) - 156543.03) < 0.01


def test_the_window_holds_the_road_at_the_deepest_zoom():
    pts = [(13.146992, 101.268457), (13.155, 101.264), (13.165330, 101.260072)]
    v = M.fit_view(pts, 228.0, 242.0, max_px=2400)
    assert v.w_px <= 2400 and abs(v.w_px / v.h_px - 228 / 242) < 1e-9
    for la, lo in pts:
        x, y = v.to_box(la, lo)
        assert 0 < x < 228 and 0 < y < 242
    deeper = M.fit_view(pts, 228.0, 242.0, max_px=2400, max_zoom=v.z + 1)
    assert deeper.z == v.z == 17
    assert 8 < v.ground_per_mm() < 12                   # about 1:10 000 on the sheet
    far = M.fit_view(pts, 95, 86, max_px=700, zoom_out=3)
    assert far.z <= v.z - 3
    tiles = v.tiles()
    assert len(tiles) == len(set(tiles)) and 60 < len(tiles) < 120
    xs = sorted({t[0] for t in tiles})
    assert xs == list(range(xs[0], xs[-1] + 1))
    dx, dy = v.tile_offset(*tiles[0])
    assert -256 < dx <= 0 and -256 < dy <= 0


def test_tiles_are_downloaded_and_holes_left(monkeypatch):
    v = M.fit_view([(13.15, 101.26), (13.16, 101.27)], 100, 100, max_px=600)
    asked = []

    def opener(url, timeout):
        asked.append(url)
        if len(asked) == 2:
            raise OSError("no tile")
        return JPEG
    got = M.fetch_tiles(v, opener=opener, workers=1)
    assert len(asked) == len(v.tiles()) and len(got) == len(asked) - 1
    assert asked[0].startswith("https://server.arcgisonline.com/") and f"/{v.z}/" in asked[0]
    monkeypatch.setenv("WANIC_OFFLINE", "1")
    assert M.fetch_tiles(v) == {}


def test_scale_bar_and_place_names():
    assert M.nice_bar(10.46, 50) == 500
    assert M.nice_bar(0.5, 50) == 20
    assert M.place_parts("ต.หนองใหญ่ อ.หนองใหญ่ จ.ชลบุรี") == [
        ("ตำบล", "หนองใหญ่"), ("อำเภอ", "หนองใหญ่"), ("จังหวัด", "ชลบุรี")]
    assert M.place_parts("แขวงลุมพินี เขตปทุมวัน จังหวัดกรุงเทพมหานคร")[1] == ("อำเภอ", "ปทุมวัน")
    assert M.place_parts("") == [("ตำบล", ""), ("อำเภอ", ""), ("จังหวัด", "")]


def _site(an, mode="tiles"):
    main, vic = RS.site_views(an)
    if mode == "file":
        return {"mode": "file", "image": JPEG, "size": (1266, 882), "main": None,
                "vicinity": vic, "vicinity_image": JPEG}
    return {"mode": mode, "main": main, "image": JPEG if mode == "tiles" else None,
            "vicinity": vic, "vicinity_image": JPEG}


def test_the_location_sheet_opens_the_set():
    an, shots = _analysis()
    info = {"project": "ถนนทดสอบ", "location": "ต.หนองใหญ่ อ.หนองใหญ่ จ.ชลบุรี"}
    S = RS.build_road_set(an, info, shots, site=_site(an))
    loc = S[0]
    assert [s.code for s in S][:3] == ["G-01", "G-02", "G-03"] and S[0].number == 1
    t = " ".join(loc.texts())
    for word in ("แผนที่ตั้งโครงการ", "แผนที่บริเวณใกล้เคียง", "ตำบล", "อำเภอ", "จังหวัด",
                 "หนองใหญ่", "ชลบุรี", "Esri", "เริ่มต้น 0+000.00", "0+100", "PI-1", "ม.",
                 "13.1", "101.2", "ความยาวทาง"):
        assert word in t, word
    assert loc.count("image") == 2
    assert "ข้อมูลการออกแบบ" in " ".join(S[1].texts())
    x0, y0, x1, y1 = RS.SITE_BOX
    cl = [it for it in loc.items if it[0] == "poly" and it[2] == "sat"]
    assert cl and all(x0 < x < x1 and y0 < y < y1 for x, y in cl[0][1])
    assert loc.colors["sat"] == (255, 214, 0)
    text = D.dxf_bytes(S[:1]).decode("cp874")             # the picture is left out of a DXF
    assert "แผนที่ตั้งโครงการ" in text and text.rstrip().endswith("EOF")


def test_a_google_earth_picture_and_no_picture():
    an, shots = _analysis()
    loc = RS.build_road_set(an, {"location": ""}, shots, ("G",), _site(an, "file"))[0]
    img = next(it for it in loc.items if it[0] == "image" and it[1][2] - it[1][0] > 150)
    x0, y0, x1, y1 = img[1]
    assert math.isclose((x1 - x0) / (y1 - y0), 1266 / 882, rel_tol=1e-6)
    assert "Google Earth Pro" in " ".join(loc.texts())
    assert not [it for it in loc.items if it[0] == "poly" and it[2] == "sat" and len(it[1]) > 4]
    none = RS.build_road_set(an, {}, shots, ("G",), _site(an, "none"))[0]
    t = " ".join(none.texts())
    assert "ยังไม่มีภาพถ่ายดาวเทียม" in t and none.count("image") == 1   # the vicinity only
    assert "PI-1" in t                                    # the road is still drawn


def test_the_dxf_has_no_white_blocks_over_the_text():
    """A CAD shows no photograph: the plates under the labels, the white
    scale-bar squares and the picture's stand-in are left out of the DXF
    (they printed as white blocks over the text), the labels stay."""
    an, shots = _analysis()
    for mode in ("tiles", "none"):
        S = RS.build_road_set(an, {"location": "ต.หนองใหญ่ อ.หนองใหญ่ จ.ชลบุรี"}, shots,
                              ("G", "PP"), _site(an, mode))
        text = D.dxf_bytes(S).decode("cp874")
        solids = text.split("\n0\nSOLID\n")[1:]
        layers = {b.split("\n")[1] for b in solids}
        assert not layers & {"HALO", "PHOTO"}, layers
        assert "0+100" in text and "PI-1" in text and "E 7" in text
    # the title column: no label over the signature, the name under the line
    t = " ".join(S[0].texts())
    assert "ผู้จัดทำ" not in t and "(นายเวนิช ธัมมะวงษ์)" in t
