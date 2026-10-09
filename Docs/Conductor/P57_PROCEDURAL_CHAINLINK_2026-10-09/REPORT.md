# P57 procedural woven chain-link — offline handoff

Scope: pure Python/NumPy/Pillow only. Unreal, MCP, PIE, Blender, FBX export, and
Show writes were not run.

## Delivered

- **declaration-proven:** `chainlink_weave.py` defines a 3.36 × 3.02676 m bay,
  25 cm diamond, 8 mm wire, four tube sides, low crimp sampling, seed 5709,
  bounded bend/lean/slack/break parameters, and a 20,000-triangle refusal gate
  (`Saved/CodexFlatV3/chainlink/chainlink_weave.py:32-62`).
- **declaration-proven:** each picket is one continuous crimped zig-zag until an
  explicitly selected break; adjacent pickets share projected knuckle nodes and
  alternate ±depth, with curled top/bottom selvage (`chainlink_weave.py:124-192`).
  Every authored random scalar goes through the counted one-scalar RNG
  (`chainlink_weave.py:77-88`).
- **declaration-proven:** LOD0 is the woven tube mesh, LOD1 is a coarser woven
  tube mesh, and LOD2 is a two-triangle masked card with shadow casting disabled
  (`chainlink_weave.py:204-220`).
- **declaration-proven:** the thin post-bake Blender adapter imports `bpy` only
  inside its function and emits zero-subdivision poly curves; Blender was not
  launched (`chainlink_weave.py:374-412`).
- **declaration-proven:** the P02 dispatcher accepts `chainlink: "weave"`; an
  absent, `off`, or `legacy` option calls the supplied legacy builder verbatim
  (`chainlink_weave.py:258-271`). The exact insertion boundary for the maintained
  main-tree P02 source is documented without duplicating that builder
  (`Saved/CodexFlatV3/chainlink/P02_INTEGRATION.md:1-27`).

## Offline measurements

- **measured:** run `P57-20261009-03` produced LOD0 5,448 triangles, LOD1 1,120,
  and LOD2 2. LOD0 is 14,552 triangles under budget
  (`Saved/CodexFlatV3/chainlink/chainlink_weave_record.json:1-25`).
- **measured:** the default has 13 pickets, one slack wire, one broken wire, and
  402 individually counted scalar RNG draws; its deterministic SHA-256 geometry
  digest is recorded (`chainlink_weave_record.json:25-30`).
- **measured:** 150 projected knuckles passed; minimum over/under separation is
  22 mm against a 14.4 mm requirement; zero bad knuckles and zero non-knuckle
  intersections were found (`chainlink_weave_record.json:30-38`).
- **measured:** guarded APPLY backed up prior generated outputs, wrote only the
  named offline files, recorded an empty Unreal dirty-package census, then read
  both PNGs back by byte size and SHA-256 (`chainlink_weave_record.json:39-55`).
- **measured:** preview inspection shows the raking silhouette contains repeated
  diamond cells with small over/under offsets rather than a single perfect X
  grid. The plan preview exposes depth changes and the broken picket
  (`Saved/CodexFlatV3/chainlink/previews/chainlink_raking_shadow.png`;
  `Saved/CodexFlatV3/chainlink/previews/chainlink_topdown.png`).
- **measured:** the offline harness passes 10/10: six positive and four negative
  controls. Positives cover interlock topology, seed determinism, LOD budget,
  draw accounting, legacy identity, and weave routing; negatives cover budget
  refusal, invalid options, missing confirmation, and invalid tube sides
  (`Saved/CodexFlatV3/chainlink/test_chainlink_weave.py:16-86`;
  `Saved/CodexFlatV3/chainlink/offline_harness_report.json:1-8`).

## Look and runtime recommendations

- **inferred:** at show distance, the existing 25 cm opening should remain
  legible as scenic chain-link and cast readable diamonds; it is deliberately
  oversized versus a common real 5–10 cm opening. Expose `diamond_m` for Gary:
  reducing toward real scale multiplies both aliasing risk and triangle cost.
- **inferred:** keep Nanite **off initially** for this 5.4k-triangle bay. Thin,
  repeated tubes are an aliasing/cluster edge case, and the ordinary LOD chain
  is already cheap. Profile a representative long run before changing that.
- **inferred:** VSM cost will be driven more by hundreds of thin moving-light
  shadow edges than by raw triangles. LOD2 therefore disables cast shadows;
  retain LOD0/1 shadows only for near and raking-light hero bays, and test the
  car drive-by before enabling the wall run globally.
- **inferred:** the industrial material coordinate is reused rather than
  duplicated (`chainlink_weave.py:28,326`). The Wing V2 10 cm slab rule is not
  applicable to tubular wire; the surrounding P02 asset still keeps its
  Front/Flap/Timber/Edge, handedness, UV, socket, and clean re-import contracts.

## Unproved / conductor boundary

- **UNCLEAR:** no Blender mesh, FBX, material-slot read-back, Unreal import,
  Nanite/VSM profile, TSR/moiré test, rendered show-distance acceptance, or
  package save exists. Those require the later bake/editor gates.
- **UNCLEAR:** the maintained P02 builder lives in the main `E:/PussStage`
  DerivedAssets tree, outside this worktree. This delivery provides and tests
  the option seam but does not mutate that main-tree file. The conductor must
  make the narrow insertion described in `P02_INTEGRATION.md` after the bake;
  default-off identity is already measured by the harness.

## Run order

1. `python Saved/CodexFlatV3/chainlink/run_harness.py`
2. `python Saved/CodexFlatV3/chainlink/chainlink_weave.py --mode DRY`
3. Review the DRY JSON, then regenerate previews only with:
   `python Saved/CodexFlatV3/chainlink/chainlink_weave.py --mode APPLY --confirm "APPLY P57 CHAINLINK" --run-id <unique-run>`
4. After the bake releases, follow `P02_INTEGRATION.md`, run Blender headless,
   enforce the existing P02 FBX gates, then run Unreal DRY/read-back in a granted
   slot. Do not infer visual acceptance from the offline harness.

Commit: intentionally not created; the brief assigns the commit to the conductor.
