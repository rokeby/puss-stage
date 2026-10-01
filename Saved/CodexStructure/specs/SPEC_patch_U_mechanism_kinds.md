# Spec: HELD PATCH U: wing mechanism kinds Slide / Topple / Turn / Trap

Output: `Scripts/patches/2026-09-30_U_mechanism_kinds.patch`, a `git diff` against HEAD (CRLF, like the other held
patches).
- Must apply with `git apply --ignore-whitespace`, alone and together with
  `Scripts/patches/2026-09-30_C_celestial_write_only_on_change.patch`.
- Leave the source tree UNCHANGED (only the patch file is new).
- Don't build or run Unreal.

## Why
Gary approved three new wing moves for the Flat V3 wings:
- TOPPLE: the card falls flat about its base hinge (P05's ending);
- TURN: a periaktos pivot about a vertical centre axis, revealing the timber back;
- TRAP: rising or sinking through the floor slots.

Today (declaration) each panel's motion is one normalised curve applied as a TRANSLATION along a fixed inward direction
× `InwardTravelCm`:
- `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStagePassageActor.cpp` ~1352–1375;
- the struct `FInfinityMechanismMotion` in `Public/InfinityStageTypes.h` ~612–660.

The result is a full per-instance `FTransform`, batched with its previous transform (~1418).

## Asset contract (agreed with Wings & Textures, `Docs/FlatV3Spec_2026-09-30.md`)
- Socket **"Hinge"**: at the card's lowest point on the pole-line plane. Socket +X runs along the base edge and is the
  TOPPLE axis.
- Socket **"Pivot"**: on the vertical centre axis. Socket +X points UP; it's the TURN axis.
- No socket: fall back to the mesh bounds.
  - Topple: bottom-centre of the bounds, with the axis along the longer horizontal bounds extent.
  - Turn: bounds centre (x, y), with the axis = local +Z.
- Poles are separate meshes in V3. Pole instancing is OUT OF SCOPE here (a later patch, once the V3 assets exist).

## Changes
1. `FInfinityMechanismMotion` (Types.h): add
   - `EInfinityMechanismKind Kind = Slide` (UENUM: Slide, Topple, Turn, Trap; default Slide, so existing content is
     byte-for-byte unchanged);
   - `double MaxAngleDeg = 90.0`, used by Topple and Turn. Its sign sets the direction. For Topple, a positive angle
     falls toward the panel's inward direction (toward the route).
   - Trap travels along the panel's world UP axis (the base rotation's Z) by curve × `InwardTravelCm`: positive rises,
     negative sinks. No new axis field is needed beyond `Kind`; document that in the header.
   - Tooltips on every new field.
2. At materialize, where the mechanism instance refs are built, store a per-panel LOCAL pivot transform:
   - from `UStaticMesh::FindSocket("Hinge")` for Topple, `FindSocket("Pivot")` for Turn;
   - else the bounds fallback above.
   - Keep it in the existing ref struct, cheap per frame. Don't do a per-frame socket lookup.
3. Evaluation, for each kind:
   - Slide: unchanged.
   - Trap: Base + UpWorld × progress × travel.
   - Topple / Turn: local rotation about the pivot, `R = T(pivot) · Rot(axis, progress × MaxAngleDeg × modulation scale)
     · T(−pivot)`, applied in the instance's local space, then `Base`. Watch FTransform's multiplication order (A*B
     applies A then B); prove it in the test.
   - The previous transform is still read from the instance, so continuity and velocity work as today.
   - `WingModulation.InwardTravelScale` scales the travel for Slide/Trap and the ANGLE for Topple/Turn.
4. Everything still goes through the same `BatchUpdateInstancesTransforms` path, so it composes with the
   `InfinityStage.Mechanism.MarkRenderStateDirty` cvar (Q). Don't touch the render-state code.

## Tests (`InfinityStageTests`, same style as the existing mechanism tests in `InfinityStageCompilerTests.cpp`)
- **Slide regression:** the existing undulation test still passes unchanged (default Kind = Slide).
- **Topple:** with a known hinge at the card's base and MaxAngle 90, progress 1:
  - a point at the card's top (height h) ends at height ≈ 0 (±0.1 cm), displaced by ≈ h along the fall direction;
  - progress 0 equals the base transform;
  - −90 falls the other way.
- **Turn:** progress 1 with MaxAngle 180 about the centre axis maps the front face normal to −normal, and the pivot
  point is invariant.
- **Trap:** progress +0.5 with travel 100 raises the instance 50 cm along up; −0.5 sinks it 50.
- **Socket vs fallback:** a mesh with a "Hinge" socket uses it; without one, the bounds fallback is used.
  - If building a test mesh with a socket is impractical, unit-test the pivot-maths function with an explicit pivot,
    and say what wasn't covered.
- **Continuity:** evaluating frame A then frame B, the previous transform recorded for B equals the new transform at A
  (±0.01).

## Traps
- Default MUST stay Slide everywhere: no change for any existing cue.
- Rotation about the pivot, NOT about the actor origin: get the order right and test it.
- Don't widen the per-frame cost: the pivot is cached at materialize.
- Comment the sign conventions at the declarations.

Final message:
- the patch path;
- the apply checks (alone, and with C);
- the test list;
- what you couldn't verify.
