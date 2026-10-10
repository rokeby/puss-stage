# P113 APPLY-pass report — 10 October 2026

## Outcome and acceptance boundary

- **Measured:** the opening editor census was clean and PIE was off: `content=[]`, `maps=[]`, `pie=false` (`Saved/Logs/PussStage.log:4418`). Gary's 01:06 Show save was therefore treated as the expected edit named in the brief, not current drift.
- **Measured:** item 1 (P02 practicals) and item 2a (P02 Top-facing flip) applied, saved only the Show and vertical-slice level, read back successfully, and were followed by clean censuses (`Saved/Logs/PussStage.log:4551`, `Saved/Logs/PussStage.log:4590`, `Saved/Logs/PussStage.log:4684`, `Saved/Logs/PussStage.log:4720`).
- **Measured:** item 2b (Job 105 beam bootstrap) reached a fresh DRY plan, then its APPLY stopped on `AttributeError: 'Transform' object has no attribute 'rotator'` (`Saved/Logs/PussStage.log:4732`, `Saved/Logs/PussStage.log:4744`). The failed record contains zero spawned actors and status `failed_rolled_back_in_memory` (`Saved/CodexFlatV3/p02lighting/p02_beam_bootstrap_record.json.failed-20261009-213557:644-645`).
- **Declaration-proven:** the P113 rule says a stop after a prepared record or without APPLY_OK stops the whole pass (`Docs/Conductor/codex_briefs/p113_apply_pass.md:9-11`). Accordingly, no further Unreal call was made after the Job 105 STOP; the rest of item 2 and items 3–14 were not run.
- **Measured:** the Job 105 stop report itself recorded `content=[]` and `maps=[]` both before APPLY and at STOP (`Saved/CodexFlatV3/p02lighting/p02_beam_bootstrap_report_APPLY_STOPPED_20261009-213557.json:15-23`).
- **Inferred:** PIE remained off at STOP because this pass never started PIE and the last explicit census before Job 105 reported `pie=false` (`Saved/Logs/PussStage.log:4720`). PIE was not re-probed after the STOP because the pass-stop rule prohibited further editor calls.
- **Measured:** no Save All, editor quit/restart, or PIE-start/end command was issued by this pass. No commit was created.

## Ordered result table

| item | run id | DRY | APPLY marker | read-back | census | stills | notes |
|---|---|---|---|---|---|---|---|
| 0. S3 diagnosis v2 | pre-marker | **Measured: FAILED before sequence evaluation.** First call rejected constructor keyword `restore_state`; the permitted API-only retry found no `restore_state` property (`Saved/Logs/PussStage.log:4434`, `Saved/Logs/PussStage.log:4471`; call site `Saved/CodexConductor/s3_visual_diag_20261009.py:810-817`). | N/A; read-only item | **Measured:** no report or per-figure/foot findings produced, so `S3_VISUAL_DIAG_V2_SUCCESS` and nonzero foot samples were not established. | **Measured:** clean after each failure (`Saved/Logs/PussStage.log:4456`, `Saved/Logs/PussStage.log:4492`). | none | **Measured:** the temporary change from constructor keyword to `set_editor_property("restore_state", True)` also failed and was reverted; final source text is back to the pre-run call. |
| 1. P02 practicals, FLOOR | `20261009-213232` | **Measured:** `P02FLOOR_DRY_OK`, run `20261009-213027`, 44 rows, plan SHA `c1a8913c…d91`, `mutated=0` (`Saved/Logs/PussStage.log:4504`). | **Measured:** `P02FLOOR_APPLY_OK`; 44 rows, Show+level saved, readback=1 (`Saved/Logs/PussStage.log:4551`). | **Measured:** record status `saved_readback_verified`; 44 spawned checks (`Saved/CodexConductor/P01FloorPracticals_20261008/p02_floor_record.json:132667-132674`). | **Measured:** record and independent live census both clean (`Saved/CodexConductor/P01FloorPracticals_20261008/p02_floor_record.json:132668-132670`; `Saved/Logs/PussStage.log:4590`). | not reached | **Measured:** 13 fresh foreign-record overlaps were reviewed and acknowledged for APPLY. Args were restored to their original DRY form afterwards. |
| 2a. Job 106, P02 Top flip | `P02TF-20261009-213500` | **Measured:** `P02_TOP_FACING_DRY_OK`, 23 Tops, state `14dc768a`, expected front sign reversal (`Saved/Logs/PussStage.log:4616`). | **Measured:** `P02_TOP_FACING_APPLY_OK`; only FacingPolicy, image flip false, P02 materialized, Show+level saved (`Saved/Logs/PussStage.log:4684`). | **Measured:** 23 fields written; image flip not written (`Saved/CodexFlatV3/p02_top_facing/p02_top_facing_apply_P02TF-20261009-213500.json:10-36`). | **Measured:** apply record and independent census clean (`Saved/CodexFlatV3/p02_top_facing/p02_top_facing_apply_P02TF-20261009-213500.json:686-692`; `Saved/Logs/PussStage.log:4720`). | not reached | **Measured:** args restored to shipped DRY confirmation. |
| 2b. Job 105, P02 beams | `20261009-213557` | **Measured:** `P02BEAMBOOTSTRAP_DRY_OK`, four actors planned, SHA `6792e5e2…623d`, `mutated=0` (`Saved/Logs/PussStage.log:4732`). | **Measured: STOPPED; no APPLY_OK.** `_spawn()` called unavailable `Transform.rotator()` (`Saved/Logs/PussStage.log:4744`; `Saved/CodexFlatV3/p02lighting/p02_beam_bootstrap_report_APPLY_STOPPED_20261009-213557.json:23-25`). | **Measured:** none applied; failed record says zero spawned and rolled back in memory (`Saved/CodexFlatV3/p02lighting/p02_beam_bootstrap_record.json.failed-20261009-213557:644-645`). | **Measured:** stop report content/maps clean (`Saved/CodexFlatV3/p02lighting/p02_beam_bootstrap_report_APPLY_STOPPED_20261009-213557.json:15-23`). | none | **Measured terminal stop.** A level backup exists at `Backups/PreP02BeamBootstrap-20261009-213557`; args restored to DRY. |
| 2c. P02 lighting = P01 | — | **Declaration-proven:** not run because Job 105 failed in the same dependency chain (`Docs/Conductor/codex_briefs/p113_apply_pass.md:22-25`). | — | — | — | none | GPU-loss runbook was not entered. |
| 3. Chandelier chain | — | **Declaration-proven:** not run after whole-pass STOP. | — | — | — | none | P75/P56/P52 untouched by this pass. |
| 4. Job 89 | — | **Declaration-proven:** not run after whole-pass STOP. | — | — | — | none | — |
| 5. Jobs 90 → 90b | — | **Declaration-proven:** not run after whole-pass STOP. | — | — | — | none | — |
| 6. Job 93 | — | **Declaration-proven:** not run after whole-pass STOP. | — | — | — | none | — |
| 7. Job 95 Python | — | **Declaration-proven:** not run after whole-pass STOP. | — | — | — | none | — |
| 8. Job 96 | — | **Declaration-proven:** not run after whole-pass STOP. | — | — | — | none | — |
| 9. Job 98 | — | **Declaration-proven:** not run after whole-pass STOP. | — | — | — | none | — |
| 10. Job 88 | — | **Declaration-proven:** not run after whole-pass STOP. | — | — | — | none | — |
| 11. Job 103; 11b Job 104 | — | **Declaration-proven:** not run after whole-pass STOP. | — | — | — | none | — |
| 12. Job 110 | — | **Declaration-proven:** not run after whole-pass STOP. | — | — | — | none | — |
| 13. Job 112-ready items | — | **Declaration-proven:** not evaluated or run after whole-pass STOP. | — | — | — | none | — |
| 14. Stills | — | **Declaration-proven:** not run after whole-pass STOP. | — | — | — | none | none | The required stage-wide still was not taken. |

## Saved authoring changes

- **Measured:** `/Game/InfinityStage/Dev/DA_InfinityStage_V1Show` and `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice` were saved by items 1 and 2a. Job 106's apply record names only those two packages (`Saved/CodexFlatV3/p02_top_facing/p02_top_facing_apply_P02TF-20261009-213500.json:686-692`).
- **Measured:** P02 practicals changed 44 scoped attachment rows and verified 44 spawned results (`Saved/CodexConductor/P01FloorPracticals_20261008/p02_floor_record.json:132667-132674`).
- **Measured:** P02 Top-facing changed exactly 23 FacingPolicy fields and did not write image flip (`Saved/CodexFlatV3/p02_top_facing/p02_top_facing_apply_P02TF-20261009-213500.json:10-36`).
- **Measured:** Job 105 changed no saved authoring data; its stopped record has zero spawned actors and the stop census is clean (`Saved/CodexFlatV3/p02lighting/p02_beam_bootstrap_record.json.failed-20261009-213557:644-645`; `Saved/CodexFlatV3/p02lighting/p02_beam_bootstrap_report_APPLY_STOPPED_20261009-213557.json:15-23`).
- **Inferred / visual acceptance pending:** these saved read-backs do not prove the P02 practical or Top-facing rendered look. Item 14 was not reached.

## Files created or updated by this pass

**Measured authoring packages**

- `Content/InfinityStage/Dev/DA_InfinityStage_V1Show.uasset`
- `Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap`

**Measured records, reports, and evidence**

- `Saved/CodexConductor/P01FloorPracticals_20261008/p02_floor_items_DRY_20261009-213027.csv`
- `Saved/CodexConductor/P01FloorPracticals_20261008/p02_floor_report_DRY_20261009-213027.json`
- `Saved/CodexConductor/P01FloorPracticals_20261008/p02_floor_report_APPLY_20261009-213232.json`
- `Saved/CodexConductor/P01FloorPracticals_20261008/p02_floor_record.json`
- `Saved/CodexFlatV3/p02_top_facing/p02_top_facing_dry_P02TF-20261009-213406.json`
- `Saved/CodexFlatV3/p02_top_facing/p02_top_facing_dry_LATEST.json`
- `Saved/CodexFlatV3/p02_top_facing/p02_top_facing_originals_P02TF-20261009-213500.json`
- `Saved/CodexFlatV3/p02_top_facing/p02_top_facing_apply_P02TF-20261009-213500.json`
- `Saved/CodexFlatV3/p02_top_facing/p02_top_facing_ACTIVE.json`
- `Saved/CodexFlatV3/p02lighting/p02_beam_bootstrap_report_DRY_20261009-213540.json`
- `Saved/CodexFlatV3/p02lighting/p02_beam_bootstrap_report_APPLY_STOPPED_20261009-213557.json`
- `Saved/CodexFlatV3/p02lighting/p02_beam_bootstrap_record.json.failed-20261009-213557`
- `Saved/Logs/PussStage.log`
- `Docs/Conductor/APPLY_PASS_REPORT_2026-10-10.md`

**Measured backups**

- `Backups/PreP02Floor-20261009-213232/` (Show + level; recorded at `Saved/CodexConductor/P01FloorPracticals_20261008/p02_floor_record.json:58880`)
- `Backups/PreP02TopFacing-20261009-2135/` (Show + level; `Saved/CodexFlatV3/p02_top_facing/p02_top_facing_apply_P02TF-20261009-213500.json:7`)
- `Backups/PreP02BeamBootstrap-20261009-213557/` (level backup only; no saved mutation followed)

**Measured temporary/restored files**

- `Saved/CodexConductor/P01FloorPracticals_20261008/p01_floor_args.json`, `Saved/CodexFlatV3/p02_top_facing/p02_top_facing_args.json`, and `Saved/CodexFlatV3/p02lighting/p02_beam_bootstrap_args.json` were temporarily put into exact-confirm APPLY mode and restored to their pre-run DRY values.
- `Saved/CodexConductor/s3_visual_diag_20261009.py` was temporarily patched for the permitted API retry, then restored after the retry failed. `Saved/CodexConductor/__pycache__/s3_visual_diag_20261009.cpython-314.pyc` was refreshed by the syntax check; `Saved/CodexFlatV3/p02_top_facing/__pycache__/p02_top_facing_core.cpython-311.pyc` was refreshed by the live run.

## First terminal STOP reason

**Measured:** Job 105 APPLY run `20261009-213557` stopped at `p02_beam_bootstrap.py:259` because UE 5.8's `Transform` wrapper has no `rotator()` method. There was no APPLY_OK. The record was retired as `failed_rolled_back_in_memory`, with zero spawned actors and clean content/map censuses. Per P113, this ended the whole pass (`Saved/Logs/PussStage.log:4744`; `Saved/CodexFlatV3/p02lighting/p02_beam_bootstrap_record.json.failed-20261009-213557:644-645`; `Docs/Conductor/codex_briefs/p113_apply_pass.md:9-11`).

## Resume attempt: item 0 rerun at 01:43 UTC

- **Measured:** the resumed pass purged the Saved-module cache first; Unreal reported `SAVED_MODULE_CACHE_PURGED|count=0|modules=` (`Saved/Logs/PussStage.log:4775`). It then dispatched `s3_visual_diag_v2_request.json` exactly once.
- **Measured:** S3 diagnosis v2 did not produce `S3_VISUAL_DIAG_V2_SUCCESS`. UE 5.8 did not expose a settable `restore_state` field, and after the transient `LS_Clams` evaluation the figure-state fingerprint changed from `c8ee3a64...ca13` to `be011283...708` (`Saved/Logs/PussStage.log:4784-4785`). The script raised `FIGURE_STATE_NOT_RESTORED` at its immediate restoration guard (`Saved/CodexConductor/s3_visual_diag_20261009.py:1152-1158`).
- **Declaration-proven:** the final dirty-package and actor censuses are below that guard (`Saved/CodexConductor/s3_visual_diag_20261009.py:1201-1213`), so they were not executed. Consequently actor identity and dirty-census equality after the run are **UNCLEAR**, and no clean-census claim is made.
- **Measured:** no fresh S3 diagnostic report was written. The existing `Saved/CodexConductor/S3_VISUAL_DIAG_20261009.json` predates this attempt (last modified 2026-10-09 19:42:35 local) and is not evidence for the resumed run. Nonzero foot samples and the requested per-figure findings were therefore not established.
- **Declaration-proven / terminal stop:** the resume instruction says to stop if actor identity or the census is not identical afterwards. The stronger in-script figure-state restoration guard failed, while the final identity/census checks were never reached. The pass stopped immediately: Job 105 beams, P02 lighting, and items 3-14 were not run.
- **Measured:** after the failure, this pass made no further Unreal/MCP call, issued no save, did not start or end PIE, and did not quit or restart the editor.

### Files updated by the resume attempt

- **Measured:** `Saved/Logs/PussStage.log` (Unreal appended the purge, warning, and failure evidence).
- **Measured:** `Docs/Conductor/APPLY_PASS_REPORT_2026-10-10.md` (this appended resume record).

### Resume terminal STOP reason

**Measured:** `S3_VISUAL_DIAG_V2_FAILED|FIGURE_STATE_NOT_RESTORED` after the one permitted item-0 run. Because the script failed before its final actor and dirty-package censuses, post-run cleanliness is UNCLEAR rather than clean (`Saved/Logs/PussStage.log:4785`; `Saved/CodexConductor/s3_visual_diag_20261009.py:1152-1158`, `:1201-1213`).

## Resume 2 preflight stop at 02:33 UTC

- **Measured:** the required opening census reported `content=[]`, `maps=["/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"]`, and `pie=false` (`Saved/Logs/PussStage.log:2969`). The vertical-slice map was therefore dirty at the preflight boundary.
- **Declaration-proven / terminal stop:** the resume-2 instruction says to stop if the opening dirty census is not clean. This pass stopped before item 2a / Job 115 and made no J115 DRY, APPLY, VERIFY, stills, args edit, targeted save, Save All, PIE start/end, editor quit, or editor restart.
- **Measured:** the only live-editor actions in resume 2 were the required Saved-module cache purge and the read-only census (`Saved/Logs/PussStage.log:2963`, `:2969`). No later Unreal/MCP call was issued by this pass.
- **UNCLEAR:** the source of the dirty vertical-slice package was not investigated because that would require continuing after the explicit preflight stop. Job 115, Job 105, P02 lighting, and items 3-14 remain unrun in resume 2.

### Files updated by resume 2

- **Measured:** `Saved/Logs/PussStage.log` (Unreal appended the purge and census evidence).
- **Measured:** `Docs/Conductor/APPLY_PASS_REPORT_2026-10-10.md` (this preflight-stop record).

## Resume 3: clean preflight, item 2a-first order, terminal Job 90 stop

