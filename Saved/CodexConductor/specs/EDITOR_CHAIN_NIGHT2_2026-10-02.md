# Night chain, part 2 (Conductor 4). Same rules as EDITOR_CHAIN_NIGHT_2026-10-02.md (PIE/census gate, never end PIE,
# never quit, never Save All, purge cached modules, MCP envelope from quit_request.json). Stop at the first failure.
STEP A, S3 STANDARD LIGHTS TO +10 s (Gary: all S3 lights strike at +10 s). The built ApplyHangarTiming for S3 moved only
  the six `S3 Strike` lights (lights=6 vs 41 elsewhere): a code bug, fixed later in C++. Now: a Python tool
  Saved/CodexConductor/s3_standard_lights_retime.py (DRY/APPLY/REVERT, record) that, in LS_S3_HangarRise, finds the
  same families the C++ uses for other hangars (S3 Uplight*, S3 Practical*, S3 Lattice Glow*; read the family rule from
  InfinityStageArrival.cpp in 3d923f5 and cite the line) and shifts each light's zero->on strike ramp so the earliest
  standard-light strike lands at 10.0 s, preserving per-light offsets and ramp shapes; values unchanged; nothing else
  touched. DRY first (report every channel's before/after keys), then APPLY: backup LS_S3_HangarRise to
  Backups/PreS3StdLightsRetime-<stamp>, save that asset only, read back, SavedMasterMatchesShow alone.
STEP B, S5 STRIKE RELATIVE TO ITS LANDING. On `S5 Arrival`: ReadHangarTiming(), set LightStrikeSeconds = LandSeconds +
  5.8667 (the standard hangars' strike-after-landing: 10.0 - 4.1333), keep the roof/lattice values it has now, then
  ApplyHangarTiming(). Backup LS_S5_HangarRise first (Backups/PreS5StrikeRelative-<stamp>); save that asset only; read
  back; expect INFINITY_HANGAR_TIMING_APPLIED|actor=S5 Arrival ... strike=<~31.17>.
STEP C, S3 WAVE SLIDES re-apply: DRY must now read the strike at frame 240 +/- 1 (the uncommitted derived-gate code from
  part 1 stays). APPLY, then SavedMasterMatchesShow and SceneCutBindingsResolve singly; run the offline harness.
STEP D = part 1 STEP 3 (Opening probe, read-only). STEP E = part 1 STEP 4 (resize DRY RUNS ONLY for P02-P04).
Then landed-preview STATUS: all six UP. FINAL MESSAGE: markers per step, backups, censuses, the three resize dry-run
summaries (table), the probe values; tags per AGENTS.md. Commit nothing.
