# History — from the first commit to now

Owner: นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ). Repository `venidnid-creator/wanicn1`, branch `claude/youthful-pascal-ctgtr0`.
Every version below was built as a Windows installer by `.github/workflows/build-windows.yml`. Versions up to
2026.11.07.5 were released; from 2026.11.11.1 on they were built for the owner to test (`release=false`) and are
**not published** unless the owner orders it. Details per version: `WANIC-CHANGELOG.md`, `installer/release-notes.md`;
the step-by-step log: `docs/WANIC-HANDOFF.md`.

## 1. October 2026 — the suite is born

| Version | What |
|---|---|
| 2026.10.28 – .28.5 | WANICNSURVEY = IngeCAD 0.6.7 (2D, `cad/`) + IngeTrazo 0.5.8 (3D, `3d/`) in Thai, one Inno Setup installer, CI. .2 ถอดปริมาณ · .3 โปรไฟล์ · .4 ออกแบบอาคาร · .5 roof follows the plan, doors/windows/stairs, ปร.1–ปร.4 (หลักเกณฑ์ 2569). |
| 2026.10.29 – .29.5 | Part library, BOQ 2569, new plan page; copyright in the owner's name; eaves, barge boards, real doors/windows, sanitary ware, room finishes; Monier tiles and caps; roof frame on beams. |
| 2026.10.30 – .30.7 | Province selection; Ministry of Commerce (สนค.) prices by province and month, market fallback; full 2D set export (A · S · SN · EE · M); ปร.4 appended to the drawing set. |
| 2026.10.31 – .31.9 | WANIC ออกแบบถนน: survey import (CL codes, N/E swap of GNSS files), alignment through field PI stakes, vertical curves, cross sections, earthworks, Google Earth, province/district, pavement layers ทช./ทล., A3 road sheets, site map, Thai DXF text, signature boxes. |

## 2. Early November — building, MEP, roads

