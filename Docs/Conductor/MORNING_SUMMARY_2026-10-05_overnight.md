# Overnight 5 Oct, ~01:00–03:00 local (Conductor 4, Gary's bedtime approvals)

Read this first. Each item says how it was checked. "Both tests" means SavedMasterMatchesShow and
SceneCutBindingsResolve, run singly in the live editor, both green; census clean after every write.

## Applied to the show
- **Build PM + F2** (430f038): portal timber slots (`PortalMesh`/`PortalMaterial`, null = gridiron's) and the
  SavedFixturePIE fix for the Interaction 1 sleight. Full suite 145/2 [measured]; both reds were fixture faults in the
  new portal tests (the engine cube/sphere's own materials ARE WorldGrid/Default here), fixed and Structure 13/0
  [measured]. SavedFixturePIE is GREEN again.
- **Dark wet floor** (3088cd1, run 20261005-015555): P01, P03, P05, P06 slabs raised to top +0.5 (5.5 cm), new P04 slab
  lip→hinge (x −150..11168.5, four hinge sources agree), `MI_Floor_DarkWet` created; P02 untouched. Backup
  Backups/PreFloorDarkWet-20261005-015555. [measured: tool read-back, census, both tests]
  - Acknowledged: pond lily `SM_lily_01_1` now 6 of 30 cm under the floor (siblings at −11.5 and +5.5).
  - **For Gary:** pit strips beside the P01/P03/P05/P06 hangar pits stay at −5, a 5.5 cm step at each hinge. The wet look
    and its Lumen cost are unreviewed.
- **Underpass rig on P05** (6d70b04): 7 kit meshes imported, M_UP_PaintedSteel / M_UP_GrimyConcrete + 3 MIs (no compile
  errors), Phase A on Structure 05; portal pinned to what it rendered (engine cube + WorldGrid, i.e. the P05 portal
  was never real timber). Hanging lines 2 → 154, inside the predicted range. Backup
  Backups/PreUnderpassP05-20261005-0223. [measured] **No stills yet** — a stills tool is being written.
- **Lighting scores P01, P02, P03, P04, P06 applied** (5a32710; P05 was already in). Each DRY → APPLY → both tests.
  | passage | bays scored | lights + props placed | old lights disabled | shadow casters |
  |---|---|---|---|---|
  | P01 | 48 | 283 + 95 | 522 | 99 → 83 |
  | P02 | 23 | 133 + 46 | 115 | 70 → 37 |
  | P03 | 21 | 127 + 42 | 228 | 54 → 49 |
  | P04 | 15 (bays 1–6 keep the looks) | 74 + 29 | 135 | 43 → 33 |
  | P06 | 55 of 64 (bays 2–10 black mode) | 227 + 103 | 495 | 117 → 79 |
  - P06 was rescored 55 → 64 (W&T interleave): same shape as the harness's designed rescore — grand 1–12, failing
    13–63, void 64. Harness 68/68 [measured].
  - **For Gary:** the void bay (P06 Wing 055, bay 64) carries "FX TEST - S6 Candle Light". The score would have
    snuffed it; it is RETAINED as found until you say. (You said P06 ends in darkness with the curtain already burning.)
  - Overlapping records acknowledged after review: blink spots (kept), the previous passage's score record (only its
    restored scratch cue), slow-walk records (protect timing/meshes, not lights), a W&T fence fixture.

## Look bench (P04)
- Contact sheet sent to Gary (bays 4 and 9). Bay 9 glint on Coventry Wing 009 R reads strongly (silver paper).
- Bay 4 gates FAILED [measured]: P04's tune-4 beams use intermittent flicker light functions (Slow, Fault), so luma
  swings ~20–55 regardless of toggles. Sheet shows each clip's brightest frame. Bay 4 toggles change little from
  ~1.2 m before the bay; underpass/arch rings only appear as far grey blocks.
- **Shadow cost: NOT measured** — the bench records no frame times. Needs a timing run.
- Bench restored, PIE ended, Don't-Save restart, census clean.

## Fuser (for Gary to paste)
- 8-per-paste blocks (`~~`): BATCH8_no_reference_blocks.txt (16 no-image prompts), BATCH8_series_2026-10-05.txt
  (jobs 49–56), BATCH8_series_more_2026-10-05.txt (57–71), BATCH8_series_gobos_2026-10-05.txt (72–77).
  All in DerivedAssets/FlatV3/FuserQueue/. A check refuses "curtain"/"gobo"/"slide" in any prompt.

## Other streams
- W&T cv12 gallery swap: given a slot; its DRY refused (TK_DEPTH_ENVELOPE_GREW, +0.08 cm vs 0.01 allowed on one
  right-hand piece). Nothing written. W&T diagnosing offline.

## Still to do
1. P05 underpass stills (tool being written), then stills of P01–P04/P06 under their new scores.
2. P04 shadow-cost timing run.
3. Gary: underpass look on P05 before other passages; candle in P06's void; pit-strip steps; lighting score verdicts.
