# SPDX-License-Identifier: GPL-3.0-or-later
"""อายุการใช้งานครุภัณฑ์ตามประกาศของหน่วยงาน, การแจ้งเตือนหมดอายุ, นำเข้าผลการตรวจสอบพัสดุประจำปี (Excel)
และข้อเสนอ ซ่อมแซม / ปรับปรุง / จำหน่าย (ขายทอดตลาด) ตามระเบียบกระทรวงการคลังฯ พ.ศ. 2560 ข้อ 213–215.

ประกาศที่ใช้เป็นเกณฑ์ (เจ้าของสั่ง 26 พ.ย. 2569): ประกาศองค์การบริหารส่วนตำบลไม้ขาว เรื่อง การกำหนดอายุการใช้งาน
และอัตราค่าเสื่อมราคาสินทรัพย์ (แก้ไขเปลี่ยนแปลง ครั้งที่ 1) ลงวันที่ 3 ตุลาคม 2565 — เมื่อมีประกาศใหม่ให้แนบและ
แก้อายุในหน้าตั้งค่า ประกาศล่าสุดเป็นเกณฑ์.
"""
from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path

from . import thaidate as TD

NOTICE_TITLE = ("ประกาศองค์การบริหารส่วนตำบลไม้ขาว เรื่อง การกำหนดอายุการใช้งานและอัตราค่าเสื่อมราคาสินทรัพย์ "
                "(แก้ไขเปลี่ยนแปลง ครั้งที่ 1)")
NOTICE_DATE = "2022-10-03"
NOTICE_FILE = "notice_life_maikhao_2565.pdf"
CHECK = "ตรวจทานกับประกาศ (ตัวเลขอยู่ระหว่างบรรทัด)"

