# Wing materiality

Owned by the **Wing materiality** stream, session "Puss · Wing materiality".
The brief is `Docs/Conductor/BRIEF_WING_MATERIALITY_2026-09-25.md`. This is the
stream's living record: what exists, what is proven and at which tier, and what
is next. Scope is `/Game/Scenes/Wings` materials only.

## P04 rolled out; kit master built (29 Sep)

- **P04 DONE:** 26 meshes, 78 MIs, 39 panels, no collateral; read-back 78/78, 0
  dirty, 0 compile failures. **All 45 P04 panels are now on the new master.**
  Undo: `rollout_rollback_20260929-132520.json`. Backup:
  `Backups/PreWingRolloutP04-20260929-132505`. P05 is still held for Gary (relief
  and cost).
- **Kit master BUILT** per Gary's choice ("walnut planks, procedural steel for
  the grooves"): `/Game/Scenes/Wings/PaintedSurface/Kit/M_Kit_Surface_Master`
  (60 nodes, ISM and Nanite set, world-space normals), presets
  `MI_Kit_WalnutPlank` (IsMetal off) and `MI_Kit_SteelGroove` (IsMetal on). 0
  dirty, 0 compile failures. **Not assigned:** Rig assigns them
  (`Ground.BoardMaterial`, `Ground.GrooveMaterial`) and re-fits. Built by
  `build_kit_surface_master.py`. The texture layout, read off the exported walnut
  strip, is embedded there: 960 cm tile, 20 strips, one painted plank per
  480 cm board, so no painted joint lands mid-board.
- **Rendered look not yet seen.** It shows once Rig assigns and re-fits.
- **One painted strip per member holds across the whole kit** (Rig, from source,
  29 Sep). Every face is laid in even lanes at the board pitch (24 + 0.8 cm).
  Fascia and returns are 5 courses of about 23.4 cm, other lanes about 24.8 cm,
  and the widest possible lane is about 36 cm. That's under the ~40 cm point where
  a single strip would look stretched, so no fascia variant is needed. If
  BoardWidthCm or the course logic changes, revisit (Rig will say).
  Walnut: Rig's `board_material_apply.py`. Steel: after Rig's next build
  (`Ground.GrooveMaterial` is unbuilt C++).

## Proposal (29 Sep, now built, see above): walnut on the structure kit

Gary asked for "texture plus geometry": his walnut floor on the kit's real boards.
The kit is engine Cubes scaled to size (about 29k instances, empty material slot).
Per-instance data is `[variation, length, width, thickness]` cm, with local
X = length. Rig owns assignment (`Ground.BoardMaterial`, re-fit); this stream
would own the material.

- **New kit master in our folder**, reusing the pack's textures. The walnut MI's
  parent `M_Flooring_Mat` is UV plus CustomRotator only, and editing a
  marketplace master is off-limits.
- **Two mapping modes, one static switch:** *world-aligned* (continuous
  herringbone with the slots cut through it) or *per-member* (grain along each
  board, offset by variation). Per-member is required for anything that moves.
  The pack also has straight walnut planks (`T_Walnut_Strp_02`).
- **Cost:** box faces are axis-aligned, so the projection is picked per face:
  one texture set per pixel, no triplanar, no POM. About half the wing master's
  instructions.
- **Presets for** floor, grooves, wing poles and side frames: same kit, same master.
- **Open for Gary:** (A) herringbone deck or walnut planks; (B) which parts are
  "metal", and whether a procedural stopgap is acceptable. There's no convincing
  textured metal in the project; real metal would need a download.

## P04 / P05: PLANNED, READY TO RUN, NOT APPLIED (prepared 2026-09-29 overnight)

Prepared read-only from disk, for Gary's go. Nothing has been applied.

| | P04 (remaining) | P05 |
| --- | --- | --- |
| Meshes / MIs | 26 / 78 | 22 / 66 |
| Panels | 39 (+6 already done = 45) | 279 |
| Family | Group B legacy, **generated** `_H`/`_N` (all 26 imported) | Group A, existing relief set in the `Passage05_BirdToMountain` root (cross-root, as approved) |
| Edge half-thickness | 2.5 (legacy 5 cm FBXs) | 5 |
| Collateral into done passages | **none** | **none** |

