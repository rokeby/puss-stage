# Look depth plan: shadows, haze, floor, rake, edges (5 Oct 2026)

**Summary**
1. **Shadows were cut on purpose, in four passes from 25 Sep to 4 Oct. Today 385–398 of 2,812 Show lights cast shadows.** Two reasons: the VSM "colour rectangles" (a look fault, proven from the log) and frame rate. The stutter was blamed on the 338 P01 casters and then **refuted**: turning off every dynamic shadow did not remove it. Since 4 Oct the tools forbid adding casters.
2. **The one measured shadow cost is 4.5 ms of 31 ms PIE** (`ShowFlag.DynamicShadows 0`, 29 Sep, at P01's old 338 casters). Nothing has been measured since the cuts. The headroom is unknown, not zero.
3. **Haze is one global height fog** (0.022, measured 25 Sep; a cut to 0.012 was queued, but nobody has confirmed it was applied). The plugin **already has** a per-attachment Local Fog Volume (`Haze` effect). Only one EFFECT attachment exists in the whole Show, so varied density is an authoring job, not an engine one.
4. **The "dark glossy floor" planes still exist.** They are buried 5 cm down, under the 5 cm structure boards. Raising them is a prepared, never-run tool (`floors_above_boards_apply.py`). P04 has no plane and P02's is a known fault.
5. **"5 cm boards" means two things:** the floor kit's boards (5 cm since 26 Sep) and the Flat V3 wing boards (5 cm since 4 Oct, "TK"). Gary's edge question is about the wings.
6. **5 cm alone won't read.** The wing edge is about 5 px at 10 m and about 1 px at 20 m, seen edge-on. Its material is the generic canvas-edge master, and no light rakes along it. Cheap fix: a pale raw-board Edge, plus rake or rim light.
7. **Raking side lights already exist in P04 bays 1–6** (`LOW_SIDE`, shadowed keys). Elsewhere the rigs are top-down or forward.
8. **Next:** run the LOOK BENCH (built, offline harness 34/34). P04 bay 4 gets 9 toggles. Bay 8 gets the **glint** practical, mirror-placed for W&T's no-glint wet-paper flat. The bench also carries the **underpass** mock bay. It runs in PIE only, saves nothing, and measures per-toggle frame time and in-motion clips. Gary judges, and only then do we author per passage.

Tiers used per claim: **[decl]** declaration-proven, **[bin]** binary-proven, **[meas]** measured, **[inf]** inferred (reason given).

---

## 1. Shadows: what happened, and the count today

**Timeline**

| When | What | Why | Evidence |
|---|---|---|---|
| ≤25 Sep | About 1,700 shadow-casting local lights show-wide | engine default; the rigs were replicated with shadows on | [meas] `Docs/RigAndAtmosphere_Handover_2026-09-28.md:66-69` |
| 26 Sep | P03: 147 → 53 casters (fills made shadowless) | VSM one-pass overflow made hard colour rectangles; log `[VSM] One Pass Projection max lights overflow` | [meas] memory `puss-lighting-authoring-lessons.md`; commit `eb44f07` |
| 29 Sep 13:23 | P04–P06 baseline: show-wide 1,643 → 612. Keys `Entry Top` and `Entry Fwd +Y` keep shadows; **P05 all shadowless** | Gary's "build the lighting across the dark scenes", lean caster census | [decl] `Saved/CodexStructure/p456_baseline_plan_readonly.py:16-17`; commit `52412c1` |
| 29 Sep 14:37 | Handover: "stutter = P01's 338 casters" | hypothesis | commit `5e21d55` |
| 29 Sep (eve) | **Refuted:** stutter clusters persist with `ShowFlag.DynamicShadows 0` | A/B | [meas] `Docs/LightingEfficiencyPlan_2026-09-29.md:54` |
| 30 Sep 02:49 | P01: 338 → 99 (keys keep shadows; blink spot and house warmers exempt) | Gary "Yes, P03's recipe" + conductor "largest frame-rate item left". **Frame rate never measured after.** | [decl] `Saved/CodexStructure/p01_shadow_pass_apply.py:1-13`; [meas-absent] `RigAndAtmosphere_Handover_2026-09-28.md:546` |
| 3 Oct | Recommendation: at most 140 concurrent Show casters (−63%) | caster budget is concurrent, not installed | [inf] `Docs/Conductor/LIGHTING_TALK_PREP_2026-10-03.md:220-232` |
| 4 Oct | P04 looks: `shadow_budget` cap 43, rule `after_lte_before`. Scores tool: only `LOW_SIDE` may cast (`NON_SIDE_SHADOW_CASTER`), budget after ≤ before, P05 `NONE` | locks the cuts in | [decl] `Saved/CodexConductor/lighting_looks.json` (`shadow_budget`); `lighting_scores_apply.py:69, :366, :785-800` |
| 4 Oct 12:33 | P06 black mode: 130 → 117 | event design | [meas] `Docs/Conductor/MORNING_SUMMARY_2026-10-04.md:109` |

**Gary's suspicion, answered.** It is half right. P01's cut was sold partly on frame rate, and the stutter link it rested on was refuted the same evening. P03 and P04–P06 were cut for the rectangles and as rig design. **[meas]** for both reasons (sources above).

**Casters per passage today**

Source: `Saved/CodexConductor/light_guid_audit_20261004-121338.json`, the per-attachment `lighting.cast_shadows`, counting only lights whose cue and attachment are both enabled. **[meas]** at 4 Oct 12:13. P06 is adjusted for the 12:33 change **[meas]**. P05's 13:23 score kept 2 casters **[meas]** (`lighting_scores_report_P05.json`, `shadow.passage_after: 2`).

| Passage | Show lights | enabled | casters (enabled) | of which | vol. shadow flag | light fn on |
|---|---|---|---|---|---|---|
| P01 | 579 | 525 | **99** | Entry Top 48, Entry Fwd +Y 48, House L/R, blink | 0 | 480 |
| P02 | 139 | 116 | **70** | Cross ±Y 46, Entry Top 23, blink | 12 | 139 |
| P03 | 264 | 243 | **54** | Rig R/L/Slash/Back 53, blink | 6 | 211 |
| P04 | 256 | 181 | **43** | Entry Top/Fwd 30, LOOK LOW_SIDE/FENCE_BEAM 12, blink | 46 | 235 |
| P05 | 932* | 839* | **2** | the two blink spots | 0 | 932* |
| P06 | 642 | 578 | **117** (130 at audit) | Entry Top/Fwd 128 at audit | 129 | 641 |
| **Total** | 2,812 | | **385** (398 at audit) | | | |

\*P05 is from before the 13:23 score. The score disabled 837 lamps and built 539 new lights, so P05's light counts above are stale. Its caster count is not. **[meas]**

- **What reads flat because of this [inf]:** in P01, P04 and P06 the only casters are the top-down and forward keys. Their shadows fall behind the wings and down onto the floor, away from the camera. No shadow lands across a wing face from the side. P05 has none.
- **Moving lights:** `slow_move` is authored on 14 lamps (13 in P03, 1 in P04). Strike-on-approach is on 65 (20 in P03, 45 in P04). **[meas]** (same audit).
  - A moving caster re-renders its VSM pages every frame. **[decl]** `LightingEfficiencyPlan_2026-09-29.md:87` cites `InfinityStageLightDrama.cpp:133`.

**Performance evidence**

What exists:
- **[meas]** PIE A/B on 29 Sep, transport paused, P01 at 338 casters (`LightingEfficiencyPlan_2026-09-29.md:34-41`):
  - base 31.3 ms;
  - `DynamicShadows 0`: −4.5 ms;
  - light functions off: −1.5 ms;
  - VSM cache off: +3.5 ms (worse);
  - editor `InstancedStaticMeshes 0`: −6.6 ms. The wings cost more than all the shadows.
- **[meas]** The stutter is not shadows (`:54`). On 30 Sep it measured gone after the landscape delete, cause not attributed (memory `puss-stutter-status.md`).

What is unmeasured:
- frame time after any cut (30 Sep onward);
- cost per added caster;
- the Local Fog Volume cost;
- the glossy-floor Lumen reflection cost.
- `sg.ShadowQuality` was never read bare. It is suspected to be Cinematic (`LightingEfficiencyPlan:77`), and `r.VolumetricFog.GridPixelSize = 4` (`Saved/CodexStructure/vsm_cvars.json`, 25 Sep) points the same way. **[inf]**: 4 matches the Cinematic tier, not the engine default.

**Proposal [inf]**
- Shadows go back on **per bay, not per passage**: the 1–2 side or rake keys of the bay in view, plus the blink spots.
- Keep every top or fill light shadowless, so the per-pixel VSM overlap that made the rectangles never comes back.
- Hold the concurrent in-frustum budget at about the old P03 level (~50). The bench measures what one more caster costs.
- The authoring change is to the score validator's `after_lte_before` rule (`lighting_scores_apply.py`), which now forbids this. That is Gary's call.

## 2. The floor

- **Gary's "earlier floor" is the hand-placed textured slabs**, scaled engine Cubes, all still in the level as of the 30 Sep sweeps **[meas]** (`Saved/CodexStructure/floor_vs_lip_173226.json`; `plane_trim_record.json`). They are listed below.
  - In order: originally 100 cm thick with the top at +49.5. On 29 Sep Gary said "drop all floors to zero", and they went **below** the boards (top −5) so the boards would show. **[decl]** `Saved/CodexStructure/floors_to_stage_apply.py:1-11`, `floors_to_stage_revert_record.json`.
  - Then Gary: "the chariot slots don't look nearly as good as the regular floor … ideally we would use the walnut." `floors_above_boards_apply.py:1-9` was written to raise them to top +0.5. **It has no revert record, so it was never run.** **[inf]**: absence of `floors_above_boards_revert_record.json`, which the script writes first.
- **What covers them:** the Structure kit's ground boards.
  - Settings: `BoardThicknessCm = 5.0`, `BoardGapCm = 0.8`, top at the route line (`FloorHeightCm = 0`) **[decl]** `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageStructureActor.h:131, :137, :140`.
  - In place since 26 Sep (26,090 boards). Material `MI_Kit_WalnutPlank` since 29 Sep **[meas]** `Saved/CodexStructure/board_material_revert_record.json`.
  - Gary already rejected the plank look: "the floorboard like slats don't work great" (`Docs/InfinityStageSessionHandover.md:160`).
  - So the slabs (top −5) sit flush under the boards' bottom face. They are invisible except through the 0.8 cm gaps and the slots. **[inf]** from the declared heights.

| Passage | Slab (label) | Material | x extent (route frame) | Status |
|---|---|---|---|---|
| P01 | "Passage 01 - Opening Floor" | walnut herringbone `M_Walnut_Hrrngbn_02_Mat_Inst_Dup` | −150 (lip) … 29,284 (hinge) | [meas] trimmed 30 Sep |
| P02 | "Passage 02 - Floor Near/Left/Right/Far" | walnut (copied from P01) | rotated 66.5° to the mouth | **knowingly retained fault** (Gary: "Leave P02 for now"), `RigAndAtmosphere_Handover:844-850` |
| P03 | "Passage 03 - Floor" | oak `M_Oak_Hrrngbn_01` | −150 … 45,144 | [meas] |
| P04 | **none** | — | — | needs a new slab; the hinge x is not on file (UNCLEAR: searched every `Saved/*` JSON for `hinge_x` and found only S1/S5/S6) |
| P05 | "Passage 05 - Floor (oak)" | oak | lip … 47,091 (hinge) | [meas] hinge; lip trim 30 Sep 17:36 [decl] `RigAndAtmosphere_Handover:838-841` |
| P06 | "Passage 01 - Opening Floor2" | **Versailles** `M_Versailles_Mat_Dup` | lip … 28,140 (hinge) | [meas] hinge; lip trim [decl] same lines |

All slabs: top z −5.0, 1 cm thick. P03/P05/P06 also carry oak house-floor planes at −119 (`:839`).

**What "one plane, stage lip to hangar" needs [inf]**
1. Raise each existing slab to top +0.5. The prepared tool covers P01/P05/P06. P03's slab was spawned later, so the tool's `EXPECTED` table needs adding to (`floors_above_boards_apply.py:23-27`).
2. P04: spawn one slab from −150 to its hinge. Read the hinge first; P04 was retimed after 30 Sep.
3. P02: Gary's deferred notch.
4. One shared material: a new `MI_Floor_DarkWet`, a child of the walnut MI, so P06 stops being Versailles.
   - **[bin]** The walnut MI overrides `Roughness_Low` and `Roughness_High` (strings in `M_Walnut_Hrrngbn_02_Mat_Inst_Dup.uasset`).
   - **[bin]** Its master family `M_Flooring_Mat.uasset` also exposes `Roughness_Add_Grunge`, `Roughness_Contrast`, `Mask_Scale_Grunge`, `Mask_Low_Grunge` and `Mask_High_Grunge`, driven by `T_Grunge_Macro_01_M`. That grunge macro mask is the **no-new-texture puddle mask**: low base roughness, with grunge adding roughness, leaves glossy pools. **[inf]**: the parameter names are proven, but not their wiring.
   - Creating that MI is a Content write, so it is Gary's.
5. Ground boards: leave them on. The stage front's lip, fascia and house floor need the ground layer **[decl]** `InfinityStageStructureActor.h:331`, and a slab at +0.5 hides the planks.
   - **Cost:** the chariot slots vanish. They were already invisible from eye height (0.05% of pixels changed when widened) **[meas]** `InfinityStageSessionHandover.md:165-169`.
6. **Wet-floor cost [inf]:** at roughness below about 0.4, Lumen traces reflections (the project runs Lumen reflections, per memory). One large plane is cheap in draw calls, and the reflection cost scales with the glossy screen area. The bench measures it.

## 3. Haze

- **Global fog:** "Infinity Stage - Dusk Height Fog".
  - Settings: density 0.022, falloff 0.12, start 680 cm, volumetric fog on, g 0.55, extinction 0.9 **[meas]** `Saved/CodexStructure/shaft_probe.json` (25 Sep).
  - Fog is net-negative by 2–3 mean, and a shaft shows only toward the viewer. **[meas]** `RigAndAtmosphere_Handover:60-65`.
  - "Fog density to 0.012" was queued (`:137`). **Whether it ran is UNCLEAR**: no later fog read-back exists in `Saved/` (searched for `fog_density` and found only the 25 Sep files).
- **Local Fog Volumes are in the engine and already wired into the plugin.**
  - Engine: `LocalFogVolumeComponent.h:20-70` gives radial and height density, falloff, phase g and albedo, with BlueprintCallable setters; base volume 500 cm (`:74-76`) **[decl]**. They are voxelised into volumetric fog (`Shaders/Private/VolumetricFog.usf:209`) **[decl]**.
  - Plugin: `AInfinityStageEffectSource` owns a `ULocalFogVolumeComponent` "Medium" (`InfinityStageEffectSource.cpp:118, :270-280`). The `Haze` effect type feeds it (`bFeedsLocalMedium`, `MediumDensity` 0.15, `MediumRadiusCm`; `InfinityStageEffectTypes.h:103-125`) **[decl]**.
  - The Show holds **one** EFFECT attachment, a P06 fire **[meas]** (audit).
  - Open in the code itself: "the first rendered spike confirms whether that reads as radius or diameter" (`EffectSource.cpp:271-272`) **[decl]**.
- **Beam scattering on lights:** every Show light has VSI > 0, mostly 0.6. Exceptions: P01 has 24 at 9.0; P03 has 47 at 2.0 and 6 at 4.0 **[meas]** (audit).
- **Varied-density design [inf]:** keep the global fog thin (0.008–0.012) so everything sits in a little air. Put the density in Haze effect attachments, per bay or per phrase:
  - thick (0.4–0.6) in back-lit "beam bays", where a light throws toward the camera;
  - medium (0.2) over practical pools;
  - none in "clear" bays, so the eye gets relief;
  - thin near the camera and thicker upstage, so depth stacks.
  - P05 (497 cm wide) and P01 (1,244 cm) need different radii (the `EffectTypes.h:115` comment).
- **Cost [inf]:** LFVs add voxelisation work in the volumetric-fog pass; the grid is already fine (4 px). Count them per view, not per show, since they live on bay attachments. Shadowed lights inject into volumetric fog separately (`r.VolumetricFog.InjectShadowedLightsSeparately 1`, `vsm_cvars.json`), so every re-enabled caster with `cast_volumetric_shadow` costs twice. That is why the bench measures them together.

## 4. Edges: why 5 cm hasn't done it (for Gary)

- **Which boards:** the V3 wing flats went to 5 cm on 4 Oct, all 122 placed flats [meas] `Docs/FlatV3Status.md:279`; Gary's note is at `RUNTHROUGH_NOTES_2026-10-03.md:79-80`. (The floor boards are also 5 cm, but that is unrelated.)
- **Geometry [inf, arithmetic]:** a wing's inward edge faces across the corridor, and the camera looks down the corridor, so the edge is seen almost edge-on.
  - Projected width ≈ t·w/r² rad (t thickness, w lateral offset, r distance). With t 5 cm, w 6 m, r 10 m: 0.17°, about 5 px at 1080p and a ~60° field of view. At 20 m it is about 1 px. At the old 1.8 cm, about 2 px at 10 m.
  - So thickness helps only close up, against 10 m faces.
- **Material:** the V3 Edge slot is the bare `M_Wing_CanvasEdge_Master` **[decl]** `Saved/CodexFlatV3/swapkit/run_tk.json:51`.
  - The spec's ply laminations plus paper-lip Edge master (`FlatV3Spec:91`) was never built ("Timber and Edge masters once library.json lands", `WingMateriality.md:50`) **[decl]**.
  - Its brightness against the front is not measured. **[inf]** It reads as the same dark tone, given Gary's note.
- **Light:** edge faces point across the corridor. The keys are top-down or forward-thrown, so they light fronts and tops, not the edges **[inf]** from the rig roles (§1).
- **Cheap fixes, in order [inf]:**
  - (a) A pale raw-board / paper-core Edge MI. One MI swap per family; the bench's `edge` toggle previews it.
  - (b) Rake or rim light from the side, which lights edges and front relief together (§5).
  - (c) A 3–5 mm bevel in `build_v3_flat.py`. It catches specular. This is a mesh rebuild, so held behind (a) and (b).
  - (d) Not POM (`FlatV3Spec:157`).

## 5. Raking side lights, practicals, reflections, blinks

- **Already built in P04 bays 1–6:** `LOW_SIDE_L_KEY` at y −1450, z 100, a 15° cone, shadowed. They are the model **[meas]** PIE `live_lights` in `Saved/CodexConductor/LightingLooks/20261004_*/runtime_result.json`.
- **The scores tool already allows `LOW_SIDE` as the only shadowed role** (`lighting_scores_apply.py:366`). Rolling rake to other passages is a score edit, not new tooling **[decl]**.
- **Practicals:** score kits carry `PRACTICAL_*` and visible bulbs **[decl]** `lighting_scores.json`.
- **Reflections:** come mainly from the glossy or wet floor (§2), plus the Billboard v2 gloss (`3f593ea`).
- **Glints:** W&T's wet-paper test showed **no glints** on P04 Wing 008 R (`ruined_gallery_R_v3`, `M_Wing_Billboard_Master_v3`), because no light sits at a mirror angle (W&T, relayed by the conductor, 5 Oct). A gloss material only shows a highlight where light, face normal and eye obey the mirror law.
  - So glint practicals must be **placed by computation** from the camera route and the face normal, not by eye. That is the bench's `glint` toggle, §7.
  - Reasoning: specular physics **[inf]**, consistent with W&T's measurement.
- **Strobe:** lighting events give seeded, aperiodic blinkers. Gary's underpass note asks for a regular ~1 Hz strobe whose reflection shows in the wet floor (`UNDERPASS_AMBIENCE_BRIEF_2026-10-05.md`). The bench `strobe` toggle is regular 1 Hz at 12% duty; whether he wants regular or aperiodic is his call.

## 6. Overhead "subway deck" where P05/P06 have no ceiling wings (plan only, Gary 5 Oct)

All of this section is **[inf]**.

- **Where:** P05 now, and P06 since its V3 swap, per the conductor brief. Grep evidence: P05 has `CloudCeiling*` meshes in content, so verify which spans really have none.
- **What:** a deck-underside layer in `InfinityStageStructureActor`, alongside the gridiron, cross beams and rails it already builds. It needs:
  - riveted I-beam stringers along the route at the gridiron height;
  - transverse girders at every station (one per cross beam);
  - a dark steel plate soffit above;
  - pipe runs on one side.
  - Two or three meshes plus one grimy steel and one concrete MI, all ISM (cheap: the structure kit is ISM already).
- **Only over spans with no ceiling or border wing:** a per-bay mask from the Show's ceiling-wing attachments, so it never fights the wings.
- **Light it from below with rake and haze only, and keep it unshadowed or a cheap caster.** It is glimpsed, never featured (the brief's hierarchy).
- **Already planned in detail:** `Docs/Conductor/UNDERPASS_RIG_KIT_PLAN_2026-10-05.md`. Its §4 Phase B mock bay is 2 × (C1 column + P1 pier + 2 K1 knees) at ±(745+60), plus a D1 deck at 2000, plus one shadowed shaft light. Its §4 asks for an `underpass` bench toggle; that now exists, as box proxies, because `SM_UP_*` are not imported yet (searched `Content/` for `SM_UP_*`, none).
- **Owner and cost:**
  - Rig & atmosphere scope.
  - A C++ layer means a build window.
  - A pure-Show prop alternative (static props per bay) is possible but costs one actor per bay.

## 7. LOOK BENCH (built, offline-tested; not yet run)

**Files:**
- `Saved/CodexConductor/look_bench.py`
- runners `look_bench_{probe,capture,capture_bay8,hold,restore}_run.py`
- harness `test_look_bench.py`

**How it is safe:**
- **PIE game world only.** It refuses otherwise, so every change dies with PIE. It never starts or ends PIE.
- **Originals first:** written to `LookBench/<run>/look_bench_originals.json`, fsynced, re-read and compared, and the path logged before the first change.
- **Announced:** logs `LOOK_BENCH_ANNOUNCE` with the `ZZ_LOOKBENCH_*` count.
- **No save call in the file** (the harness scans for one). It fails if the editor dirty census changes.
- **UE objects only in the callback's closure.** Spawns are destroyed by reference. The leftover check uses GameplayStatics, which sees transient actors.
- **Exposure:** no override.

**Toggles:**
- `shadows`: the 4 brightest bay spots get shadows and volumetric shadows.
- `haze`: 3 LFVs at 0.10, 0.25 and 0.55, near to far. Bay-light VSI goes to 2.5 or more, and one back-light beam throws toward the camera.
- `rake`: a warm/cool pair at the corridor edges, z 140, shadowed.
- `floor`: a walnut MID with `Roughness_Low/High` at 0.08/0.22, top +0.5.
- `floor_wet`: roughness 0.02/0.06 + `Roughness_Add_Grunge` 0.6, plus 5 puddle discs at roughness 0.
- `strobe`: 1 Hz.
- `edge`: the bay's Flat V3 Edge slots swapped to a pale `BasicShapeMaterial` MID.
- `glint`: a small warm point practical (source radius 2 cm) and a visible bulb.
  - **Position:** at prepare time the bench finds the front face of the nearest `ruined_gallery_R_v3` instance (centre and normal from the mesh bounds; fronts face local −X per `FlatV3Spec:179-180`). It then solves the mirror law, light = P + d·(2(n·v)n − v), for cameras on the route at 150 cm, 4–22 m before the face. The first solution inside z 40–1100 cm and the corridor + 6 m wins.
  - **Recording:** the solution, the incidence angle and every rejected candidate are written to the originals file. Clip frames record the real camera location, so the geometry can be checked afterwards.
- `underpass`: the rig plan's §4 Phase B mock bay as box proxies: 2 piers, 2 columns, 4 knees, 2 stringers, ties every 45 cm, deck at 2000, plus one shadowed shaft light above the deck. Columns sit at the corridor half-width + 60.

**Capture, per state** (base, each toggle alone, all):
- force textures resident (`r.Streaming.FullyLoadUsedTextures 1`, restored afterwards);
- scrub to 4 s before the bay;
- settle 4 s and at least 45 ticks, with a re-pose halfway (a frame after a jump is stale);
- record static frame-time stats over the second half of the settle;
- play a 5 s clip at 6 fps (HighResShot, the `lighting_looks_p04_driver.py` pattern);
- restore everything, verify exactly, and log `LOOK_BENCH_OK` only after that.

**Harness:** `python Saved/CodexConductor/test_look_bench.py` → **34/34 OK** [meas, offline]. Each property is paired with a − control that fails:
- originals before any change;
- exact restore;
- a lost restore write is caught;
- states rebuild from base;
- PIE-only and leftover refusals;
- restore from the file alone;
- the save-call scan;
- strobe rate and clip plan;
- frame stats;
- glint mirror law (bisector ∥ normal), its camera on the route, the normal flip, no solution → refusal;
- underpass part counts, with columns outside the corridor;
- glint + underpass exact restore.

**Unproven until run [inf]:**
- `begin_deferred_actor_spawn_from_class` for `LocalFogVolume`, `SpotLight` and `StaticMeshActor`. Proven only for `CineCameraActor` (`st_pie_stills_driver.py:448`).
- That `set_cast_shadows` on PIE components does not dirty editor packages.
- Whether Light Drama or lighting events overwrite the bench's VSI or shadow changes per tick.
- That the walnut MID parameters change the look; the bench records MID read-backs.
- The LFV radius-vs-diameter question.
- That HighResShot frames are spaced in master time; the transport keeps playing while shots render.
- Frame-time stats include editor and Slate cost: compare states, don't quote absolutes.
- P05 is not supported, because its bay labels repeat; P04 is the default.
- **Glint:**
  - For ISMs, the face comes from mesh bounds plus `get_instance_transform` (out-param shape handled both ways); it has not run.
  - The family may also sit at bay 4 (the gloss test used `ruined_gallery_R_v3` on `P04 Wing 004`), so the nearest-instance rule matters.
  - The 150 cm camera height is assumed; the real height is recorded per frame.
  - A glint seen from only one point is a beat, not a state: the clip shows how long it lasts.
- **Underpass:** the box proxies show massing and shaft light, not the rivet or tie detail of the real kit.

## 8. Editor run order (each step reported before the next)
1. Gary or the operator starts PIE (the floating Preview) and leaves the transport paused. Announce: "look bench on P04 bay 4, PIE only, ~6 min".
2. `look_bench_probe_run.py`: read-only. Check `look_bench_probe_*.json`: about 6–9 bay lights, Edge-slot count ≤ 64, and the cvar value.
3. `look_bench_capture_run.py`: 11–13 states (base, each toggle alone, glint+wet when a glint face resolves near the bay, all), each about 9 s of settle and clip. Wait for `LOOK_BENCH_OK` (or `_FAILED`) in the log, parsed by run id.
4. `look_bench_capture_bay8_run.py`: bay 8, states base / glint / glint+wet / glint+wet+haze. Check `glint.light` in the originals file before reading the frames.
5. If anything failed or the editor hiccuped: `look_bench_restore_run.py`, while PIE is still up.
6. The operator ends PIE. Run the dirty census (expect maps=[] and content=[]).
7. Offline: contact sheet and clips per state, plus the frame-ms table, to Gary. Then decide:
   - the per-bay shadow budget;
   - the haze bay pattern;
   - floor raise + `MI_Floor_DarkWet` + the P04 slab (Content and level writes: backup, Gary's yes);
   - the Edge MI;
   - rake roll-out by score.
