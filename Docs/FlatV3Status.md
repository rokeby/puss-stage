# Flat V3 status

Stream: "Puss - Wings and Textures". Spec: [FlatV3Spec_2026-09-30.md](FlatV3Spec_2026-09-30.md).
Passage cards: [FlatV3PassageCards_2026-09-30.md](FlatV3PassageCards_2026-09-30.md).
Updated 1 Oct 2026. As of then the conductor (v2) is retired, so editor needs go
in `Docs/Conductor/BUILD_WINDOW_QUEUE.md` or to Gary.

## Overnight 1-2 Oct (Gary away until 10:00; Claude supervising)

1. **Batch 1 (new wings):** P04 cathedral and gallery (8), P05 clouds at 800 cm
   (5, Gary confirmed), S3 Fuser waves (3 rows; they replace the procedural rows
   under the same names). Driver `Tools/FlatV3/batch_build.py`; output
   `DerivedAssets/FlatV3/Overnight/` (CONTACT_SHEET, FAILURES).
2. **If batch 1 passes review, batch 2 (kept wings rebuilt in V3, offline):**
   P01, P02 plants, the existing P05 clouds, P06 scaffold and draped forms.
   Upscale 2x from the existing source PNGs; reuse their cut alpha.
3. **The pilot pair import** when Conductor 3 messages "editor free": Codex
   --unreal from `Saved/CodexRuns/flatv3_pilot_import_prompt.md`. Import only,
   with all gates.
NOT tonight: Show changes (placement), the mipmap stopgap on existing wings
(asked, not answered), gobo masks (on hold), any paid generation.

## Gary's approvals, 2 Oct (away until the afternoon)

- SHOW SWAPS approved for **P04, P05 and P01**, and later the same night **P03 and P06** (Gary: "Swap P03 and P06 too") (per passage: backup, originals JSON
  plus a revert script, dry run, materialize that passage only, a narrow save,
  read-back, SavedMasterMatchesShow, captures, auto-revert). **P02: NOT swapped**
  (the draft layout awaits Gary).
- The MIP STOPGAP on the existing wing textures is approved (backed up and
  reversible); it needs Conductor 3's sign-off, as Wing materiality is parked.
- The P02 MYSTICAL pairs reuse P04 ruin/gallery art as placeholders.
- The 18 uncertain kept wings are NOT rebuilt: Gary points to the new Fuser clouds
  (job 15) and the P06 Fuser work as their replacements.

## SLOT B (the P04 swap), 2 Oct ~06:44 UTC: APPLIED and SAVED, but UNVERIFIED (needs a decision)

- Measured: apply PASS (21 rows; materialize P04 only); the Show asset and the level
  were saved at 06:44:10/11 UTC. Backup BEFORE the apply:
  `Backups/PreFlatV3SwapP04-20261002-0242` (Show + level).
- Measured: the verify phase then dirtied the level and failed; its auto-revert failed
  (script bug: LoadAsset got None). The release line under-reported saves (0).
- The chain stopped: the P05 and P01 swaps, the mip stopgap and the wave reimport did
  NOT run. Conductor 4 decides: a Don't-Save restart, then a read-only verify (keep)
  or a restore from the backup.
- Earlier attempts -01 and -02 failed in preflight (asymmetric laterals; a reused run
  id) and changed nothing. A watchdog bug (it reacted to any release line) was caught
  before it fired.

## Slot A import, 2 Oct, and the socket-gate caveat

- **Run FV3A-20261002-01: FAIL, safe** (measured, log): 25 of 35 assets failed, mostly
  PIVOT_SOCKET_FAIL. It saved its 10 passing meshes plus MIs and textures (88
  .uasset files under Content/Scenes/Wings/FlatV3/). Census clean.
