# ลำดับการทำงานของระบบ QD (จากคู่มือ 5 หน้า)

ระบบทำงานร่วมกัน 3 ส่วน: AutoCAD (แปลน และเมนู Mainmenu), SketchUp (ปลั๊กอิน
Quickdesign / QuickSteel) และการแลกเปลี่ยนไฟล์ผ่านโฟลเดอร์ `C:\SKUDWG`

## ลำดับหลัก (ตามคู่มือ)
1. **แปลนใน AutoCAD** วาดแปลนและกำหนดขนาด/ระดับ
2. **Export 3D** — ส่งข้อมูลแปลนจาก AutoCAD ออกเป็นไฟล์ข้อความ (text file)
3. **SketchUp** อ่านไฟล์ข้อความแล้วสร้างโมเดล 3 มิติ โดยเลือกคำสั่งตามประเภทงาน:
   - *Draw Building* (อาคาร): Door → Home → Frame → Roof → CoverRoof → Stair
   - *Draw Factory* (โรงงาน/โกดัง): Door → Home → QuickSteel (WF, Truss, InTruss, Purlin)
   - ชั้นของโมเดลแยกเป็น layer เปิด/ปิดการมองเห็นได้
4. **Decoration** — เพิ่มส่วนตกแต่งก่อนส่งออก (ทำใน SketchUp ก่อน Export)
5. **Export to DWG** — เลือกฉาก (scene) ทีละฉาก: Front, Rear, Left, Right, A-A, B-B
   แล้วส่งออกเป็น `C:\SKUDWG\<ชื่อฉาก>.dwg` (เมนู File → Export → 2D Graphic)
6. **Elev. And Section ใน AutoCAD** — เมนู Mainmenu → Section:
   - `SketchUp` ดึงไฟล์ภาพตัดจาก `C:\SKUDWG\...`, คัดลอกเส้นกริดจากหน้าด้านไปยังภาพตัด
   - `Decor.` เปิดเมนูบล็อกหน้าด้านและภาพตัด
   - `Landscape` เปิดเมนูตกแต่งภูมิทัศน์
   - `D-W` เลือกชื่อประตู/หน้าต่างแล้วคลิกจุดวาง รายการ: D1, D2, D3, W1, W2, W3
     เลือก `S` สำหรับมุมด้านข้าง และ `E`/`F` สำหรับมุมด้านหน้า
   - `Vport` วาง viewport ของภาพตัดลงในเลย์เอาต์ "Plan"

