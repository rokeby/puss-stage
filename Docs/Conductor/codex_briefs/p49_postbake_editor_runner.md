# P49 — Execute the post-bake editor queue, batch 1 (Codex --unreal, LIVE)

You are driving the live Unreal Editor through the guarded MCP route. Read first, in full:
`Docs/Conductor/codex_briefs/_house_rules.md`, `Docs/CodexUnrealMCPRunbook.md`, memory notes summarised below, and
`Docs/Conductor/POSTBAKE_QUEUE_2026-10-09.md`. Transport: `Saved/CodexConductor/conductor_helpers/mcprun.sh <request.json>
"<OK|FAIL regex>" "<marker prefix>" 1` (see existing `*_request.json` files: ExecuteProjectPythonFile, path relative to Saved/).

## HARD RULES (any breach = stop and report)
- NEVER end PIE you did not start; never quit/restart the editor; never Save All; never reload the open level.
- One tool at a time. Each tool: DRY → read the DRY report → APPLY with its exact confirm string → require its
  `*_APPLY_OK` marker with this run's id AND a clean dirty census after → next. Any FAILED/STOPPED/unexpected census →
  STOP the whole batch and report (do not retry, do not "fix" Show data by hand).
- Read markers by run id from `Saved/Logs/PussStage.log`, never `tail -1`.
- After an editor restart (only the conductor restarts): run `Saved/CodexConductor/editor_sky_toggle_request.json` (hide).
- Visibility tracks bind ("bHidden","bHidden"); never bHiddenInGame.
- No Blender. No GPU-heavy probes (dune shadow probe, wing burn) in this batch.
- Do not edit tool code unless a DRY proves a trivial API-name bug; then patch, rerun its offline harness, and report the
  exact diff. Never weaken a guard.

## Batch 1 (in this order; each item's tool and args are in POSTBAKE_QUEUE)
1. Job 33 passages_to_music (APPLY; Gary approved without review). Report every passage old→new length.
2. Job 42 p06_retime (needs 1). Report new P06 length, k, new dusk (horizon) seconds.
3. Job 24 shrink I2 to 1950 → job 34 I2 move-in (finishing touches' tool) → job 39 I2 polish APPLY parts that need no PIE
   (F18, run-on report). The job 39 boundary probe needs PIE: you MAY start PIE yourself for it and end ONLY that PIE.
4. `p02_floor_darkwet.py` (P02 floor shiny).
5. Job 44 S1 F4 darkness + F5 rig fade (frame 783) + interactions I1/I3/I4/I5 stand-in transitions (DRY first; report the
   per-interaction present/missing table before any APPLY).
6. Job 38: F20 lid + 0:04 spoiler + handprints +50 % (DRY each; APPLY).
7. Job 40: Shore05 (+ extra_count 2 for variation) + underwear colour (APPLY); cloth settle: DRY only, report options.
8. Clam chain (existing 8 Oct tools; re-DRY): `s3_pearl_fade.py`, `s3_shots_fix.py`, `ClamSlime_20261008` — DRY all three
   and report; APPLY only those whose DRY is clean.

Skip anything owned by Wings & Textures (topple chains, scaffold, fences, Q7 lighting) — they run their own slots.

## Report
A table: item | run id | DRY verdict | APPLY marker | census after | notes, with tiers per claim. Commit nothing (the
sandbox can't); list every file you changed. End with the first STOP reason, if any.
