# บันทึกส่งต่องาน (Handoff) — WANICNSURVEY / ReadWanicn2027

ไฟล์นี้เก็บสถานะงานทั้งหมด เพื่อให้ทำต่อได้ทันทีในรอบใหม่ (เมื่อโทเคนหมดหรือเริ่มเซสชันใหม่)
อัปเดตล่าสุด: 2026-11-11 · สาขา `claude/youthful-pascal-ctgtr0` · repo `venidnid-creator/wanicn1`

## กฎที่ผู้ใช้กำหนด (ต้องทำทุกครั้ง)
- ทุกส่วนใหม่ต้อง **ส่งภาพหน้าจอให้อนุมัติก่อน** สร้าง .exe — commit งานที่ยังไม่อนุมัติด้วย `[skip ci]`
- เมนูและข้อความทั้งหมดเป็น **ภาษาไทย** (ไม่ใช้ชื่อยี่ห้อ Word/Excel) · ใช้ **ฟอนต์ไทย**
- หากสงสัยให้ **ถามก่อน** · ตอบผู้ใช้เป็นภาษาไทย
- ก่อน push: `git fetch origin claude/youthful-pascal-ctgtr0 && git rebase origin/claude/youthful-pascal-ctgtr0`
- ห้ามเผยแพร่ GitHub Release เอง ยกเว้นผู้ใช้สั่ง (ReadWanicn: workflow_dispatch `release=true`)

## ReadWanicn2027 (โฟลเดอร์ `readwanicn2027/`)
- รุ่นล่าสุดที่เผยแพร่: **2027.3.0** (Release `readwanicn-v2027.3.0`) — workflow `readwanicn-windows.yml`
- คีย์ใบอนุญาตอยู่ใน GitHub secret `READWANICN_LICENSE_KEY` (ตั้งแล้ว) · รหัสต่ออายุ: `tools/readwanicn_code.py`
- ผู้ใช้ Wanicn / รหัสผ่าน Thammawong

## WANICNSURVEY (cad/ 3d/ launcher/) — workflow `build-windows.yml`
รุ่นที่กำลังสร้าง: **2026.11.11.1** (dispatch, release=false — ผู้ใช้จะลองก่อน ยังไม่เผยแพร่) รวมงานที่อนุมัติแล้วทั้งหมดรวมทั้งคำนวณโครงสร้าง
(รอบแรกล้มเพราะ CI ไม่มี openpyxl → รายงาน RC ใช้ตัวเขียน .xlsx ของโปรแกรมเอง `core.wanic_takeoff._xlsx`):
1. หลังคา: จั่วสมมาตร (โครงถักบนผนังจั่ว), ทรงไทย, จั่วซ้อน, โครงไม้ — `3d/core/wanic_building.py`
2. หน้าเริ่มต้น 2027: ธีม 5 แบบ, ไทย/EN, การ์ด 4 ใบ, แผงผู้พัฒนา — `launcher/launcher.py`
   (ส่ง `WANIC_LANG`, `WANIC_START_PANEL` ให้ 2D/3D — `3d/main.py`, `cad/main.py`)
3. ออกแบบโครงสร้าง คสล. 8 ขั้น — `3d/plugins/wanic_rc.py`, `3d/core/wanic_rc.py`
4. แก้เลือกวัตถุช้า (`views/extension_api.py on_document_changed` กรองการเลือก) และข้อมูลชิ้นส่วนตามขนาดจริง
   (`core/wanic_partprice.py live_rows/refresh`, `core/history.py ScaleGroupCommand`)

อนุมัติแล้ว (อยู่ในตัวติดตั้ง 2026.11.11.1 รอบที่สอง):
5. **คำนวณโครงสร้าง** ขั้น 9 — `3d/core/wanic_calc.py` (โหลด, คานต่อเนื่อง stiffness, SDM/WSD, ASD หลังคา,
   เสา, ฐานราก/เข็ม), `3d/core/wanic_calc_view.py` (SFD/BMD, รายการคำนวณ PDF), ทดสอบ `3d/tests/test_wanic_calc.py`
   ค่าออกแบบ (ผู้ใช้ตกลง): SDM วสท. 011008 (WSD ทางเลือก), fc′ 240, SD40/SR24, SS400 Fy 2450,
   LL พื้น 150 / หลังคา 30 กก./ตร.ม., ลม 50 กก./ตร.ม., ดิน 10 ตัน/ตร.ม., เข็ม I-0.18 ยาว 6 ม. 8 ตัน/ต้น

