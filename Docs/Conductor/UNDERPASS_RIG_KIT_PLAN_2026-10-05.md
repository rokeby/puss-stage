# Underpass rig kit: implementation plan (5 Oct 2026, offline, nothing applied)

**Summary**
1. **Verdict: adapt the existing rig; do not replace it.** `AInfinityStageStructureActor` already gives the stations, the bay rhythm, clean ends, tagged ownership and deterministic per-cue streams. Its gridiron already has a swappable mesh slot and material slot.
2. **Phase A, no C++, all Passages.** Swap `Gridiron.BeamMesh` for a Blender plate-girder *profile* and `Gridiron.Material` for green riveted steel, set the section to the mesh's true size, then re-fit. The cross beams and rails (277 instances in P05) become iron. Instance counts do not change.
3. **The fit rule drives the kit.** Every slot mesh is stretched to size by its bounds. A *profile* mesh therefore only ever stretches along its length, and that matches "the rig only changes in length".
   - Rivets and paint go in the material, tiled by the per-instance length.
4. **Phase B, one C++ layer, one build window.** An `Underpass` layer adds laced columns, concrete piers, knee brackets and an open-tie deck at ~2000 cm, all from the same stations. It adds about 1.2 % instances in P05.
5. **The kit is 5 core meshes, plus 2 optional**, built headless in Blender 4.4. Triangle budgets run 40–600 each, with no LODs and Nanite off (§2). Export reuses the Flat V3 FBX call. Import goes through Interchange with options set, a strays diff, a 1-LOD gate and a bounds gate (§3).
6. **Two masters**, built per-member like `M_Kit_Surface_Master`:
   - painted steel: green, rivet trim, chips and rust, black lower band below world Z 150;
   - grimy concrete with graffiti.
   The textures come from Content plus Blender bakes. No metal Megascans are in the project.
7. **Order:** offline Blender build and gate, import, then the masters. Prototype Phase A on **P05 only**, with a hand-placed Phase-B mock bay, then Gary's look.
   - After that, Phase A on P02–P06, with P01 per Gary.
   - Then Phase B C++, the build, and enabling it per Passage.
8. **Gary must decide** (§7): girder depth (show-wide), P01's timber portal and grid, deck height, a regular 1 Hz strobe, and graffiti placement.

Proof tiers per claim: **[decl]** declaration-proven (source/config read), **[meas]** measured (log or probe read back), **[inf]** inferred (with the reason). File references are relative to `E:\PussStage`. `.h` = `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageStructureActor.h`, `.cpp` = `.../Private/InfinityStageStructureActor.cpp`.

---

## 1. The rig today, and why adaptation wins

**Facts**

- **One actor per Passage**, separate from the Passage. It owns only components tagged `InfinityStage.Structure`, so hand-placed actors survive every re-fit. **[decl]** `.h:418-431`; tags at `.cpp:18-26`.
- **`MaterializeStructure()`** is editor-only. It validates and loads every mesh *before* clearing, so a failure keeps the old build. **[decl]** `.cpp:359-439`.
- **One ISM component per layer**: Static, NoCollision, one shadow flag, 4 custom floats. **[decl]** `.cpp:533-564`.
  - `SetCastShadow` is at :556 and `SetNumCustomDataFloats` at :559. `TimberCustomDataFloats = 4` is at :29.
  - **One material goes on every slot of the component.** **[decl]** `.cpp:548-553`.
- **The fit:** `FitMeshToTimber` scales each axis to the wanted size and centres the mesh by its bounds, not its pivot. **[decl]** `.cpp:105-123`.
  - Length is always local +X. This holds for horizontal beams (`MakeFromXZ(Along, Up)`, `.cpp:587-588`) and for vertical portal posts (`FVector(PostHeightCm, PostCm, PostCm)`, `.cpp:940-943`).
