# Flat V3 passage-parameterised swapkit report

## Outcome

- **declaration-proven:** Passage occurrences are identified by cue index plus
  cue GUID. Preflight permits repeated labels and rejects empty/duplicated GUIDs;
  dry/apply/verify/revert all re-check index + GUID, with label only as a
  secondary diagnostic check (`preflight.py:31-50`, `common.py:218-235`).
- **declaration-proven:** Internal occurrence maps and capture frames are keyed
  by GUID. A repeated `capture_label` selects the first planned occurrence by
  cue index and records target index, GUID and label (`verify.py:131-176`,
  `verify.py:265-282`).
- **declaration-proven:** Run configs require the measured occurrence counts:
  P05=93, P01=48, P03=21 and P02=23. P05 capture now names existing
  `P05 Wing 001` (`run_c_p05.json:20-21`, `run_d_p01.json:20-21`,
  `run_p03.json:20-21`, `run_p02.json:20-22`).
- **declaration-proven:** P02 mapping is positional by `sequence_order`, asserts
  the 23-row contract, derives exclusions from current `validation.json` files,
  imports only passing set assets plus all eight industrial FBXs (including
  unused DuctVent), keeps any failed C asset old, and resolves mystical rows to
  Passage04 (`common.py:260-284`, `common.py:342-371`, `p02_import.py:47-127`,
  `p02_import.py:130-197`).
- **declaration-proven:** Apply/revert retain narrow Show+level dirty/save scope;
  verification remains read-only and token-gated (`apply.py:61-74`,
  `revert.py:49-61`, `verify.py:277-305`).
- **measured:** The probe-backed harness passes 14/14 across P05/P01/P03/P02.
  The legacy unique-label gate fails on real P05, duplicated GUID and missing
  capture label controls fail as required, and all prior controls remain green
  (`../offline_harness/SWAPKIT_RESULTS.md:3-24`).
- **measured:** The original Slot B harness still passes 9/9, every scoped Python
  file compiles, and every swapkit JSON parses (`../offline_harness/SWAPKIT_RESULTS.md:24-40`).
- **inferred:** The scripts are prepared for later editor execution, but this
  task ran no Unreal import, MCP, port 8010, Show mutation/save, PIE/render check,
  or visual acceptance.

## Run configs and offline plans

| Passage | No-edit config | Mapping authority | Offline plan |
| --- | --- | --- | --- |
| P05 / Slot C | `run_c_p05.json` | `Kept/KEPT_MAP.json`, with `SM_FlatV3_P05_CloudRef02_L_L` forcibly excluded | `PLAN_C_P05.md`: needs live preflight |
| P01 / Slot D | `run_d_p01.json` | `Kept/KEPT_MAP.json` | `PLAN_D_P01.md`: needs live preflight |
| P03 | `run_p03.json` | `P03_LAYOUT_DRAFT.json` | `PLAN_P03.md`: needs live preflight |
| P02 | `run_p02.json` | approved `P02_LAYOUT_DRAFT_v2.json`, positional 23-row order | P02 import + live preflight required |

The retained P04 Slot B pool is captured without changing it in
`mapping_b_p04.json`.

## Live-agent rule and exact entrypoints

Run the binding scripts below **as-is**. Each binding passes its named run JSON
to the shared implementation; neither the binding, run JSON nor core script is
to be edited in an editor slot. Stop immediately on any `FAIL`, exception,
unexpected dirty census, missing backup, identity mismatch, overreach requiring
review, or missing marker.

For Slot C / P05:

1. Create the exact backup folder named by `run_c_p05.json`, containing the two
   required package files.
2. Run `c_p05_preflight.py`, then `c_p05_dry.py`.
3. Inspect the dry artifact. It must report the CloudRef02-L occurrence in
   `excluded_rows_kept_old`; that occurrence's old mesh stays assigned.
4. Run `c_p05_apply.py`.
5. Run `InfinityStage.Editor.SavedMasterMatchesShow` and require Success.
6. Run `c_p05_verify.py`. A later fresh read-back uses
   `c_p05_verify_saved.py`. Manual rollback uses `c_p05_revert.py`.

For Slot D / P01, repeat the same sequence with `d_p01_*`, only after
`FLATV3_C_OK` exists. For P03, run `p03_p03_import.py` first; only after
`FLATV3_P03_IMPORT_OK`, create the configured Show/level backup and run the
`p03_preflight.py`, `p03_dry.py`, `p03_apply.py`, SavedMasterMatchesShow test,
and `p03_verify.py` sequence. Fresh verification and manual rollback use
`p03_verify_saved.py` and `p03_revert.py`.

For P02, run `p02_p02_import.py` first and require
`FLATV3_P02_IMPORT_OK`. The importer and mapping read current validation files:
only passing set assets enter the destination, and any failed proposal keeps its
old panel. The final offline snapshot had all 24 set assets passing. All eight
industrial FBXs import; DuctVent L/R remain deliberately unused by the 23-row
layout. After creating the configured backup, run `p02_preflight.py`,
`p02_dry.py`, inspect all 23 rows and any dynamically reported keep-old records, then
`p02_apply.py`, SavedMasterMatchesShow, and `p02_verify.py`. Fresh verification
and rollback use `p02_verify_saved.py` and `p02_revert.py`.

## Slot-note text prepared under the allowed scope

The request simultaneously limited edits to new files under `swapkit/` and
`offline_harness/` and asked to update existing files under `Saved/CodexRuns`.
The narrower edit boundary was respected, so `C_P05.md` and `D_P01.md` were not
modified and `P03_swap.md` was not created outside the allowed directories.
The operational text those notes need is:

> Run the Flat V3 swapkit binding scripts AS-IS for this slot, using the bound
> run JSON. Never edit a core script, binding, or config per passage. Execute
> preflight then dry; inspect the plan; create/verify the exact configured
> backup; execute apply; run SavedMasterMatchesShow; execute verify. Stop on any
> FAIL, exception, unexpected dirty census, identity mismatch, missing marker,
> missing backup, or unexplained overreach flag. Apply may save only the Show
> and current level. Use verify_saved for a fresh read-back and revert for
> rollback.

P05's note must additionally say that
`SM_FlatV3_P05_CloudRef02_L_L` is excluded after the 1700-vs-1702 triangle gate
failure; the mapped occurrence keeps its old mesh and the dry artifact must
report it. P03's note must additionally place `p03_p03_import.py` before the
swap sequence and require `FLATV3_P03_IMPORT_OK`.

## Evidence pointers

- GUID identity helper and unique-GUID preflight: `common.py:218-235`,
  `preflight.py:31-50`.
- GUID-keyed apply/revert/verify maps: `apply.py:34-40`, `revert.py:21-31`,
  `verify.py:131-176`.
- First-by-index repeated-label capture and recorded GUID: `verify.py:265-282`.
- Positional P02 mapping, live validation gate and Passage04 mystical routing:
  `common.py:260-284`, `common.py:342-371`.
- P02 validation-filtered set inventory and eight-industrial inventory:
  `p02_import.py:47-127`, `p02_import.py:130-197`.
- P02 source roots and eight-industrial count: `run_p02.json:22-28`.
- Occurrence counts and corrected P05 capture: `run_c_p05.json:20-21`,
  `run_d_p01.json:20`, `run_p03.json:21`, `run_p02.json:20-22`.
- Probe-backed controls and measured results:
  `../offline_harness/test_swapkit_offline.py:70-167`,
  `../offline_harness/test_swapkit_offline.py:350-423`,
  `../offline_harness/SWAPKIT_RESULTS.md:3-45`.
