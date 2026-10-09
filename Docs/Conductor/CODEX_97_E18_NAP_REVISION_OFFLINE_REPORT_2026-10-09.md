# Codex 97 — E18 Nap revision offline delivery

Date: 2026-10-09

## Verdict

- **[measured] OFFLINE TOOLING PASS.** The harness reports 3/3 positive controls,
  15/15 negative controls, and 26/26 checks with no failures
  (`Saved/CodexConductor/NapInterlude_20261009/e18_harness_result.json:1-7`).
- **[UNCLEAR] LIVE, SAVED, RUNTIME, AND RENDERED ACCEPTANCE.** This worktree run
  did not open Unreal, MCP, PIE, or Blender and did not mutate or save packages
  (`Saved/CodexConductor/NapInterlude_20261009/e18_nap_revision.py:1-8`;
  `Docs/Conductor/codex_briefs/_house_rules.md:2-3`). The conductor
  must establish every live tier separately.

## Dedupe evidence and scope

- **[declaration-proven]** Gary's E18 note requires a dark Nap, no cat model,
  ground-level breathing camera, and the exact new label
  (`Docs/Conductor/GARY_PIE_NOTES_2026-10-09_evening.md:22`).
- **[declaration-proven]** The retained diagnostic records old label
  `Nap — battery change` and presave Show GUID
  `211B6129497610E7977707AA939D7763`, but that diagnostic explicitly says its
  stage was presave/not-saved
  (`Saved/CodexConductor/NapInterlude_20261009/nap_diag.json:219-233`). The user
  states E18 was subsequently applied; live DRY must confirm the pair.
- **[declaration-proven]** I2–I5 spot records say `applied=true`; I4's planned
  mouth spot already reaches zero at frame 1700 and unspawns at 1701, before its
  1837 end (`Saved/CodexConductor/shadow_play_spot_record_I4.json:2-52`;
  `Saved/CodexConductor/shadow_play_spot_record_I4.json:217-229`).
- **[inferred]** That historical plan does not prove the live sequence evaluated
  dark after I4 or caused the Nap flood. The new tool therefore audits all five
  live interactions, I4 first, and adds explicit terminal end keys only to the
  two exact named bindings it finds; it refuses a one-spot state
  (`Saved/CodexConductor/NapInterlude_20261009/e18_nap_revision.py:159-215`;
  `Saved/CodexConductor/NapInterlude_20261009/e18_nap_revision.py:415-435`).
- **[inferred]** If live state matches the retained records, the APPLY census is
  exactly eight packages: Show, Master, vertical-slice level, Nap sequence, and
  I2/I3/I4/I5 sequences. No I1 spot record exists in this worktree, which does
  not prove the live I1 sequence has no matching bindings; DRY's all-five audit
  is authoritative and will add I1 only if both exact bindings exist. Searched:
  `Saved/CodexConductor/shadow_play_spot_record_I*.json` (found I2–I5 only).

## Delivered behavior

- **[declaration-proven]** `e18_nap_revision.py` provides DRY/APPLY/REVERT with
  exact confirmation strings and a pure planner. It normalises UE enum strings,
  channel suffixes, and GUIDs using `GuidLibrary.conv_guid_to_string`
  (`Saved/CodexConductor/NapInterlude_20261009/e18_nap_revision.py:70-92`;
  `Saved/CodexConductor/NapInterlude_20261009/e18_nap_revision.py:325-379`).
- **[declaration-proven]** The existing cue is renamed by the recorded GUID; the
  read-only minted `cue_guid` is never assigned. The old GO marker is located by
  `find_marked_frame_by_label`, replaced at the same frame, and Master is rebuilt
  (`Saved/CodexConductor/NapInterlude_20261009/e18_nap_revision.py:484-502`).
- **[declaration-proven]** The planner pins the recorded Master segment to
  1490.64–1511.64 seconds and post-APPLY read-back requires unchanged start/end
  ticks with only the new label (`Saved/CodexConductor/NapInterlude_20261009/e18_nap_revision.py:159-232`).
- **[declaration-proven]** The cat is hidden through the existing Visibility
  track plus actor `bHidden`; the camera receives a 45 cm ground-height,
  seamless 1.25 cm / 0.20 degree four-second breath with AUTO interpolation; the
  two owned lights become 18/8
  (`Saved/CodexConductor/NapInterlude_20261009/e18_nap_revision_settings.py:8-16`;
  `Saved/CodexConductor/NapInterlude_20261009/e18_nap_revision.py:503-520`).
- **[declaration-proven]** APPLY makes a `Backups/PreE18NapRevision-<run>` copy
  and exclusive record before mutation, checks the exact dynamically named
  dirty-package set, saves only it, and performs post-save semantic read-back
  (`Saved/CodexConductor/NapInterlude_20261009/e18_nap_revision.py:454-481`;
  `Saved/CodexConductor/NapInterlude_20261009/e18_nap_revision.py:623-651`).
- **[declaration-proven]** REVERT makes its own backup, restores the complete
  recorded cue/marker, cat, camera, light and spot-channel state, checks the same
  exact census, target-saves, and requires an exact snapshot digest after read-back
  (`Saved/CodexConductor/NapInterlude_20261009/e18_nap_revision.py:546-594`;
  `Saved/CodexConductor/NapInterlude_20261009/e18_nap_revision.py:654-680`).
- **[declaration-proven]** The DRY/APPLY record includes a five-shot plan: entry,
  breath peak, both sides of the vamp seam, and I4 terminal darkness
  (`Saved/CodexConductor/NapInterlude_20261009/e18_nap_revision.py:683-692`).

## Harness and live acceptance

- **[measured]** Positive controls cover planning, DRY→APPLY saved read-back, and
  exact REVERT; negative controls cover identity/marker/Master timing/actor/spot
  cardinality, seam, value, confirm, and terminal-leak failures
  (`Saved/CodexConductor/NapInterlude_20261009/test_e18_nap_revision.py:111-188`).
- **[UNCLEAR]** Remaining gates: exact live census, saved Show/Master/level/sequence
  read-back, both named automation tests, PIE vamp continuity and GO release,
  and rendered proof of no cat, ground-level breath, near-dark Nap, and I1–I5
  terminal darkness (`Saved/CodexConductor/NapInterlude_20261009/README.md:90-124`).

**[measured]** No commit was created: the user assigned live execution and
commit ownership to the conductor (`git status --short`, 2026-10-09 offline run).
