# -*- coding: utf-8 -*-
"""Read the plumbing (หมวด 3) and electrical (หมวด 4) labour rates a house needs from the text of
ว480 (pdftotext -layout) into data/labour_mep_2569.json.

    pdftotext -layout w480.pdf w480.txt
    python tools/parse_w480_mep.py w480.txt
"""
import json
import os
import re
import sys

KEEP = {"3.7", "3.8", "3.11", "3.13", "3.14", "4.21", "4.22", "4.23", "4.24", "4.44", "4.53", "4.57", "4.58"}
UNIT = r"(เมตร|ชุด|ถัง)"
FIX = str.maketrans({"ำ": "ำ"})


def main(path):
    out, sec, group = {}, None, ""
    for raw in open(path, encoding="utf-8"):
        s = raw.rstrip("\n")
        m = re.match(r"^\s{0,3}(\d\.\d{1,2})\s{2,}(\S.*)$", s)
        if m:
            sec = m.group(1) if m.group(1) in KEEP else None
            title = re.sub(r"\s{2,}", " ", m.group(2)).strip().replace("งำน", "งาน")
            group = ""
            if sec:
                out.setdefault("_sections", {})[sec] = title
            continue
        if not sec:
            continue
        m = re.match(r"^\s*-?\s*(\S.*?)\s{2,}" + UNIT + r"\s{2,}([\d,]+)\s*(.*)$", s)
        if m:
            label = re.sub(r"\s+", " ", m.group(1)).strip()
            name = f"{group} {label}".strip() if group else label
            code = f"{sec}/{label}" if not group else f"{sec}/{group}/{label}"
            out[code] = {"name": name, "unit": m.group(2), "rate": float(m.group(3).replace(",", "")),
                         "condition": re.sub(r"\s+", " ", m.group(4)).strip()}
        elif re.match(r"^\s{1,12}(โคม.*|Switch and receptacle)\s*$", s) and not re.search(UNIT + r"\s{2,}[\d,]+", s):
            group = re.sub(r"\s+", " ", s).strip()
    secs = out.pop("_sections")
    data = {"source": "หนังสือกรมบัญชีกลาง ด่วนที่สุด ที่ กค 0433.2/ว 480 ลงวันที่ 26 มิถุนายน 2569 "
                      "บัญชีค่าแรงงาน/ดำเนินการ หมวด 3 งานระบบสุขาภิบาล และหมวด 4 งานระบบไฟฟ้า (เฉพาะรายการที่ใช้กับอาคารพักอาศัย)",
            "pipe_rule": "ท่อ PVC: ข้อต่อ อุปกรณ์ท่อ ค่าวัสดุ 40 % (ระบายน้ำ) / 50 % (ประปา) ของราคาท่อ, เหล็กยึดท่อ 30 %, "
                         "ทดสอบ ทำความสะอาด 10 %; ค่าแรงของทั้งสามรายการ 30 % ของค่าวัสดุ (ว480 3.7–3.8 หมายเหตุ 1–3)",
            "pipe_extra": {"3.7": {"fittings": 0.40, "hangers": 0.30, "test": 0.10, "labour": 0.30},
                           "3.8": {"fittings": 0.50, "hangers": 0.30, "test": 0.10, "labour": 0.30}},
            "sections": secs, "labour": out}
    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "labour_mep_2569.json")
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(len(out), "items;", ", ".join(f"{k} {v}" for k, v in secs.items()))


if __name__ == "__main__":
    main(sys.argv[1])