- **P05 registration is clean.** The 21 flags are the post-restart 32×32 compile
  placeholder. All 66 P05 textures were last modified on **18 Sep**. The 25 Sep
  plan checked compiled sizes on all 40 Group A meshes with 0 problems, and the
  colour pairs were proven pixel-identical then. The 22nd isn't flagged because
  its height map is also used by the P01 ceiling, so it was already compiled.
- **Nothing needs generating.** All maps exist.
- **What's different from the first four passages:**
  1. The deferral was scope, not a known defect. On 25 Sep Gary said P04/P05 were
     "barely lit", so nobody could judge them. He's lighting all wing series
     from 29 Sep.
  2. **P05 relief is an art call.** In August Gary said "not to worry about
     Passage 5 height/bump maps" for the clouds. The plan wires real relief
     (HeightRatio 0.006). For flat **and cheaper** clouds, set `HeightRatio` 0
     **plus `POMMinSteps` 1 and `POMMaxSteps` 1**: with the ratio at 0 alone, the
     POM loop still runs its 8–24 steps and costs the same. These are MI scalars,
     so there's no master change. The masked cut-out (the black-area fix) and the
     paint look still apply. Options for Gary: (a) full relief, (b) lean flat
     clouds, (c) not yet.
  3. **P05 clouds are 45–98 % transparent**, and the legacy material is opaque,
     so any part of the cut-out mesh over transparent texels likely draws
     black (the P01 ceiling mechanism). The new master's mask would fix it.
     This is likely, not measured: the mesh outlines aren't readable from disk.
  4. **Cost:** P05 alone is 279 panels, about as many as P01+P02+P03 together.
     They're Nanite, so opaque → masked plus POM on mostly transparent clouds
     is the largest raster/VSM cost step of the rollout. Watch frame time.
  5. P04 is the legacy 5 cm FBX set (phone photos, stone, pillars). Changing its
     materials is not rebuilding the FBXs, so the conventions doc's
     no-retro-rebuild rule isn't engaged.
- **To run it** (editor write slot, a fresh backup of the P04 and P05 material
  folders first):
  1. `rollout_plan.py` (read-only; refreshes the snapshot, which predates P03)
  2. `rollout_request.json` = `{"passages": ["P04","P05"], "families": ["GroupA","GroupB"], "dry_run": true}`,
     run `rollout_apply.py`, and report the numbers
  3. set `"dry_run": false`, run it again, then `verify_rollout_readonly.py`

## V2 edges rebuilt and P03 rolled out: DONE 2026-09-28 late (approved by Gary via the conductor)

- **`M_StageOpeningV2_Edge` rebuilt in place, delete-free.** The first attempt
  deleted a node and hit `Assertion failed: !IsRooted()`, crashing the editor
  (nothing saved; the asset stayed at 17 Aug). **Project rule: never delete
  expressions on assets this stream didn't create.** The builder's
  `get_or_create` now refuses outside `PaintedSurface`. `rebuild_v2_edge.py` renamed
  the 3 originals to `Legacy_*` (left inert), added the 19 canvas-edge nodes and
  rewired the outputs (mode=added, 22 expressions, 0 dirty, no compile failures).
  All 75 live users are 10 cm (HalfThicknessCm 5). **Correction (29 Sep, from
  Soft goods): `SM_FireSafetyCurtain_01` (also 10 cm) is not placed in the level,
  but `AInfinityStageCurtainRig` force-shows it when active. There's a curtain rig
  in all seven sequence blocks, so this edge change IS visible at every
  transition.** It gains the batten and canvas edge instead of flat dark brown.
  If Gary dislikes it on the curtain: `restore_v2_edge_original.py` reverts the
  material for **all** its users (the 74 V2 wings too), so separating the curtain
  would need its own edge material and a change to that mesh's slot. That's
  Soft goods' asset. Undo, delete-free:
  `restore_v2_edge_original.py`. Backup: `Backups/PreV2EdgeRebuild-20260928-232203`.
  The ISM flag was already True there and its users aren't Nanite, so it never
  had the packaged-build hazard; the Nanite flag is belt and braces.
