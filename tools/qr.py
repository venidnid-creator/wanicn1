# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""A small QR Code encoder (ISO/IEC 18004): byte mode, error correction
level M, versions 1–10, the mask with the lowest penalty. Pure Python —
used to make the launcher's «ติดต่อผู้พัฒนาระบบ» code:

    python tools/qr.py "tel:0935838348" branding/png/contact-qr.png
"""
from __future__ import annotations

import sys

# (total codewords, ec codewords per block, blocks group 1, data cw/block g1,
#  blocks group 2, data cw/block g2) for level M, versions 1..10
_M = {1: (26, 10, 1, 16, 0, 0), 2: (44, 16, 1, 28, 0, 0), 3: (70, 26, 1, 44, 0, 0),
      4: (100, 18, 2, 32, 0, 0), 5: (134, 24, 2, 43, 0, 0), 6: (172, 16, 4, 27, 0, 0),
      7: (196, 18, 4, 31, 0, 0), 8: (242, 22, 2, 38, 2, 39), 9: (292, 22, 3, 36, 2, 37),
      10: (346, 26, 4, 43, 1, 44)}
_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34],
          7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50]}

_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _gmul(a, b):
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def _rs(data, n):
    gen = [1]
    for i in range(n):
        gen = [a ^ b for a, b in zip(gen + [0], [0] + [_gmul(g, _EXP[i]) for g in gen])]
    rem = list(data) + [0] * n
    for i in range(len(data)):
        c = rem[i]
        if c:
            for j in range(1, len(gen)):
                rem[i + j] ^= _gmul(gen[j], c)
    return rem[len(data):]


def _codewords(data: bytes):
    for ver in range(1, 11):
        total, ec, b1, d1, b2, d2 = _M[ver]
        cap = b1 * d1 + b2 * d2
        cbits = 8 if ver < 10 else 16
        if 4 + cbits + 8 * len(data) <= cap * 8:
            break
    else:
        raise ValueError("ข้อความยาวเกินไป")
    bits = [0, 1, 0, 0] + [int(b) for b in format(len(data), f"0{cbits}b")]
    for byte in data:
        bits += [int(b) for b in format(byte, "08b")]
    bits += [0] * min(4, cap * 8 - len(bits))
    bits += [0] * (-len(bits) % 8)
    cws = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = (0xEC, 0x11)
    i = 0
    while len(cws) < cap:
        cws.append(pad[i % 2])
        i += 1
    blocks, k = [], 0
    for cnt, size in ((b1, d1), (b2, d2)):
        for _ in range(cnt):
            blocks.append(cws[k:k + size])
            k += size
    ecs = [_rs(b, ec) for b in blocks]
    out = []
    for i in range(max(len(b) for b in blocks)):
        out += [b[i] for b in blocks if i < len(b)]
    for i in range(ec):
        out += [e[i] for e in ecs]
    return ver, out


def _bch(value, poly, bits):
    v = value << bits
    top = poly.bit_length() - 1
    while v.bit_length() - 1 >= top:
        v ^= poly << (v.bit_length() - 1 - top)
    return (value << bits) | v


def encode(text: str):
    """The matrix (list of rows of 0/1, 1 = dark) of ``text``."""
    ver, cws = _codewords(text.encode("utf-8"))
    n = 17 + 4 * ver
    grid = [[None] * n for _ in range(n)]

    def finder(r, c):
        for i in range(-1, 8):
            for j in range(-1, 8):
                rr, cc = r + i, c + j
                if 0 <= rr < n and 0 <= cc < n:
                    dark = (0 <= i <= 6 and j in (0, 6)) or (0 <= j <= 6 and i in (0, 6)) \
                        or (2 <= i <= 4 and 2 <= j <= 4)
                    grid[rr][cc] = 1 if dark else 0
    finder(0, 0)
    finder(0, n - 7)
    finder(n - 7, 0)
    for i in range(8, n - 8):
        grid[6][i] = grid[i][6] = 1 if i % 2 == 0 else 0
    pos = _ALIGN[ver]
    for r in pos:
        for c in pos:
            if grid[r][c] is not None:
                continue
            for i in range(-2, 3):
                for j in range(-2, 3):
                    grid[r + i][c + j] = 1 if max(abs(i), abs(j)) != 1 else 0
    grid[n - 8][8] = 1                                   # dark module
    reserved = [[v is not None for v in row] for row in grid]
    for i in range(9):                                   # format areas
        reserved[8][i] = reserved[i][8] = True
    for i in range(8):
        reserved[8][n - 1 - i] = reserved[n - 1 - i][8] = True
    if ver >= 7:
        for i in range(6):
            for j in range(3):
                reserved[i][n - 11 + j] = reserved[n - 11 + j][i] = True
    bits = []
    for cw in cws:
        bits += [int(b) for b in format(cw, "08b")]
    data = [[0] * n for _ in range(n)]
    k = 0
    col = n - 1
    up = True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(n - 1, -1, -1) if up else range(n)
        for r in rows:
            for c in (col, col - 1):
                if not reserved[r][c]:
                    data[r][c] = bits[k] if k < len(bits) else 0
                    k += 1
        up = not up
        col -= 2
    masks = [lambda r, c: (r + c) % 2 == 0, lambda r, c: r % 2 == 0,
             lambda r, c: c % 3 == 0, lambda r, c: (r + c) % 3 == 0,
             lambda r, c: (r // 2 + c // 3) % 2 == 0,
             lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
             lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
             lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0]
    best = None
    for m, fn in enumerate(masks):
        g = [[grid[r][c] if reserved[r][c] else data[r][c] ^ (1 if fn(r, c) else 0)
              for c in range(n)] for r in range(n)]
        fmt = _bch((0b00 << 3) | m, 0b10100110111, 10) ^ 0b101010000010010   # M = 00
        fb = [(fmt >> i) & 1 for i in range(15)]
        for i in range(6):                         # g[row][col]
            g[i][8] = fb[i]
        g[7][8], g[8][8], g[8][7] = fb[6], fb[7], fb[8]
        for i in range(9, 15):
            g[8][14 - i] = fb[i]
        for i in range(8):
            g[8][n - 1 - i] = fb[i]
        for i in range(8, 15):
            g[n - 15 + i][8] = fb[i]
        g[n - 8][8] = 1
        if ver >= 7:
            vb = _bch(ver, 0b1111100100101, 12)
            for i in range(18):
                b = (vb >> i) & 1
                g[i // 3][n - 11 + i % 3] = b
                g[n - 11 + i % 3][i // 3] = b
        p = _penalty(g)
        if best is None or p < best[0]:
            best = (p, g)
    return best[1]


def _penalty(g):
    n = len(g)
    p = 0
    for lines in (g, [list(c) for c in zip(*g)]):
        for row in lines:
            run, prev = 0, None
            for v in row:
                if v == prev:
                    run += 1
                else:
                    if run >= 5:
                        p += run - 2
                    run, prev = 1, v
            if run >= 5:
                p += run - 2
            s = "".join(map(str, row))
            p += 40 * (s.count("10111010000") + s.count("00001011101"))
    for r in range(n - 1):
        for c in range(n - 1):
            if g[r][c] == g[r][c + 1] == g[r + 1][c] == g[r + 1][c + 1]:
                p += 3
    dark = sum(map(sum, g)) * 100 / (n * n)
    p += int(abs(dark - 50) // 5) * 10
    return p


def save_png(matrix, path, scale=10, border=4):
    from PIL import Image
    n = len(matrix)
    size = (n + 2 * border) * scale
    img = Image.new("L", (size, size), 255)
    px = img.load()
    for r in range(n):
        for c in range(n):
            if matrix[r][c]:
                for i in range(scale):
                    for j in range(scale):
                        px[(c + border) * scale + j, (r + border) * scale + i] = 0
    img.save(path)


if __name__ == "__main__":
    save_png(encode(sys.argv[1]), sys.argv[2])
