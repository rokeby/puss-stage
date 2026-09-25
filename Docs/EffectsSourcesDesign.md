# Effects sources — design

Owned by the **"Puss · Effects sources"** session. Written 2026-09-25, before any
building: per the brief, this stream designs now and builds only once the
conductor says the gridiron and ground are in. Read
`Docs/Conductor/CONTAINER_WORLD_PLAN_2026-09-25.md` and
`Docs/Conductor/BRIEF_EFFECTS_SOURCES_2026-09-25.md` first.

## What it is

Practical weather-making devices that sit in the machine and can be seen doing
their job: a haze pot pumping in the wings, a kettle venting steam, a fire basket.
Each one does two things:

1. **Shows the apparatus and its output**: a mesh plus a small Niagara plume or
   flame. This is what the audience reads as "the theatre is making this".
2. **Leaves a local medium behind**: a Local Fog Volume downstream of the
   nozzle. It is what makes a beam shaft read *in this bay* rather than
   everywhere. Local haze density, not more global fog, is what turns a uniform
   fog into atmosphere.

The second point matters most. Verified in the 5.8 engine shaders:
`Shaders/Private/VolumetricFog.usf` includes `LocalFogVolumeCommon.ush` under
`USE_LOCAL_FOG_VOLUMES` and reads each `FLocalFogVolumeGPUInstanceData` while it
builds the froxel grid. That means Local Fog Volumes are voxelised into
volumetric fog, lit by the rig's spots, and shadowed by their volumetric shadows.
They are analytic (a sphere plus a height falloff), with no particles and no
overdraw, so they cost far less than making the Niagara plume itself dense
enough to carry a beam.

## Data: one `Effect` kind, sub-typed in an Effects-owned header

**Recommendation:** add a single `Effect` value to `EInfinityAttachmentKind`, not
three separate `Haze`/`Fire`/`Smoke` values. Choose the sub-type with an enum
that lives in a new header this stream owns. Light already works this way: one
`Light` kind, with `Lighting.Type` choosing Spot, Rect or Point. With this
design, adding Steam, sparks or dust falling from the grid never needs another
change to the shared file.

Proposed contents of the new header
`Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageEffectTypes.h`
(not yet in the tree; see "Sequencing" for why):

```cpp
UENUM(BlueprintType)
enum class EInfinityStageEffectType : uint8
{
    Haze,   // smoke pot / bellows: fine, long-lived, feeds the medium
    Smoke,  // heavier, darker, shorter-lived puffs
    Steam,  // kettle / boiler vent: white, fast, rises, dissipates quickly
    Fire    // fire basket / cresset: flame + embers, drives a linked light
};

USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityStageEffectSettings
{
    GENERATED_BODY()

    EInfinityStageEffectType Type = EInfinityStageEffectType::Haze;

    // 0..1, pushed to the Niagara user parameter User.Output (spawn rate / flame size).
    float Output = 0.5f;
    FLinearColor Tint = FLinearColor::White;

    // Pumping: a haze pot is worked by hand, not run continuously. 0 period = steady.
    // The phase is seeded from cue+attachment identity, so a replay is identical.
    float PulsePeriodSeconds = 6.0f;
    float PulseDuty = 0.35f;

    // The medium this source leaves in its bay (a Local Fog Volume, lit by the rig).
    bool bFeedsLocalMedium = true;
    FVector MediumOffsetCm = FVector(250.0, 0.0, 150.0); // downstream, in source space
    float MediumRadiusCm = 400.0f;
    float MediumDensity = 0.15f;       // LFV RadialFogExtinction; stays modest
    float MediumHeightFalloff = 1000.0f;

    // Cost control: plume and flicker run only within this distance of the view.
    float ActiveRadiusCm = 6000.0f;

    // Fire only: flicker a sibling Light attachment on the same cue. That light is
    // Rig & atmosphere's; this never creates a light of its own.
    FGuid LinkedLightAttachmentGuid;
    float FlickerAmount = 0.25f;

    // Set on replicated copies, so a later re-replication removes only its own
    // copies and never a hand-placed source.
    FGuid ReplicatedFromAttachmentGuid;
};
```

