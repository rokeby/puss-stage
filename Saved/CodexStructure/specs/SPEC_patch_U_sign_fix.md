# Spec: fix the Topple SIGN reference in HELD PATCH U (review follow-up)

Regenerate `Scripts/patches/2026-09-30_U_mechanism_kinds.patch` in place:
1. apply it at HEAD with `--ignore-whitespace`;
2. fix;
3. re-diff (CRLF);
4. restore the sources.
Don't build or run Unreal.

## Facts (declaration-proven, read them yourself)
- `ResolvePanelFacing` (`InfinityStagePassageActor.cpp` ~96–130) is identity or 180° about Up (plus the placement
  adjustment). So a wing's local axes stay aligned with the PAIR frame.
- Production wings (`Docs/WingGenerationConventions.md`, V2 profile): X = thickness, i.e. the face normal, pointing
  ALONG the route toward or away from the camera; Y = width, ACROSS the corridor; Z = up.
- Side panels slide along pair ±Y (`GetPairLocalInwardDirection` ~136), i.e. along their WIDTH.
- TOPPLE = falling flat about the base edge, which runs along the WIDTH (Y). The card falls along ±X: toward or away
  from the CAMERA. That's the asset contract (`Docs/FlatV3Spec_2026-09-30.md`: Hinge +X along the base edge; "fall
  direction (toward or away from camera) is a mechanism parameter").
- So the socketless fallback choosing the LARGER horizontal extent (Y for production cards) as the hinge axis is
  CORRECT. KEEP IT.

## The bug
The materialize-time sign check uses `dot(cross(AxisWorld, Up), InwardWorldDirection)`.
- For production cards the fall direction (along X / the route) is PERPENDICULAR to inward (across / pair Y), so the
  dot product is ~0 and the sign is arbitrary.
- The current tests use an equal-sided cube, which hides this.

## Fix
- Define: a POSITIVE `MaxAngleDeg` topples the card TOWARD THE CAMERA, i.e. downstage, opposite the route's forward
  direction (the pair frame's −X in world). Negative topples it away.
- Compute the reference at materialize from the PAIR transform's forward vector (`GetCuePlacementTransforms` /
  `PairWorld.GetRotation().GetForwardVector()`, whichever the ref-building code already has).
- The sign check becomes `dot(cross(AxisWorld, Up), -PairForwardWorld) < 0 → flip the axis`. Keep using the SCALED
  axis, as now.
- If `|cross(AxisWorld, Up) · PairForward| < 0.1` (a degenerate card, for example a hinge axis along the route), warn
  once and keep the socket's own axis sign.
- TOP panels: Topple and Turn don't apply. They keep their existing Slide behaviour (document it at the enum). Trap
  still applies.
- Update the `MaxAngleDeg` tooltip and comments to "positive = toward the camera (downstage)".

## Tests (production proportions, so the bug is visible)
Use a fixture with a thin X, a wide Y and a tall Z (for example a mesh scaled or built 10 × 400 × 1000 cm, or the
existing cube with base scale (0.1, 4, 10)), on a LEFT and on a RIGHT side panel (the right one with the 180° facing).
- Socketless fallback: the hinge axis is the width (Y) direction.
- `MaxAngleDeg` +90 at progress 1: the card's top point moves toward the camera (world −route-forward) by ≈ its height
  (±1 cm), on BOTH sides.
- −90 moves it away.
- **Negative control:** with the OLD inward-based reference, the same fixture's sign dot product is ~0. Assert
  `|dot| < 1e-3`, which shows the old check was degenerate.
- Top panel with Kind Topple: identical to Slide.
- All of U's existing tests (mirror, non-uniform, θ=0, continuity, Slide regression) still pass.

Final message: the patch path; apply checks (alone, and with C); what changed; what you couldn't verify.