## งานถัดไป (ลำดับ)
- [x] พื้นแบบสัมประสิทธิ์ วสท. (Method 2) — `slab_moment`, `discontinuous_edges`
- [x] เสา: แรงอัดร่วมโมเมนต์ แผนภาพ P-M — `pm_curve`, `pm_ratio`, `draw_pm`
- [x] แรงลมบนหลังคา: D+W (Cp 0.7, ×4/3) แป/จันทัน + แรงยกที่จุดยึด
- [ ] ส่งภาพให้อนุมัติ → สร้างตัวติดตั้งรุ่นถัดไป (dispatch build-windows.yml พร้อม version ใหม่)
- [x] ตัวติดตั้ง 2026.11.11.1 สร้างสำเร็จ (run 43021651986, artifact wanicnsurvey-setup-2026.11.11.1) ส่งให้ผู้ใช้ลองแล้ว
- [ ] รอผลการลองจากผู้ใช้ · เผยแพร่ Release เมื่อผู้ใช้สั่งเท่านั้น (dispatch build-windows.yml version 2026.11.11.1 release=true)
- [ ] (ตัวเลือก) ธีม 5 แบบในหน้าต่างโปรแกรม 2D/3D · ภาพเหล็กเสริมในโมเดล 3D · ค่าเริ่มต้น GB1 3-DB12

## การทดสอบ/ภาพหน้าจอ
- 3D รันจริงได้ด้วย: `xvfb-run -a -s "-screen 0 1920x1080x24"` + `QT_QPA_PLATFORM=xcb LIBGL_ALWAYS_SOFTWARE=1`
  (ติดตั้ง libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0
  libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 libxcb-xkb1)
- ชุดทดสอบใน CI: ดูบรรทัด pytest ใน `.github/workflows/build-windows.yml`

## การศึกษาโปรแกรมในแฟลชไดรฟ์ของผู้ใช้ (2026-11-12)
ผู้ใช้ส่ง «ขั้นตอนติดตั้ง.xls» และ «VDOsteel.xls» (คู่มือ) — เป็นโปรแกรมเชิงพาณิชย์ QuickDesign / HouseDemo / QuickSteel
(AutoCAD VBA+LISP + Excel + ปลั๊กอิน SketchUp) เข้าถึงไดรฟ์ F: โดยตรงไม่ได้ (ไม่มีโฟลเดอร์ Remote Control) วิดีโอ .mp4/.swf ดูไม่ได้
ขั้นตอนของโปรแกรมนั้น: กริด → เส้นร่างเสา/คาน → เสา คสล./เหล็ก คาน ผนัง (เมทัลชีท) พื้น (FlatSlab/Post-tension)
→ หลังคา (เส้นชายคา อกไก่ ครอบ Truss หลัก/รอง วัสดุมุง แป SagRod TieRod) → ออกแบบ: ถ่ายน้ำหนักเสา (Checkload),
เสา คสล. ตาราง, เสา/คานเหล็กจัดกลุ่มแล้วเลือกขนาด, FlatSlab + Drop panel บนเข็ม, PT (โมเมนต์เสาตาม วสท. M=(WL1−WDL2)/40,/30),
Truss 6 แบบหรือเขียนเอง → Matrix หาแรงในชิ้นส่วน → เลือกเหล็ก → ออกแบบแป → รายการคำนวณ/แบบ Truss/แผ่นเหล็กหัวเสา
→ ถอดปริมาณ (โครงสร้าง สถาปัตย์ เหล็ก หลังคา สุขภัณฑ์ ไฟฟ้า) → ประมาณราคา → ส่งออก SketchUp → รูปด้าน/รูปตัด DWG
แผนที่เสนอผู้ใช้ (รออนุมัติ): A เหล็กรูปพรรณ เสา/คาน WF/H · B วิเคราะห์ Truss แบบ Matrix + Truss 6 แบบ/เขียนเอง + แผ่นหัวเสา
· C แป + SagRod/TieRod · D FlatSlab + Drop panel · E หลังคาวาดอิสระ/หลังคาโค้ง ผนังเมทัลชีท · (เขียนเองทั้งหมด ไม่คัดลอกโปรแกรมเขา)

