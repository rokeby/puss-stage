# Codex job 62 — I2 polish Master-section lookup repair

Date: 2026-10-09. Scope: offline diagnosis, source repair, and offline regression only. Unreal, MCP, PIE, and rendered review were not run. No commit was made.

## Outcome

- **declaration-proven** — the old locator did not use the cue label or a GUID. It scanned only tracks whose exact class name was `MovieSceneSubTrack` or `MovieSceneCinematicShotTrack`, then matched the active section by the hard-coded I2 sequence path. The repaired locator additionally accepts `MovieSceneInfinitySceneTrack`, inventories track name, range, path, active state, and optional `BlockGuid`, and still requires exactly one active path match (`Saved/CodexConductor/I2Polish_20261009/i2_polish.py:30-36,79-88,540-564`).
- **declaration-proven** — the managed Master's actual schema is a custom `UMovieSceneInfinitySceneTrack`, derived from `UMovieSceneSubTrack`; rebuild creates/finds that custom track and assigns each compiled Scene/Interaction section its child sequence and compiled range (`Plugins/InfinityStage/Source/InfinityStage/Public/MovieSceneInfinitySceneTrack.h:27-37`; `Plugins/InfinityStage/Source/InfinityStageEditor/Private/InfinityStageSequenceBuilderLibrary.cpp:313-365`).
- **measured (live artifact read offline)** — job 24 retained the cue label `Interaction 2 — Turnips`, read back I2 playback `[0,1950]`, rebuilt 13 Scene sections, and reported Show/Master match true (`E:/PussStage/Saved/CodexSoftGoods/shrink_scene_playback_apply_51C-I2SHRINK-APPLY-20261009-0530.json:4,2757-2763,2873-2876`). Job 39 then refused with `MASTER_I2_SECTION_COUNT|0` (`E:/PussStage/Saved/CodexConductor/EDITOR_BATCH1E_REPORT.json:61-63`).
- **inferred from the two proved facts above** — the shrink did not rename I2 or change its sequence path. Its managed-Master rebuild exposed the pre-existing bad exact-class assumption: the custom track was skipped before its I2 section could be tested. No evidence supports a label, path, or GUID change caused by the shrink.

## Regression

- **measured (offline)** — `python Saved/CodexConductor/I2Polish_20261009/test_i2_polish.py` passes 31/31: 15 positive and 16 negative. The logged-state regression proves the legacy class filter returns `MASTER_I2_SECTION_COUNT|0`, the repaired filter returns exactly one section at logged Master tick `16929600`, and a Master containing only another Interaction still refuses with count 0 (`test_i2_polish.py:127-137,210-215`).
- **measured (offline)** — `python -m py_compile` passes for the tool and harness.
- **UNCLEAR (live)** — the corrected DRY has not been run in Unreal. The conductor must rerun DRY with a fresh run id and require `I2_POLISH_DRY_OK`; this report does not claim saved-state or rendered acceptance.

## I2 boundary camera

- **measured (live artifact read offline)** — probe `I2BOUNDARY-20261009-085622` recorded Scene 2 Exit Handoff Camera at offset -2, `CineCameraActor2` at -1, and `I2 Hangar Hold Camera` at offsets 0 through +2 (`E:/PussStage/Saved/CodexConductor/I2Polish_20261009/i2_boundary_probe_I2BOUNDARY-20261009-085622.json:94-146`).
- **declaration-proven** — the polish repair does **not** target `CineCameraActor2` by name or binding. Its probe gate accepts any seam with at least two view-target transitions in the sample window, and APPLY extends the unique active terminal nested section by one local Scene frame (`i2_polish.py:205-252,921-931`). With current args it evaluates all Scenes 1–6.
- **inferred / not visually proved** — therefore the repair is aimed at the general terminal nested-section seam condition, not exactly the observed offset -1 camera. A post-APPLY repeat probe is required to prove whether that specific `CineCameraActor2` frame disappears; APPLY should not be described as fixing that exact camera until it does.

## Conductor run

1. Copy the two changed tracked files into the active workspace.
2. From a clean, non-PIE editor state, give `i2_polish_args.json` a fresh DRY run id and execute the existing request.
3. Require `I2_POLISH_DRY_OK`, inspect the emitted Master I2 start and boundary plans, and do not APPLY if any refusal remains.
4. If APPLY is approved, follow the existing backup/save/read-back gates, then rerun `SavedMasterMatchesShow`, `SceneCutBindingsResolve`, and the boundary PIE probe. Rendered acceptance remains Gary's.
