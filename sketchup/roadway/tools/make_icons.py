"""สร้างไอคอนแถบเครื่องมือ RoadWay (16 และ 24 px) — วาดที่ 96 px แล้วย่อ"""
import os, sys
from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(__file__), "..", "src", "roadway", "icons")
BLUE, ROAD, RED, GRAY, GREEN, ORANGE = (31, 95, 174), (60, 60, 62), (190, 40, 40), (150, 150, 150), (40, 140, 80), (230, 140, 30)
W = 96


def canvas():
    im = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def profile(d):
    d.line([(10, 80), (40, 40), (86, 30)], fill=GRAY, width=6)
    d.polygon([(4, 66), (28, 66), (28, 70), (18, 70), (18, 88), (28, 88), (28, 92), (4, 92), (4, 88), (14, 88), (14, 70), (4, 70)], fill=BLUE)
    d.polygon([(40, 30), (86, 20), (90, 40), (44, 50)], fill=BLUE)


def profile_face(d):
    d.rectangle([8, 56, 36, 88], fill=ORANGE)
    d.line([(22, 72), (60, 40), (90, 34)], fill=GRAY, width=6)
    d.polygon([(52, 30), (90, 22), (92, 44), (56, 52)], fill=BLUE)


def assembly(d):
    d.line([(6, 80), (90, 50)], fill=GRAY, width=5)
    for x in (14, 42, 70):
        y = 77 - (x - 6) * 30 / 84
        d.rectangle([x - 5, y - 46, x + 5, y], fill=BLUE)
        d.ellipse([x - 10, y - 56, x + 10, y - 40], fill=ORANGE)


def road(d):
    d.polygon([(38, 6), (58, 6), (92, 90), (4, 90)], fill=ROAD)
    for y in (14, 38, 64):
        d.polygon([(46, y), (50, y), (51 + y // 10, y + 16), (45 - y // 10, y + 16)], fill=(250, 250, 250))
    d.line([(38, 6), (4, 90)], fill=(240, 200, 40), width=3)
    d.line([(58, 6), (92, 90)], fill=(240, 200, 40), width=3)


def bars(d, horizontal=True):
    if horizontal:
        d.rectangle([4, 26, 92, 70], outline=GRAY, width=4)
        for x in range(14, 90, 14):
            d.rectangle([x - 2, 22, x + 2, 74], fill=ORANGE)
        for y in (34, 62):
            d.line([(4, y), (92, y)], fill=RED, width=6)
    else:
        d.rectangle([28, 4, 68, 92], outline=GRAY, width=4)
        for y in range(12, 90, 14):
            d.rectangle([24, y - 2, 72, y + 2], fill=ORANGE)
        for x in (38, 58):
            d.line([(x, 4), (x, 92)], fill=RED, width=6)


def slab(d):
    d.polygon([(4, 60), (48, 84), (92, 60), (48, 36)], outline=GRAY, fill=(225, 225, 220))
    for i in range(1, 5):
        t = i / 5
        d.line([(4 + 44 * t, 60 - 24 * t), (48 + 44 * t, 84 - 24 * t)], fill=RED, width=3)
        d.line([(4 + 44 * t, 60 + 24 * t), (48 + 44 * t, 36 + 24 * t)], fill=RED, width=3)


def rebar_path(d):
    d.line([(8, 84), (8, 40), (40, 14), (88, 14)], fill=RED, width=9, joint="curve")
    d.ellipse([2, 78, 14, 90], fill=BLUE)
    d.ellipse([82, 8, 94, 20], fill=BLUE)


def quantity(d):
    d.rectangle([12, 6, 80, 90], fill=(255, 255, 255), outline=BLUE, width=5)
    for y in (24, 42, 60):
        d.line([(22, y), (70, y)], fill=GRAY, width=5)
    d.ellipse([52, 56, 92, 94], fill=GREEN)
    d.text((64, 62), "฿", fill=(255, 255, 255))
    d.line([(64, 66), (64, 86)], fill=(255, 255, 255), width=5)
    d.line([(60, 70), (78, 70)], fill=(255, 255, 255), width=4)
    d.line([(60, 82), (78, 82)], fill=(255, 255, 255), width=4)


def inspect(d):
    d.ellipse([10, 10, 62, 62], outline=BLUE, width=8)
    d.line([(56, 56), (88, 88)], fill=BLUE, width=12)


ICONS = {"profile": profile, "profile_face": profile_face, "assembly": assembly, "road": road,
         "rebar_beam": lambda d: bars(d, True), "rebar_column": lambda d: bars(d, False),
         "rebar_slab": slab, "rebar_path": rebar_path, "quantity": quantity, "inspect": inspect}

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, fn in ICONS.items():
        im, d = canvas()
        fn(d)
        for s in (16, 24):
            im.resize((s, s), Image.LANCZOS).save(os.path.join(OUT, f"{name}_{s}.png"))
        if "--preview" in sys.argv:
            im.save(os.path.join(OUT, "..", "..", "..", f"preview_{name}.png"))
    print("icons:", len(ICONS))
