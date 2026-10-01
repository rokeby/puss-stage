# Spec: fix HELD PATCH U for scaled and mirrored wing instances (review finding)

Regenerate `Scripts/patches/2026-09-30_U_mechanism_kinds.patch` in place:
1. apply it at HEAD in your worktree with `--ignore-whitespace`;
2. fix;
3. re-diff (CRLF) back to the same file;
4. restore the sources.
Don't build or run Unreal.

## The bug (declaration-proven)
Wing instance transforms carry SCALE, including MIRRORS:
- `InfinityStagePassageActor.cpp` ~1026–1030: `ImageTransform = (1,-1,1)` when `bFlipImageHorizontally`, then
  `* FacingTransform * Panel.LocalTransform * ...`;
- `PlacementAdjustment` scale ~118, which may be non-uniform or mirrored.

U computes `NewWorld = [T(-p) · R(axis, θ) · T(p)] * Base` in the mesh's UNSCALED local space, then lets Base apply the
scale. So:
- a mirrored card ((1,−1,1)) rotates the opposite way: it topples AWAY from the route while unmirrored cards fall
  toward it. The materialize-time sign check uses `TransformVectorNoScale` and so can't see the mirror.
- a non-uniformly scaled card SHEARS during the topple or turn, because a rigid rotation before a non-uniform scale is
  not rigid.

## Fix
Rotate in the SCALED frame. Split Base into its scale `S = Base.GetScale3D()` and its rigid part
`RB = FTransform(Base.GetRotation(), Base.GetTranslation())`. With `p_s = p * S` (component-wise) and
`a_s = (axis * S).GetSafeNormal()`:

    NewWorld = FTransform(Identity, 0, S) * T(-p_s) * FTransform(FQuat(a_s, θ)) * T(p_s) * RB

- After the first factor every factor is unit-scale, so FTransform can represent the product (scale, then rigid).
- At θ = 0 this must equal Base exactly (test it).
- Make the Topple sign check at materialize use the SCALED axis, `RB.GetRotation().RotateVector(a_s)`, so a positive
  angle falls toward the route for mirrored and unmirrored cards alike.

## Tests (add to U's tests)
- **Mirror:** a base with scale (1,−1,1), Topple +90. The top point falls toward the route, in the same world direction
  as the unmirrored case.
- **Non-uniform:** a base with scale (2,1,0.5), Topple 45° and Turn 90°. The transformed card stays rigid:
  - the world distance between two mesh-local points equals their distance after scaling alone, within 0.01;
  - the pivot is invariant.
- **θ = 0:** for both scaled cases the result equals Base (±1e-4).
- All of U's existing tests still pass.

Final message: the patch path; apply checks (alone, and with C); what changed; what you couldn't verify.