- **Custom data per instance is [tone 0..1, length, width, depth] in cm.** **[decl]** `.cpp:591`.
- **The slots that exist** **[decl]**:
  - Gridiron: `BeamMesh` (`.h:102-103`), `Material` (`.h:105-106`), `bCastShadow` (`.h:108-109`). The section comes from `BeamWidthCm`/`BeamDepthCm` (`.h:80-84`) with wear from `SectionVariation`/`TwistDegrees` (`.h:92-97`).
  - Ground: board, understage and groove (`.h:190-205`). Fixtures: body and line (`.h:393-415`).
  - **The portal reuses the gridiron mesh and material** (`.cpp:470-476`).
- **What does not exist:** there is no column, pier, deck, bracket or stringer layer. **[decl]** I read the whole header, `.h:1-571`. The only verticals are the portal posts.
- **P05 census at the last re-fit:** `stations=93 cross_beams=93 rails=184 boards=10463 slots=186 portal=1901 housings=541 lines=2 instances=13789 half_width_cm=745`. **[meas]** `Saved/Logs/PussStage-backup-2026.10.04-17.27.44.log`.
  - This matches W&T's probe: `Saved/CodexFlatV3/swapkit/p05_box_probe.json`, with the per-actor sum at `p05_box_probe.py:33-35`.
  - **The gridiron is 277 of 13,789 instances.**
- **Station pitch is 500 cm.**
  - **[meas]** On P04 the last stations sit at 9250, 9750 and 10250 (`Saved/CodexStructure/p04_end_colliders.json`).
  - **[meas]** P05 Wing 004 is at 1750 (`p05_slot_probe.json`). That is consistent with 250 + 3×500. **[inf]** I did not read every P05 station.
  - The Show can re-space stations, so nothing may assume 500 exactly.
- **Heights (29 Sep, so re-probe before relying on them):** all six grids are at 1150 with 34-deep beams. **[meas, dated]** `Saved/CodexStructure/gridiron_height_check.json`.
  - P05: wing tops ≤ 600, borders ≥ 527, 372 lamps above 1150, highest lamp 1891.
  - P06: highest lamp 1891.
  - P01: borders already reach down to 746, so the beams pass through them. **[decl]** `Docs/RigAndAtmosphere_Handover_2026-09-28.md:83-85`.
- **Material state:** on 29 Sep every rig piece was a Cube with no material. **[meas, dated]** `RigAndAtmosphere_Handover:158-160`. Today's per-actor `Gridiron.Material` was not read; see UNCLEAR.
- **Fence bays on P04** are 47 Show props, not structure: posts are 972 cm tall at |y| ≈ 1419. **[meas]** `Docs/FlatV3Status.md:277`; **[decl]** `Saved/CodexFlatV3/fence/run_fence_p04_plan.json`.

**Replacement vs adaptation**

| | Adaptation (recommended) | Replacement |
| --- | --- | --- |
| Girders and rails | **0 C++**: the slots exist (`.h:102-109`) | rewrite |
| Stations, rhythm, clean end, ownership, signature, `IsStructureCurrent` | kept as they are | must be re-implemented and re-tested |
| Columns, piers, deck | one new settings struct + one `BuildUnderpass()` on the existing `CreateManagedComponent` / `MakeTimberStream` pattern (`.cpp:31-50, 533-564`) | the same work, plus everything above |
| Risk | the floor boards re-fit too, and board counts drifted unexplained on 29 Sep (`RigAndAtmosphere_Handover:276-279`). A census diff gates it. | a new actor duplicates fixtures, ground and portal, or loses them |

Two things follow from the code:
- **Steel is machined stock.** Set `SectionVariation = 0` and `TwistDegrees = 0` (`.h:92-97`), or the girders wobble like hewn timber.
- **Set `BeamWidthCm`/`BeamDepthCm` to the girder mesh's true bounds.** Y and Z scale then stay exactly 1.0, and only X stretches. **[decl]** Arithmetic in `FitMeshToTimber`, `.cpp:116-121`.

## 2. Blender module list (build steps)

