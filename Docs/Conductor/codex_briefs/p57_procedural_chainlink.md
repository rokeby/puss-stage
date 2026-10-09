# P57 — Procedural woven chain-link fence (Codex, offline; Blender build runs after the bake)

Read `_house_rules.md`. Offline only now (no Unreal; Blender only AFTER the ragged rebake — script may be written and
unit-tested with pure Python/numpy). Dedupe: EXTENDS existing work, do not start over:
- P02 industrial builder `` (real wire diamonds ~25 cm, FenceTarp/FenceOpen/RollerShutter, barbed coil, poles;
  `P02Industrial/REPORT.md`), and the 5 Oct backlog `Docs/FlatV3Status.md:287-292` (Gary: "the big X grid is too
  perfect … actually create the interlinked wire structure in 3D … good detail for reflection and shadow"; first
  guess 100–200k tris/bay is too heavy).
- `Docs/Conductor/OUTER_WALL_FENCE_FITNESS_2026-10-03.md` (moiré, triangle cost, shadow actor for the car drive-by).
- W&T Q3 finding: the P02 IND fence faces use 64×64 placeholder textures; W&T is authoring M_Wing_IndustrialTiling_Master
  (galvanised/zinc CC0) — use that material path, coordinate, don't duplicate.

## Gary 9 Oct
"a more realistic chainlink fence … doesn't need to be a tonne of vertices, just a more convincing cross of wires than our
current, non-mesh one". Rodin is unsuitable (thin repeating lattice); build it procedurally.

## Build
1. `chainlink_weave.py` (pure numpy core + thin Blender/FBX wrapper): real chain-link topology — each picket is a crimped
   zig-zag wire that interlocks with its neighbours (over/under at every knuckle), knuckled top/bottom selvage. Params:
   diamond size (default from the existing ~25 cm, report what reads at show distance vs a real 5–6 cm), wire Ø, tube
   sides (4–6), crimp samples per diamond (low), seeded irregularity (small bends, a few slack/broken wires; ONE draw
   per value), panel width/height to the existing FenceBay sizes.
2. Budget: target ≤ 20k tris per 336 cm bay at LOD0 with LOD1/2 (or a masked-card LOD at distance); report the
   exact counts, Nanite on/off recommendation, and VSM shadow-cost notes [inferred where not measured].
3. Shadow test offline: render a top-down + raking-light silhouette PNG (numpy rasteriser is fine) showing the diamond
   shadow is a woven mesh, not a perfect X grid.
4. Integrate as an option into the P02 builder (args `chainlink: "weave"`), keeping the current output bit-identical when
   the option is off; FBX export spec per Docs/WingGenerationConventions / V2 thickness rules where they apply.
5. Harness +/- (interlock: no two pickets intersect except at knuckles; tri budget refuses overruns; option off =
   unchanged output; seed determinism). Tiered report. Deliver in your worktree; the conductor commits.
