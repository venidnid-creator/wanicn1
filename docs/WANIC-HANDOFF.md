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
- [x] แป/Sag Rod/Tie Rod/ผนังเมทัลชีท — `3d/core/wanic_purlin.py` (LipC เส้นกลางความหนา, purlin_check ASD Mx+My+Δ L/180+แรงยกลม, rod_for 0.6Fy·0.75A, X-bracing จากลมหน้าจั่ว, girt), `3d/core/wanic_purlin_view.py` (PurlinDialog + ผังแป, purlin_pages เมื่อมี data["purlin"]), ปุ่ม «แป / Sag Rod / Tie Rod…», tests/test_wanic_purlin.py ใน CI — อนุมัติแล้ว
- [x] Flat Slab + Drop (DDM) — `3d/core/wanic_flatslab.py` (min_thickness, design: Mo, สัมประสิทธิ์ช่วงใน/ริม, แถบเสา 75/60/100%, As SDM/WSD ≥0.0018bh, punching รอบเสา/รอบ drop เสาใน/ขอบ/มุม; ช่วงจาก data["grid"] หรือ grid_axes),
  `3d/core/wanic_flatslab_view.py` (FlatSlabDialog + ผังแถบเสา/drop, flatslab_pages เมื่อมี data["flatslab"]), ปุ่มในขั้น 5 พื้น, tests/test_wanic_flatslab.py ใน CI — อนุมัติแล้ว
- [x] แรงด้านข้าง — `3d/core/wanic_lateral.py` (level_weights จาก cards แบบ DL, seismic มยผ.1301/1302-61 Fa/Fv/SDS/SD1/T/Cs + k / สูตรเดิม ZIKCSW, wind มยผ.1311-50 q·Ce·Cg2·Cp1.3 / กฎกระทรวง 6, analyse ตรวจเสา P-M ด้วย 0.75(1.4D+1.7L+1.87E/1.6W); eq_on=False ค่าเริ่มต้น (ต้องกรอก Ss/S1 ตามอำเภอ)),
  `3d/core/wanic_lateral_view.py` (LateralDialog, รูปด้านแรงแต่ละระดับ, lateral_pages เมื่อมี data["lateral"]), ปุ่ม «แรงด้านข้าง (แผ่นดินไหว/ลม)…» แถวล่าง, tests/test_wanic_lateral.py ใน CI — อนุมัติแล้ว
- [x] ประมาณราคาเอกชน 8 หมวด — `3d/core/wanic_private_est.py` (ใช้ Q.compute แล้วจัด 8 หมวด, waste_kind แก้ % ได้, ราคาต่อหน่วยแก้ได้เก็บตามชื่อรายการ data["private_est"]["prices"], เหล็กที่ออกแบบ Truss/WF-H/แป เพิ่มตามน้ำหนัก, ดำเนินการ/กำไร % + VAT 7%, save_xlsx 2 แผ่น),
  `3d/core/wanic_private_est_view.py` PrivateEstDialog; ปุ่มใน BoqDialog («💼 ประมาณราคาเอกชน 8 หมวด») และแถวล่าง RCPanel, tests/test_wanic_private_est.py ใน CI — **รออนุมัติ**
- [x] preset SDM/WSD — wanic_calc.PRESETS (วสท. SDM fc′240 SD40 / กทม.2522 WSD fc′173 SD30), LIVE_LOADS (กฎกระทรวง 6 ข้อ 15), fy_of/fs_of (fs = 0.5fy ≤ 1700) ใช้แทน bar.fy ทุกจุดใน calc/book; กล่อง «ค่าที่ใช้ออกแบบ…» มีชุดค่ามาตรฐาน + ประเภทการใช้อาคาร + fy ข้ออ้อย — **รออนุมัติ**
- [ ] ถัดไป: ครบตามแผนที่อนุมัติแล้ว → ตัวติดตั้งรุ่นใหม่ (รวมทุกส่วน) เมื่อผู้ใช้สั่ง; ผู้ใช้ยังไม่ได้รายงานผลทดสอบ 2026.11.11.1 → ตัวติดตั้งรุ่นใหม่ (รอผู้ใช้สั่ง)