# (รหัส, ประเภท, อายุ (ปี) ของ «อื่นๆ»/ทั่วไป, [(ชนิดย่อย, อายุ, คำค้น, หมายเหตุ)]) — จากตารางท้ายประกาศ
MAIKHAO_2565 = [
    ("01", "ครุภัณฑ์สำนักงาน", 12, [
        ("กล้องวงจรปิด", 5, "กล้องวงจรปิด,ซีซีทีวี,cctv,กล้องโทรทัศน์วงจรปิด", ""),
        ("รถเข็น", 3, "รถเข็น", ""), ("เครื่องดูดฝุ่น", 3, "ดูดฝุ่น", ""),
        ("ถังเก็บน้ำ", 12, "ถังเก็บน้ำ,ถังน้ำ,ถังบรรจุน้ำ", ""),
        ("เก้าอี้ โต๊ะ ตู้ เคาน์เตอร์ และเครื่องใช้สำนักงานอื่นตามประกาศ (ข้อ 1–27)", 12, "", "")]),
    ("02", "ครุภัณฑ์ยานพาหนะและขนส่ง", 10, [
        ("ป้ายไฟจราจร", 30, "ป้ายไฟจราจร", CHECK),
        ("รถจักรยานยนต์", 5, "จักรยานยนต์,มอเตอร์ไซค์", CHECK), ("รถจักรยาน", 5, "รถจักรยาน", CHECK),
        ("รถดับเพลิง รถบรรทุก รถบรรทุกขยะ รถยนต์ และยานพาหนะอื่นตามประกาศ", 10, "", "")]),
    ("03", "ครุภัณฑ์ไฟฟ้าและวิทยุ", 5, [
        ("เครื่องกำเนิดไฟฟ้า", 10, "กำเนิดไฟฟ้า,เครื่องปั่นไฟ", ""),
        ("เครื่องขยายเสียง", 10, "ขยายเสียง,แอมป์,แอมพลิฟาย,amplifier,มิกเซอร์,mixer", "")]),
    ("04", "ครุภัณฑ์โฆษณาและเผยแพร่", 5, []),
    ("05", "ครุภัณฑ์การเกษตร", 3, [
        ("เครื่องมือและอุปกรณ์ เช่น เครื่องพ่นยา", 2, "เครื่องพ่นยา", ""),
        ("เครื่องจักรกล เช่น เครื่องเก็บเกี่ยว เครื่องตัดวัชพืช รถไถ แทรคเตอร์", 5,
         "ปั๊ม,ปั้ม,สูบน้ำ,รถไถ,แทรคเตอร์,ตัดวัชพืช,หว่านปุ๋ย", "")]),
    ("06", "ครุภัณฑ์ก่อสร้าง", 3, [
        ("เครื่องมือและอุปกรณ์ เช่น เครื่องพ่นสี รอกแม่แรง", 3, "พ่นสี,รอก,แม่แรง", ""),
        ("เครื่องจักรกล เช่น เครื่องกระทุ้งดิน รถตักหน้าขุดหลัง รถบด", 8, "กระทุ้งดิน,รถตัก,รถบด,รถขุด", "")]),
    ("07", "ครุภัณฑ์สำรวจ", 5, []),
    ("08", "ครุภัณฑ์วิทยาศาสตร์และการแพทย์", 5, []),
    ("09", "ครุภัณฑ์งานบ้านงานครัว", 5, []),
    ("10", "ครุภัณฑ์กีฬา", 3, []),
    ("11", "ครุภัณฑ์คอมพิวเตอร์", 5, []),
    ("12", "ครุภัณฑ์การศึกษา", 3, []),
    ("13", "ครุภัณฑ์ดนตรีและนาฏศิลป์", 3, []),
    ("14", "ครุภัณฑ์โรงงาน", 3, [
        ("เครื่องมือและอุปกรณ์ เช่น กบไฟฟ้า ไขควงไฟฟ้า เลื่อยไฟฟ้า สว่านไฟฟ้า", 2,
         "กบไฟฟ้า,ไขควง,เลื่อย,สว่าน", ""),
        ("เครื่องจักรกล เช่น เครื่องกลึง เครื่องเชื่อมโลหะ เครื่องตัดเหล็ก", 5, "กลึง,เชื่อม,ตัดเหล็ก", "")]),
    ("15", "ครุภัณฑ์สนาม", 3, []),
    ("16", "ครุภัณฑ์อื่น", 5, [
        ("ชุดดับเพลิง เครื่องอัดอากาศแรงดันสูง", 10, "ชุดดับเพลิง,อัดอากาศ", CHECK),
        ("เครื่องมือ อุปกรณ์ดับเพลิง", 15, "อุปกรณ์ดับเพลิง,ถังดับเพลิง,สายดับเพลิง", CHECK),
        ("สัตว์ป่าสำหรับสวนสัตว์", 3, "สัตว์", CHECK)]),
    ("17", "ครุภัณฑ์อาวุธ", 5, []),
    ("20", "อาคาร", 40, [("อาคารอื่น ๆ", 15, "", "")]),
    ("21", "อาคารชั่วคราว/โรงเรือน", 8, []),
    ("22", "สิ่งปลูกสร้าง", 15, [("ใช้ไม้หรือวัสดุอื่นเป็นส่วนประกอบหลัก", 10, "ไม้", "")]),
    ("23", "สินทรัพย์โครงสร้างพื้นฐาน", 5, [
        ("ถนนคอนกรีต", 10, "ถนนคอนกรีต", ""), ("ถนนลาดยาง", 10, "ลาดยาง", ""),
        ("สะพานคอนกรีตเสริมเหล็ก", 20, "สะพาน", ""), ("เขื่อนดิน", 20, "เขื่อนดิน", ""),
        ("เขื่อนปูน", 50, "เขื่อนปูน", ""), ("อ่างเก็บน้ำ", 30, "อ่างเก็บน้ำ", "")]),
    ("24", "สินทรัพย์ไม่มีตัวตน", 5, [("โปรแกรมคอมพิวเตอร์", 5, "โปรแกรม,ลิขสิทธิ์,software", "")]),
]
# ชื่อในประกาศที่ต่างจากชื่อในโปรแกรม (ถือเป็นประเภทเดียวกัน)
NOTICE_NAMES = {"08": "ครุภัณฑ์การแพทย์และวิทยาศาสตร์", "10": "ครุภัณฑ์กีฬา/กายภาพ",
                "13": "ครุภัณฑ์ดนตรี/นาฏศิลป์"}

