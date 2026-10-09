# Shadow-cat actions + action POV (P46/P46b, held patch)

Status: **HELD; never built or applied.** The C++ and Unreal automation tests exist only in
`Scripts/patches/2026-10-09_shadow_cat_actions.patch`. This folder contains an offline harness and two defaults
previews; none imports `unreal`. DRY changes nothing; guarded APPLY/REVERT are for the conductor's later closed-editor
build window. This job did not run either mutating mode and did not build.

## Verified foundations and UE 5.8 boundary

- **declaration-proven:** the rig-owned child cat follows the camera rig, because `ShadowCat` is attached below
  `ShadowFigureRoot` and that root below `SceneRoot` (`InfinityStageCameraRig.cpp:101-113`); evaluated route/offset
  camera motion is applied to the rig before the shadow root is re-positioned (`InfinityStageCameraRig.cpp:510-526`).
- **declaration-proven:** today's game path suppresses the body main pass in `ShouldDrawShadowCatBody`, then applies
  body rendering to each cat mesh (`InfinityStageCameraRig.cpp:258-318`). The authoring flags are declared at
  `InfinityStageCameraRig.h:159-169`.
- **declaration-proven:** Passage sections already expose Longitudinal, Lateral, Height, Pitch, Yaw, Roll and
  LookAhead channels (`MovieSceneInfinityPassageTrack.h:16-31`, `:160-182`). P46b therefore adds no off-route system.
- **binary-proven:** read-only strings from
  `E:/PussStage/Content/CharacterPacks/AnimX/_Common/CatMannequin/Mesh/CatMnq_Skeleton_ANX.uasset` include `Head`,
  `Neck`, `Neck_1`, `eye_L` and `eye_R`. The held patch defaults `HeadPOVBone` to `Head`; the eye midpoint is the
  per-action `HeadPOVOffsetCm`, not an invented skeleton socket (`p46b_offline_evidence.md:3-5`).
- **declaration-proven:** UE 5.8 says `bVisibleInRayTracing` controls ray-traced effects, while
  `bVisibleInReflections` is ignored by screen-space traces because SSR samples SceneColor
  (`D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/Engine/Classes/Components/PrimitiveComponent.h:471-481`). Reflection
  captures and scene-capture-only visibility are separate flags (`PrimitiveComponent.h:463-477`, `:714-718`).
- **declaration-proven:** `bOwnerNoSee` hides an entire primitive from its owner's view; it cannot mask only the head
  (`PrimitiveComponent.h:495-501`). `HideBoneByName` scales the named bone to zero and tracks it across LOD changes
  (`D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/Engine/Classes/Components/SkinnedMeshComponent.h:2145-2161`). The
  patch therefore hides `Head` only in `POVBody`; **inferred:** that also removes the head from this component's
  shadow/reflection, although the remaining body still casts a shadow.
- **declaration-proven:** the cine camera has a per-camera perspective near plane override
  (`D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/CinematicCamera/Public/CineCameraComponent.h:83-104`). The held patch
  refuses HeadPOV when `offset.X < near clip + clearance`, logs `SHADOW_CAT_HEAD_POV_REFUSED`, and restores the route
  camera's prior near-clip settings outside HeadPOV.
- **inferred (offline limitation):** no inspected header promises one skeletal primitive can be absent from the main
  view yet present in every Lumen, SSR, planar-reflection and capture path. `ReflectionOnly` follows the narrow
  declaration-supported route: main pass off, shadow retained, ray-tracing/reflection flags on. SSR cannot show it
  because there is no cat in SceneColor. Start look-down acceptance with a planar reflection on a small puddle; if
  UE 5.8's planar path also respects the main-pass exclusion, use a dedicated capture-only mirror proxy rather than
  weakening the POV camera rule. An SSR-friendly wet decal is suitable only when `POVBody` is acceptable in the view.

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

The harness runs `git apply --check --whitespace=error-all`, ports the phase, action envelope, seeded variation,
HeadPOV blend, visibility edge and near-clip maths, exercises positive and negative controls, and prints
`SHADOW_CAT_ACTIONS_HARNESS|...`.

Guarded conductor modes require an exact run id and confirmation. They census only the five named patch targets,
write `Backups/PreShadowCatActions-<run>/record.json` (or `PreShadowCatActionsRevert-<run>`) and copies before changing
anything, then read back the target census and P46b contract. No Unreal package is loaded or saved.

```powershell
python Tools/ShadowCatActions/shadow_cat_actions_harness.py --mode APPLY --run-id <run> --confirm APPLY_SHADOW_CAT_ACTIONS_<run>
python Tools/ShadowCatActions/shadow_cat_actions_harness.py --mode REVERT --run-id <run> --confirm REVERT_SHADOW_CAT_ACTIONS_<run>
```

## Build window (conductor, ordered; not run here)

1. Require every Unreal Editor closed. Record a run id and `git status --short`; refuse unrelated changes in any of
   the five patch targets.
2. Copy those five targets to `Backups/PreShadowCatActions-<run>/`: `InfinityStage.Build.cs`,
   `InfinityStageTypes.h`, `InfinityStageCameraRig.h`, `InfinityStageCameraRig.cpp`, and (if it already exists)
   `InfinityStageShadowCatActionTests.cpp`.
