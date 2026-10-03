# Build ATF + re-apply hangar timing (Conductor 4, 2 Oct night; Gary "full steam ahead" + his timing answers, his own words
# in the Conductor 4 session). Procedure as specs/BUILD_WINDOW_AT_PR.md (marker method, filter EXACTLY `InfinityStage`,
# revert on red to 116/0/116 @3d923f5). Stop at the first failure. MCP envelope: Saved/CodexConductor/quit_request.json.
1. Close: run Saved/CodexConductor/quit_request.json via Saved/CodexMocap/mcp_request.py (quit_editor_clean.py refuses unless
   dirty 0/0). Confirm no UnrealEditor.exe. Never Stop-Process.
2. Apply Scripts/patches/2026-10-02_ATF_strike_rule_fix.patch (--ignore-whitespace; check first). Build. Markers with +/-
   controls (new test names UTF-8 in the tests DLL: TimingKeepsDuringRiseGlow, TimingStrikeIsRelativeToLanding).
3. Each new/changed timing test alone, then the suite. Baseline 116; expect 118/0/118. Red -> revert, rebuild, confirm 116.
4. Commit: "Build 2 Oct night: ATF strike rule fix; suite N/0/N". Relaunch the editor; wait for MCP; census empty, PIE off.
5. Backup the six LS_S<N>_HangarRise to Backups/PreHangarTimingApply2-<stamp>. For S1..S6 Arrival: ReadHangarTiming();
   set RoofCloseStart=LandSeconds, RoofCloseEnd=LandSeconds+4.5, LatticeStart=RoofCloseEnd, LatticeEnd=LatticeStart+4.0,
   StrikeAfterLandSeconds=5.8667 (S6 dim mode); ApplyHangarTiming(). Any _REFUSED -> STOP (report; nothing saved for it).
   Census = exactly the touched rise assets; save_asset each.
6. VERIFY with Saved/CodexConductor/hangar_light_keys_probe.py (request json exists; read-only): expect S1-S4,S6? uplights
   at 10.000/10.133/10.300 (S6: no strike, dimming), glow/practical first ramps UNCHANGED at -5.867, S5 uplights ~31.17+,
   S3 Strike lights' earliest at 10.0. Any mismatch -> STOP and report (the conductor restores from the step-5 backup).
   Then run_saved_master_test_request.json (SavedMasterMatchesShow) and landed-preview STATUS (all six UP).
7. S3 wave slides re-time: Saved/CodexConductor/s3_wave_slides_apply.py REVERT (record exists), then DRY (its gate derives the
   expected frame from the measured strike: expect ~240), APPLY; then SavedMasterMatchesShow and SceneCutBindingsResolve
   (run_scene_cut_test_request.json) singly. Final census empty.
FINAL MESSAGE: markers per step, suite N/F/T, commit hash, backups, the probe lines; tags per AGENTS.md.
