# Live queue report — 9 October 2026

**measured:** Job 102 stopped at the first queue item. **declaration-proven:** this is the required response to a failed tool (`Docs/Conductor/codex_briefs/p102_live_queue_evening.md:16`). **measured:** no later queue item was run.

| item | run id | DRY verdict | APPLY marker | census after | stills | notes |
| --- | --- | --- | --- | --- | --- | --- |
| 1. S3 visual diagnosis (E1, read-only) | **measured:** `2026.10.09-22.34.44` (UTC log timestamp); **declaration-proven:** the tool has no separate run-id field | **measured:** **FAILED / STOP** — `S3_VISUAL_DIAG_FAILED` | **declaration-proven:** N/A; fixes were forbidden | **measured:** **NOT PRODUCED** — failure occurred before the script's post-run census and JSON write | **measured:** none | **measured:** UE reported `AttributeError: 'InstancedStaticMeshComponent' object has no attribute 'get_static_mesh'` at `Saved/CodexConductor/s3_visual_diag_20261009.py:675` (`Saved/Logs/PussStage.log:2846`). **declaration-proven:** the script declares itself read-only and says its only intended write is the requested JSON report (`Saved/CodexConductor/s3_visual_diag_20261009.py:1-4`). **measured:** that JSON was not created, so the requested per-figure diagnosis was not available. |

## First STOP reason

- **measured:** the first tool failed while enumerating the S3 ground candidates because it called the unavailable `get_static_mesh()` accessor on an `InstancedStaticMeshComponent` (`Saved/CodexConductor/s3_visual_diag_20261009.py:675`; `Saved/Logs/PussStage.log:2846`).
- **declaration-proven:** Job 102 says any `FAILED`, `STOPPED`, or unexpected census must stop the queue, and says not to retry a mutation blind (`Docs/Conductor/codex_briefs/p102_live_queue_evening.md:16`). It also says the S3 item is diagnosis-only with no fixes (`Docs/Conductor/codex_briefs/p102_live_queue_evening.md:26-34`). Therefore the tool was not patched or retried, and items 2 onward were not run.
- **measured:** the required module-cache purge ran first and removed zero modules (`Saved/Logs/PussStage.log:2837`).
- **UNCLEAR:** no post-run dirty-package census was reached. The script defines that census after the failed section (`Saved/CodexConductor/s3_visual_diag_20261009.py:718`), so clean editor state after this call is not claimed.

## Result boundaries

- **declaration-proven:** no APPLY step exists for item 1 and Gary prohibited fixes in this item (`Docs/Conductor/codex_briefs/p102_live_queue_evening.md:34`).
- **measured:** no `S3_VISUAL_DIAG_SUCCESS` marker and no `S3_VISUAL_DIAG_20261009.json` output were produced.
- **inferred:** because execution failed before any report or explicit post-run census, no per-figure material, translucency, missing-shroud, or feet-depth conclusions can safely be reported from this run.
- **measured:** no stills were taken and no later queue request was executed.

## Files changed by Job 102

- **measured:** `Docs/Conductor/LIVE_QUEUE_REPORT_2026-10-09.md` — this report.
- **measured:** `Saved/Logs/PussStage.log` — appended automatically by the open editor for the purge and failed diagnostic call.

**declaration-proven:** the diagnostic script contains no save operation and the queue prohibited an APPLY/fix for this item. **measured:** this session issued no asset-save, level-save, commit, PIE, editor-quit, or editor-restart command.

---

## Resume attempt from item 1 (9 October 2026, 22:51 UTC)

**measured:** the conductor-provided API-name correction compiled successfully with `python -m py_compile` before the live retry. **declaration-proven:** the corrected call is `component.get_editor_property("static_mesh")` (`Saved/CodexConductor/s3_visual_diag_20261009.py:675`), replacing the unavailable `component.get_static_mesh()` call captured by the earlier failure (`Saved/Logs/PussStage.log:2846`). The exact one-line correction was:

```diff
-            mesh_path = path_of(component.get_static_mesh())
+            mesh_path = path_of(component.get_editor_property("static_mesh"))
```

