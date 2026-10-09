# P38 — S3 grounding, +50% camera-wall handprints, lid, 0:04 spoiler (9 Oct 2026)

**Status: OFFLINE DELIVERY ONLY. Nothing was applied.** No saved Unreal read-back, PIE/runtime result, or rendered
acceptance exists from this stream. Tiers below are per claim: **declaration-proven** = code/config states it;
**binary-proven** = decoded saved asset evidence; **measured** = offline command/harness result; **inferred** = needs
the named live/rendered check; **unclear** = the tool must not choose yet.

## Outcome by brief item

### A/B — dune/fire-shadow probe and gated fix

- **[declaration-proven]** `s3_ground_probe.py` is read-only and routes to a probe that inventories both named fire
  lights, dune mobility/material/two-sided state, cast flags, sampled LOD0 polygon normals, surface height by dune
  trace with a bounds fallback, and current-pose lowest foot bones. It verifies that dirty state did not change
  (`Saved/CodexConductor/P38S3Grounding_20261009/p38_editor.py:176-310`).
- **[declaration-proven]** Candidate ranking can return `UNCLEAR`; bounds-only surface estimates and non-sequence-
  evaluated feet cannot prove a cause. A fix is refused unless the probe records a matching `PROVED` candidate
  (`Saved/CodexConductor/P38S3Grounding_20261009/p38_core.py:159-253`).
- **[declaration-proven]** The fix tool supports parameterized light-Z lift, shadow bias, and a **new** two-sided MI
  child. APPLY writes a record and `Backups/PreP38GroundFix-<run>` first, target-saves the map, and requires a later
  VERIFY read-back; REVERT restores exact values and retains the MI rather than deleting it
  (`Saved/CodexConductor/P38S3Grounding_20261009/p38_editor.py:331-449`).
- **[unclear]** No cause or fix is selected offline. The first live ground probe must decide; if its verdict remains
  `UNCLEAR`, stop. The current-pose foot sample explicitly is not a sequence-evaluated pose
  (`Saved/CodexConductor/P38S3Grounding_20261009/p38_editor.py:251-283`).

### C — handprints +50% on the camera wall

- **[binary-proven]** The saved S3 dump carries four B06 camera translation keys at world X 14072.5889–14866.1523,
  Y 160976.0312–160994.0312, Z 188.8662–220.1756
  (`Saved/CodexConductor/S3Diag/ds03_now_sem.json:6507-6581`).
- **[measured]** The offline geometric planner selected `S3 Hangar Right Wall` by camera-path distance—not UE ±Y—
  counted 544 existing grease marks on it, and planned `ceil(544 × 0.5) = 272` additions with seed 3803
  (`Saved/CodexConductor/P38S3Grounding_20261009/handprints_topdown_offline.json:2-9`,
  `Saved/CodexConductor/P38S3Grounding_20261009/handprints_topdown_offline.json:54-65`).
- **[declaration-proven]** Live DRY re-derives the wall from current B06 keys and wall bounds, recounts saved actors,
  reuses their grease/tint materials and decal fields, and emits a dependency-free top-down PNG. APPLY only adds
  owned `P38.S3Handprints` actors; REVERT removes exactly those labels
  (`Saved/CodexConductor/P38S3Grounding_20261009/p38_editor.py:574-659`).
- **[inferred]** The PNG is analytical, not an Unreal render. Gary must approve distribution/legibility before APPLY;
  live DRY may produce a different count if the level changed
  (`Saved/CodexConductor/P38S3Grounding_20261009/handprints_topdown_offline.json:6-9`).

### D — F20 lid

- **[declaration-proven]** The probe reports S3 roof rotation keys, root/lattice context keys, Arrival initial-transform
  drives, lid visibility tracks/actor flags, and smoke/haze/fog actors whose bounds overlap the roof opening
  (`Saved/CodexConductor/P38S3Grounding_20261009/p38_editor.py:660-724`).