- **P03 rolled out:** 18 meshes, 54 MIs, 63 panels, **no collateral**. 36
  Front/Back MIs are on the painted master with the P03 relief maps, 18 Edge MIs
  on the canvas edge. Read-back 54/54, 0 dirty, no compile failures. Registration
  was proven from exported source pixels (`groupa_registration.json`), because
  placeholder 32×32 sizes after a restart are not dimensions. Undo:
  `rollout_rollback_20260928-232414.json`. Backup:
  `Backups/PreWingRolloutP03-20260928-232314`.
- VSM: the one `[VSM] One Pass Projection max lights overflow` line in the log is
  from the editor relaunch, before P03 changed. Unreal usually prints it once per
  session, so the log alone can't show whether it recurs. Opaque → masked
  changes shadow **cost**, not the **count** of lights per pixel that the overflow
  measures. P03 lighting is Rig's.
- Now on the new look: **P01, P02, P03, P06**. Deferred by Gary: P04 (39 panels
  still legacy) and P05.

## Rollout of P01/P02/P06: DONE 2026-09-28 (approved by Gary via the conductor)

- **81 meshes, 94 MIs** reparented and saved; every change read back
  (`verify_rollout_readonly.py`: 94/94 match); 0 dirty; no compile failures.
  - V2: 74 MIs (all of P02, 14 StageOpeningV2 in P06) moved to the painted
    master, textures kept, measured UV spans set.
  - Legacy Group B: 6 meshes × Front/Back/Edge = 18 MIs, generated `_H`/`_N` wired.
  - Trial rococo R: moved from luminance relief onto its generated maps (2 MIs).
    `UseBurn` stays on only for the two P01 trial MIs.
- Panels changed: P01 119, P02 69, P06 159, **plus 6 in P04** as collateral
  through 4 shared meshes (`SM_L_1_roccoco`, `SM_L_pillar1_bw`,
  `SM_R_Pillar1_bw`, `SM_R_Pillar2_bw`). P04's other 39 panels are still legacy.
- Live undo: `Saved/CodexWingMateriality/rollout_rollback_20260928-205959.json`.
  File backup: `Backups/PreWingRollout-20260928-205743` (687 assets).
- **Usage flags, stated correctly** (read-only probe, `usage_flags.json`): the
  packaged-build hazard was the old `M_StageOpeningV2_Relief_Master` alone
  (`used_with_instanced_static_meshes` False). It carried all 74 V2 relief meshes,
  about 173 panels in P02 and P06, and none of them are Nanite. The legacy FBX Phong
  material (ISM and Nanite True) and `M_StageOpeningV2_Edge` (ISM True, non-Nanite
  meshes) were never at risk. After this rollout **no wing renders with the old
  relief master**, so the hazard is gone. Earlier notes and a commit message said
  "every wing"; that was an overstatement.
- **V2 edges unchanged:** the 74 V2 meshes use `M_StageOpeningV2_Edge` directly
  (a Material, not an MI), so their edges are still flat dark brown. Matching
  them to the batten-and-fray edge means rebuilding that material's graph in
  place. That's a separate yes/no for Gary.
- Known false alarm: right after an editor restart, the plan's registration check
  reports Group A relief maps as 32×32 (the texture placeholder while compiling).
  Fix the check to read the real size before any P03/P05 run.
- Still waiting on Gary: P03/P04/P05 (Group A plus the rest of P04), V2 edges,
  upscale install, which wings burn.

## Resume here (stood down 2026-09-28 for a studio visit)

Working tree clean; last stream commit is the one that added this section.
Everything below waits on **Gary**, not on another stream:

