# Spec: HELD PATCH P: the Arrival also plays light-intensity and exposure-weight tracks before the cut

Output: ONE file, `Scripts/patches/2026-09-30_P_arrival_predrive.patch`, a `git diff` against HEAD. It must apply
cleanly with `git apply` (the repo is CRLF on checkout: see the other patches in `Scripts/patches/` for format).
The working tree must be left UNCHANGED at HEAD, because any build compiles the working tree.

## Why
Gary (30 Sep): "rig/curtain/lighting dimming all happening gradually at once".
- The Scene 4 rise (`LS_S4_HangarRise`) now starts with the P04 curtain release, at motion time W0 ≈ −5.874 s.
- Before Scene 4's first frame, only `AInfinityStageArrival` plays anything, and today it drives ONLY the root's
  rotation and the backcloth's cache time (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageArrival.cpp`,
  `EvaluateAtMasterFrame`, lines ~246–275).
- The wall practicals, lattice glow and the exposure volume's BlendWeight are keyed in the same sequence, but they
  only play from the cut. So the dim can't begin with the curtain.

## What to change (REFERENCE implementation: the existing backcloth path in the same class)
- **In `InfinityStageArrival.h`:** a new `USTRUCT FInfinityArrivalFloatDrive`:
  - `TSoftObjectPtr<UObject> Target`, a `ULightComponent` or an `APostProcessVolume`;
  - `FGuid BindingGuid`, the possessable in MotionSequence holding the float track;
  - `FName PropertyName`, `"Intensity"` or `"BlendWeight"`.
  - Add `UPROPERTY(EditAnywhere, BlueprintReadWrite) TArray<FInfinityArrivalFloatDrive> PreSceneFloatDrives;`.
  - Add a side-effect-free `UFUNCTION bool ResolveFloatDriveAtMasterFrame(const UInfinityStageShowAsset*, FFrameTime,
    int32 DriveIndex, float& OutValue) const`, mirroring `ResolveBackclothTimeAtMasterFrame`.
- **In `InfinityStageArrival.cpp`:**
  - Resolve with `ResolveMotionTime` (the same negative-time mapping the root uses), find the binding's
    `UMovieSceneFloatTrack` whose property name matches, and evaluate its `FMovieSceneFloatChannel` at the motion time.
    Use a `FindBindingSection`-style helper for float tracks.
  - In `EvaluateAtMasterFrame`, after the root and the backcloth, for each drive that resolves:
    - `ULightComponent`: `SetIntensity(Value)`, only if it differs by > 1e-3;
    - `APostProcessVolume`: set `BlendWeight`, only if it differs by > 1e-4. Use the same "only on change" discipline as
      the root, so nothing is rewritten per frame.
  - False and untouched at or after the Scene's first frame (Sequencer owns it there), exactly as the root.

## Traps
1. **The cut must be seamless.** The Arrival evaluates the SAME channel at the same continuous time, so at t = 0⁻ it
   sets exactly what Sequencer sets at t = 0. The test proves it.
2. **The Arrival also runs in EDITOR worlds.** It's called from the Master's Passage track during Sequencer
   evaluation. Setting a light's intensity there can be persisted by a later level save ("level saves persist
   evaluated state").
   - Gate the NEW float drives to game worlds: `GetWorld()->IsGameWorld()`.
   - The existing root/backcloth behaviour must stay exactly as it is.
   - Document the gate in the header comment.
3. **Don't change the existing behaviour for the root or the backcloth.** The existing Arrival tests must still pass
   unchanged.
4. Missing links warn once, via `WarnOnce`, never per frame.
5. No new module dependencies beyond what the class already uses. `APostProcessVolume` is Engine; `ULightComponent` is
   Engine.

## Test (extend `Plugins/InfinityStage/Source/InfinityStageTests/Private/InfinityStageArrivalTests.cpp`, same style)
Build a motion sequence in the test with one possessable, a float track "Intensity", and keys
(−2.0 s, 0) → (2.0 s, 400). Assert:
- **POSITIVE:** at master time → motion −1.0 s, `ResolveFloatDriveAtMasterFrame` gives 100 ± 1.
- **SEAM:** at motion −1 tick, the value equals the channel's value at 0 within 1e-2.
- **NEGATIVE:** at or after the Scene's first frame it returns false.
- **NEGATIVE:** with a wrong `PropertyName` it returns false and warns once.
- **EDITOR GATE:** in an editor (non-game) world `EvaluateAtMasterFrame` leaves the light's intensity untouched. If
  a game world can't be made in the test, test the resolve function and the gate branch separately, and SAY SO in
  your final message.

## The key timing this patch assumes (put it in the patch header comment)
- Until P is built, `LS_S4_HangarRise` keys practicals/glow `[(0,0),(W1,full)]` and BlendWeight `[(0,0),(W1,1)]`.
  W0 ≈ −5.874 s (the P04 cloth release), W1 ≈ +4.126 s (the cloth section end); both are read from
  `Saved/CodexStructure/p04_backcloth_section_record.json`.
- AFTER P is built:
  - re-key those tracks to start at W0 (`[(W0,0),(W1,full)]`, `[(W0,0),(W1,1)]`);
  - author `PreSceneFloatDrives` on "S4 Arrival": 14 practical + 24 glow `LightComponent`s + the "S4 Hangar Pinned
    Exposure" volume, with their binding GUIDs from the sequence.
  - Both steps are done by Rig & atmosphere after the build, not by this patch.

## Constraints
- Don't build and don't run Unreal. Produce the patch plus a short note of what you could not verify.
- Tree at HEAD when done (`git status` clean of your changes; the patch file is the only new file).
