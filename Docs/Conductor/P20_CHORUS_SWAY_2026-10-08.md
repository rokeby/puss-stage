# P20 - Scene 3 chorus sway together (8 October 2026)

## Outcome

- **[measured]** The offline plan uses the six briefed CALM spans, reads the production inputs only from `E:/PussStage/DerivedAssets`, and produces a 30 s plan for Scene frames 3480-4200 / `LS_Clams` frames 3502-4222. The selected spans and mapping are explicit data, not inferred from actor labels (`Tools/Mocap/chorus_sway_together.py:38-49`; `Saved/CodexConductor/s3_chorus_sway_plan.json:54-570`).
- **[measured]** The WAV refinement finds a 7.320 s phrase period in 2:08-3:07, autocorrelation 0.794 under this tool's stated smoothing method, with maxima at 2:11.725, 2:19.225, 2:27.125, 2:34.175, 2:42.125, 2:48.725, 2:57.425 and 3:04.275 (`Saved/CodexConductor/s3_chorus_sway_plan.json:30-52`). This is a fresh measurement, not the same estimator as the brief's 0.64 figure.
- **[measured]** The offline harness passes **20/20**: 11 positive and 9 negative controls, including rate limits, overlap coverage, phase spread, continuation offsets, stale read-back detection and malformed/missing audio (`Tools/Mocap/test_chorus_sway_together.py:35-124`).
- **[inferred]** The curve-phase convention is editorial: 0 degrees means the fitted dominant signal is at its maximum. Whether those maxima read as a visible lean, and whether the resulting crowd feels collective rather than mechanical, still needs Gary's rendered review.

Preview: [`Previews/P20_CHORUS_SWAY_preview.png`](Previews/P20_CHORUS_SWAY_preview.png). Blue lines are the 3.6 s sway grid; gold lines are refined phrase maxima. The plotted signals include the planned retimes, one-second repeat overlaps and 1.5 s entry/exit easing (`Tools/Mocap/chorus_sway_together.py:291-330`).

## Plan