1. **Rollout** of P01/P02/P06 (80 meshes, 92 MIs, P04 collateral through shared
   meshes). Planned and dry-run, not executed. Gary judges the P01 trial first
   (rococo R new beside rococo L legacy, plus the cloud ceiling). Re-run
   `rollout_plan.py` before applying: the plan is a snapshot of live MIs, and
   other streams have changed P01 and P03 since.
2. **Upscale.** Upscaling was chosen over regeneration; the spec is below. No
   tiled upscaler is installed, and installing one (tool plus models) needs
   Gary's OK. Don't run it during heavy disk work on D:.
3. **Which wings burn.** This gates the per-MI `UseBurn` switch, which is on only
   for the two P01 trial MIs.
4. ~~CaptureManager check~~ **Done 2026-09-28, nothing for the wings.**
   `C:\Users\Administrator\AppData\Local\CaptureManager\Media\PussStage` holds
   4.9 GB of facial-capture video ingest (8 takes: child1/2, shoreguy1–6; 28,406
   JPEG frames, WAVs, .cparch). It contains no wing imagery. Only
   `Saved/CodexMocap` references it, so the C:/D: split is the mocap stream's
   concern.

To judge the trial in your own viewport, paste these into the editor console
(`trial_viewpoints_readonly.py`; eye height 1.7 m, 30° off the face, both from
the corridor side):

```
BugItGo 3763 -450 170 0.0 -30.0 0   (rococo L, legacy, 1 m)
BugItGo 3677 -400 170 0.0 -30.0 0   (rococo L, legacy, 2 m)
BugItGo 3763 450 170 0.0 30.0 0     (rococo R, new master, 1 m)
BugItGo 3677 400 170 0.0 30.0 0     (rococo R, new master, 2 m)
```

Facts that landed while stood down:

- Per-instance custom data **verified live on 2026-09-28** (read-back): P01
  (9 components) and P03 (18) carry 4 floats, with distinct seeds in [0, 1) in
  slot 3. **P02, P04, P05 and P06 still carry 0 floats** and fall back to
  PerInstanceRandom until their next re-materialize, so any variation judged
  there now is **not** the variation the show will have.
- P01 station spacing is deliberately irregular: ±750 on station 1 and 21 other
  pairs, 15 at ±500, 3 at ±400, 7 asymmetric at −400/+750. Nothing in this stream
  depends on spacing. The rollout reparents MIs per mesh, and the burn front and
  detail coordinates are computed per panel in mesh-local centimetres.

## State at 2026-09-25, end of the first session

| | Status | Tier |
| --- | --- | --- |
| Survey of what actually renders | done | read-back |
| Ceiling OpacityMask bug fixed | done | saved read-back; **render unverified** |
| New masters built | done, compile clean | saved read-back; **render unverified** |
| Two-panel trial in P01 | applied, revertible | saved read-back; **awaiting Gary's eye** |
| Rollout of all wing MIs | planned and dry-run; **not executed** | — |
| Group B height/normal maps | generated and imported (66 textures); **not wired** | read-back |
| 4K upscale | spec agreed; silhouette proof done; tooling not installed | — |

Editor captures don't follow the viewport camera (see the plan's screenshot
note), so nothing here has been visually verified.

## What renders (survey, read from live ISMs)

149 meshes, 765 panels. The Show has **no** `MaterialOverrides` and no image
flips, so what renders is decided entirely by each mesh's slot MIs.

| Family | Meshes | Panels | Where |
| --- | --- | --- | --- |
| V2 relief (`M_StageOpeningV2_Relief_Master`) | 74 (+1 moved in trial) | 197 | P02, P06, P01 ceiling |
| Legacy FBX Phong, **Group A** (relief maps exist, unassigned) | 40 | 342 | P03, P05 clouds |
| Legacy FBX Phong, **Group B** (no maps) | 33 | 219 | P01, P04, P06 |
| Salt formation (own material) | 1 | 7 | P01 |

Texture resolution is the far-read ceiling: median 6.5 mm/texel on 10 m panels,
against about 0.6–1.2 mm/px on screen at 1–2 m. The wing art was made with
Codex's built-in image generator, whose native output is 1024×1536. See Upscale
below.

