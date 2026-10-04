# S6 bee/firefly swarm: build-window and editor runbook (4 Oct 2026)

**Status when written (night of 3–4 Oct, offline).** Nothing has been built,
applied, imported or run in Unreal. Every editor script below has only been
byte-compiled (`py_compile`). The C++ is a held patch. The tuning numbers come
from a Python mirror of the C++, not from the engine.

**Proof tiers** (AGENTS.md), tagged on every claim:
- **[decl]**: declaration-proven from a UE 5.8 header or source file under `D:/Unreal Engine/UE_5.8`.
- **[shader]**: proven from an installed `.ush`/`.usf`.
- **[measured]**: an intervention was run and its result read back.
- **[mirror]**: measured on the offline Python mirror only.
- **[inferred]**: not verified; the reason is given each time.

The install has no private Niagara `.cpp`: `find Plugins/FX/Niagara/Source/Niagara/Private -name "*.cpp"` returns **0**.
So no claim about Niagara *runtime behaviour* in this document is declaration-proven.

Design: `Docs/BeeSwarmDesign_2026-10-02.md`. Gary's asks: `Docs/Scene6BeatSheet_2026-10-02.md`.
**Sound stays paused**: no audio work anywhere below.

---

## 0. What exists tonight (files)

| File | What it is |
|---|---|
| `Scripts/patches/2026-10-04_BS_bee_swarm_sim.v3.patch` | **The patch to apply.** It contains the full v2 content plus the v3 fixes and the actor. `git apply --check` passes on HEAD 96e9174 **[measured]**. |
| `Scripts/patches/2026-10-04_BS_bee_swarm_sim.v2-to-v3.review.diff` | Review aid only (v2 → v3 delta, 8 files, +284/−16). Do not apply it. |
| `Scripts/patches/2026-10-03_BS_bee_swarm_sim.v2.patch` | Unchanged. It is superseded by v3. |
| `Tools/BeeSwarm/bee_swarm_mirror.py` | Python mirror of `FInfinityStageBeeSwarmSimulation` (v3). |
| `Tools/BeeSwarm/bee_swarm_harness.py` | 120 s replay, metrics, gates, plots, GIF/MP4, tuning, C++-test prediction, golden values. |
| `Saved/CodexBeeSwarm/*.py` + `*_request.json` | Editor scripts and their MCP requests (section 2). |
| `Saved/CodexBeeSwarm/harness/` (git-ignored) | `trails_top_tuned.png`, `trails_side_tuned.png`, `swarm_dots_tuned.gif/.mp4`, the same for `_v2`, `metrics_*.json`, `golden.json`, `cpp_tests_prediction.json`, `tuning.json`. |

Nothing is committed. The patch and these files belong to the effects stream, which commits them.

---

## 1. v2 → v3 review (UE 5.8 API correctness)

### API calls checked against headers: no compile breaker found [decl]

| Call in patch | Header evidence |
|---|---|
| `UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayVector(UNiagaraComponent*, FName, const TArray<FVector>&)` | `Plugins/FX/Niagara/Source/Niagara/Classes/NiagaraDataInterfaceArrayFunctionLibrary.h:27` |
| `…::SetNiagaraArrayPosition(…, const TArray<FVector>&)` | same file `:30`. Getters `GetNiagaraArrayVector/Position` at `:64`/`:67` (used by the probes). |
| `UNiagaraComponent::SetTickBehavior(ENiagaraTickBehavior)` | `Niagara/Public/NiagaraComponent.h:412`. Enum `UsePrereqs` in `Niagara/Public/NiagaraTickBehaviorEnum.h:9-12`. |
| `SetAsset`, `GetAsset`, `SetVariableFloat` (v3 actor) | `NiagaraComponent.h:295`, `:298`, `:533` |
| `UActorComponent::AddTickPrerequisiteComponent` / `Remove…` | `Engine/Classes/Components/ActorComponent.h:1359`, `:1367` |
| `APlayerCameraManager::bGameCameraCutThisFrame` (public bitfield) | `Engine/Classes/Camera/PlayerCameraManager.h:459` |
| `GCurrentLevelEditingViewportClient` | `Editor/UnrealEd/Public/Editor.h:948`. `GetViewLocation()` is at `EditorViewportClient.h:562`. `UnrealEd` is already a private dependency under `bBuildEditor` (`InfinityStage.Build.cs`). |
| `FRandomStream::Initialize(int32)`, `FRandRange(FReal,FReal)` | `Core/Public/Math/RandomStream.h:62`, `:221` |
| `FVector::GetSafeNormal(Tol, ResultIfZero)`, `GetClampedToMaxSize` | `Core/Public/Math/Vector.h:647`, `:717` |
| Mixed float/double `FMath::Max/Min` | `MIX_FLOATS_2_ARGS(Max/Min)`, `Core/Public/GenericPlatform/GenericPlatformMath.h:987-988` |
| v3: `UWorld::IsPaused`, `DrawDebugSphere`, `TSoftObjectPtr(FSoftObjectPath)`, `SetAutoActivate`, `bTickInEditor` (public) | `World.h:3721`, `DrawDebugHelpers.h:45`, `SoftObjectPtr.h:307`, `ActorComponent.h:614`, `ActorComponent.h:292-294` |

