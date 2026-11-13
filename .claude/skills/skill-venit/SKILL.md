---
name: skill-venit
description: Everything needed to continue work on WANICNSURVEY (cad/ 3d/ launcher/) and ReadWanicn2027 (readwanicn2027/) for Mr. Venit Thammawong (survey engineer) — the owner's working rules, the repository map, how to build/test/screenshot/release, the history from the first commit to now, the engineering conventions of every design module, and the agreed future roadmap. Use it at the start of any task in this repository, before changing code, building an installer or answering the owner.
---

# Skill Venit — WANICNSURVEY & ReadWanicn2027

Owner and certifying developer: **นายเวนิช ธัมมะวงษ์ (Venit Thammawong), วิศวกรสำรวจ (survey engineer)**.
Repository: `venidnid-creator/wanicn1`. Working branch: `claude/youthful-pascal-ctgtr0`.
Live, detailed state (Thai): `docs/WANIC-HANDOFF.md` — read it first, update it after every step.
Release history (Thai): `WANIC-CHANGELOG.md`, `installer/release-notes.md`.

---

## 1. The owner's rules (always)

1. **Reply in Thai.** Every menu, label, dialog, report and PDF in the programs is **Thai** with Thai fonts
   (TH Sarabun New / TH SarabunPSK / Laksaman / Tahoma fallbacks). Do not use brand names (Word, Excel) in the UI —
   say «ตารางคำนวณ», «เอกสาร».
2. **Screenshots for approval before any .exe.** Every new part: build it, test it, screenshot it (headless, see §3),
   send the images, wait for «อนุมัติ». Commit unapproved work with `[skip ci]` in the message.
3. **Ask when unsure** (AskUserQuestion), but when the owner says «ตามที่แนะนำ / อนุมัติ» proceed without asking again.
4. **Never publish a GitHub Release unless the owner says so.** Installers for testing are built with
   `release=false`; the owner tests the artifact first.
5. **Record everything so work can resume** («หากโทเคนหมด ให้บันทึกข้อมูลเก็บไว้ทั้งหมดเพื่อทำต่อ»):
   keep `docs/WANIC-HANDOFF.md` current; commit and push after each piece.
6. **Signature**: every report/booklet/BOQ carries «ผู้คำนวณ/ผู้พัฒนา นายเวนิช ธัมมะวงษ์» with qualification
   «วิศวกรสำรวจ» (editable in «ค่าที่ใช้ออกแบบ…», stored in `data["calc"]`). Every changelog entry ends with the signature block.
7. **Copyright**: the owner showed a commercial program (QuickDesign / HouseDemo / QuickSteel) from a flash drive only
   to learn the *workflow*. Never copy its code, UI, names or files; never upload its files to this public repo.
   Write everything ourselves from the engineering standards.
8. **Privacy**: never put credentials, the ReadWanicn licence key (GitHub secret `READWANICN_LICENSE_KEY`), the owner's
   e-mail or other private data into code, commits, prompts to outside services or messages.
9. The developer panel on the start screen is mandatory: photo, QR (LINE), phone, Krungsri account
   666-1-32472-1 with a copy button, «โปรแกรมใช้ได้ฟรี ไม่มีค่าลิขสิทธิ์».
10. Engineering output always states: «เครื่องมือช่วยคำนวณ — ต้องให้วิศวกรโยธาผู้มีใบอนุญาตตรวจและลงนามก่อนก่อสร้าง».

---

## 2. Repository map

