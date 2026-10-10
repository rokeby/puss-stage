# Codex job 117 - S3 feet additive yaw transfer (offline)

Date: 2026-10-09  
Scope: `Saved/CodexConductor/S3FeetByHand_20261009/`

## Outcome and proof boundary

- **Measured (offline):** Python compilation passed and the expanded harness passed **34/34 positive + 28/28 negative = 62/62**. Unreal and Blender were not started. Evidence: `Saved/CodexConductor/S3FeetByHand_20261009/s3_feet_harness_report.json:1-88`.
- **Declaration-proven:** `allow_yaw` exists and defaults to false. Roll/pitch always refuse; yaw over tolerance refuses unless explicitly enabled; scale still refuses. Evidence: `Saved/CodexConductor/S3FeetByHand_20261009/s3_feet_core.py:58-72,89-115`.
- **UNCLEAR / not measured:** Crowd 15's live binding blend, its captured `-40` degree yaw, saved read-back, evaluated world pose, and rendered result were not checked because this job was offline only.

## Additive composition implemented

- **Declaration-proven (engine surface):** UE 5.8's installed headers declare three double channels each for translation, rotation, and scale on `UMovieScene3DTransformSection`; transform-key source data taken from a scene component is its relative location, rotation, and scale. Evidence: `D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/MovieSceneTracks/Public/Sections/MovieScene3DTransformSection.h:307-315`; `D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/MovieScene/Public/TransformData.h:28-35`.
- **Inferred (runtime composition unproved offline):** the installed headers do not expose the transform blender's implementation. For the requested additive-offset model, with hand translation delta `d=(dx,dy,dz)`, yaw delta `a`, and original additive location `p=(x,y,z)`, the tool writes `p'=(dx+cos(a)x-sin(a)y, dy+sin(a)x+cos(a)y, dz+z)` and `Yaw'=Yaw+a`. This is the requested “hand pose plus original motion rotated” relationship, but UE evaluation must still be established by the live probe. Evidence: `Saved/CodexConductor/S3FeetByHand_20261009/s3_feet_core.py:143-195`.
- **Declaration-proven:** yaw transfer is allowed only when every affected transform section is `ADDITIVE`. X/Y channels must have identical key presence, counts, and frames; otherwise the tool refuses rather than resampling or changing curve topology. Keyed pairs rotate about additive offset zero (the actor pivot); unkeyed pairs rotate their defaults. Every `Rotation.Z` key, or its default when unkeyed, receives the yaw delta. Evidence: `Saved/CodexConductor/S3FeetByHand_20261009/s3_feet_core.py:151-169,178-195`.
- **Measured (offline arithmetic):** the harness numerically checks three frames and proves the modeled evaluated world location equals the hand-placed pose plus the original motion rotated by `-40` degrees. Evidence: `Saved/CodexConductor/S3FeetByHand_20261009/test_s3_feet_offline.py:124-138`.

## Capture, apply, and refusal behavior

- **Declaration-proven:** a zero location and zero yaw remains an unmoved no-op row. A yaw-only move is accepted only with `allow_yaw=true`; changing the flag after CAPTURE refuses APPLY. Evidence: `Saved/CodexConductor/S3FeetByHand_20261009/s3_feet_core.py:89-115`; `Saved/CodexConductor/S3FeetByHand_20261009/s3_feet_editor.py:528-528`.
- **Declaration-proven:** APPLY/REVERT now write/read back `Rotation.Z` as well as location, using the tighter default `0.001` degree rotation tolerance. Spawnable templates retain the existing guarded template route and now receive the captured yaw. Evidence: `Saved/CodexConductor/S3FeetByHand_20261009/s3_feet_core.py:63-69,192-195`; `Saved/CodexConductor/S3FeetByHand_20261009/s3_feet_editor.py:285-304,479-505`.
- **Declaration-proven:** the older v1 pre-hand snapshot remains usable. Before its curve values are rebased, the tool requires the previous applied record to be saved/applied and numerically identical to the current binding. This preserves Crowd 15's old actor transform from `all_actors` without reapplying the earlier feet deltas. Evidence: `Saved/CodexConductor/S3FeetByHand_20261009/s3_feet_editor.py:338-370`.
- **Measured (offline controls):** negative controls cover default-off yaw, roll, pitch, scale, absolute/relative sections, malformed X/Y topology, missing defaults, and all pre-existing safety gates. Evidence: `Saved/CodexConductor/S3FeetByHand_20261009/test_s3_feet_offline.py:140-183`.

## Live one-frame A/B probe (not run)

- **Declaration-proven:** `s3_feet_yaw_ab_probe.py` reads and hashes Crowd 15's real binding before and after, requires all of its sections to report `ADDITIVE`, creates an unsaved transient sequence and one temporary actor, keys the rewritten additive transform, evaluates exactly frame 0, compares world position within 0.01 cm, destroys only its temporary actors, and requires the dirty-package census to return exactly to its entry state. It never calls a write method on the real binding. Evidence: `Saved/CodexConductor/S3FeetByHand_20261009/s3_feet_yaw_ab_probe.py:27-29,57-78,81-123,134-154`.
- **Inferred:** the probe should distinguish the requested component-additive result from a different runtime composition, but its UE 5.8 API path and cleanup are unverified until the conductor runs it. A failure is a stop: do not APPLY yaw.

## Conductor run order

1. Do not overwrite the existing pre-hand snapshot while Gary's Crowd 15 pose is live. Leave both Crowd 06 and Crowd 15 in `extra_target_labels` so its target set matches the prior snapshot, and set `allow_yaw=true` before CAPTURE.
2. Recommended first: set `s3_feet_yaw_probe_args.json` confirm to `RUN TRANSIENT S3 YAW A/B`, run `s3_feet_yaw_probe_request.json`, and require `S3_FEET_YAW_AB_OK`, `real_binding_writes=0`, `temp_saved=0`, and identical entry/exit dirty censuses. Restore its confirm to empty.
3. Set the main args to `mode=CAPTURE`; require Crowd 15's reported/applied yaw is approximately `-40`, roll/pitch and scale are zero, its intended XYZ move is correct, and every affected section is additive.
4. Set `mode=APPLY`, `confirm="APPLY S3 FEET"`; require the existing hashed backup, targeted sequence saves only, numeric read-back, `map_saved=0`, and `S3_FEET_APPLY_OK`.
5. Undo/reload the disposable viewport pose without saving the map, then evaluate frames and obtain Gary's rendered acceptance. REVERT remains `confirm="REVERT S3 FEET"`.

## Files

- Updated: `s3_feet_core.py`, `s3_feet_editor.py`, `s3_feet_args.json`, `test_s3_feet_offline.py`, `s3_feet_harness_report.json`.
- Added: `s3_feet_yaw_ab_probe.py`, `s3_feet_yaw_probe_args.json`, `s3_feet_yaw_probe_request.json`.