- **Measured:** after Gary reported his floor test undone and the level saved, the required opening census was clean and PIE was off: `content=[]`, `maps=[]`, `pie=false` (`Saved/Logs/PussStage.log:3027`). Item 0 was skipped exactly as instructed.
- **Measured:** Job 115 failed during DRY before mutation with `TypeError: 'NoneType' object is not subscriptable`; its failure marker itself reports clean content/map censuses and no `J115SHIRTS_APPLY_OK` exists (`Saved/Logs/PussStage.log:3039-3040`). Under the resume-3 zero-mutation/clean-census SKIP rule, the pass continued to Job 105.
- **Measured:** Job 105 fresh DRY planned the same four P02 BeamLook actors and APPLY created four, saved the level only, and read back successfully (`Saved/Logs/PussStage.log:3070`, `:3093`). The independent post-apply census was clean with PIE off (`Saved/Logs/PussStage.log:3128`).
- **Measured:** P02 lighting fresh DRY planned 414 additions, 222 removals, 48 preserved specials and four atmosphere changes; APPLY emitted `PASSAGELIGHT_APPLY_OK`, saved Show+level, and passed field-scoped read-back (`Saved/Logs/PussStage.log:3205`, `:3305`). Its independent post-apply census was clean with PIE off (`Saved/Logs/PussStage.log:3381`).
- **Measured:** the owned P02-from-start PIE replay scrubbed successfully. The GPU-loss scan passed with no loss signatures, but the configured performance gate failed: p95 40.673 ms, p99 43.054 ms, max 84.756 ms (`Saved/Logs/PussStage.log:3528`, `:3546-3547`). This was recorded without immediate revert because no GPU-loss signature occurred. The pass restored the temporary transport setting, ended only its own PIE, and measured a clean post-PIE census (`Saved/Logs/PussStage.log:3560`, `:3572`, `:3599`).
- **Measured:** P75 Opening fresh DRY succeeded, but APPLY refused on `OWNED_ACTORS_EXIST|opening` before backup/record creation (`Saved/Logs/PussStage.log:3612`, `:3631`; guard order `Saved/CodexConductor/P75ChandelierStaging_20261009/chandelier_staging.py:567-578`). The following census was clean (`Saved/Logs/PussStage.log:3646`), so the dependent P75 P06/P56/P52 chain was skipped.
- **Measured:** Job 89 fresh DRY found all four requested changes. I1 APPLY then refused before backup/record creation on `UNBOUNDED_SECTION|MovieSceneDoubleVectorTrack` (`Saved/Logs/PussStage.log:3658`, `:3695`; mutation order `Saved/CodexConductor/P89CurtainBeforeShadow_20261009/p89_curtain_before_shadow.py:778-788`). The following census was clean (`Saved/Logs/PussStage.log:3707`), so the pass continued.
- **Measured / terminal stop:** Job 90 fresh DRY was apply-ready, but APPLY run `I1POLISH-R3-APPLY-20261009-2254` failed saved-state read-back for camera-fit `Location.X`; no `I1_POLISH_APPLY_OK` exists (`Saved/Logs/PussStage.log:3719`, `:3760`). The tool mutates channels and saves `/Game/InfinityStage/Interactions/LS_Interaction_01_WashingTheBoy` before performing that read-back (`Saved/CodexConductor/I1Polish_20261009/i1_polish.py:446-467`). Its transaction record remains `applied=false` and contains empty `camera_fit`, `f17` and `f18` arrays, with the pre-change backup path recorded (`Saved/CodexConductor/I1Polish_20261009/i1_polish_record.json:2-15`). This is a saved mutation with no APPLY_OK, so resume 3 stopped immediately without a further Unreal/MCP call. Current post-failure editor census is therefore **UNCLEAR**.
- **Declaration-proven:** Job 90b and items 6-14 were not run after the terminal stop. No S3 figure transform tool was run; Job 115 stopped in DRY. No Save All, editor quit/restart, or non-owned PIE end was issued.

### Resume 3 result table

| item | run id | DRY | APPLY/read-back | census | stills | result |
|---|---|---|---|---|---|---|
| 2a-critical. Job 115 shirts | `J115SHIRTS-20261009-224024` | **Measured:** failed before mutation | none | **Measured:** failure marker clean | none | skipped under zero-mutation rule |
| 2b. Job 105 beams | `20261009-224122` | **Measured:** OK, plan `6792e5e2...d623d` | **Measured:** APPLY_OK, four actors, level-only save, readback=1 | **Measured:** clean independently | not reached | complete at saved/read-back tier |
| 2c. P02 lighting = P01 | `20261009-224343` | **Measured:** OK, plan `7efdb840...b4e4` | **Measured:** APPLY_OK, Show+level saved, readback=1 | **Measured:** clean after APPLY and owned PIE | not reached | saved/read-back complete; performance gate failed; GPU health passed |
| 3. Chandelier chain | `P75CHAN-20261009-224852` | **Measured:** Opening DRY OK | **Measured:** pre-mutation refusal; P06/P56/P52 not run | **Measured:** clean after refusal | none | chain skipped |
| 4. Job 89 | `P89-R3-I1-20261009-2251` | **Measured:** ALL DRY OK | **Measured:** I1 pre-mutation refusal | **Measured:** clean after refusal | none | skipped |
| 5. Job 90 -> 90b | `I1POLISH-R3-APPLY-20261009-2254` | **Measured:** Job 90 DRY OK | **Measured:** saved mutation, read-back failed, no APPLY_OK; 90b not run | **UNCLEAR:** no post-failure call permitted | none | **terminal stop** |
| 6-14 | - | not run | not run | not re-probed | none | stopped after Job 90 |

### Resume 3 saved changes and evidence

- **Measured:** Job 105 saved the vertical-slice level and created `Saved/CodexFlatV3/p02lighting/p02_beam_bootstrap_record.json` plus `Backups/PreP02BeamBootstrap-20261009-224122/`.
- **Measured:** P02 lighting saved the Show and vertical-slice level and created `Saved/CodexFlatV3/p02lighting/passage_lighting_record.json`, its DRY/APPLY reports and preview, and a `PreP02LightingAsP01` backup named by that record.
- **Measured:** Job 90 created `Backups/PreI1Polish-I1POLISH-R3-APPLY-20261009-2254/LS_Interaction_01_WashingTheBoy.uasset`, then saved the live I1 sequence before read-back failed (`Saved/CodexConductor/I1Polish_20261009/i1_polish.py:438-467`).
- **Measured:** all temporarily edited args files were restored to their shipped DRY modes. The only source/doc file intentionally updated by resume 3 is this report.

### Resume 3 terminal STOP reason

**Measured:** Job 90 saved a mutation to `LS_Interaction_01_WashingTheBoy`, then failed `READBACK_CAMERA_FIT|...|Location.X` and emitted no APPLY_OK (`Saved/Logs/PussStage.log:3760`). The transaction record is not usable for REVERT because it remains `applied=false` with empty mutation rows, but the exact pre-change asset backup exists (`Saved/CodexConductor/I1Polish_20261009/i1_polish_record.json:2-15`). Per the resume-3 rule, no further editor call was made.

## Resume 4: item 6 complete, terminal Job 95 stop

- **Measured:** the required opening census was clean and PIE was off: `content=[]`, `maps=[]`, `pie=false` (`Saved/Logs/PussStage.log:3214`). Items 3-5 were skipped as instructed because Job 120 owns P75, Job 89 and Job 90/90b.
- **Measured:** Job 93 WINGS fresh DRY found 21 cues, classified 3 old and 18 newer pairs, and produced the approved 1/8/15 ordinal plan with `mutated=0` (`Saved/Logs/PussStage.log:3226-3227`). APPLY run `P93-20261009-231011` emitted `P93_P03_WINGS_APPLY_OK`, materialized 21 rows, saved only Show+level, and reported a clean internal census (`Saved/Logs/PussStage.log:3239-3258`). The independent census was also clean with PIE off (`Saved/Logs/PussStage.log:3294`).
- **Measured:** Job 93 FLOOR fresh DRY found exactly one actor/component/slot, the target was not already assigned, and the plan had `mutated=0` (`Saved/Logs/PussStage.log:3306-3307`). APPLY run `P93-20261009-231059` emitted `P93_P03_FLOOR_APPLY_OK`, assigned `/Game/InfinityStage/RigAtmos/MI_Floor_DarkWet`, saved only the level, and reported a clean internal census (`Saved/Logs/PussStage.log:3319-3327`). The independent post-item census was clean with PIE off (`Saved/Logs/PussStage.log:3362`).
- **Measured:** Job 95 fresh DRY run `J95-R4-DRY-20261009-2312` found six Passage rigs, six Passage-to-Scene seams and six Scene Entry cameras, with `matched=6` and `stale=0` (`Saved/Logs/PussStage.log:3384`).
- **Measured / terminal stop:** Job 95 APPLY run `J95-R4-APPLY-20261009-2312` created a SHA-256-verified level backup and a record with status `PREPARED_BEFORE_MUTATION`, then failed with `TypeError("set_actor_transform() required argument 'sweep' (pos 2) not found")`; no `JOB95_APPLY_OK` exists (`Saved/Logs/PussStage.log:3396`; `Saved/CodexConductor/Job95CameraSeams_20261009/records/job95_J95-R4-APPLY-20261009-2312_apply.json:2-8,443-447`).
- **Declaration-proven:** the tool writes the PREPARED record, calls `rig.modify()`, writes `crossing_settle_seconds`, and then calls the failing `set_camera()` before reaching `save_and_verify()` (`Saved/CodexConductor/Job95CameraSeams_20261009/camera_seam_tool.py:275-291`). Therefore the editor may contain an in-memory map mutation, but the tool did not reach its targeted save. The current dirty census is **UNCLEAR** because the resume-4 rule prohibits any further editor call after a prepared record/no-APPLY_OK stop.
- **Declaration-proven:** items 8-14, including Jobs 96, 98, 88, 103, 104, 110, the Job-112-ready subset, Job 119 and all stills, were not run after the Job 95 terminal stop. No Save All, PIE start/end, editor quit/restart, or S3 figure-transform command was issued by resume 4.

### Resume 4 result table

| item | run id | DRY | APPLY/read-back | census | stills | result |
|---|---|---|---|---|---|---|
| preflight | - | **Measured:** clean, PIE off | N/A | **Measured:** `content=[]`, `maps=[]`, `pie=false` | none | continue |
| 6a. Job 93 P03 wings | `P93-20261009-231011` | **Measured:** OK, 21/3/18, ordinals 1/8/15 | **Measured:** APPLY_OK, 21 materialized, Show+level saved and read back | **Measured:** clean independently | deferred to item 14 | complete at saved/read-back tier |
| 6b. Job 93 P03 floor | `P93-20261009-231059` | **Measured:** OK, 1/1/1, not already target | **Measured:** APPLY_OK, dark-wet material assigned, level saved and read back | **Measured:** clean independently | deferred to item 14 | complete at saved/read-back tier |
| 7. Job 95 camera seams | `J95-R4-APPLY-20261009-2312` | **Measured:** OK, matched 6, stale 0 | **Measured:** PREPARED record; APPLY failed before save; no APPLY_OK | **UNCLEAR:** no post-failure call permitted | none | **terminal stop** |
| 8-14 | - | not run | not run | not re-probed | none | stopped after Job 95 |

### Resume 4 saved changes and evidence

- **Measured:** Job 93 WINGS saved `/Game/InfinityStage/Dev/DA_InfinityStage_V1Show` and `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice`; its record is `Saved/CodexConductor/P93_P03InterleaveFloor_20261009/p93_wings_record_P93-20261009-231011.json`, with backup `Backups/PreP93P03Wings-20261009-231011/` (`Saved/Logs/PussStage.log:3258`).
- **Measured:** Job 93 FLOOR saved the vertical-slice level; its record is `Saved/CodexConductor/P93_P03InterleaveFloor_20261009/p93_floor_record_P93-20261009-231059.json`, with backup `Backups/PreP93P03Floor-20261009-231059/` (`Saved/Logs/PussStage.log:3327`).
- **Measured:** Job 95 wrote `Saved/CodexConductor/Job95CameraSeams_20261009/records/job95_J95-R4-DRY-20261009-2312_dry.json` and the incomplete APPLY record named above. Its pre-APPLY level backup is `Backups/PreJob95CameraSeam-J95-R4-APPLY-20261009-2312-20261009-231237/`, recorded with SHA-256 `299ed352c0f99e931830d9290a2f350b724f989506895700d5ebe5f3d45fa5cc` (`Saved/CodexConductor/Job95CameraSeams_20261009/records/job95_J95-R4-APPLY-20261009-2312_apply.json:2-8`).
- **Measured:** `p93_args.json` and `camera_seam_args.json` were restored to their pre-run DRY contents. `Saved/Logs/PussStage.log` contains the live evidence, and this report is the only source/document file intentionally updated by resume 4.

### Resume 4 terminal STOP reason

**Measured:** Job 95 produced a `PREPARED_BEFORE_MUTATION` record, then failed on the missing required UE 5.8 `sweep` argument before any APPLY_OK or targeted save (`Saved/Logs/PussStage.log:3396`). Per the explicit resume-4 rule, no subsequent census or other Unreal/MCP operation was issued; the conductor must reconcile the live editor state, normally by its Don't-Save recovery procedure, before another pass.

## Resume 5: fixed retries, bounded Gary waits, terminal pearl-fade stop

- **Measured:** The opening census initially found the vertical-slice map dirty with non-owned PIE active; after one 60-second recheck it was clean and PIE was off. Only then was the failed R4 Job 95 record retired by rename to `job95_J95-R4-APPLY-20261009-2312_apply.json.failed-J95-R4-APPLY-20261009-2312`.
- **Measured:** Job 95 fresh DRY matched all six Passage-to-Scene seams. APPLY run `J95-R5-APPLY-20261010-0337` emitted `JOB95_APPLY_OK`, saved only the vertical-slice map, and supplied its backup/record paths (`Saved/Logs/PussStage.log:4380,4399`). The independent census was clean with PIE off.
- **Measured:** Job 90 fresh DRY was apply-ready. Its first APPLY refused before mutation because the stale resume-3 record still occupied the fixed record path (`Saved/Logs/PussStage.log:4451,4463`). The record was `applied=false`, the independent census was clean, and the user's resume instruction states I1 had already been restored from backup; the stale record was therefore preserved by rename to `i1_polish_record.json.failed-I1POLISH-R3-APPLY-20261009-2254`. Retry `I1POLISH-R5-APPLY-20261010-0344` emitted `I1_POLISH_APPLY_OK`, changed six camera-fit channels and five F18 holds, saved only I1, and reported `dirty=0` (`Saved/Logs/PussStage.log:4519`). The independent census was clean.
- **Measured:** Job 90b failed during DRY before mutation on `I2_NOT_THROUGH_PLANE|start=601.104|end=0.000|margin=1.000`; the independent census was clean, so the step was skipped (`Saved/Logs/PussStage.log:4640-4659`).
- **Measured:** Job 89 fresh DRY initially encountered an externally dirty PearlClam material and then succeeded after the second 60-second recheck. It planned four changes. I1 and I3 APPLY runs emitted `P89_CURTAIN_BEFORE_SHADOW_APPLY_OK`, saved/read back their named sequences, and their transaction records captured clean post-save censuses (`Saved/Logs/PussStage.log:4850,4872,4919,4941`; `Saved/CodexConductor/P89CurtainBeforeShadow_20261009/p89_curtain_before_shadow_record_I3.json`).
- **Measured:** Immediately after I3, an independent census found the vertical-slice map dirty even though the I3 transaction's own `dirty_after` was empty. That external dirt persisted through five 60-second rechecks, so I4 and I5 were skipped. The same map remained dirty across five item-specific rechecks for the chandelier chain, Job 96, Job 98, Job 88, and Job 103; non-owned PIE was active during part of that interval and was never ended by this pass (`Saved/Logs/PussStage.log:4983-6185`). Each item was skipped without a tool run. The census finally became clean at the first Job 104 recheck (`Saved/Logs/PussStage.log:6230`).
- **Measured:** Job 104 fresh DRY returned the approved `IMPORT_AND_SWAP` decision for `P06_Walking6`, 125 seconds, with plan digest `f8bee409...6409` (`Saved/Logs/PussStage.log:6257`). APPLY failed before writing its PREPARED record or mutating assets because the loader doubled the `CodexConductor` directory while resolving `passage_retime_to_music.py` (`Saved/Logs/PussStage.log:6269-6297`). The independent census was clean, so Job 104 was skipped.
- **Measured:** Job 110 DRY refused before mutation because the live radius is 9000 cm while the guarded expected-current radius is 3200 cm (`Saved/Logs/PussStage.log:6336-6339`). The 10000 cm target was not applied; the independent census was clean.
- **Measured:** Job 87 failed in DRY before mutation because UE exposed no `passages` property on `InfinityStageShowAsset`. Job 92 failed in DRY before mutation on `LATTICE_Z_CHANNEL_COUNT|0` (`Saved/Logs/PussStage.log:6396`). Job 94 failed in DRY before mutation because `S3 WaveV3 Warm Side2` has keys `[0,436,...,456]` rather than the guarded start-key form (`Saved/Logs/PussStage.log:6420-6421`). Each was skipped after a clean independent census.
- **Measured:** Job 97 DRY resolved the live nap cue GUID `790E6F8D47A3B003E61BDA9FF691D78E`. APPLY run `E18-R5-APPLY-20261010-0446` emitted `E18_NAP_REVISION_APPLY_OK`, saved/read back the nine named Show/Master/map/nap/interaction packages, and recorded backup `Backups/PreE18NapRevision-E18-R5-APPLY-20261010-0446` (`Saved/Logs/PussStage.log:6583`). The independent census was clean.
- **Measured / terminal stop:** The two-second pearl fade fresh DRY was apply-ready and planned legacy-key adoption/retiming (`Saved/Logs/PussStage.log:6638`). APPLY run `S3PFADE-R5-APPLY-20261010-0450` wrote its exclusive transaction record and verified backup, called `scene.modify()`, then failed at the first legacy visibility-key removal because UE 5.8's `MovieSceneScriptingBoolKey` has no `remove()` method (`Saved/CodexConductor/s3_pearl_fade.py:183-205`; `Saved/Logs/PussStage.log:6653`). No `S3PFADE_APPLY_OK` exists. The current editor census is deliberately **UNCLEAR** because no further Unreal/MCP call is permitted after this post-record mutation-path failure.
- **Declaration-proven:** Job 99 non-PIE DRY, Job 101, Job 119, and all item-14 stills were not run after the terminal pearl stop. Job 100 remained excluded exactly as instructed. No Save All, editor quit/restart, non-owned PIE end, or S3 figure-transform operation was issued.

### Resume 5 result table

