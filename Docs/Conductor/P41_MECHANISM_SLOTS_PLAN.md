# P41 — mechanism slots plan

Status: **offline design only**. No Unreal tool, C++, `Content/`, Show, level, or main-tree file was changed by this work.

## Recommendation

**[inferred]** Adopt **C+, a procedural slot-trim kit backed by the existing generated void**. Passage floors should keep using Structure-owned board omissions, dark understage, and three-piece steel channels, but each fixed 8 cm cut should become the union of the existing outward chariot run and the mechanism’s swept footprint. This rule never removes existing track clearance. S3 should receive a non-destructive dark backer and blackened-steel lip on each inner wall face; the intact wall/liner continues to occlude the wave until it crosses the face. Do not use GeometryScript booleans in the first implementation.

**[inferred]** Default design study values, all exposed as Gary arguments: total clearance `2 cm` (1 cm each side), blackened steel lip, `0.2 cm` proud lip, `2 cm` recessed wall backer, and no emissive. These are preview values, not approvals.

## Findings

### Movement and authority

- **[declaration-proven]** The authored mechanism kinds are Slide, Topple, Turn and Trap; playback is Static, OneShot, ContinuousLoop, BoundedLoop or CameraGust. Motion stores side-specific curves, `InwardTravelCm`, `MaxAngleDeg`, phase origin and explicit origin frame (`Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h:89-104`, `:579-588`, `:646-717`).
- **[declaration-proven]** Runtime motion evaluates the selected side curve and modulation scale; Trap translates on panel-local up, Topple/Turn rotate about an authored pivot/axis, and Slide translates along the materialized inward vector (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStagePassageActor.cpp:1565-1643`). CameraGust and phase-origin settings change *when* a pose occurs, not the geometric set of authored poses (`InfinityStagePassageActor.cpp:1461-1557`).
- **[measured, saved record]** The 8 Oct P01 report contains 48 mechanism records; every parsed record is Slide with 75 cm inward travel and no mechanism risk in that run (`E:/PussStage/Saved/CodexConductor/P01FloorPracticals_20261008/p01_floor_report_APPLY_20261008-212102.json:11961-12203`). This is a recorded run, not live-current proof.
- **[UNCLEAR]** P02–P06 current mechanism-kind distributions, curve extrema, and live modulation maxima were not established by the searched saved Structure/S3/P01 records. A later DRY must read the current Show and refuse to size from enum defaults alone.

### Passage floors

- **[declaration-proven]** Structure stations derive from compiled wings and materialized panels, including asymmetric side distances; they are not a second spacing authority (`Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageStructureActor.h:15-52`). The Structure actor is separate from the Passage actor and owns only its tagged generated components (`InfinityStageStructureActor.h:999-1007`, `:1020-1047`). **[UNCLEAR]** No generic “constant module” slot API was found in the inspected Ground and actor declarations; Ground is the exposed floor layer (`InfinityStageStructureActor.h:114-190`, `:999-1043`).
- **[declaration-proven]** The floor is one Structure-owned board ISM plus groove and understage ISMs, not a shared pre-cut floor asset. Current defaults are 24 cm boards, 5 cm thickness, 8 cm slot width, 150 cm inboard reach, 120 cm cat clearance, and 0.5 cm groove plate (`InfinityStageStructureActor.h:114-188`). `BuildGround` splits board runs at each station and creates three steel pieces per slot (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageStructureActor.cpp:1308-1431`, `:1433-1500`).
- **[declaration-proven]** Boards cast shadows so the understage reads as a dark cut; thin groove pieces and understage slabs do not cast shadows (`InfinityStageStructureActor.cpp:1426-1430`, `:1493-1499`, `:1503-1526`). Preserve that division.
- **[measured, saved readback]** Recorded counts are below. The six reports total 261 stations and 479 generated slots; P03 had ground disabled/no slots, and P05 was one slot short of two per station (`E:/PussStage/Saved/CodexStructure/structure_state.json:2-50`). The theoretical two-side census is 522, only an upper bound until DRY proves which panels actually cross the floor.

