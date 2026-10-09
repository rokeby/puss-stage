# P102: execute the 9 Oct evening live queue (Codex --unreal, LIVE)

Read these first, in full:
- `Docs/Conductor/codex_briefs/p49_postbake_editor_runner.md`: its **HARD RULES apply verbatim**.
- `_house_rules.md`.
- `Docs/Conductor/GARY_PIE_NOTES_2026-10-09_evening.md` (E1–E25).
- Each job's own README or REPORT.

Transport: `Saved/CodexConductor/conductor_helpers/mcprun.sh <request.json> "<OK|FAIL regex>" "<prefix>" 1`.

Rules that matter most tonight:
- Gary is NOT in PIE. Do not start PIE except where a tool requires it, and then end only the PIE you started.
- Never Save All. Never save Klara's levels.
- Visibility tracks bind bHidden.
- DRY, then APPLY, then read-back, then a clean dirty census, then the next item.
- On any FAILED, STOPPED or unexpected census, STOP and report. Never retry a mutation blind.
- Purge the stale module cache before each tool: `Saved/CodexConductor/conductor_helpers/purge_saved_module_cache.py`.
- Known 5.8 traps:
  - `str(enum)` and `str(FGuid)` must be normalised.
  - Channel names carry suffixes.
  - `cue_guid` is minted on rebuild, so read it after the rebuild.
  - `set_light_color` takes `LinearColor`.
  - `get_cine_camera_component()` is an accessor, not a property.

## Order (Gary's priority, 9 Oct 22:35)
1. **S3 diagnosis, READ-ONLY (E1)**: run `Saved/CodexConductor/s3_visual_diag_20261009_request.json`. Report per figure:
   - which material and texture is bound to the shroud, T-shirt and underwear slots
   - whether those textures are loaded
   - the shading model
   - why the hessian reads black or shiny and untextured
   - which figure has no shroud, and which is translucent
   - feet depth below the dune MESH (a trace against the mesh, not the formula)

   **NO fixes**: Gary said diagnose only.
2. **P02 Top wings (E9, job 91)**: run only the DRY that proves facing: `Saved/CodexFlatV3/rzswap` DRY for P02 with `top_border:true`, per `Docs/Conductor` job 91 report / `Saved/CodexRuns/last-message-20261009-174641-1883.txt`. Report the measured facing. No APPLY.
3. **P02 lighting = P01 (E8)**: W&T Q7 `Saved/CodexFlatV3/p02lighting/` (Q10-reconciled, commit 9d9e6b44). Follow the job 43 GPU-loss runbook. Then the P02 practicals: the P01 floor-practicals tool `P01FloorPracticals_20261008`, op FLOOR, passage P02. Both of these steps remove the old domestic lights.
4. **Chandelier**:
   - Staging: job 85 tool `Saved/CodexConductor/P75ChandelierStaging_20261009/`.
   - Then candles: job 56 `P56ChandelierCandles_20261009`, which needs job 55's socket JSON, now `ChandelierImport_20261009` (sockets Candle_01..44).
   - Then the swing: `P52PendulumSwing_20261009` (52/52b).
5. **Remaining tools**, each with DRY → APPLY, in this order:
   - 87 `P87OpeningFixes_20261009`. Also take ONE extra still: a WIDE shot of the whole new stage front. Gary has never seen it, because the opening camera is too tight.
   - 88 `Saved/CodexFlatV3/paperprosc/fringe_fix` (IMPORT).
   - 89 `P89CurtainBeforeShadow_20261009`.
   - 90 `I1Polish_20261009`.
   - 90b `Interaction90b_20261009`. It touches the same I2/I3 data as 90, so re-DRY it after 90.
   - 92 `Job92S2Envelope_20261009`.
   - 93 `P93_P03InterleaveFloor_20261009`.
   - 94 `P94S3Arrival_20261009`.
   - 96 `P96S4DarkCut_20261009`.
   - 97 `NapInterlude_20261009/e18_nap_revision*`.
   - 98 `S5GirderTexture_20261009`.
   - 95 camera seams `Job95CameraSeams_20261009`: Python half only. Its C++ patch FAILED its own test tonight (`FreeLookReturnsDuringPassageSettle`) and is NOT built.
   - Pearl 2 s fade (E2): `s3_pearl_fade.py` from the ~3:25 vanish point. DRY first; if no tool supports a 2 s fade, report and stop.
6. **Deprioritised (only if everything above is done)**:
   - 99 `P99S6ArrivalSun_20261009`.
   - 100 `S6OldLadySwarm` (Tools/Mocap/s6_old_lady_swarm.py).
   - 101 `E25Ending_20261009`.

   99–101 may still be finishing offline. Skip any whose folder or harness is not in the main tree.

## Stills
After each APPLY, take the tool's own stills plan where it has one (PIE you start and end yourself). Save them under `Saved/CodexConductor/LiveQueue_20261009/stills/`.

## Report
Write `Docs/Conductor/LIVE_QUEUE_REPORT_2026-10-09.md`:
- A table: item | run id | DRY verdict | APPLY marker | census after | stills | notes.
- Tier every claim per AGENTS.md.
- List the files you changed.
- Give the first STOP reason, if any.

Commit nothing.

## Added 9 Oct ~23:20 (run after item 5, before item 6)
7. **Job 103, P05 to 42.04 s (E26)**: `Saved/CodexConductor/passages_to_music_p05_e26_{dry,apply}_request.json`. The REVERT is `..._revert`. See `Docs/Conductor/P103_P05_E26_REPORT_2026-10-09.md`.
8. **Job 104, P06 to the full 125 s (E27/E27b)**: `Saved/CodexConductor/P104P06FullTrack_20261009/`. Run its DRY first. **Gary: "Leave the sound waves".** APPLY only if the DRY verdict is `LENGTHEN_ONLY`. If it says `IMPORT_AND_SWAP`, STOP and report.
