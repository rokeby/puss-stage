# Spec: regenerate HELD PATCH C (`Scripts/patches/2026-09-30_C_celestial_write_only_on_change.patch`)

Start from HEAD:
1. apply the existing patch in your worktree (`git apply --ignore-whitespace`);
2. make the change below;
3. write the new `git diff` (CRLF) back to the same file;
4. restore the source files, so only the patch file differs.
Don't build or run Unreal.

## Review finding (P2)
`ApplyCyclePhase` in `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageCelestialRig.cpp` still calls
`StarsDome->SetScalarParameterValueOnMaterials(...)` UNCONDITIONALLY, four times: the stars brightness, "Sun
brightness", "Cloud opacity" and "Sun height". That contradicts the patch's own comment, "Every write below is skipped
when the value is already in place".

## Fix: gate them, keep the comment true
- Add transient private members holding the last value written for each of the four parameters, initialised to NaN so
  the first call always writes.
- Write a parameter only when its new value differs from the last written by more than 1e-6, then update the cache.
- When the stars visibility toggles, reset the cache (write all four), so a hidden/shown dome never keeps a stale value.
- Invalidate the cache wherever the rig re-resolves or rebuilds its bindings (for example
  `ResolveEnvironmentBindings`, `OnConstruction`, `BeginPlay`), because the materials can change there.
- Nothing else in the patch changes.

## Test
If a celestial-rig test exists in `Plugins/InfinityStage/Source/InfinityStageTests/Private/`, add a case: apply the
same phase twice, and the second call writes no material parameter. Use an observable such as a counter behind
`WITH_DEV_AUTOMATION_TESTS`, or a MID parameter read-back. If that isn't feasible without heavy scaffolding, say so and
skip it.

Final message:
- the `git apply --check --ignore-whitespace` result at HEAD, alone and together with the P and Q patches;
- what changed;
- what you couldn't verify.
