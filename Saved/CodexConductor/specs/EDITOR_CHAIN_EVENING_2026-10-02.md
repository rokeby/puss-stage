# Editor chain, 2 Oct evening (Conductor 4). Gary approved each item in his own words in the Conductor 4 session
# ("full steam ahead"; "Lengthen to fit the rise"; P01 "make sure it plays"). Stop at the first failure. Every step:
# PIE off and census clean first (else STOP; never end PIE); never quit the editor; never Save All; purge cached
# Saved/ modules before importing helpers (memory: stale module cache); read markers by run id from the log.
STEP 1: P01 wing score. Saved/CodexConductor/p01_score_shift.py DRY. Expect the 3-key score, constant offset +15.0 s.
  If the DRY doesn't report exactly that, STOP. Then APPLY (its backup, Master-only save, read-back), then
  InfinityStage.Editor.SavedMasterMatchesShow alone. Census empty after.
STEP 2: Opening walk-in PROBE, READ-ONLY: Saved/CodexConductor/opening_walkin_probe.py. Report every value it measures;
  write the result JSON it defines. No keys, no saves. Census unchanged.
STEP 3: Lengthen Scenes 2, 5 and 6 from 15.0 s to 25.0 s each (placeholder so their hangar rise, roof, lattice and the
  S6 dim complete; final lengths come with content). Tool: Saved/CodexSoftGoods/extend_scene_playback.py (read its
  header and modes first; it handles SCENE cues; its old "SetRange-only" key warning is stale: patch K's MoveSection is
  built). Per Scene: DRY, then APPLY (its own backup), then rematch_only for that Scene's handoff, as the tool requires.
  After all three: SavedMasterMatchesShow and SceneCutBindingsResolve, singly. Then landed-preview STATUS (read-only):
  all six hangars must still read UP. Census empty at the end.
FINAL MESSAGE: markers verbatim per step, backups, censuses, the probe's values; tags per AGENTS.md. Commit nothing.
