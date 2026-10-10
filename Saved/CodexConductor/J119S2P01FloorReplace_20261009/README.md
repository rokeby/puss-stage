# Jobs 119/129: replace target floor with P01-derived actors

Offline-built; no Unreal, MCP or PIE call was made. Original floor actors are never deleted.

Set `target` in `j119_s2_p01_floor_replace_args.json` to `S2` or `P02`. It is delivered as `P02`/DRY for job 129.
Selecting `S2` preserves job 119's existing confirmations, markers, record path and execution body.

## P02 / job 129

1. Set `target=P02`, leave `mode=DRY`, and run the guarded request. Require
   `J129_P02_P01_FLOOR_REPLACE_DRY_OK`, unchanged dirty census, four target actors, one route replacement per
   static-mesh component or ISM instance, zero component-binding blockers, and review every uncertain sequence row.
2. Review `j129_p02_dry_<run>.json`: construction methods, every fitted footprint, scale ratios, P02 Passage
   live-root transform/inside-box guard, sequence audit, and stills plan. The tool never makes one corridor-spanning plane.
3. Copy `plan_sha256` into args. Set the two acknowledgement fields only after their named uncertainties are reviewed.
4. Set `mode=APPLY`, `confirm=APPLY J129P02P01FLOOR`. APPLY records and backs up first, creates one P01-derived
   actor per route segment/instance, composes and attaches it against the LIVE materialized Passage root, lowers only
   the old mesh component(s), materializes Passage 02, then refuses before save unless every copy remains inside the
   live-root-local floor box and its component world Z matches the original slab within 1 cm. It saves only the persistent map.
5. Capture the planned grazing, full-route, visibility, passage-timing and collision stills. Rendered acceptance is Gary's.
6. To undo, use `mode=REVERT`, `confirm=REVERT J129P02P01FLOOR`. REVERT restores every recorded component,
   destroys only tagged/recorded P02 replacements, materializes Passage 02, saves only the persistent map, and archives the record.

## S2 / unchanged job 119 path

1. Use `target=S2`, `mode=DRY`; require `J119_S2_P01_FLOOR_REPLACE_DRY_OK`, four floors, unchanged census,
   zero component-binding blockers, and manually resolve every `sequence_scan_unclear` row.
2. Review `j119_dry_<run>.json`, copy its plan digest, and set acknowledgements only after review.
3. APPLY confirmation remains `APPLY J119S2P01FLOOR`; REVERT remains `REVERT J119S2P01FLOOR`.
4. The S2 marker, tag, record path, backup stems, four-actor fit/attachment implementation and save/read-back path are unchanged.
