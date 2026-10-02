# Passage resize, route A (Gary, 2 Oct, his own answers in the Conductor 4 session)
Gary: placeholder lengths until final music; "set any mistimed passages at 3 min", "only short ones or ones for which music
isn't set", and route "A since that's more like where we'll need to end up" = PRESERVE WALK SPEED AND SPACING, DERIVE THE
WING COUNT (append copied WingPairs). Targets: P01, P02, P03, P04 -> 180.000 s each. P05 (186.4) and P06 (110.6) untouched.
Background (read it): Saved/CodexRuns/last-message-* of passage_length_investigation.log (the verdict with file:line).
Duration = LeadInFrames + sum(IntervalToNext) + TailFrames (InfinityStageCompiler.cpp:240-312); count-refit appends rows with
NEW GUIDs, copies the design pattern, clears local override bits (InfinityStageWingSequenceInterchange.cpp:693-740);
Refit-from-Music overwrites the duration from the Rail (SInfinityStageCueDesk.cpp:4894-4917) -> NOT usable as-is.

## Tool `Saved/CodexConductor/passage_resize_apply.py` (DRY / APPLY / REVERT)
- Find a route that reaches the existing solver + resize WITHOUT the Rail duration override: first check whether the
  solver / count-resize / materialize / Master rebuild are exposed to Python (BlueprintCallable/editor library). If they are,
  use them. If not, STOP the Python route and instead produce a HELD C++ patch adding one narrow BlueprintCallable editor
  function `ResizePassageToDuration(PassageGuid, TargetSeconds, Policy=PreserveSpeedAndSpacing, bDryRun)` that returns a
  plan struct and applies it (Scripts/patches/2026-10-02_PR_passage_resize.patch, tree restored, no build).
- Per passage the DRY plan reports: old/new count, pairs appended, old/new duration (assert exactly 180.000 s: the
  residual bug at InfinityStageCompiler.cpp:344-358 must be handled: refuse unless residual == 0 or absorbed into
  TailFrames/TailDistanceCm explicitly), old/new route length vs the passage's spline length (REFUSE if the route would need
  Auto Fit on a shaped spline: InfinityStagePassageActor.cpp:768-821; report the required length), rows with local
  timing/layout override bits that a refit would erase (list them; REFUSE unless --accept-override-loss), every later cue's
  index shift (old->new index per GUID; Wings and Textures key swaps by index+GUID), Master playback range delta, managed
  sections moving, and ARTIST-owned Master content (tracks/markers/keys not managed by GUID) that would NOT ripple: list it.
- Physical layout: report each resized passage's new world extent against its neighbours (hangars/scenes docking at clean
  passage ends: Docs memory "structure invariants"); REFUSE on overlap.
- APPLY (one passage per run, P02 first): backup Show + Master + level + affected Passage assets to
  Backups/PrePassageResize-<P>-<stamp>; resize; materialize ONLY that passage; rebuild the Master; rematch the following
  Scene's handoff (Soft goods' extend_scene_playback.py rematch_only=true for that Scene); targeted saves; read back the
  duration, count, GUIDs and the index map; SavedMasterMatchesShow + SceneCutBindingsResolve singly. REVERT restores the
  backup files with the editor closed (document the steps; never reload the open level from Python).
- Harness `test_passage_resize_plan.py` (offline): + 47.4 s/23 pairs -> 180 s at 2.5 m/s, 5 m spacing (count, appended,
  exact duration); − residual not closing, shaped route too short, override bits present, overlap with neighbour.
THIS PASS: investigate the exposure question, write the tool or the held patch + harness, run the harness only.
NO Unreal (Wings and Textures hold the editor), NO build. Commit nothing. Final message tagged per AGENTS.md tiers.
STANDING RULES: never end PIE, never quit the editor, no Sequencer UI/eval/scrub, never Save All, no reloads.
