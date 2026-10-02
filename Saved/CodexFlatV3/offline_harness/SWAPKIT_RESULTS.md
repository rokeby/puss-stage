# Flat V3 swapkit offline harness result

Command: `python -B Saved\CodexFlatV3\offline_harness\test_swapkit_offline.py`

| Test | +/- | Expected | Result | Detail |
| --- | --- | --- | --- | --- |
| swapkit P05 | + | succeed | PASS | 93 real probe occurrences; 12 failed-CloudRef02 L replacements kept old; apply/read-back/revert passed |
| swapkit P01 | + | succeed | PASS | 48 real probe occurrences passed |
| swapkit P03 | + | succeed | PASS | 21 real probe occurrences; 18 mapped changes passed |
| swapkit P02 | + | succeed | PASS | 23 real probe occurrences; positional plan and dynamic validation gate passed |
| CloudRef02 included | - | fail | PASS | `KNOWN_FAILED_ASSET_INCLUDED` |
| verify token absent | - | fail | PASS | `VERIFY_TOKEN_NOT_FOUND` |
| revert with None tops | + | succeed | PASS | None tops preserved without loading a null asset path |
| wrong passage prefix | - | fail | PASS | `PASSAGE_IDENTITY_GATE_FAIL` |
| old unique-label preflight on real P05 | - | fail | PASS | legacy gate produces `DUPLICATE_PASSAGE_LABEL` |
| duplicated occurrence GUID | - | fail | PASS | `DUPLICATE_PASSAGE_GUID` |
| missing capture label | - | fail | PASS | `CAPTURE_LABEL_NOT_PLANNED` |
| read-only verify tokens | + | succeed | PASS | no mutation tokens in `verify.py` or `verify_saved.py` |
| P03 import sources | + | 11 gated | PASS | built/validated LodGroup FBXs and socket contracts passed |
| P02 import/layout sources | + | passing-only + 8 / 23 positions | PASS | current snapshot: 24 passing set flats, 0 rejected, all 8 industrial FBXs, 23 ordered layout rows |

**OVERALL: PASS (14/14 harness assertions passed).**

Command: `python -B Saved\CodexFlatV3\offline_harness\test_slot_b_offline.py`

| Test | +/- | Expected | Result |
| --- | --- | --- | --- |
| new revert / real originals | + | succeed | PASS |
| old revert / real originals | - | fail | PASS |
| read-only verify / clean world | + | succeed | PASS |
| saved verifier / fresh run id | + | succeed | PASS |
| dirty evaluation verifier | - | fail | PASS |
| aggregated release | + | saved_count=2 | PASS |
| old release path | - | saved_count=0 | PASS |
| static token check | + | succeed | PASS |
| planted forbidden token | - | fail | PASS |

**OVERALL: PASS (9/9 harness assertions passed).**

Static check: every swapkit/offline-harness Python file compiles, and every
swapkit JSON file parses. Result: **`SYNTAX_JSON_PASS`**.

## Inner-edge minimum-gap gate addendum — 2 October 2026

Commands:

- `python -B Saved\CodexFlatV3\offline_harness\test_swapkit_offline.py`
- `python -B Saved\CodexFlatV3\offline_harness\test_slot_b_offline.py`

| Test | +/- | Expected | Result | Detail |
| --- | --- | --- | --- | --- |
| P02 current minimum-gap gate | - | fail | PASS | min old 662.333 cm; min current 48.667 cm; P02 Wing 002 |
| P02 shifted minimum-gap gate | + | pass | PASS | comparator old 525.145 cm; min after 528.688 cm; 22 shifted rows |
| P04 current minimum-gap gate | - | fail | PASS | min old 736.425 cm; min current 114.909 cm; P04 Wing 004 |
| P04 shifted minimum-gap gate | + | pass | PASS | comparator old 603.260 cm; min after 603.260 cm; 19 shifted rows |

| Passage | Min old (cm) | Min current (cm) | Min after shift (cm) |
| --- | ---: | ---: | ---: |
| P02 | 662.333 | 48.667 | 528.688 |
| P03 | 708.153 | 348.265 | 638.516 |
| P04 | 736.425 | 114.909 | 603.260 |

`Min old` is the original-plan gap for the occurrence owning `Min current`.
The live gate likewise pairs each state's minimum-new occurrence with that
same occurrence's original-plan gap; after shifting, the minimum occurrence
can change.

| Passage | Release min old (cm) | Release min new (cm) | Shifted rows |
| --- | ---: | ---: | ---: |
| P02 | 525.145 | 528.688 | 22 |
| P03 | 621.941 | 638.516 | 18 |
| P04 | 603.260 | 603.260 | 19 |

**Measured offline:** swapkit **40/40**, Slot B **9/9**, and
`SYNTAX_JSON_PASS`. No Unreal, MCP, or port 8010 was used.

## P05 FLOAT addendum — 2 October 2026

Command: `python -B Saved\CodexFlatV3\offline_harness\test_p05float_offline.py`

| Test | +/- | Expected | Result | Detail |
| --- | --- | --- | --- | --- |
| stable SHA plan across two runs | + | identical | PASS | 93 rows / 186 panels |
| all target bottoms | + | [150, 450] cm | PASS | observed 150.164358–449.022816 cm |
| `random.random` variant | - | determinism failure | PASS | differently seeded executions differ |
| planted world top >1100 cm | - | fail | PASS | `P05FLOAT_WORLD_TOP_LIMIT_FAIL` |
| verify with changed X | - | fail | PASS | `P05FLOAT_VERIFY_LOCAL_XY_CHANGED` |
| revert restores local Z | + | exact | PASS | all 93 rows / 186 panels restored |
| full fake workflow | + | pass | PASS | 2-file backup, apply 93, verify 186, saved verify 186, released with `saved_count=2` |
| read-only verifier token check | + | clean | PASS | no mutation tokens in either P05 FLOAT verifier |

**P05 FLOAT OVERALL: PASS (8/8 harness assertions passed).** The same final
control run also kept the shared swapkit at **26/26** and Slot B at **9/9**.
