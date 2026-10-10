# P165: self-recovering live slot (Codex --unreal), approved by Gary on 10 Oct

Gary approved this mode: Codex may **restart the editor with Don't-Save itself**, fix the failing tool, and retry. Claude only reads the final report.

## Read first
- `Docs/Conductor/codex_briefs/p135_live_pass3.md`: the rules, plus stills as the acceptance evidence.
- `Docs/Conductor/APPLY_PASS_REPORT_2026-10-10.md`: every pass so far, and why each stopped.
- `Docs/Conductor/MORNING_REPORT_2026-10-10.md`.

## Hard rules
These still apply unless overridden below:
- Never Save All. Never save Klara's levels.
- Never end a PIE you did not start.
- Visibility tracks bind bHidden.
- Each item: DRY → APPLY → APPLY_OK → read-back → clean census.

## Override: the self-recovery loop
When an item fails AFTER a mutation, or leaves the census dirty:
1. Record it in the report.
2. Run a **Don't-Save restart**, in PowerShell:
   1. `Stop-Process -Name UnrealEditor -Force`
   2. Wait 8 s.
   3. Rename `Saved/Autosaves/PackageRestoreData.json` → `PackageRestoreData.json.old-<ts>` if it exists.
   4. Rename that tool's `prepared` / `ACTIVE` record to `<name>.failed-<run>`.
   5. `Start-Process explorer.exe -ArgumentList '"E:\PussStage\PussStage.uproject"'`
3. Wait for MCP on 127.0.0.1:8010, plus about 45 s.
4. Confirm `P18_EDITOR_SKY_AUTOHIDE_OK` in the new log.
5. Run the census with `bash Saved/CodexConductor/conductor_helpers/mcprun.sh census_print_request.json "CENSUS_PRINT" "CENSUS_PRINT" 1`. The path is RELATIVE to `Saved/CodexConductor`. It must be clean, with PIE false.
6. FIX the tool offline (any code change is allowed now, because the state is clean). Rerun its offline harness, which must pass, and add a harness case for the failure.
7. Retry the item. **At most 3 attempts per item.** After the third failure, restart clean once more, mark the item FAILED with all three causes, and move on.

## Stop conditions
- Any `DXGI` / `D3D12` / `DEVICE_REMOVED` / `DEVICE_RESET` in the log: STOP everything, close the editor with Don't-Save, report. Gary must reboot.
- **Gary may be using the editor.** Before every restart, check: if PIE is active and you did not start it, or the dirty census contains anything your item did not touch, do NOT restart. Wait 5 min ×3, then STOP and report.
- Hard time cap: 3 h total.

## Items, in order
1. **P02 LEAN lighting** (`Saved/CodexFlatV3/p02lighting/p02_lighting_lean*`; Gary approved; car radius 4600).
   - Last failure: one attachment kept `cast_shadows=True` after APPLY. Find out why; maybe a BP construction script resets it, or the Show materialization re-applies it.
   - Then a PIE p95 at 3 P02 spots, plus stills.
   - Auto-REVERT if p95 is not better than 40.7 ms.
2. **Shadow radii** (job 163: persistent-level Passage lights only) with the perf auto-revert.
3. **The 3D stage front**:
   1. MATERIAL for wall, gilt, crest, column, cat. Arch is done.
   2. PLACE DRY → APPLY → VERIFY, with Iron3.
   3. A WIDE opening still.
   4. Then un-hold job 87: rename its `.HELD-until-job131-3D-stage-front` request files back.
   5. Job 87 DRY with the job 160 re-plan → APPLY → opening stills.
4. **The P75 chandelier chain.**
5. **Ending 101.**
6. **The P02 floor** (job 156) → a reflection still.
7. **I2, then I3 back wall** (job 144, `SAFE_SKIP`).
8. **Fringe** (job 159).
9. **Stills**: P06 dusk, S2 from outside, P05 wings.

## Report
Append "Self-recovering slot" to `Docs/Conductor/APPLY_PASS_REPORT_2026-10-10.md`:
- per item: attempts, causes, fixes, APPLY marker, still path, visual verdict
- every restart, with its timestamp
- every file changed

Leave the editor OPEN, clean, with the sky hidden at the end. Commit nothing.