## หมายเหตุ
- ฉากใน SketchUp คือ Front, Rear, Left, Right, A-A, B-B
- เส้นทางไฟล์ที่ระบุในคู่มือ: `C:\SKUDWG\`
- ตัวเลือกประตูหน้าต่างที่เห็น: D1, D2, D3, W1, W2, W3
- เอกสารนี้สรุปจากคู่มือเท่านั้น ยังไม่ได้ตรวจกับโค้ดต้นฉบับ

## เพิ่มเติมจากคู่มือชุดที่ 2 (5 หน้า)

### 1. เปลี่ยนเลขแบบและวันที่ (Change Drawing No.)
- เมนู: Mainmenu → List → **CHG.Head**
- ปุ่มใน List: List, Regen, CHG.Head, Excel
- ขั้นตอน:
  1. กด **Del. Overlap Paper** เพื่อลบกระดาษที่ซ้อนทับทุกเลย์เอาต์
  2. เลย์เอาต์ **Plan**: ตั้ง Head = 1 แล้วเลือกกระดาษจากแผ่นแรกถึงแผ่นสุดท้าย (A-01, A-02, …)
  3. เลย์เอาต์ **Structure**: ตั้ง Head = 1 แล้วเลือกกระดาษ (S-01, S-02, …)
  4. กด **Sel.Paper Layout** แล้วเลือกกระดาษเพื่อดึงข้อมูลหัวแบบเข้าเมนู
  5. แก้ข้อมูล แล้วกด **Regen**
  6. เปลี่ยนวันที่และจำนวนแผ่นรวม (Total) แล้วกด **Regen Total** ทั้งชุด
- ช่องในเมนู: DWG.NO. (เช่น A-11), X-00, Name, Date, Total

### 2. ใส่ส่วนตกแต่ง (Insert Decoration)
- เมนู: Mainmenu → List → **Decorate** (ปุ่ม Road อยู่ข้างกัน)
- เมนู Decoration มีหมวด: Tree-Man, Car, Chair, Table, Sofa, Bed, Closet, Kitchen, Electric, Elevation, Steel Sec
- แต่ละหมวดมี Scale 1: (ค่าเริ่มต้น 100) และ size(m.) (ค่าเริ่มต้น 1.00) แล้วเลือกรูปแบบที่ต้องการ
- **Steel Sec**: เลือกชนิดเหล็ก Tube, CH, Rect., Hbeam, C, WF, Angle Steel แล้วคลิกวาง จากนั้นเลือกขนาดผ่าน dynamic block grip

### 3. รายละเอียดประตู-หน้าต่างและห้องน้ำ (Detail Door and WC)
- เมนู: Mainmenu → **Arch.** แล้วเลือก:
  - **Detail-Door**: วาดรายละเอียดประตู-หน้าต่างในเลย์เอาต์ Plan และตั้งชื่อประตู
    แบบที่มีให้เลือกในหน้า: D1–D4 (ประตู) และ W1–W4 (หน้าต่าง) พร้อม W5–W8 แบบบานเกล็ด/บานกระจก
  - **Plan WC**: เปิดเมนู Plan and Section WC
    - กรอก Name, Scale (ค่าเริ่มต้น 1:50), **Ceil. H=** (ความสูงฝ้า, ค่าเริ่มต้น 2.50 ม.), **Ceramic H=** (ความสูงกระเบื้อง, ค่าเริ่มต้น 2.50 ม.)
    - คลิกจุดกึ่งกลางห้องน้ำ โปรแกรมจะวาดผังห้องน้ำ ภาพตัด และรายละเอียด WC ในเลย์เอาต์ Plan
    - รายการสุขภัณฑ์ที่ใช้: Water Closet, Spray, Lavatory, Valve, Shower, Floor (สีขาว หรือ Valve)

### 4. ปรับเส้นกริดให้ยืดหรือหดแปลน (Adjust Grid)
- เมนู: Mainmenu → Arch. → **Make Grid**
- กรอกค่า **Ver.** (แนวตั้ง) หรือ **Hor.** (แนวนอน)
  - ค่าบวก = ยืดกริด
  - ค่าลบ = หดกริด
- กด **Sel.** แล้วเลือกพื้นที่ด้วยการคร่อม (crossing) ในแปลน
- ผลกระทบ: ยืดเส้นกริด คาน ผนัง และพื้นตามช่วงที่เลือก

### 5. ภาพด้านหน้า (Elevation) รายละเอียดเพิ่ม
- เมนู Elevation มี: SketchUp, Gridline, Decor., RoofMat., CoverRoof, D-W, Vport
- **RoofMat.** เลือกชนิดกระเบื้อง (Type), ทิศทาง (Direction) เป็น Bot., แล้วคลิก **Sel. Area Roof** ใกล้ชายคา
- **CoverRoof** (Detail Elevation) มีค่า Roof Mat. = Monair, Barge (0 ม.), Beam L= (6 ม.), Ang. (30°), Flash (7.5)
  และมีปุ่มรายละเอียดหลังคา: Round Hip, Round Ridge, Round Ridge End, Ridge end, Ridge, Cover Edge, Cover Gable, Cover Ridge-edge, Eaves
- ภาพด้านทั้ง 4 ด้าน (Elevation A, B, C, D) ถูกวางในเลย์เอาต์ Plan ผ่าน Vport

## หมายเหตุหลังอ่านชุดที่ 2
- ชื่อประตู-หน้าต่างรวมถึง D1–D3 และ W1–W3 ที่กล่าวไว้ในชุดแรก ขยายเป็น D1–D4 และ W1–W8 ในชุดนี้
- ค่าเริ่มต้นในวงเล็บมาจากภาพหน้าจอในคู่มือ ไม่ได้ตรวจกับโค้ดต้นฉบับ