| Passage | Recorded stations | Recorded slots | Two-side upper bound | Recorded route / half-span |
|---|---:|---:|---:|---|
| P01 | 48 | 96 | 96 | 28,784 / 970 cm |
| P02 | 23 | 46 | 46 | 13,583 / 820 cm |
| P03 | 21 | 0 | 42 | 10,922 / 720 cm |
| P04 | 21 | 42 | 42 | 10,668 / 970 cm |
| P05 | 93 | 185 | 186 | 46,591 / 470 cm |
| P06 | 55 | 110 | 110 | 27,640 / 970 cm |

**[measured, saved record]** Route lengths and predicted half-spans come from the offline Structure audit (`E:/PussStage/Saved/CodexStructure/structure_audit.json:3-103`). **[UNCLEAR]** Why P05 has 185 rather than 186 slots cannot be proven from that aggregate record; a missing side panel is a plausible inference, not a finding.

### Wing and pole profile

- **[declaration-proven]** V2 production wings are 10 cm deep, so a 2 cm total margin needs a 12 cm opening (`Docs/WingGenerationConventions.md:3-17`). The current 8 cm Structure default is therefore narrower than a V2 full profile.
- **[declaration-proven]** Flat V3 is not simply “10 cm thick”: its board is about 1.8 cm, frame members are about 5×10 cm, and total depth is at most 12 cm. Poles are separate meshes at `Pole_n` sockets and extend below floor top; wide flats receive two (`Docs/FlatV3Spec_2026-09-30.md:82-102`). A conservative 2 cm total margin therefore previews as 14 cm for the maximum V3 assembly profile.
- **[UNCLEAR]** No pole diameter, clamp/bracket envelope, or final V3 pole asset bound is declared in the inspected spec. The later tool must use actual mesh bounds transformed from the pole sockets, and fail closed if a moving pole exists but its profile cannot be read.
- **[measured, saved record]** Legacy P01 Wing 001’s recorded left-side geometry lies near route distance 245 cm and its low collider sections are about 10.7 cm route-deep (`E:/PussStage/Saved/CodexStructure/wing001_footprint.json:15-25`, `:70-108`). This validates the need for profile-based width, but is not a V3 proxy.

### S3 walls and waves

- **[measured, saved readback]** The two lower wall faces are at world y 159001 and 160999; each wall uses `/Engine/BasicShapes/Cube`, while its 1 cm marble inner-face liner is a separate actor and did not mutate wall material slots (`E:/PussStage/Saved/CodexConductor/s3_walls_marble_record.json:37-117`, `:119-204`). This makes a per-copy boolean undesirable and a face-mounted kit independently reversible.
- **[measured, saved readback]** WaveV3 has 12 actors—P1/P2 pieces for six logical layers (`E:/PussStage/Saved/CodexConductor/S3Waves/s3_waves_v3_apply_record.json:4-64`). Thus each side wall receives six crossings, not twelve.
- **[declaration-proven + measured record]** The motion core applies sway, bob and roll to each rigid layer (`E:/PussStage/Saved/CodexConductor/S3Waves/s3_waves_v3_core.py:405-422`). The applied record uses 35–100 cm sway, 4–10 cm bob, up to 0.35° roll, and reports 199.98 cm worst overhang and 6.72 cm skirt lift (`E:/PussStage/Saved/CodexConductor/S3Waves/s3_waves_v3_motion_record.json:174-257`).
- **[measured, saved mesh readbacks]** The twelve imported wave pieces are 12.69–12.85 cm deep; the tallest recorded piece is 285.034 cm (`E:/PussStage/Saved/CodexConductor/S3Waves/s3_waves_v3_import_S3_WaveV3_L1Breakers_P1.json:4-15`, `E:/PussStage/Saved/CodexConductor/S3Waves/s3_waves_v3_import_S3_WaveV3_L6Foam_P2.json:4-21`). A 2 cm total margin yields 14.69–14.85 cm outside slot width before any transform-scale change.

## Footprint mathematics

**[inferred design contract]** For moving assembly mesh set `M`, authored transform `T(q)`, surface plane `P = {x | n·x=d}`, and a thin surface slab `Bε(P)`, compute:

`Swept(M) = union(q in Q) T(q)M`

`Footprint(P) = project_to_P(Swept(M) intersect Bε(P)) minkowski_sum Disc(clearance/2)`

The requested 1–2 cm is **total opening growth**, exposed as an argument; the default study uses 2 cm total. Merge overlapping footprints only when they share the same surface owner. Store the unrounded polygon/AABB plus a stable hash; round only display values.

