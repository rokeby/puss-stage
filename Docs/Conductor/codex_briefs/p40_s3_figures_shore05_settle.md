# P40 — S3 figures: place Shore05 (+ up to 5 variants), settle the hessian cloth, MetaHuman underwear = cloth colour (Codex, offline)

Read `_house_rules.md`. Offline only (no Unreal, no Blender); the conductor runs editor steps after the bake.

## Gary, 9 Oct (his words)
"Sure, [Shore]05 can indeed be placed on a level. We can place five of those as well, perhaps. It's good to have variation
… they're going to be rendered out as a video. However, we need to make sure that the new Hessian cloths and metahuman
clothes in the same color as the cloths are settled so that we don't get as much visual disruption from when they have a
glitch."  Earlier (8 Oct, S3-7): MetaHumans "as naked as possible, wearing loincloth-coloured underwear"; cloth heavy, not
stiff, pinned at the back of the head / top of the back so it doesn't flip off.

## Known facts (re-verify)
- [measured 9 Oct SHORELABELS] level has Shore01_M56, 02_F52, 03_M59, 04_F55, 06_F25 "<name> Clam" (BP_<name>_Draped_C);
  Shore05_M53 BP exists (/Game/Metahuman/ShoreCast_20260910/SceneCharacters/BP_Shore05_M53_Draped) but is not placed.
- Shroud hessian applied 9 Oct (SHAPPLY2, `Saved/CodexConductor/ShroudHessian_20261008/`): 6 MIs MI_Shroud_Hessian_03..08,
  BP template cloth component "ShoreHeadCloth" (template name ShoreHeadCloth_GEN_VARIABLE), seeded assignment.
- Crowd motion tools (LS_Clams): s3_crowd_motion/loops_v2/feet/regather/late records; loops v2 is the calm forward-only
  set (cloth whip fix). Figures 15–20 placed by Gary + clones; read `s3_crowd_*` records.
- Outfit: P1MetaFabric `p1_metahuman_outfit.py` failed RESOLVED_READBACK 8 Oct (darker shorts) — find why from its code.

## Build
1. **Place Shore05** DRY/APPLY/REVERT: one placed instance (label "Shore05_M53 Clam") at a free spot in the crowd area,
   + optional `extra_count` (default 0, max 5) further Shore-figure instances drawn from all six BPs for variation,
   positions from a seeded free-spot planner (single draw per value) that keeps the camera B-shots' sight lines (read the
   S3 camera keys) and the dune surface (feet on the surface, reuse the s3_crowd_feet method). Give each a crowd motion
   chain via the existing loops-v2 method (forward-only crossfades). Shroud MI via the SHAPPLY2 seeded assignment.
2. **Cloth settle**: cloth must start SETTLED: a pre-roll (warm-up) so the cloth reaches rest before the first visible
   frame of S3 and after every transport jump — find the Chaos cloth component settings available in 5.8 Python
   (teleport/reset behaviour, warm-up / "PreRoll"-like options); document what is binary/declaration-proven vs inferred;
   prefer a settings change on the BP template over sequence keys. Include the back-of-head/top-of-back pinning if a
   per-vertex max-distance / kinematic mask is reachable; else report what is needed (Blender — only after the bake).
3. **MetaHuman underwear = cloth colour**: diagnose the 8 Oct RESOLVED_READBACK failure, then a DRY/APPLY that sets the
   MetaHuman underwear/shorts material colour to the hessian base colour (sample MI_Shroud_Hessian_* WeaveTint × the
   desaturated weave texture mean; record the numbers), new MI children only, never edit existing masters.
4. Harness with +/- controls per tool; tiered report; stills plan (which S3 seconds to check).
Deliver in your worktree; the conductor reviews and commits.
