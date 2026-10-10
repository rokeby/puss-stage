# Codex job 112 — pass-1 fix batch

Date: 2026-10-10  
Scope: offline source fixes and offline positive/negative harnesses only. No Unreal, MCP, PIE, asset save, or Show mutation was performed.

## Verdict

All eight requested failures have narrowly scoped source fixes and passing offline controls. “Ready” below means ready for the specified pass-2 rerun or prerequisite sequence; it is **inferred**, not live/rendered acceptance.

| Item | Cause | Fix | Offline harness | Ready for pass 2? |
|---|---|---|---|---|
| (a) Job 87 / P87 opening | **Measured (prior pass):** the cue-label selector returned zero P01 cues; the uniqueness guard correctly refused (`Docs/Conductor/DRY_ALL_REPORT_2026-10-10.md:24`). | **Declaration-proven:** `Passage 1` is now selected from Show `passages`; its `first_cue_guid` then selects exactly one live cue. Both count guards remain (`Saved/CodexConductor/P87OpeningFixes_20261009/p87_unreal_adapter.py:133-144`). | **Measured offline:** 47/47, including 17 negative controls; selector contract at `test_p87_opening.py:133-138`. | **Yes — inferred:** rerun DRY. |
| (b) Job 92 / S2 envelope | **Measured (prior pass):** old requested bounds were below the measured side/top envelope (`DRY_ALL_REPORT_2026-10-10.md:29`). The first recommendation also omitted raised lattice rest/roof clearance. | **Declaration-proven:** measured-bounds proposal now preserves the 1600 cm travel and roof/rail clearance (`s2_envelope_core.py:19-38`). Args are 8500 half-width, 16000 height, lattice 14100 landed/15700 rest (`s2_envelope_args.json:16-19`). | **Measured offline:** 14/14; measured-bounds positive and undersize negatives (`test_s2_envelope_offline.py:27-43`). | **Yes — inferred:** rerun bounds DRY. |
| (c) Job 94 / S3 arrival | **Measured (prior pass):** Unreal returned post-string `"None"`, not Python `None` (`DRY_ALL_REPORT_2026-10-10.md:32`). | **Declaration-proven:** the property normalizer maps both forms to unbound and leaves `bHiddenInGame` intact for refusal (`P94S3Arrival_20261009/p94_s3_arrival.py:309-322`). | **Measured offline:** 24/24; explicit sentinel-positive and inert-property-negative controls (`test_p94.py:176-177`). | **Yes — inferred:** rerun DRY. |
| (d) Job 97 / E18 nap | **Measured (prior pass):** configured GUID matched no live cue (`DRY_ALL_REPORT_2026-10-10.md:35`). | **Declaration-proven:** recursively reads minted nap GUIDs from `NAP_LIVE_REPORT.json` and nap records, prefers them over the configured GUID, preserves uniqueness, and permits exact `Nap — battery change` fallback only after every candidate GUID is absent; the resolution is recorded (`NapInterlude_20261009/e18_nap_revision.py:87-134`, `:392-404`). | **Measured offline:** 29/29 (5 positive, 16 negative), including record-GUID precedence, recorded absence proof, and ambiguous-label refusal (`test_e18_nap_revision.py:191-209`). | **Yes — inferred:** rerun DRY and inspect `identity_resolution`. |
| (e) Pearl fade | **Measured (prior pass):** 4944→5040 at 24 fps was four seconds (`DRY_ALL_REPORT_2026-10-10.md:37`). | **Declaration-proven:** retains end 5040 and computes start 4992 (48 frames / two seconds); exact legacy 4944 keys are narrowly retimed (`Saved/CodexConductor/s3_pearl_fade.py:23-27`, `:202-236`). | **Measured offline:** 4/4, including duration, legacy adoption/retime, and drift refusal (`test_s3_pearl_fade.py:19-32`). | **Yes — inferred:** rerun DRY. |
| (f) Job 100 / S6 swarm | **Measured (prior pass):** drive-curves JSON absent (`DRY_ALL_REPORT_2026-10-10.md:41`). | **Declaration-proven:** a three-state pipeline contract identifies the next action and refuses orphan curves (`S6OldLadySwarm/swarm_pipeline.py:11-29`); the DRY failure now reports next step and full order (`swarm_sequence.py:138-144`). | **Measured offline:** pipeline 4/4 plus curve generator/tool 17/17 (`test_swarm_pipeline.py:6-22`; `Tools/Mocap/test_s6_old_lady_swarm.py:86`). | **Yes — conditional/inferred:** run the three steps below; not ready to skip directly to DRY. |
| (g) Job 101 / E25 ending | **Measured (prior pass):** no persistent-level opening-curtain actor existed (`DRY_ALL_REPORT_2026-10-10.md:42`). | **Declaration-proven:** the plan now requires the sequence spawnable `Opening Drape (baked)` in `LS_Opening_Curtain_Baked`, records its GeometryCache identity, and clones that template rather than searching the stage census (`E25Ending_20261009/e25_ending.py:27-29`, `:483-502`, `:674-687`). | **Measured offline:** 31/31 (11 positive, 20 negative), including sequence-spawnable identity and wrong-binding refusal (`test_e25_ending.py:129-132`, `:166-167`). | **Yes — inferred:** rerun DRY and pin `opening_curtain_source`. |
| (h) Job 99 / S6 arrival | **Measured (prior pass):** the single DRY required live PIE (`DRY_ALL_REPORT_2026-10-10.md:40`). | **Declaration-proven:** ordinary DRY is now non-PIE actor/component plus sun-setting census; live S6 inspection is a separate conductor-scheduled probe (`P99S6ArrivalSun_20261009/p99_s6_arrival_sun.py:261-288`, `:290-350`, `:539-547`). APPLY requires hashed reports from both (`p99_core.py:106-110`; `p99_s6_arrival_sun.py:436-442`). | **Measured offline:** 29/29, including split-contract and missing-probe refusal (`test_p99_offline.py:46-50`). | **Yes — split:** non-PIE DRY now; schedule PIE probe separately. |