| Path | What |
|---|---|
| `launcher/` | Start screen «WANICNSURVEY 2027» (`launcher.py`: THEMES ×5, TEXT th/en, CARDS 2D/3D/RC/ROAD; `wanic_login.py` sign-in; `stats.py` download/user counts). Passes `WANIC_LANG`, `WANIC_START_PANEL`, `WANIC_SESSION` to the programs. |
| `cad/` | WANICNSURVEY CAD (2D, fork of **IngeCAD 0.6.7**, GPL-3.0). Thai i18n; plugins `topografia` (งานสำรวจ: points, TIN, contours, profiles, sections, earthworks) and `terreno` (ภูมิประเทศ: georeference, lat/lon, DEM, satellite, KML). |
| `3d/` | WANICNSURVEY 3D (fork of **IngeTrazo 0.5.8**). WANIC plugins in `3d/plugins/` (auto-discovered, each has `setup(app)`); engineering logic in `3d/core/wanic_*.py` (never put helpers in `plugins/` — they would be loaded as plugins). Rust native engine in `3d/` built by CI. |
| `readwanicn2027/` | ReadWanicn2027 — Thai PDF program (measure, edit PDF, merge/compress, saraban documents, spreadsheet, CAD import, print, 3D viewer). Released as `readwanicn-v2027.3.0`. |
| `installer/` | Inno Setup script + `release-notes.md`. |
| `samples/` | Test data: `ทดสอบถนน-500ม.csv`, `…-GoogleEarth.kml`. |
| `tools/` | Helpers (e.g. ReadWanicn renewal codes). |
| `docs/WANIC-HANDOFF.md` | The handoff (Thai). |
| `.github/workflows/build-windows.yml` | WANICNSURVEY installer (inputs `version`, `release`), ~25–40 min; the pytest list of WANIC tests is in this file — add every new test file there. |
| `.github/workflows/readwanicn-windows.yml` | ReadWanicn installer/release. |

### 3D plugins (dock panels)
`wanic_building.py` ออกแบบอาคาร (panel `window._wanic_building`: `data()`, `_write(d)`, `set_rooms`, `build(parts)`,
`open_boq` → `BoqDialog`, `open_drawings` → `DrawingDialog`) · `wanic_rc.py` ออกแบบโครงสร้าง คสล. (`window._wanic_rc`,
`RCPanel`, 9 steps) · `wanic_road.py` ออกแบบถนน (`window._wanic_road`) · `wanic_takeoff.py` ถอดปริมาณ (ปร.1–ปร.4) ·
`wanic_profiles.py` โปรไฟล์. Hooks: `app.add_panel`, `app.add_menu_action`, `app.on_document_changed` (selection-only
changes are filtered out — keep it that way; it fixed the slow-selection bug).

