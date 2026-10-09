# Codex job 67 - P40 APPLY transform-channel failure

Date: 9 October 2026. Scope: offline repair only; no Unreal, MCP, PIE, Blender,
asset save, or commit.

## Verdict

- **[measured, live evidence supplied by the conductor]** APPLY run
  `P40SHORE-20261009-101527` failed in `add_transform` at
  `TRANSFORM_CHANNELS`, after dirtying `/Game/Scenes/LS_Clams` and
  `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice`; no package was
  saved. Evidence:
  `E:/PussStage/Saved/CodexConductor/EDITOR_BATCH1N_REPORT.json:10-15,50-56` and
  `E:/PussStage/Saved/Logs/PussStage-backup-2026.10.09-14.15.39.log:8919-8922`.
- **[inferred from measured failure plus declaration-proven code]** The root
  cause was name canonicalization, not missing transform channels: the failed
  code stripped only a `" ("` annotation while
  UE 5.8 scripting channels carry changing numeric suffixes such as
  `Location.X_183`. The repaired canonicalizer removes only a terminal numeric
  suffix and then enforces the exact nine-channel count and order. Evidence:
  `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:227-246`.
- **[measured, offline]** The new regression reconstructs suffixed transform
  channel names, proves the old comparison fails, proves the repaired lookup
  succeeds, and negatively controls wrong channel order. Evidence:
  `Saved/CodexConductor/P40Shore05Settle_20261009/test_p40.py:207-221`.

## Repair

- **[declaration-proven]** FGuid identity is now serialized by
  `GuidLibrary.conv_guid_to_string`, with `export_text` as the offline-safe
  fallback; no binding identity uses `str(FGuid)`. Evidence:
  `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:249-261,980-982`.
- **[declaration-proven]** `add_possessable`, `add_track`, and `add_section`
  return values are ignored. Each created binding/track/section is resolved from
  a collection read-back (GUID difference, class census, or stable section-name
  difference) before it is edited. Evidence:
  `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:264-291,789-825`.
- **[declaration-proven]** DRY/APPLY preflight now checks the existing
  nine-channel transform schema, every planned Blueprint class and spawned
  Body/Chaos-cloth template, animation assets, outfit slots and child-name
  collisions, existing actor outfit components, and all backup sources.
  APPLY resolves all loadable dependencies before backup/record creation and
  before `spawn_placements`, the first Unreal mutation. Evidence:
  `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:585-644,646-677,924-961`.
- **[declaration-proven]** Post-mutation guards remain in place, but they are
  read-back assertions for results that cannot be known before mutation
  (spawn success, new GUID/track/section presence, written defaults/materials,
  exact dirty census, save, and saved read-back). Evidence:
  `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:761-825,836-911,913-922,963-978`.

## Offline verification

- **[measured, offline]** Python compilation passed and the harness passed
  **43/43** controls: **14/14 positive**, **29/29 negative/regression**;
  `unreal=0`, `blender=0`. The added controls cover suffixed channel names,
  wrong channel order, changing GUID wrapper strings, and lying
  add-binding/track/section return values. Evidence:
  `Saved/CodexConductor/P40Shore05Settle_20261009/p40_harness_report.json:116-122,220-227`.
- **[inferred]** The tool is ready for a new conductor-owned DRY and then APPLY,
  but live creation, dirty census, save/read-back, VERIFY, cloth behavior, and
  rendered appearance remain unproved because job 67 was offline-only.

No commit was made.