All play rates are `source period / 3.6 s`. The allowed band is 0.45-0.78 (0.75x-1.30x of today's 0.6).

| Figure | CALM source span(s), seconds | Measured signal / source period | Play rate | Fitted start phase | Default target | Default nudge |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Shore01_M56 | 5.708-12.083; 25.667-32.875 | spine_02 rot Z / 1.83 s; spine_02 rot X / 1.92 s | 0.508; 0.533 | 107.38 deg | 0 deg | -1.074 s |
| Shore02_F52 | 4.375-13.208 | spine_02 rot Z / 1.71 s | 0.475 | 261.42 deg | 60 deg | +1.586 s |
| Shore03_M59 | 1.167-19.125 | spine_02 rot Z / 2.42 s | 0.672 | 48.85 deg | 120 deg | +0.711 s |
| Shore04_F55 | 71.708-89.542 | pelvis rot Y / 2.75 s | 0.764 | 76.47 deg | 180 deg | +1.035 s |
| Shore05_M53 | 18.333-32.375 | spine_02 rot Y / 2.08 s | 0.578 | 287.74 deg | 240 deg | -0.477 s |
| Shore06_F25 | 78.167-91.458 | pelvis rot Y / 1.96 s | 0.544 | 239.00 deg | 300 deg | +0.610 s |

- **[measured]** The defaults spread start phases evenly by 60 degrees; every signed nudge is within half the 3.6 s target period (`Saved/CodexConductor/s3_chorus_sway_plan.json:54-570`). A negative nudge is implemented as its phase-equivalent positive source advance within the first CALM span, so no new section extends before the requested window (`Tools/Mocap/chorus_sway_together.py:144-184`).
- **[declaration-proven]** The editor args expose `window_start`, `window_end`, `target_period_s`, both blend durations and a per-figure `phase_nudges_seconds` map (`Saved/CodexConductor/s3_chorus_sway_args.json:1-15`). Any override outside +/-1.8 s is refused.
- **[measured]** M56 alternates its two chosen spans and needs three sections; each other figure needs two. Adjacent repetitions overlap 24 frames; the first/last sections ease for 36 frames (`Saved/CodexConductor/s3_chorus_sway_plan.json:54-570`).

## Sequence and binding evidence

- **[binary-proven]** The current production `E:/PussStage/Content/Scenes/LS_Clams.uasset` (SHA-256 `a18116037940a88d5c2c989c1576a7892035a77cdd0c576fea6cce88db20f3ee`) contains `/Game/Scenes/LS_Clams` at byte `0x9C`, all six `AS_Shore..._Full` names at `0x1765`-`0x190A`, and `MovieSceneSkeletalAnimationTrack` at `0x1CDA`. Binary assets have byte offsets rather than source lines.
- **[measured, historical read-back]** The latest stored probe names the nested sequence and 21,000-tick start offset, then reports all six animation assets on `Body` skeletal-animation bindings (`E:/PussStage/Saved/CodexConductor/probe_s3_shots.json:150-151`; `:1661`; `:1737`; `:1791`; `:1821`; `:1868`; `:2006`; `:2036`). The asset was saved later than that probe, so exact binding GUIDs are deliberately **UNCLEAR until DRY**.
- **[declaration-proven]** DRY discovers each binding by the exact animation asset, requires one section spanning the edit window, and reports the owner path and GUID without modifying or saving (`Saved/CodexConductor/s3_chorus_sway.py:276-310`).

## UE 5.8 section behavior

- **[declaration-proven]** `FMovieSceneSkeletalAnimationParams` declares Animation, FirstLoopStartFrameOffset, StartFrameOffset, EndFrameOffset, PlayRate, bReverse and Weight (`D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/MovieSceneTracks/Public/Sections/MovieSceneSkeletalAnimationSection.h:49-82`). Its section overrides `GetTotalWeightValue` (`.../MovieSceneSkeletalAnimationSection.h:147-153`).
- **[declaration-proven]** Base sections carry manual ease-in/out durations and evaluate easing; total section weight defaults to that easing (`D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/MovieScene/Public/MovieSceneSection.h:112-167`; `:654-694`). Constant time-warp read/write is exposed by `MovieSceneTimeWarpExtensions` (`D:/Unreal Engine/UE_5.8/Engine/Plugins/MovieScene/SequencerScripting/Source/SequencerScripting/Public/ExtensionLibraries/MovieSceneTimeWarpExtensions.h:23-52`).
- **[declaration-proven]** The engine's trim helper advances FirstLoopStartFrameOffset modulo the playable sequence (`D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/MovieScene/Public/MovieSceneSection.h:884-897`). The tool mirrors that calculation for the preserved right-hand section (`Saved/CodexConductor/s3_chorus_sway.py:75-94`).
- **[inferred, pending Unreal run]** These declarations support overlapping skeletal sections blending through section weight/easing. The tool has not been run in UE because the brief forbids editor access; DRY/APPLY read-back is still required before this becomes measured project behavior.

## Editor mutation contract

**[declaration-proven]** APPLY keeps the original section as the left side, clones a pose-continuous right side, inserts the retimed CALM sections between them, and never removes motion outside the window. It first requires no PIE, no open Sequencer and zero dirty packages; writes a record; creates `Backups/PreS3ChorusSway-<run>`; then requires the exact dirty census `[/Game/Scenes/LS_Clams]`, saves only that package, checks its disk hash changed, and reads back every range, offset, play rate, reverse flag, row, easing and weight (`Saved/CodexConductor/s3_chorus_sway.py:409-588`).

**[declaration-proven]** REVERT first validates every applied section against the record, makes `Backups/PreS3ChorusSwayRevert-<run>`, removes only recorded created section names, restores the original ranges/easing, saves only `LS_Clams`, and reads the originals back (`Saved/CodexConductor/s3_chorus_sway.py:462-503`). A failed APPLY leaves the record plus backup and emits `NOTHING SAVED; Don't-Save restart` where applicable.

## Extra crowd design stub

- **[inferred estimate]** A full close MetaHuman duplicate with hair/cloth is budgeted as roughly one additional "figure unit"; N full duplicates therefore add about `N/6` of the current six-character character/cloth load before extra shadow and translucency cost. Six full extras could approach twice the current crowd cost. This is a scaling estimate, not milliseconds measured on the show machine.
- **[inferred recommendation]** Prefer, in order: distant duplicates with cloth simulation disabled; baked cloak motion; hair cards or no groom; lower MetaHuman LODs; then low-poly skeletal or impostor crowd. Preserve the six hero figures for close shots.
- **[declaration-proven]** `extra_crowd_count` is present for planning, but APPLY refuses any non-zero value with `EXTRA_CROWD_DESIGN_ONLY`; this task does not duplicate a MetaHuman (`Saved/CodexConductor/s3_chorus_sway.py:445`; `:511-519`).

## Conductor run order

1. **[measured offline]** Re-run `python Tools/Mocap/test_chorus_sway_together.py E:/PussStage`; require `passed=20|failed=0|positive=11|negative=9`.
2. **[optional measured refresh]** Recompute without writing: `python Tools/Mocap/chorus_sway_together.py --mode DRY --run <run> --source-root E:/PussStage`. To replace the committed plan/preview, use APPLY with exact confirmation `APPLY S3CHORUSSWAYPLAN`; it creates its own backup.
3. **[pending measured]** Edit only `mode`, `run`, optional bounded phase nudges, and confirmation in `Saved/CodexConductor/s3_chorus_sway_args.json`. Start with DRY and blank confirmation.
4. **[pending measured]** Run `python Saved/CodexMocap/mcp_request.py tools/call --params-file Saved/CodexConductor/s3_chorus_sway_request.json`. Require six `S3_CHORUS_SWAY_PHASE` lines and `S3_CHORUS_SWAY_DRY_OK`; review exact binding paths/GUIDs and zero writes.
5. **[pending measured]** Set `mode=APPLY`, confirmation `APPLY S3CHORUSSWAY`, and a fresh run id; run the same request. Require `S3_CHORUS_SWAY_APPLY_OK`, `sections_read_back=25` (six preserved-left sections plus 19 newly created right/loop sections), the named backup, and `dirty=0`.
6. **[pending measured]** Restart cleanly and run DRY again; require `state=applied`. Then inspect the 2:25-2:55 section rendered with cloth, especially the two repeat blends and entry/exit.
7. **[pending measured]** To undo, set `mode=REVERT`, confirmation `REVERT S3CHORUSSWAY`, and a fresh run id. Require `S3_CHORUS_SWAY_REVERT_OK` and `dirty=0`.

## Open acceptance questions

- **[inferred]** Audio time is assumed equal to Scene 3 time. The existing audio note explicitly leaves the offset open (`Docs/Conductor/S3_AUDIO_BEATS_2026-10-08.md:3`); if an offset exists, shift phrase markers/preview before APPLY.
- **[inferred]** The 0/60/.../300 degree ordering is a neutral default, not creative approval. Gary may prefer clusters, pairs, or one counter-phase figure after seeing motion.
- **[inferred]** Offline curves do not prove cloth stability, root-foot behavior, repeat-seam invisibility, or performance. Those remain rendered and show-machine acceptance gates.