### 3D core modules (engineering)
| Module | Purpose |
|---|---|
| `wanic_building.py` | Plan → elements (`B.elements(data)`: footings, stumps, columns, beams, slabs, walls, lib, settings, floors), library marks F1 PC1 C1 GB1 B1 RB1 S1 S2, roofs (`ROOF_TYPES` incl. thai, double; gable trusses on the gable wall), timber/steel frames, `settings["inner_walls"]`. |
| `wanic_quantities.py` | Government BOQ (กรมบัญชีกลาง 2569, ว480 labour, Factor F ว481, 17+ categories, province prices). |
| `wanic_takeoff.py` | Take-off, ปร.1–ปร.4 workbook; **own .xlsx writer** `_Sheet`/`_xlsx` (CI has **no openpyxl** — always use these). |
| `wanic_rc.py` | Bars (`parse_bar`, lap), detailing checks, `takeoff`, `grid_axes`, `axis_names`, grid mode `parse_spacings/grid_rooms/apply_grid`, `report_xlsx`. |
| `wanic_calc.py` | Structural calculation: `basis`, `PRESETS` (SDM/WSD), `LIVE_LOADS`, `fy_of`/`fs_of`, `solve_beam` (stiffness), slabs (ACI 318-63 Method 2), `pm_curve`/`pm_ratio`, roof ASD + wind, `analyse(data)` → members, beams, columns, `cards` (column load per floor), levels. |
| `wanic_calc_view.py` / `wanic_calc_book.py` | SFD/BMD/P-M drawing, PDF report; **A4 calculation booklet** `make_book` (`Book`, 404-mm layout units) that appends Truss, purlin, flat-slab, lateral and steel pages when `data` has those keys. |
| `wanic_truss.py` / `_view.py` | Trusses: Howe, Pratt, Fink, Warren, king-post, parallel, arch, custom; 2D stiffness solver; ASD pipe/box/lipped-C; base plate; heel welds. `data["truss"]`. |
| `wanic_steel.py` / `_view.py` | WF/H beams & columns (ASD), grouping, base plates. `data["steel"]`. |
| `wanic_purlin.py` / `_view.py` | Purlins, sag rods, tie rods (X-bracing), sheet-wall girts. `data["purlin"]`. |
| `wanic_flatslab.py` / `_view.py` | Flat slab + drop panel (DDM), punching. `data["flatslab"]`. |
| `wanic_lateral.py` / `_view.py` | Seismic (มยผ. 1301/1302-61 or old ZIKCSW) + wind (มยผ. 1311-50 or กฎกระทรวง 6), column P-M checks. `data["lateral"]`. |
| `wanic_private_est.py` / `_view.py` | Private estimate, 8 categories, editable waste/prices, overhead+VAT, xlsx. `data["private_est"]`. |
| `wanic_grid_view.py` | Grid-mode dialog. |
| `wanic_struct_sheets.py` | S sheets from the calculation: footing/column/slab details, typical beam, beam profiles per line (`beam_lines`, `beam_sheets`). |
| `wanic_steel_sheets.py` | Steel sheets: AWS weld standard (`min_fillet`), connections, plates, clip angles (`has_steel`). |
| `wanic_calc_cards.py` | Booklet cards: footing, slab, roof pages; `attach_lateral_moments` (Me row); `critical_members` (print only the critical ones). |
| `wanic_advice.py` / `wanic_fix_view.py` | Advice for failing members (what to add, where), `apply_fixes` (all marks, iterates until pass incl. detailing minimums), `member_fix` + `FixDialog` (one row), `balance_spec(keep_shape)` = symmetric/balanced edits (square columns, bars ÷ 4, equal top/bottom bar size, square footings), `fit_in_row` (clear spacing ≥ max(25 mm, bar)). |
| `wanic_stair.py` / `wanic_stair_view.py` | RC stairs straight / L / U: `designs(data)` (step checks กฎกระทรวง 55, waist slab one-way along the flight incl. landing, L/20, steel minimums, landing beam BS1), `suggest`, `apply_all`, `advice_for`; `StairDialog`. Geometry in `wanic_building.stair_layout/stair_plan/stair_members`. |
| `wanic_pile.py` / `wanic_pile_view.py` | Two pile types P1/P2 (`data["piles"]`, footing spec `pile`), capacity from given / static / dynamic test / Hiley / soil boring with FS, capped by 0.25 fc′ Ac; `cap_of`, `pile_text`; `PileDialog`; booklet `pile_page`. |
| `wanic_sanitary.py` | Users → septic tank / grease trap / screen pit (`users_of`, `septic_pick`, `grease_pick`, `design`, `design_lines`); used by the SN sheets (`sn_plan`, `sn_index`, `septic_table`, `sn_traps`) and the BOQ (`wanic_mep.bill`). |
| `wanic_beamload_view.py` | น้ำหนักเพิ่มบนคาน (`BeamLoadDialog`, presets: walls, water tanks, A/C, balcony), คานยื่น (`CantileverDialog`), `CheckloadDialog`; `beam_lines(data)`; row⇄dict helpers. |
| `wanic_road*.py`, `wanic_pavement.py`, `wanic_sitemap.py` | Road design, AI 1970 / Road Note 29 pavement, sheets G PP ST VT SD DR TS QS, site map. |
| `wanic_partprice.py` | Live part data/price as parts are stretched (`live_rows`, `refresh`, xform determinant). |
| `wanic_login.py` | Sign-in (identical copy in launcher/, cad/core/, 3d/core/ — a test keeps them equal). |

---

## 3. How to work

**Tests** (fast, headless): `cd 3d && QT_QPA_PLATFORM=offscreen python3 -m pytest -q -p no:cacheprovider tests/test_wanic_<x>.py`.
The full CI list: `grep -o "tests/test_[a-z_0-9]*\.py" .github/workflows/build-windows.yml` (≈275 tests, ~12 min).
Run the full list before dispatching an installer build.