| item | run id | DRY | APPLY/read-back | census | stills | result |
|---|---|---|---|---|---|---|
| 7. Job 95 camera seams | `J95-R5-APPLY-20261010-0337` | **Measured:** six matched, zero stale | **Measured:** APPLY_OK, six seams, level-only save/read-back | **Measured:** clean independently | none | complete at saved/read-back tier |
| 5a. Job 90 | `I1POLISH-R5-APPLY-20261010-0344` | **Measured:** apply-ready | **Measured:** APPLY_OK, camera=6, F18=5, I1-only save/read-back | **Measured:** clean independently | none | complete at saved/read-back tier |
| 5b. Job 90b | `I90B-R5-DRY-20261010-0346` | **Measured:** pre-mutation through-plane refusal | none | **Measured:** clean independently | none | skipped |
| 4. Job 89 | `P89-R5-I1-20261010-0356`; `P89-R5-I3-20261010-0359` | **Measured:** four changes, then three after I1 | **Measured:** I1 and I3 APPLY_OK; I4/I5 not run | **Measured:** both transaction records clean; later external map dirt | none | partial; I4/I5 skipped after five waits |
| 3. Chandelier P75/P56/P52 | - | not run | not run | **Measured:** external map dirt persisted through five rechecks | none | chain skipped |
| 8. Job 96 | - | not run | not run | **Measured:** external map dirt/non-owned PIE persisted through five rechecks | none | skipped |
| 9. Job 98 | - | not run | not run | **Measured:** external map dirt/non-owned PIE persisted through five rechecks | none | skipped |
| 10. Job 88 | - | not run | not run | **Measured:** external map dirt persisted through five rechecks | none | skipped |
| 11. Job 103 | - | not run | not run | **Measured:** external map dirt persisted through five rechecks | none | skipped |
| 11b. Job 104 | `P104-R5-APPLY-20261010-0432` | **Measured:** IMPORT_AND_SWAP, 125 s, digest pinned | **Measured:** pre-record path-resolution failure; no mutation | **Measured:** clean independently | none | skipped |
| 12. Job 110 | generated timestamp | **Measured:** expected-current drift, 9000 vs 3200 cm | none | **Measured:** clean independently | none | skipped; 10000 cm not applied |
| 13a. Job 87 | `P87-R5-DRY-20261010-0437` | **Measured:** pre-mutation property-resolution failure | none | **Measured:** clean independently | none | skipped |
| 13b. Job 92 | generated timestamp | **Measured:** pre-mutation lattice-channel refusal | none | **Measured:** clean independently | none | skipped |
| 13c. Job 94 | `P94-R5-DRY-20261010-0442` | **Measured:** pre-mutation wave-key refusal | none | **Measured:** clean independently | none | skipped |
| 13d. Job 97 | `E18-R5-APPLY-20261010-0446` | **Measured:** live nap GUID resolved | **Measured:** APPLY_OK, nine named packages saved/read back | **Measured:** clean independently | none | complete at saved/read-back tier |
| 13e. Pearl two-second fade | `S3PFADE-R5-APPLY-20261010-0450` | **Measured:** apply-ready | **Measured:** record+backup, mutation path entered, API failure, no APPLY_OK | **UNCLEAR:** no post-failure call permitted | none | **terminal stop** |
| 13f-13g. Job 99 non-PIE; Job 101 | - | not run | not run | not re-probed | none | stopped after pearl |
| Job 119 S2 floor=P01 | - | not run | not run | not re-probed | none | stopped after pearl |
| 14. Stills | - | not run | not run | not re-probed | none | stopped after pearl |

### Resume 5 files and backups

- **Measured authoring packages saved:** vertical-slice map (Job 95); `LS_Interaction_01_WashingTheBoy` (Job 90 and Job 89 I1); `LS_Interaction_03_ForgetsHisName` (Job 89 I3); the nine packages named by Job 97's marker. No pearl sequence save completed.
- **Measured records/backups created:** Job 95 R5 record and `PreJob95CameraSeam-J95-R5-APPLY-20261010-0337-*`; Job 90 record and `PreI1Polish-I1POLISH-R5-APPLY-20261010-0344`; Job 89 I1/I3 records and matching backups; Job 97 record and `PreE18NapRevision-E18-R5-APPLY-20261010-0446`; pearl PREPARED-state record and `PreS3PearlFade-S3PFADE-R5-APPLY-20261010-0450`.
- **Measured retired records:** Job 95 R4 failed record and Job 90 resume-3 failed record were renamed with `.failed-<run>` suffixes; neither was deleted.
- **Measured temporary settings:** every edited args/settings file was restored to its pre-resume DRY content.
- **Measured report/evidence updates:** `Saved/Logs/PussStage.log` and this report.

### Resume 5 terminal STOP reason

**Measured:** `S3PFADE-R5-APPLY-20261010-0450` created its exclusive transaction record and backup, entered the mutation path, then failed on missing UE 5.8 `MovieSceneScriptingBoolKey.remove()` with no APPLY_OK (`Saved/Logs/PussStage.log:6653`; `Saved/CodexConductor/s3_pearl_fade.py:183-205`). Per the explicit stop rule, no subsequent census or live operation was issued. The conductor must reconcile the in-memory pearl-sequence state with Don't-Save recovery before another pass.

## Resume 6: Gary-priority order, terminal Job 104 partial APPLY

- **Measured:** the opening and item-1 censuses were clean with PIE off: `content=[]`, `maps=[]`, `pie=false` (`Saved/Logs/PussStage.log:2957,2963`). No bounded Gary wait was needed before items 1-4.
- **Measured:** Job 96 DRY found one curtain, 67 hangar lights/emissives, 13 Klara-precut targets and 128 P04 lights. APPLY run `P96-R6-APPLY-20261010-0447` added 209 tracks, saved/read back only `LS_DevScene_04`, emitted `P96_S4_DARK_CUT_APPLY_OK`, and reported `dirty=0` (`Saved/Logs/PussStage.log:2975,2996`). The independent census was clean (`Saved/Logs/PussStage.log:3031`).
- **Measured / rendered evidence:** this pass started and ended its own PIE and captured the requested P04 end, S4 cut and S4+1 s frames. The two S4 frames resolved to Master ticks `29706240` and `29730240`, exactly 24,000 ticks apart, and both still runs emitted `PASSAGE_STILLS_OK` (`Saved/Logs/PussStage.log:3263-3268,3332-3358`). The post-PIE census was clean (`Saved/Logs/PussStage.log:3397`).
- **Measured:** Job 92's first fresh DRY reproduced the pre-mutation `LATTICE_Z_CHANNEL_COUNT|0` refusal and the independent census was clean (`Saved/Logs/PussStage.log:3481,3487`). The read-only bounds probe then measured the live Klara bounds and retained the `Location.Z_4` suffix in its sequence inventory (`Saved/Logs/PussStage.log:3513`; `Saved/CodexConductor/Job92S2Envelope_20261009/s2_bounds_S2BOUNDS-20261010-005027.json`).
- **Declaration-proven / measured offline:** the Job 92 tool was narrowly corrected to canonicalise only UE's changing numeric channel suffix, to read the visibility property from its section row, and to keep malformed/multiple properties as a refusal (`Saved/CodexConductor/Job92S2Envelope_20261009/s2_envelope.py:130-158,187,212-218`). `S2_ENVELOPE_HARNESS` remained green at 14/14. Two consecutive live DRYs then produced the identical digest `fd71e510...38b7b` (`Saved/Logs/PussStage.log:3601,3613`).
- **Measured:** Job 92 APPLY run `S2ENV-R6-APPLY-20261010-0454` changed 99 scoped hangar actors and three lattice keys, saved/read back only `LS_S2_HangarRise` and the vertical-slice map, left the three Klara/scene sequences as guards, emitted `S2_ENVELOPE_APPLY_OK`, and reported `census=0+0` (`Saved/Logs/PussStage.log:3640`). The independent census was clean (`Saved/Logs/PussStage.log:3670`).
- **Measured / rendered evidence:** this pass started and ended a second owned PIE and captured S2 frame 1200 from the active Klara camera at Master tick `14343582`; `PASSAGE_STILLS_OK` and the clean post-PIE census followed (`Saved/Logs/PussStage.log:3799-3824,3851`). The file is `Saved/CodexConductor/ApplyPass_20261010/stills/02_job92_s2_klara_camera_wide_frame1200.png`. **Inferred:** the frame is visual enclosure evidence, not Gary's final look acceptance.
- **Measured:** Job 103 DRY was apply-ready for exactly P05, 186.363625 s -> 42.040000 s. It retained two reviewed `Camera.HeightOffsetCm` late keys by scaling them inside and warned that the resulting 1108.238 cm/s exceeds the 500 cm/s warning threshold (`Saved/Logs/PussStage.log:3888-3892`). APPLY emitted `PASSAGES_TO_MUSIC_APPLY_OK`, saved/read back the Show and Master, and recorded `PrePassagesToMusic-P103-E26-P05` (`Saved/Logs/PussStage.log:3965`). The independent census was clean (`Saved/Logs/PussStage.log:3995`).
- **Measured:** Job 104 DRY returned `IMPORT_AND_SWAP`, 125.000 s, scale `1.130596310`, chains A=6 and B=11, with the approved digest `f8bee409...6409` (`Saved/Logs/PussStage.log:4019,4034`). The previously measured doubled-directory loader was corrected by resolving `CodexConductor/...` from `Saved/` (`Saved/CodexConductor/P104P06FullTrack_20261009/p104_live.py:55-61`); `P104_HARNESS_OK` passed 36/36 offline.
- **Measured / terminal stop:** Job 104 APPLY run `P104-R6-APPLY-20261010-0458` saved the imported/swap audio step (`WALKING_MUSIC_APPLY_OK`) and saved the P06 length at 125 s (`PASSAGES_TO_MUSIC_APPLY_OK`) before failing while snapshotting an unbounded `MovieSceneSpawnSection`: `get_start_frame()` raised because the section has no start frame (`Saved/Logs/PussStage.log:4073,4133,4205,4218-4230`). No `P104_P06_FULL_125_APPLY_OK` exists.
- **Declaration-proven:** the coordinator record is `status="prepared"`, `stage="length_applied"`, and names both saved sub-records (`Saved/CodexConductor/P104P06FullTrack_20261009/p104_record_ACTIVE.json:2-3,128-131`). The failure occurred before the custom backup/record and before Job 42, chains A/B, domino and chandelier retiming writes (`Saved/CodexConductor/P104P06FullTrack_20261009/p104_live.py:376-396,494-505`). The saved sound swap and 125 s Show/Master length are therefore partial authoring changes; the remaining P06 retime is not established.
- **Declaration-proven / terminal boundary:** because Job 104 has a PREPARED record and no top-level APPLY_OK after saved mutations, no post-failure census or later live call was made. The editor's current dirty census is **UNCLEAR**. Items 5-12 were not run. No Save All, editor quit/restart, S3 figure-transform operation, or edit to `LS_Nap_BatteryChange` was issued by resume 6.

### Resume 6 result table

| priority | item | run id | DRY | APPLY/read-back | census | stills | result |
|---|---|---|---|---|---|---|---|
| 1 | Job 96 S4 dark cut | `P96-R6-APPLY-20261010-0447` | **Measured:** apply-ready, 209 additions | **Measured:** APPLY_OK; `LS_DevScene_04` saved/read back | **Measured:** clean independently and after owned PIE | P04 end, frame 405, frame 430 | complete at saved/read-back and still-evidence tiers |
| 2 | Job 92 S2 envelope | `S2ENV-R6-APPLY-20261010-0454` | **Measured:** initial zero-mutation refusals; repaired DRY stable twice | **Measured:** APPLY_OK; 99 actors, 3 keys; rise+map saved/read back | **Measured:** clean independently and after owned PIE | Klara active-camera wide at scene frame 1200 | complete at saved/read-back and still-evidence tiers |
| 3 | Job 103 P05 42.04 s | `P103-E26-P05` | **Measured:** apply-ready; two warnings | **Measured:** APPLY_OK; Show+Master saved/read back | **Measured:** clean independently | none requested | complete; speed warning remains |
| 4 | Job 104 P06 Walking6 125 s | `P104-R6-APPLY-20261010-0458` | **Measured:** IMPORT_AND_SWAP, digest pinned | **Measured:** audio swap and 125 s length substeps APPLY_OK; custom retime failed; top-level APPLY_OK missing | **UNCLEAR:** prohibited after PREPARED partial mutation | none | **terminal partial APPLY** |
| 5 | Job 110 P02 car radius 10000 | - | not run | not run | not re-probed | none | stopped after Job 104 |
| 6 | Job 98 S5 girders | - | not run | not run | not re-probed | none | stopped after Job 104 |
| 7 | Job 88 proscenium fringe IMPORT | - | not run | not run | not re-probed | none | stopped after Job 104 |
| 8 | Job 94 S3 arrival | - | not run | not run | not re-probed | none | stopped after Job 104 |
| 9 | Pearl two-second fade | - | not run | not run | not re-probed | none | stopped after Job 104; Job 132 fix not live-tested |
| 10 | Job 90b | - | not run | not run | not re-probed | none | stopped after Job 104 |
| 11 | P75 ADOPT_OR_CLEAN DRY -> staging -> P56 -> P52 | - | not run | not run | not re-probed | none | stopped before chain start |
| 12 | Job 101 ending | - | not run | not run | not re-probed | none | stopped after Job 104 |

### Resume 6 files, backups, and exclusions

- **Measured authoring packages saved before the terminal stop:** `LS_DevScene_04`; `LS_S2_HangarRise`; the vertical-slice map; Show and Master for P05; the P06 Cameron sound asset/swap plus Show and Master for the 125 s P06 length. Job 104's custom retime packages were not saved by its failed stage.
- **Measured records/backups:** `p96_record.json` and `PreP96S4DarkCut-P96-R6-APPLY-20261010-0447`; `s2_envelope_record.json` and `PreS2Envelope-S2ENV-R6-APPLY-20261010-0454`; `passages_to_music_record_P103-E26-P05.json` and `PrePassagesToMusic-P103-E26-P05`; Job 104's active PREPARED coordinator plus `walking_music_swap_record_P06.json`, `passages_to_music_record_P06_125_E27.json`, and their two recorded backups.
- **Measured stills:** `Saved/CodexConductor/ApplyPass_20261010/stills/01_job96_p04_end.png`, `01_job96_s4_cut_frame405.png`, `01_job96_s4_plus1s_frame430.png`, and `02_job92_s2_klara_camera_wide_frame1200.png`.
- **Measured tool/evidence changes:** Job 92 `s2_envelope.py`, its corrected MCP probe request, live bounds/dry reports and `s2_envelope_dry_r6_snapshot.json`; Job 104 `p104_live.py`; `Saved/Logs/PussStage.log`; and this report. All temporarily edited args files were restored to their pre-run DRY values.
- **Declaration-proven exclusions:** jobs 87, 99/126, 131, 119/129 and 111 were not run. No P75 cleanup was attempted. No S3 figure transform, Nap camera, Save All, editor quit or editor restart command was issued.

### Resume 6 terminal STOP reason

**Measured:** `P104-R6-APPLY-20261010-0458` saved its audio-swap and 125 s length substeps, left `p104_record_ACTIVE.json` PREPARED at `length_applied`, then failed on an unbounded `MovieSceneSpawnSection` before the remaining retime and before a top-level APPLY_OK (`Saved/Logs/PussStage.log:4133,4205,4218-4230`; `Saved/CodexConductor/P104P06FullTrack_20261009/p104_record_ACTIVE.json:128-131`). Per the resume-6 stop rule, no later Unreal/MCP call was made. The conductor must reconcile this partial saved state and the live editor before another pass.

## Pass 3

### Outcome and terminal boundary

