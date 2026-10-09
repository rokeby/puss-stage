# W&T brief Q14 (--unreal, Codex job 61b / conductor slot 9 Oct ~14:20): topple chain A REVERT → chain B (job 37b) → chain A re-APPLY at the retimed dusk
Read _house_rules.md. Rule 2 RELAXED: you MAY call the Unreal MCP via `python Saved/CodexMocap/mcp_request.py tools/call --params-file <request.json> --timeout 900`. Editor is freshly restarted, sky hidden, census clean, no PIE.
Rule 1 EXCEPTION (W&T stream owner, this job only): you run in the MAIN tree E:PussStage because the editor reads its Saved/. You MAY write ONLY: Saved/CodexFlatV3/topple/** (args, keys, records), Saved/CodexConductor/P37P06DominoFinale_20261009/** (args, records), Saved/CodexFlatV3/curtain/census_probe.json outputs, and new request/probe JSON files under Saved/CodexFlatV3/q14/. Nothing else in the tree; no git operations.
HARD RULES: NO PIE (never start/end), NO captures/renders/GPU-heavy work (Hyper3D's mask bake may be using the GPU), NEVER quit/restart the editor, NEVER Save All, no Blender. Save only the Show asset + main level that a tool's own APPLY saves. If any step fails, STOP: report the failure markers and do not continue to the next step. Do not attempt a repair.
TRAPS: str(FGuid) is a changing wrapper address: compare GUIDs via unreal.GuidLibrary.conv_guid_to_string or export_text. Parse log markers by run id, never tail -1. Read state back numerically, never by rounded hashes. Klara's levels (L_KK_children, L_Animals) must NEVER be saved. If they show dirty, stop and report.
Census before each write step: run Saved/CodexFlatV3/curtain/census_probe.json and read the last CI_CENSUS line. It must say content=[] maps=[] pie=False. If anything else is dirty, stop.

1. **Chain A field-scoped REVERT.** Tool: Saved/CodexFlatV3/topple/ (topple_run.py, topple_request.json, topple_args.json; the active record is TOPPLE-20261007-114412).
   - Set topple_args.json to mode REVERT, confirm "REVERT TOPPLE TOPPLE-20261007-114412".
   - Require FLATV3_TOPPLE_REVERT_OK|run=<yours>. Report foreign_edits_kept.
   - Restore topple_args.json from topple_args.dry.json.
2. **Chain B (job 37b).** Tool: Saved/CodexConductor/P37P06DominoFinale_20261009/ (domino_finale_run.py / _apply.py / _request.json, args domino_finale_args.json (DRY) and domino_finale_live_args.json).
   - Run DRY first; check that its rows are disjoint from chain A's 6 rows + keeper (topple_plan.json / topple_originals_TOPPLE-20261007-114412.json).
   - Then APPLY per the tool's confirm, with the record keyed by cue GUID + side. Require its OK marker and the record path.
3. **Chain A re-APPLY.**
   - `python Saved/CodexFlatV3/topple/make_keys.py --slam-s 32.477488 --exclude-from-record <chain-B record>`, plus whatever other args the 114412 run used (read its record/args; keep n/end/side).
   - Gates must pass; on NO_WINDOW_FOR_SLAM, stop and report the table.
   - Then topple DRY → APPLY with the new keys. Require the OK markers. Report the creak time and the final impact time (target 32.477488 s P06-relative).
4. **Verify:** run the SavedMasterMatchesShow and SceneCutBindingsResolve automation tests the way existing tools do (see Saved/CodexConductor/_fx_authoring_common.py), and report the pass markers.
Final message: run ids + markers per step, census before/after, record paths, foreign_edits_kept, slam times. Under 250 words.

## Q14c (continuation after run TOPPLE-20261009-102400-Q14R stopped: DRIFT_SINCE_APPLY "P06 Wing 001 mechanism"). Conductor 5's ruling:
A. READ-ONLY field diff first: for EVERY chain-A row in topple_originals_TOPPLE-20261007-114412.json, read the live WingPair.Mechanism and LocalOverrideMask (new read-only probe under Saved/CodexFlatV3/q14/, no writes or saves) and diff them field by field against topple_apply_TOPPLE-20261007-114412.json's after-state (Kind, PlaybackMode, CycleRateHz, PhaseOffsetCycles, PhaseOrigin, L/R/Top curves, and any other field). Name each changed field, with old and new values. Find the likely writer: grep Saved/**/*record*.json, Saved/**/*_apply_*.json and git log since 7 Oct for that cue GUID (in string form via conv_guid_to_string).
B. GATE: proceed ONLY if every drift is (i) on chain-A rows only, AND (ii) only in fields chain A's re-key overwrites anyway (Kind/PlaybackMode/CycleRateHz/PhaseOffsetCycles/PhaseOrigin/curves), AND (iii) LocalOverrideMask is unchanged. Otherwise STOP and report the diff. Do not write anything.
C. If the gate passes: add a narrow `accept_drift_fields` option to the topple REVERT. It names the exact fields, accepts drift only in those fields on those rows, and logs every accepted field with old and new values in the REVERT marker and the record. Run the offline harness (Saved/CodexFlatV3/topple/test_topple_apply.py) with new +/- controls: accepted field passes; a non-listed field and a mask drift both still refuse. Back up topple_apply.py first (.bak-20261009-acceptdrift). Then resume at step 1 (REVERT with the option) and continue through steps 2–4 as written above.

