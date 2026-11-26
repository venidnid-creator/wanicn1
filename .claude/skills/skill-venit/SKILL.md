---
name: skill-venit
description: Everything needed to continue work on WANICNSURVEY (cad/ 3d/ launcher/) and ReadWanicn2027 (readwanicn2027/) for Mr. Venit Thammawong (survey engineer) — the owner's rules and decisions, the repository and module map, how to test/screenshot/build installers without publishing, the full history from the first commit (28 Oct 2026) to now, the engineering conventions (calc book = drawings = BOQ = cutting list, recalculate on every model change, glossary on every sheet), and the open roadmap. Use it at the start of any task in this repository, before changing code, building an installer or answering the owner.
---

# Skill Venit — WANICNSURVEY & ReadWanicn2027

Owner and certifying developer: **นายเวนิช ธัมมะวงษ์ (Venit Thammawong), วิศวกรสำรวจ (survey engineer)**.
Repository `venidnid-creator/wanicn1`, working branch `claude/youthful-pascal-ctgtr0`.
Live Thai log: `docs/WANIC-HANDOFF.md` — read it first, update it after every step.

Reference files (read the one you need):
- `references/history.md` — every version and work group from 28 Oct 2026 to now, installers built.
- `references/modules.md` — repository map and every `wanic_*` module.
- `references/conventions.md` — engineering/drawing conventions and the single-source rules.
- `references/workflows.md` — tests, screenshots, installer build, git, environment gotchas.
- `references/owner-decisions.md` — the owner's decisions (do not ask them again).

---

## 1. The owner's rules (always)

1. **Reply in Thai.** Programs, sheets, reports are Thai; no brand names (Word/Excel) in the UI.
2. **Screenshots before any installer**: build → test → screenshot → `SendUserFile` → wait for «อนุมัติ».
   Commit unapproved work with `[skip ci]`.
3. **Never publish a Release** unless the owner says «อนุมัติเผยแพร่». Installers for testing use `release=false`.
4. **Record everything**: update `docs/WANIC-HANDOFF.md` and this skill; commit and push after each piece.
5. **Ask when unsure** (`AskUserQuestion`, recommended option first); «ตามที่แนะนำ / อนุมัติ» means proceed.
6. **Signature** «นายเวนิช ธัมมะวงษ์ · วิศวกรสำรวจ» on every report, booklet, BOQ and changelog entry.
7. **Copyright**: commercial programs (QuickDesign …) and Thai-Pave/Thai-Slope are studied for the workflow only —
   never copy code, UI, names or files; never upload them to this public repo.
8. **Privacy**: no credentials, licence keys (`READWANICN_LICENSE_KEY`), e-mail or private data in code, commits,
   prompts to outside services or messages. No model names in commits/artifacts.
9. Developer panel on the start screen is mandatory (photo, QR LINE, 093-5838348, Krungsri 666-1-32472-1, free use).
10. Engineering output states it is a tool: a licensed civil engineer must check and sign before construction.

## 2. The single-source rules (owner, 25 Nov — details in `references/conventions.md`)

- **Calc book = drawings (PDF and DXF) = BOQ = cutting list.** Spacings via `wanic_rc.spacing`, beam end stirrups via
  `end_stirrups`, bar counts only via `stirrup_count` / `mesh_count`; beams carry every bar the whole span; footing
  bars as drawn (`nbar` ≥ `need` or fail).
- **A changed model is calculated again, every item** (`B.struct_stamp`, `B.recalc_all`, orange banner, exports
  recalculate first).
- **Every sheet explains its technical terms** (`wanic_glossary`), **no text over text**, permission text on every road
  sheet, characters outside cp874 mapped in `D._DXF_SUB`.

## 3. Where things are (short — full map in `references/modules.md`)

`launcher/` start screen (7 languages, update window, licence) · `cad/` 2D (IngeCAD fork: PDF import, paper blocks,
«เวนิช» font) · `3d/` 3D (IngeTrazo fork): plugins `wanic_building`, `wanic_rc`, `wanic_road`, `wanic_takeoff`,
`wanic_profiles`; engineering in `3d/core/wanic_*.py` · `readwanicn2027/` PDF program · `installer/`,
`.github/workflows/build-windows.yml`. `3d/core/road/*.py` must stay byte-for-byte the CAD's.

## 4. How to start a task

1. Read `docs/WANIC-HANDOFF.md` (end of file = latest) and this skill.
2. Restate the request in Thai; for a big one propose a plan (lettered items) and wait for approval.
3. Find the code (`references/modules.md`), change it, add/extend tests, run them in small sets
   (`references/workflows.md`).
4. Screenshot, send, ask for «อนุมัติ»; commit `[skip ci]`, push; log in the handoff.
5. Installer only when ordered or after approval of a batch — `release=false`, check with `send_later`.

## 5. Current state (26 Nov 2026)

- Installer **2026.11.25.1** built (run 45629906678, artifact `wanicnsurvey-setup-2026.11.25.1` id 15032262767,
  expires 2027-02-23), **not published** — waiting for the owner's test and «อนุมัติเผยแพร่».
- All approved plan groups are done: ข (structure/calculation), ค (model/menus), ง (BOQ/prices), จ (roads 30–39),
  ฉ (7 languages, PDF import, A0–A4 paper blocks with «เวนิช»), plus the consistency rules and the update window.
- Not done / limits (told to the owner): live LandsMaps lookup (parcel files instead); 2D program catalogs only for Lao
  among the new languages; PDF fills come in as outlines (no hatch); Thai-Slope not ordered; combined footings have
  no hand-calculation comparison yet; translations of the 5 new languages not reviewed by native speakers.
- Open question: block exports while items fail? (now warn only; the calc book is blocked).

## 6. Roadmap (confirm with the owner before starting)

1. Owner's test results of 2026.11.25.1 → fixes → publish on order (`release=true`).
2. Thai-Slope (slope stability: Ordinary, Bishop, Janbu) if ordered.
3. PDF import: fills as hatches; 2D catalogs for vi / id / zh-CN / zh-TW.
4. Hand-calculation comparison for combined footings; Ss/S1 table by district; post-tensioned slabs.
5. Truss/steel/purlins as 3D parts; rebar in the 3D model; themes inside the 2D/3D windows.
6. Keep ReadWanicn2027 in step (branch `claude/zen-feynman-ptcfng`, tags `readwanicn-v…`).

When the owner gives a new request: restate it in Thai, plan if large, build → test → screenshot → approval →
installer (not published) → publish on order, recording each step in `docs/WANIC-HANDOFF.md` and this skill.
