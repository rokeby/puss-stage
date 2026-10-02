# Flat V3 passage-parameterised swapkit report

## Outcome

- **declaration-proven:** The config schema now defaults
  `overreach_tolerance_cm` to `0.0` and `keep_old_sides` to `[]`, validates a
  finite non-negative tolerance plus unique `{cue_guid, side, reason}` entries,
  and therefore keeps older configs strict (`common.py:36-101`).
- **declaration-proven:** Preflight rejects configured GUIDs outside the selected
  Passage with `UNKNOWN_KEEP_OLD_GUID`. Dry planning preserves the old panel
  record for every kept side, records the proposed edge evidence, classifies
  flags as `within_tolerance`, `kept_old`, or `unexplained`, and still raises
  `UNEXPLAINED_OVERREACH_FLAGS` for any unadjudicated remainder
  (`preflight.py:31-68`, `dry.py:37-165`, `dry.py:179-196`).
- **declaration-proven:** Apply, verify, and revert require the plan's kept-old
  declarations to match the config. They do not write those sides and assert
  that mesh, transform, material overrides, facing policy, and horizontal-flip
  state remain equal to preflight (`apply.py:25-33`, `apply.py:85-107`,
  `verify.py:130-175`, `revert.py:19-43`, `revert.py:75-97`).
- **declaration-proven:** Slot C is now `FV3C-20261002-03`, saved verification is
  `FV3CV-20261002-03`, the backup path matches `-03`, tolerance is 2.0 cm, and
  GUID `1ED83B530F4AEEB89EB6DE8F21BD20F9` right is explicitly kept old for the
  recorded 339 cm onstage-overreach reason (`run_c_p05.json:4-27`).

- **declaration-proven:** Passage occurrences are identified by cue index plus
  cue GUID. Preflight permits repeated labels and rejects empty/duplicated GUIDs;
  dry/apply/verify/revert all re-check index + GUID, with label only as a
  secondary diagnostic check (`preflight.py:31-54`, `common.py:259-276`).
- **declaration-proven:** Internal occurrence maps and capture frames are keyed
  by GUID. A repeated `capture_label` selects the first planned occurrence by
  cue index and records target index, GUID and label (`verify.py:124-181`,
  `verify.py:274-291`).
- **declaration-proven:** Run configs require the measured occurrence counts:
  P05=93, P01=48, P03=21 and P02=23. P05 capture now names existing
  `P05 Wing 001` (`run_c_p05.json:20-21`, `run_d_p01.json:20-21`,
  `run_p03.json:20-21`, `run_p02.json:20-22`).
- **declaration-proven:** P02 mapping is positional by `sequence_order`, asserts
  the 23-row contract, derives exclusions from current `validation.json` files,
  imports only passing set assets plus all eight industrial FBXs (including
  unused DuctVent), keeps any failed C asset old, and resolves mystical rows to
  Passage04 (`common.py:297-321`, `common.py:379-408`, `p02_import.py:47-127`,
  `p02_import.py:130-197`).
- **declaration-proven:** Apply/revert retain narrow Show+level dirty/save scope;
  verification remains read-only and token-gated (`apply.py:66-79`,
  `revert.py:60-73`, `verify.py:297-305`).
- **measured:** The probe-backed swapkit harness passes 23/23 across
  P05/P01/P03/P02/P06. For P05 `-03` it reads the released `-02` dry artifact's
  edge values back into the fake world and measures 0 unexplained, 12 within
  2.0 cm, and 1 kept-old side. The zero-tolerance/no-keep control fails with 13,
  the wrong-GUID control fails at `UNKNOWN_KEEP_OLD_GUID`, and an altered
  kept-old side fails at `VERIFY_KEPT_OLD_SIDE_CHANGED`
  (`../offline_harness/test_swapkit_offline.py:16-21`,
  `../offline_harness/test_swapkit_offline.py:129-176`,
  `../offline_harness/test_swapkit_offline.py:333-346`,
  `../offline_harness/test_swapkit_offline.py:420-484`).
- **measured:** The original Slot B harness still passes 9/9. The changed Python
  files compile and `run_c_p05.json` parses.
- **inferred:** The scripts are prepared for later editor execution, but this
  task ran no Unreal import, MCP, port 8010, Show mutation/save, PIE/render check,
  or visual acceptance.

## Run configs and offline plans

| Passage | No-edit config | Mapping authority | Offline plan |
| --- | --- | --- | --- |
| P05 / Slot C | `run_c_p05.json` (`FV3C-20261002-03`) | `Kept/KEPT_MAP.json`; CloudRef02-L excluded; 2 cm overreach tolerance; one GUID/right kept old | `PLAN_C_P05.md`: needs live preflight |
| P01 / Slot D | `run_d_p01.json` | `Kept/KEPT_MAP.json` | `PLAN_D_P01.md`: needs live preflight |
| P03 | `run_p03.json` | `P03_LAYOUT_DRAFT.json` | `PLAN_P03.md`: needs live preflight |
| P02 | `run_p02.json` | approved `P02_LAYOUT_DRAFT_v2.json`, positional 23-row order | P02 import + live preflight required |

