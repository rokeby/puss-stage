# Run brief for Codex (`Scripts/codex.sh --unreal`): Scene 3 steps 1 → 2a → 2b → 3 in the open editor

You RUN four reviewed, committed tools. You write NO code and edit NO file. Gary approved every write (1 Oct, Rig &
atmosphere session), and the conductor grants this editor slot.

## Transport (the only allowed call)
`python Saved/CodexMocap/mcp_request.py tools/call --params-file Saved/CodexStructure/<request>.json`

Use only the eight request files below, in this order. After each call, read the editor log (`Saved/Logs/PussStage.log`)
and find the marker line whose `run=<HHMMSS>` is NEW for that call. Parse by marker plus run id, NEVER by `tail -1`:
an old line reads as a pass. Each script stamps its own run id.

| # | Request file | Required marker (new run id) |
|---|---|---|
| 1a | `hangar_retime_dryrun_request.json` | `HANGAR_RETIME_DRY_RUN_OK` with `mutated=0` and `issues=[]` |
| 1b | `hangar_retime_apply_run_request.json` | `HANGAR_RETIME_DONE` … `applied` |
| 2a-dry | `s3_cast_reveal_dryrun_request.json` | `S3_CAST_REVEAL_DRY_RUN_OK`, and NO `S3_CAST_REVEAL_BLOCKER` line for this run |
| 2a | `s3_cast_reveal_apply_run_request.json` | `S3_CAST_REVEAL_DONE` |
| 2b-dry | `s3_pit_deck_dryrun_run_request.json` | `S3_PIT_DECK_DRY_RUN_OK` |
| 2b | `s3_pit_deck_apply_run_request.json` | `S3_PIT_DECK_DONE` |
| 3-dry | `s3_strike_dryrun_run_request.json` | `S3_STRIKE_DRY_RUN_OK` |
| 3 | `s3_strike_apply_run_request.json` | `S3_STRIKE_DONE` |

**STOP the whole chain at the first:**
- missing or `*_DRY_RUN_MISMATCH` / `*_STOPPED` / `*_BLOCKER(S)` marker;
- Python error in the log for that run;
- DONE line whose census shows ANY dirty map or content package.

Report the failure verbatim. Run NO revert and NO retry; I decide.

## Editor safety rules (each has crashed or corrupted this editor before)
- Never run any other Python, no inline snippets. Never reload the level or any package (the open world crashes).
- Never Save All. Never open Sequencer, scrub, or play the Master or any Scene sequence (that dirties the map). Never
  start PIE.
- Never call `SequencerTools` helpers.
- Don't touch Plugins/ or build. Don't relaunch the editor.
- If the editor dies or MCP stops answering: STOP and report. Don't relaunch.

## Final message (short)
- One line per step: the marker line verbatim (trimmed to the marker, run id, census, backup path).
- Then: "chain complete" or "stopped at <step>: <reason>".
- Mark each claim: measured (read from the log) or inferred.