Memory "header-checking is not compiling" still applies: **UNCLEAR until the build compiles it.**

### What was wrong in v2, and what v3 does about it

1. **The editor camera branch was dead code.** **[decl]** v2 never sets `bTickInEditor`. That property (`ActorComponent.h:294`) is required for a component to tick in an editor world. Without it, the `GCurrentLevelEditingViewportClient` branch never runs, and a swarm placed in a level stays frozen outside PIE.
   **v3:** `bTickInEditor = true`.
2. **Bees would pop after a pause.** **[inferred]** The tick-while-paused delta semantics live in `LevelTick.cpp`, which is not installed. v2 ticks when paused (`bTickEvenWhenPaused`) and passes the raw `DeltaTime` into the simulation, while Niagara pauses with the world. Every bee would then jump on unpause.
   **v3:** the simulation delta is `0` when `World->IsPaused()`. The camera-bubble enforcement still runs.
3. **UBT warns about the plugin descriptor.** **[decl, UBT source]** `Engine/Source/Programs/UnrealBuildTool/Configuration/UEBuildTarget.cs:1577` warns: "Plugin 'InfinityStage' does not list plugin 'Niagara' as a dependency". It is a warning, not an error.
   **v3:** adds `Niagara` to `InfinityStage.uplugin` `Plugins`.
4. **v2's behaviour misses Gary's brief.** **[mirror]**
   - The target ran pinned at its 3× speed cap (median 447 cm/s), ping-ponging off its box in straight lines. The v2 target had no damping.
   - Bees sat a median 242 cm from the target, so the swarm did not read as "around" it.
   - Heading changed at only 79 °/s, so the paths were smooth arcs rather than zig-zags.
   - With a box centred 150 cm above the floor, v2's 300 cm Z half-extent put **6.8 % of bee samples underground**.

   **v3 changes:**
   - New `TargetDragPerSecond`. The orbit literals `4.0` and `240.0` become `OrbitSpringPerSecondSquared` and `OrbitTangentialAccelerationCmPerSecondSquared`. Setting drag 0, spring 4 and tangential 240 reproduces v2.
   - The defaults are re-tuned (section 4).
   - `BeeCount` is clamped to 1–512.