The retained P04 Slot B pool is captured without changing it in
`mapping_b_p04.json`.

## Offline harness tables — 2 October 2026

`python Saved\CodexFlatV3\offline_harness\test_swapkit_offline.py`

| Test group | Polarity | Expected | Result |
| --- | --- | --- | --- |
| P05 `-03` full plan/apply/verify/saved-verify/revert | + | 0 unexplained; 12 within tolerance; 1 kept old | PASS |
| P01, P03, P02 and P06 full positive paths | + | Succeed | PASS (4/4) |
| P05 zero tolerance and no keep-old entry | - | `UNEXPLAINED_OVERREACH_FLAGS\|count=13` | PASS |
| Unknown keep-old GUID | - | `UNKNOWN_KEEP_OLD_GUID` | PASS |
| Altered kept-old side | + detector / - variant | `VERIFY_KEPT_OLD_SIDE_CHANGED` | PASS |
| Existing exclusion, token, None-top, identity, capture and static-token controls | mixed | Preserve prior outcomes | PASS (8/8) |
| P03/P02 import-source controls | + | Preserve prior outcomes | PASS (2/2) |
| P06 identity, pairing, negative-family and source-closure controls | mixed | Preserve prior outcomes | PASS (5/5) |
| **Overall** |  |  | **PASS 23/23** |

`python Saved\CodexFlatV3\offline_harness\test_slot_b_offline.py`

| Test | Polarity | Expected | Result |
| --- | --- | --- | --- |
| New revert / real originals | + | Succeed | PASS |
| Old revert / real originals | - | Fail on None mesh | PASS |
| Read-only verify / clean world | + | Succeed | PASS |
| Saved verifier / fresh run id | + | Succeed | PASS |
| Dirty evaluation verifier | - | Fail | PASS |
| Aggregated release | + | `saved_count=2` | PASS |
| Old release path | - | `saved_count=0` | PASS |
| Static token check | + | Succeed | PASS |
| Planted forbidden token | - | Fail | PASS |
| **Overall** |  |  | **PASS 9/9** |

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
3. Inspect the dry artifact. It must report 0
   `unexplained_overreach_flags`, 12 `within_tolerance_overreach_flags`, and one
   `kept_old_sides` entry for GUID
   `1ED83B530F4AEEB89EB6DE8F21BD20F9` / right. It must also report the
   CloudRef02-L occurrences in `excluded_rows_kept_old`; those old meshes stay
   assigned.
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

- Schema defaults and validation: `common.py:36-101`.
- Unknown keep-old GUID gate: `preflight.py:31-68`.
- Edge classification, explicit keep-old planning, and unexplained failure:
  `dry.py:37-165`; plan artifact fields and logging: `dry.py:179-196`.
- Apply/verify/revert kept-old enforcement: `apply.py:25-33`,
  `apply.py:85-119`, `verify.py:130-175`, `verify.py:297-302`,
  `revert.py:19-43`, `revert.py:75-103`.
- P05 `-03` IDs, backup, tolerance and right-side adjudication:
  `run_c_p05.json:4-27`.
- Released-edge injection and exact edge comparison in the harness:
  `../offline_harness/test_swapkit_offline.py:16-21`,
  `../offline_harness/test_swapkit_offline.py:129-176`,
  `../offline_harness/test_swapkit_offline.py:333-346`.
- New negative/detection controls:
  `../offline_harness/test_swapkit_offline.py:420-484`.

- GUID identity helper and unique-GUID preflight: `common.py:259-276`,
  `preflight.py:31-50`.
- GUID-keyed apply/revert/verify maps: `apply.py:40-46`, `revert.py:27-33`,
  `verify.py:140-181`.
- First-by-index repeated-label capture and recorded GUID: `verify.py:274-291`.
- Positional P02 mapping, live validation gate and Passage04 mystical routing:
  `common.py:297-321`, `common.py:379-408`.
- P02 validation-filtered set inventory and eight-industrial inventory:
  `p02_import.py:47-127`, `p02_import.py:130-197`.
- P02 source roots and eight-industrial count: `run_p02.json:22-28`.
- Occurrence counts and corrected P05 capture: `run_c_p05.json:20-21`,
  `run_d_p01.json:20`, `run_p03.json:21`, `run_p02.json:20-22`.
- Probe-backed controls and measured results:
  `../offline_harness/test_swapkit_offline.py:70-167`,
  `../offline_harness/test_swapkit_offline.py:350-423`,
  `../offline_harness/SWAPKIT_RESULTS.md:3-45`.
