# Make the S2/S5/S6 hangars rise (Gary: "Lengthen to fit the rise", and confirmed in PIE they don't rise; his own words in the
# Conductor 4 session). Cause (measured, probe 3 Oct): LS_DevScene_02/05/06 lack the `Hangar Fold` subsection of their rise
# (S1/S3/S4 have it at 0, row 0, no offsets, KeepState); rises are 31 s (S2, S6) and 49 s (S5); Scenes are 25 s.
Rules: PIE off + census clean first (never end anyone's PIE), never quit, never Save All, purge cached Saved/ modules, MCP
envelope from Saved/CodexConductor/quit_request.json, markers by run id. Stop on failure.
1. Lengthen: LS_DevScene_02 25 -> 31 s, LS_DevScene_06 25 -> 31 s, LS_DevScene_05 25 -> 49 s, with
   Saved/CodexSoftGoods/extend_scene_playback.py (DRY, APPLY, rematch_only each), as on 2 Oct evening.
2. Nest: Saved/CodexStructure/nest_apply.py (read it and its S1/S3 wrappers nest_s1_apply_run.py etc.; same pattern: a
   `Hangar Fold` subsection at 0, row 0, full rise duration, no offsets, KeepState) for S2, S5, S6: DRY then APPLY each, with
   its own backups and read-back.
3. SavedMasterMatchesShow and SceneCutBindingsResolve singly (run_saved_master_test_request.json, run_scene_cut_test_request.json);
   landed-preview STATUS (all six UP).
4. PROOF IN PIE (own PIE only, short): start PIE (the New Editor Window route used by Saved/CodexConductor PieRecording runs, with
   the ownership flag), let the transport jump to each of P02/P05/P06's last 5 s and play 15 s into S2/S5/S6, then end OUR PIE.
   From the log: no `INFINITY_STAGE_ARRIVAL_WAITING ... NotNested` for S2/S5/S6, and each Arrival's active/initial-pose markers.
   Census clean after.
FINAL MESSAGE SHORT: markers per step, backups, the PIE proof lines; tags per AGENTS.md. Commit nothing.
