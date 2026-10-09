# P38 — S3: ground the fire shadows on the dune, +50 % handprints on the camera wall, the rising-rig lid, the 0:04 spoiler (Codex, offline)

Read `_house_rules.md` first; every rule applies. Offline only (no Unreal, no Blender). The conductor runs editor steps.

## Gary, 9 Oct (his words, conductor session)
1. **Dune shadows**: "the current fires in S03 cast shadows by the figures, but they float in the air on the wall,
   suggesting that the dune landscape that they are standing on is not casting shadows and must cast shadows."
   Fire shadows stay ON (Gary 8 Oct: "that's a key visual").
2. **Handprints**: layout as is, plus "50% more handprints on the wall in the area where the camera track is, which is
   basically on the right hand wall if you are the audience in their usual place above the dunes. You can reuse handprints."
3. **F20 lid**: the rig that comes up in S3 "lacks a lid … The lid should be shut … always be on the ceiling. So when we see
   the box come up, we're consumed by its darkness."
4. **0:04 spoiler**: P03's score lights are still visible at the S3 cut (~0:04 into S3) — switch them off at the cut.

## Known facts (cite and re-verify; do not trust blindly)
- [measured 9 Oct S3POLISH-DRY-4] the dune "RigAtmos.S3ShoreGround" StaticMeshActor has cast_shadow=True,
  cast_dynamic_shadow=True (report `Saved/CodexConductor/S3Polish_20261009/s3_polish_dry_S3POLISH-DRY-4.json`, plan.dune_shadow).
  So the fault is NOT the flag. Candidates [inferred]: fire light origin below/inside the dune surface; dune mesh
  single-sided or normals facing down so it neither occludes nor receives; dune NO_COLLISION irrelevant; light
  shadow bias/contact-shadow/`ShadowSlopeBias`; the figures' feet above the dune (S3 crowd feet tool) so shadows
  detach; VSM page budget. Dune built by `Saved/CodexConductor/S3Shore/s3_shore_ground_ue.py`.
- Fires: `s3_fires.py`, `s3_fire_look.py`, fire lights "S3 Fire B Light", "S3 Fire C Light" (A off), polish record
  `S3Polish_20261009/s3_polish_record.json`.
- Handprints: grease prints placed 8 Oct (HP_TINT_PLACE_SUCCESS run 20261008-020151, 1034 twins; revert request
  `hp_grease_tint_revert_request.json`); find the placement tool + record and reuse its asset set.
- Rig/hangar: `Saved/CodexConductor/*hangar*` + ARRMOV (Arrival roof hinge + lattice movers, 8 Oct).

## Build
A. **Read-only probe** (`s3_ground_probe.py`): for each fire light: world location vs the dune surface height under it
   (line trace or mesh bounds), light shadow settings; dune mesh: two-sided flag of its material, normal direction
   sample, cast/receive flags, mobility; each figure's lowest foot bone vs the dune surface. Output JSON + a verdict
   ranking the candidates with tiers. Must be able to say UNCLEAR.
B. **Fix tool** DRY/APPLY/REVERT for whichever candidate the probe proves (parameterised: light z lift, material
   two-sided via a NEW MI child only, shadow bias), record + backup, targeted save.
C. **Handprints +50 %**: planner that finds the camera-facing right wall (audience view = audience-right; DERIVE the side
   from the S3 camera track poses, do not assume UE ±Y), counts current prints on it, adds +50 % reusing existing print
   assets/MIs, same placement rules as the 8 Oct tool, seeded (single draw per value). DRY emits a top-down PNG.
D. **F20 lid**: probe the S3 hangar roof/lid state across the rise (keys, Arrival movers, visibility), then a DRY/APPLY
   that keeps the lid shut on the ceiling throughout the rise; report the smoke actors visible through the gap.
E. **0:04 spoiler**: find P03 score lights evaluating at the S3 cut; DRY/APPLY visibility (bHidden-bound tracks, rule 9)
   or intensity-zero at the cut, owned + recorded.
Harness with +/- controls per tool. Deliver in your worktree; report with tiers; the conductor commits.
