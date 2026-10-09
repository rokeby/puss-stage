# P35 — ADD_UPLIGHTS: APPLY/REVERT for P02-P06 floor uplights (Codex, offline)

Read `_house_rules.md` first; every rule applies.

## What Gary asked
8 Oct questionnaire + 9 Oct ("are uplights installed everywhere ready for programming?" -> go tonight):
- Stage Fresnel-style floor uplights at the wing feet, aimed up the wing faces, **cooler 4500 K for P02-P06**.
- "The bright and milky ones (P2, P3) need them fairly dim."
- "Uplights are set up now as infrastructure but do not all need to be on" -> install every one, with per-passage
  levels in args; a passage set to "off" keeps its rows (and lanterns) at 0 lm, ready for programming.

## Starting point (read the code, do not rewrite it)
`Saved/CodexConductor/P01FloorPracticals_20261008/` — `p01_floor_common.py` (pure planner incl. `add_uplights_plan`),
`p01_floor.py` (orchestrator; `ADD_UPLIGHTS` is proposal-only: `check_args` refuses APPLY at p01_floor.py:161-162),
`README.md` (ADD_UPLIGHTS section + offline proposals), `test_p01_floor.py` (70/0 harness),
offline proposals `p0N_addup_report_COUNT_*.json`: P02 46 / P03 42 / P04 30 / P05 105 / P06 110 uplights.
FLOOR APPLY for P01 already ran live (`p01_floor_report_APPLY_20261008-212102.json`) — reuse its write/backup/
census/read-back path for Show rows; ADD_UPLIGHTS adds NEW Station light rows (it does not move existing ones).

## Build
1. Extend ADD_UPLIGHTS to APPLY/REVERT (confirm "APPLY P0NADDUP" / "REVERT P0NADDUP", one passage per run), recording
   every created row id; REVERT removes exactly those rows and refuses on drift.
2. Args per passage: `kelvin` (default 4500 for P02-P06), `lumens` (defaults: P02 200, P03 200, P04 500, P05 500,
   P06 500 — Gary's to tune), `on` (default true; false = 0 lm, rows kept), cone/radius as the proposal defaults.
3. Structure lanterns: the structure fits a lantern behind every ENABLED Station light
   (`InfinityStageStructureActor.h:386-416`; fitting at the structure cpp:164) and there is no per-attachment
   opt-out, so the visible housing is the passage's Structure can (P02 ParCan, P03 Fresnel, ...). Report the housing
   per passage; do NOT try to swap it (needs C++, out of scope). Rows must stay ENABLED so the lantern exists even
   when `on` is false.
4. Preserve the existing skip rule (a side that already has a floor uplight is skipped) and the existing P01 work.
5. Previews: per-passage top-down + elevation PNGs (the existing preview script) with the 4500 K colour.
6. Harness: extend test_p01_floor.py — negative controls (APPLY without confirm, record active, drift on REVERT,
   two passages in one run, kelvin/lumens out of range, P01 FLOOR record clobber) and a positive APPLY->REVERT round
   trip per passage on the fake backend. Report counts.
Save only the Show asset (+ whatever the existing FLOOR APPLY saves, named exactly); materialize only the affected
Passage actor(s), per the AGENTS.md authoring rules.
