# P39 — Interaction 2 polish: boundary glitch, sleight-cut lighting, the slow lowering, the playhead run-on (Codex, offline)

Read `_house_rules.md` first; every rule applies. Offline only. Conductor runs editor steps. Coordinate with P34 (I2
sleight move-in, finishing touches) and P24 (shrink I2 to 1950): P24 runs FIRST, P34 next, then this.

## Gary (8–9 Oct, his words)
- "i2 with the boy shadow initially cut to P03? then glitched back to P02." (I2 start)
- F17: at ~49–50 s "the lighting dramatically shifts … because we just switched out of the scene. It switches again at
  the end … because we did the sleight of hand thing, but we need to make that not obvious."
- F18: after the curtain falls at ~1:07, "we sort of slowly lower onto [P03], and there's no obvious need for that at all"
  — cut the slow lowering.
- Playhead "should play straight through at 1:06.09 when it moves to next cue" (GO 20 now PASS, GOREL-ALL5-APPLY-1 —
  check whether anything else still holds).

## Known facts
- [measured 9 Oct probe_s2_shots.json] LS_DevScene_02 root cuts: Entry Handoff [0,3866], Exit Handoff [3866,3891];
  Klara's nested "Replacement Shot" sub [376,3891] outranks root cuts (memory: nested shot cuts outrank root).
  [inferred] the root cuts surface only on the boundary frame -> exit cam (P03 side) then entry cam (P02 side) = Gary's
  glitch. Finishing touches measured a 1-frame "Exit Handoff Camera" at the S2->I2 boundary (master 17524657).
- I2 tools: `Saved/CodexConductor/I2Order_20261008/`, `I2HangarCam_20261009/` (P27 applied), P34 brief.
- Camera handover rules: `puss-camera-handover-facts` (GetViewTarget mid-blend = incoming; cut tracks must cover
  playback; bindings must resolve in the show level). Tests that must stay green: SavedMasterMatchesShow,
  SceneCutBindingsResolve.

## Build
1. **Boundary probe** (PIE-only, read-only): frame-step the S2->I2 seam (and S1->I1, S3->I3 etc. for the same pattern)
   logging the view target per frame; stamp run ids. Proves or refutes the inferred cause.
2. **Fix** DRY/APPLY/REVERT: make the root cut at each Scene's tail resolve to the SAME camera as the nested shot's
   last frame (or extend the nested sub's coverage), never leaving a frame on a handoff cam. Record + backup.
3. **F17 lighting diff**: read-only diff of lights / spot keys / camera post-process exposure / fog across each sleight
   cut (Hangar <-> Mouth) and the smallest matching fix as an opt-in part.
4. **F18**: find what moves in I2's last ~30 s (camera / hangar arrival / route) and propose end-at-curtain-fall or
   hold; DRY/APPLY.
5. **Run-on**: list every GO/HOLD/Vamp marker still in I2 + the Master around 1:06.09; report whether play-through
   is now guaranteed.
Harness with +/- controls. Report with tiers. Deliver in your worktree; conductor commits.