## Q14d (supersedes Q14c; Claude finished A–C by hand, 9 Oct ~14:35 UTC)
MEASURED: read-only dump Saved/CodexFlatV3/q14/q14_live_dump_Q14D-20261009-103147.json. All 28 rows equal APPLY 114412's after_mech_sha EXACTLY once the new EMPTY `SoundCues=` field is dropped. That field was added to InfinityMechanismMotion by build 2604e8f8 (wing mechanism sound). No foreign writer; masks unchanged.
FIX in place: topple_apply.py `_legacy_mech()` drops ONLY an empty SoundCues for the drift sha, the restore round-trip and the REVERT read-back (backup topple_apply.py.bak-20261009-soundcues; harness 17/186/0; +/- controls OK).
DO: run steps 1–4 above as written. Do NOT edit topple_apply.py. Chain B's and make_keys' tools may hit the same SoundCues text trap: if one stops on a text/sha mismatch that is ONLY the empty SoundCues field, STOP and report it. Do not patch it.

## Q14e (resume at STEP 2). Step 1 is DONE: FLATV3_TOPPLE_REVERT_OK run=TOPPLE-20261009-103455. Do NOT rerun it.
The chain B DRY HTTP 400 was a missing MCP envelope in domino_finale_request.json. It is now fixed to {"name":"call_tool","arguments":{...}}; the original is kept as .bak-20261009-envelope. Run steps 2, 3 and 4 as written; same rules; stop on first failure.

## Q14f (Conductor 5 approved new ORDER, 9 Oct ~14:45 UTC). Step 1 REVERT is DONE (TOPPLE-20261009-103455). Never rerun it.
State: chain B APPLY P37DOMINO-20261009-103833 stopped PLAN_STALE. B's plan was made with A active, and the 37b tool requires an active A. The editor census is clean (re-checked 14:38).
F1. Chain A re-APPLY FIRST:
   - `make_keys.py --slam-s 32.477488 --exclude-rows <every cue_guid in domino_finale_plan.json selected_rows>`, keeping the other args of the 7 Oct 114412 run (n/end/side/candidate from topple_plan.json "request");
   - gates must pass (NO_WINDOW_FOR_SLAM → stop with the table);
   - topple DRY → APPLY via topple_args.json and topple_request.json (restore topple_args.json from topple_args.dry.json after);
   - require FLATV3_TOPPLE_*_OK markers by run id. Report the creak and final impact times.
F2. Retire B's prepared record per the 37b tool's rules: rename domino_finale_apply_P37DOMINO-20261009-103833.json to .failed-P37DOMINO-20261009-103833. NEVER delete.
   - Regenerate B's plan with make_domino_finale_plan.py, using the same args file (seed 3706) and fresh measurements (run B's DRY to refresh topple_measurements.json if the tool does that; otherwise use the tool's own measurement path), with --chain-a-active set to the NEW topple_originals_ACTIVE.json. Back up the old domino_finale_plan.json first (.bak-20261009-preA).
   - Check that B's selected_rows are unchanged from the old plan; if they changed, STOP and report.
   - Then B DRY → APPLY. Require its OK markers + the record path. Report B's final impact time.
F3. The verifiers (step 4 above).
The rule-1 exception covers everything in these folders. Stop on the first failure.

## Q14g (GO from Conductor 5 on Gary's choice (a), 9 Oct ~14:55 UTC). REVERT is DONE; never rerun it.
Claude made the chain A plan offline: Saved/CodexFlatV3/topple/topple_plan.json (old copy topple_plan.json.bak-20261009-preQ14). It used make_keys --slam-s 32.477488 --n 6 --end braced --side L --candidate 9 --lead-min-m 23, plus --exclude-rows <B's 11 GUIDs>. Result: gates_ok; chain L = OLD 09, Wing 002, 038, 047, OLD 19, 050, braced on Wing 007; creak 24.89 s, final impact 32.48 s. Do NOT re-run make_keys.
G1. Topple: run the DRY using its plan's inputs. If DRY's live measurement hash differs from the plan, STOP (do not re-run make_keys). Then APPLY with the confirm in the plan ("APPLY TOPPLE P06 still+chain L 884761C0..AA62A3AC #14ad8825"), decided_by "Gary (via Conductor 5, option a, 9 Oct)", and the same exclude rows. Require OK markers; restore topple_args.json from the DRY copy afterwards.
G2 and G3: exactly as F2 and F3 above.