## แผนรอบใหม่ (อนุมัติ 2026-11-12) — หลังศึกษาชุดงาน QD (main.pdf คู่มือ, ชุดแบบ A-01..13 S-00..13 SN-01..05, รายการคำนวณ)
1. [x] (อนุมัติแล้ว) แบบโครงสร้างจากผลคำนวณ — `3d/core/wanic_struct_sheets.py` (beam_lines, beam_profile, s_footing_details, s_column_details, s_slab_details, s_typical_beam) ต่อท้ายกลุ่ม S ใน build_set; แปลนคานมีค่าระดับ; tests/test_wanic_struct_sheets.py ·: รูปด้านคานทุกแนว (Profile เหล็กบนเสริม L/4 ที่หัวเสา, เหล็กล่าง, ปลอก, หน้าตัดต้น/กลาง/ปลายช่วง) ·
       รูปฐานรากทุกเบอร์ (แปลน + รูปตัด, ทราย/คอนกรีตหยาบ 0.05) · หน้าตัดเสาแยกช่วงชั้น · รูปตัดพื้นต่อเนื่อง (L/4) ·
       รูปเหล็กคานทั่วไป (Start/Mid/End/CAN, L/4 L/5) · ค่าระดับกำกับคาน/พื้นในแปลน — `3d/core/wanic_drawings.py` กลุ่ม S
