# W&T brief Q15 (--unreal, conductor slot): restore keeper Wing 045 — chain A REVERT TOPPLE-20261009-104822, re-APPLY with --keeper 17
Read _house_rules.md. Rule 2 RELAXED: you may call the Unreal MCP via `python Saved/CodexMocap/mcp_request.py tools/call --params-file <req> --timeout 900`.
Rule 1 EXCEPTION: you run in the MAIN tree. You may write ONLY Saved/CodexFlatV3/topple/** and new files under Saved/CodexFlatV3/q15/. No git.
HARD RULES: NO PIE (never start or end it), no renders/GPU work, never quit/restart the editor, never Save All, no Blender. Klara levels must never be saved. Census (Saved/CodexFlatV3/curtain/census_probe.json → the last CI_CENSUS line, which must be content=[] maps=[] pie=False) before each write. Parse markers by run id. Stop on the first failure; no repairs.
WHY (measured): the 9 Oct re-APPLY TOPPLE-20261009-104822 used make_keys' DEFAULT keeper, which picked Wing 007. So Wing 045, the sliding keeper of the 7 Oct plan (ordinal 17, the 3D-scaffold keeper), went STILL (PlaybackMode Static), and the review still p06_wing045_mid_slide failed PANEL_DID_NOT_MOVE. Do not change chain B's rows, which are excluded by GUID. (Chain B may or may not be applied by now; the conductor's 37b tool owns them.)
1. REVERT 104822 (topple_args.json: mode REVERT, confirm "REVERT TOPPLE TOPPLE-20261009-104822"). Require FLATV3_TOPPLE_REVERT_OK|run=<yours>. Report foreign_edits_kept.
2. Topple DRY: refreshes topple_measurements.json from live data. Require its OK marker.
3. Make the plan:
   - `python Saved/CodexFlatV3/topple/make_keys.py --slam-s 32.477488 --n 6 --end braced --side L --candidate 9 --lead-min-m 23 --keeper 17 --exclude-rows <the 11 cue_guids in Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_plan.json chain_b.rows>`.
   - Back up topple_plan.json first (.bak-20261009-preQ15).
   - Require gates_ok, keeper = "P06 Wing 045", chain L rows OLD 09, Wing 002, 038, 047, OLD 19, 050, brace Wing 007, final impact 32.48 s. Anything else: STOP.
4. APPLY with the plan's confirm, decided_by "Gary (via Conductor 5, option a, 9 Oct; keeper 045 restored)", and the same --exclude-rows. Require OK markers. Restore topple_args.json from topple_args.dry.json.
5. Read back Wing 045's live mechanism: PlaybackMode must be ContinuousLoop (as in topple_originals_TOPPLE-20261007-114412.json's era, i.e. not Static).
6. Run the verifiers: Saved/CodexFlatV3/q14/q14_verifiers_request.json, then read the two "Test Completed. Result={Success}" lines after its Q14_VERIFIERS_QUEUED marker. Census after.
Final message: run ids + markers per step, census before and after, Wing 045 read-back, record paths. Under 250 words.