5. **New pieces for tomorrow's editor runs.**
   - `AInfinityStageBeeSwarmActor`: Root + Niagara + Swarm components. Its `SwarmSystem` is a soft pointer defaulting to `/Game/Scenes/Effects/Swarm/NS_BeeSwarm`. `Parameters` is pushed to the component in `OnConstruction`/`PostInitializeComponents`. `SetSwarmBrightness` writes `User.SwarmBrightness` for the S6 release dim.
   - The component gains `SetParameters`, `GetParameters`, `GetSwarmTargetPosition`, `GetSimulatedBeeCount`, `bDrawDebugTarget` (the sandbox's visible "moving target") and `PostEditChangeProperty`, which restarts the simulation when a value is edited.
   - Because the actor's class defaults are the S6 values, a Show Prop attachment can use the C++ class directly, with no Blueprint.
6. **New automation test `InfinityStage.Effects.BeeSwarm.PythonMirrorGolden`.** It checks that the mirror predicts the C++: within 0.01 cm at 1 s, and within 1 cm at 3 s, by which point one jump and one fly-by have fired.
   **[mirror]** Chaos grows a 1e-9 cm nudge to 1.5e-7 cm at 1 s and 2e-4 cm at 3 s. So a 3 s-only miss means CRT `exp`/`cos` differences, not a logic error.

### Still UNCLEAR after v3 (each is measured in section 2)

- **Does `SetNiagaraArray*` accept `"User.BeePositions"` with the `User.` prefix?** No `.cpp` is installed, so this is unknown. `bee_swarm_niagara_verify.py` tries both name forms on a transient component, and `bee_swarm_pie_probe.py` settles it on the live actor.
  - If only the bare names work, set the component's `PositionArrayParameter` and `VelocityArrayParameter` to `BeePositions` and `BeeVelocities`.
- **Does `ENiagaraTickBehavior::UsePrereqs` honour a prerequisite added with `AddTickPrerequisiteComponent`?** The enum comment says "prereqs … for attachements / data interfaces" (`NiagaraTickBehaviorEnum.h:11`) and does not name component prerequisites.
  - If a bee visibly lags the camera by one frame: set the Niagara component's Tick Behavior to `ForceTickLast` (`NiagaraTickBehaviorEnum.h:17`).
- **Is the camera manager updated before `TG_PostUpdateWork`?** **[inferred]** `LevelTick.cpp` is not installed.
- **Do world positions require a world-space emitter?** **[inferred]** `SetNiagaraArrayPosition` takes world positions, so the emitter must have **Local Space OFF**.

---

## 2. Tomorrow, in order

**Prerequisites:**
- Own the build window. The build gate is machine-wide: any open UE editor blocks any build.
- Announce it to the conductor.
- Do not end anyone's PIE.

All MCP calls use this form; use `--timeout 600` for APPLY steps:

```
python Saved/CodexMocap/mcp_request.py --timeout 600 tools/call --params-file Saved/CodexBeeSwarm/<name>_request.json
```

### B. Build window (editor closed)

| # | Do | Expect |
|---|---|---|
| B1 | Snapshot `Backups/PreBeeSwarmV3-YYYYMMDD-HHMM/`: copy `Plugins/InfinityStage/InfinityStage.uplugin` and `Plugins/InfinityStage/Source/`. | The folder exists. |
| B2 | `git apply --check Scripts/patches/2026-10-04_BS_bee_swarm_sim.v3.patch`, then `git apply` the same file. If the patch is committed by then, use `git show HEAD:Scripts/patches/…v3.patch \| git apply` (CRLF memory). | No output. `git status` shows 1 modified `.cs`, 1 modified `.uplugin`, 7 new files. |
| B3 | `"D:\Unreal Engine\UE_5.8\Engine\Build\BatchFiles\Build.bat" PussStageEditor Win64 Development -Project="E:\PussStage\PussStage.uproject" -waitmutex -NoUBA` | `Result: Succeeded`. The output has **no** "does not list plugin 'Niagara'" line. |
| B4 | Binary proof: `dumpbin /exports Plugins\InfinityStage\Binaries\Win64\UnrealEditor-InfinityStage.dll \| findstr /i BeeSwarm` | Hits for `AInfinityStageBeeSwarmActor` and `UInfinityStageBeeSwarmComponent`. Also run the hot-reload `-####.` DLL check from `WindowsBuildProcedure.md`; it must have zero hits. Test names are UTF-8 in the Tests DLL; search for `PythonMirrorGolden` as UTF-8 and run a +/− control. |
| B5 | Focused tests: `UnrealEditor-Cmd.exe … -ExecCmds="Automation RunTests InfinityStage.Effects.BeeSwarm; Quit" -TestExit="Automation Test Queue Empty" -AbsLog="E:\PussStage\Saved\Logs\BeeSwarmV3-<time>.log" …` (full flags in `WindowsBuildProcedure.md:70`). | **8 tests, 0 `Result={Fail}`**: SeedRepeat, VariableFrameRate, MovingCameraInterpolation, CameraCutBubble, PauseBubble, BoundaryConstraints, NonRepetitionReturnMap, PythonMirrorGolden. **[mirror] prediction:** the first 7 pass with the v3 defaults (`cpp_tests_prediction.json`; return map 0.225 against a 0.01 gate; interpolation max difference 1e-9 cm). |
| B6 | Full suite, narrow filter `InfinityStage` (never `PussStage`). | Matches the current baseline (memory: 90/0/90, 30 Sep) plus the 8 new tests. Warnings are not failures (baseline 29). |

**If B5's PythonMirrorGolden fails at 1 s:** the mirror is wrong. The tuned numbers are then unproven. Report it and keep the build: the other gates still hold.

**If B3 fails:** restore from the B1 snapshot, or run `git checkout -- Plugins/InfinityStage` and delete the 7 new files listed by `git status`. The repo then returns to HEAD.

### E. Editor runs (editor open, no PIE unless stated)

| # | Script / request | Marker to require | Notes |
|---|---|---|---|
| E1 | `bee_swarm_assets_dry_run` | `BEE_SWARM_ASSETS_DRY_OK\|run=…\|existing=[]` | Checks that the GeometryScript, ParticleRandom/ParticleColor/PreSkinnedPosition and MIC-factory APIs exist. GeometryScripting is mounted: **[measured]** in `Saved/Logs/PussStage-backup-2026.10.02-05.42.36.log` (`InternalLoadLibrary: 'GeometryScriptingCore'`). |
| E2 | `bee_swarm_assets_apply_run` | `BEE_SWARM_ASSETS_APPLIED\|…\|sections=3\|bounds={…}\|…\|mis=3` | Creates `M_Bee_Body`, `M_Bee_Wing`, `MI_Bee_Body/Glint/Wing` and `SM_Bee`, and saves only those 6. **About 20 s later,** grep `Saved/Logs/PussStage.log` for `Failed to compile` with `M_Bee_`; there must be none. On `BEE_SWARM_ASSETS_STOPPED`, never save: the new in-memory packages are discarded by a Don't-Save relaunch. If only the HLSL needs fixing, `bee_swarm_assets_rebuild_materials_run` rebuilds the two masters in place (own folder only). |
| M | **Niagara system by hand** (section 3), about 20 min, by Gary or the conductor. | – | Python cannot author emitters, modules or renderers (section 3 says why). |
| E3 | `bee_swarm_niagara_verify` | `BEE_SWARM_NIAGARA_VERIFIED\|…\|state=CHECKED\|arrays=User.prefixed_OK` | Read-only; it fails if the census changes. `state=UNVERIFIED_NO_OBJECT_ITERATOR` means the renderer was not checked: check it by eye. `arrays=UNCLEAR_…` means the transient component gave nothing: E6 decides. A `ONLY_BARE_NAMES_WORK` stop means: change the two FName properties (see section 1). |
| E4 | `bee_swarm_sandbox_dry_run` | `BEE_SWARM_SANDBOX_DRY_OK` | Refuses if any **map** is dirty, the sandbox exists, or the class or assets are missing. |
| E5 | `bee_swarm_sandbox_apply_run` | `BEE_SWARM_SANDBOX_SAVED\|…\|map=/Game/Scenes/Effects/Swarm/L_SwarmSandbox\|actors=16\|returned_to=/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice` | **Level activity:** it opens a new map, then re-opens the Show level. Announce it first. On a stop after the switch: do not save; reopen the Show level and answer Don't Save. Never reload the open world from Python. |
| E6 | Open `L_SwarmSandbox` and start PIE yourself. Run `bee_swarm_pie_probe` **twice**, at least 1 s apart. | Two `BEE_SWARM_PIE_PROBE\|…\|bees=200\|positions=200\|velocities=200\|min_cam_cm=≥25…` lines with **different** `hash=` values. | This measures the C++ → Niagara upload. The probe never starts or ends PIE. |
| E7 | Blur and DOF stills in the sandbox: `SB Camera Focus200`, then `SB Camera Focus60`, using the conductor's `capture_probe.py` with no exposure override. | Gary judges: the 30/60 cm reference bees and passing bees are soft at focus 200, the 200 cm bee is sharp, wings read as blur, the glint twinkles. | Optional A/B: renderer Motion Vector `Precise` versus `Approximate`. Velocity comes straight from the simulation, so Approximate is a legitimate fallback. |
| E8 | `bee_swarm_s6_plan` | `BEE_SWARM_S6_PLAN\|…\|cue=P06 Wing 055\|candle_rel=[…]\|proposed_rel=[x,y,150.0]\|class_loaded=True\|existing_swarm=0` | Read-only. It writes `Saved/CodexBeeSwarm/bee_swarm_s6_plan.json`. The S6 write itself (section 5) needs **Gary's own yes**. |

---

## 3. NS_BeeSwarm by hand (Niagara editor, UE 5.8)

**Why by hand.** **[decl]**
- `UNiagaraSystemFactoryNew` keeps `SystemToCopy` and `EmittersToAddToNewSystem` as plain members with no `UPROPERTY` (`NiagaraEditor/Public/NiagaraSystemFactoryNew.h:23-24`).
- `UNiagaraSystem::EmitterHandles` is a bare `UPROPERTY()` (`Niagara/Classes/NiagaraSystem.h:975-976`).
- No `BlueprintCallable`/`ScriptMethod` exists in `NiagaraSystem.h`/`NiagaraEmitter.h`.

So stock Python can create at most an empty system. The design's route (a), the beta `CascadeToNiagaraConverter`, is not enabled in `PussStage.uproject`.

1. Content Browser → `/Game/Scenes/Effects/Swarm` → right-click → **FX → Niagara System** → **Create empty system** → name it `NS_BeeSwarm`. Open it.
2. **Add an emitter:** right-click in the System Overview → *Add Emitter* → the **Empty** template. Rename it `Bees`.
3. **User parameters** (Parameters panel → *User Exposed* → **+**):
   - `BeePositions`: type **Position Array** (`UNiagaraDataInterfaceArrayPosition`, `NiagaraDataInterfaceArrayFloat.h:54-55`).
   - `BeeVelocities`: type **Vector Array** (`UNiagaraDataInterfaceArrayFloat3`, same file `:37-38`).
   - `SwarmBrightness`: float, default **1.0**.
   - `MaxBees`: int, default **512**.
4. **Emitter Properties:**
   - Sim Target **CPUSim**.
   - **Local Space OFF**. The arrays carry world positions.
   - Requires Persistent IDs **ON**.
   - Calculate Bounds Mode **Dynamic**.
5. **Emitter State:** Life Cycle Mode **Self**, Loop Behavior **Infinite**, Loop Duration **100000**. The burst must fire once only.
6. **Emitter Update:** remove any Spawn Rate. Add **Spawn Burst Instantaneous** with Spawn Count = `User.MaxBees` and Spawn Time = 0.
7. **Particle Spawn:**
   - In **Initialize Particle**: Lifetime Mode Direct, Lifetime **100000**; Color (1,1,1,1); Mesh Scale 1 (the mesh is already in cm).
   - Add a **Scratch Pad** module `BeeIndexInit`. In its graph:
     - Map Get `Particles.UniqueID` → Map Set new int `Particles.BeeIndex`.
     - Also set new float `Particles.MaterialRandom = frac(UniqueID × 0.6180339)`. This gives the twinkle phase per bee, and the materials read it through *Particle Random* **[shader]** (`NiagaraMeshVertexFactory.ush:538`, bound by `MaterialRandomDataOffset`).
8. **Particle Update:** delete **Particle State**, or untick *Kill Particles When Lifetime Has Elapsed*. Add a **Scratch Pad** module `BeeFromArrays`. In its graph:
   - Map Get: `User.BeePositions`, `User.BeeVelocities`, `User.SwarmBrightness`, `Particles.BeeIndex`, `Particles.Position`, `Particles.Velocity`.
   - From the `BeePositions` pin, add the **Length** function (→ `Num`) and the **Get** function (Index = `BeeIndex` → `Pos`). From `BeeVelocities`, add **Get** (Index = `BeeIndex` → `Vel`).
   - Map Set, **in this order:**
     1. `Particles.Previous.Position` = old `Particles.Position`
     2. `Particles.Previous.Velocity` = old `Particles.Velocity`
     3. `Particles.Position = Pos`
     4. `Particles.Velocity = Vel`
     5. `Particles.Color = (1,1,1, User.SwarmBrightness)`
     6. `Particles.Scale = (BeeIndex < Num) ? (1,1,1) : (0,0,0)`

     The `Previous` namespace exists **[decl]** (`Niagara/Classes/NiagaraConstants.h:21`). Whether Niagara would fill it automatically is **[inferred]**, so it is written explicitly.
9. **Render:**
   - Delete the Sprite renderer.
   - Add a **Mesh Renderer** with these settings:
     - Meshes[0] = `SM_Bee`
     - Override Materials off; the mesh's three slots carry `MI_Bee_Body`, `MI_Bee_Glint` and `MI_Bee_Wing`.
     - **Facing Mode = Velocity**. The bee's nose is +X.
     - **Motion Vector Setting = Precise** (`NiagaraRendererProperties.h:478-480`).
     - Sort Mode None.
     - Cast Shadows off: a 1.6 cm bee gives no useful shadow and has a cost.
   - Bindings:
     - Position → `Particles.Position`
     - Velocity → `Particles.Velocity`
     - Prev Position → `Particles.Previous.Position`
     - Prev Velocity → `Particles.Previous.Velocity`
     - Scale → `Particles.Scale`
     - Color → `Particles.Color`
     - Material Random → `Particles.MaterialRandom`
10. **Compile, then Save** (this asset only). Then run **E3**.

**Optional, only if E7 shows a cost problem:** add a far-LOD Sprite renderer with Camera Distance culling at 600 cm and above, and give the mesh renderer the same culling at 600 cm and below.

---

## 4. Offline harness and tuned parameters [mirror]

Reproduce:

```
python Tools/BeeSwarm/bee_swarm_harness.py --selftest
python Tools/BeeSwarm/bee_swarm_harness.py
python Tools/BeeSwarm/bee_swarm_harness.py --cpp-tests
python Tools/BeeSwarm/bee_swarm_harness.py --golden
```

Add `--v2` for the v2 comparison and `--tune` for the sweep. Each run takes about 4 s for 200 bees × 120 s.

**Self-test controls pass [mirror]:**
- A perfect 12 s loop scores a return map of 0.0, below the 0.01 gate, so it fails as it should.
- A 10 s periodic orbit scores |autocorrelation| 1.0, above the 0.85 gate, so it fails as it should.
- The first `FRandomStream(0)` draw equals the header arithmetic by hand (0.2113248).

**Scenario.** Swarm-local cm, with the actor 150 cm above the floor. The GO1 lens is at 55 cm. It trots in at about 1.2 m/s for 7 s, then wanders a figure-of-eight round the candle at 0–90 cm/s with pauses.

**Gates** were pre-registered in `GATES` before tuning. The first four mirror the C++ and design gates; the rest are look gates.

| Metric (200 bees, 120 s, seed 0xBEE62026) | Gate | v2 defaults | **v3 defaults** |
|---|---|---:|---:|
| Bounds / bubble violations | 0 / 0 | 0 / 0 | **0 / 0** |
| Return-map minimum recurrence (C++ test metric) | ≥ 0.01 | 0.281 | **0.223** |
| Bee 0, 10 s-lag \|autocorrelation\| | < 0.85 | 0.112 | **0.136** |
| Median distance to target (cm) | 50–150 | 242 ✗ | **133** |
| Median / p90 speed (cm/s) | 100–300 / 250–700 | 248 / 416 | **284 / 453** |
| Median heading-change rate (°/s) | ≥ 180 | 79 ✗ | **203** |
| Frames with a bee within 60 cm of camera | 0.30–0.85 | 0.30 | **0.54** |
| Mean bees within 200 cm / 100 cm of camera | ≥ 8 | 49 / 8 | **71 / 14** |
| Minimum camera distance (cm) | ≥ 25 | 25.0 | **25.0** |
| Target median / p90 speed (cm/s) | p90 ≥ 250 | 447 / 540 (pinned) | **109 / 280** (dart, then hover) |
| Bee samples within 5 cm of the floor | – | **6.8 %** (box below floor) | **0 %** |
| Fly-bys / darts / target jumps in 120 s | – | 36 / 2763 / 39 | **103 / 10576 / 70** |

All gates also pass with seeds 12345 and 777. Their heading rates are 202 and 201 °/s; within-60 cm fractions 0.48 and 0.43.

**v3 defaults** (the C++ header and `Params()` agree):

| Parameter | Value | Parameter | Value |
|---|---:|---|---:|
| BeeCount | 200 | DartRatePerSecond | 0.45 |
| BoundsExtentCm | (600, 450, 140) | DartStrengthCmPerSecond | 320 |
| TargetWanderSpeedCmPerSecond | 150 | DragPerSecond | 1.6 |
| TargetJumpIntervalSeconds | (0.8, 2.6) | MaxSpeedCmPerSecond | 650 |
| **TargetDragPerSecond** (new) | 1.5 | CameraAttractWeight | 0.9 |
| OrbitRadiusRangeCm | (30, 140) | CameraRepulsionRadiusCm | 25 |
| **OrbitSpringPerSecondSquared** (new) | 12 | FlyByRatePerSecond | 0.8 |
| **OrbitTangentialAccelerationCmPerSecondSquared** (new) | 240 | Seed / FixedStepSeconds | 0xBEE62026 / 1/120 |
| LargeNoiseScalePerCm / Accel | 0.003 / 220 | SmallNoiseScalePerCm / Accel | **0.09 / 1200** |

**What drove the tuning [mirror]:**
- The one-factor sweep alone could not pass the distance or heading gates.
- The decisive changes: a stiffer orbit spring (4 → 12) for cohesion, and a fine-scale noise field (0.014 → 0.09 /cm, 90 → 1200 cm/s²) for zig-zag.

**Whether this reads "fairly realistic" is not measured.** A dot plot is not a render; the judgment belongs to Gary's E7 stills.

---

## 5. S6 placement plan [inferred until E8 and Gary]

- **Anchor.** Use the same cue and anchor as the candle: `P06 Wing 055`, attachment `FX TEST - S6 Candle`. The candle is at relative (3390, 0, 110), which is the S6 hangar's depth centre on a 110 cm table (`fx_candle_s6.py`; apply marker in `fx_candle_s6_apply_response_20261003_slot.json`).
- **New attachment.** A Prop attachment `FX TEST - S6 Bee Swarm`:
  - ActorClass `/Script/InfinityStage.InfinityStageBeeSwarmActor`
  - RelativeTransform = the candle's XY with **Z = 150**
  - No per-instance overrides. The class defaults are the tuned S6 values, and a Show attachment re-materialises from class defaults.
- **Why Z = 150.** The box spans 10–290 cm above the floor, so the GO1 lens (~55 cm) is inside it. The target band is 150 ± 63 cm, so the cloud wheels round the candle and the old lady's hands. Fly-bys bring single bees to 45 cm from the lens.
- **Camera.** S6 is the one Scene where the GO1 drives the camera. The component reads player 0's camera manager in PIE, so it follows the live dog with no extra wiring **[decl]**, given the API in section 1.
  - The S6 arrival is a camera cut. If the swarm smears through it, call `NotifyCameraCut()` from the arrival.
- **Release beat.** "Bees dim away": a Sequencer or Blueprint call to `SetSwarmBrightness(1 → 0)` over the release. This dims the body, wing opacity and glint through `Particles.Color.a`.
- **Write route.** Mirror `fx_candle_s6.py`: DRY, then APPLY with a `Backups/PreBeeSwarmS6-…` snapshot of the Show and level, materialise only S6, save only the Show and level, read back, then `SavedMasterMatchesShow`. Not written tonight: it is a creative placement and needs **Gary's own yes**.
- **S6 post settings.** The look needs motion blur on, a DOF-capable camera and volumetric fog for the candle halo. These are Gary's call in the S6 look pass.

---

## 6. Known limits and risks

- The mesh, materials and HLSL have never compiled **[inferred]**.
  - Material pin names come from the working wing builder's patterns.
  - `PreSkinnedPosition` is vertex-shader-only, which is fine for WPO.
  - The wing dither uses `Parameters.SvPosition` and `View.StateFrameIndexMod8` inside a Custom node. If that fails to compile, rebuild with E2b after swapping in `/Engine/Functions/Engine_MaterialFunctions02/Utility/DitherTemporalAA` (it exists in the install **[measured]**; its pin names were not checked).
- Niagara mesh vertex colour and particle colour are separate **[shader]** (`NiagaraMeshVertexFactory.ush:283,289`). The materials use only Particle Color alpha and Particle Random, never mesh vertex colour.
- `CreateNewStaticMeshAssetFromMesh` creates one slot per material ID **[inferred]**. The script asserts 3 sections, adds slots if needed, and reads the materials back.
- Fixed-step CPU cost for 200 bees is unmeasured. The mirror runs 120 s in about 4 s of Python, which says nothing about C++ frame cost. Read `stat game` in E6.
- WPO motion vectors on the wings depend on project velocity settings **[inferred]**. Judge them in E7.