**Conventions for every module** **[decl, Flat V3 precedent]**
- Blender 4.4 headless, `--factory-startup`, one script: `Tools/Underpass/build_underpass_kit.py`. Model in **metres**; the export converts to cm.
- **Length on +X, section in Y (width) and Z (depth). The pivot is the bounds centre.** The fit centres by bounds anyway (`.cpp:110-123`), so the pivot cannot shift anything.
- **Apply all transforms. One mesh object per module.**
- **No LODs, no LodGroup.** That sidesteps the LOD-split trap, and every budget below is tiny.
- **Material slots:** one slot, `MAT_Steel` or `MAT_Concrete`. The actor overrides every slot with one material anyway (`.cpp:548-553`).
- **UV0 is the trim unwrap:**
  - U runs along X at **1.0 U per 100 cm of authored length**. The material multiplies by `custom[1]/100`, so rivets tile at true pitch at any stretch.
  - V runs around the section perimeter at 1.0 per 100 cm. **V runs DOWN on vertical faces** (the UE rule, `Docs/WingMateriality.md:407`).
  - Flange-edge faces map into the **rivet band** of the trim (V 0.0–0.1). Webs map to the plain band.
- **UV1** is the same unwrap packed 0–1, used only for a baked AO.
- **Smooth shading:** auto-smooth at 30°, then apply it as custom split normals, so the box ends stay hard.

**Profile modules**

These stretch in X only. Their authored length is **100 cm**, so X scale equals metres, which is easy to audit.

| # | Module | Section (cm) | Tris | Notes |
| --- | --- | --- | --- | --- |
| G1 | `SM_UP_PlateGirder` | I-beam: depth **90**, flange **40 × 3**, web **2** | ≤ 60 | Phase A beam slot. Set `BeamWidthCm=40`, `BeamDepthCm=90`. No geometric stiffeners, since they would stretch. Rivet rows come from the trim on the flange faces. |
| G2 | `SM_UP_Channel` *(optional)* | C-section 30 × 10 × 1.5 | ≤ 40 | Spare beam profile for the rails, if Phase B separates rails from crosses. |

**Module pieces**

Two of these (C1, D1) stretch in one axis only. The other three are never stretched.

| # | Module | Size (cm, X × Y × Z) | Tris | Build steps |
| --- | --- | --- | --- | --- |
| C1 | `SM_UP_LacedColumn` | **500** × 60 × 40 (X = height) | ≤ 600 | 1. Two C-channels 500 × 40 × 12, 36 cm apart. 2. X-lacing bars 6 × 1.5 cm, one diagonal pair every **50 cm**, so 10 pairs. 3. Splice plates 40 × 30 × 1.5 at 0 and 250. The lacing repeats on 50 cm, so a stretch of 0.9–1.3× reads fine. **The 500 module equals the P04 station pitch.** **[meas]** |
| P1 | `SM_UP_PierBase` | 140 × 140 × 120 | ≤ 300 | 1. Box. 2. Bevel 6 cm, 1 segment. 3. Batter the top face inward by 8 cm. 4. Three spall notches on the edges (boolean, then apply). 5. Concrete slot. |
| K1 | `SM_UP_KneeBracket` | 120 × 2 × 120 | ≤ 60 | A triangular gusset plate with a 10 cm flange on the hypotenuse. |
| D1 | `SM_UP_DeckBay` | **500** × **1000** × 30 | ≤ 500 | 1. Two stringers along X, 500 × 30 × 30, at Y ±250. 2. **Ties along Y**, 20 wide × 1000 long × 12 deep, **every 45 cm**, so 11 ties with **25 cm gaps** of real geometry. 3. Ties sit on the stringers. One instance per bay. **The ties run along Y, so stretching Y to the Passage span lengthens them correctly.** X stretches to the actual station gap. |
| R1 | `SM_UP_CatwalkRail` *(optional)* | 500 × 6 × 110 | ≤ 120 | Posts every 125 cm, and two 2 cm cables as thin boxes. |

- **Downpipe:** dropped. Gary says it doesn't need much detail.
- **Nanite: OFF on all modules.** Each is under 600 tris, and the total is about 1,200 instances per Passage. **[inf]** That is cost reasoning. The prototype measures stat GPU with Nanite on and off for D1 and C1 only.
- The kit master is Nanite-enabled (`Docs/WingMateriality.md:179`), so either setting is legal.

**Bakes (same script)**