(`UPROPERTY` metadata is left out above for readability. Every field gets
`EditAnywhere, BlueprintReadWrite`, with clamps and `Units = "cm"` in the same
style as `FInfinityStageLightSettings`.)

The attachment still supplies everything it already gives other kinds: `Anchor`
(`Station` for anything that sits on the floor in the wings), `RelativeTransform`
(its rotation is the nozzle's aim), `ActorClass` (the apparatus Blueprint),
`Label` and `bEnabled`. Nothing is duplicated.

## The shared change, in full, for the conductor to make once

The request is to make the whole shared footprint in one pass, together with
whatever Rig & atmosphere needs from the same enum.

**A. `InfinityStageTypes.h`**

```cpp
#include "InfinityStageEffectTypes.h"      // Effects-owned, new

enum class EInfinityAttachmentKind : uint8
{
    Prop,
    Light,
    AnimationTrigger,
    Sound,
    Effect                                  // appended, so existing values keep their numbers
};

// in FInfinityCueAttachment, after Lighting:
UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect",
    meta = (ShowOnlyInnerProperties,
        EditCondition = "Kind == EInfinityAttachmentKind::Effect", EditConditionHides))
FInfinityStageEffectSettings Effect;
```

This needs no custom-version bump. A new struct member and an appended enum value
both load cleanly from old Show assets through tagged property serialisation.

**B. `InfinityStagePassageActor.cpp`, `MaterializeAttachments`**: two insertions
that mirror the Light path exactly and call into Effects-owned code:

```cpp
// beside the Light fallback (≈ line 811)
if (!SpawnClass && Attachment.Kind == EInfinityAttachmentKind::Effect)
{
    SpawnClass = AInfinityStageEffectSource::ResolveDefaultClass(Attachment.Effect);
}

// beside ApplyAttachmentLightSettings, after AttachToActor (≈ line 879)
if (Attachment.Kind == EInfinityAttachmentKind::Effect)
{
    AInfinityStageEffectSource::ApplyAttachment(*Spawned, Cue.CueGuid, Attachment);
}
```

A hook is required because settings have to be applied after spawn and after
parenting, the same as for lights. The spawned actor cannot find out its own
identity during `OnConstruction`, because the identity tag is added only after
`SpawnActor` returns.

**Needs no change:** `Build.cs` and `.uplugin` (see "No Niagara module
dependency" below), `InfinityStageShowAsset.cpp` (replication goes in
Effects-owned files), and the move write-back in `InfinityStageEditorModule.cpp`,
which is already kind-agnostic, so dragging an emitter writes its offset back to
the Show for free.

**Later and optional (phase 2), not needed to start:**
`HandleLevelActorDeleted` filters on `!= Light`. Widening it to include `Effect`
would make deleting an emitter in the level delete it from the Show. Until then,
a deleted emitter comes back on the next materialize, which is safe. Cue Desk
"Add Haze / Fire Source" buttons in `SInfinityStageCueDesk.cpp` are also
optional: until they exist, authoring goes through Python calling the library
below.

## Code this stream owns (all new files)

| File | What |
| --- | --- |
| `Public/InfinityStageEffectTypes.h` | The enum and settings struct above |
| `Public/InfinityStageEffectSource.h`, `Private/…cpp` | `AInfinityStageEffectSource`: apparatus base actor; `ResolveDefaultClass`, `ApplyAttachment`; pulse, distance gating and fire flicker; editor write-back of its own settings |
| `Public/InfinityStageEffectLibrary.h`, `Private/…cpp` | Stride replication (below), `BlueprintCallable` so that Unreal Python and MCP can drive it |
| `InfinityStageTests/Private/InfinityStageEffectTests.cpp` | Round-trip, stride selection, "re-replication removes only its own copies", determinism |
| `/Game/Scenes/Effects/` | `BP_Effect_HazePot`, `BP_Effect_SteamKettle`, `BP_Effect_FireBasket`, `NS_*`, `M_*` |
| `Saved/CodexEffects/` | Authoring and read-back scripts, following the MCP runbook |

**No Niagara module dependency.** `UFXSystemComponent`, the base class of
`UNiagaraComponent`, lives in the Engine module and exposes
`SetFloatParameter`, `SetColorParameter`, `SetBoolParameter`,
`SetVectorParameter` and `ActivateSystem` as virtuals (verified in 5.8,
`Particles/ParticleSystemComponent.h:386–466`). The apparatus Blueprints carry
the Niagara component, and the C++ base finds it as a `UFXSystemComponent` and
pushes the Show-owned parameters. `ULocalFogVolumeComponent` is Engine too, with
`ENGINE_API` setters. The runtime module therefore gains no dependency, and the
shared `Build.cs` and `.uplugin` stay untouched.

**Details-panel write-back without touching the editor module.** The actor
exposes its `FInfinityStageEffectSettings` as an editable property. Its
`PostEditChangeProperty` (editor-only) finds its owning Passage through
`GetAttachParentActor()` → `FindAttachmentByActor`, writes the settings and
offset into the Show's attachment, and logs
`INFINITY_STAGE_ATTACHMENT_EFFECT_UPDATED … save it intentionally`. The Show
stays the only authority, just as it does for lights.

## Placement: stride replication, not whole-corridor copy

`ReplicateLightAttachments` copies the source's lights to **every** target bay.
That is right for the rig and wrong here. A haze pot on each of 261 pairs is
exactly the "many emitters" the brief warns against. Effects therefore get
their own replication in `InfinityStageEffectLibrary`:

- **Scope**: Selection / Whole Passage / Entire Show, the same scopes the Cue
  Desk already offers.
- **Stride N and phase**: the source's effect attachments are copied onto every
  Nth wing pair in the scope, counted by wing ordinal within the Passage.
- **Seeded variation**: jitter on output, pulse phase, position and aim, using
  one stream per target cue as `ReplicateLightAttachmentsWithVariation` does.
  The same seed always gives the same corridor.
- **Owns only what it made**: copies carry `ReplicatedFromAttachmentGuid`.
  Re-running with a new stride first removes the copies from that source within
  the scope, then lays new ones. Hand-placed single sources are never touched.
  This is the plan's "generate the spine, hand-place the accidents".

**Proposed default:** haze pots on the beam bays, because a shaft needs a medium
where it falls. The beam fixtures sit on every 4th bay, so a stride of **12**
(every third beam bay) gives:

| Passage | Pairs | Sources at stride 12 |
| --- | ---: | ---: |
| P01 | 48 | 4 |
| P02 | 23 | 2 |
| P03 | 21 | 2 |
| P04 | 21 | 2 |
| P05 | 93 | 8 |
| P06 | 55 | 5 |
| **Show** | **261** | **23** |

Bays are about 500 cm apart (P01 about 600), so an `ActiveRadiusCm` of 6000
spans roughly ±12 bays. **At most 2–3 plumes run at any moment.** Fire and steam
are accents, hand-placed a few per Passage rather than replicated.

**P05 is 497 cm wide against P01's 1244.** A medium radius that suits P01 would
fill P05 wall to wall. `MediumRadiusCm` is per-attachment, so the default per
Passage should scale to corridor width. The first spike should measure this
rather than guess it.

## Budget

These constraints are inherited: VSM one-pass overflow with about 541 shadow
casters plus 136 volumetric ones, about 2,500 light actors, and a global medium
at density 0.022, falloff 0.12 and extinction 0.9 that Rig & atmosphere owns and
that this stream must not fight.

| Element | Rule |
| --- | --- |
| Local Fog Volume | Analytic, no particles. Radius scaled to the corridor; density modest against the global medium. Aim for ≤ 6 inside the view frustum. |
| Haze/steam plume | GPU sim, ≤ 256 particles per active source, translucency lighting *Volumetric NonDirectional*, no shadows. **No Volume-domain particles in v1**: voxelising every particle into the froxel grid is the expensive path, and the LFV already does that job. |
| Distance gating | Plume deactivated and flicker stopped beyond `ActiveRadiusCm`. The apparatus mesh and the LFV stay, so the bay keeps its medium. |
| Fire | Additive or emissive flipbook, no lit translucency. Its light is a Rig-owned attachment linked by GUID, and it should be **non-shadow-casting** because of the VSM overflow. That is a request to Rig & atmosphere, not a decision for this stream. |
| Target | Effects add **≤ 1 ms GPU** in the worst view. This is a proposal: the frame budget is for the conductor and user to confirm. |

**Measurement** uses `stat GPU` (VolumetricFog, Translucency, Niagara passes)
and `stat Niagara`, before and after, at two views: a P01 beam bay and P05, the
narrowest corridor.

## Apparatus in the Baroque register

The rule here is that these are devices a Baroque theatre could have built:
wood, iron, copper, leather, canvas. None of them is an electric fogger.

- **Haze pot**: an iron brazier with a copper hood, fed by a lever-worked
  leather bellows, with a canvas hose to a nozzle at the wing edge. Its pumping
  is the pulse.
- **Steam kettle**: a riveted copper boiler over a firebox, with a valve and
  vent pipe.
- **Fire basket (cresset)**: an iron basket on a pole or on the floor, holding
  embers and flame.

The meshes are Blender work. They stay as grey engine primitives through the
overnight run (see Decisions), and the route for making them is to be settled
with the conductor when the effects work starts. Found assets such as
StarterContent's `Blueprint_Effect_Fire` may serve as greybox references only.

## Sequencing

1. **Now, design only**: this document; the shared-change request goes to the
   conductor, so it can be batched with Rig & atmosphere's enum needs.
2. **First spike, once the conductor opens a slot on the editor and MCP**: one
   hand-placed Local Fog Volume in one P01 beam bay, never saved. Capture before
   and after screenshots and the `stat GPU` VolumetricFog delta. This proves
   that the mechanism carries the beam, and what it costs, before any code
   exists. It is a transient actor, so it involves no Show or level mutation and
   needs no backup.
3. **On the conductor's go (gridiron and ground in)**: land
   `InfinityStageEffectTypes.h` first, then the conductor makes change A+B, then
   the actor, library and tests. After that come the build through the gate,
   the suite, and then the Blueprints and Niagara systems. The header is held
   back until then deliberately: a USTRUCT header in `Public/` is parsed by UHT
   on every build, so an unused draft would put other streams' builds at risk.
4. **Placement**: replicate onto the beam bays, run the read-back with zero
   dirty packages, then hand over to the user for rendered acceptance, at night,
   under raking beams.

Every Show or level mutation takes a `Backups/PreEffects…-YYYYMMDD-HHMM`
snapshot first, and every script asserts the Puss world on port 8010 before it
changes anything.

## Decisions (conductor, 2026-09-25)

- **One `Effect` kind, with sub-types: accepted.** When the conductor opens
  attachment kinds, it will make the shared change once, working from
  § "The shared change" as written.
- **The first spike is approved** for a gap in Phase B: a transient, unsaved
  Local Fog Volume in one P01 beam bay. It is low priority and waits for a slot.
- **Apparatus stays greybox through the overnight run.** Soft goods has moved
  from the Blender bake to Chaos Cloth, with Blender now a pattern cutter, and it
  is fully committed to that. Do not queue apparatus meshes there.

## Open questions

For the conductor (pending, and not to be designed around):
- Does Rig & atmosphere need its own `EInfinityAttachmentKind` values? Fixture
  bodies may turn out to be a mesh field on the Light settings instead. If they
  do need values, both go in the same pass.

For the user. The conductor is holding these until the effects work starts,
rather than batching them with tonight's decisions:
- Density: stride 12 (about 23 haze pots in the Show, 2–3 working at once), or
  stride 8 (about 33)?
- Should the pots pump to the music (puffs on phrase boundaries) or on their
  own clock?
- Real fire, or stage fire? Baroque and later theatres made flame from **silk
  streamers blown by a fan and lit red from below**. That is exactly this
  project's register, a painted and mechanical effect rather than a simulated
  one. It would be Soft goods cloth (now on the Chaos Cloth route) plus a linked
  light. Both are possible; they read very differently.
