# P88 paper-proscenium greenscreen-fringe report

Status: **offline fix complete; Unreal import and rendered acceptance not run**.

Delivery note (measured): the required commit could not be created because this managed session has read-only access to the linked git metadata. `git add -- Saved/CodexFlatV3/paperprosc/fringe_fix` failed with `Unable to create 'E:/PussStage/.git/worktrees/PussStage24/index.lock': Permission denied`. No main-tree file or git metadata was changed; all deliverables remain untracked in this worktree for the conductor to stage and commit.

## Deliverables

- Fix/generation tool: `fix_paperprosc_fringe.py`.
- New immutable-version textures: `textures/*_SkinColor_FringeFix_v1.png` (three files).
- Gary review: `crops/PAPERPROSC_FRINGE_BEFORE_AFTER.png`, plus separate before, after, and paired crops for all three pieces.
- Guarded Unreal tool: `paperprosc_fringe_run.py` -> `paperprosc_fringe_import.py`, with `DRY`, `IMPORT`, and non-deleting `REVERT` modes.
- Offline harness: `test_paperprosc_fringe_offline.py`; machine-readable result in `test_paperprosc_fringe_offline_report.json`.
- Source/output hashes and measurements: `fringe_fix_manifest.json`.

## Tiered findings

### Declaration-proven

- The Flat V3 silhouette is geometry rather than alpha, and the Front material is opaque (`Docs/FlatV3Spec_2026-09-30.md:103-105`, `:166-168`). Therefore the optional alpha erosion is disabled; it would not fix an opaque Front fringe. The tool retains a 0/1/2 px option but defaults to zero (`fix_paperprosc_fringe.py:59-60`, `:93-95`, `:235`).
- `SkinColor` is the relevant Front/Flap texture parameter (`Docs/FlatV3Spec_2026-09-30.md:286-291`). The import contract names exactly three new texture packages and six existing MIs (`paperprosc_fringe_core.py:9-38`).
- IMPORT is create-only for the three new textures, swaps only `SkinColor`, requires exact confirmation and `decided_by`, performs a pre-change backup, gates the exact dirty census, saves only nine named packages, and reads back MI assignments, texture settings, and import sources (`paperprosc_fringe_core.py:76-87`; `paperprosc_fringe_import.py:162-192`). REVERT restores only the six MI parameters and retains the new textures instead of permanently deleting them (`paperprosc_fringe_import.py:194-205`).

### Measured (offline)

- All three sources have binary alpha only, no partial-alpha texels, and zero non-black RGB texels in the adjacent transparent band (`fringe_fix_manifest.json:51-57`, `:101-107`, `:151-157`). This rules out an already-colour-padded or conventional partially transparent/unpremultiplied edge in the PNGs themselves.
- Bright green excess (`G > max(R,B)+20`) in opaque source texels measured 231,941 (left), 242,119 (right), and 350,817 (valance). The new files measure 0, 0, and 44 globally, and zero in every 32 px edge band (`fringe_fix_manifest.json:31-49`, `:81-99`, `:131-149`).
- The fix clamped 236,807 / 247,936 / 368,399 keyed texels, then padded 486,194 / 498,327 / 743,671 transparent texels with nearest corrected colour. Alpha erosion count is zero for every output (`fringe_fix_manifest.json:59-62`, `:109-112`, `:159-162`).
- The offline positive/negative, generated-output, source-hash, alpha-identity, read-back-contract, and static safety harness passed **27/27** (`test_paperprosc_fringe_offline_report.json:2-3`). Python compilation also passed. No Unreal or Blender process was used.

### Inferred

- **Primary cause:** green-key residue was baked into opaque silhouette-edge pixels. This inference combines the binary-alpha/black-transparent measurement with the large opaque green band; it is not a rendered-engine measurement.
- **Secondary risk:** black RGB under transparent alpha could bleed into mips/filter footprints. The 32 px colour dilation mitigates that risk (`fix_paperprosc_fringe.py:83-91`), but an Unreal rendered comparison is still required.
- The remaining 44 green-dominant valance texels are disconnected from the alpha edge and are preserved as possible illustration colour. Their visible significance is unproven until Gary reviews the crops and the conductor renders the imported assets.

### Binary-proven

- None. This offline texture task did not inspect or build binaries.

## Ordered conductor run

1. Review `crops/PAPERPROSC_FRINGE_BEFORE_AFTER.png` and approve the look.
2. In `paperprosc_fringe_args.json`, set a real run id and `mode` to `DRY`; leave confirm/decision/report blank. Execute `paperprosc_fringe_run.py` through guarded project Python. Require `PAPERPROSC_FRINGE_DRY_OK` and inspect its exact clean census/plan.
3. Set `mode` to `IMPORT`, `decided_by` to the approving person, `dry_report` to the DRY report basename, and `confirm` to **`IMPORT PAPERPROSC FRINGE a9a3e2cf`**. Run once. Require `PAPERPROSC_FRINGE_IMPORT_OK|...|saved=9`, then read back/render the three fronts.
4. If rejected, set `mode` to `REVERT`, `decided_by`, and `confirm` to **`REVERT PAPERPROSC FRINGE a9a3e2cf`**. Require `PAPERPROSC_FRINGE_REVERT_OK|...|saved=6|retained_new_textures=3`. This restores MI assignments without deleting assets.

## Open acceptance

- Gary crop approval: open.
- Unreal DRY/IMPORT and saved read-back: open by offline brief.
- Rendered fringe/mip acceptance: open; transport success alone will not close it.
