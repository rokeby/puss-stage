# Build window, 1 Oct night (Conductor 3; conductor-approved: reversible engineering, Gary's 29/30 Sep delegation)
Patches: Scripts/patches/2026-10-01_FFV_fast_forward_and_vamp.patch, Scripts/patches/2026-10-01_HL_hangars_landed_in_editor.patch
Read first: Docs/Conductor/BUILD_WINDOW_QUEUE.md ("Order" section + the 1 Oct ~21:15 entry), Docs/WindowsBuildProcedure.md,
memory notes in the queue (line endings: apply with --ignore-whitespace; check in the SAME mode).
Steps, stop at the first failure:
1. Close the editor ONLY via Saved/CodexConductor/quit_editor_clean.py (it refuses if anything is dirty). Then confirm
   no UnrealEditor.exe on the machine (tasklist). If one remains, STOP.
2. Adversarial review of the combined diff of the two patches (Scripts/codex.sh --review style, or read them yourself
   adversarially): crashes, interlock bypass, a hold/vamp that can strand playback, a BeginPlay pose applied in an
   EDITOR world, anything touching Show data. Report findings; a P0/P1 = STOP before building.
3. git status must be clean for Plugins/. Apply both patches (--ignore-whitespace), git apply --check first.
4. Build per WindowsBuildProcedure (the project's documented command). Verify each change by a UTF-16 string marker
   in the built DLL (a new test name from each patch), never by exit code.
5. Relaunch the editor headless-safe per the procedure if the tests need it, then run the automation suite with the
   filter EXACTLY `InfinityStage` (NEVER `PussStage`: it rebuilds and SAVES the Show and Master). Previous baseline
   103/0/103 (7af58f3). Expect +3 new tests (HoldRightFastForwards, VampLoopsUntilRelease, the HangarInitialPose test).
   Read results from the log. Warnings are not failures (baseline ~29).
6. ANY failure: revert the working tree to HEAD for Plugins/ (git checkout), rebuild, confirm baseline, report. No
   debugging session.
7. All green: commit ONLY the applied source + tests with message "Build window 1 Oct night: FFV + HL; suite N/0/N".
   Do NOT change the level or the Show. Do NOT run the landed-save step (that waits for Gary's PIE check).
8. Leave the editor RUNNING at the end (relaunch it) with nothing dirty; report the census.
Final message: review findings, DLL markers, suite N/F/T with the new test results by name, commit hash, census.

## Revision 2 (after run 222729 rolled back on a FALSE marker check)
MEASURED by the conductor after the rollback: an existing test name (`KindsUseCachedPivotsAndAxes`) is present in
`UnrealEditor-InfinityStageTests.dll` as UTF-8 ONLY (UTF-16: False in all three plugin DLLs). Automation test
names are narrow strings. Step 4's markers therefore become, BOTH required:
 (a) each new test name, UTF-8, in UnrealEditor-InfinityStageTests.dll (HoldRightFastForwards,
     VampLoopsUntilRelease, GameWorldStartsAtFirstHangarKeys — read the exact names from the patches);
 (b) for each patch, one UTF-16 `TEXT("...")` literal unique to its RUNTIME code (pick from the patch: a log
     marker, cvar or marker label such as `InfinityStage.VampStart`), in UnrealEditor-InfinityStage.dll.
     Prove the method first: a literal already in the baseline must be FOUND by the same search (positive
     control), and a made-up string must NOT be (negative control).
The test files preserved in Backups/FailedBuildWindowFFVHL-20261001-223255 are not needed; re-apply the patches.
Everything else in this spec stands (review, suite filter exactly `InfinityStage`, revert on red, no level/Show
changes, leave the editor running clean).