**Screenshots** of the real GUI: `xvfb-run -a -s "-screen 0 1920x1080x24"` with `QT_QPA_PLATFORM=xcb LIBGL_ALWAYS_SOFTWARE=1`.
Pattern: `from views.main_window import MainWindow; w=MainWindow(defer_extensions=True); w.show(); w.load_extensions()`,
then drive `w._wanic_building` / `w._wanic_rc` / `w._wanic_road`; rooms need `id` (`dict(id="r1", name=…, x, y, w, d)`).
Modal dialogs: grab them from a `QTimer.singleShot` and `reject()`. Exit with `os._exit(0)` (teardown errors are noise).
Dialogs in `core/*_view.py` can be shown standalone with a plain `QApplication`.
Booklet PDFs → images: `pdftoppm -r 90 -png`.

**Installer**: `mcp__github__actions_run_trigger` `run_workflow` on `build-windows.yml`, ref = the branch,
inputs `{"version": "YYYY.MM.DD.N", "release": false}`. Before it: add the version entry to `WANIC-CHANGELOG.md`
and `installer/release-notes.md` (with signature). Artifact link for the owner:
`https://github.com/venidnid-creator/wanicn1/actions/runs/<run>/artifacts/<id>` (must be signed in to GitHub).
Schedule a check with `send_later` (~45 min) instead of polling.

**Commits**: clear English messages; `[skip ci]` while awaiting approval; push with retries
`git push -u origin claude/youthful-pascal-ctgtr0`. No model names in commits.

**Guides for the owner**: Thai PDF test guides are made from HTML with Chromium (Playwright `page.pdf`, font Loma/Garuda),
step-numbered, with the button names exactly as in the program, screenshots and a ✓/✗ results table at the end.

---

## 4. History — from the start to now

| Period / versions | What was built |
|---|---|
| 2026-10-28 (first commits) | Thai suite WANICNSURVEY from IngeCAD 0.6.7 + IngeTrazo 0.5.8; single-instance names; Inno Setup installer; CI. 2026.10.28.2 ถอดปริมาณ · .3 โปรไฟล์ · .4 ออกแบบอาคาร · .5 roofs follow the plan, doors/windows/stairs, ปร.1–ปร.4 (2569). |
| 2026.10.29 – .29.5 | Part library, BOQ 2569, new plan page; copyright in the owner's name; eaves, barge boards, real doors/windows, sanitary ware, room finishes; roof tiles and caps (Monier), roof frame on beams. |
| 2026.10.30 – .30.7 | Province selection and Ministry of Commerce (สนค.) material prices by province/month; market prices fallback; full 2D drawing export (A · S · SN · EE · M); ปร.4 appended to the drawing set. |
| 2026.10.31 – .31.9 | WANIC ออกแบบถนน: survey import, alignment, vertical curves, cross-sections, earthwork, Google Earth, province/district, pavement layers (ทช./ทล.), PI curves, A3 road sheets, site map, Thai DXF text, signature boxes. |
| 2026.11.03 – .04.6 | Building: Factor F (ว481), parts cut cleanly, valleys, roof caps, soffits, structure view, new start screen, ว480 labour list, layers, standard walls/roof frames, 15 BOQ categories, door/window positions, MEP (categories 11–15), sections, cover/contents, rebar details, transparency, download counters, version warning, bathrooms with standard plumbing, septic tank. |
| 2026.11.06.1 – .06.3 | Raised floor for pipes, pipe fittings, round septic tank, gutters/downpipes, automatic bathroom layout; pavement thickness design AI 1970 and Road Note 29 vs ทช. standards. |
| 2026.11.07.1 – .07.5 | Standard pavement sheets SD (ทถ-2-201/202/302/303); RN29 charts; sign-in before use; drainage DR (ทถ-5) and traffic signs TS (ทถ-3); cut/fill sections; road BOQ; superelevation and widening (ทถ-2-104); N E Z coordinates and satellite image in the model; Arabic digits everywhere. |
| ReadWanicn2027 → **2027.3.0** (released) | Sign-in, statistics, saraban document editor (6 groups), spreadsheet, PDF text/image editing, usage stats, snap, CAD import (.dxf/.dwg/.svg/images), printing. |
| **2026.11.11.1** | Start screen 2027 (5 themes, ไทย/EN, 4 cards, developer panel); RC structure design (8 steps: grid → footings/piles → stumps → ground beams → slabs → columns/beams → roof frame → rebar/BOQ); structural calculation (step 9: loads roof → piles, continuous beams, SFD/BMD, slab coefficients, P-M, wind uplift, PDF); symmetric gables, Thai roof, double gable, timber frame; fast selection; live part data. |
| **2026.11.12.1** (built for testing, not released) | A4 calculation booklet (cover, basis sheet, beam pages with diagrams/tables, column cards, summary, signature); Truss (matrix, 7 forms + custom, ASD, base plate, welds); steel H/WF; grid mode (+ open hall); purlins/sag rods/tie rods/sheet walls; flat slab + drop (DDM); lateral loads (current and old standards); private estimate 8 categories; SDM/WSD presets, live loads by use, fy from the basis, WSD fs ≤ 1,700. |

