# P43 lighting infrastructure — offline delivery, 9 Oct 2026

## Scope and acceptance boundary

- **measured** — This worktree run used system Python only. No Unreal, MCP, PIE,
  Blender, asset save, or rendered capture was run. The integrated harness ended
  `P43_LIGHTING_HARNESS|pass=24|fail=0`; predecessor controls ended
  `P03ASP01_HARNESS|pass=35|fail=0` and
  `P13_OPENING_LIGHTING_TESTS|pass=85|fail=0`.
  [`Saved/CodexConductor/test_p43_lighting_offline.py:1`](../../Saved/CodexConductor/test_p43_lighting_offline.py)
- **inferred** — The tools are ready for a conductor-owned live DRY. They are not
  proof of current Show state, safe GPU headroom, a matched seam, correct exposure,
  or Gary's visual acceptance.

## Delivered

### P02 lit like P01

- **declaration-proven** — The existing P03 engine now derives target Passage,
  mark, record, args, report and backup names from `target_passage_number`; P03
  remains the legacy default so its existing REVERT address is preserved.
  [`Saved/CodexConductor/p03_lighting_as_p01.py:140`](../../Saved/CodexConductor/p03_lighting_as_p01.py)
- **declaration-proven** — The pre-mutation performance gate counts total,
  shadow-casting, volumetric-shadow, uncached-shadow and light-function lights,
  and refuses missing/out-of-range VSM/fog CVars. The gate is executed before
  DRY returns and before APPLY can create a backup/record or mutate the Show.
  [`Saved/CodexConductor/p03_lighting_as_p01.py:393`](../../Saved/CodexConductor/p03_lighting_as_p01.py)
  [`Saved/CodexConductor/p03_lighting_as_p01.py:1160`](../../Saved/CodexConductor/p03_lighting_as_p01.py)
- **declaration-proven** — APPLY still requires the DRY plan hash, exact foreign
  record acknowledgements, a pre-change Show+level backup, exact dirty scope,
  named saves and saved read-back. [`Saved/CodexConductor/p03_lighting_as_p01.py:1197`](../../Saved/CodexConductor/p03_lighting_as_p01.py)
- **inferred** — Default thresholds (450 lights, 125 casters, 32 volumetric
  casters) are conservative review defaults, not measured safe limits. Gary or
  the conductor must approve/change them in `p02_lighting_as_p01_args.json`.

### P02 → S2 seam and S2 dark shots

- **declaration-proven** — PROBE records every serialized P02 light, every bound
  S2 light intensity/visibility, post-process exposure and fog value at the S2
  first-two-second window and each active shot start/mid/end; it reports aggregate
  seam deltas and shot summaries. `make_range(frame, 1)` is used and evaluation
  must return exactly one value. [`Saved/CodexConductor/s2_lighting_seam.py:103`](../../Saved/CodexConductor/s2_lighting_seam.py)
- **declaration-proven** — P02's negative-two-second side is explicitly labelled
  as repeated serialized Show terminal state. Passage runtime Drama is not
  evaluated, so this is not a measured in-play crossfade. S2 values are serialized
  channel evaluations, not rendered luminance.
- **declaration-proven** — DRY/APPLY accept only exact binding/property windows
  and args factors/offsets. No wildcard or automatic creative target is selected.
  [`Saved/CodexConductor/s2_lighting_seam.py:125`](../../Saved/CodexConductor/s2_lighting_seam.py)
- **declaration-proven** — APPLY/REVERT own only `P43 S2 Lighting` float tracks on
  `LS_DevScene_02`; both backup first, require the exact sequence-only dirty
  census, save that named asset and read it back. [`Saved/CodexConductor/s2_lighting_seam.py:356`](../../Saved/CodexConductor/s2_lighting_seam.py)
- **inferred** — The smallest useful live change cannot be chosen until PROBE
  names the discontinuity and Gary chooses factors. Empty adjustments are the
  deliberate default; APPLY refuses an empty plan.

