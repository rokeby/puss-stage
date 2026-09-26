# Effects sources — design

Owned by the **"Puss · Effects sources"** session. Started 2026-09-25 as design
only. The stream was activated the same night: Gary asked, unprompted, for
"smaller effects, maybe floating niagara artefacts... flames burning down some
wings". Read `Docs/Conductor/CONTAINER_WORLD_PLAN_2026-09-25.md` and
`Docs/Conductor/BRIEF_EFFECTS_SOURCES_2026-09-25.md` first.

**State:** the C++ is written in new files and reviewed by hand against the 5.8
engine headers. It is **not built**. The conductor has landed the whole shared
footprint as specified below: **A and B** in `63e5500`, **C and C2** in
`e0c2c2f`. Nothing more is owed before the build window.

**Read shafts and motes against the right light.** The conductor's shaft A/B
(2026-09-25) found **no visible shaft at the beam bays yet**. Every beam lamp
throws forward, away from the camera, so only back-scatter is seen, and the fog
dims the scene by about 32% while giving nothing back. Rig & atmosphere is
turning some of the P03 lamps to throw back toward the audience, which is how
stage haze has always been lit. Until that lands, "where the light already is"
means where it is *supposed* to be. The Local Fog Volume spike therefore goes
in a **back-lit P03 bay** once Rig's change is in, not a P01 beam bay. There, a
null result would prove nothing about the mechanism. Motes are judged on the
same condition.

## What it is

Practical weather-making devices that sit in the machine and can be seen doing
their job. Each one does two things:

1. **Shows the apparatus and its output**: a mesh plus a small Niagara plume or
   flame, so the audience reads that the theatre is making this.
2. **Leaves a local medium behind**: a Local Fog Volume downstream of the
   nozzle. It makes a beam read *in this bay* rather than everywhere, and it is
   local haze density, not more global fog, that turns fog into atmosphere.

This works because of an engine fact, verified in the 5.8 shaders:
`VolumetricFog.usf` includes `LocalFogVolumeCommon.ush` under
`USE_LOCAL_FOG_VOLUMES`. Local Fog Volumes are therefore voxelised into
volumetric fog, lit by the rig's spots, and shadowed by their volumetric
shadows. They are analytic, with no particles and no overdraw.

## Types: one `Effect` kind, sub-typed here

The conductor accepted one `Effect` value in `EInfinityAttachmentKind`. The
sub-type lives in `InfinityStageEffectTypes.h`, which this stream owns, so a new
effect never needs the shared enum again.

| Type | What | Apparatus | Medium | Drives another actor (game worlds only) |
| --- | --- | --- | --- | --- |
| Haze | hand-worked smoke pot, pumping | yes | yes | — |
| Smoke | heavier, darker puffs | yes | yes | — |
| Steam | kettle vent, fast, clears quickly | yes | small | — |
| Fire | basket / cresset | yes | no | flickers a linked rig light |
| **WingBurn** | flame consuming the panel it is anchored to | no | no | the wing's char (custom data) and a linked light |
| **Motes** | dust, ash and motes adrift in a bay | no | no | — |

`FInfinityStageEffectSettings` in the same header carries the settings:
- common: output, tint, active radius;
- pumping: period and duty (the phase is seeded from identity);
- medium: offset, radius, density, falloff;
- fire: linked light and flicker amount;
- wing burn: start-ahead distance, span, and ignition UV;
- motes: extent;
- replication provenance.

**Wing Burn is driven by camera travel, not the clock.** The burn starts when
the show camera is `BurnStartAheadCm` short of the wing along the route. It is
complete after a further `BurnSpanCm` of travel. Scrubbing, replay and Movie
Render Queue all give the same burn, and re-timing the music re-times it too.
The camera is the camera rig's `Camera`, projected onto the owning Passage's
route. It is never taken from whichever viewport happens to be looking.

**Motes go where the light already is.** Particles are invisible in the dark
and read strongly in a shaft. Place them with `SelectBeamBays` (below).

## The wing-burn handshake with Wing materiality (agreed)

Wing materiality confirmed the channel on 2026-09-25: per-instance custom data
on the Passage's wing ISMs. It is not a material scalar, because every panel
sharing a material instance would burn together. It is not a MID, because that
would be saved into the level. It is not a world-space MPC sphere, because
panels are 10 m and bays about 5 m, so it would bleed onto neighbours.

| Slot | Meaning | Written by |
| --- | --- | --- |
| 0 | BurnProgress, 0 intact → 1 consumed | Wing Burn effect, game worlds only |
| 1, 2 | Ignition U, V: 0..1 on the panel face, V down; default (0.5, 1.0), so fire climbs | Wing Burn effect |
| 3 | VariationSeed 0..1, so the same wing looks the same every night | the Passage at materialize (change C) |

