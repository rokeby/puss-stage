# Stage wing and cue authoring

> **Long-form update:** For multi-sequence static previews, selectable pair
> anchors, attached lighting/objects/animation, bucket repetition, Opening, and
> Set Piece modes, use the UE5.8 `StageWingDirector` plugin documented in
> `Docs/StageWingDirectorAuthoring.md`. The cue workflow below remains supported
> for compact tests and backwards compatibility.

## What is implemented

`BP_StageConveyor` now has two authoring paths that share the same `BP_Wing.ApplyWingAppearance` function:

1. **Manual test path** — assign a few imported Static Meshes directly to `ManualWingSlots` on the placed conveyor.
2. **Cue path** — author rows in `DT_StageCues`; Right/Left Arrow steps through the ordered row names in PIE.

Both paths work with the existing editor child-actor preview. Cue lighting uses ordinary light actors grouped by Actor Tags, so lights remain directly placeable and art-directable in the level.

## Import the first FBXs

The FBXs exist on disk but are not yet imported as Unreal assets. Import these into `/Game/Stage/Meshes/Test`:

- `DerivedAssets/GeneratedWings/IMG_6231_root_log_pile_stage_prop_cutout/SM_IMG_6231_root_log_pile_stage_prop_cutout.fbx`
- `DerivedAssets/GeneratedWingsTest/IMG_6232_hay_mound_stage_prop_cutout_v2/SM_IMG_6232_hay_mound_stage_prop_cutout_v2.fbx`
- `DerivedAssets/GeneratedWingsTest/IMG_6250_stage_wing_transparent_v3/SM_IMG_6250_stage_wing_transparent_v3.fbx`

Use Static Mesh import, not Skeletal Mesh. Keep the generated material slots and textures. The pipeline reports the root/log piece as approximately 4.36 m x 2 m and the tall stage wing as approximately 7.86 m x 6.5 m, so expect to use the per-slot correction controls rather than normalizing every source asset destructively.

## Quick manual test

On the placed `BP_StageConveyor`:

1. Expand **Scenic Cues > Manual Test**.
2. Add entries to `ManualWingSlots` in the stable order below.
3. Set `ManualWingSlotCount` to the number of valid entries you created.
4. Enable `UseManualWingSlots`.
5. For each slot that should replace its placeholder, enable `UseAssignedMesh`, choose `Mesh`, then adjust `MeshOffset`, `MeshRotation`, and `MeshScale`.
6. Leave `UseAssignedMesh` off to retain the white placeholder in that slot. Disable `Visible` to make the slot empty.

Slot numbering is deterministic:

| Array index | Stage slot |
|---:|---|
| 0 | Layer 1 Left |
| 1 | Layer 1 Right |
| 2 | Layer 1 Top |
| 3 | Layer 2 Left |
| 4 | Layer 2 Right |
| 5 | Layer 2 Top |
| ... | Continue Left, Right, Top per deeper layer |

The editor preview uses this same order. No PIE restart is required when changing a slot mesh or correction transform.

## Cue authoring

Open `/Game/Stage/Data/DT_StageCues`. Each row is a performable scenic cue:

- `CueId` — stable identifier used for logging and external control later.
- `DisplayName` — human-readable cue name.
- `SectionId` — forest/path/place passage grouping.
- `WingSlots` — ordered slot structs using the same numbering above.
- `WingSlotCount` — number of valid entries in `WingSlots`.
- `LightingStates` — tagged light-rig states applied with the scenery.
- `DefaultTransitionSeconds` — intended scenic transition duration.
- `HoldHintSeconds` — rehearsal/show-control hint, not an automatic timer.
- `Notes` — narrative and staging notes.

On the conveyor, populate `CueOrder` with DataTable row names and set `CueCount` to the array length. In PIE:

- **Right Arrow** calls `NextCue`.
- **Left Arrow** calls `PreviousCue`.
- `EnableCueKeyboardControl` disables this temporary transport when external show control takes over.

The public `NextCue`, `PreviousCue`, `ResetCueSequence`, and `ApplyCueRow` functions are the stable control boundary for later MIDI, OSC, Stream Deck, keyboard, or performance-controller integration.

## Editor cue and lighting preview

To preview a complete cue without PIE:

1. Set `PreviewCueRow` to a row name from `DT_StageCues`.
2. Enable `UseCuePreviewInEditor`.
3. Keep `ShowPreviewInEditor` enabled.
4. Enable `PreviewLightingInEditor` after the cue's light tags exist.

For lighting, place and tune normal Unreal light actors in `StageTest`. Give each light actor an Actor Tag such as `LIGHT_ForestDawn` or `LIGHT_PathMoon`. A cue `LightingState` with the same `RigTag` controls:

- `Enabled` — component visibility in editor and PIE.
- `TargetIntensity` — base final intensity.
- `IntensityMultiplier` — cue multiplier; final intensity is Target x Multiplier.
- `Tint` — final light colour.
- `TransitionSeconds` — retained for the later fade/interpolation layer; current preview and cue switch apply the target immediately.

Each tagged actor should contain one primary Light Component. A cue can contain several lighting states, so key, fill, practicals, and background groups can be directed separately.

## Forty-five-minute structure

Do not encode the performance as one Timeline. Keep three scales of organization:

- **Section** — a major geographic/narrative passage. Use a Data Layer or Level Instance for large persistent scenery and its editable lighting rig.
- **Cue** — one operator-triggered change within a section. It selects wing slots and light-rig states.
- **Bucket** — a reusable pool of similar meshes for assisted or procedural filling later. `DT_StageWingBuckets` already has starter Trees, GroundPieces, and Architecture rows.

Explicit cue assignments remain authoritative. Buckets should generate or suggest a wing set, after which the result can be frozen and adjusted per slot. This preserves precise narrative direction while still making dense five-second passages practical to build.

At section boundaries, load or reveal the next Data Layer/Level Instance and keep `BP_StageConveyor` as the persistent cue transport. That gives each passage its own clean lighting/scenery workspace without splitting live control into unrelated systems.
