"""Standard Thai surveying terms in the Thai packs (run after apply_branding)."""
import json, re, string
from pathlib import Path
W = Path(__file__).resolve().parent.parent
PACKS = [W/'cad/i18n/th/ui.json', W/'cad/plugins/topografia/i18n/th/ui.json',
         W/'cad/plugins/terreno/i18n/th/ui.json', W/'3d/i18n/th.json']
SUBS = [
    ("ระบุทิศทาง (N45°30'E)", "ระบุมุมแบริ่ง (N45°30'E)"),
    ("ทิศทางไม่ถูกต้อง", "มุมแบริ่งไม่ถูกต้อง"),
    ("จุดจากทิศทางและระยะทาง", "จุดจากมุมแบริ่งและระยะทาง"),
    ("ใส่คำอธิบายทิศทางและระยะทาง", "เขียนมุมแบริ่งและระยะทางกำกับเส้น"),
    ("[ทิศทาง(B)/", "[แบริ่ง(B)/"), ("/ทิศทาง(B)/", "/แบริ่ง(B)/"),
    (", ทิศทาง {bearing})", ", แบริ่ง {bearing})"),
    ("ระยะห่างสถานี", "ช่วงระยะสถานี (กม.)"),
    ("มวลดิน {m", "ปริมาตรสะสมสุทธิ {m"),
    ("เส้นจุดตัดลาดดิน", "เส้นขอบงานดิน (Daylight)"),
    ("ชานพัก", "ชานพัก (Berm)"),
    ("ตารางข้อมูลแปลง", "ตารางรายการรังวัด"),
    ("รายงานรายละเอียดแปลงที่ดิน", "รายงานรายละเอียดการรังวัดแปลงที่ดิน"),
    ("พื้นหลักฐาน [WGS84", "พื้นหลักฐาน (Datum) [WGS84"),
    ("ระดับ <{z", "ค่าระดับ <{z"), ("ระดับไม่ถูกต้อง", "ค่าระดับไม่ถูกต้อง"),
    ("ทศนิยมของระดับ", "ทศนิยมของค่าระดับ"),
    ("สร้างโครงข่ายสามเหลี่ยม (TIN)", "สร้างพื้นผิวสามเหลี่ยม (TIN)"),
]
EXACT = {"BEARING": "แบริ่ง", "STATION": "สถานี (กม.)", "MASS": "ปริมาตรสะสม",
         "Grade line": "เส้นระดับออกแบบ (Grade line)", "ELEVATION": "ค่าระดับ",
         "Survey points": "จุดสำรวจ (Survey points)"}
def fields(s): return sorted(f[1] for f in string.Formatter().parse(s) if f[1] is not None)
n = 0
for p in PACKS:
    d = json.loads(p.read_text(encoding='utf-8'))
    for k, v in d.items():
        new = EXACT.get(k, v)
        for a, b in SUBS:
            if a in new and b not in new:
                new = new.replace(a, b)
        new = new.replace("ค่าค่าระดับ", "ค่าระดับ").replace("ชานพัก (Berm) (Berm)", "ชานพัก (Berm)")
        if new != v:
            assert fields(new) == fields(k), (k, new)
            d[k] = new; n += 1
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('changed', n)
