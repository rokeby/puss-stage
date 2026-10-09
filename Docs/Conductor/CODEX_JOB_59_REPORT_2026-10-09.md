# Codex job 59 — batch 51c DRY-refusal repairs

Offline only. No Unreal, MCP, PIE, Blender, package save, content mutation, or commit was performed.
Job 34 files were not touched.

## Results by refusal

- **[measured, live batch evidence] Job 44:** I1/I3/I4/I5 refused the new
  `GO <n> PASS curtain` labels (`E:/PussStage/Saved/CodexConductor/EDITOR_BATCH1C_REPORT.json:81-105`).
  **[declaration-proven]** `beats_from_markers` now accepts only the Gary-approved PASS
  suffix `curtain`; another PASS suffix still refuses as `GO_PASS_LABEL`
  (`Saved/CodexConductor/shadow_play_spot.py:199-218`).

- **[measured, live batch evidence] Jobs 38/40:** B06 has two active transform sections,
  which tripped the one-section assertions (`E:/PussStage/Saved/CodexConductor/EDITOR_BATCH1C_REPORT.json:137-145`).
  **[declaration-proven]** both tools now evaluate every keyed time from all active
  sections as exactly one ABSOLUTE pose plus zero or more ADDITIVE layers; zero/two
  absolute owners and unknown blend types still refuse
  (`Saved/CodexConductor/P38S3Grounding_20261009/p38_editor.py:456-517`;
  `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:180-266`).

- **[measured, live batch evidence] Pearl fade:** run 51c found one existing fade track
  (`E:/PussStage/Saved/CodexConductor/EDITOR_BATCH1C_REPORT.json:153`).
  **[declaration-proven]** the tool now resolves existing actor/component bindings before
  `add_possessable`, reuses exact matching visibility/material tracks, adopts unbound or
  inert visibility tracks onto `bHidden/bHidden`, and refuses detailed section, key,
  property/path, count, or binding drift (`Saved/CodexConductor/s3_pearl_fade.py:36-80,111-229`).

- **[measured, live batch evidence] S3 orbit:** run 51c stopped at `ORBIT_SHAPE`
  (`E:/PussStage/Saved/CodexConductor/EDITOR_BATCH1C_REPORT.json:161`).
  **[inferred from a measured saved snapshot]** the orbit is already centred on the new
  clam; its X/Y lattice remains 721 keys, while later creative Z keys at frames 1847 and
  1881 made the exact-three-channel-count check stale
  (`E:/PussStage/Saved/CodexConductor/S3Polish_20261009/s3_polish_dry_S3POLISH-DRY-4.json:288181,294782-294854`).
  **[declaration-proven]** the replacement validates the exact X/Y lattice, requires the
  full Z baseline, preserves extra finite Z keys, classifies old/target/other centre, and
  refuses a duplicate APPLY when already applied (`Saved/CodexConductor/s3_shots_fix.py:46-72,105-176`).

- **[measured, live batch evidence] ClamSlime:** `apply_ready=0` accompanied
  `record=0|actor=0|binding=0` (`E:/PussStage/Saved/CodexConductor/EDITOR_BATCH1C_REPORT.json:169`).
  **[declaration-proven]** the missing prerequisite is IMPORT, not a missing manual actor
  step. DRY now emits `next=IMPORT` and records the prerequisite; the queue and runbook
  explicitly require IMPORT → re-DRY → APPLY
  (`Saved/CodexConductor/ClamSlime_20261008/slime_apply_ue.py:719-754`;
  `Docs/Conductor/CLAM_SLIME_RUNBOOK_2026-10-09.md:1-20`;
  `Docs/Conductor/POSTBAKE_QUEUE_2026-10-09.md:27`).

## Offline regression proof

**[measured]** Current offline runs passed: interaction transition 57/57; underlying
shadow-play spot 91/91; P38 53/53; P40 33/33; pearl fade 3/3; S3 orbit 4/4;
ClamSlime 69/69. Each refusal repair includes the requested triplet: old logic refuses
the logged fixture, new logic passes it, and real semantic drift still refuses
(`Saved/CodexConductor/test_interaction_shadow_transition.py:175-190`;
`Saved/CodexConductor/P38S3Grounding_20261009/test_p38.py:104-115`;
`Saved/CodexConductor/P40Shore05Settle_20261009/test_p40.py:76-85`;
`Saved/CodexConductor/test_s3_pearl_fade.py:19-31`;
`Saved/CodexConductor/test_s3_shots_fix.py:26-39`;
`Saved/CodexConductor/ClamSlime_20261008/test_slime_apply_ue.py:649-670`).

## Acceptance boundary

**[measured]** Python compilation and the offline harnesses pass. **[inferred/unverified]**
the next live DRYs should clear these specific refusals, but no current-editor DRY,
APPLY, saved read-back, PIE, rendered look, or package acceptance is claimed.
