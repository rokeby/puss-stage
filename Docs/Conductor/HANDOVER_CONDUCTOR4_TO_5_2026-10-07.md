# Handover: Conductor 4 → Conductor 5 (7 Oct 2026, ~16:00 UTC)

Read first: `AGENTS.md`, `README.md`, this file, then `Docs/Conductor/MORNING_SUMMARY_2026-10-07_overnight.md`
(full overnight log with run ids). Memory index (`MEMORY.md`) carries the standing rules.

## How the conductor works (unchanged rules)
- Gary decides look/creative; conductor may approve reversible, backed-up, non-creative writes. Only Gary's own words
  in *this* session (or recorded as his own answer in a peer's session for that peer's own writes) count. On mobile he
  wants AskUserQuestion, batched, recommendation first.
- Claude writes code (subagents, offline, harness with +/- controls); the conductor runs editor steps itself.
- Every editor write: DRY → APPLY (backup, record first, narrow save, read-back, success marker) → both tests singly
  (SavedMasterMatchesShow, SceneCutBindingsResolve) → stills when visual → commit by explicit path (never `-a`).
- A failed step = stop; if anything is dirty in memory → Don't-Save restart (kill UnrealEditor, rename
  `Saved/Autosaves/PackageRestoreData.json` to `.declined-<ts>`, relaunch, poll census).
- Editor slots are exclusive: W&T ("Puss - Wings and Textures", cross-session) asks for slots; grant with census
  state + what changed since their last slot; they report "slot back" with run ids + tests.

## Helpers (now in the repo)
`Saved/CodexConductor/conductor_helpers/`:
- `mcprun.sh <request under Saved/CodexConductor> <stop-regex> [show-regex] [n]` — purges the Python module cache,
  calls MCP, waits on UTC-timestamp-filtered log lines.
- `stills.sh <Pxx> "<fractions-json>" <label>` — own PIE + passage stills (Scenes: write `scene_stills_args.json`
  with `"passage": "S<n>"` and call `scene_stills_request.json` between `conductor_pie_begin/end`).
- `tests2.sh` — census + both tests (prints can mis-pair; prefer waiting on each test *by name*, see recent commands).
- Census: `census_print_request.json` (CENSUS_PRINT line).

## State at handover (all committed; last conductor commit 83325f6)
Applied today (details + run ids in the morning summary): P06 sunset; S1 reveal v3 (roof now KEPT); S6 Void in main
level (hangar hidden, bee glimmer); P04 window+strobe shadows; Puss shadow spot ×8; P05 eye 90 cm; velvet V2G; P02
straightened + retimed 47.52 s + second half lit (strike 2500/HOLD); beams P01/P04/P06; smoke pots ×9 (re-placed
after W&T P03 swaps); dead bulbs warm ×77; girders v3 double section (all six); Meshy bulbs 3.2× real (~35 cm) +
one lantern per passage; P06 bee glints (Choreo sub-track — **tell the cueing stream**); end drapes P01/02/03/05 +
pictures; S4: hangar resized in place + Klara reveal her_dark_pan (S4 195.6 s); **hangar hold** S1/S2/S3/S4 (rises
ended at the old 31 s scene length → hangar dropped to REST, open sky); Structures 02/03/06 re-materialized.
W&T today: P06 relayout 64→29 + 12-flap swap + domino slam 37 s; P02/P03 realism swaps; flutter/LOD; imports.

## Open / next (priority order)
1. **S3 looks washed out (near white)** in the held-hangar stills (PassageStills/PSTILLS-S3-*-held). Gary asked
   nothing yet; ask: investigate now or after his PIE. Suspects: S3 daylight setup now enclosed / exposure.
2. **S4 glide not fully dark**: children + pigeon visible near the camera during our glide (her set at start pose).
   Offer Gary: keep her set hidden/unlit until the hand-over.
3. **S2**: Gary thinks her S2 shouldn't be a 5 s LS — offer an offline scan of her S2 package for a longer sequence.
4. **Morning build (held patches, editor closed)**: W&T mechanism sound a7c89c5 (no Passage sounds — verified
   TOPPLE-20261007-022206) + fence top-row wire/posts `Scripts/patches/2026-10-07_fence_top_row_wire_and_posts.patch`.
   After build: `BarbedWire_20261007/barbed_import.py` set "nw" (no-wire bays) → `barbed_apply.py` DRY/APPLY
   (wire on the TOP row only; lower rows plain — Gary). Check DLL markers; warnings baseline 29.
5. **P01 note lamps**: APPLY failed EXPORT_OUTSIDE_SCOPE_CHANGED (rolled back); tool now logs
   P01NOTELAMPS_EXPORT_DIFF — re-run DRY then APPLY and read the diff.
6. **TOP lamps inside the deeper girder band** — need a rig_lamp_drop copy for 180-deep beams with slight negative
   clearance ("lamps sit on the rig").
7. P04 rain placement (Rain2 renders, P04RAINPIE-20261007-063520) — needs Gary's placement call.
8. Curtain unfurl: W&T production bake (B1 bunched, tiny bounce) ~6 h offline; import after Gary sees it.
9. Klara-level dirty flag: L_KK_children / L_Animals got marked dirty twice during W&T runs; materialize/evaluate
   proven NOT to cause it (probe_klara_dirty.py, 333 actors unchanged). Rule given to W&T: if only Klara levels are
   extra-dirty and her actors' snapshot diff is empty, save Show+main only, never her levels, then Don't-Save restart.
10. Smoke pots still carry the greybox Apparatus cube; P03 still milky (no fog tool yet); P05 not supported by the
   atmos core.

## Traps learned today (also in memory)
- Hangar rises are bounded by the Scene length at build time; relengthening a Scene needs a hold
  (`s4_hangar_hold.py`, scene arg 1–4) or the hangar sinks back to REST.
- Klara streamed actors sit on routes: route scans must use the persistent level only (`_persistent_actors()`).
- Python API: SkeletalMeshComponent has no `.bounds` (use SystemLibrary.get_component_bounds); spawnable templates need
  `camera_component` (get_cine_camera_component() is None); get_possessables() lists removed bindings as invalid
  proxies; LevelSequence path padding `LS_DevScene_%02d`; `--` default encoding gbk: always `encoding="utf-8"`.