2. [x] (อนุมัติแล้ว) `3d/core/wanic_steel_sheets.py` (s_weld_standard, s_steel_connections, connection_rows, plate_rows; เพิ่มใน build_set เมื่อ has_steel) — แบบงานเหล็ก: มาตรฐานงานเชื่อม + รอยต่อเสา-คาน/คาน-คาน ตามความลึกคาน + Turnbuckle (เมื่อมี data["steel"/"truss"/"purlin"])
3. [x] (อนุมัติแล้ว) `3d/core/wanic_calc_cards.py` (footing_rows/pages, slab_rows/pages + coef, roof_page, attach_lateral_moments → แถว Me, critical_members); make_book(critical=) ถามตอนส่งออก — รูปเล่ม: การ์ดฐานราก (P Mx My แรงดันดิน ความลึก As เหล็ก เฉือน Vc) · การ์ดพื้นพร้อมรูป (ทางเดียว/สองทาง) · หน้าหลังคาแยกชิ้น (Z=M/Fy, แอ่น) · แถว Me · พิมพ์เฉพาะตัววิกฤต
   + [x] (อนุมัติแล้ว) คำแนะนำเมื่อไม่ผ่าน — `3d/core/wanic_advice.py` (beam/column/slab/footing/roof_advice, advise, mark_fixes, apply_fixes + R.suggest, fit_in_row); คอลัมน์ «คำแนะนำ» ขั้น 9, ปุ่ม «แก้ตามคำแนะนำ (ทุกเบอร์)», หน้า Advice ในรูปเล่ม
   + [x] (อนุมัติแล้ว) แก้รายชิ้น — `3d/core/wanic_fix_view.py` FixDialog/apply, wanic_advice.member_fix (คิดจากชิ้นวิกฤตของเบอร์), ปุ่ม «แก้ชิ้นที่เลือกให้ผ่าน…»/ดับเบิลคลิกแถว → บันทึก → bp.build(structure, roof) → คำนวณใหม่ (RCPanel._rebuild_after_fix); «แก้ตามคำแนะนำ (ทุกเบอร์)» ก็อัปเดตโมเดล
   + [x] สมมาตร/สมดุลทุกครั้งที่แก้ — wanic_advice.balance_spec(keep_shape) (เสาจัตุรัส เหล็กยืนหาร 4 / สี่เหลี่ยมผืนผ้าเลขคู่, คานบน-ล่างขนาดเดียวกัน, ฐานจัตุรัส) ใช้ใน mark_fixes, apply_fixes, FixDialog.apply และการแก้ตารางขั้น 2–6 (keep_shape=True)
   + [x] (รออนุมัติภาพ) SFD/BMD ตามหลักวิศวกรรม + เส้นกำลังที่รับได้ — wanic_calc: res.caps (φMn ล่าง/บน, φVn, φVc / Ma ASD, แอ่น) ทุกคานและชิ้นหลังคา; wanic_calc_view.draw_diagrams ใหม่ (Load diagram ลูกศรน้ำหนัก R1..Rn, SFD บวกด้านบน, BMD ด้านรับแรงดึง, Vmax/M±max @x, V=0 / M=0, เส้นประกำลัง, บรรทัดอัตราส่วน); รูปเล่ม _diagram_strip มีเส้นกำลัง
   + [x] (อนุมัติแล้ว 12 พ.ย.) «รับเพิ่มได้อีก» ภาษาง่ายทุกชิ้นส่วน — wanic_calc.Member.qty/qty_unit/qty_factor, reserve, reserve_text() (พื้น กก./ตร.ม. น้ำหนักจร ÷1.7 · คาน กก./ม. · เสา/ฐาน ตันต่อต้น · หลังคา กก./ตร.ม. · >5 เท่าเขียนว่า «รับเพิ่มได้อีกมาก»), reserve_summary() (ตัวที่หนักที่สุดของแต่ละกลุ่ม); ขั้น 9 คอลัมน์ «รับเพิ่มได้อีก (ภาษาง่าย)» + สรุปบนตาราง; บรรทัดล่าง SFD/BMD; รูปเล่ม reserve_page หลังหน้าสรุป; รายการคำนวณ PDF; test_reserve_in_plain_words. ถัดไป: แผนข้อ 4 (น้ำหนักจุด/แผ่บนคาน, คานยื่น, Checkload)
   + [x] (รออนุมัติภาพ) แผนข้อ 4 — น้ำหนักเพิ่มบนคาน / คานยื่น / Checkload:
     - [x] wanic_calc.Span มี U (น้ำหนักแผ่บางช่วง a,b,w) และ cant ("L"/"R"); solve_beam รองรับคานยื่น (โมเมนต์ที่ฐานรู้ค่า ไม่เพิ่มจุดรองรับ) BeamResult.supports; ตรวจด้วยมือแล้ว (4 ม.+ยื่น 1 ม. P=1000 ปลาย → M=-1000, R=-250/1250)
     - [x] wanic_calc_view / wanic_calc_book วาดจุดรองรับจาก res.supports, น้ำหนักจุด P และแผ่ U สีม่วง
     - [x] data["beam_loads"] = [{"level","axis":"x|y","line":c,"a","b","P"|"w","type":"D|L","note"}] พิกัดตามแนวแกน (a=b = น้ำหนักจุด) → analyse ใส่ลง Span (คูณ D_/L_)
     - [x] data["cantilevers"] = [{"level","x","y","dir":"+x|-x|+y|-y","L","mark"}] → B.elements เพิ่มคาน "cant": True (โมเดล 3D/แบบ/BOQ ได้อัตโนมัติ) → analyse ทำ Span(cant=...) และแรงปฏิกิริยาเฉพาะจุดรองรับ
     - [x] checkload(data, res): ต่อเสาชั้นล่าง Wcol (ตัน ใช้งาน), Wcol-Area (พื้นที่รับน้ำหนักรวมทุกชั้น+หลังคา), Wfloor = Wcol/พื้นที่ (กก./ตร.ม.) เทียบช่วงปกติ 800–1,500 → หน้ารูปเล่ม + ปุ่มขั้น 9
     - [x] UI core/wanic_beamload_view.py: ขั้น 4/6/9 ปุ่ม «น้ำหนักเพิ่มบนคาน…» (เลือกคาน + ของที่วางสำเร็จรูป) «คานยื่น…»; ขั้น 9 «Checkload (ตรวจน้ำหนักลงเสา)…»; รูปเล่มหน้า Checkload; SFD ขั้นบันไดตรงน้ำหนักจุด (_stations); tests/test_wanic_beamload.py (ใส่ใน CI แล้ว); skill-venit อัปเดตแล้ว
     - อนุมัติแล้ว (13 พ.ย.)
   + [x] (รออนุมัติภาพ) แผนข้อ 5 — บันได คสล. ช่วงตรง / ตัว L / สองช่วง:
     - wanic_building: STAIR_TYPES, stair_type, stair_layout (flights p0/d/n/L/z0/w, landings pts/z, rect; x,y = กลาง footprint; turn left/right; U มีช่องว่าง STAIR_GAP 0.10), flight_rect, stair_plan (polys/treads/walk), stair_rect = กรอบ; stair_members (ช่วงบันได family "stair" + ชานพัก rect) ใช้ใน structure_members; ผัง (wanic_drawings.draw_stairs, plugins/wanic_building) และ BOQ (wanic_quantities หมวด 5 รวมชานพัก) อ่านจาก layout
     - core/wanic_stair.py: params (stair_bars DB12@0.15, stair_temp RB9@0.15, stair_ll 300, stair_beam "0.15x0.35 2-DB12/2-DB12 RB6@0.15"), geometry_checks (กฎกระทรวง 55: ลูกตั้ง ≤ 20, ลูกนอน ≥ 22, กว้าง ≥ 0.80, ช่วงละ ≤ 3.00 ม., 2R+T 60–65 แนะนำ), design (พื้นทางเดียวพาดตามแนวบันได, ชานพักรวมช่วง, solve_beam + U, φMn/φVc, L/20, As min, เหล็กกันร้าว 0.0025/0.0018bt, คาน BS1), designs(data), suggest/apply_all/advice_for/find_stair; ค่าเฉพาะบันได st["t","bars","temp","w","type","turn"]
     - analyse เพิ่ม group "stair" และ res["stairs"]; GROUP_PLAIN/ชื่อกลุ่มใน UI/PDF; wanic_advice (advise, advice_by_member, member_fix target "stair", apply_fixes เรียก ST.apply_all); wanic_fix_view รองรับ target "stair"/"none"
     - UI core/wanic_stair_view.py StairDialog (ตาราง แบบ/เลี้ยว/กว้าง/หนา/เหล็ก, ภาพผัง, ผลตรวจสด, ปุ่มปรับให้ผ่าน) ปุ่ม «บันได คสล.…» ขั้น 5 และ 9; รูปเล่ม stair_page (รูปตัดคลี่ เหล็ก คาน BS1 ตาราง)
     - อนุมัติแล้ว (13 พ.ย.)
   + [x] (รออนุมัติภาพ) แผนข้อ 6 — แผ่น A / SN / EE:
     - core/wanic_sanitary.py: SEPTIC_SIZES (ย้ายมาจาก drawings), GT_SIZES (ค่าแนะนำของเราเอง), SCREEN_PIT, users_of (settings "users" หรือ ห้องนอน×2 ขั้นต่ำ 4 — รับทั้ง data และ B.elements), septic_pick/grease_pick (เกินถังใหญ่สุด → หลายถัง), design, design_lines; settings DEFAULT "users": 0 + ช่องในแท็บออกแบบอาคาร (หมวดฝ้า/งานระบบ)
     - SN: ผังมี ST {ลิตร} ({คน}), GT {ลิตร}, SP บ่อพักตะแกรง → ท่อระบายสาธารณะ (GT และ ST ออกผ่าน SP); SN-01 ข้อมูลการออกแบบ + สัญลักษณ์ SP/MH + ข้อกำหนด 12 ข้อ; SN-04 ตารางถังบำบัดไฮไลต์แถว «ใช้»; แผ่นใหม่ SN-05 sn_traps (รูปตัด GT 1:10, SP 1:10, ตาราง GT, ข้อมูลออกแบบ) — 3D ภาพเลื่อนเป็น SN-06
     - BOQ (wanic_mep.bill) ใช้ขนาดเดียวกับแบบ + บ่อพักตะแกรง SP; ข้อมูลถังใน 3D ตามขนาดที่เลือก
     - EE_NOTES 10 ข้อ (ขนาดสาย/เบรกเกอร์ สายดิน ≤ 5 โอห์ม RCD 30 mA ท่อร้อยสาย การยื่นขอมิเตอร์)
     - A: room_codes (พ / ผ2 ทาสี / ผ3 กระเบื้อง / ฝ ตาม ceiling_type) ในป้ายห้อง; elev_marker A B C D ในห้องน้ำบนแปลน (อ้างเลขแผ่นรูปด้านภายใน); A-13 ใช้ชื่อ A–D และปรับมาตราส่วน/ระยะให้พอดีกรอบ; A-01 แก้ข้อความทับตาราง + ตารางวัสดุผิวห้อง room_schedule + สัญลักษณ์รูปด้านภายใน
     - ห้ามใช้อักษรที่ cp874 ไม่มี (เช่น ✓) ในแผ่นแบบ — DXF จะเป็น «?» (test_dxf_holds_every_sheet_in_thai)
     - tests/test_wanic_sanitary.py (ใน CI) · อนุมัติแล้ว (13 พ.ย.)
   + [x] (รออนุมัติภาพ) แผนข้อ 7 — เสาเข็ม 2 ขนาด · กำลังเข็มจากผลทดสอบ:
     - core/wanic_pile.py: SECTIONS (I18–I30, สี่เหลี่ยม 0.25–0.40, สปัน Ø0.30–0.50, เข็มเจาะ Ø0.35–0.60: ชื่อ รูปทรง ขนาด A P fc′ — ค่าประมาณ), METHODS given/static/dynamic/hiley/soil, FS_DEFAULT 1/2.0/2.5/3.0/2.5, DEFAULT_TYPES P1 (I18 6 ม. given = basis pile_cap) P2; types_of(data,b_), capacity(t) (Hiley Qu = e·W·H/(S+C/2) หน่วย ตัน·มม./มม.; ดิน Σfs·P·t + qb·A; กำลังตัวเข็ม 0.25fc′Ac; Qa = min), type_of_spec, cap_of, pile_text
     - data["piles"] = {"P1": {...}, "P2": {...}}; footing spec "pile": "P1"/"P2"; B.library_of เมื่อมี data["piles"] ตั้ง pile_b/pile_len/pile_name/pile_shape ตามชนิด (เอกสารเก่าไม่เปลี่ยน); 3D เข็มกลมใช้ family "pile"; BOQ ชื่อเข็มตามชนิด
     - wanic_calc footing ใช้ cap ต่อเบอร์ ชื่อ «เข็ม n ต้น (P1)»; calc_cards rows มี pcap/ptype; advice ใช้ pcap; บรรทัดหัวขั้น 9 และ PDF ใช้ pile_text
     - UI core/wanic_pile_view.py PileDialog (P1/P2 คู่กัน ผลสด, ตารางฐานราก จำนวนเข็ม + เลือก P1/P2) ปุ่ม «เสาเข็ม 2 ขนาด / กำลังเข็ม…» ขั้น 2 และ 9; รูปเล่ม pile_page
     - tests/test_wanic_pile.py (ใน CI; ต้อง deleteLater dialog กัน segfault ตอนปิด) · อนุมัติแล้ว (13 พ.ย.)
   + [x] (รออนุมัติภาพ) แผนข้อ 8 — เขียนแบบอิสระ (ทำครบแล้ว):
     - core/wanic_free.py: chains_from_edges (แยกสายที่จุดแตกกิ่ง, curved จาก edge.curve/soft), add_from_chains (auto แยกช่วงดิ่งเป็นเสา), free_of, length2/3, supports_of (ปลาย + จุดที่มีเสาในระยะ 5 ซม.), members (กวาดหน้าตัดตามทั้งสาย: คาน anchor "tc", เสา, ผนัง "bc"), analyse_free (w ต่อเมตรแนวราบ = น้ำหนักตัวเอง×L3/Lh + w เพิ่ม + ผนังอิสระบนคาน; ปฏิกิริยาเข้า col_load/col_lv ของเสาเดิม; เสาอิสระตรวจ P-M; คานโค้งเตือนแรงบิด) — เรียกใน wanic_calc.analyse ก่อนส่วนเสา + ฐาน F1 ใต้เสาอิสระที่ไม่มีฐานกริด
     - B.elements มี E["free"]; structure_members เพิ่ม FR.members; BOQ หมวด 3b คาน/เสาอิสระ (คอนกรีต ไม้แบบ เหล็ก) + ผนังอิสระในหมวดผนัง; drawings bbox รวมชิ้นอิสระ, draw_free ในแปลน A (ผนัง เสา) และแปลนคาน S (คาน «B1 เอียง +3.00→+4.00» / «โค้ง»)
     - UI core/wanic_free_view.py: FreeConvertDialog (คลิกขวาที่เส้นที่เลือก «แปลงเส้นที่เลือกเป็น คาน / เสา / ผนัง…» — ลงทะเบียนใน plugins/wanic_rc.setup ผ่าน app.add_context_menu), FreeListDialog (ปุ่ม «ชิ้นส่วนเขียนอิสระ…» ขั้น 6 และ 9: แก้เบอร์ น้ำหนักเพิ่ม ลบ); แปลงพิกัดในกลุ่มด้วย plugins.wanic_profiles._matrix_of
     - แก้ (ผู้ใช้แจ้ง «ตำแหน่งไม่ตรงกัน»): โมเดลยกทั้งอาคารขึ้น floor_lift (0.60) — เส้นที่วาดบนโมเดลเป็นพิกัดโมเดล ต้องลบ lift ก่อนเก็บ (FR.model_to_building ใน convert_selection) · ตรวจแล้ว x,y ตรงกับแปลน (มุมมองบนของ 3D เทียบ A-03/S-04) · test_lines_drawn_on_the_model_keep_their_place
     - _rebuild_after_fix คำนวณใหม่เมื่อไม่ได้อยู่ขั้น 9 (เดิมสถานะ «ผ่านทุกรายการ» ผิด)
     - tests/test_wanic_free.py (ใน CI) · แผนจากการศึกษา QD ครบทั้ง 8 ข้อแล้ว (อนุมัติ 13 พ.ย.)
   + [ ] ตัวติดตั้ง 2026.11.13.1 (ผู้ใช้อนุมัติ 13 พ.ย.) — dispatch build-windows.yml ref claude/youthful-pascal-ctgtr0 inputs {version: 2026.11.13.1, release: false} → run 43411762994 · artifact wanicnsurvey-setup-2026.11.13.1 · ห้ามเผยแพร่จนกว่าผู้ใช้สั่ง (dispatch เดิม release=true)
   + (ข้อมูลออกแบบเดิมของข้อ 8):
     - ออกแบบ: data["free"] = {"beams": [{"pts": [[x,y,z]…] (ม.), "mark" (เบอร์คานในคลัง), "curved", "w" (กก./ม. เพิ่ม)}], "columns": [{"x","y","z0","z1","mark"}], "walls": [{"pts": [[x,y]…], "z", "h", "t", "curved"}]}
     - core/wanic_free.py: chains (แยกเส้นที่เลือกเป็นสาย, ใช้ core.sweep.order_path_edges เหมือน plugins/wanic_profiles.path_from_selection), classify (แนวดิ่ง → เสา, ระดับพื้น → ผนัง/คาน ตามที่ผู้ใช้เลือก), members 3D (กวาดหน้าตัดตามเส้นทั้งสาย — โค้ง/เอียงได้), BOQ, analyse (คานอิสระ: จุดรองรับ = ปลาย + จุดที่มีเสา; น้ำหนักตามแนวราบ /cos; คานโค้งเตือนแรงบิด; ปฏิกิริยาลงเสาเดิมเข้า col_load; เสาอิสระตรวจ P-M + ฐาน F1)
     - UI: เมนูคลิกขวา «แปลงเส้นที่เลือกเป็น คาน/เสา/ผนัง» + หน้าต่างรายการชิ้นส่วนอิสระในแผง คสล.; วาดในแปลน A/S
     - (เดิม) แผนข้อ 6 (A-01 สัญลักษณ์/รหัสวัสดุ ป้ายห้อง ABCD ตารางประตูหน้าต่าง บ่อดักไขมัน/บ่อตะแกรง ถังบำบัดตามจำนวนคน รายการ EE/SN)
4. [ ] ออกแบบคาน: น้ำหนักจุด/แผ่เพิ่มเอง · คานยื่น · Checkload (Wcol / Wcol-Area / Wfloor)
5. [ ] บันได คสล. ช่วงตรง / L / 2 ช่วง + คานชานพัก + รูปตัด
6. [ ] A-01 สัญลักษณ์ + รหัสวัสดุ F/W/C · ป้ายห้อง · ABCD · ตารางประตู-หน้าต่าง · บ่อดักไขมัน/บ่อตะแกรง · ถังบำบัดตามจำนวนผู้ใช้ · ข้อกำหนด EE/SN
7. [ ] เสาเข็ม 2 ขนาด · กำลังเข็มตามผลทดสอบ
8. [ ] เขียนแบบอิสระ: เสา/คานตามเส้นร่าง · คานโค้ง/เอียง · ผนังโค้ง
(ไม่คัดลอกตาราง/แบบ/โค้ดของ QD — ถังบำบัดคิดจากจำนวนผู้ใช้เอง)