- **Measured:** Pass 3 opened on the intended vertical-slice world with zero dirty content/map packages and PIE off (`Saved/Logs/PussStage.log:2852,2864`). The sky was already hidden after Gary's Don't-Save restart; this pass did not restart or quit the editor.
- **Measured / rendered evidence:** item 1 captured the requested S2 frame-1200 active-camera still and a runtime-only outside/above/behind wide. Both capture paths restored their runtime camera/frame state, and the owned PIE ended with a clean census (`Saved/Logs/PussStage.log:3079,3097,3136`). The measured renderable S2 bounds retained at least 377.964 cm lateral clearance and 2,289 cm roof clearance against the applied 8,500 cm half-width and 16,000 cm height (`Saved/CodexConductor/Job92S2Envelope_20261009/s2_bounds_S2BOUNDS-20261010-005027.json:23-32`; `Saved/CodexConductor/Job92S2Envelope_20261009/s2_envelope_record.json:17-18`). **Inferred / visual verdict:** neither still shows a side-wall or ceiling penetration; the exterior wide is useful enclosure evidence but not Gary's final aesthetic sign-off.
- **Measured:** item 2 set P05's curtain image to the deer texture and logged the previous pot texture as `/Game/InfinityStage/Curtains/Image/Textures/T_CurtainImage_P05_T_EndCurtain_P05_pot_20261007013712`; its immediate census was clean (`Saved/Logs/PussStage.log:3170,3215`). The held-transition still visibly shows the smaller deer and mushroom (`Saved/Logs/PussStage.log:3496`).
- **Measured:** item 3's required J118 P02-vs-P01 probe completed read-only after two narrow UE 5.8 compatibility fixes (`actor.get_actor_bounds(False)` and dynamically loaded `RendererSettings`); its offline harness remained 15/15 (`Saved/CodexConductor/J118S2FloorReflection_20261009/j118_floor_reflection_probe.py:303,486-487`; `Saved/Logs/PussStage.log:3648`). The subsequent floor DRY refused before mutation on `NON_IDENTITY_COMPONENT_TRANSFORM|Passage 01 - Opening Floor`; the independent census was clean, so no digest was copied and no floor APPLY or still was attempted (`Saved/Logs/PussStage.log:3660,3675,3687`).
- **Measured:** item 4's smoke-prop DRY refused before mutation because the named target lacks the required identity tag. The independent census was clean; no APPLY or still followed (`Saved/Logs/PussStage.log:3699-3717,3729`).
- **Measured:** item 5's DRY planned 93 left-panel local-X edits and generated confirmation `APPLY JOB128 4014b5249086beca`; the guarded live plan selected local X `0 -> -20 cm` from its recorded-sign evidence, rather than literally `+20 cm` (`Saved/CodexConductor/J128P05LeftX_20261010/job128_dry_latest.json:14341-14405`). APPLY run `J128-20261010-011735` emitted `JOB128_P05_LEFT_X_APPLY_OK`, saved/read back only the Show and vertical-slice level, and measured a minimum 0.149967 cm gap (`Saved/Logs/PussStage.log:3754,3784`; `Saved/CodexConductor/J128P05LeftX_20261010/job128_record.json:14354-14360,24703`). The independent census was clean (`Saved/Logs/PussStage.log:3820`). **Inferred / visual verdict:** the mid-pass still shows the paired corridor without an obvious panel intersection, so VISUAL PASS for overlap only; the very small measured minimum gap remains a precision concern, not a visible overlap (`Saved/Logs/PussStage.log:3950`).
- **Measured:** item 6 first reproduced the reviewed current-radius drift, 9,000 cm live versus 3,200 cm stale expected. After changing only the expected-current radius to 9,000, fresh DRY proposed 10,000 with aim, intensity and cone unchanged. APPLY run `P02CAR-TUNE-20261010-012009` saved/read back the level at 10,000 and reported dirty=0; the independent census was clean (`Saved/Logs/PussStage.log:4018,4042,4061,4096`). **Measured / visual verdict:** the required mid-pass still is too dark to reveal the far wing line, therefore VISUAL FAIL (`Saved/Logs/PussStage.log:4229`).
- **Measured / visual verdict:** item 7 captured an S5 mid-scene still, but the girders are not legible enough to judge their surface treatment; VISUAL FAIL (`Saved/Logs/PussStage.log:4400`). The owned PIE ended clean (`Saved/Logs/PussStage.log:4442`).
- **Measured / terminal stop:** item 8 fresh DRY passed with digest `475561e2`. IMPORT run `PPFRINGE-P3-20261010-0123` created its backup and durable record with `status="STARTED"`, entered texture import, then failed on UE 5.8's missing `Texture2D.post_edit_change()` before `PAPERPROSC_FRINGE_IMPORT_OK` (`Saved/Logs/PussStage.log:4455,4481`; `Saved/CodexFlatV3/paperprosc/fringe_fix/paperprosc_fringe_record.json:2,52-53`; `Saved/CodexFlatV3/paperprosc/fringe_fix/paperprosc_fringe_import.py:144,179-180`). Per the post-mutation stop rule, no census, retry, cleanup, still, PIE, or later item was run. The editor's current dirty/in-memory fringe state is **UNCLEAR**.
- **Declaration-proven:** items 9-13 were not run after the terminal fringe failure. No S3 figure transform, Klara level save, Save All, editor quit/restart, non-owned PIE end, or permanent deletion was issued.

### Pass 3 result table

| item | target | run id | APPLY marker | census | still path | visual verdict |
|---|---|---|---|---|---|---|
| 1 | S2 hangar fit, visual only | `PSTILLS-S2-20261010-050712-pass3-item01-s2-camera-w`; `P135 item01` | **Declaration-proven:** n/a, already applied | **Measured:** clean after owned PIE (`Saved/Logs/PussStage.log:3136`) | `Saved/CodexConductor/ApplyPass_20261010/stills/01_pass3_s2_klara_camera_wide_frame1200.png`; `01_pass3_s2_outside_above_behind.png` | **Inferred:** PASS for no side/roof poke-through; not look sign-off |
| 2 | P05 deer curtain | `CI-20261009-SETDEER-P05` | **Measured:** `CURTAIN_IMAGE_SET_OK` (`Saved/Logs/PussStage.log:3170`) | **Measured:** clean (`Saved/Logs/PussStage.log:3215`) | `Saved/CodexConductor/ApplyPass_20261010/stills/02_pass3_p05_deer_transition_held.png` | **Measured:** PASS, deer and mushroom visible |
| 3 | P02 floor = P01 floor | `J118P02PROBE-20261010-011552`; floor run stopped before marker | **Measured:** none; DRY guard refusal | **Measured:** clean (`Saved/Logs/PussStage.log:3687`) | none | **Declaration-proven:** NOT RUN; dependency-chain skip |
| 4 | P04 smoke-machine prop hide | pre-marker failure | **Measured:** none; DRY guard refusal | **Measured:** clean (`Saved/Logs/PussStage.log:3729`) | none | **Declaration-proven:** NOT RUN |
| 5 | P05 left wings local X -20 cm/inward separation | `J128-20261010-011735` | **Measured:** `JOB128_P05_LEFT_X_APPLY_OK` (`Saved/Logs/PussStage.log:3784`) | **Measured:** clean (`Saved/Logs/PussStage.log:3820`) | `Saved/CodexConductor/ApplyPass_20261010/stills/05_pass3_p05_wing_pairs_no_overlap.png` | **Inferred:** PASS for visible overlap only |
| 6 | P02 car radius 10,000 cm | `P02CAR-TUNE-20261010-012009` | **Measured:** `P02_CAR_LIGHT_TUNE_APPLY_OK` (`Saved/Logs/PussStage.log:4061`) | **Measured:** clean (`Saved/Logs/PussStage.log:4096`) | `Saved/CodexConductor/ApplyPass_20261010/stills/06_pass3_p02_car_far_wings_midpass.png` | **Measured:** VISUAL FAIL; far wings unreadable |
| 7 | S5 girders, visual only | `P135-I07-S5-GIRDERS-20261010` | **Declaration-proven:** n/a, already applied | **Measured:** clean after owned PIE (`Saved/Logs/PussStage.log:4442`) | `Saved/CodexConductor/ApplyPass_20261010/stills/07_pass3_s5_girders.png` | **Measured:** VISUAL FAIL; girders unreadable |
| 8 | Proscenium fringe IMPORT | `PPFRINGE-P3-20261010-0123` | **Measured:** missing; IMPORT failed after STARTED record (`Saved/Logs/PussStage.log:4481`) | **UNCLEAR:** prohibited after post-mutation failure | none | **Declaration-proven:** NOT CAPTURED; terminal stop |
| 9 | S3 arrival -> pearl 2 s -> 90b | - | **Declaration-proven:** not run | not re-probed | none | not run after terminal stop |
| 10 | 3D stage front | - | **Declaration-proven:** not run | not re-probed | none | not run after terminal stop |
| 11 | P01-P06 shadow radii + perf gate | - | **Declaration-proven:** not run | not re-probed | none | not run after terminal stop |
| 12 | Chandelier adopt/clean -> staging -> candles -> swing | - | **Declaration-proven:** not run | not re-probed | none | not run after terminal stop |
| 13 | Ending | - | **Declaration-proven:** not run | not re-probed | none | not run after terminal stop |

### Pass 3 files, backups and recovery boundary

- **Measured authoring saves before the terminal stop:** the P05 deer curtain texture/MI; Show + vertical-slice level for Job 128; vertical-slice level for the P02 car radius. No P02 floor or P04 smoke-prop APPLY occurred.
- **Measured records/backups:** `Saved/CodexConductor/J128P05LeftX_20261010/job128_record.json` and `Backups/PreP05LeftLocalX-J128-20261010-011735`; `Saved/CodexConductor/p02_car_light_tune_originals_P02CAR-TUNE-20261010-012009.json` and `Backups/PreP02CarLightTune-P02CAR-TUNE-20261010-012009`; terminal fringe `paperprosc_fringe_record.json` plus `Backups/PrePaperProscFringe-PPFRINGE-P3-20261010-0123`.
- **Measured tool/evidence changes:** J118's two UE 5.8 compatibility lines; the Job 128 MCP request wrapper; `p02_car_light_tune_args.json` left in DRY with expected/current 10,000 cm; Pass 3 still helpers and PNGs under `Saved/CodexConductor/ApplyPass_20261010/stills/`; `Saved/Logs/PussStage.log`; and this report. Existing authoring args edited for execution were returned to DRY mode where that mode exists.
- **Inferred / recovery guidance:** the fringe failure occurred after at least the first import call returned a `Texture2D`, but before the tool appended it to its `made` list or reached any targeted save. The durable record and backup prove the transaction started; exact dirty packages and whether an unsaved create-only texture remains in memory are intentionally unmeasured. The conductor should use Don't-Save recovery before a later corrected fringe IMPORT.

### Pass 3 terminal STOP reason

**Measured:** `PPFRINGE-P3-20261010-0123` left `paperprosc_fringe_record.json` at `status="STARTED"` and failed after entering the mutation path because `Texture2D.post_edit_change()` is unavailable (`Saved/Logs/PussStage.log:4481`; `Saved/CodexFlatV3/paperprosc/fringe_fix/paperprosc_fringe_record.json:52-53`; `Saved/CodexFlatV3/paperprosc/fringe_fix/paperprosc_fringe_import.py:144`). There is no IMPORT_OK marker and no permitted post-failure census. Per P135, Pass 3 stopped immediately; the conductor must reconcile via Don't-Save recovery before another live pass.

## Pass 4

### Outcome and terminal boundary

- **Measured:** after the conductor's Don't-Save restart, the transient editor-sky hide touched 13 actors without changing the dirty census, and the opening census was clean with PIE off: `content=[]`, `maps=[]`, `pie=false` (`Saved/Logs/PussStage.log:2893,2905`).
- **Measured:** Job 96 fresh DRY run `P96-P4-DRY-20261010-013028` found the already-applied cut plus 42 missing P04 darkness-extension actors: practical/glimmer/bulb bodies and related emissive descendants, all planned over `[0,406)` (`Saved/CodexConductor/P96S4DarkCut_20261009/p96_dry_P96-P4-DRY-20261010-013028.json:61-66,1868-1888`). RESUME run `P96-P4-RESUME-20261010-013028` added exactly those 42 tracks, repeated no camera edit, saved only `LS_DevScene_04`, read back and emitted `P96_S4_DARK_CUT_RESUME_OK|dirty=0` (`Saved/Logs/PussStage.log:2917,2937`). The independent census was clean with PIE off (`Saved/Logs/PussStage.log:2972`).
- **Declaration-proven:** the shipped P96 args expose no owned black-fade option; Pass 4 therefore did not invent a new fade outside the delivered tool (`Saved/CodexConductor/P96S4DarkCut_20261009/p96_args.json:1-8`; intended write surface `Saved/CodexConductor/P96S4DarkCut_20261009/README.md:7-24`).
- **Measured / rendered evidence:** the P04-end still visibly contains bright rig bulbs and warm practical pools. The frame-405 still and S4+1 s still both visibly show Klara's wall, green relief panel, floor and hanging object; neither is black. Their settled luma readings were 11.0, 6.7 and 6.6 respectively (`Saved/Logs/PussStage.log:3145,3234,3249`). **Visual verdict: FAIL** for all three darkness requirements. The owned PIE ended and the final census was clean (`Saved/Logs/PussStage.log:3293`).
- **Measured:** Job 104 fresh DRY run `P104-P4-DRY-20261010-0135` returned `decision=RESUME_RETIME_ONLY|next=RESUME`, proving the active coordinator was the saved Walking6/125-second partial transaction and that only the remaining retime was eligible to run (`Saved/Logs/PussStage.log:3305,3319`; resume guards `Saved/CodexConductor/P104P06FullTrack_20261009/p104_live.py:517-534`).
- **Measured / terminal stop:** P104 RESUME run `P104-P4-RESUME-20261010-0136` created `Backups/PreP104P06Full125Retime-P104-P4-RESUME-20261010-0136`, advanced the durable coordinator to `status="prepared"`, `stage="custom_recorded"`, wrote the proposed before/after retime state into it, mutated the live Show/level/bee/choreo/domino objects in memory, and then failed `JOB42_READBACK`; no `P104_P06_FULL_125_RESUME_OK` exists (`Saved/Logs/PussStage.log:3331,3383`; `Saved/CodexConductor/P104P06FullTrack_20261009/p104_record_ACTIVE.json:1146-1179,2499-2500`; mutation/verification order `Saved/CodexConductor/P104P06FullTrack_20261009/p104_live.py:429-444`).
- **Declaration-proven:** the P104 failure occurred before its first package save, because the failed verifier is at line 444 and targeted saves begin at lines 447-449 (`Saved/CodexConductor/P104P06FullTrack_20261009/p104_live.py:437-449`). The editor can therefore contain five-package in-memory mutations, while saved Walking6 and the 125-second Passage length remain the earlier partial save. The current post-failure dirty census is **UNCLEAR** because the pass-stop rule forbids any further Unreal call.
- **Declaration-proven:** items 3-7 were not run after the P104 prepared-record/no-RESUME_OK stop. No S3 arrival/pearl/90b, stage-front import, shadow-radius change/perf probe, chandelier operation, or Ending operation was attempted. No Save All, editor quit/restart, non-owned PIE end, Klara-level save, or permanent deletion was issued.

### Pass 4 result table

| item | target | run id | APPLY marker | census | still path | visual verdict |
|---|---|---|---|---|---|---|
| 1 | Job 96 RESUME, P04 darkness through S4 cut | `P96-P4-DRY-20261010-013028`; `P96-P4-RESUME-20261010-013028` | **Measured:** `P96_S4_DARK_CUT_RESUME_OK`, 42 tracks added, `camera_repeated=0`, LS_DevScene_04 saved/read back (`Saved/Logs/PussStage.log:2937`) | **Measured:** clean independently after save and after owned PIE (`Saved/Logs/PussStage.log:2972,3293`) | `Saved/CodexConductor/ApplyPass_20261010/stills/01_pass4_p04_end.png`; `01_pass4_s4_cut_frame405.png`; `01_pass4_s4_plus1s_frame430.png` | **Measured: VISUAL FAIL.** Bulbs/practical pools remain at P04 end; frame 405 and S4+1 s are not black. |
| 2 | Job 104 RESUME, verify Walking6 + 125 s then retime | `P104-P4-DRY-20261010-0135`; `P104-P4-RESUME-20261010-0136` | **Measured:** none; RESUME stopped at `JOB42_READBACK` after the durable record reached `custom_recorded` (`Saved/Logs/PussStage.log:3383`) | **UNCLEAR:** no post-failure Unreal call permitted | none; P06 dusk not reached | **Declaration-proven:** NOT CAPTURED; terminal stop |
| 3 | Job 94 -> pearl 2 s -> 90b | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 4 | Job 131/133 3D stage front | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 5 | Job 111 P01-P06 shadow radii + perf gate | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 6 | P75 chandelier chain | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 7 | Ending 101 | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |

### Pass 4 files, backups and recovery boundary

- **Measured authoring save:** Job 96 saved only `Content/InfinityStage/Dev/Sequences/LS_DevScene_04.uasset`; its resume backup is `Backups/PreP96S4DarkCut-P96-P4-RESUME-20261010-013028-RESUME/` (`Saved/Logs/PussStage.log:2937`).
- **Measured evidence:** Job 96 wrote `p96_dry_P96-P4-DRY-20261010-013028.json`; the two owned still runs wrote manifests under `Saved/CodexConductor/PassageStills/PSTILLS-P04-20261010-053242-pass4-item01-p96-p04end/` and `PSTILLS-S4-20261010-053354-pass4-item01-p96-cut-and/`; the three acceptance PNGs were copied to `Saved/CodexConductor/ApplyPass_20261010/stills/` with `01_pass4_` names.
- **Measured recovery evidence:** P104 wrote `p104_dry.json`, updated `p104_record_ACTIVE.json` to `prepared/custom_recorded`, and created `Backups/PreP104P06Full125Retime-P104-P4-RESUME-20261010-0136/` containing Show, vertical-slice level, bee-glints, P06 choreo and domino-finale packages. Those are backups of saved pre-retime files; Pass 4 did not restore or overwrite the live editor after the terminal stop.
- **Measured:** P96 and P104 args were returned to their shipped DRY forms by filesystem edit after execution. `Saved/Logs/PussStage.log` contains the live evidence, and this report is the only tracked document intentionally updated by Pass 4.

### Pass 4 terminal STOP reason

**Measured:** P104 RESUME run `P104-P4-RESUME-20261010-0136` mutated its five owned live objects after recording a backup and durable `custom_recorded` transaction, then failed the Job-42 semantic read-back before any targeted save (`Saved/Logs/PussStage.log:3383`; `Saved/CodexConductor/P104P06FullTrack_20261009/p104_live.py:429-449`). Because there is no RESUME_OK and the coordinator is prepared, Pass 4 stopped without a census or any later Unreal/MCP call. The conductor must use its Don't-Save recovery procedure before a corrected P104 retry.

## Pass 5

### Outcome and terminal boundary