# จำแนกประเภทจากชื่อรายการ (ลำดับสำคัญ: เฉพาะก่อนทั่วไป)
KEYWORDS = [
    ("24", "โปรแกรม,ลิขสิทธิ์"), ("06", "รถตัก,รถขุด,รถบด,รอกโซ่,กระทุ้งดิน,เครื่องตบดิน,โม่ผสม"),
    ("07", "กล้องวัดระดับ,วัดระยะ,จีพีเอส,ล้อวัดระยะ"),
    ("08", "ดูดเสมหะ,ช่วยหายใจ,ambu,เครื่องวัดออกซิเจน,ปลายนิ้ว"), ("01", "กล้องวงจรปิด,ซีซีทีวี,cctv,กล้องโทรทัศน์วงจรปิด,รถเข็น,ถังเก็บน้ำ,ถังน้ำ,ถังบรรจุน้ำ"),
    ("02", "รถยนต์,รถบรรทุก,รถตู้,รถดับเพลิง,รถกระบะ,รถจักรยานยนต์,รถดั้ม,รถดัมพ์,รถขยะ,รถพยาบาล,รถกู้ภัย,เรือ,"
           "จักรยานยนต์,รถเก๋ง,รถโดยสาร"),
    ("11", "คอมพิวเตอร์,computer,notebook,โน๊ตบุ๊ค,โน้ตบุ๊ก,แท็บเล็ต,tablet,ปริ้น,พริ้น,printer,เครื่องพิมพ์,เครี่องพิมพ์,"
           "เลเซอร์,อิงค์เจ็ท,มัลติฟังก์ชั่น,สแกนเนอร์,สแกนเอกสาร,สำรองไฟ,ups,อ่านบัตร,smart card,cpu,จอคอม,"
           "เซิร์ฟเวอร์,server,switch,router,เราเตอร์,access point,ฮาร์ดดิสก์"),
    ("10", "ออกกำลัง,จักรยานนั่ง,บริหารกล้าม,คลายกล้ามเนื้อ,ลู่วิ่ง,ฟิตเนส,โต๊ะเทเบิลเทนนิส,ดัมเบล"),
    ("08", "เทอร์โม,วัดอุณหภูมิ,วัดไข้,พ่นหมอกควัน,เครื่องชั่งน้ำหนัก,วัดความดัน,ออกซิเจน,เตียงผู้ป่วย,aed,"
           "กระตุกหัวใจ,เปลสนาม,เปลตัก"),
    ("09", "ตู้เย็น,ตู้แช่,กระติก,ต้มน้ำ,ไมโครเวฟ,เตาแก๊ส,เตาอบ,กรองน้ำ,ซักผ้า,ตัดหญ้า,ทำน้ำเย็น,ตู้น้ำ,เครื่องดูดควัน,"
           "หม้อหุงข้าว,เครื่องล้างจาน"),
    ("14", "เลื่อย,สว่าน,กบไฟฟ้า,ไขควง,เครื่องเชื่อม,ตัดเหล็ก,หินเจียร,เครื่องเจียร,สกัดไฟฟ้า,ขัดกระดาษทราย,คีม,"
           "ประแจ,บล็อก,ปั๊มลม,เครื่องอัดลม"),
    ("05", "ปั๊ม,ปั้ม,สูบน้ำ,ไดโว่,บาดาล,พ่นยา,รถไถ,แทรคเตอร์"),
    ("04", "กล้องถ่าย,กล้อง vdo,กล้องวีดีโอ,กล้องดิจิตอล,โทรทัศน์,ทีวี,smart tv,สมาร์ททีวี,โปรเจคเตอร์,projector,"
           "จอรับภาพ,จอแสดงภาพ,จอภาพ,led,ป้ายประชาสัมพันธ์"),
    ("03", "ลำโพง,ไมค์,ไมโครโฟน,microphone,ขยายเสียง,แอมป์,amplifier,มิกเซอร์,mixer,วิทยุ,เครื่องเสียง,เสียงตามสาย,"
           "หอกระจายข่าว,กำเนิดไฟฟ้า,โซล่าเซลล์,โซลาร์,ตู้ควบคุมไฟ,ตู้ควบคุมระบบไฟฟ้า,รีเลย์,โฟโต้เซลล์,"
           "สวิตซ์แสงแดด,สวิทซ์แสงแดด,ไฟฉุกเฉิน,โคมไฟ,เครื่องรับ,เครื่องส่ง"),
    ("15", "เต็นท์,เต๊นท์,เต้นท์,ถุงนอน,เตียงสนาม"),
    ("07", "กล้องระดับ,กล้องวัดมุม,ประมวลผลรวม,total station,gps,ไม้สตาฟ,เทปวัดระยะ,โซ่ลาน"),
    ("12", "กระดานไวท์บอร์ด,ไวท์บอร์ด,กระดานดำ,โต๊ะนักเรียน,เก้าอี้นักเรียน"),
    ("13", "กลอง,ระนาด,ขิม,กีตาร์,คีย์บอร์ดดนตรี,เปียโน,ออร์แกน"),
    ("16", "ดับเพลิง"),
    ("01", "โต๊ะ,โต๊,เก้าอี้,ตู้,ชั้นวาง,ชั้นเก็บ,ฉาก,ปรับอากาศ,แอร์,พัดลม,โทรศัพท์,โทรสาร,แฟกซ์,ถ่ายเอกสาร,"
           "ทำลายเอกสาร,เจาะกระดาษ,โซฟา,ชุดรับแขก,ที่แขวน,เคาน์เตอร์,แท่น,บอร์ด,ล็อกเกอร์,พาร์ทิชั่น,ปาติชั่น"),
]
STATUS_BY_SHEET = [("ชำรุด", "ชำรุด"), ("ซาก", "เสื่อมสภาพ"), ("สูญหาย", "สูญหาย"), ("พร้อมใช้", "ใช้งาน"),
                   ("รอซ่อม", "รอซ่อม")]