| item | run id | DRY verdict | APPLY marker | census after | stills | notes |
| --- | --- | --- | --- | --- | --- | --- |
| 1. S3 visual diagnosis (E1, read-only), resumed | **measured:** no Unreal run id was minted; transport attempt began `2026.10.09-22.51.11` UTC | **measured:** **NOT RUN / STOP** - cache purge could not reach Unreal | **declaration-proven:** N/A; this item permits no fixes | **measured:** **NOT AVAILABLE** - Unreal executed neither the purge nor the diagnostic | **measured:** none | **measured:** the purge request failed before Unreal execution with `ConnectionRefusedError [WinError 10061]` at `127.0.0.1:8010`. The live log shows the editor shut down at 22:48:34 UTC (`Saved/Logs/PussStage.log:2935`), stopped the 8010 listener (`Saved/Logs/PussStage.log:2953`), and closed the log (`Saved/Logs/PussStage.log:2975`). A process/listener census at the retry found zero `UnrealEditor` processes and zero listeners on 8010. **declaration-proven:** the transport targets PussStage on 8010 (`Saved/CodexMocap/mcp_request.py:8-10`). |

### First STOP reason for the resume

- **measured:** item 1 could not begin because the PussStage editor and its guarded MCP listener were no longer running. The module cache was therefore not purged in Unreal, and `S3_VISUAL_DIAG_20261009.py` was not executed.
- **declaration-proven:** the live queue requires the open editor transport and says any failed/unexpected run stops the queue (`Docs/Conductor/codex_briefs/p102_live_queue_evening.md:10-16`). The user also prohibited quitting or restarting the editor. Therefore this session did not restart it and did not run items 2 onward.
- **UNCLEAR:** current editor dirty-package state, PIE/SIE state, per-figure S3 diagnosis, and feet depth cannot be read while the editor is closed. No claim is made for any of them from this resume attempt.

### Files changed by the resume attempt

- **measured:** `Docs/Conductor/LIVE_QUEUE_REPORT_2026-10-09.md` - appended this resume result.
- **measured:** `Saved/CodexConductor/__pycache__/s3_visual_diag_20261009.cpython-314.pyc` - refreshed by the successful syntax compilation.
- **declaration-proven:** `Saved/CodexConductor/s3_visual_diag_20261009.py` already contained the conductor's API-name correction when this resume began; this session did not modify it (`Saved/CodexConductor/s3_visual_diag_20261009.py:675`).

**measured:** this resume attempt issued no asset save, level save, Save All, PIE start/stop, editor quit/restart, mutation, or commit command. No later live-queue item ran.

---

## Resume 2 from item 1 (9 October 2026, 23:40-23:47 UTC)

| item | run id | DRY verdict | APPLY marker | census after | stills | notes |
| --- | --- | --- | --- | --- | --- | --- |
| 1. S3 visual diagnosis (E1, read-only) | **measured:** no tool run-id field; success logged at `2026.10.09-23.42.35` UTC | **measured:** `S3_VISUAL_DIAG_SUCCESS`; the two intervening failures were repaired only by the permitted read-only API-name substitutions described below | **declaration-proven:** N/A; fixes were forbidden | **measured:** content `[]`, maps `[]`; actor count/hash identical before and after; marker says `dirty_identical=1|actor_identical=1` (`Saved/Logs/PussStage.log:2950`; `Saved/CodexConductor/S3_VISUAL_DIAG_20261009.json:2801-2828`) | **measured:** none | **measured:** 24 live actors, six templates and six hessian MIs were audited. **UNCLEAR:** the output did not actually recover foot samples, a shading-model field, or a translucent-figure identity, so those requested conclusions are not claimed. |
| 2. P02 Top-wing facing DRY (E9/job 91) | **measured:** `RZSW-20261009-194606` | **measured:** PASS, 23 rows, no refusals, state `cfeb328d` (`Saved/Logs/PussStage.log:2984`; `Saved/CodexFlatV3/rzswap/rzswap_dry_P02_RZSW-20261009-194606.json:8256-8259`) | **declaration-proven:** N/A; the brief explicitly prohibited APPLY | **measured:** clean before and after; the DRY implementation refuses a non-clean start and refuses if DRY changes the census (`Saved/CodexFlatV3/rzswap/rzswap.py:548-588`) | **measured:** none | **measured:** every Top is `AUTO_BY_ROLE`, `flip_image_horizontally=false`, local yaw 180 degrees, and has `front_s - back_s` about +5.474 cm. Every L/R panel has the opposite sign. This supports wrong physical face as the leading diagnosis; it is not rendered acceptance. |
| 3. P02 lighting = P01, first DRY (E8) | **measured:** `20261009-194749` | **measured:** **STOPPED** - `ATMOS_TARGET_BEAMS_MISSING|need=4|have=0` | **measured:** NOT RUN | **measured:** content `[]`, maps `[]` at stop (`Saved/CodexFlatV3/p02lighting/passage_lighting_report_DRY_STOPPED_20261009-194749.json:58-66`; `Saved/Logs/PussStage.log:2999`) | **measured:** none | **declaration-proven:** the tool requires at least as many target P02 beam actors as the four source P01 beams (`Saved/CodexFlatV3/p02lighting/passage_lighting_as_source.py:487-510`). The P02 practicals step and every later queue item were not run. |

