# P40 — S3 Shore05, cloth settle, and underwear-colour report (offline)

Date: 2026-10-09

Scope: `Saved/CodexConductor/P40Shore05Settle_20261009/`

## Result and proof boundary

- **[measured]** The job-63 offline Python compile and harness pass 34/34 controls: 14 positive and 20 negative; neither Unreal nor Blender was started. Evidence: `Saved/CodexConductor/P40Shore05Settle_20261009/p40_harness_report.json`.
- **[measured]** The preview generator produced `P40_Placement_Preview.png` and `P40_Underwear_Colour_Preview.png`, and both were visually inspected for legibility. Evidence: `Saved/CodexConductor/P40Shore05Settle_20261009/p40_preview.py:1-68`.
- **[inferred]** This delivery is ready for conductor DRY review, not live acceptance. Placement, saved-state readback, Chaos behaviour, render colour, and pin clearance remain unproved until the editor run and rendered review described below. Evidence: `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:341-364`, `:620-657`.
- **[measured]** No binary claim is made: installed source declarations were sufficient for the API boundary, so no DLL symbol/string result is represented as `binary-proven`.

## Delivered implementation

- **[declaration-proven]** `p40_core.py` is Unreal-independent planning code: guarded args, fixed-draw seeded candidates, live-camera clearance geometry, one mandatory Shore05 plus 0..5 variants, shared dune height import, forward-only overlap chains, colour math, and still times. Evidence: `Saved/CodexConductor/P40Shore05Settle_20261009/p40_core.py:75-137`, `:152-256`, `:268-298`.
- **[declaration-proven]** Placement look choices are editable defaults, including seed, local candidate bounds, figure/camera/sightline clearances, crossfade, and foot offsets. Evidence: `Saved/CodexConductor/P40Shore05Settle_20261009/p40_args.json:1-20`.
- **[declaration-proven]** DRY reads the exact B02..B12 spawnable camera census and evaluates every transform-key time with a bounded one-frame Sequencer range. Absolute plus additive, initial-only, additive-only, and one relative section are composed using the spawnable template as MovieScene's initial value. Multiple base owners and attachment constraints still refuse because raw channels do not reproduce weighted/eased or parent-world evaluation. DRY also reads current Shore actors, all six cloth templates/WeaveTint values, resolved outfit slots, colour parameters, and the exact dirty census without authoring. Evidence: `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:164-286`, `:380-389`.
- **[declaration-proven]** APPLY refuses PIE/SIE, wrong world, a dirty start, missing confirmation, a prior active record, and hard DRY problems; it hashes a `Backups/PreP40Shore-<run>` copy and writes its record before actor/material/template mutation. Evidence: `Saved/CodexConductor/P40Shore05Settle_20261009/p40_core.py:75-137`; `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:90-134`, `:583-594`.
- **[declaration-proven]** New actors get exact labels/tags, actor and Body bindings, the `bHidden` visibility track with VISIBLE bool semantics, and forward-only weighted animation sections in `LS_Clams`. Evidence: `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:380-483`.
- **[declaration-proven]** APPLY saves only the level, `LS_Clams`, opted-in BP templates, and new child MIs after an exact dirty-package equality check; it then performs readback and emits a run-id success marker. Evidence: `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:572-611`.
- **[declaration-proven]** REVERT requires unchanged recorded state, makes a second backup, restores existing actors' outfit overrides and cloth settings, removes only recorded bindings/actors, retains new MI children, saves named packages, and emits its marker. Evidence: `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:660-711`.

## Placement and motion findings

- **[declaration-proven]** The planner requires readable B cameras, rejects figure/camera/sightline conflicts, fixes Shore05 into slot 0, and selects optional sources from all six BPs using five RNG draws per candidate so rejection cannot perturb later candidates. Evidence: `Saved/CodexConductor/P40Shore05Settle_20261009/p40_core.py:152-191`, `:226-256`.
- **[declaration-proven]** Dune Z is DRY rather than duplicated: `p40_core.py` imports `DOCK_ORIGIN` and `sand_height` from `s3_beach_v2.py`; failure to import makes planning fail instead of using a second surface formula. Evidence: `Saved/CodexConductor/P40Shore05Settle_20261009/p40_core.py:12-25`, `:240-251`.
- **[inferred]** Default foot offsets are S3FEET-compatible starting estimates, not pose proof for the newly chosen motion phase; rendered feet must be checked and offsets adjusted in args if necessary. Evidence: `Saved/CodexConductor/P40Shore05Settle_20261009/p40_core.py:57-60`, `:245-250`; `Saved/CodexConductor/s3_crowd_feet.py:1-5`.
- **[declaration-proven]** Motion chains never set reverse and enforce exact coverage, overlap, and weight ramps. Evidence: `Saved/CodexConductor/P40Shore05Settle_20261009/p40_core.py:193-223`; prior mechanism: `Saved/CodexConductor/s3_crowd_loops_v2.py:4-9`, `:106-116`.
- **[inferred]** The inherited SHAPPLY2 MI is audited and recorded from each spawned cloth component; this tool does not overwrite that seeded BP-template material assignment. Evidence: `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:257-275`, `:449-483`.

## Cloth settle investigation

