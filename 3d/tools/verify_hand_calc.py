# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""รายงานเทียบผลการคำนวณ: hand formulas (written here from the textbooks,
independent of the program's own functions) against the program, for the
sample 2-storey house (grid 4.90 + 4.90 × 4.90 + 2.00 m, after «แก้ตาม
คำแนะนำ»). ``rows()`` returns the comparison; run as a script to print it."""
import json, math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import wanic_advice as AD, wanic_building as B, wanic_calc as C, wanic_calc_cards as CC, wanic_rc as RC

HERE = os.path.dirname(os.path.abspath(__file__))
d = B.default_data()
RC.apply_grid(d, [4.9, 4.9], [4.9, 2.0], 2)
AD.apply_fixes(d)
res = C.analyse(d)
M = res["members"]
lib = B.library_of(d)

# ---- the basis (as stated in the design sheet) ----
fc, fy, fyr, gc = 240.0, 4000.0, 2400.0, 2400.0
D, L = 1.4, 1.7
LL, fin, wall, H = 150.0, 50.0, 180.0, 3.0
rows = []


def add(group, item, formula, hand, prog, unit, tol=0.01):
    diff = (prog - hand) / hand * 100 if hand else 0.0
    rows.append({"g": group, "item": item, "f": formula, "hand": hand, "prog": prog, "unit": unit,
                 "diff": diff, "ok": abs(diff) <= tol * 100})


def num(text, pat):
    m = re.search(pat, text)
    return float(m.group(1).replace(",", "")) if m else float("nan")


def member(pred):
    return next(m for m in M if pred(m))


# ---- 1. slab S2 4.90 × 4.90 m, t 0.11 m, RB9@0.125 ----
t = float(lib["S2"]["t"])
q_dead = t * gc + fin
wu = D * q_dead + L * LL
s2 = member(lambda m: m.group == "slab" and "4.90×4.90" in m.name)
add("พื้น S2 (สองทาง 4.90×4.90 ม.)", "น้ำหนักประลัย wu", f"1.4×({t:g}×2400+50) + 1.7×150", wu, num(s2.note, r"wu = ([\d,]+)"),
    "กก./ตร.ม.", 0.002)
Mu = 0.049 * wu * 4.9 ** 2
add("พื้น S2 (สองทาง 4.90×4.90 ม.)", "Mu− ขอบต่อเนื่อง (ACI 318-63 วิธีที่ 2 กรณี 3, m = 1.0)",
    "C = 0.049 · Mu = C·wu·S²", Mu, num(s2.demand, r"Mu = ([\d,.]+)"), "กก.-ม./ม.")
As = math.pi * 0.9 ** 2 / 4 / 0.125
dd = t * 100 - 2.0 - 0.45
a = As * fyr / (0.85 * fc * 100)
phiMn = 0.9 * As * fyr * (dd - a / 2) / 100
add("พื้น S2 (สองทาง 4.90×4.90 ม.)", "กำลังดัด φMn (RB9@0.125, d = 8.55 ซม.)",
    "a = As·fy/(0.85fc′b) · φMn = 0.9·As·fy·(d − a/2)", phiMn, num(s2.capacity, r"φMn = ([\d,.]+)"), "กก.-ม./ม.")
tmin = 2 * (4.9 + 4.9) / 180
add("พื้น S2 (สองทาง 4.90×4.90 ม.)", "ความหนาขั้นต่ำกันแอ่น", "เส้นรอบรูป / 180", tmin * 100,
    num(s2.note, r"หนาขั้นต่ำ \(กันแอ่น\) ([\d.]+)"), "ซม.", 0.005)
s1w = member(lambda m: m.group == "slab" and "2.00×4.90" in m.name)
add("พื้น S2 (ทางเดียว 2.00×4.90 ม.)", "Mu พื้นทางเดียว (ต่อเนื่องด้านเดียว)", "wu·S² / 10", wu * 2.0 ** 2 / 10,
    num(s1w.demand, r"Mu = ([\d,.]+)"), "กก.-ม./ม.")

# ---- 2. beam B1, level 2, line y = 0 (two equal spans 4.90 m) ----
b1 = member(lambda m: m.group == "beam" and m.name.startswith("B1 ชั้น 2 · แนวนอน y = 0.00"))
bw, bh = float(lib["B1"]["b"]), float(lib["B1"]["h"])
w_self = D * bw * bh * gc
w_slab = wu * 4.9 / 3                     # a square panel: triangle → S/3
w_wall = D * wall * (H - bh)
w = w_self + w_slab + w_wall
g = "คาน B1 ชั้น 2 แนว y = 0.00 (2 ช่วงเท่ากัน 4.90 ม.)"
add(g, "น้ำหนักแผ่บนคาน w", "1.4·b·h·2400 + wu·S/3 + 1.4·180·(3.00 − h)", w, b1.diagram.spans[0].w, "กก./ม.")
add(g, "โมเมนต์ลบที่ฐานรองรับกลาง", "wL²/8 (คานต่อเนื่อง 2 ช่วงเท่ากัน)", w * 4.9 ** 2 / 8,
    -min(b1.diagram.M[24], b1.diagram.M[25]), "กก.-ม.")
add(g, "โมเมนต์บวกสูงสุด", "9wL²/128", 9 * w * 4.9 ** 2 / 128, b1.diagram.Mmax, "กก.-ม.", 0.005)
add(g, "แรงเฉือนสูงสุด", "5wL/8", 5 * w * 4.9 / 8, b1.diagram.Vmax, "กก.")
add(g, "แรงปฏิกิริยาที่เสากลาง", "10wL/8", 10 * w * 4.9 / 8, b1.diagram.reactions[1], "กก.")
add(g, "โมเมนต์ลบขั้นต่ำที่ปลายริมติดเสา (ใหม่)", "wL²/16 (ACI)", w * 4.9 ** 2 / 16, b1.diagram.Mext[0], "กก.-ม.")
dd = (bh - 0.03 - 0.006 - 0.006) * 100
for key, txt, n_ in (("bot", "ล่าง 2-DB20", 2), ("top", "บน 3-DB20", 3)):
    As = n_ * math.pi * 2.0 ** 2 / 4
    a = As * fy / (0.85 * fc * bw * 100)
    phiMn = 0.9 * As * fy * (dd - a / 2) / 100
    prog = b1.diagram.caps["M+" if key == "bot" else "M-"]
    add(g, f"กำลังดัด φMn เหล็ก{txt}", "φ = 0.90 · a = As·fy/(0.85fc′b)", phiMn, prog, "กก.-ม.")
vc = 0.53 * math.sqrt(fc) * bw * 100 * dd
vs = 2 * math.pi * 0.6 ** 2 / 4 * fyr * dd / 7.5
add(g, "กำลังเฉือน φVn (RB6@0.075)", "0.85·(0.53√fc′·b·d + Av·fy·d/s)", 0.85 * (vc + vs), b1.diagram.caps["V"], "กก.")

# ---- 3. beam B1 line x = 4.90 (unequal spans 4.90 + 2.00 m): three-moment equation ----
bx = member(lambda m: m.group == "beam" and m.name.startswith("B1 ชั้น 2 · แนวตั้ง x = 4.90"))
L1, L2 = 4.9, 2.0
q1 = w_self + 2 * wu * 4.9 / 3 + w_wall          # square panels both sides
q2 = w_self + 2 * wu * 2.0 / 3 + w_wall          # the 2.00 m edges of the 4.90 × 2.00 panels
MB = (q1 * L1 ** 3 + q2 * L2 ** 3) / (8 * (L1 + L2))
g2 = "คาน B1 ชั้น 2 แนว x = 4.90 (ช่วง 4.90 + 2.00 ม. ไม่เท่ากัน)"
add(g2, "น้ำหนักช่วงยาว w₁", "1.4bh·2400 + 2·wu·S/3 + ผนัง", q1, bx.diagram.spans[0].w, "กก./ม.")
add(g2, "น้ำหนักช่วงสั้น w₂", "1.4bh·2400 + 2·wu·(2.00)/3 + ผนัง", q2, bx.diagram.spans[1].w, "กก./ม.")
add(g2, "โมเมนต์ลบที่ฐานรองรับกลาง", "สมการสามโมเมนต์: (w₁L₁³ + w₂L₂³) / 8(L₁ + L₂)", MB,
    -bx.diagram.M[24], "กก.-ม.")
RB_ = q1 * L1 / 2 + MB / L1 + q2 * L2 / 2 + MB / L2
add(g2, "แรงปฏิกิริยาที่เสากลาง", "w₁L₁/2 + M_B/L₁ + w₂L₂/2 + M_B/L₂", RB_, bx.diagram.reactions[1], "กก.")

# ---- 4. column C1 at (4.90, 4.90), 35 × 35 cm, 12-DB12 ----
col = member(lambda m: m.group == "column" and "(4.90, 4.90)" in m.name)
cb = float(lib["C1"]["b"])
nb_ = int(lib["C1"]["main"].split("-")[0])
Ag, Ast = cb * cb * 1e4, nb_ * math.pi * 1.2 ** 2 / 4
phiPn = 0.8 * 0.7 * (0.85 * fc * (Ag - Ast) + fy * Ast)
gc_ = f"เสา C1 ที่ (4.90, 4.90) {cb * 100:.0f}×{cb * 100:.0f} ซม. {lib['C1']['main']}"
add(gc_, "กำลังรับแรงอัดล้วน φPn,max", "0.80·0.70·[0.85fc′(Ag − Ast) + fy·Ast]", phiPn / 1000,
    num(col.capacity, r"φPn ([\d,.]+)"), "ตัน", 0.002)
Lu = H - bh
kl = Lu / (0.3 * cb)
add(gc_, "ความชะลูด kLu/r (ใหม่)", "k = 1.0 · Lu = 3.00 − 0.40 · r = 0.3h", kl, num(col.note, r"kLu/r = ([\d.]+)"), "-",
    0.03)
Pu = num(col.demand, r"Pu = ([\d,.]+)") * 1000
Ec = 15100 * math.sqrt(fc) * 1e4
Pc = math.pi ** 2 * (0.4 * Ec * cb ** 4 / 12 / 1.6) / Lu ** 2
add(gc_, "ตัวขยายโมเมนต์ δns (ใหม่)", "1 / (1 − Pu/0.75Pc) · EI = 0.4EcIg/(1 + 0.6)", 1 / (1 - Pu / (0.75 * Pc)),
    num(col.note, r"δ = ([\d.]+)"), "-", 0.01)
# Pu = the reactions of every beam meeting the column + its own weight (the ground floor carries all)
reac = 0.0
for res_ in res["beams"].values():
    lo = 0.0
    pts = []
    # support positions along the run
    xs = [0.0]
    for sp_ in res_.spans:
        xs.append(xs[-1] + sp_.L)
    for name, br in [(n, b) for n, b in res["beams"].items() if b is res_]:
        line = br.line
        if br.axis == "x" and abs(line - 4.9) < 1e-6:
            reac += br.reactions[1]
        if br.axis == "y" and abs(line - 4.9) < 1e-6:
            reac += br.reactions[1]
self_w = D * cb * cb * gc * H * 2
add(gc_, "แรงอัด Pu ที่เสาชั้นล่าง", "Σ แรงปฏิกิริยาของคานทุกชั้นที่เสา + น้ำหนักเสา 2 ชั้น", (reac + self_w) / 1000,
    Pu / 1000, "ตัน", 0.002)
# ---- the stump (ตอม่อ) under it — a check added after this comparison found it missing ----
stm = member(lambda m: m.group == "column" and "ตอม่อ" in m.name and "(4.90, 4.90)" in m.name)
sb = float(lib["PC1"]["b"])
E_ = B.elements(d)
st_ = next(s_ for s_ in E_["stumps"] if abs(s_["x"] - 4.9) < 1e-6 and abs(s_["y"] - 4.9) < 1e-6)
Ls = abs(st_["z1"] - st_["z0"])
gs = f"ตอม่อ PC1 ที่ (4.90, 4.90) {sb * 100:.0f}×{sb * 100:.0f} ซม. {lib['PC1']['main']} (ตรวจใหม่)"
Pst = Pu + D * sb * sb * gc * Ls
add(gs, "แรงอัด Pu ที่ตอม่อ", "Pu เสาชั้นล่าง + 1.4·b·h·2400·ความสูงตอม่อ", Pst / 1000, num(stm.demand, r"Pu = ([\d,.]+)"),
    "ตัน", 0.002)
ns_ = int(lib["PC1"]["main"].split("-")[0])
As_s = ns_ * math.pi * 1.2 ** 2 / 4
add(gs, "กำลังรับแรงอัดล้วน φPn,max", "0.80·0.70·[0.85fc′(Ag − Ast) + fy·Ast]",
    0.56 * (0.85 * fc * (sb * sb * 1e4 - As_s) + fy * As_s) / 1000, num(stm.capacity, r"φPn ([\d,.]+)"), "ตัน", 0.002)

# ---- 5. footing F1 under it, 2.30 × 2.30 × 0.50 m ----
ft = member(lambda m: m.group == "footing" and "(4.90, 4.90)" in m.name)
fw, ft_ = float(lib["F1"]["w"]), float(lib["F1"]["t"])
P = Pst / D + fw * fw * ft_ * gc
gf = f"ฐานราก F1 ที่ (4.90, 4.90) {fw:.2f}×{fw:.2f}×{ft_:.2f} ม."
add(gf, "แรงดันดิน q (น้ำหนักใช้งาน)", "P = Pu/1.4 + น้ำหนักฐาน · q = P/A", P / fw ** 2 / 1000, num(ft.demand, r"q = ([\d.]+)"),
    "ตัน/ตร.ม.", 0.005)
row = next(r for r in CC.footing_rows(res, d) if abs(r["x"] - 4.9) < 1e-6 and abs(r["y"] - 4.9) < 1e-6)
dd_f = (ft_ - 0.075 - 0.012)
b0 = 4 * (sb + dd_f)                      # the stump stands on the footing
vc2 = 0.85 * 1.06 * math.sqrt(fc) * b0 * 100 * dd_f * 100
add(gf, "กำลังต้านแรงเฉือนทะลุ φVc", "0.85·1.06√fc′·b₀·d · b₀ = 4(c + d), c = ตอม่อ", vc2, row["Vc2"], "กก.", 0.005)

# ---- 6. the new checks for beams ----
f_ = 0.4 + 4000 * 14.2233 / 1e5
add("ความลึกขั้นต่ำกันแอ่น (ใหม่)", "คานต่อเนื่องด้านเดียว ช่วง 4.90 ม.", "L/18.5 × (0.4 + fy/100,000 psi)",
    4.9 / 18.5 * f_ * 100, C.beam_hmin(4.9, True, False, False, 4000) * 100, "ซม.")

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "rows.json"
    json.dump(rows, open(out, "w"), ensure_ascii=False, indent=1)
bad = [r for r in rows if not r["ok"]]
if __name__ == "__main__":
  print(len(rows), "rows ·", len(bad), "outside tolerance")
  for r in rows:
    print(f"{'✓' if r['ok'] else '✗'} {r['g'][:22]:22} | {r['item'][:40]:40} | {r['hand']:12,.2f} | {r['prog']:12,.2f} | {r['diff']:+.3f}%")