### Item 1: S3 per-figure material diagnosis

**Measured path abbreviations:** shroud MIs are under `/Game/Metahuman/ShoreCast_20260910/ShroudHessian/Materials/`; hessian textures are under the sibling `Textures/` folder; hessian shorts MIs are under `/Game/Metahuman/ShoreCast_20260910/OutfitHessian/`. The six Blueprint-template blocks are recorded at `Saved/CodexConductor/S3_VISUAL_DIAG_20261009.json:2377-2802`.

| figure | shroud slot | shroud textures / load state | T-shirt slot | underwear/shorts slot |
| --- | --- | --- | --- | --- |
| Shore01_M56 | **measured:** `MI_Shroud_Hessian_03` | **measured:** `T_Shroud_Stain_03_{Mask,Tint}` + `T_Shroud_Weave_{BC,N}`; all audited texture assets loaded | **measured:** `MI_WI_DefaultGarment_M_DG_bodyShapeA_Shirt` | **measured:** live actors resolve `MI_Shore01_M56_Shorts_Hessian_v1` |
| Shore02_F52 | **measured:** `MI_Shroud_Hessian_05` | **measured:** `T_Shroud_Stain_05_{Mask,Tint}` + shared weave BC/N; loaded | **measured:** `MI_WI_DefaultGarment_M_DG_bodyShapeB_Shirt` | **measured:** `MI_Shore02_F52_Shorts_Hessian_v1` |
| Shore03_M59 | **measured:** `MI_Shroud_Hessian_06` | **measured:** `T_Shroud_Stain_06_{Mask,Tint}` + shared weave BC/N; loaded | **measured:** `MI_WI_DefaultGarment_M_DG_bodyShapeA_Shirt` | **measured:** `MI_Shore03_M59_Shorts_Hessian_v1` |
| Shore04_F55 | **measured:** `MI_Shroud_Hessian_04` | **measured:** `T_Shroud_Stain_04_{Mask,Tint}` + shared weave BC/N; loaded | **measured:** `MI_WI_DefaultGarment_M_DG_bodyShapeB_Shirt` | **measured:** `MI_Shore04_F55_Shorts_Hessian_v1` |
| Shore05_M53 | **measured:** `MI_Sackcloth_OldGrey_Cloth_v2`, not a ShroudHessian MI | **UNCLEAR:** this run did not inventory that older MI's texture parameters | **measured:** `MI_WI_DefaultGarment_M_DG_bodyShapeA_Shirt` | **measured:** `MI_Shore05_M53_Shorts_Hessian_v1` |
| Shore06_F25 | **measured:** `MI_Shroud_Hessian_07` | **measured:** `T_Shroud_Stain_07_{Mask,Tint}` + shared weave BC/N; loaded | **measured:** `MI_WI_DefaultGarment_M_DG_bodyShapeB_Shirt` | **measured:** `MI_Shore06_F25_Shorts_Hessian_v1` |

- **Measured:** all audited hessian MIs and all stain/weave texture assets loaded; there were no null texture overrides or missing/unloadable texture assets (`Saved/CodexConductor/S3_VISUAL_DIAG_20261009.json:3530-3534,5256-6340`).
- **UNCLEAR:** the requested shading model is not present in the output. The tool's master-material inventory records expression classes, scalar/vector parameters and textures, but not shading model or blend mode (`Saved/CodexConductor/s3_visual_diag_20261009.py:233-253`). T-shirt and shorts texture parameters were likewise not inventoried, so only their resolved material assignments are proved.
- **Inferred from measured bindings:** black/shiny/untextured appearance is not explained by a missing hessian assignment, missing texture, null texture override, or a logged shader-compile failure. The next diagnostic target would be rendered lighting/exposure and the master graph response; no fix was applied (`Saved/CodexConductor/S3_VISUAL_DIAG_20261009.json:3507-3535`).
- **Measured:** every audited figure actor has a `ShoreHeadCloth` component. Shore05_M53 is the only figure outside the five-figure hessian assignment and retains `MI_Sackcloth_OldGrey_Cloth_v2` (`Saved/CodexConductor/S3_VISUAL_DIAG_20261009.json:3508-3528`). **UNCLEAR:** this does not identify the visually reported no-shroud figure, and the run captured no translucency/blend evidence, so the translucent figure is also unproved.
- **Measured:** Job 40 changed shorts-role slots only; shirt/T-shirt slots deliberately retain their original DefaultGarment materials (`Saved/CodexConductor/S3_VISUAL_DIAG_20261009.json:3543-3552`). This explains why a shirt can still read white even when the shorts child MI changed.
- **UNCLEAR:** no feet-depth number is available. The tool triangulated Ground B (`435760` triangles), but every actor's `foot_samples` array is empty and every `lowest_gap` is null (`Saved/CodexConductor/S3_VISUAL_DIAG_20261009.json:2840-3498`). Therefore the output's empty `sunk_figures` list is not accepted as proof that feet are clear of the dune mesh.