- **[declaration-proven]** Default DRY/APPLY preserves every roof-key time and holds the final key's rotation value for
  the full rise; `closed_value_deg` can explicitly override this after probe review. APPLY/VERIFY/REVERT save only
  `LS_S3_HangarRise` (`Saved/CodexConductor/P38S3Grounding_20261009/p38_core.py:255-263`;
  `Saved/CodexConductor/P38S3Grounding_20261009/p38_editor.py:736-782`).
- **[inferred]** “Final key = shut” is the safe default interpretation, not visual proof. Confirm it from the probe and
  a rendered rise; smoke “potentially visible” is geometry/flag evidence only
  (`Saved/CodexConductor/P38S3Grounding_20261009/p38_args.json:46-50`).

### E — P03 score-light spoiler

- **[declaration-proven]** DRY discovers P03 SCORE light actors plus practical bulbs, resolves existing bindings before
  `add_possessable`, evaluates any existing visibility channel with `sequence.make_range(frame, 1)`, and targets only
  actors visible at the configured cut (`Saved/CodexConductor/P38S3Grounding_20261009/p38_editor.py:802-909`).
- **[declaration-proven]** The visibility track binds `("bHidden","bHidden")`; its bool keys use **VISIBLE** semantics:
  `True` at sequence start and `False` at the cut. Existing tracks are snapshotted/restored; new bindings are guarded
  against the UE reuse/rename trap (`Saved/CodexConductor/P38S3Grounding_20261009/p38_core.py:266-271`;
  `Saved/CodexConductor/P38S3Grounding_20261009/p38_editor.py:878-982`).
- **[inferred]** `cut_seconds=4.0` is an argument, not a verified current cut. Live DRY derives its display-frame value;
  confirm it against the S3 edit before APPLY
  (`Saved/CodexConductor/P38S3Grounding_20261009/p38_args.json:52-56`).

## Shared safety and offline verification

- **[declaration-proven]** Every mutating path has exact confirms, clean/expected dirty-package census, record plus
  backup before mutation, named saves only, read-back markers with run id, and drift-refusing REVERT. There is no Save
  All or permanent file deletion (`Saved/CodexConductor/P38S3Grounding_20261009/p38_editor.py:79-144`,
  `Saved/CodexConductor/P38S3Grounding_20261009/p38_editor.py:878-982`).
- **[measured]** Offline harness: **50 pass / 0 fail** across ground probe, ground fix, handprints, lid, spoiler, and
  static safety/API controls (`Saved/CodexConductor/P38S3Grounding_20261009/harness_result.json:2-37`).
- **[measured]** `py_compile` passed for core, editor, preview, runner, and dedicated probe in the harness
  (`Saved/CodexConductor/P38S3Grounding_20261009/test_p38.py:130-143`).

## Conductor order

1. Rerun preview then harness (commands in bundle `README.md`).
2. Clean editor/map: `ground_probe` DRY. Inspect `s3_ground_probe_latest.json`; run `ground_fix` only if exactly one
   supported fix matches a `PROVED` candidate: DRY → APPLY → later VERIFY.
3. `handprints`: DRY; show its fresh PNG to Gary; on approval APPLY → later VERIFY.
4. `lid_probe` DRY; confirm closed endpoint and smoke list; then `lid` DRY → APPLY → later VERIFY.
5. `spoiler` DRY; confirm the derived frame/actor list; then APPLY → later VERIFY.
6. After each APPLY require clean census and marker. Capture rendered S3/fire/lid/spoiler review; automation is not
   visual acceptance. Use each operation's REVERT confirm only with an unchanged recorded target.

**[declaration-proven] Commit:** none, per the brief's “the conductor commits” instruction
(`Docs/Conductor/codex_briefs/p38_s3_grounding_handprints_lid.md:42`).

**[measured] Git handoff:** the sandbox could not create the shared worktree `index.lock`, so the files remain present
but unstaged. The exact conductor `git add -f` command is recorded because `Saved/Codex*/**` data/PNG/Markdown files
are ignored by default (`Saved/CodexConductor/P38S3Grounding_20261009/git_handoff.json:1-6`).