Test guides sent to the owner (Thai PDF): one for 2026.11.12.1 and seven by module (start screen, CAD, building, BOQ/export,
road, RC 2026.11.11.1, ReadWanicn2027).

---

## 5. Engineering conventions (keep consistent)

- Units: kg, m (cm for sections), ksc = kg/cm². Concrete 2,400 kg/m³.
- Basis defaults (`wanic_calc.DEFAULTS`): SDM วสท. 011008, U = 1.4D + 1.7L, φ 0.90 bending / 0.85 shear / 0.70 tied column;
  fc′ 240, SD40 (fy_db 4000), SR24 (fy_rb 2400), SS400 Fy 2450, LL floor 150 / roof 30, finish 50, wall 180, soil 10 t/m²,
  pile 8 t. WSD option = ข้อบัญญัติ กทม. 2522 (fc′ 173, SD30, fs = 0.5fy ≤ 1700, fc = 0.375fc′).
- Steel/timber roof and all structural steel: AISC ASD — tension 0.60Fy, Fa from KL/r vs Cc (KL/r ≤ 200 compression),
  Fb 0.66/0.60Fy with Lc, interaction with Cm 0.85, base plate bearing 0.35fc′, t = √(3fp m²/0.75Fy); deflection L/180 roof, L/360 beams.
- Slabs: ACI 318-63 Method 2 coefficients; flat slabs: DDM (Mo = wu l2 ln²/8, 0.65/0.35, end span 0.26/0.52/0.70,
  column strip 75/60/100 %), punching Vc = 1.06√fc′ b0 d (SDM).
- Wind on roof members: Cp 0.7 suction with ⅓ stress increase. Lateral: seismic off by default until Ss/S1 of the district
  are entered; strength combos 0.75(1.4D+1.7L+1.87E / 1.6W).
- Waste (private estimate defaults): RB 8 %, DB12–16 10 %, DB20 11 %, DB25+ 12 %, concrete 3 %, roofing 5 %, steel 5 %;
  overhead+profit 5 %, VAT 7 %.
- Beam solver (`solve_beam`): `Span(L, w, P=[(a, kg)], U=[(a, b, kg/m)], cant="L"|"R")`, factored loads; a cantilever
  hands its support a known moment and adds no support; `BeamResult.supports` = x of supports; two stations meet at each
  point load so the SFD steps. Diagrams: SFD + above, BMD on the tension side, dashed capacity lines (φMn top/bottom, φVn,
  dotted φVc), bottom ratio line.
- User data: `data["beam_loads"]` = [{level, axis x|y, line, a, b (a = b → point P kg, else w kg/m), type D|L, note}]
  (positions along the plan axis); `data["cantilevers"]` = [{level, x, y, dir ±x|±y, L, mark?}] → `B.elements` adds the
  beam with `"cant": True` (3D, drawings, BOQ follow). Beam level 0 = ground beams, n = roof ring beams.
- «รับเพิ่มได้อีก» (reserve, for laypeople): `Member.qty/qty_unit/qty_factor`, `reserve = qty(1/ratio − 1)/factor`,
  `reserve_text()` (> 5× → «รับเพิ่มได้อีกมาก»), `reserve_summary()` weakest per group; units: slab kg/m² live (÷1.7),
  beam kg/m, column / footing tonnes each, roof kg/m². Service values, no safety factor.