### P30 facade PAR cans

- **declaration-proven** — The default facade subset is explicit slots 2–7;
  slot 1/bay-1 is a hard refusal, and the P01 practical subset defaults empty.
  [`Saved/CodexConductor/opening_lighting_p13.py:108`](../../Saved/CodexConductor/opening_lighting_p13.py)
  [`Saved/CodexConductor/opening_lighting_p13.py:247`](../../Saved/CodexConductor/opening_lighting_p13.py)
- **declaration-proven** — Every planned facade placement names
  `/Game/InfinityStage/Lighting/Fixtures/Meshes/SM_Lantern_ParCan`; DRY audits
  that one-model invariant and reports other PAR-can meshes found in the show
  without rewriting them. [`Saved/CodexConductor/opening_lighting_p13.py:502`](../../Saved/CodexConductor/opening_lighting_p13.py)
- **inferred** — The audit proves plan identity and inventories existing models;
  it does not prove a rendered physical housing until APPLY/materialization and
  saved read-back are run.

## Ordered conductor runbook

1. Run offline harness: `python Saved/CodexConductor/test_p43_lighting_offline.py`.
2. With the correct clean PussStage editor/world, run
   `p02_lighting_as_p01_request.json` in DRY. Review the preview, every kept
   special, performance counts/CVars and `plan_sha256`. Do not loosen a failed
   gate merely to apply.
3. Run `s2_lighting_seam_request.json` in PROBE. Review every row, the explicit
   P02-runtime limitation, seam delta and per-shot summaries. Put only approved
   exact binding/property windows and factors into the args; run DRY again.
4. Run `opening_lighting_p13_request.json` in DRY. Require six facade slots,
   empty bay-1/P01 subset, one planned mesh, and review every reported other model.
5. Only after Gary reviews DRYs/stills: set the exact APPLY confirm and DRY digest
   or plan hash, APPLY one tool at a time, read its success marker, run the queued
   saved-master checks, and capture stills. Never Save All.

## GPU-loss / immediate REVERT runbook

- **measured (historical)** — The 8 Oct crash was `DXGI_ERROR_DEVICE_REMOVED` in
  `VolumetricFog::LightScattering`; the relight added about 91 lights, but the GPU
  had also timed out before APPLY. [`Docs/Conductor/CONDUCTOR5_LOG_2026-10-08.md:206`](CONDUCTOR5_LOG_2026-10-08.md)
- **measured (historical)** — After reboot, the P03 replay and stills completed
  without another timeout. Causation therefore remains unproven.
  [`Docs/Conductor/CONDUCTOR5_LOG_2026-10-08.md:222`](CONDUCTOR5_LOG_2026-10-08.md)
- If P02 live review produces a timeout/device removal: stop captures; reboot if
  the driver reports the GPU lost; do one controlled P02-from-start replay with
  the same settings. If it recurs, set mode `REVERT`, confirm
  `REVERT P02ASP01`, run the same guarded request, require
  `P02ASP01_REVERT_OK|...|readback=1`, then repeat the same replay as the A/B.
  Preserve the APPLY/REVERT records, logs and GPU dump. Report recurrence as
  **measured** and cause only as **inferred** until the A/B separates it.

## Open questions for Gary / conductor

1. Approve or change the P02 performance thresholds before APPLY.
2. Choose the exact S2 bindings, shot windows and exposure/light factors after PROBE.
3. Confirm that reported nonstandard PAR-can models should remain inventory-only;
   this tool deliberately does not normalize them.

## Commit state

- **measured** — The scoped commit could not be created in this sandbox: git
  needs `E:/PussStage/.git/worktrees/PussStage49/index.lock`, and that linked
  main-tree git directory is read-only here (`Permission denied`). No files were
  staged or committed; all deliverables remain present in this worktree for the
  conductor to review and commit with explicit paths.
