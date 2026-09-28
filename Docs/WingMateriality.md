# Wing materiality

Owned by the **Wing materiality** stream, session "Puss · Wing materiality".
The brief is `Docs/Conductor/BRIEF_WING_MATERIALITY_2026-09-25.md`. This is the
stream's living record: what exists, what is proven and at which tier, and what
is next. Scope is `/Game/Scenes/Wings` materials only.

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