All bakes come out at 1024² or below:
- `T_UP_SteelTrim_N`: a rivet row, 2.2 cm domes at a 10 cm pitch in the V 0–0.1 band, flat elsewhere.
- `T_UP_SteelTrim_M`: R = chip mask, G = rust-streak mask, B = cavity.
- `T_UP_Graffiti_Atlas`: 2×2 tag atlas with alpha. It is drawn procedurally, so it carries no copyrighted imagery.

**Offline gate**

Before Unreal is involved, re-import each FBX into a fresh Blender scene and assert:
- the bounds match the table (±0.1 cm);
- the triangle count is within budget;
- there is one object, no LodGroup and one material slot;
- the UV V-sign is negative on the vertical faces.

The gate writes `DerivedAssets/Underpass/kit_manifest.json` (bounds, tris, sha256).

**For the conductor via Blender MCP:** run the same script body through `execute_blender_code`, one module per call, and check each with `get_object_info` and `get_viewport_screenshot`.
- **The headless run is the build of record.** MCP output is look-dev only.
- **The Blender GUI is exclusive** (memory `puss-session-ownership`).

## 3. Export and import (the FBX traps)

**Export.** Use Flat V3's call verbatim: `Tools/FlatV3/build_v3_flat.py:1838-1843`.

```
bpy.ops.export_scene.fbx(filepath=..., use_selection=True, object_types={"MESH"},
    apply_scale_options="FBX_SCALE_UNITS", axis_forward="-X", axis_up="Z",
    bake_space_transform=False, add_leaf_bones=False, path_mode="AUTO")
```

This is one FBX per module, to `DerivedAssets/Underpass/`. **[decl]** Flat V3's FBXs imported correctly with it (`Docs/FlatV3Status.md`). Even so, **gate the length axis after import** rather than trust the axis flags. **[inf]** The kit's length is +X, while a Flat card's is not.

**Import.** Copy `_fbx_options` and the `AssetImportTask` pattern from `Saved/CodexFlatV3/fence/fb_workflow.py:233-275`:
- `import_materials=False`, `import_textures=False`, `combine_meshes=False`, `automated=True`, `replace_existing=False`, `save=False`;
- the import goes to `/Game/InfinityStage/RigAtmos/Underpass/Meshes`.

The traps, from memory `ue58-fbx-import-traps`:
- **Interchange ignores the FbxImportUI options.** So set them anyway, and **diff the destination folder before and after**. Delete any never-saved strays: without options, the 4 Oct test made 6 stray assets.
- **The LOD split cannot happen**, because there are no `_LOD` children. Still gate `get_num_lods()==1` and that there are no `*_LOD*` assets.
- **Gate the bounds:** the read-back `get_bounding_box()` size must match the manifest. **X must be the long axis.** If it is not, stop and fix the export; never rotate in UE.
- **Call `modify()` before every setter.** That covers the mesh Nanite settings (off), material slot assignment, and Structure actor properties. Read each back.
- **Save only the imported packages.** Assert there are no other dirty packages, then log `UNDERPASS_KIT_IMPORT_OK|run=<id>|meshes=N|strays=0`.

**Materials** (Wing materiality):
- `M_UP_PaintedSteel` and `M_UP_GrimyConcrete` go in the new `RigAtmos/Underpass/Materials` folder, with **new nodes only on new assets**. Never delete nodes on pre-existing ones (memory `ue58-python-material-authoring`).
- They use the per-member mapping of `M_Kit_Surface_Master`. U is scaled by `custom[1]/100`.
- **Black band:** `WorldPosition.Z < 150 + PassageFloorZ`. The Passage floor Z is a parameter, so a Passage not at Z 0 still works.
- **Textures reused** **[meas, file listing]**:
  - StarterContent `T_Metal_Rust_D/N`, `T_Concrete_Grime_D` and `T_Concrete_Poured_D/N` (under `KK_S2_Shrine/StarterContent/Textures/`);
  - `T_FenceBay_GalvanisedRust_*`;
  - OceanFloor `T_Rust_BC/N`.
