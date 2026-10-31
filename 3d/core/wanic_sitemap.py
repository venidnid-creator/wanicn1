# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""The project's site map: a satellite picture of the place, the way a
road study opens its drawing book with แผนที่ตั้งโครงการ.

Web-map tiles (256 px squares, Web Mercator, zoom 0–19) are asked for
the window that holds the alignment, at the zoom that gives the picture
about as many pixels as the printed box can show; the panel stitches the
tiles (Qt) and :mod:`core.wanic_road_sheets` draws the alignment on top
in paper millimetres.  Pure Python: the geometry, the tile list, the
download (any ``opener``) -- no Qt.

Imagery: Esri World Imagery, credited on the sheet as its terms ask.
A picture saved from Google Earth Pro (ไฟล์ ▸ บันทึก ▸ บันทึกภาพ…) can
be used instead; Google's own credit is printed on that picture.
"""
from __future__ import annotations

import math
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

TILE = 256
MAX_ZOOM = 19
SOURCES = {
    "esri": ("Esri World Imagery",
             "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
             "MapServer/tile/{z}/{y}/{x}",
             "ภาพถ่ายดาวเทียม: Esri, Maxar, Earthstar Geographics และผู้ร่วมให้ข้อมูล GIS"),
}
EARTH = 6378137.0


def world_px(lat: float, lon: float, z: int) -> tuple:
    """Web Mercator pixel of a point at zoom ``z`` (x east, y south)."""
    n = TILE * 2 ** z
    lat = max(-85.05112878, min(85.05112878, lat))
    s = math.sin(math.radians(lat))
    return ((lon + 180.0) / 360.0 * n,
            (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n)


def lat_lon(px: float, py: float, z: int) -> tuple:
    n = TILE * 2 ** z
    lon = px / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * py / n))))
    return lat, lon


def metres_per_px(lat: float, z: int) -> float:
    return 2 * math.pi * EARTH * math.cos(math.radians(lat)) / (TILE * 2 ** z)


@dataclass
class View:
    """A window of the world at one zoom, printed into a box of
    ``w_mm`` × ``h_mm``: world pixel (x0, y0) is the box's top left."""
    z: int
    x0: float
    y0: float
    w_px: float
    h_px: float
    w_mm: float
    h_mm: float

    @property
    def mm_per_px(self) -> float:
        return self.w_mm / self.w_px

    def to_box(self, lat: float, lon: float) -> tuple:
        """Paper mm from the box's lower-left corner (y up)."""
        px, py = world_px(lat, lon, self.z)
        return ((px - self.x0) * self.mm_per_px, (self.y0 + self.h_px - py) * self.mm_per_px)

    @property
    def centre(self) -> tuple:
        return lat_lon(self.x0 + self.w_px / 2, self.y0 + self.h_px / 2, self.z)

    def ground_per_mm(self) -> float:
        """Metres of ground in one millimetre of paper (at the centre)."""
        return metres_per_px(self.centre[0], self.z) / self.mm_per_px

    def tiles(self) -> list:
        """(x, y) of every tile under the window."""
        n = 2 ** self.z
        xs = range(math.floor(self.x0 / TILE), math.floor((self.x0 + self.w_px - 1e-9) / TILE) + 1)
        ys = range(max(0, math.floor(self.y0 / TILE)),
                   min(n - 1, math.floor((self.y0 + self.h_px - 1e-9) / TILE)) + 1)
        return [(x % n, y) for y in ys for x in xs]

    def tile_offset(self, x: int, y: int) -> tuple:
        """Where tile (x, y)'s top left falls in the window, pixels (the
        x unwrapped near the window)."""
        n = 2 ** self.z
        tx = x
        while tx * TILE < self.x0 - TILE:
            tx += n
        return tx * TILE - self.x0, y * TILE - self.y0


def fit_view(points: list, w_mm: float, h_mm: float, max_px: float = 2400.0,
             margin: float = 0.12, max_zoom: int = MAX_ZOOM, zoom_out: int = 0) -> View:
    """The window that holds every (lat, lon) of ``points`` with a margin,
    shaped like the box, at the deepest zoom whose window is at most
    ``max_px`` wide; ``zoom_out`` levels further out (a vicinity map)."""
    if not points:
        raise ValueError("ไม่มีจุดสำหรับแผนที่")
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    aspect = w_mm / h_mm
    z = max_zoom
    while True:
        xa, ya = world_px(max(lats), min(lons), z)
        xb, yb = world_px(min(lats), max(lons), z)
        bw, bh = max(xb - xa, 1.0), max(yb - ya, 1.0)
        bw, bh = bw * (1 + 2 * margin), bh * (1 + 2 * margin)
        w = max(bw, bh * aspect, 64.0)
        if w <= max_px or z == 0:
            break
        z -= 1
    if zoom_out:
        z = max(0, z - zoom_out)
        xa, ya = world_px(max(lats), min(lons), z)
        xb, yb = world_px(min(lats), max(lons), z)
    h = w / aspect
    cx, cy = (xa + xb) / 2, (ya + yb) / 2
    return View(z, cx - w / 2, cy - h / 2, w, h, w_mm, h_mm)


def tile_url(source: str, z: int, x: int, y: int) -> str:
    return SOURCES[source][1].format(z=z, x=x, y=y)


def fetch_tiles(view: View, source: str = "esri", opener=None, workers: int = 8,
                timeout: float = 20.0, progress=None) -> dict:
    """{(x, y): image bytes} of the window's tiles (missing ones left out).
    ``opener(url, timeout) -> bytes`` (the internet by default; nothing
    when WANIC_OFFLINE is set)."""
    if os.environ.get("WANIC_OFFLINE") and opener is None:
        return {}
    if opener is None:
        import urllib.request

        from core import branding

        def opener(url, timeout):
            req = urllib.request.Request(url, headers={
                "User-Agent": f"WANICNSURVEY/{getattr(branding, 'PRODUCT', 'WANIC')} site map"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
    todo = view.tiles()
    got: dict = {}

    def one(xy):
        try:
            return xy, opener(tile_url(source, view.z, *xy), timeout)
        except Exception:                               # noqa: BLE001 -- a hole in the map
            return xy, None
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for i, (xy, data) in enumerate(pool.map(one, todo), 1):
            if data:
                got[xy] = data
            if progress:
                progress(i, len(todo))
    return got


def nice_bar(ground_per_mm: float, room_mm: float = 60.0) -> float:
    """A scale bar length in metres (1, 2, 5 × 10ⁿ) that fits ``room_mm``."""
    most = ground_per_mm * room_mm
    best = 1.0
    for e in range(0, 7):
        for m in (1, 2, 5):
            v = m * 10 ** e
            if v <= most:
                best = v
    return best


_PLACE = (("ตำบล", ("ต.", "ตำบล", "แขวง")), ("อำเภอ", ("อ.", "อำเภอ", "เขต")),
          ("จังหวัด", ("จ.", "จังหวัด")))


def place_parts(text: str) -> list:
    """[("ตำบล", name), ("อำเภอ", name), ("จังหวัด", name)] read from
    ``"ต.หนองใหญ่ อ.หนองใหญ่ จ.ชลบุรี"`` (or the long forms)."""
    import re
    out = []
    for label, pre in _PLACE:
        alt = "|".join(re.escape(p) for p in sorted(pre, key=len, reverse=True))
        m = re.search(rf"(?:^|\s)(?:{alt})\s*([^\s]+)", text or "")
        out.append((label, m.group(1) if m else ""))
    return out