### ศึกษาเพิ่ม (DrawExcel.xls, EST.xls, Quan.xls, QDNew.dwg) — 2026-11-12
- เกณฑ์ของโปรแกรมนั้น: WSD ตามข้อบัญญัติ กทม. 2522 (fc′ 170, SD30, fs 1500, n 10, k j R), เหล็กรูปพรรณ ASD (A36 Fy 2400/2520,
  Fb 0.66/0.60Fy, Fa ตาม Cc, fa/Fa + Cm·fb/((1−fa/Fe)Fb) ≤ 1, แผ่นรองใต้เสา t = √(M/300)), เหล็กรีดเย็น Fy 2000 Fb 1100,
  แอ่น L/240 (หลังคา) L/360 (คาน), แผ่นดินไหว V = ZIKCSW, ลม กฎกระทรวง 6 (2527) 50/80/120/140 ตามความสูง
- คานต่อเนื่อง: Hardy Cross + น้ำหนักจุด, โมเมนต์ลงเสา · FlatSlab: DDM วสท. (ร้อยละ Mo แถบเสา/แถบกลาง, Drop = L/3, เฉือน d/2)
- ตารางน้ำหนักเสาตามกริด (Wbeam/Wcol/Wfloor/Wcol-Area ตรวจสอบกัน) · ปริมาณเผื่อเสีย (RB 8%, DB12-16 10%, DB20 11%, DB25 12%, คอนกรีต 3%)
- ประมาณราคา 8 หมวด (งานเตรียม โครงสร้าง สถาปัตย์ สุขาภิบาล ไฟฟ้า ปรับอากาศ ภายนอก อื่นๆ) + ดำเนินการ/กำไร 5% + VAT 7%
- DWG ตัวอย่าง: อาคารเหล็ก 2 ชั้น กริด 3×4, ฐานราก, FlatSlab + Drop, Truss โค้ง R 18.50 ม. ท่อ Ø101.6/Ø48.6, แบบ S-xx, layout Design/Est/San
- คำถามที่ส่งผู้ใช้ (รอคำตอบ): เกณฑ์ออกแบบเริ่มต้น, แผ่นดินไหว/ลม มาตรฐานใหม่หรือเก่า, รูปแบบประมาณราคาเอกชน, โหมดกริดอิสระ, Truss โค้ง/ท่อ

### รูปเล่มรายการคำนวณ (ผู้ใช้ส่ง cover/Column-1/Column-2/Beam26/Beam27.pdf + ภาพแผ่นข้อกำหนด) — อนุมัติแผน «ตามที่แนะนำ»
คำตอบผู้ใช้ข้อ 1–5 = ตามที่แนะนำ: (1) ปุ่มเลือก SDM วสท. / WSD กทม. 2522 ค่าเริ่ม SDM (2) แผ่นดินไหว/ลม มยผ. ปัจจุบัน + สูตรเก่าเป็นทางเลือก
(3) เพิ่มประมาณราคาเอกชน 8 หมวด (4) เพิ่มโหมดกริด (5) Truss โค้ง + เหล็กท่อ
รูปเล่ม (A3 แนวนอน กรอบเส้นเดียว): ปก (รายการคำนวณโครงสร้าง / โครงการ / เจ้าของ / สถานที่) · แผ่นข้อกำหนด
(fc′, fc, ตัวคูณ 1.4/1.7, SR24/SD30/SD40 fy fs n k j R, หน่วยแรงยอมให้คอนกรีต, น้ำหนักบรรทุกจรตามประเภทอาคาร 200/250/400/500,
หลังคา 50, ผนัง 180/90/25, ลมเมือง 60/80/120 และชายทะเล 100/120/160 ตามความสูง ≤10/10-20/20-40 ม., φ 0.90/0.85/0.75/0.70)
· แผ่นคานต่อแนวกริด: Load / Shear / Moment Diagram + ตารางต่อช่วง (NO. กว้าง ลึก ยาว span ระดับ · Moment L/M/R, Mc, Ast, Asb,
เหล็กบน/ล่าง จำนวน, As used, ระยะ M0 · Shear R, Rd(ที่ d), Vc, Rd−Vc, ปลอก@, Vs) · แผ่นเสาเป็นการ์ดต่อชั้นต่อกริด
(P, เหล็กยืน, ปลอก, As, Ag, Pg, fc′, 0.85Ag(0.25fc′+fs·Pg) สีแดง) · ลายเซ็นผู้คำนวณมุมขวาล่าง (ผู้ใช้: นายเวนิช ธัมมะวงษ์ ปวส.ช่างก่อสร้าง)
ลำดับทำ: (ก) รูปเล่มนี้จาก wanic_calc + preset WSD กทม./ตารางลม → (ข) Truss Matrix → เหล็กรูปพรรณ → โหมดกริด → แป → FlatSlab → แรงด้านข้าง → ราคาเอกชน