- **Measured:** after the conductor saved the P04 smoke-prop hide, Pass 5 opened with zero dirty content/map packages and PIE off (`Saved/Logs/PussStage.log:2994`).
- **Measured:** Job 94 APPLY run `P94-P5-APPLY-20261010-014529` saved and read back `LS_DevScene_03`, `LS_S3_HangarRise` and `LS_Clams`, emitted `P94_S3_ARRIVAL_APPLY_OK`, and was followed by an independent clean census (`Saved/Logs/PussStage.log:3054,3085`).
- **Measured:** pearl run `S3PFADE-P5-APPLY-20261010-014700` retimed the fade to Master frames 4992-5040 and visibility-off to 5040, emitted `S3PFADE_APPLY_OK`, and was followed by an independent clean census (`Saved/Logs/PussStage.log:3097,3117,3146`).
- **Measured:** 90b DRY stopped before mutation on `I3_SHADOW_SPOTS_NOT_FOUND`; the independent census remained clean, so Pass 5 continued under the zero-mutation rule (`Saved/Logs/PussStage.log:3158,3183`; rule `Docs/Conductor/codex_briefs/p135_live_pass3.md:7`).
- **Measured:** the S3 acceptance run captured 11 settled PIE frames, and its helper requires Master scrub, a one-second re-pose, a second scrub, settle gating and live-camera-pose capture (`Saved/Logs/PussStage.log:3505`; `Saved/CodexConductor/scene_stills.py:27-31,73-82,317-321,370-410`). The pass ended only its own PIE and measured a clean census afterwards (`Saved/Logs/PussStage.log:3298,3531`).
- **Measured / visual verdict:** S3 frames 371 and 372 are black, frame 408 contains the first dim figures, and frames 444/480 show the brighter arrived group. This is a **VISUAL PASS** for blackout-to-rise; whether the exact transition is free of a one-frame pop is **UNCLEAR** because these are sampled stills, not a continuous clip (`Saved/CodexConductor/ApplyPass_20261010/stills/01_pass5_s3_arrival_frame371.png`, `...frame372.png`, `...frame408.png`, `...frame444.png`, `...frame480.png`).
- **Measured / visual verdict:** the pearl is bright at frame 4992, dimmer at 5016, but remains plainly visible at the requested visibility-off frame 5040. The saved channels passed data read-back, but rendered acceptance is **VISUAL FAIL** for full disappearance (`Saved/CodexConductor/ApplyPass_20261010/stills/01_pass5_pearl_frame4992.png`, `...frame5016.png`, `...frame5040.png`).
- **Measured:** StageFront3D IMPORT DRY run `SF3DI-20261010-015104` found all 36 inputs, no missing/existing destinations and no mutation (`Saved/Logs/PussStage.log:3546-3547`). **Declaration-proven / UNCLEAR:** the delivered importer configures static-mesh import plus 4K texture caps but contains no Nanite enable/write or Nanite verification (`Saved/CodexConductor/StageFront3D_20261010/stage_front_3d_import.py:116-135,247-282,333-356`). Because Nanite was an explicit acceptance requirement, no IMPORT call was made and MATERIAL, PLACE, Iron3 and the opening-wide still were not attempted.
- **Measured:** the J118 P02 probe remained read-only and reported five floors, two post-process volumes, 874 lights, zero captures, identical before/after census and zero saves (`Saved/Logs/PussStage.log:3559-3577`).
- **Measured:** after four narrow UE 5.8 API-compatibility corrections, the supplied Job 119 offline harness passed 22/22 and the fresh P02 DRY returned four target actors, four route segments, zero bindings/blockers/unclear rows and plan SHA `7e0b08d4...7cf0fd` (`Saved/CodexConductor/J119S2P01FloorReplace_20261009/j119_s2_p01_floor_replace.py:197,206,269,411,455`; `Saved/Logs/PussStage.log:3701`).
- **Measured / terminal stop:** APPLY run `J129P02P01-20261010-015520` shifted all four old P02 floor components in memory and duplicated the first P01-derived actor, then failed its first footprint read-back with `NOTHING_SAVED_DONT_SAVE_RESTART`; no APPLY_OK exists (`Saved/CodexConductor/J119S2P01FloorReplace_20261009/j129_p02_p01_floor_replace_record.json:4,31-97,620-622`; `Saved/Logs/PussStage.log:3713,3721-3722`). The tool performs that check before `save_attempted` and `_save_level_only()` (`Saved/CodexConductor/J119S2P01FloorReplace_20261009/j119_s2_p01_floor_replace.py:608-657`), so no authoring package was saved by this attempt, but the live editor contains uncommitted in-memory mutations. Per the post-mutation/missing-marker rule, Pass 5 stopped without another Unreal/MCP call or census (`Docs/Conductor/codex_briefs/p135_live_pass3.md:5-8`). Current dirty-package state is therefore **UNCLEAR**.
- **Declaration-proven:** Fringe IMPORT, shadow-radius survey/APPLY/performance gate, the P75 chandelier chain and Ending 101 were not run after the terminal stop. Jobs 96, 104, 87, 99/126 and 127, and `LS_Nap_BatteryChange`, were not run anywhere in Pass 5. No Save All, editor quit/restart, non-owned PIE end, Klara-level save or permanent deletion was issued.

### Pass 5 result table

| item | target | run id | APPLY marker | census | still path | visual verdict |
|---|---|---|---|---|---|---|
| 1a | Job 94, S3 arrival | `P94-P5-DRY2-20261010-014529`; `P94-P5-APPLY-20261010-014529` | **Measured:** `P94_S3_ARRIVAL_APPLY_OK` (`Saved/Logs/PussStage.log:3054`) | **Measured:** clean (`Saved/Logs/PussStage.log:3085`) | `Saved/CodexConductor/ApplyPass_20261010/stills/01_pass5_s3_arrival_frame371.png`, `...372.png`, `...408.png`, `...444.png`, `...480.png` | **Measured:** PASS for sampled blackout-to-rise; one-frame continuity UNCLEAR |
| 1b | Pearl 2 s fade | `S3PFADE-P5-DRY-20261010-014700`; `S3PFADE-P5-APPLY-20261010-014700` | **Measured:** `S3PFADE_APPLY_OK` (`Saved/Logs/PussStage.log:3117`) | **Measured:** clean (`Saved/Logs/PussStage.log:3146`) | `Saved/CodexConductor/ApplyPass_20261010/stills/01_pass5_pearl_frame4992.png`, `...5016.png`, `...5040.png` | **Measured: VISUAL FAIL;** pearl remains visible at frame 5040 |
| 1c | Job 90b | `I90B-P5-DRY-20261010-014800` | **Measured:** none; DRY refused on missing I3 shadow spots (`Saved/Logs/PussStage.log:3158`) | **Measured:** clean (`Saved/Logs/PussStage.log:3183`) | none | **Declaration-proven:** NOT APPLIED |
| 2 | Job 131 StageFront3D, six pieces + Iron3 | `SF3DI-20261010-015104` | **Measured:** none; IMPORT DRY only (`Saved/Logs/PussStage.log:3546-3547`) | **Measured:** clean in DRY marker | none | **Declaration-proven:** NOT IMPORTED; Nanite contract absent from delivered tool |
| 3 | J118 probe then J119/J129 P02 floor = P01 | `J118P02PROBE-20261010-015210`; `J129P02P01-20261010-015500`; `J129P02P01-20261010-015520` | **Measured:** none; APPLY failed after in-memory mutation (`Saved/Logs/PussStage.log:3713`) | **UNCLEAR:** no post-failure Unreal call permitted | none | **Declaration-proven:** NOT CAPTURED; terminal stop before saved result |
| 4 | Job 88 Fringe IMPORT | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 5 | Job 111 shadow radii + three-spot p95 gate | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 6 | P75 chandelier chain | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 7 | Ending 101 | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |

### Pass 5 files, saves and recovery boundary

- **Measured authoring saves before the terminal stop:** Job 94 saved `Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset`, `Content/InfinityStage/RigAtmos/LS_S3_HangarRise.uasset` and `Content/Scenes/LS_Clams.uasset`; the pearl step then saved `LS_DevScene_03` with its retimed fade/visibility channels (`Saved/Logs/PussStage.log:3054,3117`). StageFront3D and P02 floor saved no package.
- **Measured backups/records:** Job 94 created `Backups/PreP94S3Arrival-P94-P5-APPLY-20261010-014529/`. The terminal P02 attempt created `Backups/PreJ129P02P01Floor-J129P02P01-20261010-015520/` and left `j129_p02_p01_floor_replace_record.json` at `applied=false`, `state="applying"` (`Saved/CodexConductor/J119S2P01FloorReplace_20261009/j129_p02_p01_floor_replace_record.json:31-33,620-622`).
- **Measured evidence/tool updates:** the 11 Pass 5 S3/pearl PNGs are under `Saved/CodexConductor/ApplyPass_20261010/stills/`; three fresh J129 DRY reports and the J118 probe report were written; the Job 119 tool contains only the narrow compatibility corrections cited above. P94, pearl, 90b, StageFront3D and J119 authoring args were returned to DRY; J119 currently has blank digest and both acknowledgements false (`Saved/CodexConductor/J119S2P01FloorReplace_20261009/j119_s2_p01_floor_replace_args.json:1-10`).

### Pass 5 terminal STOP reason

**Measured:** P02 APPLY run `J129P02P01-20261010-015520` recorded four shifted existing components and one duplicated actor, then found the duplicate's measured bounds far smaller than the target segment and raised `P02_SEGMENT_FOOTPRINT_READBACK|...|NOTHING_SAVED_DONT_SAVE_RESTART` before its save stage (`Saved/Logs/PussStage.log:3713,3721-3722`; `Saved/CodexConductor/J119S2P01FloorReplace_20261009/j119_s2_p01_floor_replace.py:613-657`). The conductor must perform the prescribed Don't-Save editor recovery before another live pass; this job intentionally did not quit or restart the editor.

## Pass 6

### Outcome and terminal boundary

- **Measured:** after the conductor's Don't-Save restart, Pass 6 opened with zero dirty content/map packages and PIE off: `content=[]`, `maps=[]`, `pie=false` (`Saved/Logs/PussStage.log:2957`). A malformed Job-140 request envelope was rejected by MCP before project Python execution; after the wrapper-only correction, a second clean census proved that transport failure made no editor mutation (`Saved/Logs/PussStage.log:2979`; corrected wrapper `Saved/CodexConductor/P96S4DarkCut_20261009/p96_master_tail_request.json:1-10`).
- **Measured:** the Job-140 offline harness passed 9/9. Fresh DRY run `P96MASTER-P6-DRY-20261010-0219` found exactly 67 reviewed S4 hangar-light/emissive actors, planned hidden range `[30537,30540)`, and planned linear fade keys `[[30537,0.0],[30539,1.0],[30540,0.0]]`; it emitted `P96_MASTER_TAIL_DRY_OK` with plan SHA `4857d491...97d73fd` and `dirty=0` (`Saved/Logs/PussStage.log:2991`; `Saved/CodexConductor/P96S4DarkCut_20261009/p96_master_tail_dry_P96MASTER-P6-DRY-20261010-0219.json`).
- **Measured / terminal stop:** APPLY run `P96MASTER-P6-APPLY-20261010-0222` created its pre-change backup and durable record, then recorded all 67 visibility rows before failing at the fade creation call with `AttributeError: 'LevelSequence' object has no attribute 'add_master_track'` (`Saved/Logs/PussStage.log:3003,3011-3013`; `Saved/CodexConductor/P96S4DarkCut_20261009/p96_master_tail_record.json:612-657`). The record remains `status="applying"`, `fade=null`; no `P96_MASTER_TAIL_APPLY_OK` exists.
- **Declaration-proven:** the failure occurred before pre-save read-back and before the first targeted save: fade creation is line 241, while the first `save_asset` call is line 254 (`Saved/CodexConductor/P96S4DarkCut_20261009/p96_master_tail.py:241-255`). The saved Master package therefore remains the pre-APPLY file, while the live editor can contain 67 unsaved Master visibility bindings/tracks. Current dirty-package state is **UNCLEAR** because the post-mutation/missing-marker rule prohibits any further Unreal call.
- **Declaration-proven:** items 2-9 were not run after the Job-140 terminal stop. No still or visual verdict was produced; no owned PIE was started. No Save All, editor quit/restart, non-owned PIE end, Klara-level save, permanent deletion, or prohibited job was issued.

### Pass 6 result table

| item | target | run id | APPLY marker | census | still path | visual verdict |
|---|---|---|---|---|---|---|
| 1 | P96 Master tail: 67 S4 hangar lights hidden over P04 tail/cut plus black fade | `P96MASTER-P6-DRY-20261010-0219`; `P96MASTER-P6-APPLY-20261010-0222` | **Measured:** none; APPLY failed after recording 67 visibility mutations and before creating the fade (`Saved/Logs/PussStage.log:3003,3011-3013`) | **UNCLEAR:** no post-failure Unreal call permitted | none | **Declaration-proven:** NOT CAPTURED; terminal stop before P04-end/cut/S4+1 s stills |
| 2 | Job 104 RESUME, P06 retime | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 3 | Pearl 2 s fade, twin hidden at 5039 | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 4 | StageFront3D IMPORT/MATERIAL/PLACE/VERIFY, Dusty, Iron3 | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 5 | J119/J129 P02 floor = P01 | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 6 | Job 88 proscenium fringe IMPORT | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 7 | Job 111 shadow radii plus performance auto-revert gate | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 8 | P75 chandelier chain | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 9 | Ending 101 | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |

### Pass 6 files, backups and recovery boundary

- **Measured:** no authoring package was saved in Pass 6. Job 140 created `Backups/PreP96MasterTail-P96MASTER-P6-APPLY-20261010-0222/`, containing the pre-APPLY `LS_InfinityStage_V1Master.uasset` and `prestate.json`, and left `p96_master_tail_record.json` at `status="applying"` with 67 visibility rows and no fade.
- **Measured:** Pass 6 wrote the fresh DRY report, the durable failed APPLY record, the backup, and Unreal log evidence. The missing MCP request envelope was corrected in `p96_master_tail_request.json`. `p96_master_tail_args.json` was returned to its DRY placeholder state (`Saved/CodexConductor/P96S4DarkCut_20261009/p96_master_tail_args.json:1-10`). This report is the only tracked document intentionally updated.
- **Inferred / recovery guidance:** the conductor should use the prescribed Don't-Save restart to discard the 67 unsaved Master visibility edits. Before a later retry, Job 140 needs a UE5.8-compatible Master-track creation call and a fresh offline/live DRY; do not treat the existing `applying` record as an applied result.

### Pass 6 terminal STOP reason

**Measured:** Job-140 APPLY entered the mutation path and recorded all 67 visibility rows, then failed while trying to call unavailable `LevelSequence.add_master_track` for the black fade. Because the durable record is `applying`, `fade=null`, and no `P96_MASTER_TAIL_APPLY_OK` exists, Pass 6 stopped immediately without a post-failure census or any later Unreal/MCP call. The conductor must perform Don't-Save recovery before another live pass; this job did not quit or restart the editor.

## Pass 7

### Outcome and terminal boundary

- **Measured:** Pass 7 opened on the intended vertical-slice world with PIE/SIE off and zero dirty content/map packages (`Saved/Logs/PussStage.log:2837`; `Saved/CodexWingIntegration/remote_healthcheck.py:9-31`). The dedicated P96 Master-tail harness passed 9/9 before live execution.
- **Measured:** fresh P96 DRY `P96MASTER-P7-DRY-20261010-022837` reproduced the reviewed 67-actor plan and digest `4857d491...97d73fd`. APPLY `P96MASTER-P7-APPLY-20261010-022837` added 67 Master visibility tracks plus one fade, saved/read back only `LS_InfinityStage_V1Master`, emitted `P96_MASTER_TAIL_APPLY_OK`, and was followed by a clean independent census (`Saved/Logs/PussStage.log:2910,2933,2968`; applied record `Saved/CodexConductor/P96S4DarkCut_20261009/p96_master_tail_record.json:657-659`).
- **Measured / visual verdict:** P04's final sampled display frame, the P04-to-S4 cut frame, and S4 +1 s each render fully black at measured luma 0.0. This is a **VISUAL PASS** for the three requested checkpoints (`Saved/CodexConductor/PassageStills/PSTILLS-P04-20261010-063254-pass7-item01-p96-p04-end/passage_stills_manifest.json:63-76`; `Saved/CodexConductor/PassageStills/PSTILLS-S04-20261010-063415-pass7-item01-p96-boundar/passage_stills_manifest.json:66-78,131-135`). The pass ended only its own PIE and measured a clean census afterwards (`Saved/Logs/PussStage.log:3302`).
- **Measured:** Job 104 DRY `P104-P7-DRY-20261010-023600` selected `RESUME_RETIME_ONLY`. RESUME `P104-P7-RESUME-20261010-023600` preserved the already-swapped Walking6 audio and 125 s length, scaled sunset/car/bee, TOPPLE A (6), TOPPLE B (11) and P37, kept spatial FX and chandelier state, saved/read back its owned packages, emitted `P104_P06_FULL_125_RESUME_OK`, and was followed by a clean independent census (`Saved/Logs/PussStage.log:3340,3455,3494`; coordinator status `Saved/CodexConductor/P104P06FullTrack_20261009/p104_record_ACTIVE.json:3360-3363`). **UNCLEAR:** no P06 dusk still was captured before the later terminal stop, so rendered retime acceptance is not claimed.
- **Measured:** pearl DRY `S3PFADE-P7-DRY-20261010-023900` found the existing tracks adoptable and identified only the twin-visibility rewrite. APPLY `S3PFADE-P7-APPLY-20261010-023900` moved the twin's hidden key to frame 5039, retained the 4992-to-5040 fade, saved/read back `LS_DevScene_03`, emitted `S3PFADE_APPLY_OK`, and was followed by a clean independent census (`Saved/Logs/PussStage.log:3506,3526,3561`). **Measured / visual verdict:** the exact frame-5040 still shows the open clam with no pearl present, therefore **VISUAL PASS** (`Saved/CodexConductor/PassageStills/PSTILLS-S3-20261010-063835-pass7-item03-pearl-frame/passage_stills_manifest.json:65-77`). The pass ended only its own PIE and again measured a clean census (`Saved/Logs/PussStage.log:3753`).
- **Measured:** StageFront3D DRY `SF3DI-20261010-023944` found all 36 inputs, no missing/existing targets and no dirty packages (`Saved/Logs/PussStage.log:3766`). Thirty-six separate one-selector IMPORT calls then saved six Nanite meshes and thirty texture assets, with the final call reporting `complete=36/36` and `dirty_after=0+0` (`Saved/Logs/PussStage.log:5763`; six persisted Nanite records begin at `Saved/CodexConductor/StageFront3D_20261010/stage_front_3d_import_record.json:40-47`).
- **Measured / terminal stop:** the first MATERIAL call, `SF3DI-20261010-024911` for `arch`, created an unsaved master Material and material-expression graph, then failed on `CONNECT_MASK_r` with `NOTHING_ELSE_SAVED_USE_DONT_SAVE` (`Saved/Logs/PussStage.log:5801`; mutation before the failed connection is declaration-proven at `Saved/CodexConductor/StageFront3D_20261010/stage_front_3d_import.py:197-222`). The durable record still has 36 saved imports, zero completed materials, and a pending `arch` MATERIAL transaction (`Saved/CodexConductor/StageFront3D_20261010/stage_front_3d_import_record.json:648-656`). No post-failure census or Unreal/MCP call was made, so current dirty-package state is **UNCLEAR**.
- **Declaration-proven:** items 5-9 were not run after the terminal StageFront3D failure. Jobs 90b, 87, 99/126 and 127, and `LS_Nap_BatteryChange`, were not run anywhere in Pass 7. No Save All, editor quit/restart, non-owned PIE end, Klara-level save, or permanent deletion was issued.

