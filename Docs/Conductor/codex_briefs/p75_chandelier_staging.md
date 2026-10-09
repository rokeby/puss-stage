# P75 — Chandelier staging: opening shadow + P06 silent swing (Codex, offline; live runs by the conductor)

Read `_house_rules.md` (+ known traps: str(FGuid) changes per call; channel names carry suffixes; BP subobject lists
repeat components). Offline only. DEDUPE — reuse, don't rebuild:
- Mesh: Hyper3D Iron 3, `DerivedAssets/ChandelierBuild/Output/Iron3/` (SM_Chandelier_Iron3.fbx with 44 SOCKET_Candle_*
  at the wick tips + ChainAttach; SM_Chandelier_Iron3_Chain.fbx; chandelier_Iron3_chain.json `chandelier_chain_v1`,
  24 links, 300 cm; mass 1665 kg INFERRED/high placeholder). Aging = Hyper3D job 55 (gilt/iron MIs).
- Candles: job 56 `Saved/CodexConductor/P56ChandelierCandles_20261009/` (BP_Effect_ChandelierCandle, NS_Stylish_Fire_1,
  no light, no auto-activate; runs only after the socket JSON exists).
- Swing: job 52 `P52PendulumSwing_20261009/` (motion-driven pendulum keys, REBUILD) + 52b `P52BChainPendulum_20261009/`
  (chain + rigid body) + held cue-kick patch `Scripts/patches/2026-10-09_sway_kick.patch`.
- Prelude light plan (Hyper3D, Blender look-test, Opening frame cm, curtain line x=0): DRIVE-BY spot (−4200,−900,850) →
  (−200,+250,800), cone 34°, warm (1.0,0.9,0.75), soft 0.15; motion: target sweeps y +1200 → −1200 over ~3 s, ease,
  intensity 0→peak→0, ONE pass. MOON spot (−700,+3000,1600) → (−250,−300,550), cone 55°, cool (0.62,0.74,1.0). Idea:
  real chandelier hidden in game (Visible off) but Cast Hidden Shadow ON so only its shadow shows.

## Gary, 9 Oct (his words)
"Chandelier can cast a shadow from an object driving past it or rotating by it like turning a corner, during the opening.
Maybe the candles can even ignite out of view and create shadows. Then maybe it can come back and swing about during the
opening of p6, in an eerie silent opening down the dark last passage where things fall apart."

## Build (DRY/APPLY/REVERT tools, records, exact census, targeted saves; live runs later by the conductor)
1. **Opening shadow**: place one hidden-in-game, cast-hidden-shadow Iron 3 instance (+chain) out of camera view between
   the drive-by light and the proscenium; a "turning the corner" variant = the light's target ARCS (yaw sweep) rather than
   slides; keys owned, one pass, timing args (default: the existing opening timeline; read the Opening/P01 sequence +
   Hyper3D prelude cue if one exists, else args). Report the shadow's projected size on the proscenium at peak.
2. **Candles igniting out of view**: candles light one by one (seeded order, single draw per value) while the chandelier
   is still off-camera; their light = a SMALL number of grouped point lights (args, default ≤4, NOT 44; shadow casting only
   on ≤2) so the chandelier throws flickering shadows on the walls. GPU guard: refuse >4 lights or >2 shadow casters
   (memory: fire shadows crashed the GPU on 8 Oct). Flame VFX = job 56.
3. **P06 return**: a second instance (visible) hung in P06's opening stretch (before chain A's creak at 24.89 s; P06 =
   110.6 s), swinging via job 52/52b keys driven by P06's motion, plus an optional cue kick; candles lit (or guttering —
   args) in the dark. "Silent" = no new sound by default. Choose the hang point from P06's route/camera (clear of wings
   and the topple chains; report clearances).
4. DRY reports: placements, light counts, shadow casters, timing tables, clearances; a timeline PNG for the opening and
   P06 0–30 s. Harness +/- controls (GPU guard, hidden-shadow flags, no overlap with topple rows, socket count 44).
Deliver in your worktree; tiered report; the conductor commits.