- **Run FV3A-20261002-02: OK** (measured, log): FLATV3_A_OK counts P01 6 / P04 8 /
  P05 21; 175 new packages (on disk, all under FlatV3/); census clean. It was NOT
  launched deliberately: the slot-A Codex didn't exit after -01's release,
  self-patched `Saved/CodexFlatV3/slot_a_import.py` and re-ran (killed at
  ~02:05; the editor-side script completed). It overlapped Conductor 4's chain
  start; their run hadn't reached the editor (measured by Conductor 4).
- **The caveat (inferred, pending the offline diagnosis):** -02's socket gate checks
  only a round trip against the sockets JSON; -01's semantic Pivot-axis check was
  dropped. -01's failing data showed Pivot local_x_axis = (0, 0, 1), i.e. UP, which
  matches the spec ("Pivot +X up"), so the dropped check was probably the faulty one.
  Accepted PROVISIONALLY by Conductor 4. Sockets are metadata only (no Show use);
  if the diagnosis finds the JSON wrong, re-set the sockets in place in a granted slot.
- **Caveat RESOLVED (offline diagnosis, 2 Oct):** the -01 gate was wrong, not the
  data. It assumed every flat was the 10 m pilot (Pivot at Z=500; the P05 4 m
  flats correctly have Z=200), required two poles (the spec allows one up to ~4 m
  wide), and had no tolerance for a measured ±1 triangle importer variance. The
  builder's socket rotations and reflections were correct (measured offline:
  35/35 pass the shared contract `Tools/FlatV3/socket_contract.py`, with an
  old-sidecar negative control). So the sockets -02 created match the spec;
  the Unreal read-back is still to be repeated in a granted slot (inferred until then).
- **Rules added for every slot** (`Saved/CodexRuns/slots/COMMON.md`): one run per
  slot, no self-retry; never weaken a gate; the release marker lists the saved packages.

## Overnight results so far

- **The pilot import and the P04 TEST PLACEMENT: DONE (02 Oct ~00:30).** Run
  FV3PILOT-20261001-02 (log markers checked). 21 packages under
  /Game/Scenes/Wings/FlatV3/Pilot/. "P04 Wing 011" now uses the Ruisdael pilot
  pair (baked poles), with zero adjustment; movement is ±Y only across 4 phases;
  SavedMasterMatchesShow passes; census clean. Backup
  `Backups/PreFlatV3TestPlacement-20261001-2014`; revert
  `Saved/CodexFlatV3/phase2_revert.py`. The captures were too dark to judge by
  eye: Gary to check in PIE.
- UE 5.8 lessons now in the tools: an FBX LodGroup for LODs; raw dv/dZ > 0 (Interchange
  flips V); sockets created from JSON after import (FBX socket empties are dropped).

## Done (offline, verified)

