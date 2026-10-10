# Codex job 114 - S3 feet by hand transfer tool (offline)

Date: 2026-10-09  
Scope: `Saved/CodexConductor/S3FeetByHand_20261009/`

## Result and proof boundary

- **measured (offline):** Python compilation passed and the harness passed **21/21 positive + 22/22 negative = 43/43**. Unreal and Blender were not started. Evidence: `Saved/CodexConductor/S3FeetByHand_20261009/s3_feet_harness_report.json:1-25`.
- **declaration-proven:** the exact target gate requires `Shore01_M56 Clam` through `Shore06_F25 Clam` and admits only labels beginning `P40 Shore Variant`; it therefore excludes `S3 Hangar Float Hold: Shore05_M53 Clam`, all `S3 Crowd` actors, and component `/Body` bindings. Evidence: `Saved/CodexConductor/S3FeetByHand_20261009/s3_feet_core.py:12-21,40-55`; `Saved/CodexConductor/S3FeetByHand_20261009/s3_feet_editor.py:109-119`.
- **UNCLEAR:** no Unreal call was made, so current binding ownership, live channel schemas, saved read-back, and visual foot contact remain unmeasured until the conductor runs DRY/SNAPSHOT/CAPTURE/APPLY/REVERT.

## Tool behavior

- **declaration-proven:** DRY/SNAPSHOT/CAPTURE obtain the editor world and asset data directly; they never use the Sequencer editor library, create a sequence player, open the Master, play, or scrub. SNAPSHOT requires a clean editor, records every target actor world transform, the complete binding/channel state, and a non-target actor transform census. Evidence: `Saved/CodexConductor/S3FeetByHand_20261009/s3_feet_editor.py:75-87,256-269,305-386`.
- **declaration-proven:** recursive asset traversal follows plain sub-sequences and cinematic-shot sequences from `/Game/Scenes/LS_Clams`, then resolves exactly one binding per target and records whether it is possessable or spawnable and which sequence owns it. Evidence: `Saved/CodexConductor/S3FeetByHand_20261009/s3_feet_editor.py:189-269`.
- **declaration-proven:** CAPTURE refuses missing/duplicate actors, unrelated actor drift, curve/schema drift, any rotation change over 0.01 degrees, scale change, missing Z movement, or a location delta over 200 cm. X/Y are always reported and default to not applied; `apply_xy=true` must be chosen before CAPTURE. Evidence: `Saved/CodexConductor/S3FeetByHand_20261009/s3_feet_core.py:56-108`; `Saved/CodexConductor/S3FeetByHand_20261009/s3_feet_editor.py:338-386`.
- **declaration-proven:** APPLY offsets every key on every Location channel; an unkeyed Location channel has its default offset and refuses if it has no default. Non-absolute sections refuse. Spawnable initial pose changes go through the object template and are based on SNAPSHOT plus delta, preventing a viewport template edit from being doubled. Evidence: `Saved/CodexConductor/S3FeetByHand_20261009/s3_feet_core.py:110-134`; `Saved/CodexConductor/S3FeetByHand_20261009/s3_feet_editor.py:447-469,487-543`.
- **declaration-proven:** APPLY and REVERT require exact confirm strings, make hashed `Backups/PreS3Feet-<run>` / `PreS3FeetRevert-<run>` copies before mutation, save only the resolved owning sequence asset(s), and read back each key/default/template numerically. No map-save call exists. Evidence: `Saved/CodexConductor/S3FeetByHand_20261009/s3_feet_editor.py:406-421,476-577`.

## Level-save answer

- **inferred from the declared ownership model:** the hand-positioned possessable actor transforms are measurement state, not the persistent fix. They **must not be saved in the level**. APPLY persists the deltas in the owning sequence and intentionally leaves the map dirty; after the saved read-back, undo Gary's hand moves or reload/close the level with **Don't Save**. Saving the map could persist evaluated/manual actor state and is neither required nor performed.
- **declaration-proven:** for a spawnable, its persistent initial transform belongs to its sequence template, so that template is updated through the owning sequence asset; the level is still not saved.

## Conductor run order

1. Keep the Master/Sequencer closed, no sequence playing, no PIE/SIE, and start clean. Leave args at `mode=DRY`; run `s3_feet_request.json`; require `S3_FEET_DRY_OK`.
2. Set `mode=SNAPSHOT`, no confirm; run before Gary edits; require `S3_FEET_SNAPSHOT_OK` and inspect `s3_feet_snapshot.json`.
3. Gary moves only the eight gated figures in the viewport, with no sequence playing and no save.
4. Set `mode=CAPTURE`; choose `apply_xy` now (default false); run and require `S3_FEET_CAPTURE_OK`. Review every reported/applied delta in `s3_feet_capture.json`.
5. Set `mode=APPLY`, `confirm="APPLY S3 FEET"`; run once. Require `S3_FEET_APPLY_OK`, hashed backup, named sequences only, `map_saved=0`, and saved read-back in `s3_feet_readback.json`.
6. For the required reversibility exercise, set `mode=REVERT`, `confirm="REVERT S3 FEET"`; require `S3_FEET_REVERT_OK` and original-value read-back. To retain the correction, stop after step 5 instead.
7. Undo the viewport moves or reload/close the map with Don't Save. Reopen and render S3 for Gary's visual foot-contact acceptance.

## Open live gates

- **UNCLEAR:** the diagnostic shows the eight intended target labels, but only a live DRY can prove whether each binding is still owned by `LS_Clams` or a nested/shot sequence and whether all transform sections are absolute.
- **UNCLEAR:** sequence read-back proves numbers, not foot contact; Gary must accept the rendered result after the disposable map edits are discarded.