- **[declaration-proven]** UE 5.8 exposes one-shot teleport/reset, suspend/resume, enable simulation, persistent teleport/reset flags, and auto-teleport distance/rotation thresholds. Evidence: `D:/Unreal Engine/UE_5.8/Engine/Plugins/ChaosClothAsset/Source/ChaosClothAssetEngine/Public/ChaosClothAsset/ClothComponent.h:115-164`, `:457-481`, `:502-516`.
- **[declaration-proven]** The installed component header has no warm-up or pre-roll setting. Persistent `bReset` is not a warm-up mechanism: it requires `bTeleport`, while the one-shot form is cleared each frame. Evidence: `D:/Unreal Engine/UE_5.8/Engine/Plugins/ChaosClothAsset/Source/ChaosClothAssetEngine/Public/ChaosClothAsset/ClothComponent.h:119-135`, `:475-481`, `:530-534`.
- **[inferred]** The optional default-off template policy therefore changes only auto-jump thresholds and explicitly leaves persistent teleport/reset false. It may reduce discontinuity after large root jumps, but it cannot prove settled cloth and requires `acknowledge_inferred_behavior=true`. Evidence: `Saved/CodexConductor/P40Shore05Settle_20261009/p40_core.py:108-116`; `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:486-502`.
- **[inferred]** Initial settle is provided operationally by playing from S3 start while new figures remain invisible until frame 360 (15 s at 24 fps). Direct transport jumps still require a render/transport warm-up or lead-in outside this BP-template API. Evidence: `Saved/CodexConductor/P40Shore05Settle_20261009/p40_core.py:63-64`, `:287-298`; `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:436-446`.
- **[declaration-proven]** Per-vertex MaxDistance masks are not exposed by the cloth component API inspected here. Existing v3 tooling declares crown plus upper-back kinematic discs and gates pin coverage, so a failed live pin audit should route to that Dataflow build; Blender is only needed after bake if the source geometry/mask needs revision. Evidence: `Saved/CodexConductor/s3_sack_livecloth.py:66-78`, `:96-104`; `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:267-275`.

## Underwear colour and prior failure

- **[declaration-proven]** The 8 Oct tool wrote raw `override_materials` and validated that raw array before later failing resolved-material readback. Evidence: `Saved/CodexConductor/P1MetaFabric_20261008/p1_metahuman_outfit.py:233-234`, `:294`.
- **[inferred]** The most specific code-level diagnosis is that raw array assignment did not exercise the component's `SetMaterial` render-state path. P40 creates versioned MI children, leaves masters untouched, assigns with `set_material`, and checks `get_material` immediately and again in VERIFY. Evidence: `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:505-526`, `:543-568`, `:642-648`.
- **[measured]** Offline sampling of the 2048x2048 desaturated weave base (4,194,304 pixels) produced sRGB mean `(0.6658808661, 0.6412755957, 0.6070530256)` and linear mean `(0.4400743730, 0.4071881324, 0.3630656971)`. Evidence recorded in `Saved/CodexConductor/P40Shore05Settle_20261009/p40_core.py:61-62` and emitted in DRY at `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:352-355`.
- **[declaration-proven]** Each target colour is `linear weave mean * live MI WeaveTint`, clamped to `[0,1]`; the tool refuses missing or ambiguous colour parameters. Evidence: `Saved/CodexConductor/P40Shore05Settle_20261009/p40_core.py:268-284`; `Saved/CodexConductor/P40Shore05Settle_20261009/p40_editor.py:287-307`.
- **[inferred]** Numerical parameter readback is not rendered equivalence: Gary must accept the underwear/cloth match from the B02/B08 stills under scene lighting.

## Conductor run order

1. **[declaration-proven]** Copy the whole `P40Shore05Settle_20261009` folder into the main project's `Saved/CodexConductor/`; leave `p40_args.json` at `mode=DRY`, choose `extra_count` and review all creative defaults.
2. **[declaration-proven]** With the correct level open, no PIE/SIE, and no expectation that DRY will save, send `p40_request.json`; require `P40SHORE_DRY_OK`, `apply_ready=1`, `writes=0`, and unchanged dirty census. Transport declaration: `Saved/CodexConductor/P40Shore05Settle_20261009/p40_request.json:1-10`.
3. **[inferred]** Review `p40_dry_latest.json`, both supplied previews, all candidate positions/camera rejections, inherited shroud MIs, outfit parameters, and pin warnings. Keep `cloth_reset.enabled=false` unless Gary explicitly approves the threshold experiment.
4. **[declaration-proven]** Set `mode=APPLY` and `confirm="APPLY P40SHORE"`; send the same request once. Require `P40SHORE_APPLY_OK` with run id, backup, exact packages, and `dirty=0`.
5. **[declaration-proven]** Set `mode=VERIFY`, clear `confirm`, rerun, and require `P40SHORE_VERIFY_OK` with zero problems.
6. **[inferred]** Play/render continuously from 0 s; do not judge a frame reached by a cold direct jump. Check stills at 0, 5, 14.5, 15, 35.7, 64.2, 117.8, 189.1, and 238 s for reset pop, settling, feet, pin retention, forward-loop whip, and colour. Evidence: `Saved/CodexConductor/P40Shore05Settle_20261009/p40_core.py:287-298`.
7. **[declaration-proven]** To undo, first ensure no state drift and a clean census, then set `mode=REVERT`, `confirm="REVERT P40SHORE"`; require `P40SHORE_REVERT_OK`. New MI children are intentionally retained, not deleted.

## Open decisions and acceptance gates

- **[inferred]** Gary must choose `extra_count` (0..5), approve the proposed seeded positions from live DRY, and decide whether to trial the default-off auto-jump threshold policy.
- **[inferred]** Gary must accept rendered underwear colour, cloth rest at every cut/jump, feet contact, and back-of-head/top-of-back retention; source/readback success alone is insufficient.
- **[inferred]** If live DRY reports non-v3 cloth assets or rendered pin failure, run/review the existing v3 Dataflow pin path before considering any Blender bake.
