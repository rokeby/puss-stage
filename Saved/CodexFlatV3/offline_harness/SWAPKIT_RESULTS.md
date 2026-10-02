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
