# S6 bee/firefly swarm — PASS 1 route and design

**Date:** 2 October 2026
**Status:** offline PASS 1 only. No Unreal asset was written, no editor automation
was run, and no build was run. The C++ below is a **HELD, uncompiled draft**.

## Intent and acceptance boundary

The swarm should look fairly realistic without claiming biological simulation:
chaotic and non-repetitive, orbiting a target that wanders and jumps, sometimes
darting around the live view and making rate-limited close fly-bys. Bees are small
opaque or masked meshes, approximately 1.5 cm long, with a dark body, rim-lit
blurred wings, an optional emissive firefly glint, and independently phased
twinkle. Close particles are meshes; the far LOD may use sprites. Recordings use
a fixed seed.

This pass proves only declarations and available APIs. It does **not** prove the
look, performance, depth-of-field response in this project, motion blur in this
project, or that the held C++ compiles.

## V1 — depth of field

**declaration-proven:** opaque and masked materials take the solid/masked base-pass
path. UE 5.8's base-pass shader declares GBuffer use for
`MATERIALBLENDING_SOLID || MATERIALBLENDING_MASKED` and allows those same two
modes to write velocity in the base pass
(`D:/Unreal Engine/UE_5.8/Engine/Shaders/Private/BasePassCommon.ush:43-55`). The
masked base pass clips only pixels below the opacity threshold
(`D:/Unreal Engine/UE_5.8/Engine/Shaders/Private/BasePassPixelShader.usf:2459-2477`).
The diaphragm-DOF setup then samples scene colour and scene depth and computes
circle-of-confusion radius from that depth
(`D:/Unreal Engine/UE_5.8/Engine/Shaders/Private/DiaphragmDOF/DOFSetup.usf:258-268`).

**inferred from those declarations:** a Niagara mesh renderer using an opaque or
masked bee material participates in ordinary scene DOF like other base-pass
geometry. Masked wings contribute DOF only at pixels that survive the mask. This
still needs the prescribed 30/60/200 cm rendered test because a 1.5 cm mesh,
TAA/TSR reconstruction, material animation, and the chosen lens can alter the
perceived result.

**declaration-proven:** translucent materials have an explicit translucency-pass
choice: `Before DOF`, `After DOF`, or `After Motion Blur`
(`D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/Engine/Public/Materials/Material.h:140-149`),
and the material exposes that choice as `TranslucencyPass`
(`Material.h:593-598`). Therefore a translucent bee/wing material that is meant
to receive scene DOF must be authored **Before DOF**. `After DOF` will remain
sharp relative to the already-blurred scene; `After Motion Blur` also bypasses
the normal depth-tested reconstruction described by the enum comment. Opaque or
masked is preferred for the bees.

## V2 — mesh-renderer velocity and motion vectors

**declaration-proven:** the renderer property is
`UNiagaraRendererProperties::MotionVectorSetting`. Its UE 5.8 default is
`ENiagaraRendererMotionVectorSetting::AutoDetect`
(`D:/Unreal Engine/UE_5.8/Engine/Plugins/FX/Niagara/Source/Niagara/Public/NiagaraRendererProperties.h:478-480`).
The enum values are `AutoDetect`, `Precise`, `Approximate`, and `Disable`.
`Precise` forces precise vectors, `Approximate` derives them from current
velocity at lower memory/performance cost, and `Disable` renders the object as
stationary (`D:/Unreal Engine/UE_5.8/Engine/Plugins/FX/Niagara/Source/Niagara/Public/NiagaraCommon.h:161-172`). Project-wide Niagara
defaults resolve automatic selection to `Precise` in this installation
(`D:/Unreal Engine/UE_5.8/Engine/Plugins/FX/Niagara/Source/Niagara/Public/NiagaraSettings.h:229-231`).

**inferred recommendation, not yet measured:** set the bee mesh renderer explicitly to
`Precise`, bind particle velocity, and verify the setting by asset read-back.
That avoids a future project-default change silently altering TSR and motion
blur. The performance cost and visible smear remain rendered measurements, not
declaration proof.

## V3 — authoring routes ranked

### 1. Route (c), using one thin route-(b) renderer template — recommended

**declaration-proven:** UE 5.8 exposes `SetNiagaraArrayPosition` and
`SetNiagaraArrayVector` as `BlueprintCallable` functions on the Niagara array
data-interface library
(`D:/Unreal Engine/UE_5.8/Engine/Plugins/FX/Niagara/Source/Niagara/Classes/NiagaraDataInterfaceArrayFunctionLibrary.h:10-30`).
It also exposes per-component user-vector and float setters
(`D:/Unreal Engine/UE_5.8/Engine/Plugins/FX/Niagara/Source/Niagara/Public/NiagaraComponent.h:499-533`). This is the smallest stable
seam: deterministic C++ owns behavior and writes `User.BeePositions` and
`User.BeeVelocities` each tick; Niagara reads the arrays and only renders.