- [x] (ก) รูปเล่ม (เปลี่ยนเป็น A4 แนวนอนตามผู้ใช้ · ลายเซ็นค่าเริ่ม «นายเวนิช ธัมมะวงษ์ / วิศวกรสำรวจ» แก้ได้) — อนุมัติแล้ว · — `3d/core/wanic_calc_book.py` (make_book) + ปุ่ม «รูปเล่มรายการคำนวณ A3» ในขั้น 9 + ช่องโครงการ/เจ้าของ/สถานที่/ผู้คำนวณ/คุณวุฒิ
  ใน «ค่าที่ใช้ออกแบบ…» · analyse() คืน "cards" (น้ำหนักเสาทุกชั้น/ตอม่อ) และ BeamResult มี mark/spec/level/axis/line/z
- [x] (ข) Truss Matrix — `3d/core/wanic_truss.py` (make 7 แบบ: howe pratt fink warren kingpost parallel arch + custom(); solve() stiffness 2D; design() ASD เลือกท่อ/กล่อง/ตัวซี ที่เบาที่สุดต่อกลุ่ม top/bottom/web, วนน้ำหนักตัวเอง; base plate; params_of/design_of อ่าน data["truss"]),
  `3d/core/wanic_truss_view.py` (draw_truss, TrussDialog, truss_pages ในรูปเล่ม A4 เมื่อมี data["truss"]), ปุ่ม «ออกแบบ Truss…» ในแถวทรงหลังคา (RCPanel.edit_truss),
  tests/test_wanic_truss.py (5) อยู่ใน CI แล้ว — **รออนุมัติหน้าจอ** (ส่งภาพ howe/arch/หน้ารูปเล่มแล้ว)
- [x] Truss อนุมัติแล้ว + Truss เขียนเอง (CustomTrussDialog ตารางจุดต่อ/ชิ้นส่วน, T.build(p)) + รอยเชื่อมส้นโครง E70 (plate["weld"])
- [x] เหล็กรูปพรรณ — `3d/core/wanic_steel.py` (WF/H คำนวณคุณสมบัติจากขนาด, ASD: Fb (Lc/F1-8), Fv, Δ L/360, เสา Fa+interaction Cm 0.85, base plate 0.35fc′; design_building ใช้ analyse แบบ WSD = น้ำหนักใช้งาน, คาน level≥1, เสา floor≥0, จัดกลุ่ม mark+ชั้น),
  `3d/core/wanic_steel_view.py` (SteelDialog 3 แท็บ, steel_pages ในรูปเล่มเมื่อมี data["steel"]), ปุ่ม «ออกแบบเหล็กรูปพรรณ…», tests/test_wanic_steel.py (4) ใน CI — **รออนุมัติหน้าจอ**
- [x] เหล็กรูปพรรณอนุมัติแล้ว
- [x] โหมดกริด — wanic_rc.parse_spacings/grid_rooms/apply_grid (ห้องต่อช่อง, data["grid"]), `3d/core/wanic_grid_view.py` GridDialog (คลิกเว้นช่อง),
  ปุ่ม «โหมดกริด: สร้างผังจากเส้นแกน…» ในขั้น 1, tests/test_wanic_grid.py ใน CI — อนุมัติแล้ว + ตัวเลือก «มีผนังภายในตามแนวกริด» (settings["inner_walls"]=False → ผนังเฉพาะรอบนอก)
- [x] แป/Sag Rod/Tie Rod/ผนังเมทัลชีท — `3d/core/wanic_purlin.py` (LipC เส้นกลางความหนา, purlin_check ASD Mx+My+Δ L/180+แรงยกลม, rod_for 0.6Fy·0.75A, X-bracing จากลมหน้าจั่ว, girt), `3d/core/wanic_purlin_view.py` (PurlinDialog + ผังแป, purlin_pages เมื่อมี data["purlin"]), ปุ่ม «แป / Sag Rod / Tie Rod…», tests/test_wanic_purlin.py ใน CI — **รออนุมัติ**
- [ ] ถัดไป: FlatSlab → แรงด้านข้าง → ราคาเอกชน
