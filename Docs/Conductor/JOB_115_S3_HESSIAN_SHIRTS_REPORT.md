# Codex job 115 - S3 hessian shirts (offline delivery)

## Outcome and proof boundary

- **declaration-proven:** The tool in `Saved/CodexConductor/J115S3HessianShirts_20261009/` has DRY/APPLY/VERIFY/REVERT modes. It creates only versioned shirt child MIs under `OutfitHessian`, never edits or deletes a pre-existing material or node, and REVERT retains the created children (`Saved/CodexConductor/J115S3HessianShirts_20261009/j115_editor.py:1-7,254-296,400-432`).
- **declaration-proven:** Its actor scope is exactly the six canonical `<figure> Clam` actors plus actors tagged `P40.ShoreFigure`. It uses job 40's `_outfits` skeletal-component resolver and `set_material(slot, child)` path, targeting only slots whose resolved material is a DefaultGarment `_Shirt` (`Saved/CodexConductor/J115S3HessianShirts_20261009/j115_core.py:159-176`; `Saved/CodexConductor/J115S3HessianShirts_20261009/j115_editor.py:96-119,153-181,299-320`).
- **measured (offline):** The source PNG `T_Shroud_Weave_BC.png` was found on disk and measured as 2048x2048 / 4,194,304 pixels, sRGB mean `(0.6658808661, 0.6412755957, 0.6070530256)`, and per-pixel linear mean `(0.4400743730, 0.4071881324, 0.3630656971)`. Its SHA-256, dimensions and values are in `Saved/CodexConductor/J115S3HessianShirts_20261009/j115_source_measurement.json:1-19`; the calculation is at `Saved/CodexConductor/J115S3HessianShirts_20261009/j115_core.py:49-75`.
- **measured (offline):** Python compilation passed; the harness passed **8/8 positive + 7/7 negative = 15/15**, and neither Unreal nor Blender was started (`Saved/CodexConductor/J115S3HessianShirts_20261009/j115_harness_report.json:79-89`). The preview was generated and visually inspected for legibility.
- **UNCLEAR:** No Unreal call was made. Live parent parameter names, selected texture-vs-tint strategy, actor/variant count, saved assignments, rendered match, and visual interference remain unproved until the conductor runs DRY/APPLY/VERIFY and Gary reviews stills.

## Part A - guarded tool

- **declaration-proven:** DRY inventories each target actor, exact component path, resolved slots, per-figure shirt parent, texture/vector/scalar/static-switch parameter names, source colour measurement, exact dirty census, and Part B diagnostic gates. It writes no Unreal assets or packages (`Saved/CodexConductor/J115S3HessianShirts_20261009/j115_editor.py:122-187,198-225`).
- **declaration-proven:** A parent exposing both configured base-colour and normal texture parameters selects `T_Shroud_Weave_BC` and `T_Shroud_Weave_N`. Otherwise the tool requires one tint and one roughness parameter, applies the measured linear mean plus the configured roughness, and optionally sets Specular (`Saved/CodexConductor/J115S3HessianShirts_20261009/j115_core.py:125-157`; `Saved/CodexConductor/J115S3HessianShirts_20261009/j115_editor.py:254-278`).
- **declaration-proven:** Static-switch values in args must be JSON booleans (`true`/`false`). Setter return values are ignored; every texture, vector, scalar and static-switch value is read back. Slot assignments are read back immediately and again in VERIFY (`Saved/CodexConductor/J115S3HessianShirts_20261009/j115_core.py:94-122`; `Saved/CodexConductor/J115S3HessianShirts_20261009/j115_editor.py:134-150,279-295,313-319,362-397`).
- **declaration-proven:** APPLY refuses PIE/SIE, wrong world, any dirty package, existing versioned children, missing canonical actors, ambiguous components/slots/parents/parameters, or an active record. It creates `Backups/PreJ115S3Shirts-<run>` and the exclusive record before mutation, then saves only six named child MIs and the vertical-slice map after exact dirty-census equality (`Saved/CodexConductor/J115S3HessianShirts_20261009/j115_core.py:94-122,159-176`; `Saved/CodexConductor/J115S3HessianShirts_20261009/j115_editor.py:71-81,110-181,241-251,323-359`).
- **declaration-proven:** REVERT requires clean and unchanged applied state, backs up the map again, restores only the recorded shirt slots with `set_material`, saves only the map, and retains all created child MIs (`Saved/CodexConductor/J115S3HessianShirts_20261009/j115_editor.py:400-432`).

