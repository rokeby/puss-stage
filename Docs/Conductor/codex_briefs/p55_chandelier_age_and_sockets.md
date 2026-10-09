# Codex job 55 — chandelier recolour/aging + candle sockets (offline Blender), 9 Oct 2026

Requested by Gary via "Blender MCP Hyper3D". **Follow `Docs/Conductor/codex_briefs/_house_rules.md` in full.** Run with `--worktree`.

## Goal
Make two Rodin chandeliers production FBXs carrying the same "out of the cellar since 1790" aging as the stage front, and add one socket per candle cup for job 56 (candle flames) and p52 (pendulum swing).

## Inputs (read only)
- `DerivedAssets/StageFront_Chandelier_Iron3/Rodin/base_high_pbr.glb`: PRIMARY (Gary picked it 9 Oct), text-only heavy-metal black iron, two wide hoops, ~40 dripping candles, spiked crown/finial, ~260 cm wide x 300 cm. It has NO long chain above the crown, so step 1b MUST build a procedural hanging chain above the crown (default 300 cm, configurable in args), and its internal crown-to-ring chains stay part of the rigid body.
- `DerivedAssets/StageFront_Chandelier_Img/Rodin/base_high_pbr.glb`: gilt two-tier, from Fuser views.
- The look to match:
  - `DerivedAssets/StageFrontBuild/overlays_v2.py` (node groups `PeelOverlay`, `DustOverlay3`);
  - `light_test_v2.py`;
  - approved sheet `light_test_v3_sheet.png`.
- Bake tool to EXTEND (not fork): `DerivedAssets/StageFrontBuild/MaskBakeTool/`, i.e. `run_stage_front_mask_bake.ps1` + `stage_front_mask_bake.py`. Its ValidateSet is fixed at 9 assets.

## Do
1. **Prep script** (`chandelier_prep.py`, headless `blender -b --factory-startup`), one GLB per process:
   - Import the GLB; scale to real size in cm. Iron3: ~300 cm tall excl. the new top chain. Img: ~230 cm wide.
   - Hanging point (top of the chain) at origin; +Z up.
   - Keep the Rodin UV0 and the 12K texture (load once).
   - Detect the candle cups (top centres of the candle cylinders). Use geometry heuristics and record the method; if detection is unreliable, write the candidates plus a preview PNG for review instead of guessing.
   - Write sockets `Candle_01..NN` (the FBX `SOCKET_` empty convention per `Docs/WingGenerationConventions.md` / memory note `ue58-fbx-import-traps`).
   - Export `SM_Chandelier_<Name>.fbx`: FBX_SCALE_UNITS, axis_forward "-Z", axis_up "Y", triangulated, no embedded textures.
   - Write `chandelier_<Name>_sockets.json`.
1b. **Split the hanging chain from the body** (Gary 9 Oct: the chain must swing differently from the body).
   - Separate the chain above the top ring by connectivity or a Z cut, and record which method was used.
   - Export it as `SM_Chandelier_<Name>_Chain.fbx`, plus a chain-link spline / joint list JSON: link count, pivot points top→bottom, total length. The swing rig (p52, the same physics family as the wing lights) can then drive it as a multi-segment pendulum.
   - The JSON schema is FIXED, because job 52b consumes it. Write `chandelier_<Name>_chain.json` as
     `{"schema":"chandelier_chain_v1","units":"cm","frame":"UE (x fwd, y right, z up), origin = top hang point","count":N,"length_cm":L,"links":[{"index":0,"pivot_cm":[x,y,z],"length_cm":l,"mass_kg":m_or_null}, ...],"body":{"attach_cm":[x,y,z],"mass_kg":m_or_null}}`.
     Masses are estimated from mesh volume × wrought-iron density (7.8 g/cm³); mark them inferred.
   - The body pivots at the chain's bottom attach point: put the body's origin there and write a socket `ChainAttach` on the body.
   - If the Rodin chain is fused into one blob that can't be separated cleanly, say so and write a procedural replacement chain instead: N torus links matching the measured length and link size.
2. **Recolour**, Iron3 only:
   - Push towards forged black iron with rust in the crevices: an AO/cavity-driven rust colour, edge wear brighter steel.
   - The gilt Img keeps its gilt but gets the tarnish + dust treatment.
3. **Extend MaskBakeTool**:
   - Add assets `Chandelier_Iron3` and `Chandelier_Img`. Bake in an isolated scene (chandelier alone plus a ground plane is not needed; AO from self only).
   - Apply DustOverlay3 with Grime 0.6, PeelOverlay OFF (metal), and a rust tint on Iron3.
   - Same outputs as the existing assets: BaseColor_Dusty/Clean sRGB, Masks RGBA linear, N DirectX, Roughness. Sizes 8192 colour / 4096 others.
   - Keep every existing gate: 12 GB RAM, other-blender refusal, `-Confirm`, no-overwrite.
4. **Harness:**
   - Positive: a synthetic candle-ring scene with N cups yields exactly N sockets at the cup tops (±1 cm).
   - Negatives that must FAIL:
     - a GLB with no UV;
     - a scale far from the target (e.g. 1 m units);
     - zero cups detected, which must refuse rather than export.

## Blender use
- ALLOWED: headless only, on synthetic harness scenes, and on the two GLBs for prep/export plus ONE 512² smoke bake, in your worktree.
- NOT ALLOWED:
  - any production 8K bake; it goes in Hyper3D's gated chain;
  - running while another blender.exe runs (check `tasklist`; wait or stop and report).
- Free RAM must be ≥ 12 GB.

## Deliverable
- Tool paths in your worktree; harness counts.
- Socket counts per chandelier, with a preview PNG of the detected sockets on each chandelier.
- The ordered production commands.
- Every claim marked declaration-proven / measured / inferred with `file:line`.
- Write `DONE_p55.txt` in the worktree root.