### Pass 7 result table

| item | target | run id | APPLY marker | census | still path | visual verdict |
|---|---|---|---|---|---|---|
| 1 | P96 Master tail and black boundary | `P96MASTER-P7-DRY-20261010-022837`; `P96MASTER-P7-APPLY-20261010-022837` | **Measured:** `P96_MASTER_TAIL_APPLY_OK` (`Saved/Logs/PussStage.log:2933`) | **Measured:** clean after save and owned PIE (`Saved/Logs/PussStage.log:2968,3302`) | `Saved/CodexConductor/ApplyPass_20261010/stills/01_pass7_p04_end_black.png`; `01_pass7_p04_s4_cut_black.png`; `01_pass7_s4_plus1s_black.png` | **Measured: VISUAL PASS;** all three luma 0.0 |
| 2 | Job 104 RESUME, P06 Walking6 / 125 s retime | `P104-P7-DRY-20261010-023600`; `P104-P7-RESUME-20261010-023600` | **Measured:** `P104_P06_FULL_125_RESUME_OK` (`Saved/Logs/PussStage.log:3455`) | **Measured:** clean (`Saved/Logs/PussStage.log:3494`) | none | **UNCLEAR:** saved/read-back pass; P06 dusk not rendered |
| 3 | Pearl 2 s fade, frame 5040 empty | `S3PFADE-P7-DRY-20261010-023900`; `S3PFADE-P7-APPLY-20261010-023900` | **Measured:** `S3PFADE_APPLY_OK` (`Saved/Logs/PussStage.log:3526`) | **Measured:** clean after save and owned PIE (`Saved/Logs/PussStage.log:3561,3753`) | `Saved/CodexConductor/ApplyPass_20261010/stills/03_pass7_pearl_frame5040_empty.png` | **Measured: VISUAL PASS;** clam is open and empty |
| 4 | StageFront3D: Nanite imports, Dusty materials, Iron3, placement and wide opening still | IMPORT calls `SF3DI-20261010-024020` through `SF3DI-20261010-024849`; MATERIAL `SF3DI-20261010-024911` | **Measured:** 36/36 `STAGEFRONT3D_IMPORT_OK`; no MATERIAL_OK; MATERIAL failed after mutation (`Saved/Logs/PussStage.log:5763,5801`) | **UNCLEAR:** no post-failure census permitted | none | **Declaration-proven:** NOT CAPTURED; no material/placement/Iron3/wide still after terminal stop |
| 5 | J119/J129 P02 floor = P01 | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 6 | Job 88 proscenium fringe IMPORT | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 7 | Job 111 shadow radii plus performance auto-revert gate | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 8 | P75 chandelier chain | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 9 | Ending 101 | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |

### Pass 7 files, backups and recovery boundary

- **Measured authoring saves before the terminal stop:** `LS_InfinityStage_V1Master`; Job 104's owned Show/level, bee-glints, P06 choreo and domino-finale packages; `LS_DevScene_03`; and the 36 create-only StageFront3D mesh/texture packages. The StageFront material master was mutated only in memory and was not saved because the failure precedes the save block (`Saved/CodexConductor/StageFront3D_20261010/stage_front_3d_import.py:324-345`).
- **Measured backups/records:** `Backups/PreP96MasterTail-P96MASTER-P7-APPLY-20261010-022837/`; `Backups/PreP104P06Full125Retime-P104-P7-RESUME-20261010-023600/`; `Backups/PreS3PearlFade-S3PFADE-P7-APPLY-20261010-023900/`; 36 `PreStageFront3DImport-*` folders and `Backups/PreStageFront3DMaterial-SF3DI-20261010-024911/`. The StageFront import record deliberately remains live because its 36 imports were saved; its pending MATERIAL row identifies the failed unsaved step.
- **Measured evidence/tool state:** Pass 7 added four acceptance stills under `Saved/CodexConductor/ApplyPass_20261010/stills/`, the corresponding PassageStills manifests, fresh DRY reports/records and this report section. P96, P104, pearl and StageFront args were returned to DRY forms by filesystem edit after their last execution. No live tool source was patched in Pass 7.
- **Inferred / recovery guidance:** use the prescribed Don't-Save restart to discard the unsaved create-only StageFront master Material. Preserve the 36 saved imports and the live import record. Before retrying MATERIAL, fix `CONNECT_MASK_r` offline, run `py_compile` plus the positive/negative harness, then fresh live verification; do not clean or delete any imported package by hand.

### Pass 7 terminal STOP reason

**Measured:** StageFront3D MATERIAL run `SF3DI-20261010-024911` crossed its mutation boundary by creating the master Material and nodes, then failed its first mask-channel connection before any material save or `STAGEFRONT3D_MATERIAL_OK`. This is neither an `AttributeError` nor a failure before first mutation, so job 143's API-name exception does not apply. Per the post-mutation/missing-marker rule, Pass 7 stopped immediately without a census or any later Unreal/MCP call. The conductor must perform Don't-Save recovery before a corrected material retry; this job did not quit or restart the editor.

## Pass 8

### Outcome and terminal boundary

- **Measured:** Pass 8 opened on `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice` with PIE/SIE off and zero dirty content/map packages (`Saved/Logs/PussStage.log:2906`). The required post-restart editor sky toggle affected 13 actors transiently and reported an unchanged census; no package was dirtied (`Saved/Logs/PussStage.log:2900`).
- **Measured:** the read-only Job 144 reference probe evaluated the shadow frame in I1, I4 and I5 using the active camera binding, the common `GC_CurtainDrop_Opening` bounds, keyed transforms and keyed 35 mm focal length. I1 occupied `0.970849493` of frame width; I4 and I5 each overfilled the frame and therefore occupied `1.0` of visible width. Their mean visible fraction was `0.990283164`, giving `camera_distance_override_cm=714.008604` for Job 144's 480 cm curtain (`Saved/CodexConductor/Job144InteractionHangar_20261010/reference_frame_fraction.json:2,70,90,179,199,288,308,333`; final live marker `Saved/Logs/PussStage.log:3001`).
- **Measured:** I2 DRY `J144-P8-I2-DRY1-20261010-0308` and I3 DRY `J144-P8-I3-DRY1-20261010-0309` each refused before mutation with `ACTOR_LABELS_NOT_UNIQUE` (`Saved/Logs/PussStage.log:3013,3060`). Independent censuses after each refusal were clean and PIE was off (`Saved/Logs/PussStage.log:3048,3095`). Therefore neither interaction reached inventory digest/gobo approval, APPLY, saved read-back, or stills.
- **Measured:** the read-only J118 P01/P02 floor probe completed with `target=P02`, five floor actors, two PPVs, 874 lights, zero captures, unchanged census and no save (`Saved/Logs/PussStage.log:3125`).
- **Measured:** J129's first floor DRY refused before mutation because UE 5.8 exposes the root component as an editor property rather than `StaticMeshActor.get_root_component` (`Saved/Logs/PussStage.log:3137,3153`). Under the brief's pre-mutation API-name exception, only that call was changed to `actor.get_editor_property("root_component")` (`Saved/CodexConductor/J119S2P01FloorReplace_20261009/j119_s2_p01_floor_replace.py:223`); `py_compile` passed and the offline harness passed 24/24 with 20 positive and 15 negative controls (`Saved/CodexConductor/J119S2P01FloorReplace_20261009/harness_result.json:2-7`). Fresh DRY `J129P02P01-20261010-030446` then found four target actors/four route segments, zero sequence bindings, zero blockers and zero unclear rows, with plan SHA `059bd8c7...37285db` (`Saved/Logs/PussStage.log:3171`).
- **Measured / terminal stop:** APPLY `J129P02P01-20261010-030518` created and recorded four replacement actors, recorded four shifted original components, materialized Passage 02, entered `save_attempted`, and wrote the persistent map; the map timestamp became 03:05:20 and its size became 37,905,388 bytes. Its first post-save segment read-back then failed on `StaticMeshActor_1569`, so no `J129_P02_P01_FLOOR_REPLACE_APPLY_OK` exists (`Saved/Logs/PussStage.log:3193,3202`; record `Saved/CodexConductor/J119S2P01FloorReplace_20261009/j129_p02_p01_floor_replace_record.json:2-112,113-114,702-704`). No further Unreal/MCP call was made, so the current editor census and the saved floor result are **UNCLEAR**.
- **Declaration-proven:** Fringe 88, shadow radii 111 and its performance gate, the P75 chandelier chain, Ending 101, and the P06 dusk still were not run after the terminal stop. StageFront3D/145, 87, 90b, 99/126, 127 and `LS_Nap_BatteryChange` were not run anywhere in Pass 8. No Save All, editor quit/restart, non-owned PIE end, Klara-level save or permanent deletion was issued.

### Pass 8 result table

| item | target | run id | APPLY marker | census | still path | visual verdict |
|---|---|---|---|---|---|---|
| 1a | Job 144 reference fraction, I1/I4/I5 | final reference probe at `2026-10-10 03:02:44` local | read-only marker `JOB144_REFERENCE_FRACTION_OK` | **Measured:** clean, PIE off (`Saved/Logs/PussStage.log:3001`) | none | **Declaration-proven:** geometry measurement only; not a rendered acceptance still |
| 1b | Job 144 I2, back-wall curtain/shadow | `J144-P8-I2-DRY1-20261010-0308` | **Measured:** none; DRY refused before mutation | **Measured:** clean, PIE off (`Saved/Logs/PussStage.log:3048`) | none | **Declaration-proven:** NOT APPLIED / NOT CAPTURED |
| 1c | Job 144 I3, back-wall curtain/shadow | `J144-P8-I3-DRY1-20261010-0309` | **Measured:** none; DRY refused before mutation | **Measured:** clean, PIE off (`Saved/Logs/PussStage.log:3095`) | none | **Declaration-proven:** NOT APPLIED / NOT CAPTURED |
| 2 | J118 probe then J129 P02 floor = P01 | `J118P02PROBE-20261010-030402`; `J129P02P01-20261010-030446`; `J129P02P01-20261010-030518` | **Measured:** none; APPLY failed after targeted map save during post-save read-back | **UNCLEAR:** no post-failure Unreal call permitted | none | **Declaration-proven: VISUAL NOT CAPTURED;** saved result is not accepted |
| 3 | Job 88 proscenium fringe IMPORT | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 4 | Job 111 shadow radii + perf auto-revert | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 5 | P75 chandelier chain | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 6 | Ending 101 | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 7 | P06 dusk still for Job 104 | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |

### Pass 8 files, saves and recovery boundary

- **Measured:** the only authoring package saved in Pass 8 was `Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap` during the failed J129 APPLY. The pre-save backup is `Backups/PreJ129P02P01Floor-J129P02P01-20261010-030518/L_InfinityStage_V1VerticalSlice.umap` (37,893,282 bytes). The durable record remains `applied=false`, `state="save_attempted"`, with four actors and four shifted components.
- **Measured:** evidence/tool files written were the Job 144 reference probe/request/report, J118's fresh P02 report, J129's fresh DRY report and durable record, the J129 backup, the one-line UE 5.8 compatibility correction plus 24/24 harness result, and this report. Job 144 and J129 args were returned to their original DRY placeholder forms by filesystem edit after the stop.
- **Declaration-proven / recovery guidance:** J129 REVERT explicitly accepts records in `save_attempted` state before restoring recorded components and destroying only owned replacement actors (`Saved/CodexConductor/J119S2P01FloorReplace_20261009/j119_s2_p01_floor_replace.py:557-591`). Because the map save already occurred, a Don't-Save restart alone cannot be claimed to restore the pre-Pass-8 floor. The conductor should preserve the record and backup, then choose the guarded REVERT/recovery path before another live pass.

### Pass 8 terminal STOP reason

**Measured:** J129 APPLY reached its targeted save, then failed the first post-save footprint/material read-back and emitted no APPLY_OK marker. The durable record is `save_attempted`, not `applied`; therefore Pass 8 stopped immediately without a census, still, or any later Unreal/MCP item. Saved/runtime/rendered acceptance of the P02 floor is **UNCLEAR**.

## Pass 9

### Outcome and terminal boundary

- **Measured:** Pass 9 connected to the sole Unreal Editor listener on PussStage's configured loopback port `8010`, discovered `MCPBlueprintsGenerator.MCPBlueprintsGeneratorToolset`, and opened on `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice` with PIE/SIE off and zero dirty content/map packages (`Saved/Logs/PussStage.log:3479`; `.codex/config.toml:1-8`). The StageFront3D Job-145 offline harness passed **51/51** with zero Unreal/Blender processes started before live execution (`Saved/CodexConductor/StageFront3D_20261010/stage_front_3d_harness_result.json`).
- **Measured:** fresh StageFront3D DRY `SF3DI-20261010-031451` made no mutation, found all 36 source inputs present, and refused re-import because the six Nanite meshes and thirty textures already exist from Pass 7; its own dirty census remained empty (`Saved/Logs/PussStage.log:3491-3492`). This is the persisted import handoff, not a new import acceptance.
- **Measured / terminal stop:** the first Job-145 MATERIAL retry, `SF3DI-20261010-031507` for `arch`, created the unsaved master Material graph and then failed when UE returned false for `connect_material_expressions(add2, "", saturate, "Input")`. It emitted `STAGEFRONT3D_MATERIAL_FAILED|...|CONNECT_SATURATE|NOTHING_ELSE_SAVED_USE_DONT_SAVE`; no `STAGEFRONT3D_MATERIAL_OK` exists (`Saved/Logs/PussStage.log:3504,3506`; call site `Saved/CodexConductor/StageFront3D_20261010/stage_front_3d_import.py:304-312`).
- **Declaration-proven:** the failure occurred before MI creation, material binding, dirty-scope assertion, or any targeted asset save; those steps begin after the failed master build and the first save is at line 429 (`Saved/CodexConductor/StageFront3D_20261010/stage_front_3d_import.py:409-429`). The durable record remains `state="imported"`, with zero completed materials and a pending `arch` MATERIAL transaction for this run (`Saved/CodexConductor/StageFront3D_20261010/stage_front_3d_import_record.json:648-656`). The live editor can contain the unsaved partial master graph; current dirty state is **UNCLEAR** because the post-mutation/missing-marker rule prohibits a further Unreal call.
- **Declaration-proven:** Fringe 88, shadow-radius survey/APPLY/performance gate, the P75/P56/P52 chandelier chain, Ending 101, and the P06 dusk still were not run after the terminal stop. No owned PIE was started, so none was ended. Jobs 144, 147/P02 floor, 87, 90b, 99/126, 127 and `LS_Nap_BatteryChange` were not run. No Save All, editor quit/restart, Klara-level save, permanent deletion, or live tool-source patch was issued.

### Pass 9 result table

| item | target | run id | APPLY marker | census | still path | visual verdict |
|---|---|---|---|---|---|---|
| 1 | StageFront3D: six Dusty materials, PLACE DRY/APPLY/VERIFY with Iron3, opening-camera wide still | `SF3DI-20261010-031451` (DRY); `SF3DI-20261010-031507` (MATERIAL `arch`) | **Measured:** none; MATERIAL failed after in-memory mutation at `CONNECT_SATURATE` (`Saved/Logs/PussStage.log:3506`) | **UNCLEAR:** no post-failure Unreal call permitted | none | **Declaration-proven: VISUAL NOT CAPTURED;** material chain stopped on its first piece, so placement/verify/wide still were not run |
| 2 | Job 88 proscenium fringe IMPORT and close-up | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 3 | Job 111 P01-P06 shadow radii, raise-only APPLY, three-spot before/after p95 gate | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run; no performance samples or auto-REVERT decision |
| 4 | P75 ADOPT_OR_CLEAN/CLEAN, opening + P06 staging, P56 candles, P52 swing and stills | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 5 | Ending 101 and still | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 6 | P06 dusk still | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |

### Pass 9 files, backup and recovery boundary

- **Measured:** the terminal call created `Backups/PreStageFront3DMaterial-SF3DI-20261010-031507/` and rewrote the durable record's pending row before graph construction (`Saved/CodexConductor/StageFront3D_20261010/stage_front_3d_import.py:401-409`; record lines 649-653). No authoring package reached the save loop.
- **Measured:** Job 148 added MCP discovery/preflight response evidence under `Saved/CodexConductor/job148_*`, refreshed the StageFront harness result, created the MATERIAL backup/pending record, restored `stage_front_3d_import_args.json` to its original DRY form, and appended this report. No tool source was changed.
- **Inferred / recovery guidance:** use the prescribed Don't-Save editor restart to discard the unsaved partial StageFront master. Preserve the 36 saved imports and the live import record. Before a later retry, repair the Saturate connection offline, rerun `py_compile` plus the positive/negative harness, and then begin from a fresh clean live preflight; do not clean or delete any imported package by hand.

### Pass 9 terminal STOP reason

**Measured:** StageFront3D MATERIAL run `SF3DI-20261010-031507` crossed its mutation boundary while building the create-only master graph, then failed at `CONNECT_SATURATE` before any save and without `STAGEFRONT3D_MATERIAL_OK`. The user-authorized API-name exception applied only pre-mutation in DRY, so it cannot be used here. Per the Pass-9 post-mutation rule, the pass stopped immediately without a census, PIE, still, or any later Unreal/MCP item; this job did not quit or restart the editor.