**[inferred design contract]** `Q` must come from the real side curve extrema and declared modulation envelope, not just `[0,1]`: sample all rich-curve segments and analytic tangent extrema. Slide sweeps the floor section along `InwardWorldDirection`; Trap sweeps it along base-world up; Topple/Turn rotate the full assembly about the cached pivot/axis. Test actual plane intersection—do not create a floor slot merely because a mechanism exists. Playback mode, CameraGust and explicit origin do not enlarge the full-cycle envelope.

**[inferred design contract]** Include card, moving poles and brackets as one assembly. For floor boards, union that swept footprint with today’s outward chariot run, then convert the result to a route-distance interval plus per-side across-route interval; unlike today’s single `SlotWidthCm`, this permits different widths and travel lengths per station without reducing existing clearance. Keep the 120 cm cat corridor as a hard exclusion; if a true swept footprint enters it, DRY reports a safety/design conflict rather than clipping the slot silently.

**[inferred design contract]** For S3, evaluate the actual sequence transform at every frame and at interpolation extrema, transform the static-mesh bounds (or vertices when available), intersect the y=159001/160999 planes, and union P1/P2 only if their same-wall footprints overlap. Use a conservative rectangular trim envelope for version 1; do not mistake rest AABBs for swept wall sections.

## Options

| Option | Geometry / look | Cost and light | Re-author / revert | Verdict |
|---|---|---|---|---|
| A. decal or masked card | **[inferred]** Dark line can hide a seam, but has no real parallax and cannot widen today’s 8 cm floor void. | **[inferred]** Up to 522 floor decals plus 12 wall cards; transparent/decal overdraw and weak contact shadow. | **[inferred]** Easy tag/delete, but risks stacking and z-fighting after re-author. | Reject as primary; retain only as an optional grime pass. |
| B. boolean / baked variants | **[inferred]** Only choice that physically opens the intact S3 wall. | **[inferred]** Unique meshes, asset/package writes, LOD/collision risk, slow booleans; breaks the simple cube/liner precedent. | **[inferred]** Requires source-mesh/asset backups and exact replacement maps. | Reject for first implementation. |
| C+. generated gap + trim kit | **[declaration-proven + inferred]** Floors already provide genuine gaps, steel sides/bottom and understage depth; S3 can use a face kit without modifying the wall. | **[inferred]** Reuses three groove instances per floor slot (upper bound 1,566 pieces) and adds about five pieces × 12 wall slots (60), with no translucent overdraw. | **[inferred]** Deterministic rebuild from current authority; tagged components/actors can be replaced exactly. | Recommend. |

## Recommended representation

### Passage floor

**[inferred]** Extend the future Structure ground planner from `CutsCm[] + global HalfSlotCm` to `FMechanismSlotPlan {CueGuid, Side, route_min/max, across_min/max, profile_cm, clearance_cm, footprint_hash}`. Board lanes stop at each interval; groove bottom and faces fit that interval. Preserve `InfinityStage.Structure` ownership and add `InfinityStage.Structure.MechanismSlots` plus stable CueGuid/Side metadata. No unowned hand dressing is touched.

**[inferred]** Regeneration order is Passage materialize first (it compiles the Show and creates panel refs), Structure materialize second (it reads those stations), then named-package save. Passage materialization is editor-only and replaces validated wing instances before attachments (`InfinityStagePassageActor.cpp:755-824`, `:868-901`); Structure already validates before `ClearStructure`, rebuilds ground, and emits a count marker (`InfinityStageStructureActor.cpp:621-650`, `:720-759`). Slots belong in Structure, not `EvaluateMechanismsInternal` and not the Passage actor.

### S3 wall

**[inferred]** Create one tool-owned ISM/actor set per wall: recessed matte-black backer, four narrow blackened-steel edge strips per footprint, optional dirt card disabled by default. Place against the marble liner’s inner face with a Gary-controlled proud offset. The wall and liner remain intact, so their existing occlusion and packages are not rebuilt. Owner tags: `S3.MechanismSlots.ToolOwned`, `S3.MechanismSlots.Left|Right`, and stable layer id.

## Later guarded tool contract (not implemented here)

**[inferred design contract]** A future project-Python conductor at `Saved/CodexConductor/p37_mechanism_slots.py`, paired with the necessary reviewed Structure implementation, must implement:

