# Q6 review stills

Offline-authored capture tool for Gary's eight-shot review set. It is deliberately
limited to one **already-open** PIE session: it never starts, ends, saves, or
restarts Unreal, and it never applies an exposure override.

## Ordered conductor run

1. Leave `review_stills_args.json` in `DRY` mode with confirmation
   `DRY REVIEW STILLS`; execute `review_stills_request.json`.
2. Read the `REVIEW_STILLS_DRY_OK` marker. Put that report filename in
   `dry_report`, change the mode to `RUN`, and set confirmation to
   `RUN REVIEW STILLS`.
3. Run `Saved/CodexConductor/conductor_pie_begin_request.json` once. Wait for its
   begin marker and do not start a second PIE session.
4. Execute `review_stills_request.json` once. Wait for `REVIEW_STILLS_OK` or
   `REVIEW_STILLS_FAILED`. Outputs are under `runs/<run-id>/`: eight PNGs,
   `review_stills_contact_sheet.png`, and `review_stills_manifest.json`.
5. The person/session that started PIE may then run
   `Saved/CodexConductor/conductor_pie_end_request.json`. This driver never does.

If a callback must be stopped, set mode `REVERT`, confirmation
`REVERT REVIEW STILLS`, and execute the same request. REVERT restores the runtime
frame/view and keeps every output; it performs no deletion.

All look values (close-view distance, FOV, resolution, settle thresholds) live
in the args file. Every target frame is resolved from live Master segments or a
live passage/panel query during RUN; the schema rejects baked absolute frames.
