# Job 90b offline delivery - I2 reference / I3 darkness / cut lighting

## Result

- **declaration-proven:** `Saved/CodexConductor/Interaction90b_20261009/`
  contains guarded DRY/APPLY/REVERT tooling, request/runner, arguments, offline
  harness, transaction record contract, exact dirty census, targeted saves,
  read-back gates, success markers, and a stills plan
  (`interaction_90b.py:271-285,536-555,606-711,715-745`;
  `README.md:6-35`).
- **declaration-proven:** I2 preserves all keys before the live sleight cut,
  holds the job-34/60 close pose through the existing `CST drop`, then samples a
  smooth path whose final transform is the live P03 start pose. APPLY requires
  the camera to change sides of the mouth-curtain plane
  (`interaction_90b.py:129-168,414-439`).
- **declaration-proven:** S3 reaches full black on its final displayed frame;
  I3 keeps its cuts, curtain sections, playback end and mouth-camera end outside
  the mutation set. I3 remains black while the existing hangar camera moves,
  then reveals while the I2-reference shadow intensities rise
  (`interaction_90b.py:171-197,404-412,485-501,548-555,659-667`).
- **declaration-proven:** all I1-I5 sleight cuts receive a shadow-spot census.
  The job-39 F17 math also inventories world/spawned lights, PP exposure and
  fog, ranks differences and emits proposals. Fixes remain explicit; no
  creative step is guessed offline (`interaction_90b.py:200-212,448-483,502-517,557-597`).
- **measured-offline:** the harness result is recorded in
  `harness_result.json`: 16 pass / 0 fail, including positive and negative
  controls (`test_interaction_90b.py:30-83,100-126`). This proves planner/guard
  behavior, not Unreal state.
- **UNCLEAR:** no Unreal, PIE, MCP or Blender was used. Engine-minted binding
  identities, saved persistence, darkness, lighting match and visual acceptance
  require the ordered conductor run in the bundle README.

## Dedupe

- **declaration-proven:** job 34/60 already owns the pre-cut I2 push-in and its
  live-derived cut/component identities; 90b preserves that pre-cut curve
  (`Docs/Conductor/codex_briefs/p34_i2_sleight_move_in.md:28-34`;
  `Saved/CodexConductor/I2SleightMoveIn_20261009/README.md:37-45,117-119`).
- **declaration-proven:** job 39 already defines F17 as a lights/spot/exposure/
  fog cut census and F18 as the post-drop movement investigation; 90b reuses
  that math rather than introducing another lighting model
  (`Docs/Conductor/codex_briefs/p39_i2_polish.md:20-32`).
- **measured-offline:** `git log --all --grep=90b`, tracked-path searches, and
  tool/record searches found no prior job-90b delivery. Existing I2 tools and
  records were retained; none were edited.

## Non-ownership guard

Jobs 89/90 timing is not rewritten: I1 is audit-only unless an explicit F17
step is supplied; P02 is not addressed; curtain-drop sections are never edited.