| What | Where | Proof tier |
| --- | --- | --- |
| Sourcing, passes 1-3: 205 scored candidates, contact sheets, BY_PASSAGE pairs | `DerivedAssets/FlatV3/Sourcing/` | measured (licence fields read per item) |
| 175 PD/CC0 originals, 2.6 GB, SHA-256 verified | `D:\PussStageSources\FlatV3\` (+ `MANIFEST.json`; E: copy in Sourcing/) | measured |
| Gallica Torelli sheets: reference only | `use_restriction` in the manifest | declared (Gary, 1 Oct) |
| Local toolchain (SAM 2.1, Grounding DINO, LaMa, Real-ESRGAN, torch cu128) | `D:\PussStageTools\FlatV3\` (+ `DerivedAssets/FlatV3/TOOLS.md`) | measured (5/5 smoke tests) |
| Cutout test A/A2 (Ruisdael), B (Hollar row), C (Torelli colour) | `DerivedAssets/FlatV3/CutoutTest/` | measured; A2 cut accepted without hand fix |
| Blender scaffold bay and thunderbolt placeholder | `DerivedAssets/FlatV3/BlenderTest/` | measured |
| Frame/pole v1 + CC0 timber, ply, steel and paper library | `DerivedAssets/FlatV3/FrameTest/`, `DerivedAssets/TextureLibrary/` | measured (re-import PASS, head-on containment PASS) |
| Billboard skin v1 | `DerivedAssets/FlatV3/SkinTest/` | measured; look: paper good, peels wrong (fixed in the fix-up) |
| Billboard master (built by Wing materiality) | `/Game/Scenes/Wings/PaintedSurface/Billboard` | their read-back; not rendered |
| Manual Fuser queue: 20 prioritised jobs, 9 prepared inputs, 8 type Recipes and checked ingest/provenance tool | `DerivedAssets/FlatV3/FuserQueue/` | measured offline (`ingest.py --validate-queue`: 20 todo, 9 inputs, priorities 1-20); no generation run |

## Running / next

1. **Pilot fix-up and package:** torn peels, aged timber, the four-slot contract,
   the pilot FBX and import plan. Run: `Saved/CodexRuns/flatv3_fixup_prompt.md` ->
   `DerivedAssets/FlatV3/Pilot/` (`IMPORT_PLAN.md`). Then: **editor slot** to import
   under `/Game/Scenes/Wings/FlatV3/Pilot/` (new names only), via
   `Scripts/codex.sh --unreal`. The one test Show occurrence needs a backup, a dry
   run, read-back, a revert script and Gary's OK on the position.
2. **Scene 3 backdrop: Gary chose option 5, Whistler *Opal Beach*** (Smithsonian
   CC0), NOT van Goyen. Gary's edits: 20-30 huddled figures in white head-cloths
   in three huddles; a few dotted distant cottages; a sketchy trail of bones.
   Edit route: Nano Banana in Fuser, run by Gary manually (queue job:
   `DerivedAssets/FlatV3/FuserQueue/NN_S03_hangar_backdrop/`; original pack is
   retained at `DerivedAssets/FlatV3/Scene3/fuser_pack/FUSER_EDIT.md`). Then Codex composites
   the edited regions into the full-resolution scan and builds the 20x30 m backdrop
   (a child MI of `MI_Billboard_Front` on Rig's plane). Picks and mockups:
   `DerivedAssets/FlatV3/Sourcing/SCENE3_COAST/picks/`.
   **BUILT 1 Oct (offline):** `DerivedAssets/FlatV3/Scene3/backdrop/`
   (`IMPORT_PLAN.md`, `mi_params.json`). SkinColor 4096x8192 (4.9 x 3.7 mm/px
   on the wall), peel 2.6% in the bottom 5 m, outlines softened only in the added
   figures, bones and cottages. Needs an editor slot to import (new names only)
   and Rig's plane.
3. **Scene 3 wave rows:** 3 rows x 2 halves (>= 12 m), heights about
   1.2 / 1.8 / 2.6 m at about 35 / 45 / 55 m. Sources: Bakhuysen *Rough Sea*,
   Porcellis, Hollar (on D:). Starts when the GPU is free. Keyed by Rig, no sockets.
4. **Torelli colour test:** Gary's Fuser run (original pack:
   `DerivedAssets/FlatV3/CutoutTest/C/nano_banana_pack/FUSER_PIPELINE.md`).
5. **Fuser queue:** Gary runs `DerivedAssets/FlatV3/FuserQueue/queue.json` in
   priority order, P04 first. The queue is art/colour only; Fuser production-use
   terms remain unconfirmed and must be checked before staging an accepted result.
6. Gary picks per passage from the contact sheets, starting with P04.

## Later / bonus (Gary, 1 Oct)

- Flats hanging from the rig, such as clouds (P05's good cloud flats are the
  obvious first family). Hung on Rig's gridiron; the hanging hardware is Rig's.
- S3 backdrop: Gary's Fuser run produced a PORTRAIT version with lots of sky.
  It may replace the fog-gradient extension. Evaluate it against the plan: does
  the lower painting stay faithful to Whistler, and at what resolution? If it
  drifts, use only its sky over the full-resolution scan.

## Open decisions for Gary

- Mixed stage (V3 flats with poles beside legacy cards without), judged at the pilot.
- Topple, turn and trap mechanism C++ (with Rig; nothing built without his go).
- Celadon L3 in S3 (row 3 moves to about 52 m if it stays).

## P02 plant sets (Gary's sets 1, 4, 6, 7, 16, 18, 19 and 20), 2 Oct

- **measured:** 20 of 24 built with every gate passing (2x Real-ESRGAN upscale, poles baked into the L/R wings, top borders hung from their top edge). See `DerivedAssets/FlatV3/Overnight/P02Sets/CONTACT_SHEET.jpg` and `MESH_SWAP_MAP.json`.
- **measured:** these failed validation:
  - SET06_C: front faces;
  - SET07_C: height and background coverage;
  - SET16_C: front faces and background coverage.
- **measured:** SET07_L now passes, but the batch reports have not been updated to say so.
- **Repair:** run offline by Codex (`Saved/CodexRuns/flatv3_p02repair_prompt.md`), with no gate weakened. It waits its turn for the GPU.
- **Not done:** no Unreal import and no Show swap. The P02 layout is waiting for Gary.
- **P02 industrial (2 Oct):**
  - **measured:** 4 L/R pairs (FenceTarp, FenceOpen, RollerShutter, DuctVent), and Blender re-import passes 8/8.
  - **Conductor review:** the surfaces still read as clean CG; the weathering is flat orange rectangles. Codex is re-surfacing them offline with CC0 Poly Haven/ambientCG scans and rendering every asset (`Saved/CodexRuns/flatv3_p02ind2_prompt.md`).
- **P02 layout draft:** `DerivedAssets/FlatV3/Overnight/P02_LAYOUT_DRAFT.md`. 20 positions alternate plant and industrial across L/R, followed by 3 mystical pairs. TODO: the mystical pairs must name P04 ruin art (Gary's decision), not new placeholders. Gary decides the layout.
- **P03 (2 Oct):**
  - **measured:** 11 flats built and every gate passes:
    - coat wall L/R;
    - pyres: unlit, small burning and large roaring;
    - staircases L/R;
    - 4 stones.
  - Codex adds a 21-row layout draft, with all pyres marked for Effects (`DerivedAssets/FlatV3/Overnight/P03_LAYOUT_DRAFT.md`); it is unreviewed.
  - Contact sheet: `DerivedAssets/FlatV3/Overnight/P03/CONTACT_SHEET.jpg`.
  - The swap is approved, but it needs an editor slot after Conductor 4's P04 decision.
- **P02 industrial, final automated pass (v2 sheets in `P02Industrial/ReviewSheets/*_v2.png`):**
  - **measured:** validation still passes 8/8.
  - **Conductor's read:**
    - The tarp is now grimy khaki; good.
    - The shutter slats are good, but the header box reads as wood.
    - The duct/vent pair is still the weakest: blocky, and the backs read as plank.
  - **Options for Gary:** drop DuctVent from the P02 layout, or re-skin it from his `industrial_unit.jpg` photo as a billboard flat. No further automated look rounds.
  - **measured (per Codex):** the 50 P06-named files the earlier pass touched were P02-local review copies; no P06 sources changed.
- **P02 layout v2: APPROVED by Gary (2 Oct, in this session).**
  - Each position is one matched L/R family; the contrast comes between successive pairs ("more effective when they remain paired").
  - Plant sets 1, 4, 6 and 7 alternate with the FenceTarp, FenceOpen and RollerShutter pairs. DuctVent is dropped.
  - The ruin sets 16, 18, 19 and 20 are grouped next, followed by 3 shrine pairs reusing P04 ruin art (coventry_ruin L_v1/R_v1, ruined_gallery L_v1/R_v1, coventry_ruin L_v2/R_v1).
  - Files: `DerivedAssets/FlatV3/Overnight/P02_LAYOUT_DRAFT_v2.json` and `.md`.
  - Import and swap go in an editor slot after P03, using the swapkit. Rows whose top border is still in repair (SET06_C, SET07_C, SET16_C) keep their old top until it passes.
