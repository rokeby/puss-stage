# Job 105 - P02 BeamLook bootstrap runbook

This is an offline-authored, level-only prerequisite for the existing
`PASSAGELIGHT` tool. It creates exactly four P02 atmosphere beam-volume actors,
at B03/B07/B12/B20, by copying the four P01 record-selected actors in
Passage-relative coordinates. It does not edit the Show.

## Ordered live run

1. Require no PIE/SIE and an exact clean dirty-package census.
2. Leave `p02_beam_bootstrap_args.json` in DRY mode and run:
   `python Saved/CodexMocap/mcp_request.py tools/call --params-file Saved/CodexFlatV3/p02lighting/p02_beam_bootstrap_request.json`
3. Read `P02BEAMBOOTSTRAP_DRY_OK` in `Saved/Logs/PussStage.log`. Copy its
   `plan_sha256` into `expected_plan_sha256`, set mode `APPLY`, and set confirm
   to `APPLY P02BEAMBOOTSTRAP`.
4. Run the same request. Require `P02BEAMBOOTSTRAP_APPLY_OK`, `created=4`,
   `level_saved=1`, `show_saved=0`, `readback=1`, and zero dirty packages.
5. Restore `p02_beam_bootstrap_args.json` to DRY/blank confirmation.
6. Run the existing `passage_lighting_request.json`. Its DRY must now reach
   `PASSAGELIGHT_DRY_OK`; inspect the new plan hash and preview before any
   lighting APPLY.

## Undo order

If `PASSAGELIGHT` was applied, REVERT it first. Then set the bootstrap args to
mode `REVERT`, confirm `REVERT P02BEAMBOOTSTRAP`, and run the bootstrap request.
It drift-checks all owned actor fields, takes a fresh level backup, deletes only
the four actors carrying all three ownership tags, saves only the level, reads
back zero remaining actors, and archives its record.

Do not bootstrap-REVERT while an active `PASSAGELIGHT` record still depends on
these actors. The tool enforces this ordering by refusing APPLY or REVERT while
`passage_lighting_record.json` exists.
