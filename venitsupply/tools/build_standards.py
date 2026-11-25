# SPDX-License-Identifier: GPL-3.0-or-later
"""Build venitsupply/data/standards_maikhao.json from the มาตรฐานกำหนดตำแหน่ง PDFs of อบต.ไม้ขาว.

Source: https://www.maikhaow.go.th/news_download3 (98 scanned PDFs). Steps used (25 พ.ย. 2569):
  1. save the page links as DIR/standards_list.json {url: "4203เจ้าพนักงานพัสดุ (…)"} and the PDFs as DIR/pdf/<code>.pdf
  2. OCR pages 1–3: pdftoppm -r 200 -gray; OMP_THREAD_LIMIT=1 tesseract -l tha --psm 4 → DIR/ocr/<code>.txt
  3. python3 venitsupply/tools/build_standards.py DIR   (writes DIR/standards_maikhao.json; copy it into data/)
Takes the entry level («ปฏิบัติการ/ปฏิบัติงาน/ต้น») duties from «๑. ด้าน…» to «คุณสมบัติเฉพาะ», with OCR clean-up.
"""
import json, re, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from venitsupply.manpower import parse_standard
D = sys.argv[1]
lst = json.load(open(f"{D}/standards_list.json"))
FIX = [("ํา", "ำ"), ("ดังนี่", "ดังนี้"), ("ทัวไป", "ทั่วไป"), ("ซือ", "ซื้อ"), ("ทีได้", "ที่ได้"),
       ("ทีเกี่ยว", "ที่เกี่ยว"), ("ทีกำหนด", "ที่กำหนด"), ("ทีชัดเจน", "ที่ชัดเจน"), ("ทีเป็น", "ที่เป็น"),
       ("ทีจะ", "ที่จะ"), ("ทีมีประสิทธิ", "ที่มีประสิทธิ"), ("ทีรับผิดชอบ", "ที่รับผิดชอบ"), (" ที ", " ที่ "),
       ("ทีสุด", "ที่สุด"), ("ทีดี", "ที่ดี"), ("ทีถูกต้อง", "ที่ถูกต้อง"), ("ทีเหมาะสม", "ที่เหมาะสม"),
       ("ต่างๆ", "ต่าง ๆ"), ("  ", " ")]
TITLE_FIX = {"วิศวกรรมโยธา": "วิศวกรโยธา", "วิศวกรรมเครื่องกล": "วิศวกรเครื่องกล", "วิศวกรรมไฟฟ้า": "วิศวกรไฟฟ้า",
             "วิศวกรรมสุขาภิบาล": "วิศวกรสุขาภิบาล", "เจ้าพนักงานรังสีการแทพย์": "เจ้าพนักงานรังสีการแพทย์",
             "โภชนาการ": "นักโภชนาการ"}
def clean_line(s):
    s = s.strip()
    for a, b in FIX:
        s = s.replace(a, b)
    return s
def clean_text(x):
    x = re.split(r"\s(?:ค|ค\S)?ณ?สมบัติเฉพาะ|\sคณสมบัติ", x)[0]
    toks = [tk for tk in x.split(" ") if not re.search(r"[%“”\"'/|=~_<>{}\[\]]|\d[ก-๙]|[ก-๙]\d", tk)]
    while len(toks) > 1 and len(toks[-1]) <= 4 and not toks[-1].endswith(("ได้", "งาน", "ไว้", "ๆ")):
        toks.pop()
    keep, run = [], []
    for tk in toks:                                   # ตัดเศษอักขระ: ช่วงคำสั้น ≤2 ตัวอักษรติดกัน 3 คำขึ้นไป
        if len(tk) <= 2 and tk not in ("ๆ", "และ"):
            run.append(tk)
            continue
        if len(run) < 3:
            keep += run
        run = []
        keep.append(tk)
    if len(run) < 3:
        keep += run
    x = " ".join(keep)
    for a, b in (("\u0e49\u0e49\u0e32", "\u0e49\u0e33"), ("ก๊าหนด", "กำหนด"), ("เสือม", "เสื่อม"), ("ทีพร้อม", "ที่พร้อม"),
                 ("จ้ จัดซื้อ", "จัดซื้อ"), ("ใหม่ๆ", "ใหม่ ๆ"), ("ต่างๆ", "ต่าง ๆ"), ("  ", " "),
                 ("ของว่าด้วย", "ว่าด้วย"), ("ส่วนท้องถิน", "ส่วนท้องถิ่น")):
        x = x.replace(a, b)
    x = re.sub(r"เมือ(?!ง)", "เมื่อ", x)
    x = re.sub(r"\s+([,.])", r"\1", x)
    return x.strip(" ,")


def noise(s):
    th = sum(1 for c in s if "ก" <= c <= "ฮ" or "ะ" <= c <= "์")
    if len(s) < 4:
        return True
    if s.startswith(("ก.ท.", "ก.จ.", "ก.อบต.", "=====")) or "กำหนดเมื่อ" in s:
        return True
    return th / max(1, len(s.replace(" ", ""))) < 0.55
out, report = [], []
for url, label in lst.items():
    m = re.match(r"\s*(\d{4})\s*(.+?)\s*(\(.*)?$", label)
    code, title = m.group(1), m.group(2).strip()
    title = TITLE_FIX.get(title, title)
    raw = open(f"{D}/ocr/{code}.txt", encoding="utf-8").read()
    lines = [clean_line(x) for x in raw.splitlines()]
    tn = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
    i = next((k for k, x in enumerate(lines) if re.match(r"^1\s*[.,]\s*\S{0,2}?ด้าน", x.translate(tn))), None)
    if i is None:
        out.append(dict(code=code, title=title, url=url, duties=[]))
        report.append((code, title, {}))
        continue
    body = []
    for x in lines[i:]:
        z = x.replace(" ", "").translate(tn)
        if re.match(r"^(คุณสมบัติ|ชื่อตำแหน่ง|ระดับตำแหน่ง|ความรู้ความสามารถ|ทักษะที่จำเป็น|สมรรถนะ|มีคุณวุฒิ|"
                    r"\d\.?ได้รับ(ปริญญา|ประกาศนียบัตร|วุฒิ)|ได้รับ(ปริญญา|ประกาศนียบัตร|วุฒิ))", z):
            break
        if not noise(x):
            body.append(x)
    txt = "\n".join(body)
    # หมายเลขข้อที่ OCR อ่านเพี้ยน เช่น «1.ณ» (= ๑.๗) กลางบรรทัด → ขึ้นข้อใหม่
    txt = re.sub(r"\s+([๑-๙\d])\s*\.\s*[ณฅฆ]\s+", lambda m: "\n" + m.group(1) + ".99 ", txt)
    txt = re.sub(r"(?m)^([๑-๙\d])\s*\.\s*[ณฅฆ]\s+", lambda m: m.group(1) + ".99 ", txt)
    items = [(s, clean_text(x)) for s, x in parse_standard(txt)]
    items = [(s, x) for s, x in items if len(x) >= 8]
    sides = {}
    for s, t in items:
        sides[s] = sides.get(s, 0) + 1
    out.append(dict(code=code, title=title, url=url, duties=[dict(side=s, text=t) for s, t in items]))
    report.append((code, title, sides))
out = [e for e in out if not e["code"].startswith(("1", "2"))]     # เจ้าของ 25 พ.ย.: ไม่ใช้สายบริหาร/สายอำนวยการ
json.dump(sorted(out, key=lambda e: e["code"]), open(f"{D}/standards_maikhao.json", "w"), ensure_ascii=False, indent=1)
for r in sorted(report):
    print(r[0], r[1], r[2])
