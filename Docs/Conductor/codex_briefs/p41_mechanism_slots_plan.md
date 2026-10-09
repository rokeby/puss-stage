# P41 — Mechanism SLOTS where moving wings/waves pass through floors and walls (Codex, offline PLAN only)

Read `_house_rules.md` first; every rule applies. **This is a plan/design job: no tool is required, no C++ edits,
no Content writes.** Low priority ("deeply a nice to have", Gary 9 Oct).

## What Gary wants
Wherever a moving piece passes through a surface, the audience should see a **slot** in that surface, about
1-2 cm wider than the pole or the wing's full profile thickness, instead of the piece simply clipping through it.
Moving pieces include:
- Passage wings whose mechanisms run **through the floor** (rising/sinking, inward travel);
- the S3 **waves** that slide in and out of the side walls.

It should be **procedural**: something that runs once, ideally during staging/materialization, for all mechanisms,
rather than hand-placed per wing.

## Investigate (cite file:line, proof tiers)
1. **How pieces move.** Mechanism types and their motion paths:
   - `InfinityStageTypes.h` mechanism structs: PlaybackMode, InwardTravelCm, CameraGust, ExplicitOriginFrame;
   - `InfinityStagePassageActor.cpp` EvaluateMechanismsInternal (~:1300-1560): ISM instance transforms per panel.
   Which pieces cross a floor or wall plane, and the swept volume over a full cycle (min/max travel, any rotation).
2. **What the surfaces are.**
   - Passage floors: Structure actor modules and constant modules (`InfinityStageStructureActor.h`, memory
     "stations-only layers, constant modules").
   - S3: marble side walls and the waves (`Saved/CodexConductor/S3*`, WaveV3 t5o tools; inner wall faces at world
     y 159001 / 160999 per `Saved/CodexConductor/s3_drama_lights.py:39`).
   - Are floors per-Passage meshes, ISMs, or a shared floor? Are they instanced, so that one cut would hit every
     copy?
3. **Wing/pole geometry.** Profile thickness per wing (Flat V3 is 10 cm per `Docs/FlatV3Spec_2026-09-30.md`; V2
   wings per `Docs/WingGenerationConventions.md`), and poles/brackets if any.
4. **When materialization runs** (Passage Actor materialize path), and whether a once-per-materialize step can add
   components safely. Respect: "Show is the authority; materialize each affected Passage actor; save only affected
   packages".

## Design options to compare (recommend one)
- **A. Slot decals:** a dark slot plus bevel-lip decal, or a masked trim mesh, laid on the surface along each swept
  footprint. No geometry cut. Cheapest; reads well from the camera height.
- **B. Real cut-outs:** a GeometryScript boolean at materialize time on non-instanced floor/wall pieces, or
  pre-baked slotted variants. Expensive, and risky with instancing and LODs.
- **C. Slot trim kit:** small modular "slot plate" meshes (dark gap, steel edge) spawned as ISMs per footprint,
  sitting a few mm proud of the surface. Middle cost; the most "theatre stage trap" look.

For each option, cover:
- how footprints are computed (swept profile ∩ surface plane, + 1-2 cm margin);
- per-Passage counts (estimate from the Show/records you can read);
- performance;
- interaction with lighting and shadows;
- what happens when a wing is re-authored (regenerate = idempotent, tagged ownership);
- REVERT.

## Deliverable
`Docs/Conductor/P41_MECHANISM_SLOTS_PLAN.md`:
- findings with proof tiers;
- the footprint maths;
- the recommended option and its later tool contract (DRY/APPLY/REVERT, tagged ownership, census, read-back);
- an offline mock-up image of one Passage's floor with slots, from a top-down plan computed from the Show data you
  can read offline (if any), plus one S3 wall elevation;
- open questions for Gary (slot look, lip/edge material, which Passages first).
