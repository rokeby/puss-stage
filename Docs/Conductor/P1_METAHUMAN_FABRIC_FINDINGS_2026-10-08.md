# P1 MetaHuman fabric and outfit findings — offline handoff

**Date:** 8 Oct 2026. **Scope:** offline source inspection and asset generation only. Unreal, MCP, PIE and Blender were
not run. Nothing was applied to `Content`, a Blueprint, the level, the Show, or a live editor.

Claim tiers are per `AGENTS.md`: **declaration-proven** = readable source/record; **measured** = this session's offline
run/read-back; **inferred** = proposed conclusion still requiring Unreal/rendered proof.

## 1. What exists now

| Question | Finding |
|---|---|
| Cloth authority | **[declaration-proven]** The shore covering is a `ChaosClothComponent` using `CA_ShoreHeadDrape` (or the bowed Shore02 asset); the earlier source was a 1 m plane scaled to about 1.64 m (`Docs/Conductor/S3_SACKCLOTH_PLAN_2026-10-06.md:24-28,63`). |
| Current generated live-sack size | **[declaration-proven]** v1/v2 decisions are 2.0 m; Shore02 is the back-pin special case (`Saved/CodexConductor/s3_sack_livecloth.py:158-159`). **[declaration-proven, one-figure record only]** the latest Shore05 probe resolves `MI_Sackcloth_OldGrey_Cloth_v2` (`Saved/CodexConductor/probe_s3_clam_rock.json:215-219`). **[inferred]** the saved state of all six is UNCLEAR without a fresh six-figure DRY/VERIFY read-back. |
| Mesh and size definition | **[declaration-proven]** `build_sheet()` receives the authored square edge from `params.size_m`; the supported range is 1.2–2.4 m (`Saved/CodexConductor/s3_sack_livecloth.py:191,226,924-929`). |
| Pin / Max Distance definition | **[declaration-proven]** v3 allows a two-pin rear-head-plus-upper-back layout for any named figure, including Shore02 (`Saved/CodexConductor/s3_sack_livecloth.py:275-280,924-936`). Pin weights are a minimum of head/back distance samplers, then smoothstep to one Max Distance weight map (`Saved/CodexConductor/s3_sack_livecloth.py:1107-1114`). Existing historical crown weights were 0 inside 3 cm, fading to 14 cm, free beyond (`Docs/Conductor/S3_SACKCLOTH_PLAN_2026-10-06.md:66`). |
| Physics definition | **[declaration-proven]** the Dataflow graph receives density, stretch, bend/buckle, damping and collision thickness from `PARAMS` (`Saved/CodexConductor/s3_sack_livecloth.py:1074-1088`). The old defaults are density 0.50 kg/m², stretch 1.0, bend 0.90, damping 0.12 and collision thickness 2 cm (`Saved/CodexConductor/s3_sack_livecloth.py:201-208`). |
| Old material | **[declaration-proven]** `M_ShoreLinen` is a flat constant colour with no maps (`Docs/Conductor/S3_SACKCLOTH_PLAN_2026-10-06.md:68`). |
| Outfit mesh/materials | **[declaration-proven, Shore05 probe]** the component named `SkeletalMesh` uses `MHC_Shore05_M53_Outfits`; its eight resolved slots alternate DefaultGarment Short and Shirt MIs (`Saved/CodexConductor/probe_s3_clam_rock.json:201-211`). **[inferred]** the other five use the same generated convention; the DRY tool refuses rather than assuming it. |
| Why “strip the shirt” is unsafe today | **[declaration-proven]** the optimized exported Body has legs, feet and neck but no torso faces, and the outfit supplies Shirt and Short geometry (`Docs/Conductor/S3_SACKCLOTH_PLAN_2026-10-06.md:730-738`). **[inferred]** hiding the shirt without rebuilding a full body exposes a hole, not naked skin. |

## 2. P1 cloth proposal (v3; not applied)

**[declaration-proven]** The versioned args request 1.8 m on all six, with the head disc shifted 6 cm rearward and an
upper-back disc on all six (`Saved/CodexConductor/P1MetaFabric_20261008/p1_metahuman_fabric_args.json:13-26`).

| Control | Old | P1 v3 | Reason / tier |
|---|---:|---:|---|
| density kg/m² | 0.50 | 0.50 | **[inferred]** retain heft; mass is not the stiffness control. |
| stretch stiffness | 1.00 | 0.85 | **[inferred]** allow slight give without turning the sheet elastic. |
| bend stiffness | 0.90 | 0.28 | **[inferred]** primary correction for “carpet” behavior. |
| buckling ratio / stiffness | 0 / 0.05 | 0.45 / 0.03 | **[inferred]** permit folds to yield after buckling. |
| damping | 0.12 | 0.08 | **[inferred]** less overdamped while still heavier than the curtain's documented 0.05. |
| collision thickness | 2 cm | 3 cm | **[inferred]** add clearance for reported show-through; this does not prove the PHYS shapes are adequate. |
| solver | 2 iterations, 4 substeps | 3 iterations, 5 substeps | **[inferred]** spend modestly more solver work on contact. |

