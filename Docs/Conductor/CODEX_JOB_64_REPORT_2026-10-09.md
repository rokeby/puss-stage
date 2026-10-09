# Codex job 64 — batch 1h refusal repairs

Offline only. No Unreal, MCP, PIE, Blender, asset mutation, save, or commit was
performed.

## 1. Job 39 boundary-only gate

- **[measured, live batch evidence]** DRY run
  `B1H-I2POLISH-BOUNDARY-DRY-20261009-092652` had the Scene 2 boundary READY,
  `f17_fix_steps=[]`, and `f18_target_ids=[]`, but returned `apply_ready=0`
  solely because the F17 audit could not find a transform track on
  `I2 Hangar Hold Camera`. The dirty census remained empty. Evidence:
  `E:/PussStage/Saved/CodexConductor/EDITOR_BATCH1H_REPORT.json:10-17`;
  `E:/PussStage/Saved/Logs/PussStage.log:3020`.
- **[declaration-proven]** The old report builder appended
  `F17_AUDIT_UNAVAILABLE` unconditionally. F17 and F18 mutation already depended
  on nonempty fix/target selections. The new gate derives enabled parts from
  `boundary_apply`, `f17_fix_steps`, and `f18_target_ids`; disabled-part findings
  remain in `reported_issues` but do not enter `refusals`. Evidence:
  `Saved/CodexConductor/I2Polish_20261009/i2_polish.py:114-142,730-753,863-870,977-985`.
- **[declaration-proven]** A disabled part is not allowed to hide a write:
  `DISABLED_PART_WOULD_MUTATE|<PART>|<COUNT>` gates APPLY. An invocation with no
  enabled mutation part also refuses `NO_ENABLED_PARTS`. Evidence:
  `Saved/CodexConductor/I2Polish_20261009/i2_polish.py:123-142`.
- **[measured offline]** The logged boundary-only shape now passes, while an
  unavailable enabled F17 part and a synthetic disabled-F17 mutation both
  refuse. Evidence:
  `Saved/CodexConductor/I2Polish_20261009/test_i2_polish.py:127-136,216-226`.

## 2. Job 40 outfit-template uniqueness

- **[measured, live batch evidence]** DRY run `P40SHORE-20261009-092937`
  refused `OUTFIT_TEMPLATE_COUNT|Shore01_M56|2` before mutation; the dirty census
  remained empty. Evidence:
  `E:/PussStage/Saved/CodexConductor/EDITOR_BATCH1H_REPORT.json:27-34`;
  `E:/PussStage/Saved/Logs/PussStage.log:3093-3094`.
- **[declaration-proven]** The outfit search counted raw
  `SubobjectDataSubsystem` handles, while the adjacent cloth-template search
  already deduplicated objects by `get_path_name()`. The new shared helper
  deduplicates by full object path, accepts exactly one unique path, and refuses
  zero or multiple genuinely distinct paths. Evidence:
  `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:73-89,304-338`.
- **[declaration-proven]** The next DRY report records raw hit count, unique
  candidate count, candidate paths, and collapsed-handle count for every outfit
  template. Evidence:
  `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:83-89,369-393`.
- **[inferred, not yet live-verified]** Shore01's count of two is most likely two
  handles resolving to the same component. The batch log did not record paths,
  so whether those two live paths are identical remains UNCLEAR until the next
  corrected DRY. The tool will still refuse if they are distinct.
- **[measured offline]** The logged two-hit/same-path shape passes and a
  two-distinct-path control still refuses. Evidence:
  `Saved/CodexConductor/P40Shore05Settle_20261009/test_p40.py:111-135`.

## Regression proof and live order

- **[measured offline]** I2 passes 34/34 controls: 16 positive and 18 negative.
  P40 passes 35/35: 14 positive and 21 negative. Unreal and Blender were not
  started. Commands:
  `python Saved/CodexConductor/I2Polish_20261009/test_i2_polish.py` and
  `python Saved/CodexConductor/P40Shore05Settle_20261009/test_p40.py`.
- **[declaration-proven]** After deploying these files to the active tree, the
  conductor must run a fresh job-39 boundary-only DRY with a new run id, inspect
  `reported_issues`, require `enabled_parts={boundary:true,f17:false,f18:false}`
  and `apply_ready=1`, then APPLY and perform the already-required saved
  read-back/post-APPLY PIE seam probe. Next run job 40 DRY and require Shore01's
  `template_discovery.unique_candidate_count=1` before APPLY. Use the existing
  guarded request files in each tool directory.
- **[inferred/unverified]** The next live DRYs should clear these two false
  refusals. No current-editor result, saved-state read-back, seam repair, Shore05
  placement, render, or visual acceptance is claimed.