The Niagara side should be one deliberately simple, hand-verified template:
array-indexed particles, mesh renderer, optional far sprite renderer, velocity
binding, precise motion vectors, and material parameters for glint/twinkle. It
can be duplicated for the sandbox or S6 placement, but behavior does not live in
an opaque hand-edited stack. The held draft in this pass implements the pure
fixed-step simulation and the requested behavior test; it intentionally does
not add a Niagara module dependency or actor integration before a build window.

### 2. Route (b) alone — viable renderer bootstrap, weak behavior authority

**declaration-proven:** editor Asset Tools exposes `DuplicateAsset` as
`BlueprintCallable`
(`D:/Unreal Engine/UE_5.8/Engine/Source/Developer/AssetTools/Public/IAssetTools.h:449-451`),
and Niagara component user parameters are scriptable at runtime as cited above.
This reliably duplicates a known-good system and tunes its exposed inputs.

**inferred limitation:** route (b) alone works only if the full swarm behavior is
already encoded in the template graph. That makes the crucial non-repetition,
bounds, and camera-bubble rules hard to unit-test outside Niagara and returns
behavior authority to hand graph editing. Use it only as the rendering half of
route (c).

### 3. Route (a) — API exists, but is not the maintained project route

**declaration-proven:** the installed Cascade-to-Niagara converter exposes
Blueprint-callable wrappers that add empty/template emitters and finalize a
system (`D:/Unreal Engine/UE_5.8/Engine/Plugins/FX/CascadeToNiagaraConverter/Source/CascadeToNiagaraConverter/Public/NiagaraStackGraphUtilitiesAdapterLibrary.h:607-652`),
add/find module scripts, set parameters, add renderers
(`D:/Unreal Engine/UE_5.8/Engine/Plugins/FX/CascadeToNiagaraConverter/Source/CascadeToNiagaraConverter/Public/NiagaraStackGraphUtilitiesAdapterLibrary.h:683-745`), create a mesh
renderer (`D:/Unreal Engine/UE_5.8/Engine/Plugins/FX/CascadeToNiagaraConverter/Source/CascadeToNiagaraConverter/Public/NiagaraStackGraphUtilitiesAdapterLibrary.h:1047-1050`), and create
a system conversion context as a script method
(`D:/Unreal Engine/UE_5.8/Engine/Plugins/FX/CascadeToNiagaraConverter/Source/CascadeToNiagaraConverter/Public/NiagaraStackGraphUtilitiesAdapterLibrary.h:1085-1087`).

**declaration-proven:** that plugin declares itself beta, not installed, and
disabled by default
(`D:/Unreal Engine/UE_5.8/Engine/Plugins/FX/CascadeToNiagaraConverter/CascadeToNiagaraConverter.uplugin:13-16`).
**UNCLEAR / searched:** `PussStage.uproject` contains no
`CascadeToNiagaraConverter` entry; the complete plugin list was searched
(`PussStage.uproject:6-102`). Thus
the stack-editing wrappers are not currently a callable project dependency.
Enabling a beta conversion plugin just to synthesize one small render stack is
more surface area than this effect needs. Route (a) is technically possible
after a project/plugin change and editor restart, but it ranks last here.

## V4 — camera position input

**declaration-proven:** in game worlds,
`UGameplayStatics::GetPlayerCameraManager(WorldContext, PlayerIndex)` is
`BlueprintPure`
(`D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/Engine/Classes/Kismet/GameplayStatics.h:216-219`),
and `APlayerCameraManager::GetCameraLocation()` is `BlueprintCallable`
(`D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/Engine/Classes/Camera/PlayerCameraManager.h:702-705`). In editor worlds,
`UEditorEngine::GetActiveViewport()` returns the active viewport
(`D:/Unreal Engine/UE_5.8/Engine/Source/Editor/UnrealEd/Classes/Editor/EditorEngine.h:2611-2616`),
and `FEditorViewportClient::GetViewLocation()` returns its camera location
(`D:/Unreal Engine/UE_5.8/Engine/Source/Editor/UnrealEd/Public/EditorViewportClient.h:561-565`). The runtime module already
has an editor-only `UnrealEd` dependency
(`Plugins/InfinityStage/Source/InfinityStage/InfinityStage.Build.cs:30-37`), so
the editor branch does not require a new module.