1. **DRY** — exact current dirty-package census; compile/read current Show; census Passage actors, Structure actors, mechanism curves, materialized panel refs, pole assets, S3 wall/liner/wave actors and sequence bindings; compute footprints, hashes, counts, conflicts and two preview images. Write only `Saved/CodexConductor/P37Slots/<run>/`. Refuse missing authority, missing bounds, non-finite curves/scales, cat-corridor intrusion, unexpected wall transforms, or unrelated dirty packages.
2. **APPLY** — require exact confirmation `APPLY P37_SLOTS <run_id>` matching an unchanged DRY hash. Before mutation, copy every affected on-disk package to `Backups/PreMechanismSlots-<timestamp>/` and record paths/hashes. Recompute and compare the dirty census; replace only tagged prior output; materialize each named Passage then its paired Structure; build S3 kits; save only the exact affected actor/map packages. Never `Save All` and never modify the Show for derived geometry.
3. **Read-back** — reload/read current objects; prove owner tags, per-Cue/layer footprint hashes, transforms, instance counts, materials, shadow flags, package saves and zero unexpected dirtiness. Require both existing `INFINITY_STAGE_MATERIALIZE_OK` / `INFINITY_STAGE_STRUCTURE_OK` markers and `P37_SLOTS_APPLY_OK run=<id> floor_slots=<n> wall_slots=<n>`.
4. **REVERT** — require `REVERT P37_SLOTS <applied_run_id>`; verify the recorded post-apply hashes, remove only matching tool-owned outputs, restore exact recorded packages from the backup, reload, re-census and emit `P37_SLOTS_REVERT_OK`. Refuse hash drift instead of overwriting later work.

**[inferred design contract]** The future offline harness must include positive controls for asymmetric P01 placement, Slide, sinking/rising Trap, Topple, Turn, curve overshoot, two poles, S3 six-per-wall grouping and idempotent rerun; negative controls for missing pole mesh, unbounded modulation, cat-corridor intrusion, stale DRY hash, unrelated dirty package, transformed S3 wall, ownership collision and REVERT-after-drift. No such tool or harness exists in this P41 plan deliverable.

## Offline visual studies

- [Passage 01 top-down slot study](P41_MECHANISM_SLOTS_PASSAGE_MOCKUP.svg) — **[measured + inferred]** Uses P01’s recorded 970 cm floor half-span and source-declared asymmetric wing lines (-750/+500), with the recorded 75 cm Slide travel; the 14 cm V3 opening and styling are proposed (`E:/PussStage/Saved/CodexStructure/structure_audit.json:3-18`, `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageStructureActor.h:44-52`, P01 report cited above).
- [S3 wall elevation](P41_MECHANISM_SLOTS_S3_WALL_MOCKUP.svg) — **[measured + inferred]** Six crossings and the 12.69–12.85 cm mesh-depth range are measured from saved records; trim, backer and 2 cm total margin are proposed. Heights in the drawing are comparative rest-envelope studies, not final swept apertures.

## Acceptance boundaries

- **[inferred]** Source/build acceptance: reviewed Structure change and guarded script/harness pass. Saved/read-back acceptance: exact tags, hashes, counts, transforms and named-package census survive reload. Runtime acceptance: mechanisms complete their full authored envelope without mesh/surface overlap. Rendered acceptance: camera-height and grazing-angle captures show a dark physical recess, coherent contact shadow, no z-fighting/light leak, and no cat-corridor opening. Package/delivery acceptance: backup, record, affected-package list and log markers are delivered separately. None is satisfied by this plan or by headless/transport success alone.

## Questions for Gary before implementation

1. **[UNCLEAR]** Clearance: 1 cm total, 2 cm total (preview default), or 1–2 cm on *each* side?
2. **[UNCLEAR]** Finish: reuse each Passage’s current groove material, standard blackened steel, or paint the lip to the floor/wall?
3. **[UNCLEAR]** Should S3 remain an apparent slit (recommended first pass), or must the marble wall be physically open when seen obliquely?
4. **[UNCLEAR]** Rollout: P01 pilot first, S3 first, or a different Passage? P03 currently has no generated ground slots in the saved readback.
5. **[UNCLEAR]** What is the approved V3 pole/clamp outer profile, and should a two-pole flat create two narrow tracks or one combined slot?
