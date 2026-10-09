# Job 97 / E18 Nap revision — conductor runbook

Status: offline-authored and offline-harnessed only. No Unreal, MCP, PIE, Blender,
Show asset, level, or package save was opened or run in this worktree.

## Dedupe and ownership

This is an in-place revision of the applied P79 Nap. It does not insert another
cue or create another sequence. The hard identity anchor is the recorded minted
GUID `211B6129497610E7977707AA939D7763` plus the old exact label. The tool never
writes `cue_guid`.

It owns only:

- that cue's label and its one `GO 45 PASS ...` marker (same frame);
- the existing P79 cat visibility, camera Z/roll channels, and two P79 light
  intensities;
- terminal zero-intensity and unspawned keys on already-existing bindings named
  `Shadow Play Spot (Hangar)` / `(Mouth)` in I1–I5.

I4 is audited first. Each interaction must contain either both named bindings or
neither; a one-spot state refuses. A zero count is recorded as absent and is not
invented. Vamp markers, cue timing, sequence ranges, and GO PASS semantics are
read back unchanged.

Creative defaults live in `e18_nap_revision_settings.py`: camera Z 45 cm,
1.25 cm rise/fall, 0.20 degree roll, four-second seamless cycle, and near-dark
P79 light intensities 18/8. The cat is hidden both by `AActor::bHidden` and the
existing visibility channel (whose values are visible semantics: False means
hidden). Camera transform keys use AUTO interpolation.

## Ordered live run

1. Open the canonical Puss vertical-slice world; stop PIE/SIE; close Sequencer;
   require an empty dirty-package census. Do not Save All.
2. Edit `e18_nap_revision_settings.py` with a unique run id and
   `mode="DRY"`, `confirm="DRY E18 <run>"`. Execute
   `e18_nap_revision_run.py` through `e18_nap_revision_request.json`. Require
   `E18_NAP_REVISION_DRY_OK` and `writes=0`.
3. Review the DRY JSON, analytical PNG, dynamic exact package list, I4-first
   all-interaction census, and creative defaults. The expected production census
   is Show + Master + level + Nap sequence + each interaction sequence that
   actually has the two spots; DRY is authoritative.
4. Without changing state or plan, use a fresh run id with `mode="APPLY"` and
   `confirm="APPLY E18 <run>"`. APPLY creates
   `Backups/PreE18NapRevision-<run>` and an exclusive record before mutation,
   requires the exact dirty census, saves only the DRY-named packages, reloads
   semantically, and emits `E18_NAP_REVISION_APPLY_OK` only after clean read-back.
5. Run `InfinityStage.Editor.SavedMasterMatchesShow` and
   `InfinityStage.Editor.SceneCutBindingsResolve` separately. Transport success
   is not either test result.
6. Capture the stills plan from the APPLY record: Nap frame 0, breath peak,
   pre/post-vamp seam, and I4's last frame. In PIE verify no cat, ground-level
   CAT'S VIEW, smooth camera breath, near-dark ambience, repeated seam, one GO 45
   release, unchanged P05 handoff, and terminal darkness for I1–I5.

## REVERT

From the exact applied state, use `mode="REVERT"`, a new run id,
`source_run_id="<apply-run>"`, and `confirm="REVERT E18 <apply-run>"`.
REVERT first creates `Backups/PreE18NapRevisionRevert-<run>`, restores the
recorded cue/marker, cat, camera, lights, and complete original spot channels,
requires the same exact dirty census, target-saves only those packages, and
requires exact semantic read-back before `E18_NAP_REVISION_REVERT_OK`.

Offline harness:

```powershell
python Saved/CodexConductor/NapInterlude_20261009/test_e18_nap_revision.py
```

Expected: `E18_NAP_REVISION_HARNESS_OK|positive=3/3|negative=15/15|checks=26/26`.