THAI_MONTH = {m: i for i, m in enumerate(TD.MONTHS, 1)}
THAI_MONTH.update({"กรกฏาคม": 7, "กรกฎา": 7, "มิถุนา": 6})
for i, m in enumerate(TD.MONTHS_SHORT, 1):
    THAI_MONTH[m] = i
    THAI_MONTH[m.replace(".", "")] = i
TH_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
DIVISION_WORDS = ("สำนักปลัด", "กอง", "หน่วยตรวจสอบภายใน", "ศูนย์พัฒนาเด็กเล็ก")


def parse_thai_date(v) -> _dt.date | None:
    """«01 ตุลาคม 2550», «1 ต.ค. 50», 2557 (ปีอย่างเดียว = 1 ต.ค. ของปีงบประมาณนั้น), datetime → date."""
    if v is None or v == "":
        return None
    if isinstance(v, _dt.datetime):
        d = v.date()
        return d if d.year < 2400 else _dt.date(d.year - 543, d.month, d.day)
    if isinstance(v, _dt.date):
        return v
    if isinstance(v, (int, float)):
        y = int(v)
        if 2400 <= y <= 2700:
            return _dt.date(y - 543 - 1, 10, 1)
        return None
    t = str(v).strip().translate(TH_DIGITS)
    m = re.match(r"^(\d{1,2})\s*([ก-๙.]+)\s*(\d{2,4})$", t)
    if m:
        d, mon, y = int(m.group(1)), m.group(2).strip(), int(m.group(3))
        mo = THAI_MONTH.get(mon) or next((v_ for k, v_ in THAI_MONTH.items() if mon.startswith(k[:4])), None)
        if mo:
            y = y + 2500 if y < 100 else y
            try:
                return _dt.date(y - 543, mo, d)
            except ValueError:
                return None
    m = re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$", t)
    if m:
        d, mo, y = (int(x) for x in m.groups())
        y = y + 2500 if y < 100 else y
        y = y - 543 if y > 2400 else y
        try:
            return _dt.date(y, mo, d)
        except ValueError:
            return None
    m = re.match(r"^(25\d\d)$", t)
    if m:
        return _dt.date(int(m.group(1)) - 543 - 1, 10, 1)
    return None


def add_years(d: _dt.date, years: float) -> _dt.date:
    whole = int(years)
    try:
        e = d.replace(year=d.year + whole)
    except ValueError:                      # 29 ก.พ.
        e = d.replace(year=d.year + whole, day=28)
    return e + _dt.timedelta(days=round((years - whole) * 365))


def life_state(end: _dt.date | None, today: _dt.date | None = None) -> tuple[str, str]:
    """(สถานะ, สี): หมดอายุแล้ว = แดง · เหลือไม่เกิน 1 ปี = ส้ม · มากกว่า 1 ปี = เขียว (เจ้าของสั่ง 26 พ.ย. 2569)."""
    today = today or TD.today()
    if end is None:
        return "ไม่ทราบ", ""
    if end <= today:
        return "หมดอายุแล้ว", "#F8C9C4"
    if end <= add_years(today, 1):
        return "เหลือไม่เกิน 1 ปี", "#FDE3C8"
    return "มากกว่า 1 ปี", "#D5F0DD"


SQL = """
CREATE TABLE IF NOT EXISTS life_items(
  id INTEGER PRIMARY KEY, category_id INTEGER NOT NULL REFERENCES categories(id), name TEXT NOT NULL,
  life_years REAL NOT NULL, keywords TEXT DEFAULT '', note TEXT DEFAULT '', seq INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS life_notices(
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, notice_date TEXT, filename TEXT DEFAULT '', data BLOB,
  note TEXT DEFAULT '', added TEXT);
"""


