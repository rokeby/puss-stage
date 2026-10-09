# Shadow-cat actions (P46, held patch)

Status: **HELD; never built or applied.** The C++ and Unreal automation tests exist only in
`Scripts/patches/2026-10-09_shadow_cat_actions.patch`. This folder contains an offline verifier and a defaults
preview; neither imports `unreal` nor changes project state.

## Why Passage-relative Show data

- **declaration-proven:** `FInfinityPassageSettings` is serialized in the Show asset, and reconciliation copies an
  existing matching settings row before updating its cue bounds (`InfinityStageShowAsset.cpp:126-181`).
- **declaration-proven:** compiled Passages expose `SegmentStartFrame` (`InfinityStageCompiler.h:27-40`).
- **inferred design choice:** storing `ShadowCatActions[].StartFrame` relative to that compiled start is the narrowest
  way to let rehearsal move WHEN an action happens and have it travel on a Master rebuild. It avoids changing or
  rebinding any Sequencer object. The patch implements this in `InfinityStageTypes.h`.

## Offline verification (safe now)

From the repository root:

```powershell
python Tools/ShadowCatActions/shadow_cat_actions_harness.py --mode DRY
```

The harness runs `git apply --check --whitespace=error-all`, ports the phase, action-envelope and seeded-variation
maths, exercises positive and negative controls, and prints `SHADOW_CAT_ACTIONS_HARNESS|...`. It is deliberately a
DRY-only verifier: APPLY/REVERT belong to the conductor's build window below, so this tool cannot mutate the tree.

## Build window (conductor, ordered; not run here)

1. Require every Unreal Editor closed. Record a run id and `git status --short`; refuse unrelated changes in any of
   the five patch targets.
2. Copy those five targets to `Backups/PreShadowCatActions-<run>/`: `InfinityStage.Build.cs`,
   `InfinityStageTypes.h`, `InfinityStageCameraRig.h`, `InfinityStageCameraRig.cpp`, and (if it already exists)
   `InfinityStageShadowCatActionTests.cpp`.
3. DRY: `git apply --check --whitespace=error-all Scripts/patches/2026-10-09_shadow_cat_actions.patch`.
4. APPLY confirm string: `APPLY_SHADOW_CAT_ACTIONS_<run>`. Then run
   `git apply Scripts/patches/2026-10-09_shadow_cat_actions.patch`.
5. Census: `git diff --name-only` must add/change exactly the five targets above. Build with the documented Windows
   procedure and prove a new UTF-16 marker from the patch is in the DLL. Do not trust build exit code alone.
6. Run these singly:
   - `InfinityStage.Editor.ShadowCatActions.MasterTimePose`
   - `InfinityStage.Editor.ShadowCatActions.BlendContinuity`
   - `InfinityStage.Editor.ShadowCatActions.BobVariationDeterministicBounded`
   - `InfinityStage.Editor.ShadowCatActions.MovesWithPassage`
7. Then run the full suite and compare its warning count with the registered baseline. A build/test pass is not
   rendered acceptance.
8. REVERT confirm string: `REVERT_SHADOW_CAT_ACTIONS_<run>`. Before any authored action exists, use
   `git apply -R Scripts/patches/2026-10-09_shadow_cat_actions.patch`; verify the same five-file census returns clean.

## Add `Idle_Stretching` at Passage P03 +42 s

After the patch has passed its build window, edit only the Show asset
`/Game/InfinityStage/Dev/DA_InfinityStage_V1Show`. In P03's `PassageSettings` row, append one `ShadowCatActions`
element:

- Animation: `/Game/CharacterPacks/AnimX/_Common/CatMannequin/Anim/Idle/A_Cat_Idle_Stretching`
- StartFrame: `42 * Show.TickResolution` (at 24,000 ticks/s: `1,008,000`)
- PlayRate: `1.0`; BlendInSeconds: `0.25`; BlendOutSeconds: `0.25`; HoldLastFrame: `false`
- Label: `P03 breath stretch +42s`

Before changing it, write the run record and take `Backups/PreShadowCatActionP03-<run>`. Record the exact
dirty-package census and refuse unless it is empty. After the edit, materialize only P03, then require the dirty
census to contain only the named Show asset and
`/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice`; refuse any other package. Save only those two named
packages (no Save All), read back the soft path and all five values, require zero dirty packages, and emit
`SHADOW_CAT_ACTION_APPLY_OK|run=<run>|passage=P03|frame=1008000`. Runtime reads the settings from the Show; the
materialization and narrow level save are the project authoring guard. Rendered silhouette and handover/bob
continuity remain Gary's acceptance.

For **Arch**, append the timing row but leave `Animation` empty until a custom AnimX-skeleton clip exists; this patch
does not author animation. Variation is off by default. Its 12 s drift, 3% slow amplitudes, 2% occasional stride
amplitude, 0.8 s stride and 25% chance are rehearsal-tunable defaults; the combined play-rate and bob-gain scales
stay within +/-5%. See `shadow_cat_variation_preview.svg` before enabling it.
