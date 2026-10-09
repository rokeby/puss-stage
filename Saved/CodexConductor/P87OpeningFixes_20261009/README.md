# P87 Opening fixes — conductor runbook

Offline-authored on 9 October 2026. Nothing in this folder has been run in
Unreal. `p87_opening_args.json` deliberately leaves `first_flurry_frame` null,
so APPLY cannot run until a live DRY resolves Gary's `00:37:50` against both
the Master and Opening-local clocks.

## Files

- `p87_opening_common.py`: pure plans and safety rules.
- `p87_opening_fixes.py`: transaction, record, backup, narrow-save and read-back.
- `p87_unreal_adapter.py`: UE 5.8 discovery/mutation adapter; composes P13 helpers.
- `p87_opening_run.py`: guarded project-Python entrypoint.
- `p87_opening_args.json`: Gary-owned look/timing values.
- `p87_opening_request.json`: mode/confirm/run-id control.
- `p87_execute_request.json`: guarded MCP request body for the conductor.
- `test_p87_opening.py`: offline positive and negative harness.
- `p87_preview.py`: PIL-only preview generator.
- `P87_OPENING_FIXES_REPORT_2026-10-09.md`: tiered handoff and open questions.

## Ordered live run (conductor only)

1. Run the offline harness and preview commands from the report.
2. Require a clean editor and close Sequencer. Set a unique run id, keep mode
   `DRY`, confirm `DRY P87`, and keep `first_flurry_frame` null.
3. Execute `p87_opening_run.py` through the guarded project-Python route. Read
   the exact dirty census and the Master/Opening-local clock report. DRY must
   end in `P87_OPENING_FIXES_DRY_OK` and `mutated=0`.
4. Pin `first_flurry_frame` to the measured Opening-local frame. Review every
   foreign active record; put only deliberately accepted exact paths in
   `ack_records`. Re-run DRY and archive its JSON.
5. Set mode/confirm to `APPLY` / `APPLY P87`. APPLY first copies the Show,
   Opening sequence and level to `Backups/PreP87OpeningFixes-<run>`, then writes
   the record before mutation. It saves only those three packages and reloads
   them for read-back.
6. Require `P87_OPENING_FIXES_APPLY_OK`, `readback=1`, and `dirty_final=0`.
   Capture the five planned stills: wide hold, mid-fall, uplights established,
   final P01 pose, and bulb top/grazing views. Gary owns visual acceptance.
7. To undo, preserve the APPLY record, set `REVERT` / `REVERT P87` with the same
   parts, and run. REVERT refuses any drift, makes a second backup, restores the
   recorded before-state, reads back, and archives the APPLY record.

Never use Save All. Never run APPLY with an unresolved clock or unreviewed
foreign record.
