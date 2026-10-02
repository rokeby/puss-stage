# Build window, 2 Oct morning (Conductor 4). Gary, his own words this session: "take the build window now while it's closed".
Patch: Scripts/patches/2026-10-02_SS_scene_shot_step.patch (scene shot stepping; spec specs/SCENE_SHOT_STEP.md).
Read first: Docs/WindowsBuildProcedure.md, Docs/Conductor/BUILD_WINDOW_QUEUE.md (top entries), and
specs/BUILD_WINDOW_FFV_HL.md INCLUDING its Revision 2 (the marker method). Stop at the first failure.
1. The editor is already CLOSED (Gary, 08:38). Confirm no UnrealEditor.exe anywhere (tasklist). If one exists, STOP:
   never close an editor yourself.
2. Adversarial review of the patch: crashes, interlock/DeclaredUnpausable bypass, a jump that strands playback or the
   vamp, a camera claim skipped, behaviour change outside Scenes. A P0/P1 = STOP before building. (The extra IsActive
   check in FindSceneCameraCut is intended.)
3. `git status --short Plugins/` must be empty. `git apply --check --ignore-whitespace` then apply the same way.
4. Build per WindowsBuildProcedure. Markers, BOTH required, with +/- controls proven first (Revision 2 method):
   (a) UTF-8 test names in UnrealEditor-InfinityStageTests.dll: ShotStepNextAndPrevious, ShotStepEngagesVampAtStart,
       ShotStepOutsideSceneUnchanged; (b) UTF-16 literal INFINITY_SHOT_STEP in UnrealEditor-InfinityStage.dll.
5. Run the three new tests ALONE first (exact names), then the suite with filter EXACTLY `InfinityStage` (NEVER
   `PussStage`). Baseline 106/0/106 (467d2c8); expect 109/0/109. Results from the log; warnings are not failures.
6. ANY red: `git checkout -- Plugins/` + delete the new test file, rebuild, confirm baseline 106, report. No debugging.
7. All green: commit ONLY the applied source + test file: "Build window 2 Oct: SS scene shot stepping; suite N/0/N".
   No level/Show changes, no saves of any Content.
8. Relaunch the editor (procedure's command) and leave it RUNNING and clean: census content=[] maps=[], PIE off.
   NEVER end PIE, never quit an editor someone else opened.
Final message: review findings, markers with controls, the new tests by name, suite N/F/T, commit hash, census.

## Revision 2 (Conductor 4, after review P1 of the first attempt)
P1 accepted: JumpToMasterFrame's Pause() cancels the Scene's bounded PlayTo (MovieSceneSequencePlayer.h:329) and the
patch then calls an unbounded Play(). FIX: in JumpToMasterFrame, when bKeepPlaying, call PlayForwardToBoundary()
(InfinityStageTransportController.cpp:741) instead of Player->Play(), AFTER SelectedSegmentIndex is set; return its
result if it is not Succeeded. Keep ClaimSegmentCamera as in the patch. Add a test assertion (in
ShotStepNextAndPrevious, or a new test ShotStepKeepsSceneBoundary) that after a playing shot step the transport's
bounded stop is still the Scene's end (whatever the existing test seam exposes for PlayTo targets; if none exists,
add the narrowest test seam), with a negative control (bare Play() must fail it).
Procedure: apply the patch (step 3), make this fix in the tree, regenerate
Scripts/patches/2026-10-02_SS_scene_shot_step.patch from the tree (v2), then re-run step 2's adversarial review on the
FULL amended diff, and continue with steps 4-8. Expected suite 109 or 110 (if the new test). Commit the patch v2 with
the source.