- **Megascans:** only grass, soil, rocks and logs are in the project. **[meas]** `Docs/WingMateriality.md:216-217` agrees there is no textured metal.
- **MIs:** `MI_UP_Steel_Green`, `MI_UP_Steel_Black` (for the deck underside, so it reads dark) and `MI_UP_Concrete`.

## 4. Apply route

Each editor step is its own slot. Each has a dry run, a backup, an originals JSON written *before* any change, and a revert script. Success is asserted on read-back plus a log marker with a run id. Save only the affected level; never Save All.

**Step 0, offline**
- The Blender build and gate (§2).
- Write the Phase B C++ as a **held patch** in `Scripts/patches/` and restore the file (memory `puss-held-cpp-edits-as-patches`). It contains:
  - `FInfinityStageUnderpassSettings`: `bEnabled=false`; mesh, material and shadow slots per part; `ColumnEvery=2`; `ColumnOutsetCm=60`; `DeckHeightCm=2000`; `bDeck`, `bColumns`, `bKnees`, `bCatwalk`;
  - new `ETimberPart` values 8–12;
  - `BuildUnderpass()` using `FitMeshToTimber`, with one random draw per statement (memory `puss-random-draw-order`);
  - tests mirroring `InfinityStageStructureTests.cpp`: counts, clean end at the last station, off-by-default leaves counts unchanged.

**Step 1, import** (one slot, §3).

