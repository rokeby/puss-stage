# P02 P01-style lighting generalisation - offline handoff

## What is built

- **Declaration-proven:** `passage_lighting_as_source.py` is passage-parameterised and accepts only DRY/APPLY/REVERT with exact confirmations; its shipped default is P01 -> P02, full density, expected/capped at 414 (`passage_lighting_as_source.py:80-222`).
- **Declaration-proven:** source mapping is same ordinal with no wrap; `half` selects alternating lights globally; P02 target colours are retained by role then dominant fallback; sided Spot/Rect rows are aimed at their own target wing (`passage_lighting_as_source.py:335-484`).
- **Declaration-proven:** DRY stops when target bays, expected additions, or the configurable count cap disagree, and reports per-row/projected/shadow counts plus a preview (`passage_lighting_as_source.py:384-484`).
- **Declaration-proven:** Meshy/dead-bulb labels, plan special tokens, effects and non-lights are preserved. REVERT removes only recorded minted GUIDs, restores only removed originals, and refuses drift in fields this tool authored; unrelated rows survive (`passage_lighting_as_source.py:261-277`, `passage_lighting_as_source.py:584-596`, `passage_lighting_as_source.py:1104-1156`).
- **Declaration-proven:** APPLY/REVERT back up Show+level before mutation, require the exact dirty census, save only Show+level, read back owned rows/atmosphere fields, queue the saved-master test, and emit run-id markers (`passage_lighting_as_source.py:1273-1457`).
- **Declaration-proven:** the post-APPLY hook refuses without PIE, samples Slate frame deltas for a configurable interval, scans `PussStage.log` from the pre-mutation cursor recorded by APPLY for the historical device-removal/GPU-loss signatures, writes p50/p95/p99/max plus GPU health, and requires both `PASSAGELIGHT_PERF_OK` and `PASSAGELIGHT_GPU_HEALTH_OK` (`passage_lighting_perf_probe.py:26-125`). A hard GPU loss that prevents either completion marker is not a pass.
- **Declaration-proven:** APPLY records the clean pre-state, backup, pending GPU probe, and exact one-command field-scoped immediate revert before mutation. Its success marker prints both commands; the dedicated revert runner derives passage/hash/acknowledgements from the saved APPLY record rather than asking the operator to edit args (`passage_lighting_as_source.py:1369-1447`; `passage_lighting_immediate_revert.py:1-24`).
- **Measured:** P03's saved APPLY supplies 377 source lights for ordinals 1-21, and the P01 rig record supplies 19/18 for ordinals 22/23: `377 + 19 + 18 = 414`. The row table and cap are correct; the former 415 statement was stale arithmetic (`../p02p03_audit/LIGHTING_PLAN.md:34-40`).
- **Measured:** the offline harness passed 50/50 including positive and negative controls (`OFFLINE_HARNESS_RESULTS.md:1-5`).

## Ordered conductor run

1. Run the offline harness above again; require 44/0.
2. Leave `passage_lighting_args.json` in DRY and run `passage_lighting_request.json` through the guarded project-Python route.
3. Require `PASSAGELIGHT_DRY_OK`; inspect every per-row count, retained special, fallback colour, own-side aim, atmosphere action, exact dirty census, PNG preview, foreign-record list, and plan SHA. Do not APPLY if live added count is not exactly the chosen budget.
4. For half density, transfer the values from `passage_lighting_half_args.json` into the active args file and repeat DRY; never reuse a full-density SHA.
5. For APPLY, paste the fresh SHA, set `confirm` to `APPLY PASSAGELIGHT`, acknowledge only reviewed foreign records, and rerun. Require backup path, `PASSAGELIGHT_APPLY_OK`, saved read-back, zero final dirty packages, `gpu_health=PENDING`, and both exact commands in the marker.
6. Start one controlled P02-from-start PIE replay with the same review settings, then run `python Saved/CodexMocap/mcp_request.py tools/call --params-file Saved/CodexFlatV3/p02lighting/passage_lighting_perf_probe_request.json`. Require its JSON plus both `PASSAGELIGHT_PERF_OK` and `PASSAGELIGHT_GPU_HEALTH_OK`; no completion marker is a failure, not evidence of health.
7. Capture rendered stills at early/middle/late P02 and inspect wing depth, no corridor-crossing beams, fog, car/special motion, practical bodies, and shadow/VSM overlap. These are conductor/Gary acceptance, not tool success.
8. If live review produces a timeout/device removal: stop captures; reboot if the driver reports the GPU lost; preserve the APPLY record, logs and GPU dump; then replay P02 from start once with identical settings. If it recurs, run exactly `python Saved/CodexMocap/mcp_request.py tools/call --params-file Saved/CodexFlatV3/p02lighting/passage_lighting_immediate_revert_request.json`. Require `PASSAGELIGHT_IMMEDIATE_REVERT_BEGIN`, `PASSAGELIGHT_REVERT_OK`, field-scoped saved read-back, and repeat the identical replay as the A/B. Report recurrence as **measured** and causation only as **inferred** (`Docs/Conductor/P43_LIGHTING_INFRASTRUCTURE_2026-10-09.md:87-101`).

## Open questions / proof boundary

- **Inferred creative defaults:** own-side aim height 600 cm and frame thresholds p95 33.4 ms / p99 50 ms are reviewable args, not Gary-approved look/performance values (`passage_lighting_args.json:15-17`, `passage_lighting_args.json:33-39`).
- **Inferred operational boundary:** P43's GPU-loss section does not require row-by-row materialization, so APPLY keeps one reversible in-memory staging pass, one target-Passage materialization, and one narrow save. The post-APPLY controlled replay/probe is the GPU gate; it does not prove a safe causal light-count threshold.
- **Inferred/unverified:** no Unreal, MCP, PIE, Blender, saved-state, rendered, or performance run occurred in this stream. Visual and runtime acceptance remain pending.
- **Measured environment blocker:** explicit-path `git add` could not create `E:/PussStage/.git/worktrees/PussStage/index.lock` because this managed worktree has read-only access to the shared Git metadata. The nine scoped changed files are complete but uncommitted; no commit hash is claimed.
