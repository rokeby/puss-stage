# P02 P01-style lighting generalisation - offline handoff

## What is built

- **Declaration-proven:** `passage_lighting_as_source.py` is passage-parameterised and accepts only DRY/APPLY/REVERT with exact confirmations; its shipped default is P01 -> P02, full density, expected/capped at 414 (`passage_lighting_as_source.py:72-202`).
- **Declaration-proven:** source mapping is same ordinal with no wrap; `half` selects alternating lights globally; P02 target colours are retained by role then dominant fallback; sided Spot/Rect rows are aimed at their own target wing (`passage_lighting_as_source.py:321-464`).
- **Declaration-proven:** DRY stops when target bays, expected additions, or the configurable count cap disagree, and reports per-row/projected/shadow counts plus a preview (`passage_lighting_as_source.py:365-464`).
- **Declaration-proven:** Meshy/dead-bulb labels, plan special tokens, effects and non-lights are preserved. REVERT removes only recorded minted GUIDs, restores only removed originals, and refuses drift in fields this tool authored; unrelated rows survive (`passage_lighting_as_source.py:242-257`, `passage_lighting_as_source.py:565-578`, `passage_lighting_as_source.py:1085-1141`).
- **Declaration-proven:** APPLY/REVERT back up Show+level before mutation, require the exact dirty census, save only Show+level, read back owned rows/atmosphere fields, queue the saved-master test, and emit run-id markers (`passage_lighting_as_source.py:1248-1411`).
- **Declaration-proven:** the post-APPLY hook refuses without PIE, samples Slate frame deltas for a configurable interval, writes p50/p95/p99/max, and emits thresholded `PASSAGELIGHT_PERF_OK` or `PASSAGELIGHT_PERF_FAILED` (`passage_lighting_perf_probe.py:30-91`).
- **Measured:** the offline harness passed 44/44 including positive and negative controls (`OFFLINE_HARNESS_RESULTS.md:1-5`).

## Ordered conductor run

1. Run the offline harness above again; require 44/0.
2. Leave `passage_lighting_args.json` in DRY and run `passage_lighting_request.json` through the guarded project-Python route.
3. Require `PASSAGELIGHT_DRY_OK`; inspect every per-row count, retained special, fallback colour, own-side aim, atmosphere action, exact dirty census, PNG preview, foreign-record list, and plan SHA. Do not APPLY if live added count is not exactly the chosen budget.
4. For half density, transfer the values from `passage_lighting_half_args.json` into the active args file and repeat DRY; never reuse a full-density SHA.
5. For APPLY, paste the fresh SHA, set `confirm` to `APPLY PASSAGELIGHT`, acknowledge only reviewed foreign records, and rerun. Require backup path, `PASSAGELIGHT_APPLY_OK`, saved read-back, zero final dirty packages, and `perf_gate=PENDING`.
6. Capture rendered stills at early/middle/late P02 and inspect wing depth, no corridor-crossing beams, fog, car/special motion, practical bodies, and shadow/VSM overlap. These are conductor/Gary acceptance, not tool success.
7. In PIE, at the agreed review position, run `passage_lighting_perf_probe_request.json`; require its JSON plus `PASSAGELIGHT_PERF_OK`. It gates frame cadence only; collect GPU/VSM evidence separately.
8. To undo, keep the record, set `mode`/`confirm` to `REVERT`/`REVERT PASSAGELIGHT`, rerun, and require `PASSAGELIGHT_REVERT_OK` plus saved read-back.

## Open questions / proof boundary

- **Measured discrepancy:** the plan's P02 row table sums to 415, while its explicit default and cap are 414 (`E:/PussStage/Saved/CodexFlatV3/p02p03_audit/LIGHTING_PLAN.md:38-62`, `LIGHTING_PLAN.md:116-117`). The tool deliberately trusts 414 and makes live DRY stop if the source census says otherwise; the conductor must resolve this before APPLY.
- **Inferred creative defaults:** own-side aim height 600 cm and frame thresholds p95 33.4 ms / p99 50 ms are reviewable args, not Gary-approved look/performance values (`passage_lighting_args.json:15-17`, `passage_lighting_args.json:33-39`).
- **Inferred/unverified:** no Unreal, MCP, PIE, Blender, saved-state, rendered, or performance run occurred in this stream. Visual and runtime acceptance remain pending.
- **Measured environment blocker:** `git add -f` could not create `E:/PussStage/.git/worktrees/PussStage52/index.lock` because this managed worktree has read-only access to the shared Git metadata. The 14 stream files are complete but uncommitted; no commit hash is claimed.