The exact proposed values are in `p1_metahuman_fabric_args.json:23-41`. The builder retains versioned assets,
DRY/BUILD/APPLY/REVERT/VERIFY, confirm strings, a pre-write dirty census, `Backups/PreS3LiveSack-<run>`, named-package
saves, read-back and `S3LIVESACK_<MODE>_OK|run=...` markers. **[declaration-proven]** the runner selects the P1 args
through `S3LIVESACK_ARGS`, leaving the historical args untouched
(`Saved/CodexConductor/P1MetaFabric_20261008/p1_metahuman_fabric_run.py:1-6`).

## 3. Filthy-shroud textures

**[measured]** `P1SHROUD-20261008-032542` generated three tileable 2048² BaseColor, Roughness and DirectX-normal sets:
`A_ash_grey`, `B_damp_brown`, `C_soot_salt`, plus a preview sheet. The manifest declares size, tiling and convention
(`DerivedAssets/S3Sackcloth/P1_FilthyShroud_20261008/manifest.json:2-8,32,56`). Seam-to-neighbour ratios are 0.35–1.58,
below the generator's 4.0 refusal gate (`manifest.json:191-239`). **[measured, visual inspection]** all three previews
show coarse weave, irregular dark grime, rusty flecks and variant-specific damp/soot colour; no obvious border seam was
visible in the sheet. **[inferred]** A is the most neutral “filthy shroud”; Gary must choose A/B/C before Unreal import.

Generator: `Tools/S3Sackcloth/generate_filthy_shroud_textures.py`. **[declaration-proven]** it uses periodic FFT fields,
integer-frequency weave, wrapped normal derivatives and recoverable REVERT-by-move (`:66-91,92-138,187-225`).

## 4. MetaHuman outfit tool

`Saved/CodexConductor/P1MetaFabric_20261008/p1_metahuman_outfit.py`:

- **[declaration-proven]** classifies only DefaultGarment `_Short` and `_Shirt` slots and refuses unknown slots
  (`:55-63,102-110`).
- **[declaration-proven]** creates a rough colour-controlled loincloth material for Short slots. Shirt slots are
  preserved by default; optional hiding requires explicit `accept_missing_torso=true` (`:81-99`).
- **[declaration-proven]** DRY/APPLY/REVERT use confirm strings; APPLY/REVERT back up the map, require an exact dirty
  census, save only named packages/the named level, and read back (`:170-178,239-249,252-329`). REVERT keeps created
  material assets rather than deleting them.
- **[inferred]** the default brown `0.16/0.095/0.055`, roughness 0.86 is a first loincloth-colour proposal, not a
  rendered acceptance (`p1_metahuman_outfit_args.json:13-17`).

## 5. Harness and acceptance boundary

- **[measured]** P1 offline harness: **12/12** — positive **7/7**, negative **5/5**
  (`Saved/CodexConductor/P1MetaFabric_20261008/p1_metahuman_fabric_harness_report.json:2-11`). It confirms that Unreal
  and Blender were not run (`:147-148`).
- **[measured with environment limitation]** the legacy live-cloth harness reported 269/287 checks passing and 18
  failures, all from excluded `Content` files/assets missing in this git worktree. This is not a runtime failure and is
  not Unreal proof.
- **[inferred / open]** Visual drape, pin stability, collision clearance, garment coverage and skin continuity remain
  unaccepted until conductor DRY/read-back and rendered PIE stills. Null/source/offline success is not visual approval.

## 6. Conductor order (stop on any `_FAILED` marker)

1. Cloth DRY: keep `p1_metahuman_fabric_args.json` at `mode=DRY`; run `p1_metahuman_fabric_request.json`.
2. Review its six figure geometry/pin problems and dirty census. If clean, set `mode=BUILD`,
   `confirm="BUILD S3LIVESACK"`; run again. This creates v3 assets only.
3. Before swapping, if an apply record exists, set `mode=REVERT`, `confirm="REVERT S3LIVESACK"`; run the same request
   to restore the exact recorded current version. Then set `mode=APPLY`, `confirm="APPLY S3LIVESACK"`, version 3;
   run. Finish with `VERIFY` and later PIE/read-back under conductor control.
4. Choose shroud A/B/C from `filthy_shroud_preview_sheet.png`; texture import/material wiring is intentionally not
   performed until that look decision.
5. Outfit DRY: run `p1_metahuman_outfit_request.json` with its args unchanged. For the safe first pass, keep
   `hide_shirt=false`, then use `APPLY P1OUTFIT`; use `REVERT P1OUTFIT` for the exact inverse.
6. To remove shirts, first rebuild/verify full-body torso geometry, or explicitly accept visible torso holes. The tool
   refuses accidental shirt hiding.

## 7. Open decisions

1. Gary: texture A, B or C?
2. Is a full-body MetaHuman rebuild authorized so shirts can truly be removed?
3. After rendered v3 comparison: keep 1.8 m for all six, or retain a 2.0 m exception for bowed Shore02? The prior
   2.0 m back-pin covered her head and rump (`Docs/Conductor/S3_SACKCLOTH_PLAN_2026-10-06.md:902-911`).
4. Does 3 cm collision thickness fix show-through, or must the per-figure PHYS shoulder/back shapes be enlarged?