### Permitted read-only API-name repairs

Both one-line changes passed `python -m py_compile` before their retry. No guard was weakened.

```diff
-    transform = component.get_component_transform()
+    transform = component.get_world_transform()
```

```diff
-            world = transform.transform_position(local)
+            world = unreal.MathLibrary.transform_location(transform, local)
```

**Measured:** the failed calls and exact exception sites are in `Saved/Logs/PussStage.log:2890,2921`; the corrected calls are at `Saved/CodexConductor/s3_visual_diag_20261009.py:358,370`.

### Item 2: measured facing

- **Measured:** 23/23 P02 Top panels use `AUTO_BY_ROLE`, `flip=false`, and local yaw 180 degrees. For Wing 001, for example, Top `front_s=256.8367`, `back_s=251.3630`, while both L/R have front below back (`Saved/CodexFlatV3/rzswap/rzswap_dry_P02_RZSW-20261009-194606.json:188-356`). The same sign pattern holds for every row.
- **Inferred from that measurement:** the Top physical face is reversed relative to the corridor-facing L/R convention, matching Gary's report that the Top artwork looks backwards. This does not prove a source-image rotation or UV defect.
- **Measured:** no APPLY, plan generation, asset save, level save or still capture was run for item 2.

### First STOP reason for resume 2

- **Measured:** item 3's P02-lighting DRY stopped before mutation because P01 has four tagged atmosphere beams and P02 has zero, violating `ATMOS_TARGET_BEAMS_MISSING|need=4|have=0`; its stop census was clean (`Saved/CodexFlatV3/p02lighting/passage_lighting_report_DRY_STOPPED_20261009-194749.json:58-66`).
- **Declaration-proven:** the queue requires a full stop on any `FAILED` or `STOPPED`, with no blind retry (`Docs/Conductor/codex_briefs/p102_live_queue_evening.md:16`). Because this is a mutating-capable tool, the user-authorized API-name patch exception does not apply.
- **Measured:** no P02-lighting APPLY, no P02 practicals DRY/APPLY, no jobs 4-5, no added jobs 7-8, and no deprioritised item 6 were run after this stop.

### Files changed or generated by resume 2

- **measured:** `Saved/CodexConductor/s3_visual_diag_20261009.py` - the two one-line read-only API-name corrections above.
- **measured:** `Saved/CodexConductor/__pycache__/s3_visual_diag_20261009.cpython-314.pyc` - refreshed by `py_compile`.
- **measured:** `Saved/CodexConductor/S3_VISUAL_DIAG_20261009.json` - successful read-only diagnostic artifact.
- **measured:** `Saved/CodexFlatV3/rzswap/rzswap_dry_P02_RZSW-20261009-194606.json` and `rzswap_dry_P02_LATEST.json` - item-2 DRY artifacts.
- **measured:** `Saved/CodexFlatV3/p02lighting/P02_LIGHTING_PREVIEW_OFFLINE_2026-10-09.png` - regenerated by the 50/50 offline harness.
- **measured:** `Saved/CodexFlatV3/p02lighting/passage_lighting_report_DRY_STOPPED_20261009-194749.json` - item-3 stop artifact.
- **measured:** `Saved/CodexFlatV3/rzswap/rzswap_args.json` was temporarily set to the item-2 P02 Top DRY and then restored byte-for-byte to its prior P03 DRY contents.
- **measured:** `Saved/Logs/PussStage.log` - appended automatically by the live editor.
- **measured:** `Docs/Conductor/LIVE_QUEUE_REPORT_2026-10-09.md` - appended with this resume.

**Measured:** resume 2 issued no Save All, asset save, level save, PIE start/stop, editor quit/restart, mutation APPLY, or commit command.