| Version | What |
|---|---|
| 2026.11.03 – .03.3 | Factor F (ว481), parts cut cleanly, valleys, caps, soffits, structure view, new start screen, full ว480 labour list, layers, standard walls/roof frames, 15 BOQ categories, door/window positions, MEP (categories 11–15), sections, cover/contents. |
| 2026.11.04 – .04.6 | Rebar details, transparency, download counters, version warning, bathrooms with standard plumbing, septic tank, 3D section views, standard trusses, manila/lean-to roofs. |
| 2026.11.06.1 – .06.3 | Raised floor for pipes, pipe fittings, round septic tank, gutters/downpipes, automatic bathroom layout; pavement thickness AI 1970 (asphalt) and Road Note 29 (concrete) vs ทช. standards. |
| 2026.11.07.1 – .07.5 | SD standard pavement sheets (ทถ-2-201/202/302/303); RN29 charts; sign-in before use; drainage DR (ทถ-5), signs TS (ทถ-3); cut/fill sections; road BOQ; superelevation/widening (ทถ-2-104); N E Z and satellite image in the model; Arabic digits everywhere. |
| ReadWanicn2027 **2027.3.0** (released, `readwanicn-v2027.3.0`) | Thai PDF program: sign-in, statistics, saraban documents, spreadsheet, PDF editing, snap, CAD import, printing. Later 2027.4.x on branch `claude/zen-feynman-ptcfng` (update window with download — the model for WANICNSURVEY's). |

## 3. Structural design (11–16 November)

| Version | What |
|---|---|
| **2026.11.11.1** | Start screen 2027 (5 themes, ไทย/EN, 4 cards, developer panel); RC structure design (8 steps grid → rebar/BOQ); structural calculation step 9 (loads roof → piles, continuous beams, SFD/BMD, slab coefficients, P-M, wind); symmetric gables, Thai roof, double gable, timber frame; fast selection; live part data. |
| **2026.11.12.1** | A4 calculation booklet; Truss (matrix, 7 forms + custom, ASD, base plate, welds); steel H/WF; grid mode; purlins/sag rods/tie rods/sheet walls; flat slab + drop (DDM); lateral loads (current + old standards); private estimate 8 categories; SDM/WSD presets. |
| QD study plan 1–8 (approved 12 Nov) | Learned the workflow of a commercial program (QuickDesign) the owner showed — never its code. 1 S sheets from the calculation · 2 steel sheets · 3 booklet cards, advice, per-member fix, symmetric edits, SFD/BMD with capacity lines, «รับเพิ่มได้อีก» · 4 beam point/partial loads, cantilevers, Checkload · 5 RC stairs straight/L/U · 6 A/SN/EE sheets, septic/grease trap by users · 7 two pile sizes, capacity from tests · 8 free drafting (lines → beams/columns/walls, curved/inclined). |
| **2026.11.13.1 / .13.2** | Everything of the QD plan; code checks (exterior −wL²/16, ACI 9.5 min depth + deflection, slender columns, stumps P-M, service load ÷1.4); every panel fits the screen (`ui_fit`). `tools/verify_hand_calc.py` compares the program with 27 hand values. |
| **2026.11.15.1** | Synced with upstream IngeTrazo 0.6.2.1 / IngeCAD 0.8.0 (3-way merge); 5× faster rebuild (hidden tabs don't recount); fewer buttons (menus). |
| **2026.11.16.1** | P1 calc book in plain words («กระทำ / รับได้ / ใช้ไป %»), fail dialog that offers fixes · P2 door/window swing symbols · P3 automatic stairs (6 positions) + railings + stair openings · P4 permit drawing set by storey count · P5 BOQ price gate (0 until a province, orange rows, no export until priced) · P6 per-room MEP. Teaching clip 4:15 min sent 17 Nov. |

## 4. Drawings like the government standard sets (17–23 November)

The owner sent 5 standard house sets of กรมโยธาธิการและผังเมือง and asked for drawings «เหมือน 100 % ทุกแผ่น ยกเว้นกรอบเซ็นชื่อ».
Done sheet by sheet with screenshots and approval: A (index, specification, plans with tags/levels/markers, elevations,
sections, details) → S (S-07/S-09 three rounds: stirrup hooks, footings + ring bar, piles; stairs and slabs) → SN (SN-01..SN-10:
plans, pipe isometrics, septic/grease trap, standard bathroom details, hanger table) → EE (EE-01..EE-06: index/specs, main
panel single line, lighting and socket plans with circuits) → M (M-01, M-02: A/C and ventilation). Modules `wanic_std_sheets`,
`wanic_std_ee`, `wanic_std_m`, `wanic_struct_sheets`, `wanic_stair_sheets`.

## 5. Plan groups ข → ค → ง → จ → ฉ (24–25 November)

- **ข structure/calculation**: ข1 auto-design until really passing (`wanic_autodesign`) · ข2 pass/fail on every RC menu ·
  ข3 DL/LL separate load cases, reactions, SFD/BMD graphs, load-behaviour picture · ข4 new booklet cover/layout ·
  ข5 standards from the owner's PDFs (กฎกระทรวงการออกแบบโครงสร้างอาคาร 2566 + ประกาศ มท. 2567, seismic by province) ·
  ข6 no material list until designed · ข12 from the owner's own WanicnDesign program (written ourselves): plane frames +
  storey drift (`wanic_frame`), combined footings (`wanic_combined`), live-load reduction (never for ข้อ 14 uses),
  precast slabs, fire rating + column cover set automatically (`wanic_fire`), 10 m bar cutting list (`wanic_cutting`),
  CPM schedule + S-curve + installments (`wanic_schedule`).
- **ค model/menus**: stairs (head/tail swap, drag in preview, SB1/SB2 beams, landing at the column line, railings + newels),
  ceilings only on the top floor (bathrooms below), no wall across open corridors, roof members only touching, toggles per
  structure kind, skirting chips, copy/paste rooms, copy floor up, 3D furnishing preview, free beams loading main beams.
- **ง BOQ/prices**: only items in the model; every line needs material and labour; price checkers; sources ว480 labour →
  พาณิชย์จังหวัด → central → neighbouring provinces → orange; สพฐ. book only for สพฐ. jobs (`wanic_obec`); import commerce
  lists from xlsx/csv/docx/pdf (`wanic_province`).
- **จ roads** (items 30–39): pavement design summary «6. สรุปการออกแบบ» required before layers/model; THAI-PAVE workflow
  steps (traffic classes, design CBR percentile); English layer names; ทช./ทล. cross sections; 34 smooth curves + entry
  speed + plain-word curve tables; 35 «ปรับค่ากึ่งกลาง» (fit tangents + arcs, move CL shots N E Z, undo); 36 site check
  from a parcel file (LandsMaps unreachable from the cloud) with rai-ngan-wa and LC-01 PDF with UTM grid; 37 permission
  text on every sheet; 38 no drainage pipes in the road set; 39 no text over text on any sheet, north arrow in a free
  corner, upright station labels, balanced title block; glossary box on every sheet + glossary sheet.
- **Consistency rules (owner, 25 Nov)**: drawings PDF/DXF show exactly what the calc book checked; a changed model must be
  calculated again, every item (stamp + orange banner + exports recalculate); one change updates all — the calc book,
  drawings, BOQ and cutting list count bars with the same functions.
- **Start screen**: «มีเวอร์ชันใหม่» window with the installer download (like ReadWanicn2027 2027.4.11).
- **ฉ**: ฉ1 start screen in 7 languages (ไทย EN ລາວ Tiếng Việt Bahasa Indonesia 简体中文 繁體中文) · ฉ2 PDF import
  (vector → DXF) in the 2D program · ฉ3 A0–A4 paper blocks with the program's own font «เวนิช» (Venit = Charm renamed, OFL).

## 6. Installers built in this period (not published)

| Version | Run / artifact | Notes |
|---|---|---|
| 2026.11.11.1 | run 43021651986 | first RC design + calculation |
| 2026.11.12.1 | run 43147870896 | booklet, truss, steel, grid, purlins, flat slab, lateral, private estimate |
| 2026.11.13.1 / .2 | runs 43411762994 / 43457061167 | QD plan, code checks, screen fitting |
| 2026.11.15.1 | run 43725374411, artifact 14167181144 | upstream sync, speed |
| 2026.11.16.1 | run 43855541826, artifact 14222855838 | P1–P6 |
| **2026.11.25.1** | run 45629906678, artifact 15032262767 (311 MB, expires 2027-02-23) | groups ข–ฉ, consistency rules; first attempt 45606184696 failed 2 tests (old L/4 label; hand check on a footing now combined) — fixed 94ee98c. **Awaiting the owner's test and «อนุมัติเผยแพร่».** |
