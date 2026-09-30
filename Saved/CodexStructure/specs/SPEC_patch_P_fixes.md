# Spec: regenerate HELD PATCH P (`Scripts/patches/2026-09-30_P_arrival_predrive.patch`) with the review fixes

Start from HEAD:
1. apply the existing patch in your worktree (`git apply --ignore-whitespace`);
2. make the changes below;
3. write the new `git diff` (CRLF, like the other patches) back to the same file;
4. restore the source files, so only the patch file differs.
Don't build or run Unreal.

Review findings (Codex adversarial review, `Saved/CodexRuns/last-message-20260930-185129.txt`) and what to do:

1. **P1, cost.** `ResolveMotionTime` compiles the whole Show on every call, by design: see its comment, "compiled every
   call and never cached", which must stay that way. Each drive calling it means ~39 compiles per frame.
   - FIX: resolve the motion time ONCE per `EvaluateAtMasterFrame` for all float drives.
   - Add a private helper `bool EvaluateFloatDriveAtMotionTime(const UMovieScene& MotionScene, FFrameTime MotionTime,
     int32 DriveIndex, float& OutValue) const`.
   - `ResolveFloatDriveAtMasterFrame` (public, for tests) = `ResolveMotionTime` + the helper.
   - `EvaluateAtMasterFrame` calls `ResolveMotionTime` once, then the helper per drive.
   - Leave the root and backcloth paths exactly as they are.
2. **P2, stale target.** A soft reference could write the EDITOR component while running in PIE.
   - FIX: before writing, require the target's world to be the Arrival's own world (`Target->GetWorld() == GetWorld()`).
     Otherwise warn once (`"ForeignWorldTarget"`) and skip.
3. **P2, section choice.** Section 0 is used without a range check.
   - A plain range check would BREAK the feature: pre-cut motion times are NEGATIVE, outside the section's [0, end]
     range by construction. The root works the same way, evaluating its channel outside its section.
   - FIX: prefer a section whose range contains the motion time; if none does, use the section with the earliest start.
   - Say in a comment that pre-cut evaluation reads the channel outside the section range on purpose, exactly as the
     root does.
4. **P2, untested write branches.** Add tests in `InfinityStageArrivalTests.cpp` that exercise the GAME-WORLD write
   path:
   - create a transient game world (for example `UWorld::CreateWorld(EWorldType::Game, false)` plus
     `FWorldContext`/cleanup), then spawn the Arrival, a light component's owner and an `APostProcessVolume` in it;
   - evaluate before the cut, and assert the intensity and BlendWeight were WRITTEN with the channel values;
   - assert a target living in ANOTHER world is NOT written (the guard from 2);
   - assert no writes happen at or after the Scene's first frame.
   - If a game world truly can't be created in this test harness, write the tests as far as possible and say exactly
     what was not possible.

Keep the header comment's timing: W0 ≈ **−5.874 s** (the P04 cloth release), W1 ≈ +4.126 s. Don't regress it to
−0.874.

Final message:
- the `git apply --check --ignore-whitespace` result at HEAD, alone and together with
  `Scripts/patches/2026-09-30_Q_mechanism_renderstate_cvar.patch`;
- how each finding was fixed;
- what you couldn't verify.
