# Codex job 63 — batch 1f refusal repairs

Offline only. No Unreal, MCP, PIE, Blender, content package, Show/level mutation,
or commit was performed.

## 1. P40 B07 camera

- **[measured, live batch evidence]** DRY
  `P40SHORE-20261009-091053` refused `S3 Shot B07` at frame 0 because no
  absolute transform section covered that frame. The dirty census remained
  empty. Evidence:
  `E:/PussStage/Saved/Logs/PussStage-backup-2026.10.09-13.14.57.log:5297-5323`.
- **[declaration-proven]** MovieScene uses the object's initial value when only
  additive channels contribute, and defines Relative as initial plus channel
  value. Evidence:
  `D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/MovieScene/Public/Evaluation/Blending/MovieSceneBlendType.h:21-28`;
  `D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/MovieScene/Public/Evaluation/Blending/MovieSceneMultiChannelBlending.h:211-238,266-286`.
- **[declaration-proven]** P40 now treats no covering section as the spawnable
  template pose; it also supports additive-only and one relative section from
  that initial pose, while preserving job 59's absolute-plus-additive support.
  Multiple absolute/relative owners still refuse because their weighted/eased
  blend cannot be reconstructed exactly from raw channel values. Evidence:
  `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:190-228,267-286`.
- **[declaration-proven]** A `MovieScene3DAttachTrack` still refuses with
  `CAMERA_ATTACHMENT_UNEVALUATED`: its channels are parent-relative, and this
  offline reader has no authoritative parent-world evaluation. The planner
  must not silently skip it; either bake an absolute camera transform, or add a
  separately measured world-space exclusion margin and report that camera as
  skipped. Evidence:
  `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:244-250`.

## 2. ClamSlime LID_PIVOT

- **[measured, live batch evidence]** IMPORT measured the generated animation
  bone `lid` at `[0.0,-0.479,0.300]` for frames 0, 6, 12, 18, 24 and 30. The old
  expectation was `[0.0,-47.86,30.02]`: same axes/signs, exactly 100x different
  units. Evidence:
  `E:/PussStage/Saved/Logs/PussStage-backup-2026.10.09-13.14.57.log:5403-5425`.
- **[declaration-proven]** The design is centimetres but `build_slime.py`
  creates Blender bones in metres. The gate now names both units and expects
  AnimationLibrary local translation `[0.0,-0.4786,0.3002]` metres, with the
  former 0.05 cm tolerance converted to 0.0005 m. Mesh bounds retain their
  centimetre gate. Evidence:
  `Saved/CodexConductor/ClamSlime_20261008/build_slime.py:19-23,60-85`;
  `Saved/CodexConductor/ClamSlime_20261008/slime_apply_ue.py:127-135,235-257`.
- **[declaration-proven]** This is the generated
  `SK_PearlClam_Slime` / `A_PearlClam_SlimeOpen` bone, on actor
  `S3 PearlClam Slime`, which APPLY attaches to the existing
  `S3 PearlClam` bottom actor from the S3Millstone record. It is not the
  separate lid actor's mesh pivot. Evidence:
  `Saved/CodexConductor/ClamSlime_20261008/slime_apply_ue.py:103-119,691-696,1032-1065`.
- **[inferred]** The gate was stale; no asset rebuild is indicated. A sign error
  or 1 cm pivot drift still refuses. The conductor must first discard batch
  1f's unsaved transient imports by the already-required Don't-Save restart,
  then repeat DRY -> IMPORT -> DRY -> APPLY.

## Regression proof and boundary

- **[measured]** P40 compiles and passes 34/34 offline controls. Its regression
  covers old zero-absolute refusal, new initial/relative/additive passes, and a
  conflicting-base refusal. Evidence:
  `Saved/CodexConductor/P40Shore05Settle_20261009/test_p40.py:77-111`.
- **[measured]** ClamSlime compiles and passes 72/72 offline controls using the
  batch build/validation JSON as read-only fixtures. Its regression proves old
  centimetre comparison refusal, new logged-number pass, axis-flip refusal,
  and 1 cm drift refusal. Evidence:
  `Saved/CodexConductor/ClamSlime_20261008/test_slime_apply_ue.py:591-612`.
- **[declaration-proven]** Offline rerun commands are
  `python Saved/CodexConductor/P40Shore05Settle_20261009/test_p40.py`, then set
  `CLAMSLIME_FIXTURE_DIR=E:/PussStage/Saved/CodexConductor/ClamSlime_20261008`
  and run
  `python Saved/CodexConductor/ClamSlime_20261008/test_slime_apply_ue.py`.
- **[inferred/unverified]** The next live P40 DRY and ClamSlime IMPORT should
  clear these exact refusals. No current-editor result, saved read-back, PIE,
  render, or visual acceptance is claimed.