The layout is `InfinityStageWingCustomData` in `InfinityStageEffectTypes.h`,
with 4 floats in total.

The material (`M_Wing_PaintedSurface_Master`, Wing materiality's) burns in UV
space, converting to centimetres per material instance. It chars, then shows an
ember band, then clips to a hole behind the front so that stage light comes
through. It takes `max(MI BurnPreview, custom data)`, so the look can be
authored in the editor. `UseBurn` is on for the two P01 trial material
instances: `SM_R__1_roccoco` (16 panels) and `SM_CloudCeilingSmall_02_C` (24
ceiling panels).

**The front, agreed with Wing materiality:**
- Mean radius in cm = `BurnProgress × (Dmax + 130)`.
- `Dmax` is the distance from the ignition point to the farthest corner of the
  **UV square**.
- 130 is `IrregularityCm/2 + 1.25 × BurnEdgeCm` at the master's defaults, and is
  `InfinityStageWingBurn::FrontPadCm` in code. Wing materiality will not vary it
  per material instance without saying so.
- The visible char wanders about ±80 cm around that mean. The flames follow the
  mean, so a little overlap into the ember band is intended.

**The mesh bounds are not the UV square.** Images carry transparent margins:
`SM_CloudCeilingSmall_02_C`'s UV square is 4726 × 1889 cm on a 2129 × 1000 cm
mesh. Every wing mesh has exact planar UVs, identical on Front, Back and Edge:
- `U = aU·Y + bU` and `V = aV·Z + bV`, in mesh-local cm, with X as thickness.
- `aV < 0` on all 149 meshes: V runs down, with V = 0 at the top.
- `aU < 0` on 145 meshes, so its sign is never assumed.

These are measured by `Saved/CodexWingMateriality/probe_uv_axes_readonly.py`
(committed in `320cbb9`; re-run it rather than trusting `uv_axes.json`). Each
Wing Burn attachment carries its own `BurnUAxis`, `BurnVAxis` and
`BurnUVMeasuredMesh`, recorded with `SetWingBurnUVMapping`. That keeps the Show
the authority and PIE, MRQ and cooked runs identical. A burn on a different
mesh logs `INFINITY_STAGE_EFFECT_BURN_UV_STALE`. Only the flames depend on the
mapping, because the char is drawn in UV space.

The flame Niagara receives, in panel-local space:
- `User.BurnProgress` and `User.FrontRadiusCm` (the agreed formula, worked out
  in C++ as `ComputeBurnFront`);
- `User.IgnitionLocal`;
- `User.UVRectMin` / `User.UVRectMax` (the image square, to clip spawning);
- `User.PanelOrigin` / `User.PanelExtent` (bounds, used only for the thickness).

## The shared change, in full, for the conductor to make once

**A. `InfinityStageTypes.h`**

```cpp
#include "InfinityStageEffectTypes.h"      // Effects-owned

enum class EInfinityAttachmentKind : uint8
{
    Prop,
    Light,
    AnimationTrigger,
    Sound,
    Effect                                  // appended
};

// in FInfinityCueAttachment, after Lighting:
UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect",
    meta = (ShowOnlyInnerProperties,
        EditCondition = "Kind == EInfinityAttachmentKind::Effect", EditConditionHides))
FInfinityStageEffectSettings Effect;
```

This needs no custom-version bump. Appended enum values and new struct members
load cleanly through tagged property serialisation.

**B. `InfinityStagePassageActor.cpp`, `MaterializeAttachments`**: two
insertions, plus `#include "InfinityStageEffectSource.h"`:

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

`ResolveDefaultClass` never returns null. It checks
`FPackageName::DoesPackageExist` first, so until the Blueprints exist it returns
the native greybox silently.

**C. `InfinityStagePassageActor.cpp`, `AddPanelInstance`**: when a managed wing
ISM is created, just after `SetHasPerInstancePrevTransforms(true)` and before
any instance is added (the call resets the buffer):

```cpp
Component->SetNumCustomDataFloats(InfinityStageWingCustomData::NumFloats);
```

**C2 (Wing materiality's request, the conductor's call):** after each instance
is added, write a deterministic seed from the cue and side into
`InfinityStageWingCustomData::VariationSeed`.

Existing levels take the floats on their next materialize, because the
components are recreated. Until C lands, a Wing Burn logs
`INFINITY_STAGE_EFFECT_BURN_NO_CUSTOM_DATA` once and chars nothing. Nothing
breaks.

**Needs no change:** `Build.cs` and `.uplugin`. Niagara is driven through
`UFXSystemComponent` and the medium is a `ULocalFogVolumeComponent`, both in the
Engine module. The move write-back is kind-agnostic, so dragging an effect
writes its offset to the Show.

**Phase 2, through the conductor:** widening `HandleLevelActorDeleted` to
`Effect`, and Cue Desk buttons. `SInfinityStageCueDesk.cpp` is currently held by
Look & camera.

## Code this stream owns (all new files)

| File | What |
| --- | --- |
| `InfinityStage/Public/InfinityStageEffectTypes.h` | Custom-data layout, `EInfinityStageEffectType`, `FInfinityStageEffectSettings`, `FInfinityEffectReplicationVariation` |
| `InfinityStage/Public/InfinityStageEffectSource.h`, `Private/…cpp` | `AInfinityStageEffectSource` (details below) |
| `InfinityStage/Public/InfinityStageEffectLibrary.h`, `Private/…cpp` | Authoring and stride replication, `BlueprintCallable` for Unreal Python and MCP |
| `InfinityStageTests/Private/InfinityStageEffectTests.cpp` | Eight tests (below) |
| `/Game/Scenes/Effects/` | `BP_Effect_HazePot`, `…_SmokePot`, `…_SteamKettle`, `…_FireBasket`, `…_WingBurn`, `…_Motes`, with their `NS_*` and `M_*` |
| `Saved/CodexEffects/` | Authoring and read-back scripts, following the MCP runbook |

What `AInfinityStageEffectSource` does:
- **Greybox**: a cube for the apparatus plus a Local Fog Volume.
- **Show-owned settings**: pushed to FX systems as User parameters (`Output`,
  `Tint`, `Pump`, `BurnProgress`, `Ignition`, `Extent`, `PanelOrigin`,
  `PanelExtent`).
- **Distance gating** against `UWorld::ViewLocationsRenderedLastFrame`, so it
  follows the editor viewport, PIE or Movie Render Queue, whichever is actually
  rendering.
- **Panel tracking**: the actor's current offset from the panel's rest pose is
  re-applied to the live instance. Wing travel and a viewport drag therefore both
  hold, with no per-tick Show compile. `GetCuePlacementTransforms` compiles the
  whole Show on every call, so it is avoided.
- **Details-panel write-back** to the Show (`INFINITY_STAGE_ATTACHMENT_EFFECT_UPDATED`)
  from its own `PostEditChangeProperty`, with no change to the editor module.

**Anything that writes into another actor runs only in game worlds** (PIE and
Movie Render Queue, whose packages are never saved). That covers the wing's
custom data and the rig light's flicker. The engine `.cpp` files are not in this
install, so it cannot be confirmed that `SetCustomDataValue` does not call
`Modify()` and dirty the editor level. The editor world keeps zero dirty
packages at rest.

Tests (`InfinityStage.Effects.*`, eight):
- `BurnProgressFollowsCameraTravel`
- `BurnFrontFollowsTheWingMastersContract` (formula, pad, and both signs of U)
- `PumpIsSoftEdgedPhasedAndBounded`
- `StrideCountsAfreshWithinEachPassage`
- `BeamBaysAreThoseWithVolumetricFixtures`
- `ReplicationOwnsOnlyItsCopies`
- `VariationIsSeededAndBounded`
- `MaterializeSpawnsAndTracksEffectSources`, the integration test for hook B:
  it spawns, configures and panel-tracks a Haze and a Wing Burn through a real
  materialize.

## Placement: selection, then replication

`ReplicateLightAttachments` copies to **every** target bay: right for a rig,
wrong for a smoke pot. Effects are placed by choosing the bays first:

- `SelectBeamBays(Show, Cues, MinScattering = 5)` returns the bays with an
  enabled light casting a volumetric shadow at scattering 5 or more. The rig's
  136 beam fixtures run at 9.0 and everything else at 0.6.
- `SelectEveryNthPerPassage(Show, Cues, Stride, Phase)` counts **among the given
  cues**, afresh in each Passage and in Show order. Over beam bays, stride 3
  means every third beam bay.
- `ReplicateEffectAttachments(Show, Source, Scope, Targets, Variation)` copies
  the source cue's hand-placed effects onto exactly the targets. It first clears
  that source's earlier copies from the scope and the targets, so a changed
  stride leaves nothing stale. Copy identities are deterministic, variation is
  seeded per target, and a fire's linked light is re-pointed to the target
  pair's light in the same ordinal slot.
- `ClearReplicatedEffects(Show, Source or invalid, Scope)` removes copies only.
  Hand-placed effects are never touched.
- `AddEffectAttachment(Show, Cue, Type, Anchor, Offset, Label)` and
  `MakeDefaultEffectSettings(Type)` are for hand placement.

A Details edit to a replicated copy is written to the Show, but the next
replication from that source replaces it. The log line says `replicated=true`
so this is visible.

**Proposed default:** haze pots on every third beam bay (about every 12th pair),
which is about 23 in the Show and 2–3 working at once. Motes go on beam bays.
Fire and wing burns are hand-placed accidents, never replicated.

| Passage | Pairs | Pots at every 3rd beam bay |
| --- | ---: | ---: |
| P01 | 48 | 4 |
| P02 | 23 | 2 |
| P03 | 21 | 2 |
| P04 | 21 | 2 |
| P05 | 93 | 8 |
| P06 | 55 | 5 |

P05 is 497 cm wide against P01's 1244 cm, so `MediumRadiusCm` should scale with
the corridor.

## Budget

| Element | Rule |
| --- | --- |
| Local Fog Volume | Analytic; radius scaled to the corridor; density modest against the global 0.022; aim for ≤ 6 in view |
| Plume | GPU sim, ≤ 256 particles per active source, Volumetric NonDirectional lighting, no shadows, **no Volume-domain particles** in v1 |
| Gating | Plume off beyond `ActiveRadiusCm`; the apparatus and medium stay |
| Fire / burn light | Rig-owned, linked by GUID, **non-shadow-casting** because of the VSM overflow (a request to Rig & atmosphere). **One writer per lamp:** if the linked light has Light Drama active, the effect yields (`INFINITY_STAGE_EFFECT_LIGHT_YIELDED`) and never flickers it |
| Burn writes | `SetCustomDataValue(…, true)` re-creates that one wing ISM's render state each frame, but only during the burn window. Components hold about 5 instances each (765 panels over 149 meshes), so this is expected to be cheap. To be measured. |
| Target | ≤ 1 ms GPU in the worst view (proposed; the frame budget is for the conductor and user to confirm) |

## Wing-burn PIE proof: procedure

This runs after the build window and needs one conductor editor slot. It must
be followed as written, because a read-back taken against the wrong state
proves nothing.

1. Take a backup: `Backups/PreEffectsBurnProof-YYYYMMDD-HHMM` covering the Show
   and level. Assert the Puss world on port 8010.
2. Add one Wing Burn to a `SM_R__1_roccoco` panel in P01, anchored to its side,
   with `AddEffectAttachment`. Record its UV mapping with `SetWingBurnUVMapping`,
   using values from a fresh run of
   `Saved/CodexWingMateriality/probe_uv_axes_readonly.py`.
3. **Re-materialize P01.** This one mutation both spawns the burn actor and
   recreates the wing ISMs with 4 custom floats. Components serialized before
   change C have 0 floats, and burn writes to them are dropped (logged once as
   `INFINITY_STAGE_EFFECT_BURN_NO_CUSTOM_DATA`).
4. **Check `NumCustomDataFloats == 4`** on that panel's component before trusting
   anything else.
5. In PIE, at several show-camera distances (before, during and after the burn
   window), read back and send to Wing materiality:
   - the instance index;
   - the ignition UV;
   - slots 0–3;
   - `FrontRadiusCm`.
   They check the front against where their char line should sit in local cm.
6. Save only the Show and the level; end with zero dirty packages. The user
   judges the look.

The pad (`FrontPadCm` = 130) is coupled to the master's `IrregularityCm` and
`BurnEdgeCm`. Wing materiality marked those parameters in `e8a29d5` and in
`Docs/WingMateriality.md`: change both sides together, never per material
instance.

## Unverified, and where each gets proved

- Local Fog Volume base size (radius or diameter at scale 1), and whether a
  volume inside volumetric fog scatters with its own `FogPhaseG` or the global
  distribution (0.55): the first rendered spike, in a back-lit bay.
- Per-instance custom data on Nanite wings in 5.8: Wing materiality proves it on
  one Nanite and one non-Nanite panel in PIE once C lands.
- Whether `SetCustomDataValue` dirties the editor level: avoided by design
  (game-world only), not proved.
- Every line of this C++: build exit 0, the UTF-16 marker in the DLL, and the
  suite with the eight new tests. All of that happens in the conductor's build
  window.

## Decisions

Conductor, 2026-09-25:
- One `Effect` kind, sub-typed.
- The Local Fog Volume spike is approved for a gap in Phase B.
- Apparatus stays greybox through the overnight run; Soft goods is on Chaos
  Cloth.
- Stream activated: write the new files now; A + B + C land after them, in one
  batched build.

## Open questions

For Gary, held by the conductor:
- Density: stride 12 (about 23 pots) or stride 8 (about 33)?
- Should the pots pump to the music?
- Real fire or silk flames? This stream recommends **Niagara for a wing burning
  down**. The burn is a one-way event that consumes a mask and opens holes to
  the light behind; lit cloth cannot eat through scenery. **Silk is better for
  contained fire that must run every night without variance**, such as a
  cresset or footlight flames. That would be Soft goods cloth on Chaos, plus a
  linked light.
- Which wings burn? That is a creative choice, and it gates Wing materiality's
  per-mesh `UseBurn` switch.