## Stills plan and acceptance

1. **inferred:** B02 before/after should show the shirt/shroud overlap without a white edge and with continuous midtone/weave response (`Saved/CodexConductor/J115S3HessianShirts_20261009/j115_editor.py:216-220`).
2. **inferred:** B08 should compare body-shape A/B highlight and roughness response; numerical equality is not rendered equivalence (`Saved/CodexConductor/J115S3HessianShirts_20261009/j115_editor.py:216-220`).
3. **inferred:** B11 should include Shore05 and every visible P40 variant and prove no variant retained a white shirt slot (`Saved/CodexConductor/J115S3HessianShirts_20261009/j115_editor.py:216-220`).
4. **measured acceptance required:** Only Gary's side-by-side review can accept the look. APPLY/VERIFY markers prove saved assignments and parameters, not the image (`Saved/CodexConductor/J115S3HessianShirts_20261009/j115_editor.py:388-396`).

## Part B - exact gated fixes for black/shiny/untextured hessian

| candidate from job 109 | diag-v2 gate | exact create-only fix if gate is true |
| --- | --- | --- |
| overly glossy/dark response | Effective Roughness/Specular or base shading model is outside the reviewed cloth regime. | Create versioned child shroud MIs overriding exposed Roughness/Specular. If the shading model is wrong, create a fresh versioned cloth master plus children and reassign only recorded shroud slots. |
| missing/wrong UV channel | A referenced TextureCoordinate index is greater than or equal to the cloth mesh UV-channel count. | Create a versioned master sampling the weave from a valid measured channel, normally UV0; create child MIs and reassign recorded shroud slots. Do not touch the old graph. |
| weave scaled out | Effective Tiling/Tile/UV/Scale/Weave values are zero, extreme, or disagree on bad figures. | Create versioned child MIs with reviewed nonzero tiling overrides. If scale is hard-coded, create a fresh parameterised versioned master. |
| wrong texture interpretation | BC is not sRGB/color-compressed; N is sRGB or not normal-map compressed; or measured green orientation is wrong. | Duplicate BC/N to versioned textures, correct settings only on duplicates, then create child MIs referencing those duplicates. |
| transparency/culling mismatch | Blend mode, two-sided, opacity clip, or effective opacity/mask disagrees with the approved opaque/masked two-sided design. | Create a fresh versioned cloth master with approved flags and correctly wired opacity/mask. Any StaticSwitch graph connection uses explicit True/False pins; create children and reassign recorded slots. |

- **declaration-proven:** These are conditional preparations, not approved changes. The exact gates/fixes are code-owned at `Saved/CodexConductor/J115S3HessianShirts_20261009/j115_core.py:183-201`, and DRY emits them beside the current diag artifact schema/result (`Saved/CodexConductor/J115S3HessianShirts_20261009/j115_editor.py:190-196,210-220`).
- **inferred:** If diag-v2 reports normal values for a candidate, make no material fix for that candidate and route the problem to rendered lighting/exposure isolation instead; job 109 identifies those same five candidates and their live JSON paths (`Docs/Conductor/JOB_109_S3_FIGURE_DIAG_V2_REPORT.md:16-22`).

## Conductor run order

1. Run `python Saved/CodexConductor/J115S3HessianShirts_20261009/test_j115_offline.py` and `j115_preview.py` offline.
2. Keep args at `DRY`; run `j115_request.json`. Require `J115SHIRTS_DRY_OK`, `writes=0`, `apply_ready=true`, clean census, six canonical actors, and the expected P40 variant count.
3. Review every parent strategy and parameter name. If a texture-mode switch is needed, add its exact live name with JSON `true` or `false`, then rerun DRY.
4. Set `mode=APPLY`, `confirm="APPLY J115SHIRTS"`; run once. Require `J115SHIRTS_APPLY_OK`, six children, exact packages, backup, and `dirty=0`.
5. Set `mode=VERIFY`, clear confirm, rerun. Require `J115SHIRTS_VERIFY_OK` with assignment and MI-parameter readbacks.
6. Capture B02/B08/B11 before/after stills and obtain Gary's acceptance.
7. To undo assignments, set `mode=REVERT`, `confirm="REVERT J115SHIRTS"`; require `J115SHIRTS_REVERT_OK`. The six create-only MIs remain intentionally.