**inferred recommendation:** resolve player 0's camera manager when `World->IsGameWorld()`;
under `WITH_EDITOR`, otherwise resolve the active editor viewport client. If no
active camera exists, hold the last valid camera position rather than snapping
the swarm. For MRQ or multi-view work, prefer the evaluated show camera when it
is available and use `UWorld::ViewLocationsRenderedLastFrame` only as a
one-frame-late fallback; that array is explicitly documented as last frame's
rendered views (`D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/Engine/Classes/Engine/World.h:1233-1234`).

## Recommended parameter surface and provisional defaults

These values are **inferred starting points**, not accepted tuning:

| Parameter | Default | Meaning |
| --- | ---: | --- |
| Target wander speed | 180 cm/s | Continuous attractor drift |
| Target jump interval | 1.5–4.5 s | Seeded change/impulse interval |
| Orbit radius range | 35–180 cm | Per-bee target orbit |
| Large noise scale | 0.003 /cm | Broad evolving curl-like field |
| Small noise scale | 0.014 /cm | Fine evolving curl-like field |
| Large/small noise acceleration | 220 / 90 cm/s² | Field strength |
| Dart rate | 0.12 /s/bee | Seeded per-bee impulses |
| Dart strength | 420 cm/s | Velocity impulse |
| Drag | 1.6 /s | Exponential damping |
| Maximum speed | 900 cm/s | Hard speed limit |
| Camera attract weight | 0.08 | Weak attraction relative to swarm target |
| Camera repulsion radius | 25 cm | Hard bubble; inward velocity removed |
| Fly-by rate | 0.35 /s global | Rate-limited close pass injection |
| Near / mid / far count | 200 / 80 / 24 | Counts selected by distance LOD |
| Behavior bounds | 600 × 450 × 300 cm half-extents | Sandbox/S6 local box |
| Fixed simulation step | 1/120 s | Frame-rate-independent deterministic integration |
| Recording seed | `0xBEE62026` | Repeatable recordings and tests |

The look surface is separate: body length ~1.5 cm, wing blur/glint intensity,
twinkle rate range, near/mid/far distances, and mesh-to-sprite cross-fade.

## Held C++ draft and test contract

The held patch adds a UObject-free `FInfinityStageBeeSwarmSimulation`. It uses a
fixed step, seeded target jumps, per-bee orbit radii, two evolving curl-like
fields, seeded dart impulses, exponential drag, a speed cap, weak camera pull, a
hard 25 cm camera bubble, bounded motion, and a globally rate-limited fly-by.

The single behavior automation test runs 48 bees for 60 seconds and pre-registers
three gates:

1. every bee remains inside the configured box;
2. no bee enters the camera repulsion radius (0.01 cm numerical tolerance);
3. bee 0's absolute normalized 10-second-lag position autocorrelation is below
   `0.85` over the 60-second path.

**UNCLEAR until build/test:** the draft is syntax-inspected only. It has not been
compiled or executed, as PASS 1 forbids a build. The autocorrelation threshold is
therefore a proposed red gate, not a passing result.

## Build and acceptance plan

1. **Sandbox map, never the Show level.** Create `/Game/Dev/Effects/L_BeeSwarmSandbox`
   with a fixed camera, metric distance markers, a focus target, and an explicit
   no-save/read-back procedure.
2. **Behavior with debug sprites.** Integrate the held fixed-step simulation in
   an effects-owned actor/component. Feed position and velocity arrays to a
   minimal Niagara system. Run the 60-second automation gate, seed-repeat check,
   variable-frame-rate equivalence check, and CPU timing for 24/80/200 bees.
3. **Mesh bees, wings, velocity output, DOF.** Add opaque/masked 1.5 cm mesh bees,
   blurred masked wings, firefly glint/twinkle, near mesh and far sprite LODs.
   Set mesh-renderer motion vectors explicitly to `Precise`. Read back renderer
   bindings/settings. Capture matched DOF and motion-blur shots with bees at
   **30 cm, 60 cm, and 200 cm** from camera; judge silhouette, smear, and popping.
4. **Camera behavior.** Use player camera manager in game worlds and active editor
   viewport otherwise, with last-valid fallback. Verify moving camera, camera
   cuts, pause, reverse/scrub, fixed-seed replay, and the 25 cm hard bubble.
5. **S6 placement last.** After sandbox behavior, cost, and rendered look pass,
   place one effect instance in S6 through the Show-authoritative workflow,
   materialize only S6, save only affected assets, read back, and obtain rendered
   user acceptance. Sound remains paused.

## PASS 1 result

**inferred recommended route:** **(c) deterministic C++ behavior + a thin duplicated or
hand-authored (b) Niagara rendering template.** It is the only route that makes
the artistic behavior tunable, deterministic, and unit-testable while keeping
Niagara in the job it demonstrably exposes well here: array-driven rendering,
materials, LODs, and motion-vector output.