## Assets (`/Game/Scenes/Wings/PaintedSurface`)

- `M_Wing_PaintedSurface_Master`: POM from `_H` (or BaseColor luminance through
  static switch `HasHeightMap`), ClearCoat varnish with its own roughness,
  anisotropy, height-driven grime and ridge wear, tiling canvas weave and brush
  detail in panel-local cm faded by distance, per-instance variation, and burn.
  Parameter names `BaseColor/Height/Normal/OpacityMask/Roughness/Specular` match
  the old relief master, so old MIs reparent with their textures intact.
- `M_Wing_CanvasEdge_Master`: timber batten core, canvas lip, fray.
  `HalfThicknessCm` is 5 for V2 meshes and 2.5 for the legacy 5 cm meshes.
- `Textures/T_WingDetail_*`: tiling detail maps from
  `Tools/WingMateriality/generate_detail_maps.py`.
- `GeneratedRelief/T_<texture>_H|_N`: Group B maps, from
  `Tools/StageOpening/generate_relief_maps.py` run on textures exported out of
  Unreal (`DerivedAssets/WingMateriality/SourceExports/GroupB`), so they are
  pixel-registered with what renders.

**Usage flags are set explicitly on both masters** (`used_with_instanced_static_meshes`,
`used_with_nanite`). The old relief master had both False, which would render
default material in a `-game` or packaged run. Do not remove them.

The old `M_StageOpeningV2_Relief_Master` and `M_StageOpeningV2_Edge` are
untouched, as the rollback.

## Per-instance custom data (agreed with Effects sources)

| Slot | Meaning | Default while ISMs carry 0 floats |
| --- | --- | --- |
| 0 | BurnProgress, 0 intact → 1 consumed | 0 |
| 1, 2 | ignition UV on the panel face (V-down) | 0.5, 1.0 (bottom centre) |
| 3 | VariationSeed; replaces PerInstanceRandom when ≥ 0 | −1 |

`SetNumCustomDataFloats(4)` and a deterministic seed in slot 3 landed in
e0c2c2f: `(HashCombine(cue, side) % 100000) / 100000`, so the value is in [0, 1).
The floats are reserved only when a component is **created**, so components
serialized before that build carry 0 floats until their passage is re-materialized. From that build on, slot 3 replaces
PerInstanceRandom as the variation source.

**Burn contract with Effects sources' WingBurn Niagara.** The front spreads in
centimetres, not UV:

- `UVSpanUCm` / `UVSpanVCm` per MI = centimetres covered by UV 0..1 on that mesh.
  These are measured from the mesh UVs by `probe_uv_axes_readonly.py`
  (`uv_axes.json`), **not** from the bounds, because the images carry
  transparent margins. The cloud ceiling's UV span is 4726 × 1889 cm on a
  2129 × 1000 cm mesh.
- Mean front radius R = BurnProgress × (Dmax + pad), where Dmax is the distance
  from the ignition UV to the farthest corner of the UV square (in cm), and
  pad = IrregularityCm/2 + 1.25 × BurnEdgeCm (160 and 40 by default, so
  130 cm). Progress 1 is therefore always fully consumed. The pad is **coupled**
  to `InfinityStageWingBurn::FrontPadCm` in Effects' code (79bb2d2). Change both
  sides together, and never override these two per MI. BurnMask moves the
  visible front by ±IrregularityCm/2 around R.
- Every wing mesh has exact planar UVs: V = aV·Z + bV with aV < 0 (V-down), and
  U = aU·Y + bU with aU < 0 on 145 meshes and > 0 on 4. The per-mesh a/b values
  are in `uv_axes.json`.
- **Ignition (0, 0) means "not set", which is bottom centre (0.5, 1.0), not the
  UV top-left corner** (since 21bc807). Once the ISMs carry 4 floats, unwritten
  slots read 0 rather than the node defaults. Effects: write a real ignition
  whenever you burn, and never use exactly (0, 0) to mean a corner.