**Step 2, materials** (Wing materiality's slot).

**Step 3, P05 prototype** (one slot)
- **Back up:** `Backups/PreUnderpassP05-YYYYMMDD-HHMM`.
- **Read-only probe:** Structure 05's Gridiron struct and `IsStructureCurrent`. Run a **clearance check**:
  - girder underside = 1150 − 45 = 1105, against P05 wing tops (≤ 600), border bottoms (≥ 527, already below the grid) and lamp housings inside 1105–1240;
  - list the intersections; do not fix them.
- **Write the originals JSON.**
- **Apply.** Copy the struct, set `BeamMesh=SM_UP_PlateGirder`, `Material=MI_UP_Steel_Green`, `BeamWidthCm=40`, `BeamDepthCm=90`, `SectionVariation=0`, `TwistDegrees=0`, `bCastShadow=True`, then `actor.modify()` and set the struct back. Read it back, then run `MaterializeStructure()`.
- **Assert:**
  - the new `INFINITY_STAGE_STRUCTURE_OK` line for Structure 05 with **cross_beams=93, rails=184, boards=10463, portal=1901** and the same totals;
  - any board drift is reported as a finding, not as failure (the known drift, `RigAndAtmosphere_Handover:276-279`);
  - `IsStructureCurrent()==True`.
- **Save** the level only, then read it back.
- **Hand-place a Phase B mock bay:** tagged `UnderpassProto` StaticMeshActors. That is 2 × (C1 + P1 + 2 K1) at ±(745+60) and 1 D1 at 2000 over one mid bay, plus one shadow-casting shaft Rect light above the deck.
  - The structure never touches untagged actors (`.h:422-424`).
  - Memory `puss-benches-are-level-activity`: announce the mock, and keep it out of the save script.
- **Look bench:** add an `underpass` toggle next to the wet floor and the ~1 Hz strobe from the brief.
  - `Docs/Conductor/LOOK_DEPTH_PLAN_2026-10-05.md` **does not exist yet** (checked 4 Oct).
  - Capture from P05's ~150 cm camera with no exposure override, plus one from the Opening's stalls camera (Gary: it "may be glimpsed from the Opening").
- **Measure:** stat GPU with and without the mock, and with Nanite on and off for C1 and D1.
- **Revert:** `underpass_p05_revert.py` restores the originals, re-fits and deletes the mock by tag.

**Step 4, Gary's look, then Phase A show-wide** (one slot)
- The same script loops over Structures 02, 03, 04 and 06, and 01 if Gary says so.
  - It runs a per-Passage clearance probe first: P01 has borders down to 746 and lamps above 1150.
  - It asserts the census per Passage, then does one level save.
- **P03 ground is off.** **[decl]** `RigAndAtmosphere_Handover:33`. That does not matter here, because Phase A touches only the gridiron.

**Step 5, the build window**
- Apply the patch and build with the editor closed (memory `puss-build-gate-is-machine-wide`).
- Run the filtered `InfinityStage.Structure.*` tests.

**Step 6, Phase B per Passage**
- Delete the P05 mock. Set `Underpass.bEnabled` with its slots, re-fit, and run the census gate.
- Do P05 first, then the rest in one loop.

**Shaft lights and the strobe:** the Lighting looks stream owns these. **P05 has 0 shadow casters today.** **[meas, dated]** `RigAndAtmosphere_Handover:170-172`. So every slatted-shaft light is a new VSM cost: keep it to 1–3 per glimpse zone, with tight cones.

## 5. Performance budget

All of these are inferred (arithmetic); the Step 3 profile replaces them.

- **Phase A:** 0 new instances. The triangle cost goes from 12 (the cube) to ≤ 60 per beam, so about 17k tris added to P05.
- **Phase B in P05**, with columns every 2nd station:
  - columns 94, piers 94, knees 188, deck 93, rails optional 186;
  - **about 470–660 instances and about 130k tris**, against the existing 13,789 instances.
- **Shadows:**
  - **On:** girders (Phase A) and the deck. These make the bands on the wet floor and the slatted shafts.
  - **Off:** columns, piers, knees and rails.
- **No WPO and no translucency.** Graffiti is masked within the opaque concrete; it is not a decal actor.

## 6. Owners (proposed)

| Work | Owner |
| --- | --- |
| Blender kit script, bakes, offline gate, import (Steps 0–1) | **Conductor via Blender MCP and headless Blender**, or a conductor-run Claude "Rig kit" subagent. Rig & atmosphere is parked (`RigAndAtmosphere_Handover:919`). Codex is superseded from 3 Oct (memory `claude-coding-from-3-oct`). |
| `M_UP_*` masters and MIs (Step 2) | **Wing materiality**: it owns `M_Kit_Surface_Master` |
| Phase B C++ patch and tests | the Rig kit subagent. The structure files were Rig & atmosphere's, and the conductor approves the build. |
| Structure re-fits (Steps 3, 4, 6) | the conductor schedules them, with one level writer |
| Shaft lights, 1 Hz strobe, haze | Lighting looks |
| Wet floor | the look bench owner |

## 7. Open questions for Gary (my recommendation first)

1. **Girder depth, show-wide:** 90 cm plate girders in place of the 26 × 34 timbers? I recommend **yes**. It is one constant module, so the scale invariant holds.
2. **P01's timber portal and grid.** The portal shares the gridiron's mesh, so P01 would turn to iron too. I recommend **keeping P01 as timber**, as the "theatre" register, with the iron starting at P02. The setting is per actor.
3. **Deck height:** a tie deck at ~20 m over girders at ~11.5 m? I recommend **yes**. A single level at about 12.5 m would sit below 372 P05 lamps.
4. **Strobe:** a regular 1 Hz, as you described, or the seeded aperiodic blinkers? I recommend **one regular 1 Hz per glimpse zone**.
5. **Graffiti:** piers only (ref_03), or girders too (ref_01)? I recommend **piers only**.
6. **Fab download** of real riveted steel? I recommend **not yet**: go procedural first and decide after seeing it.

## UNCLEAR (searched, not proven)

- **Current per-Passage `Gridiron.Material`, BeamMesh and HeightCm.** These are level data, so I did not read them offline. As of 29 Sep they were Cubes with no material at 1150. Step 3's probe reads them.
- **Station pitch on P01, P02, P03 and P06.** It is 500 cm on P04 and consistent on P05, but the others were not read. The fit stretches modules to any gap, so this only affects how the lacing and deck read.
- **Lamp housings inside the deeper girder band (1105–1240)**, per Passage. Not probed.
- **The ~47 unattributed P05 instances** (probably the understage).
- **Whether the StarterContent rust and concrete read as credible at show exposure, and the GPU cost of Nanite and the shaft VSM.** Not rendered or measured.
- **Whether the FBX axis flags put the kit's +X on UE +X.** Flat V3 proves the call, not this axis. The bounds gate in Step 1 decides.
