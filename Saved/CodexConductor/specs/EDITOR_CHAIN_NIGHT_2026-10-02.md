# Editor chain, 2 Oct night (Conductor 4). Built 3d923f5 (AT + PR, suite 116/0/116). Gary approved each step in his
# own words in the Conductor 4 session ("full steam ahead"; hangar-timing defaults: roof from landing, lattice after,
# strike +10 s incl. S3's six Strike lights, S6 dims, S5 standardised; resize P02-P04 to 3:00 DRY RUN ONLY).
# Rules: PIE off + census clean first (else STOP; never end PIE); never quit the editor; never Save All; purge cached
# Saved/ modules before importing helpers; MCP envelope = Saved/CodexConductor/quit_request.json; markers by run id.
STEP 1, HANGAR TIMING APPLY. For each of `S1 Arrival` .. `S6 Arrival`: ReadHangarTiming() (log the values), set the
  defaults (RoofCloseStart = LandSeconds, RoofCloseEnd = LandSeconds+4.5, LatticeStart = RoofCloseEnd, LatticeEnd =
  LatticeStart+4.0, LightStrikeSeconds = 10.0; S6 dim mode on), ApplyHangarTiming(). If the UFUNCTIONs aren't reachable
  from Python, STOP and report what is exposed. BEFORE: backup all six LS_S<N>_HangarRise assets (+ LS_DevScene_03 if
  any S3 light keys live there) to Backups/PreHangarTimingApply-<stamp>. Check INFINITY_HANGAR_TIMING_APPLIED per actor
  (or _REFUSED: STOP). Census = exactly the touched rise assets; save_asset each; read back roof/lattice/strike keys
  per hangar. Then SavedMasterMatchesShow alone. Then landed-preview STATUS (read-only): all six must still read UP
  (the last keys are unchanged); if not, report.
STEP 2, RE-TIME THE S3 WAVE SLIDES to the new strike. Saved/CodexConductor/s3_wave_slides_apply.py: REVERT (its record),
  then make its expected strike frame derived from the strike gate's own reading (not the constant 147), then DRY (expect
  the strike at ~+10 s = frame 240 +/- 1 in LS_DevScene_03 at 24 fps; report) and APPLY. Then SavedMasterMatchesShow and
  SceneCutBindingsResolve singly. Run the offline harness after the code change (update its constants accordingly).
STEP 3, OPENING WALK-IN PROBE (read-only): Saved/CodexConductor/opening_walkin_probe.py; report every value.
STEP 4, PASSAGE RESIZE DRY RUN ONLY for `Passage 2`, `Passage 3`, `Passage 4` to 180.000 s with
  PreserveSpeedAndSpacing via the built ResizePassageToDuration (bDryRun=true). NO APPLY. Write each plan to
  Saved/CodexConductor/passage_resize_dry_<P>.json: old/new pair count, appended rows (source design per appended row),
  new route length vs spline, override-loss list, neighbour overlap check, index shifts, Master range delta, artist-owned
  content not rippling, refusal reasons. Census must stay empty.
FINAL MESSAGE: markers verbatim per step, backups, censuses, the three dry-run summaries in a table; tags per AGENTS.md.
Commit nothing.