## Pass 10

### Outcome and terminal boundary

- **Measured:** Pass 10 opened on `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice` with PIE/SIE off and zero dirty content/map packages (`Saved/Logs/PussStage.log:2865`). Exactly one `UnrealEditor` process was present at the filesystem/process preflight.
- **Measured:** Fringe DRY `PPFRINGE-P10-20261010-0330` completed with plan digest `475561e2`, three create-only textures, six target material instances, and a clean census (`Saved/Logs/PussStage.log:2878`; `Saved/CodexFlatV3/paperprosc/fringe_fix/paperprosc_fringe_dry_PPFRINGE-P10-20261010-0330.json`).
- **Measured / terminal stop:** Fringe IMPORT `PPFRINGE-P10-20261010-0330` imported all three textures in memory, then failed on the first `SkinColor` material-instance setter for `MI_FlatV3_PRO_side_L_Front`; no `PAPERPROSC_FRINGE_IMPORT_OK` exists (`Saved/Logs/PussStage.log:2888-2901`). The durable record was written before import and remains `status="STARTED"` (`Saved/CodexFlatV3/paperprosc/fringe_fix/paperprosc_fringe_record.json:2,52-53`).
- **Declaration-proven:** mutation precedes dirty-scope validation and all targeted saves: the tool imports textures and attempts the MI swap at line 196, while the first census gate and save are lines 197-198 and the success marker is line 206 (`Saved/CodexFlatV3/paperprosc/fringe_fix/paperprosc_fringe_import.py:193-206`). Therefore current dirty-package state is **UNCLEAR** and no further Unreal/MCP call was permitted.
- **Declaration-proven:** shadow radii Job 111 and its three-spot before/after performance gate, the P75/P56/P52 chandelier chain, Ending 101, and the P06 dusk still were not run after the terminal stop. StageFront3D/149, Job 144, the P02 floor/147, Jobs 87 and 90b, 99/126, 127, and `LS_Nap_BatteryChange` were not run anywhere in Pass 10. No PIE was started, so none was ended. No Save All, editor quit/restart, Klara-level save, permanent deletion, or live tool-source patch was issued.

### Pass 10 result table

| item | target | run id | APPLY marker | census | still path | visual verdict |
|---|---|---|---|---|---|---|
| 1 | Job 88 proscenium Fringe IMPORT and close-up | `PPFRINGE-P10-20261010-0330` | **Measured:** none; IMPORT failed after three in-memory texture imports at the first MI `SkinColor` setter (`Saved/Logs/PussStage.log:2888-2901`) | **UNCLEAR:** no post-failure Unreal call permitted | none | **Declaration-proven: VISUAL NOT CAPTURED** |
| 2 | Job 111 P01-P06 shadow radii, raise-only APPLY, three-spot before/after p95 gate | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run; no performance samples or auto-REVERT decision |
| 3 | P75 ADOPT_OR_CLEAN/CLEAN, opening + P06 staging, P56 candles, P52 swing and stills | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 4 | Ending 101 and still | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 5 | P06 dusk still | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |

### Pass 10 files, backup and recovery boundary

- **Measured:** the IMPORT created `Backups/PrePaperProscFringe-PPFRINGE-P10-20261010-0330/` and rewrote `paperprosc_fringe_record.json` before mutation (`Saved/CodexFlatV3/paperprosc/fringe_fix/paperprosc_fringe_record.json:2,52-53`). The three create-only texture packages were imported in memory, but the tool failed before its first `save_only` call (`Saved/CodexFlatV3/paperprosc/fringe_fix/paperprosc_fringe_import.py:196-198`).
- **Measured:** Pass 10 added the fresh Fringe DRY report, backup/record evidence, restored `paperprosc_fringe_args.json` to DRY placeholders (`Saved/CodexFlatV3/paperprosc/fringe_fix/paperprosc_fringe_args.json:2-6`), and appended this report. No tool source was changed.
- **Inferred / recovery guidance:** use the prescribed Don't-Save editor restart to discard the unsaved imported textures and any in-memory MI modification. Preserve the backup and `STARTED` record as failure evidence. Before a later retry, treat the UE 5.8 material setter's false return as a post-mutation API/return-value issue: repair offline, run the positive/negative harness, and only then begin from a fresh clean live preflight. Do not delete imported packages by hand.

### Pass 10 terminal STOP reason

**Measured:** Fringe IMPORT run `PPFRINGE-P10-20261010-0330` crossed its mutation boundary by importing three textures, then failed on the first material-instance `SkinColor` setter before any save and without `PAPERPROSC_FRINGE_IMPORT_OK`. Per the Pass-10 rule, the pass stopped immediately without a census, PIE, still, or any later Unreal/MCP item; this job did not quit or restart the editor.

## Pass 11

### Outcome and terminal boundary

- **Measured:** P02 VERIFY examined the Pass-8 `save_attempted` record and found eight saved-state issues: each of the four replacement actors had a world-location and world-bounds delta of exactly -100,000 cm in Z, classified as `ATTACHED_TO_SHIFTED_TARGET_FRAME`; it emitted `J129_P02_P01_FLOOR_REPLACE_VERIFY_MISMATCH` and did not mark the record applied (`Saved/Logs/PussStage.log:2915`; `Saved/CodexConductor/J119S2P01FloorReplace_20261009/j129_p02_verify_20261010-032611.json:65-70,206-211,347-352,488-493,578`).
- **Measured:** guarded REVERT `J129P02P01-20261010-032628` restored four recorded original components, destroyed four owned replacement actors, materialized P02, saved only the vertical-slice map, archived the record and ended with `content=[]`, `maps=[]` (`Saved/Logs/PussStage.log:2947`).
- **Measured:** this pass started its own PIE, captured P02 through `passage_stills.py`, ended that PIE, and then measured PIE off with a clean census. The brighter fraction-0.02 frame shows the reverted floor from the authored camera at Z=180 cm; the other sampled passage frames become very dark (`Saved/Logs/PussStage.log:2983,3150,3253,3266`). **Measured visual verdict:** the floor is visible in `01_pass11_p02_floor_reverted_f020.png`, but its strong green cast and lack of an unambiguous reflected image make this a **VISUAL FAIL** for the Pass-3 reflection criterion, not acceptance of the rejected P01-copy result.
- **Measured:** Job 111 did not reach its survey. Its shipped request envelope first returned HTTP 400; when routed temporarily through the current guarded request shape, its DRY runner failed before tool execution because the `exec` namespace omitted `__file__` (`Saved/CodexConductor/shadow_radius_reach_run.py:4-10`; `Saved/Logs/PussStage.log:3324`). The request file was restored unchanged. The independent post-failure census was clean and PIE was off (`Saved/Logs/PussStage.log:3336`). **Declaration-proven:** no shadow radius, performance sample or REVERT decision was made.
- **Measured:** P75 ADOPT_OR_CLEAN found one opening actor owned by failed run `P75CHAN-20261009-204553`, and CLEAN removed exactly that one actor with saved read-back and a clean census. The P06 adoption survey found no failed-run leftovers (`Saved/Logs/PussStage.log:3348,3367,3402`).
- **Measured:** fresh opening staging DRY `P75CHAN-20261010-033229` was clean, planned 24 links, three lights/two casters, no flames or swing keys, and produced reviewed plan SHA `017e07a7...e5326c86f` (`Saved/Logs/PussStage.log:3415`).
- **Measured / terminal stop:** opening APPLY `P75CHAN-20261010-033246` wrote its backup and durable `status="prepared"` record, spawned the assembly/lights/drive-by path, then failed at the first float-section channel access because UE 5.8 exposes no `MovieSceneFloatSection.get_channels`; no `P75_CHANDELIER_APPLY_OK` exists (`Saved/CodexConductor/P75ChandelierStaging_20261009/chandelier_staging_opening_ACTIVE.json:19,691-693`; `Saved/Logs/PussStage.log:3471`). **Declaration-proven:** record creation and actor/light spawning precede the failing track call, while dirty-scope validation and all targeted saves follow it (`Saved/CodexConductor/P75ChandelierStaging_20261009/chandelier_staging.py:681-698`). Therefore the live editor may contain unsaved partial opening-chandelier actors/lights and the current census is deliberately **UNCLEAR**.
- **Declaration-proven:** after that post-mutation/no-APPLY_OK failure, P06 staging, P56 candles, P52 swing, chandelier stills, Ending 101, Job 144 I2/I3, their stills and the P06 dusk still were not run. Fringe 88, StageFront3D/149, 87, 90b, 99/126, 127 and `LS_Nap_BatteryChange` were not run anywhere in Pass 11. No Save All, editor quit/restart, Klara-level save or permanent deletion was issued.

### Pass 11 result table

| item | target | run id | APPLY marker | census | still path | visual verdict |
|---|---|---|---|---|---|---|
| 1 | J129 P02 floor VERIFY-only, then guarded REVERT | source APPLY `J129P02P01-20261010-030518`; REVERT `J129P02P01-20261010-032628` | **Measured:** VERIFY mismatch; `J129_P02_P01_FLOOR_REPLACE_REVERT_OK` | **Measured:** clean after REVERT and after owned PIE ended | `Saved/CodexConductor/ApplyPass_20261010/stills/01_pass11_p02_floor_reverted_f020.png` | **Measured: VISUAL FAIL** for reflections; reverted floor is visible, rejected replacement is absent |
| 2 | Job 111 P01-P06 shadow radii + three-spot p95 gate | none | **Measured:** none; DRY infrastructure failure before tool mutation | **Measured:** clean, PIE off | none | not applied; no before/after performance samples |
| 3a | P75 failed-run adoption/cleanup | `P75CHAN-20261010-033143`; CLEAN `P75CHAN-20261010-033158`; P06 survey `P75CHAN-20261010-033216` | **Measured:** `P75_CHANDELIER_CLEAN_OK`, one opening leftover only | **Measured:** clean in each marker | none | cleanup only; not a show-look acceptance |
| 3b | P75 opening + P06 staging | opening DRY `P75CHAN-20261010-033229`; opening APPLY `P75CHAN-20261010-033246` | **Measured:** none; APPLY failed after mutation at missing `get_channels` | **UNCLEAR:** terminal rule prohibited a post-failure call | none | **Declaration-proven: VISUAL NOT CAPTURED**; P06 staging not run |
| 3c | P56 candles then P52 swing | - | **Declaration-proven:** not run after P75 terminal stop | not re-probed | none | not run |
| 4 | Ending 101 | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 5 | Job 144 I2 then I3 | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 6 | P06 dusk still | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |

### Pass 11 files, saves and recovery boundary

- **Measured:** the P02 REVERT saved only `Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap`; its safety backup is `Backups/PreJ129P02P01FloorRevert-J129P02P01-20261010-032628/`, and the failed source record was archived with suffix `.reverted-J129P02P01-20261010-032628` (`Saved/Logs/PussStage.log:2947`).
- **Measured:** P75 CLEAN saved the vertical-slice map after removing one failed-run opening leftover and created `Backups/PreP75ChandelierOpeningcleanup-P75CHAN-20261010-033158/` plus its cleanup record (`Saved/Logs/PussStage.log:3367`).
- **Measured:** the failed P75 APPLY created `Backups/PreP75ChandelierOpening-P75CHAN-20261010-033246/` and the live `chandelier_staging_opening_ACTIVE.json` prepared record. **Declaration-proven:** the failure occurs before `_save_named(packages)`, so no authoring package from that APPLY can be claimed saved (`Saved/CodexConductor/P75ChandelierStaging_20261009/chandelier_staging.py:692-699`).
- **Measured:** Pass 11 added the J129 VERIFY report, archived REVERT record and backup, two PassageStills manifests/runs, two copied P02 stills, P75 adoption/cleanup/DRY evidence and the prepared P75 record. J129, P75 and PassageStills args were restored to their pre-pass DRY contents. The shadow request was restored byte-for-byte after the pre-mutation transport diagnosis. No live tool source was patched.
- **Inferred / recovery guidance:** use the prescribed Don't-Save editor restart to discard the unsaved partial opening chandelier assembly/lights. Preserve the prepared record and both P75 backups. Repair the UE 5.8 float-channel lookup offline, run the positive/negative harness, then start a fresh clean live pass; do not CLEAN or delete the new partial actors by hand.

### Pass 11 terminal STOP reason

**Measured:** P75 opening APPLY `P75CHAN-20261010-033246` crossed its mutation boundary after writing a prepared record and spawning owned actors/lights, then failed on missing UE 5.8 `MovieSceneFloatSection.get_channels` before any targeted save and without `P75_CHANDELIER_APPLY_OK`. Per the Pass-11 rule, no subsequent Unreal/MCP call was issued; this job did not quit or restart the editor.

## Pass 12

### Outcome and terminal boundary

- **Measured:** Pass 12 opened after the conductor's Don't-Save restart with PIE/SIE off and zero dirty content/map packages (`Saved/Logs/PussStage.log:2841,2857`). The stale Pass-11 P75 ACTIVE record had already been retired by the conductor; Pass 12 did not delete it.
- **Measured:** Job 111 DRY `SRR-20261010-034009` completed with 381 shadow casters, 310 raise-only candidates, zero Sequencer-keyed radius changes and 362 report-only fog flags (`Saved/Logs/PussStage.log:2872`; `Saved/CodexConductor/shadow_radius_reach_report_DRY_SRR-20261010-034009.json:54,107-110`).
- **Measured:** inside a PIE started and ended by this pass, three 20-second before samples at Passage 1/3/6 +10 s measured p95 frame times of 40.67, 42.43 and 40.55 ms respectively (`Saved/Logs/PussStage.log:3027-3028,3054-3055,3094-3095`). The owned PIE ended with a clean census and PIE off (`Saved/Logs/PussStage.log:3140`).
- **Measured:** Job 111 APPLY `SRR-20261010-034334` refused before its own mutation because loading its backup helper executed `lighting_looks_apply.py`, whose unrelated active-revert-record guard raised `ACTIVE_REVERT_RECORD_EXISTS`. Its marker says `saved=0|NOTHING SAVED`, and the independent post-refusal census was clean with PIE off (`Saved/Logs/PussStage.log:3153,3182`). **Declaration-proven:** no after sample or auto-REVERT decision exists because no radius change was applied.
- **Measured:** Job 144 I2 inventory DRY `J144-20261010-034352` was read-only/clean and found 7,030 actors plus two existing card bindings, `Sleight Hangar Shadow Card` and `Sleight Mouth Shadow Card` (`Saved/Logs/PussStage.log:3194`; `Saved/CodexConductor/Job144InteractionHangar_20261010/job144_dry_I2_J144-20261010-034352.json:83791-83792`). After review, the approved source was limited to the Hangar card and the hide set excluded walls, floors, roof/lattice, roots, cameras, curtains and shadow rigs.
- **Measured:** the reviewed I2 DRY `J144-20261010-034524` then refused before mutation on the existing visibility track for `S2 Ghost Light` / `PointLight_75`; the independent census remained clean with PIE off (`Saved/Logs/PussStage.log:3206,3232`). **Declaration-proven:** I2 was not applied and I3 was skipped because the requested I3 setup reuses I2's gobo/puppet result. No Job-144 still was taken.
- **Measured:** StageFront3D MATERIAL DRY `SF3DI-20261010-034553` found the exact five expected texture parameters on existing parent `/Game/Scenes/Props/Chandelier/M_AgedMaskedMetal_CreateOnly`, selected Dusty inputs for `arch`, made no mutation and reported `dirty=0` (`Saved/Logs/PussStage.log:3244-3246`).
- **Measured / terminal stop:** `arch` MATERIAL run `SF3DI-20261010-034601` created `MI_StageFront_Arch`, assigned it to `SM_StageFront_Arch`, and saved those two targets, then failed its post-save clean-census assertion with `DIRTY_AFTER_SAVE`; no `STAGEFRONT3D_MATERIAL_OK` exists (`Saved/Logs/PussStage.log:3258,3278`; save/control-flow boundary `Saved/CodexConductor/StageFront3D_20261010/stage_front_3d_import.py:296-320`). The two asset timestamps are 03:46:03 local, but the durable record remains `state="imported"`, `materials={}`, with pending run `SF3DI-20261010-034601` (`Saved/CodexConductor/StageFront3D_20261010/stage_front_3d_import_record.json:648-656`). Therefore saved material state and the live dirty census are **UNCLEAR** and require the conductor's prescribed Don't-Save recovery/reconciliation.
- **Declaration-proven:** after the StageFront3D post-mutation/no-OK failure, the remaining wall/gilt/crest/column/cat MATERIAL calls, PLACE DRY/APPLY/VERIFY, Iron3, opening-wide still, P75 ADOPT_OR_CLEAN/staging, P56 candles, P52 swing, chandelier stills, Ending 101 and the P06 dusk still were not run. Fringe, P02 floor 152, 87, 90b, 99/126, 127 and `LS_Nap_BatteryChange` were not run anywhere in Pass 12. No Save All, editor quit/restart, Klara-level save or permanent deletion was issued.

### Pass 12 result table

