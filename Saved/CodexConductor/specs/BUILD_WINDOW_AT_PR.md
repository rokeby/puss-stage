# Build window, 2 Oct evening (Conductor 4). Gary: "full steam ahead" (Conductor 4 session) + every AT/PR design answer
# in his own words there. Patches: Scripts/patches/2026-10-02_AT_hangar_timing_details.v2.patch THEN
# Scripts/patches/2026-10-02_PR_passage_resize.v2.patch (reviewed; apply together on HEAD). Read
# specs/BUILD_WINDOW_SS.md (incl. Revision 2) and specs/BUILD_WINDOW_FFV_HL.md Revision 2: same procedure and marker
# method. Stop at the first failure.
1. Close the editor ONLY via Saved/CodexConductor/quit_editor_clean.py (refuses unless dirty 0/0; if it refuses, STOP).
   Confirm no UnrealEditor.exe anywhere. Never Stop-Process an editor.
2. Short adversarial re-review of the combined diff (P0/P1 = STOP before building): packaging (editor code in the
   runtime module), a timing Apply that touches root keys or S6 lights turning ON, a resize that loses GUIDs.
3. `git status --short Plugins/` empty; apply AT then PR with --ignore-whitespace (check first, same mode).
4. Build per WindowsBuildProcedure. Markers with +/- controls (Revision 2 method): each NEW test name UTF-8 in
   UnrealEditor-InfinityStageTests.dll (or the editor tests DLL where it lives: find it); a UTF-16 runtime literal per
   patch (e.g. INFINITY_HANGAR_TIMING_APPLIED; the PR library's log marker).
5. Run each NEW test alone (read exact names from the patches), then the suite filter EXACTLY `InfinityStage` (NEVER
   `PussStage`). Baseline 109/0/109 (301c8ae). Expect 109 + the number of new tests. Results from the log.
6. ANY red: git checkout -- Plugins/ and delete new files, rebuild, confirm 109, report. No debugging.
7. All green: commit ONLY applied source + tests: "Build window 2 Oct evening: AT hangar timing + PR passage resize; suite N/0/N".
8. Relaunch the editor (D:\Unreal Engine\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe "E:\PussStage\PussStage.uproject")
   and leave it RUNNING, census empty, PIE off. If a restore prompt shows in the log, report it.
Final message: review findings, markers with controls, new tests by name, suite N/F/T, commit hash, census.