class LifecycleMixin:
    """Methods of :class:`venitsupply.db.Store`."""

    def _lifecycle_init(self):
        self.con.executescript(SQL)
        for table, col, decl in (("categories", "notice_status", "TEXT DEFAULT ''"),
                                 ("categories", "notice_note", "TEXT DEFAULT ''"),
                                 ("categories", "notice_life", "REAL"),
                                 ("assets", "life_item_id", "INTEGER"),
                                 ("assets", "inspect_note", "TEXT DEFAULT ''")):
            cols = [r[1] for r in self.con.execute(f"PRAGMA table_info({table})")]
            if col not in cols:
                self.con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        self.con.commit()

    # ------------------------------------------------------------ notice
    def apply_life_notice(self, table=None) -> list[dict]:
        """ปรับประเภท/อายุการใช้งานตามประกาศ: มีในประกาศ = ฟ้าอ่อน (ปรับอายุให้ตรง) · มีในโปรแกรมแต่ไม่มีในประกาศ =
        เหลือง · ต้องเพิ่มตามประกาศ = ส้ม — หมายเหตุ «แจ้งสถานะ» ทุกรายการ. Returns the comparison rows."""
        table = MAIKHAO_2565 if table is None else table
        cats = {c["code"]: c for c in self.categories("asset")}
        by_name = {c["name"]: c for c in self.categories("asset")}
        seen, out = set(), []
        for code, name, life, items in table:
            c = cats.get(code) or by_name.get(name)
            nname = NOTICE_NAMES.get(code, name)
            if c is None:
                cid = self.run("INSERT INTO categories(kind,code,name,life_years) VALUES('asset',?,?,?)",
                               (code, name, life))
                status, note = "added", f"แจ้งสถานะ: เพิ่มตามประกาศ — «{nname}» อายุ {life:g} ปี"
                old = None
            else:
                cid, old = c["id"], c["life_years"]
                status = "match"
                note = (f"แจ้งสถานะ: ตรงกับประกาศ «{nname}» — " +
                        (f"ปรับอายุจาก {old:g} เป็น {life:g} ปี" if abs((old or 0) - life) > 1e-9
                         else f"อายุ {life:g} ปี ตรงแล้ว"))
                self.con.execute("UPDATE categories SET life_years=? WHERE id=?", (life, cid))
            if items:
                note += f" · มีชนิดย่อยกำหนดอายุต่างกัน {len(items)} รายการ"
            self.con.execute("UPDATE categories SET notice_status=?, notice_note=?, notice_life=? WHERE id=?",
                             (status, note, life, cid))
            self.con.execute("DELETE FROM life_items WHERE category_id=?", (cid,))
            for i, (iname, ilife, kw, inote) in enumerate(items, 1):
                self.con.execute("INSERT INTO life_items(category_id,name,life_years,keywords,note,seq) "
                                 "VALUES(?,?,?,?,?,?)", (cid, iname, ilife, kw, inote, i))
            seen.add(cid)
            out.append(dict(code=code, name=name, status=status, old=old, life=life, note=note))
        for c in self.categories("asset"):
            if c["id"] not in seen:
                note = "แจ้งสถานะ: ไม่มีในประกาศ — ตรวจสอบว่ายังใช้ประเภทนี้หรือไม่ / รวมกับประเภทในประกาศ"
                self.con.execute("UPDATE categories SET notice_status='missing', notice_note=? WHERE id=?",
                                 (note, c["id"]))
                out.append(dict(code=c["code"], name=c["name"], status="missing", old=c["life_years"],
                                life=c["life_years"], note=note))
        self.con.commit()
        return out

    def attach_notice(self, title, notice_date, path_or_bytes, filename="", note="") -> int:
        data = path_or_bytes if isinstance(path_or_bytes, (bytes, bytearray)) else Path(path_or_bytes).read_bytes()
        filename = filename or (Path(path_or_bytes).name if not isinstance(path_or_bytes, (bytes, bytearray)) else "")
        return self.run("INSERT INTO life_notices(title,notice_date,filename,data,note,added) VALUES(?,?,?,?,?,?)",
                        (title, notice_date, filename, data, note, str(TD.today())))

    def notices(self):
        return self.q("SELECT id,title,notice_date,filename,note,added,length(data) AS size FROM life_notices "
                      "ORDER BY notice_date DESC, id DESC")

    def current_notice(self):
        r = self.notices()
        return r[0] if r else None

    def notice_data(self, nid) -> bytes:
        r = self.one("SELECT data FROM life_notices WHERE id=?", (nid,))
        return bytes(r["data"]) if r and r["data"] else b""

    def delete_notice(self, nid):
        self.run("DELETE FROM life_notices WHERE id=?", (nid,))

    def life_items(self, category_id=None):
        if category_id:
            return self.q("SELECT * FROM life_items WHERE category_id=? ORDER BY seq, id", (category_id,))
        return self.q("SELECT li.*, c.code, c.name AS category FROM life_items li JOIN categories c "
                      "ON c.id=li.category_id ORDER BY c.code, li.seq")

    def save_life_item(self, data: dict, iid=None) -> int:
        d = {k: data[k] for k in ("category_id", "name", "life_years", "keywords", "note", "seq") if k in data}
        if iid:
            self.run(f"UPDATE life_items SET {','.join(f'{k}=?' for k in d)} WHERE id=?", (*d.values(), iid))
            return iid
        return self.run(f"INSERT INTO life_items({','.join(d)}) VALUES({','.join('?' * len(d))})", tuple(d.values()))

    def delete_life_item(self, iid):
        self.con.execute("UPDATE assets SET life_item_id=NULL WHERE life_item_id=?", (iid,))
        self.run("DELETE FROM life_items WHERE id=?", (iid,))

    def ensure_lifecycle(self) -> dict:
        """ครั้งเดียวต่อไฟล์ (อบต.ไม้ขาว หรือยังไม่ตั้งชื่อหน่วยงาน): ใช้ประกาศ 3 ต.ค. 2565 เป็นเกณฑ์ + แนบไฟล์ประกาศ."""
        org = self.setting("org_name") or ""
        if (org and "ไม้ขาว" not in org) or self.setting("life_notice") == "MAIKHAO_2565":
            return {}
        rows = self.apply_life_notice()
        pdf = Path(__file__).resolve().parent / "data" / NOTICE_FILE
        if pdf.exists() and not self.q("SELECT 1 FROM life_notices WHERE notice_date=?", (NOTICE_DATE,)):
            self.attach_notice(NOTICE_TITLE, NOTICE_DATE, pdf, note="ฉบับที่ใช้เป็นเกณฑ์ (ไฟล์ในชุดโปรแกรม)")
        n = self.reapply_lives()
        self.set_setting("life_notice", "MAIKHAO_2565")
        return dict(categories=len(rows), assets=n)

    # ------------------------------------------------------------ assets
    def classify(self, name: str, number: str = "") -> str | None:
        t = (name or "").lower()
        for code, kws in KEYWORDS:
            if any(k and k in t for k in kws.split(",")):
                return code
        return None

    def life_for(self, category_id, name) -> tuple[float | None, int | None]:
        """อายุการใช้งานของรายการ: ชนิดย่อยตามประกาศที่ตรงคำค้น (เจาะจงที่สุด) มิฉะนั้นใช้อายุของประเภท."""
        if not category_id:
            return None, None
        t = (name or "").lower()
        best = None
        for it in self.life_items(category_id):
            for k in (it["keywords"] or "").split(","):
                k = k.strip().lower()
                if k and k in t and (best is None or len(k) > best[0]):
                    best = (len(k), it)
        if best:
            return best[1]["life_years"], best[1]["id"]
        c = self.one("SELECT life_years FROM categories WHERE id=?", (category_id,))
        return (c["life_years"] if c else None), None

    def reapply_lives(self) -> int:
        """ปรับอายุการใช้งานของครุภัณฑ์ทุกรายการตามประกาศ (ประเภท + ชนิดย่อย)."""
        n = 0
        for a in self.q("SELECT id, category_id, name, life_years FROM assets"):
            life, iid = self.life_for(a["category_id"], a["name"])
            if life is not None and (life != a["life_years"]):
                n += 1
            if life is not None:
                self.con.execute("UPDATE assets SET life_years=?, life_item_id=? WHERE id=?", (life, iid, a["id"]))
        self.con.commit()
        return n

    def asset_life(self, a, today=None) -> dict:
        start = TD.parse(a["acquire_date"])
        life = a["life_years"]
        end = add_years(start, life) if start and life else None
        state, color = life_state(end, today)
        today = today or TD.today()
        return dict(life=life, end=end, state=state, color=color,
                    days=(end - today).days if end else None, fy=TD.fiscal_year(start) if start else None)

    def suggestion(self, a, info=None) -> str:
        """ข้อเสนอเพื่อพิจารณา ตามระเบียบกระทรวงการคลังฯ พ.ศ. 2560 ข้อ 213–215 (เครื่องมือช่วยพิจารณา)."""
        info = info or self.asset_life(a)
        st, exp = a["status"], info["state"] == "หมดอายุแล้ว"
        if st == "จำหน่ายแล้ว":
            return "จำหน่ายแล้ว"
        if st == "สูญหาย":
            return "สอบหาผู้รับผิด (ข้อ 213) — ไม่มีผู้รับผิด: จำหน่ายเป็นสูญ (ข้อ 215(5))"
        if st == "เสื่อมสภาพ":
            return "จำหน่าย: ขายทอดตลาด หรือแปรสภาพ/ทำลาย (ข้อ 215(1),(4))"
        if st in ("ชำรุด", "รอซ่อม"):
            if exp:
                return "หมดอายุและชำรุด: เสนอจำหน่ายโดยขายทอดตลาด (ข้อ 215(1)) หากค่าซ่อมไม่คุ้มค่า"
            return "ซ่อมแซม (จ้างซ่อม) — เทียบค่าซ่อมกับมูลค่าคงเหลือ ไม่คุ้มค่าให้เสนอจำหน่าย"
        if st == "ไม่จำเป็นต้องใช้":
            return "โอน/ขาย/แลกเปลี่ยน (ข้อ 215)"
        if exp:
            return "หมดอายุแต่ยังใช้งานได้: ใช้งานต่อ ปรับปรุง/บำรุงรักษา และวางแผนจัดหาทดแทน"
        if info["state"] == "เหลือไม่เกิน 1 ปี":
            return "ใกล้หมดอายุ: วางแผนตั้งงบประมาณจัดหาทดแทน"
        return "ใช้งานตามปกติ"

    def life_alerts(self, today=None) -> dict:
        """จำนวนที่ต้องแจ้งเตือน: หมดอายุแล้ว / ภายใน 1 เดือน / ภายใน 1 ปี (ไม่นับที่จำหน่ายแล้ว)."""
        today = today or TD.today()
        out = dict(expired=0, month=0, year=0)
        for a in self.q("SELECT acquire_date, life_years FROM assets WHERE status<>'จำหน่ายแล้ว'"):
            info = self.asset_life(a, today)
            if info["end"] is None:
                continue
            if info["days"] <= 0:
                out["expired"] += 1
            elif info["days"] <= 31:
                out["month"] += 1
            elif info["end"] <= add_years(today, 1):
                out["year"] += 1
        return out

    def lifecycle_rows(self, fy=None, department_id=None, state=None, status=None, text="") -> list[dict]:
        rows = []
        sql = ("SELECT a.*, c.name AS category, c.code AS category_code, d.name AS department FROM assets a "
               "LEFT JOIN categories c ON c.id=a.category_id LEFT JOIN departments d ON d.id=a.department_id "
               "WHERE a.status<>'จำหน่ายแล้ว'")
        args = []
        if department_id:
            sql += " AND a.department_id=?"
            args.append(department_id)
        if status:
            sql += " AND a.status=?"
            args.append(status)
        if text:
            sql += " AND (a.number LIKE ? OR a.name LIKE ?)"
            args += [f"%{text}%"] * 2
        for a in self.q(sql + " ORDER BY d.name, a.acquire_date IS NULL, a.acquire_date, a.number", args):
            info = self.asset_life(a)
            if fy and info["fy"] != fy:
                continue
            if state and info["state"] != state:
                continue
            rows.append(dict(asset=a, **info, suggestion=self.suggestion(a, info)))
        return rows

    # ------------------------------------------------------------ import
    def import_inspection_xlsx(self, path) -> dict:
        """นำเข้าบัญชีผลการตรวจสอบพัสดุประจำปี (บัญชี 1 ชำรุด · 2 ซาก · 3 สูญหาย · 4 พร้อมใช้งาน · 5 รอซ่อม):
        แถวชื่อกองเป็นหัวกลุ่ม; รายการที่มีเลขรหัสเดิมในโปรแกรม = ปรับปรุงสถานะ/หน่วยงาน, ไม่มี = เพิ่มใหม่."""
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        cats = {c["code"]: c["id"] for c in self.categories("asset")}
        stats = dict(added=0, updated=0, skipped=0, components=0, sheets={}, unclassified=0)
        staged = []
        for ws in wb.worksheets:
            status = next((st for key, st in STATUS_BY_SHEET if key in ws.title), None)
            if status is None:
                continue
            cols, dept, n = None, "", 0
            for row in ws.iter_rows(values_only=True):
                cells = list(row)
                if cols is None:
                    if any(isinstance(c, str) and "หมายเลขครุภัณฑ์" in c for c in cells):
                        cols = {}
                        for i, c in enumerate(cells):
                            if not isinstance(c, str):
                                continue
                            for key, name in (("หมายเลข", "number"), ("รายการ", "name"), ("ได้รับมา", "date"),
                                              ("ราคา", "price"), ("สาเหตุ", "cause")):
                                if key in c and name not in cols:
                                    cols[name] = i
                    continue
                vals = [c for c in cells if c not in (None, "")]
                if not vals:
                    continue
                first = cells[0]
                is_seq = isinstance(first, (int, float)) or (isinstance(first, str) and first.strip().isdigit())
                if not is_seq:
                    if len(vals) == 1 and isinstance(vals[0], str):
                        txt = vals[0].strip()
                        if txt.startswith(DIVISION_WORDS):
                            dept = txt
                        elif staged and staged[-1]["sheet"] == ws.title:   # ส่วนประกอบของรายการก่อนหน้า
                            staged[-1]["components"].append(txt.lstrip("-• ").strip())
                            stats["components"] += 1
                    continue

                def get(k):
                    i = cols.get(k)
                    return cells[i] if i is not None and i < len(cells) else None
                name = get("name")
                if not isinstance(name, str) or not name.strip():
                    name = next((c for c in cells[2:9] if isinstance(c, str) and len(c.strip()) > 2), "")
                num = get("number")
                num = (str(int(num)) if isinstance(num, float) else str(num)).strip() if num not in (None, "") else ""
                num = num.translate(TH_DIGITS)
                date = parse_thai_date(get("date"))
                est = False
                m = re.match(r"^\d{3}-(\d{2})-", num)
                if date is None and m:                 # ไม่มีวันที่: ประมาณจากปีในเลขรหัส (XXX-ปี-ลำดับ)
                    date, est = _dt.date(2500 + int(m.group(1)) - 543 - 1, 10, 1), True
                price = get("price")
                try:
                    price = float(str(price).replace(",", "")) if price not in (None, "") else 0.0
                except ValueError:
                    price = 0.0
                extra = [str(c).strip() for i, c in enumerate(cells)
                         if i not in cols.values() and i > 1 and isinstance(c, str) and re.match(r"^\d{3}-", c.strip())]
                staged.append(dict(sheet=ws.title, status=status, dept=dept, number=num, name=re.sub(r"\s+", " ",
                                   str(name)).strip(), date=date, price=price, cause=str(get("cause") or "").strip(),
                                   elaas=extra[0] if extra else "", components=[], est=est))
                n += 1
            stats["sheets"][ws.title] = n
        # ประเภท: คำค้นจากชื่อ แล้วใช้กลุ่มเลขรหัส (3 หลักแรก) ที่ส่วนใหญ่จัดได้
        by_prefix = {}
        for r in staged:
            r["code"] = self.classify(r["name"], r["number"])
            p = r["number"][:3]
            if r["code"] and p.isdigit():
                by_prefix.setdefault(p, {}).setdefault(r["code"], 0)
                by_prefix[p][r["code"]] += 1
        seen = set()
        for r in staged:
            if not r["code"]:
                p = r["number"][:3]
                if p in by_prefix:
                    r["code"] = max(by_prefix[p], key=by_prefix[p].get)
                else:
                    r["code"] = "16"
                    stats["unclassified"] += 1
            cid = cats.get(r["code"]) or cats.get("16")
            did = None
            if r["dept"]:
                d = self.one("SELECT id FROM departments WHERE name=?", (r["dept"],))
                did = d["id"] if d else self.run("INSERT INTO departments(name) VALUES(?)", (r["dept"],))
            life, iid = self.life_for(cid, r["name"])
            note = "; ".join(x for x in (
                f"ส่วนประกอบ: {', '.join(r['components'])}" if r["components"] else "",
                f"สาเหตุ: {r['cause']}" if r["cause"] else "",
                f"รหัสใน e-LAAS: {r['elaas']}" if r["elaas"] else "",
                "วันที่ได้มาประมาณจากปีในเลขรหัส (1 ต.ค.) — ตรวจและแก้ได้" if r["est"] else "") if x)
            insp = f"ผลตรวจสอบประจำปี ({r['sheet']})"
            num = r["number"] or None
            if num and num in seen:
                k = 2
                while f"{num}#{k}" in seen:
                    k += 1
                num = f"{num}#{k}"
            if num:
                seen.add(num)
            ex = self.one("SELECT id FROM assets WHERE number=?", (num,)) if num else None
            if ex:
                self.con.execute("UPDATE assets SET status=?, department_id=COALESCE(?, department_id), "
                                 "inspect_note=? WHERE id=?", (r["status"], did, insp, ex["id"]))
                stats["updated"] += 1
                continue
            self.con.execute(
                "INSERT INTO assets(number,name,category_id,acquire_date,price,department_id,life_years,life_item_id,"
                "status,note,inspect_note,method,salvage) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1)",
                (num, r["name"] or "(ไม่มีชื่อรายการ)", cid, str(r["date"]) if r["date"] else None, r["price"], did,
                 life, iid, r["status"], note, insp, "นำเข้าจากบัญชีตรวจสอบพัสดุ"))
            stats["added"] += 1
        self.con.commit()
        stats["total"] = len(staged)
        return stats