- Stairs: `st = {id, x, y (footprint centre), dir, type straight|L|U, turn left|right, w?, t?, bars?, temp?}`; risers split
  ⌈n/2⌉ + ⌊n/2⌋ with the landing at ⌈n/2⌉·R; settings `stair_t`, `riser_max`, `going`, `stair_bars`, `stair_temp`,
  `stair_ll` (300), `stair_beam`; analyse adds group "stair" and `res["stairs"]`.
- Drawings: never put characters outside cp874 (e.g. ✓) on a sheet — the DXF writes «?» and a test fails. Room tags
  `room_codes` = พ# ผ2|ผ3 ฝ#; interior elevations A B C D (`elev_marker` on plans, A-13 titles).
- Checkload (`wanic_calc.checkload`): per ground column Wcol (service t), tributary area over every carried floor + roof,
  Wfloor = Wcol/area, Wcol-Area = area × building mean; usual range `WFLOOR_RANGE` 450–1,600 kg/m²; flag > ±40 %.
- New design data lives in the building document: `data["calc"]`, `["grid"]`, `["truss"]`, `["steel"]`, `["purlin"]`,
  `["flatslab"]`, `["lateral"]`, `["private_est"]`, `["beam_loads"]`, `["cantilevers"]` — write through `bp._write(d)`, never directly to the scene.

---

## 6. Current state (2026-11-12, after the QuickDesign workflow study)

- Installer **2026.11.12.1** built (run 43147870896), not released; owner's test results for 2026.11.11.1 / .12.1 pending.
- Since then, on branch `claude/youthful-pascal-ctgtr0`, committed `[skip ci]` (no installer yet), each approved by
  screenshots: struct sheets, steel sheets, booklet cards, advice + per-member fix + symmetric/balanced edits, SFD/BMD with
  capacity lines, «รับเพิ่มได้อีก» reserve, plan item 4 (beam loads, cantilevers, Checkload — approved) and plan item 5
  (RC stairs — approved) and plan item 6 (A/SN/EE — approved) and plan item 7 (two pile sizes, capacity from tests — awaiting approval).
- The QD study plan (approved): 1 struct sheets ✓ · 2 steel sheets ✓ · 3 booklet cards ✓ · 4 beam point/uniform loads,
  cantilever, Checkload (Wcol / Wcol-Area / Wfloor) ✓ · 5 RC stair (straight / L / two-flight) ✓ ·
  6 ✓ A-01 symbols + finish codes, room tags, ABCD markers, door/window schedule, grease trap / screen pit, septic tank by
  users, EE/SN specifications · 7 ✓ awaiting approval: two pile sizes, pile capacity from test results · 8 free drafting (columns/beams from
  sketch lines, curved/inclined beams, curved walls). QD is studied for workflow only — never copy its code/UI/files.
- Next installer only when the owner asks; it will contain all of the above.

## 7. Future development (agreed or proposed — confirm with the owner before starting)

1. Fix whatever the owner finds in the 2026.11.12.1 / 2026.11.11.1 tests; then release on order.
1b. Continue the QD plan items 5 → 8 (see §6) one by one: build → test → screenshot → approval.
2. Ss/S1 table by district (มยผ. 1301/1302-61) and the Bangkok-basin spectrum — needs the owner's copy of the table.
3. Storey drift check and a frame (stiffness) analysis for lateral loads instead of equal column shares.
4. Remove double counting when a Truss replaces rafters in the BOQ; draw Truss/steel/purlins as 3D parts in the model.
5. Free-drawn and curved roofs, metal-sheet walls in the model (plan item E from the study).
6. Post-tensioned slabs; rebar shown in the 3D model; default GB1 3-DB12.
7. The five start-screen themes inside the 2D/3D program windows.
8. DXF structural sheets (S-xx) generated from the RC/steel/truss designs.
9. Keep ReadWanicn2027 in step (licence renewal codes via `tools/`, releases tagged `readwanicn-v…`).

When the owner gives a new request: restate it in Thai, propose a plan if it is large, build → test → screenshot →
approval → installer → release on order, recording each step in `docs/WANIC-HANDOFF.md`.