## Required Job 100 run sequence

1. **Editor, read-only, PIE stopped:** execute `Saved/CodexConductor/S6OldLadySwarm/sample_hands.py` via `sample_hands_request.json`; require `S6_OLD_LADY_HAND_SAMPLE_OK`.
2. **Offline:** `python Tools/Mocap/s6_old_lady_swarm.py Saved/CodexConductor/S6OldLadySwarm/hand_samples.json --json DerivedAssets/S6OldLadySwarm/s6_old_lady_swarm_drive.json --png DerivedAssets/S6OldLadySwarm/s6_old_lady_swarm_curves.png`; require `S6_SWARM_CURVES_OK` and review the PNG.
3. **Editor, non-PIE DRY:** execute `swarm_sequence.py` via `swarm_sequence_request.json`; require `S6_SWARM_SEQUENCE_DRY_OK`.

## Required Job 99 split sequence

1. With PIE stopped, run `p99_request.json`; require `P99_S6_DRY_OK|pie=0` and unchanged dirty census.
2. In a separately authorized session, manually pause at S6 arrival and run `p99_pie_probe_request.json`; require `P99_S6_PIE_PROBE_OK`. The probe does not start, stop, or scrub PIE.
3. Stop PIE manually. Pass 2 may proceed only after both report paths and SHA-256 values are pinned and reviewed.

## Aggregate verification

- **Measured offline:** all changed Python sources compile with `python -m py_compile`.
- **Measured offline:** nine harness invocations passed: P87 47/47; S2 14/14; P94 24/24; E18 29/29; pearl 4/4; swarm pipeline 4/4; swarm generator/tool 17/17; E25 31/31; P99 29/29.
- **Measured offline:** `git diff --check` reports no whitespace errors.
- **Inferred / not yet proved:** live DRY success, saved/read-back state, runtime behavior, rendered result, packaging, and creative approval all remain pass-2 work.
- **Declaration-proven scope:** no tools whose pass-1 DRY was OK were edited.
- **Measured delivery limitation:** the required explicit-path commit could not be created because this managed worktree cannot write `E:/PussStage/.git/worktrees/PussStage46/index.lock` (`Permission denied`). All changes remain present but uncommitted in this worktree.