`UseBurn` is on only for the P01 trial MIs, at Effects' request, for the first
PIE proof. Which wings burn is Gary's call.

## Cross-root dependency (for the `/Game/Wings` cleanup, ShowBuildTodo 0.5)

Once rolled out, the 22 **Passage 5 cloud** MIs under `Passage5_BirdToMountainV2`
reference `_H`/`_N` in **`/Game/Scenes/Wings/Passage05_BirdToMountain/Textures`**.
This is by the conductor's decision: reference, don't copy. All 40 Group A colour
textures were checked pixel-identical to the relief set's own BaseColor, so the
maps are registered. That root is not unused. Moving it must go through
redirectors, never deletion.

The P01 ceiling mesh `SM_CloudCeilingSmall_02_C` also renders from the
`Passage05_BirdToMountain` root.

## Upscale spec (Gary chose upscaling over regenerating)

Inputs are the approved generations. The anchors in `.codex/generated_images`
and the approved packs under `DerivedAssets/GeneratedConcepts` are load-bearing,
not scratch.

1. Upscale **RGB only**. Before upscaling, pad colour out into the transparent
   area (edge dilation). Transparent texels are RGB 0 and an upscaler would pull
   black into the silhouette edge.
2. **Alpha must not be re-sampled with Lanczos or bicubic.** Proof on
   `T_P02_SET01_L` and `R__1_roccoco` at 4×, against the edge the GPU draws
   today (bilinear, clip 0.333):

   | alpha method | differing px | mean edge shift | max |
   | --- | --- | --- | --- |
   | bilinear, kept soft | **0** | 0 | 0 |
   | bicubic, re-thresholded | 10–13 k | 0.05–0.07 px | ≥ 4 px |
   | Lanczos, re-thresholded | 14–15 k | 0.07–0.08 px | ≥ 4 px |

   The max comes from ringing creating or erasing specks in soft alpha, so thin
   features appear or vanish. Use bilinear, or keep `OpacityMask` on the
   original texture and upscale colour into a new asset. The master samples the
   mask separately, so the silhouette then cannot move at all.
3. Exact 2× or 4×; overlapping tiles; final-handedness sources, never flipped.
4. 4K colour and normal, 2K height. Regenerate `_H` from the upscaled colour
   with `Tools/StageOpening/generate_relief_maps.py` (multi-scale local
   contrast, not raw luminance).
5. Order: P01, P02, P06, then P03. P04/P05 deferred.

No neural upscaler is installed on this PC (RTX 5070 Ti, 16 GB available).
Installing one, and downloading models, needs Gary's explicit OK.

## Scripts (`Saved/CodexWingMateriality`, run via MCP 8010)

Every script asserts the vertical-slice world and checks the dirty set.

- Survey (read-only): `survey_rendered_materials_readonly.py`,
  `survey_master_graph_readonly.py`, `texture_sizes_readonly.py`,
  `probe_mesh_bounds_readonly.py`, `export_texture_sources.py`
- Build: `build_painted_surface_master.py`. Idempotent; it clears node by node,
  because `delete_all_material_expressions` leaves nodes behind in 5.8.
- Trial: `trial_apply.py` / `trial_revert.py` (with `trial_rollback.json`)
- Rollout: `rollout_plan.py` (read-only) → `rollout_apply.py` with
  `rollout_request.json` (`dry_run` true by default; every real run writes its
  own rollback file). The dry run for P01/P02/P06 changes 80 meshes / 92 MIs, and
  touches P04 as collateral through shared meshes.

Backup of all 615 Wings material assets before any change:
`Backups/PreWingMateriality-20260925-193234`.

## Next

1. Gary looks at the trial in P01: rococo **R** (new) beside rococo **L**
   (legacy), and the cloud ceiling overhead. Tune, then roll out P01/P02/P06.
2. Import the Group B maps and wire them at rollout.
3. V2 edges use `M_StageOpeningV2_Edge` directly, so they can't be reparented.
   Rebuild that material's graph in place, or leave it.
4. Upscale tooling, once Gary OKs an install.