3. DRY: run the harness command above and require its failure count to be zero.
4. APPLY: use the guarded harness APPLY command above. Do not invoke raw `git apply`.
5. Census: `git diff --name-only` must add/change exactly the five targets above. Build with the documented Windows
   procedure and prove a new UTF-16 marker from the patch is in the DLL. Do not trust build exit code alone.
6. Run these singly:
   - `InfinityStage.Editor.ShadowCatActions.MasterTimePose`
   - `InfinityStage.Editor.ShadowCatActions.BlendContinuity`
   - `InfinityStage.Editor.ShadowCatActions.BobVariationDeterministicBounded`
   - `InfinityStage.Editor.ShadowCatActions.MovesWithPassage`
   - `InfinityStage.Editor.ShadowCatActions.CameraModeBlendContinuity`
   - `InfinityStage.Editor.ShadowCatActions.VisibilityModeEdges`
   - `InfinityStage.Editor.ShadowCatActions.POVDeterminismAndNearClip`
7. Then run the full suite and compare its warning count with the registered baseline. A build/test pass is not
   rendered acceptance.
8. Before any authored action exists, use the guarded harness REVERT command. Require the same five-file census to
   return clean and retain its pre-revert backup.

## Worked breath recipes (defaults for Gary to approve; apply nothing here)

All `StartFrame` values remain Passage-relative Show ticks. `HeadPOV` uses the action's existing BlendIn/BlendOut
envelope and is therefore Master-time locked. While the route moves, the existing direct gait remains the AnimX walk;
no trot clip is introduced. See `shadow_cat_pov_modes_preview.svg` before choosing offsets.

| Breath/action | Clip | CameraMode | BodyVisibility | Suggested score keys |
| --- | --- | --- | --- | --- |
| Stretch | `/Game/CharacterPacks/AnimX/_Common/CatMannequin/Anim/Idle/A_Cat_Idle_Stretching` | `HeadPOV` | `POVBody` | Route offsets unchanged; start with head offset `(12,0,3)` cm so front paws can enter frame. |
| Look down | `/Game/CharacterPacks/AnimX/_Common/CatMannequin/Anim/Idle/A_Cat_Idle_LookDown` | `HeadPOV` | `ReflectionOnly` | Route offsets unchanged; place/approve the puddle separately and test the planar-reflection boundary above. |
| Sharpen claws | `/Game/CharacterPacks/AnimX/_Common/CatMannequin/Anim/Action/A_Cat_Action_SharpensClaws` | `HeadPOV` | `POVBody` | Example only: at `t-2s` `(Long=0, Lat=0, Yaw=0)`; `t-0.5s` `(Long=150cm, Lat=Gary-approved wing side, Yaw=Gary-approved wing angle)`; hold through action; restore all three by `end+1.5s`. Never copy a sign without checking the chosen wing side. |
| Sit and lick | `/Game/CharacterPacks/AnimX/_Common/CatMannequin/Anim/Action/A_Cat_Action_Licking_sit` | `HeadPOV` | `POVBody` | Route offsets unchanged; tune local eye offset so the raised paw, not the hidden head, crosses frame. |
| Sleep transition | `/Game/CharacterPacks/AnimX/_Common/CatMannequin/Anim/Rest/A_Cat_Rest_Sleep_to` (optionally `A_Cat_Rest_Lie_to` first) | `HeadPOV` | `POVBody` | Route offsets unchanged; `bHoldLastFrame=true` only if no `A_Cat_Rest_Sleep_idle` follow-up is scored. Dog coordination stays outside this patch. |
| Sleep idle | `/Game/CharacterPacks/AnimX/_Common/CatMannequin/Anim/Rest/A_Cat_Rest_Sleep_idle` | `HeadPOV` | `POVBody` | Start after the transition and hold to the end-of-show boundary. |
| Optional P05 crouch | `/Game/CharacterPacks/AnimX/_Common/CatMannequin/Anim/Crouch/A_Cat_Move_Crouch_F` | `Route` | `ShadowOnly` | Use only in the separately authored low P05 sequence; no dog crouch coupling is added. |

**measured (read-only file census):** all eight named `.uasset` clips above, including `A_Cat_Rest_Lie_to` and
`A_Cat_Move_Crouch_F`, exist under the absolute main-tree AnimX folders (`p46b_offline_evidence.md:6-17`).
**inferred:** their framing and contact quality remain unaccepted until Gary reviews a rendered build-window pass.

## Add `Idle_Stretching` at Passage P03 +42 s

After the patch has passed its build window, edit only the Show asset
`/Game/InfinityStage/Dev/DA_InfinityStage_V1Show`. In P03's `PassageSettings` row, append one `ShadowCatActions`
element:

- Animation: `/Game/CharacterPacks/AnimX/_Common/CatMannequin/Anim/Idle/A_Cat_Idle_Stretching`
- StartFrame: `42 * Show.TickResolution` (at 24,000 ticks/s: `1,008,000`)
- PlayRate: `1.0`; BlendInSeconds: `0.25`; BlendOutSeconds: `0.25`; HoldLastFrame: `false`
- CameraMode: `HeadPOV`; BodyVisibility: `POVBody`; HeadPOVBone: `Head`; HeadPOVOffsetCm: `(12,0,3)`
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