| item | target | run id | APPLY marker | census | still path | visual verdict |
|---|---|---|---|---|---|---|
| 1 | Job 111 P01-P06 shadow radii plus three-spot p95 gate | DRY `SRR-20261010-034009`; APPLY refusal `SRR-20261010-034334`; before probes `FT-20261010-034112`, `FT-20261010-034153`, `FT-20261010-034239` | **Measured:** none; APPLY refused before mutation with `saved=0|NOTHING SAVED` | **Measured:** clean after refusal, PIE off | none | not applied; before p95 only, so no performance verdict or visual acceptance |
| 2a | Job 144 I2 back-wall interaction | inventory DRY `J144-20261010-034352`; reviewed DRY `J144-20261010-034524` | **Measured:** none; reviewed DRY failed on existing visibility-track conflict | **Measured:** clean, PIE off after failure | none | **Declaration-proven: VISUAL NOT CAPTURED** |
| 2b | Job 144 I3 reusing I2 gobo/puppet | - | **Declaration-proven:** not run after dependent I2 DRY failure | not re-probed | none | not run |
| 3a | StageFront3D MATERIAL, `arch` using Dusty maps and existing aged-metal parent | DRY `SF3DI-20261010-034553`; MATERIAL `SF3DI-20261010-034601` | **Measured:** none; MATERIAL failed after target saves at `DIRTY_AFTER_SAVE` | **UNCLEAR:** terminal rule prohibited a post-failure Unreal call | none | **Declaration-proven: VISUAL NOT CAPTURED** |
| 3b | StageFront3D wall/gilt/crest/column/cat, PLACE/VERIFY, Iron3 and opening wide | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 4 | P75 ADOPT_OR_CLEAN, opening/P06 staging, P56 candles, P52 swing | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 5 | Ending 101 | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 6 | P06 dusk still | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |

### Pass 12 files, saves and recovery boundary

- **Measured:** evidence written before the stop includes the Job-111 DRY JSON/CSV, three frame-time probe JSONs, the Job-144 I2 inventory DRY report, and the StageFront3D `arch` safety backup at `Backups/PreStageFront3DMaterial-SF3DI-20261010-034601/` (`Saved/CodexConductor/StageFront3D_20261010/stage_front_3d_import_record.json:649-653`).
- **Measured:** `Content/Scenes/Props/StageFront3D/Materials/Instances/MI_StageFront_Arch.uasset` and `Content/Scenes/Props/StageFront3D/Meshes/SM_StageFront_Arch.uasset` both received 03:46:03 local filesystem timestamps. **Declaration-proven:** the tool saved exactly those target paths before checking the whole-editor census (`Saved/CodexConductor/StageFront3D_20261010/stage_front_3d_import.py:290-313`), but its record-commit and success marker occur later (`:314-320`) and were not reached.
- **Measured:** Job-111, Job-144, StageFront3D, PIE-goto and frame-probe args were restored to their pre-pass DRY/default forms by filesystem edit. Pass 12 added `Saved/CodexConductor/job153_shadow_radius_request.json` solely as the current guarded MCP envelope for the shipped legacy Job-111 request shape; no live tool source was patched.
- **Inferred / recovery guidance:** perform the prescribed Don't-Save editor restart before another live call, preserve the StageFront backup and pending record, then reconcile whether the saved Arch MI/mesh should be adopted or reverted. Diagnose which package remained dirty after the two target saves; do not broaden the save to Save All.

### Pass 12 terminal STOP reason

**Measured:** StageFront3D MATERIAL `SF3DI-20261010-034601` mutated and saved the Arch MI/mesh, then failed the whole-editor clean-census gate without `STAGEFRONT3D_MATERIAL_OK`. Per the Pass-12 rule, no further Unreal/MCP call was issued; this job did not quit or restart the editor.

## Pass 13

### Outcome and terminal boundary

- **Measured:** after the freshly launched editor settled, the opening census was clean with PIE off: `content=[]`, `maps=[]`, `pie=false` (`Saved/Logs/PussStage.log:2856`). The Saved-module cache was purged before the floor DRY and APPLY (`Saved/Logs/PussStage.log:2862,2878`).
- **Measured:** P02 floor DRY `J129P02P01-20261010-044458` completed with four target actors, four route segments, zero bindings/blockers/unclear rows and plan SHA `681e5ff2...d5414`; its before/after censuses were clean (`Saved/Logs/PussStage.log:2871`; `Saved/CodexConductor/J119S2P01FloorReplace_20261009/j129_p02_dry_J129P02P01-20261010-044458.json:1-13`). **Declaration-proven:** the plan uses the live Passage 02 root for composition and requires the inferred-texel-density acknowledgement (`Saved/CodexConductor/J119S2P01FloorReplace_20261009/j129_p02_dry_J129P02P01-20261010-044458.json:21-39,638-641`).
- **Measured / terminal stop:** APPLY `J129P02P01-20261010-044517` duplicated, labelled and transformed the first replacement actor, recorded it, then failed its first in-memory duplicate snapshot because `_snapshot(..., component_world=True)` rejected the expected `-43.572498...` yaw as `UNSUPPORTED_SOURCE_COMPONENT_ROTATION`; no `J129_P02_P01_FLOOR_REPLACE_APPLY_OK` exists (`Saved/Logs/PussStage.log:2884-2896`; mutation/read-back boundary `Saved/CodexConductor/J119S2P01FloorReplace_20261009/j119_s2_p01_floor_replace.py:883-904`). The durable record is `state="applying"`, `applied=false`, contains one owned actor and no shifted old-floor components (`Saved/CodexConductor/J119S2P01FloorReplace_20261009/j129_p02_p01_floor_replace_record.json:2-34,669-671`).
- **Declaration-proven:** the failure occurred before the old P02 components are shifted, before Passage 02 materialization, and before the targeted level save (`Saved/CodexConductor/J119S2P01FloorReplace_20261009/j119_s2_p01_floor_replace.py:908-925,937-966`). Therefore no authoring package was saved by Pass 13, but the live editor contains one uncommitted replacement actor and its current dirty census is **UNCLEAR** because the stop rule forbids another editor call.
- **Declaration-proven:** because this was a mutation without APPLY_OK, Pass 13 stopped immediately. Shadow radii, StageFront3D, the P75/P56/P52 chandelier chain, Ending 101 and the P06 dusk still were not run. No PIE was started, so none was ended. Fringe, Job 144, 87, 90b, 99/126, 127 and `LS_Nap_BatteryChange` were not run. No Save All, editor quit/restart, Klara-level save or permanent deletion was issued.

### Pass 13 result table

| item | target | run id | APPLY marker | census | still path | visual verdict |
|---|---|---|---|---|---|---|
| 1 | J119/J129 P02 floor = P01 floor | DRY `J129P02P01-20261010-044458`; APPLY `J129P02P01-20261010-044517` | **Measured:** none; failed after the first replacement actor was created and recorded | **Measured:** clean after DRY; **UNCLEAR after APPLY failure** because no post-mutation editor call was permitted | none | **Declaration-proven: VISUAL NOT CAPTURED;** owned PIE was never started |
| 2 | Job 111 P01-P06 shadow radii + performance gate | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 3 | StageFront3D wall/gilt/crest/column/cat MATERIAL, PLACE/VERIFY, Iron3 and opening wide | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 4 | P75 ADOPT_OR_CLEAN, opening/P06 staging, P56 candles, P52 swing | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 5 | Ending 101 | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 6 | P06 dusk still | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |

### Pass 13 files, saves and recovery boundary

- **Measured:** evidence created by the stopped floor item is `Saved/CodexConductor/J119S2P01FloorReplace_20261009/j129_p02_dry_J129P02P01-20261010-044458.json`, `Saved/CodexConductor/J119S2P01FloorReplace_20261009/j129_p02_p01_floor_replace_record.json`, `Backups/PreJ129P02P01Floor-J129P02P01-20261010-044517/` and the appended `Saved/Logs/PussStage.log`.
- **Measured:** the floor args were restored by filesystem edit to their pre-pass DRY form: blank plan digest and both acknowledgements false (`Saved/CodexConductor/J119S2P01FloorReplace_20261009/j119_s2_p01_floor_replace_args.json:1-10`).
- **Declaration-proven:** Pass 13 saved no Unreal package and captured no still. The conductor should preserve the record and backup and perform the prescribed Don't-Save recovery before another live call; this pass intentionally did not quit or restart the editor.

### Pass 13 terminal STOP reason

**Measured:** P02 floor APPLY `J129P02P01-20261010-044517` created one replacement actor and then failed before its in-memory Z/footprint verification completed, with no APPLY_OK. Per the explicit Pass-13 rule, the pass stopped immediately and made no later Unreal/MCP/PIE call (`Saved/Logs/PussStage.log:2884-2896`).

## Pass 14

### Outcome and terminal boundary

- **Declaration-proven:** Pass 12's Job-111 refusal is not repairable by changing the shadow args from its DRY output. The refused APPLY already carried the exact confirm string and `expected_changes=310` (`Saved/CodexConductor/shadow_radius_reach_report_APPLY_SRR-20261010-034334.json:4-6`). The shadow tool instead imports `lighting_looks_apply.py` solely to obtain its backup helper (`Saved/CodexConductor/shadow_radius_reach.py:283-288`); that imported module unconditionally runs `main()` when Unreal is present (`Saved/CodexConductor/lighting_looks_apply.py:2259-2267`), and a live lighting-looks revert record still exists (`Saved/CodexConductor/lighting_looks_revert_record.json:1-9`). Therefore no args-only correction can bypass `ACTIVE_REVERT_RECORD_EXISTS` without changing tool code or the unrelated record. Pass 14 did not re-run Job 111, did not patch tool source, and did not take an after-performance sample.
- **Measured:** after the conductor's clean Don't-Save restart, the live log reported `content=[]`, `maps=[]`, `pie=false` (`Saved/Logs/PussStage.log:2830-2841`). Before StageFront3D MATERIAL could begin, the editor logged a D3D12 device reset / removal while rendering frame 3150 (`Saved/Logs/PussStage.log:2847-2889`). The process retained a listening socket but stopped servicing MCP initialization; a second read-only census request timed out and produced no Unreal log marker. No mutation tool had started.
- **Declaration-proven:** because the existing editor could no longer service the guarded MCP route and this job is forbidden to quit or restart it, StageFront3D wall/gilt/crest/column/cat MATERIAL, PLACE DRY/APPLY/VERIFY, Iron3, every still, the P75/P56/P52 chandelier chain, Ending 101 and the P06 dusk still were not run. This was an external pre-mutation transport/render failure, not a mutation-without-APPLY_OK stop.
- **Declaration-proven:** the P02 floor (job 156), fringe, Job 144, 87, 90b, 99/126, 127 and `LS_Nap_BatteryChange` were not run. No Save All, package save, editor quit/restart, permanent deletion or Klara-level save was issued. This pass started no PIE and therefore ended no PIE.

### Pass 14 result table

| item | target | run id | APPLY marker | census | still path | visual verdict |
|---|---|---|---|---|---|---|
| 1 | Job 111 P01-P06 shadow radii plus three-spot p95 gate | prior DRY `SRR-20261010-034009`; prior refusal `SRR-20261010-034334` | **Declaration-proven:** none; prior refusal is caused by helper import side effects, while its args already contain the exact confirm and 310 expected changes | **Measured:** clean before the editor GPU failure | none | not applied; no after sample, perf verdict or visual acceptance |
| 2 | StageFront3D wall/gilt/crest/column/cat MATERIAL, PLACE/VERIFY, Iron3 and opening wide | - | **Declaration-proven:** not run; editor became unavailable before the first MATERIAL call | **Measured:** last live census was clean; post-GPU-failure census unavailable because MCP stopped responding | none | **Declaration-proven: VISUAL NOT CAPTURED** |
| 3 | P75 ADOPT_OR_CLEAN, opening/P06 staging, P56 candles, P52 swing | - | **Declaration-proven:** not run | not re-probed | none | not run |
| 4 | Ending 101 | - | **Declaration-proven:** not run | not re-probed | none | not run |
| 5 | P06 dusk | - | **Declaration-proven:** no mutation requested; still not run | not re-probed | none | **Declaration-proven: VISUAL NOT CAPTURED** |

### Pass 14 files, saves and recovery boundary

- **Measured:** Pass 14 changed only this report. Shadow, StageFront3D, P75/P56/P52, Ending and PassageStills args remained in their pre-pass forms. No Unreal package or still was written.
- **Inferred / recovery guidance:** the conductor must recover or restart the editor under its own authority before another live pass. After recovery, require a fresh clean census and PIE-off read-back before resuming at StageFront3D MATERIAL `wall`; preserve the already saved Arch MI/mesh and do not re-run Arch MATERIAL.

### Pass 14 terminal condition

**Measured:** no mutation boundary was crossed. Pass 14 could not continue after the editor's D3D12 device removal left the guarded MCP listener non-responsive (`Saved/Logs/PussStage.log:2847-2889`). In accordance with the no-quit/no-restart rule, this job did not attempt editor recovery.

## Slot 10 Oct after reboot

### Outcome and terminal boundary

- **Measured:** the freshly rebooted editor opened with PIE off and a clean census, `content=[]`, `maps=[]`; the sky auto-hide had already reported an unchanged census (`Saved/Logs/PussStage.log:2842`; `Saved/Logs/PussStage.log:2813`). Byte-offset scans after every executed step found no new DXGI device-loss or D3D12 fatal signature through the terminal shadow-radius failure.
- **Measured:** P02 LEAN failed in DRY before entering the tool because its runner could not import the same-folder `_fx_authoring_common` module (`Saved/Logs/PussStage.log:2866`). **Declaration-proven:** this is a runner-path failure, not a missing UE 5.8 API name, so the permitted pre-mutation API-name patch exception did not apply (`Docs/Conductor/codex_briefs/p135_live_pass3.md:5-8`). The independent post-failure census remained clean with PIE off (`Saved/Logs/PussStage.log:2872`). No P02 lighting field, car radius, performance sample or still was changed/captured by this slot.
- **Measured:** the job-159 shadow-radius offline harness passed 28/28, including the negative control that the unrelated lighting tool is never imported (`Saved/CodexConductor/test_shadow_radius_reach_offline.py:1-114`). Fresh DRY `SRR-20261010-105400` found 381 shadow casters, 310 raise-only changes, zero Sequencer-keyed radius edits and 362 report-only fog flags (`Saved/Logs/PussStage.log:2897`; `Saved/CodexConductor/shadow_radius_reach_report_DRY_SRR-20261010-105400.json:54-110`).
- **Measured / terminal stop:** APPLY `SRR-20261010-105417` created the verified Show/map backup and a durable `status="prepared"` record containing 310 targets (`Saved/CodexConductor/shadow_radius_reach_record.json:42-46`). It then changed the live values and materialized affected passages before the narrow-save gate refused on out-of-scope dirty streamed maps; the failure marker reports `saved=0|NOTHING SAVED`, lists the dirty Show plus the vertical-slice, Japanese Alley, Animals and Children maps, and no `SHADOWRADIUSREACH_APPLY_OK` exists (`Saved/Logs/PussStage.log:2919`). **Declaration-proven:** mutation begins at `apply_values`, the failed save gate is later, and the success marker is later still (`Saved/CodexConductor/shadow_radius_reach.py:687-721`). The editor therefore contains unsaved in-memory mutations with a prepared record, so no further Unreal/MCP/PIE call was issued.
- **Declaration-proven:** items 3-9 were not run after the mutation-without-APPLY_OK stop required by the brief (`Docs/Conductor/codex_briefs/p135_live_pass3.md:7-8`). No PIE was started, so none was ended. No Save All, editor quit/restart, Klara-level save or permanent deletion was issued.

### Slot result table

| item | target | run id | APPLY marker | census | still path | visual verdict |
|---|---|---|---|---|---|---|
| 1 | P02 LEAN lighting, car 4600 cm, three-spot p95 and stills | none | **Measured:** none; DRY runner import failed before mutation (`Saved/Logs/PussStage.log:2866`) | **Measured:** clean, PIE off after refusal (`Saved/Logs/PussStage.log:2872`) | none | **Declaration-proven: VISUAL NOT CAPTURED;** APPLY/perf/stills were not reached |
| 2 | Job 159 shadow radii plus performance auto-revert | DRY `SRR-20261010-105400`; APPLY `SRR-20261010-105417` | **Measured:** none; APPLY mutated in memory, then stopped before save with `saved=0|NOTHING SAVED` (`Saved/Logs/PussStage.log:2919`) | **Measured:** dirty failure census contains the Show and four maps; no later census was permitted | none | **Declaration-proven: VISUAL NOT CAPTURED;** no after-p95 sample or auto-REVERT decision exists |
| 3 | StageFront3D wall/gilt/crest/column/cat MATERIAL, PLACE/VERIFY, Iron3; un-hold/re-plan/apply Job 87; opening stills | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 4 | P75 chandelier chain | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 5 | Ending 101 | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 6 | Job 156 P02 floor | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 7 | Job 144 I2 then I3 back wall, `SAFE_SKIP` | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 8 | Job 159 Fringe | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | not run |
| 9 | P06 dusk, S2 outside and P05 wings stills | - | **Declaration-proven:** not run after terminal stop | not re-probed | none | **Declaration-proven: VISUAL NOT CAPTURED** |

### Files, backup and recovery boundary

- **Measured:** the shadow APPLY created `Backups/PreShadowRadiusReach-SRR-20261010-105417/`, `Saved/CodexConductor/shadow_radius_reach_record.json`, and `Saved/CodexConductor/shadow_radius_reach_report_APPLY_SRR-20261010-105417.json`. The backup record covers the Show and vertical-slice map and carries matching SHA-256 evidence (`Saved/CodexConductor/shadow_radius_reach_record.json:4-42`).
- **Measured:** `Saved/CodexConductor/shadow_radius_reach_args.json` was restored by filesystem edit to its original DRY form after the stop. This report was appended. No Unreal authoring package was saved by this slot (`Saved/Logs/PussStage.log:2919`).
- **Inferred / recovery guidance:** preserve the prepared record and backup. The conductor should use the prescribed Don't-Save recovery before any later live call; do not attempt the tool's guarded REVERT against unsaved state, and do not save the currently dirty streamed levels.

### Terminal STOP reason

**Measured:** shadow-radius APPLY `SRR-20261010-105417` crossed its mutation boundary, then stopped at the narrow-save guard without `SHADOWRADIUSREACH_APPLY_OK`. In accordance with the user's explicit stop rule, this slot made no later Unreal/MCP/PIE call and did not quit or restart the editor.
