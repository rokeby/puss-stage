# P107: DRY-ALL pass (Codex --unreal, LIVE, READ-ONLY)

This is pass 1 of Gary's two-pass plan (9 Oct). **Run every remaining item's DRY. Do no APPLY at all.** Collect every failure in one report so that one offline batch can fix them together; pass 2 then runs the APPLYs.

HARD RULES: the `p49_postbake_editor_runner.md` rules, plus:
- **No APPLY, no save, no PIE.**
- Never end a PIE you did not start. Never quit or restart the editor. Never Save All.
- Purge the module cache before each tool: `Saved/CodexConductor/conductor_helpers/purge_saved_module_cache.py`.
- After EACH DRY, check that the dirty census is unchanged. If any DRY dirties a package, STOP everything and report.
- A DRY that FAILS or STOPS is recorded and you **move on to the next item**. This pass exists to find failures; it is not a reason to stop.
- You may patch trivial API-name bugs, then `py_compile` and rerun that DRY once. Report every diff. Never weaken a guard.
- Leave every args file as you found it, with `mode` DRY. If a tool needs a DRY-specific args file, write a new file next to it.
- Gary: leave the SoundWaves (no import or swap).

Already fixed by the conductor before this pass:
- P02 practicals: `floor_disagree_accept` covers the three 120.5 cm platform fixtures; it is already set in `P01FloorPracticals_20261008/p01_floor_args.json`.
- P75: the `Rotator.rotate_vector` call now goes through a Quat.

## Items (DRY each, in this order)
1. P02 practicals: `P01FloorPracticals_20261008`, FLOOR, P02.
2. P75 chandelier staging, opening + p06: `P75ChandelierStaging_20261009`.
   - Its previous opening APPLY record was retired as `.failed-P75CHAN-20261009-204553`, after a Don't-Save restart.
   - Then the candles DRY: `P56ChandelierCandles_20261009`.
   - Then the swing DRY: `P52PendulumSwing_20261009`. It may need the unbuilt sway-kick C++. If so, report that and do not treat it as a bug.
3. Jobs:
   - 87 `P87OpeningFixes_20261009`
   - 88 `Saved/CodexFlatV3/paperprosc/fringe_fix`
   - 89 `P89CurtainBeforeShadow_20261009`
   - 90 `I1Polish_20261009`
   - 90b `Interaction90b_20261009`
   - 92 `Job92S2Envelope_20261009`
   - 93 `P93_P03InterleaveFloor_20261009`
   - 94 `P94S3Arrival_20261009`
   - 95 `Job95CameraSeams_20261009` (Python only)
   - 96 `P96S4DarkCut_20261009`
   - 97 `NapInterlude_20261009/e18_nap_revision*`
   - 98 `S5GirderTexture_20261009`
   - pearl `s3_pearl_fade.py` (2 s fade)
4. 103 P05 at 42 s (`passages_to_music_p05_e26_dry_request.json`) and 104 P06 at 125 s (`P104P06FullTrack_20261009`). Report 104's verdict: LENGTHEN_ONLY or IMPORT_AND_SWAP.
5. 99 `P99S6ArrivalSun_20261009`, 100 `S6OldLadySwarm`, 101 `E25Ending_20261009`.
6. If they are in the main tree by then: 105 (P02 beams) and 106 (P02 Top flip). Skip them if absent.

Note: some DRYs depend on an earlier APPLY (90b after 90, candles after staging, 104 after 103). Run them anyway. Classify a failure as **DEPENDS_ON_PRIOR_APPLY** when that is the cause; that is expected and not a bug.

## Report
Write `Docs/Conductor/DRY_ALL_REPORT_2026-10-10.md`. One table: item | run id | DRY verdict | failure text (exact) | class | census unchanged? | proposed fix.

Classes:
- `OK`
- `API_BUG_FIXED`
- `API_BUG`
- `PRECONDITION`
- `DEPENDS_ON_PRIOR_APPLY`
- `STALE_ARGS`
- `GUARD_REFUSAL`
- `OTHER`

Tier every claim. Commit nothing.
