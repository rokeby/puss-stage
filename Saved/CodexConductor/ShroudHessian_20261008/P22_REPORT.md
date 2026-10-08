# P22 — S3 shroud hessian handoff

Run `SHROUDHESSIAN-20261008-172000`, offline only, 8 October 2026.

## Result and proof boundary

- **[measured]** The offline prep completed and the manifest identifies the read-only Fuser input directory, run id,
  pre-output backup, encoding and output inventory (`shroud_hessian_prep_manifest.json:2-5,50,217-221`).
- **[measured]** The offline harness passed **134/134**, including positive controls, refusal controls, all three
  validation-threshold mutations, and a seeded mutation of every protected template/instance property
  (`test_shroud_hessian_offline_report.json:2-4`; harness definitions at
  `test_shroud_hessian_offline.py:100-223`).
- **[declaration-proven]** The UE tool is DRY → guarded write → later read-back/save/read-back, with separate pending
  records for texture import and material construction (`shroud_hessian_ue.py:1-23,326-368,432-466,540-575`).
- **[declaration-proven]** APPLY and REVERT record and back up before the first material-slot write, perform an exact
  dirty-package save, and compare every protected live-cloth field before and after
  (`shroud_hessian_ue.py:232-257,683-745`).
- **[inferred]** The tool has **not** been run in Unreal. Asset creation, shader compilation, the current live
  `MI_Sackcloth_OldGrey_Cloth_v3` state, seeded actor assignments, package dirtiness and save persistence remain for
  the conductor's editor calls. Offline API/header and fake-state checks do not prove editor state.
- **[inferred]** None of the material defaults is a look approval. Gary must approve the contact sheet before APPLY;
  UE-rendered roughness, normal strength, colour, offset and rotation remain visually unaccepted.

**[measured]** No Unreal editor, MCP route, Content asset, Show asset, or level was opened or changed. No files were
copied to `E:/PussStage`; every output is only in this worktree.

## Texture encoding

- **[declaration-proven]** `T_Shroud_Stain_0N_Tint` is sRGB multiply colour: white (`1.0`) is neutral. The extraction,
  robust neutral estimate, linear-light low pass and tide-line sharpening are at
  `generate_shroud_hessian.py:207-257`.
- **[declaration-proven]** `T_Shroud_Stain_0N_Mask` is linear RGBA: R wet/greasy amount, G soot, B zero, A one
  (`generate_shroud_hessian.py:229-233`).
- **[inferred]** Holes/darns were not reliably separable from the generated stain paintings, so B is intentionally
  zero and those marks remain in tint. Wet/soot separation is a colour/darkness heuristic, not semantic ground truth.
- **[declaration-proven]** `T_Shroud_Weave_N` uses linear luminance as height, percentile-normalised, strength 4.0,
  DirectX tangent-space (`generate_shroud_hessian.py:259-269`). Strength 4.0 is an offline source-map recipe; the UE
  MI's independent `NormalStrength` default is 1.0.

## Validation

All rows are **[measured]** from `shroud_hessian_validation.json`. FFT is a windowed luminance annulus around the
measured 26.06 px weave frequency. Edge is p95 tide-line gradient versus an independently de-woven reference; values
above 1 mean the edge-restoration pass is slightly sharper than that reference. Neutral error is the maximum RGB
departure from 1.0 over the robust plain-cloth sample.

| Stain | Weave suppression | Edge retained | Neutral max error | Evidence |
|---:|---:|---:|---:|---|
| 03 | 22.23× | 1.061 | 0.01430 | `shroud_hessian_validation.json:16-31` |
| 04 | 10.51× | 1.067 | 0.00370 | `shroud_hessian_validation.json:50-65` |
| 05 | 22.51× | 1.063 | 0.00513 | `shroud_hessian_validation.json:84-99` |
| 06 | 19.93× | 1.066 | 0.00870 | `shroud_hessian_validation.json:118-133` |
| 07 | 14.58× | 1.060 | 0.00359 | `shroud_hessian_validation.json:152-167` |
| 08 | 18.14× | 1.055 | 0.00483 | `shroud_hessian_validation.json:186-201` |

**[measured]** The requested gates are therefore met: every FFT ratio is at least 10×, every edge ratio is at least
0.90, and every neutral error is below 0.03. Stain 04 is the narrowest FFT margin (10.51×).

## Material and editor tool

- **[declaration-proven]** `M_Shroud_Hessian` is specified create-only with four texture parameters, all scalar/vector
  values exposed, UV0 weave tiling, independent stain rotation/offset, multiplicative tint, strength-controlled
  normal, and wet/soot roughness blending (`shroud_hessian_ue.py:114-174`).
- **[declaration-proven]** The defaults are WeaveTiling 8, dry/wet/soot roughness 0.85/0.45/0.93, NormalStrength 1,
  Specular 0.35 and neutral tint/offset/rotation (`shroud_hessian_args.json:13-24`). These are reviewable arguments,
  not applied values.
- **[declaration-proven]** Seeded assignment uses a local RNG and a one-to-one shuffle of stains 03–08
  (`shroud_hessian_ue.py:225-229`).
- **[declaration-proven]** IMPORT_TEX is one texture per call and deliberately emits PENDING rather than OK; MAT_CHECK
  performs the later size/settings read-back, targeted save and second read-back
  (`shroud_hessian_ue.py:326-368,540-558`). BUILD_MAT follows the same pending/later-check discipline
  (`shroud_hessian_ue.py:432-466,559-575`).
- **[declaration-proven]** The master refuses an existing path and never calls a material-node deletion API
  (`shroud_hessian_ue.py:378-430`; static harness at `test_shroud_hessian_offline.py:203-220`).

## Preview and file list

- **[measured]** Gary review sheet: `Shroud_Hessian_ContactSheet.png`.
- **[measured]** Four composites exist for every stain: `Preview_0N_1to1_Center.png`,
  `Preview_0N_1to1_Offset.png`, `Preview_0N_FullShroud.png`, and
  `Preview_0N_FullShroud_Rot180.png` (`generate_shroud_hessian.py:292-313`; harness result rows in
  `test_shroud_hessian_offline_report.json`).
- **[measured]** Import textures are `T_Shroud_Weave_BC.png`, `T_Shroud_Weave_N.png`, and
  `T_Shroud_Stain_0N_{Tint,Mask}.png` for 03–08. Their SHA-256 values and byte sizes are exhaustive in
  `shroud_hessian_prep_manifest.json:221-423`.
- **[declaration-proven]** Conductor copy unit: copy the whole
  `Saved/CodexConductor/ShroudHessian_20261008/` directory, excluding `__pycache__/`. It contains the generator,
  generated PNGs, args, UE tool, harness, JSON evidence and this report.

## Run notes

- **[measured]** A first prep attempt failed before stain processing because Pillow 12 rejects Gaussian blur on
  float-mode images. Its sole partial PNG was moved, not deleted, to
  `Backups/FailedShroudHessianPrep-SHROUDHESSIAN-20261008-165734/`; the numeric blur was changed to SciPy and the
  successful run used a new id.
- **[measured]** The successful rerun backed up the preceding generated set to
  `Backups/PreShroudHessianPrep-SHROUDHESSIAN-20261008-172000/` before replacement
  (`shroud_hessian_prep_manifest.json:50-216`).
- **[inferred]** These worktree backup folders are local execution evidence and are not part of the conductor copy
  unit. The generated set itself is recoverable from the commit and its manifest.
