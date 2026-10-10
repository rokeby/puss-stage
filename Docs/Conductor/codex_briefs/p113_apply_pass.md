# P113: APPLY pass (pass 2 of Gary's two-pass plan; Codex --unreal, LIVE)

HARD RULES: those in `p49_postbake_editor_runner.md`. Also:
- Purge the module cache before each tool (`Saved/CodexConductor/purge_saved_module_cache.py`).
- Each item runs **re-DRY → APPLY (exact confirm) → `*_APPLY_OK` with this run id → read-back → clean census**.
- Leave args files as you found them, back in DRY mode.
- Never Save All. Never save Klara's levels. Never end a PIE you did not start, never quit or restart the editor.
- You may start and end your OWN PIE only for a tool's stills plan.
- **A STOP inside an item:**
  - If it happened BEFORE any mutation and the census is clean: record it and go to the next independent item.
  - If it happened AFTER a mutation (dirty census, record `prepared`, or no APPLY_OK): STOP the whole pass and report. The conductor does the Don't-Save restart.
- Never skip within a dependency chain. If a chain step fails, skip the rest of that chain.

Gary's decisions:
- "Leave the sound waves". Job 104 (P06) is NOT run in this pass.
- The P02 car drive-by radius is 10000 cm (E28), when job 110 is present.

Source: `Docs/Conductor/DRY_ALL_REPORT_2026-10-10.md` (pass-1 results).

## Order
1. **P02 practicals.** `P01FloorPracticals_20261008`, FLOOR, P02. The args already carry `floor_disagree_accept`.
2. **P02 Top flip, then beams.** Neither had a DRY in pass 1, so DRY first.
   - Job 106: `Saved/CodexFlatV3/p02_top_facing/` (Gary approved).
   - Job 105: `Saved/CodexFlatV3/p02lighting/p02_beam_bootstrap*`.
   - Then the p02lighting = P01 DRY. APPLY it only if that DRY is now clean, and follow its GPU-loss runbook.
3. **Chandelier chain** (stop the chain on any failure):
   1. P75 staging, opening + p06.
   2. P56 candles.
   3. P52 swing. If it needs the unbuilt sway-kick C++, report and skip.
4. **Job 89**, curtain before shadow.
5. **Job 90, then job 90b** (a chain).
6. **Job 93**, P03 wings + floor.
7. **Job 95**, camera seams (Python only).
8. **Job 96**, S4 dark cut.
9. **Job 98**, S5 girders.
10. **Job 88**, proscenium fringe IMPORT.
11. **Job 103**, P05 to 42 s (`passages_to_music_p05_e26_*`).
12. **Job 110**, P02 car drive-by radius 10000. Only if its folder is in the main tree; DRY first.
13. **Items fixed by job 112**, only if its report marks them "ready for pass 2" and their files are in the main tree:
    - 87
    - 92
    - 94
    - 97
    - pearl 2 s
    - 99 (the non-PIE part)
    - 101
    - 100
14. **Stills.** For each applied item, take its stills plan, plus ONE wide still of the whole stage front (Gary has never seen it). Save them under `Saved/CodexConductor/ApplyPass_20261010/stills/`.

## Report
Write `Docs/Conductor/APPLY_PASS_REPORT_2026-10-10.md`:
- A table: item | run id | DRY | APPLY marker | read-back | census | stills | notes.
- Tier every claim.
- List the files you changed.
- Commit nothing.
