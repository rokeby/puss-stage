# P12 — S3 B06 dense, desperate handprints (8 Oct 2026)

**Status: OFFLINE BUILD ONLY. Nothing was applied.** No Unreal Editor, MCP, PIE, Blender, Show asset, level, or
Content package was opened or changed in this stream. Gary must approve the preview before the conductor runs the
editor steps below.

Tiers used here: **[declaration-proven]** source/config says it; **[binary-proven]** decoded from the saved sequence
bytes; **[measured]** an offline generator/harness actually ran; **[inferred]** Unreal/render outcome not testable
offline, with the missing check named.

## Outcome

- **[binary-proven]** The checked-in offline sequence dump records B06 at frames 3000–3480, with the camera moving
  beside the right wall from world X 14072.5889 to 14866.1523 and Z 220.2 to 188.9. The generated table carries the
  evidence and tier at `Saved/CodexFlatV3/handprints/p12_dense/hp_dense_layout.py:223`.
- **[declaration-proven]** The default editable band is right-wall local X 2500–4500 cm, Z 20–850 cm, density 2.0;
  those are arguments/defaults, not hidden constants (`hp_dense_config.json:5-10`, `hp_dense_layout.py:95`).
- **[measured]** The previous table has 99 mark centres in that band; the new table has exactly 198 marks and zero
  rotated extent outside it (`previews/p12_b06_preview_report.json:2-23`; positive and negative gates
  `test_hp_dense.py:41-58`).
- **[measured]** The 198 marks comprise 61 reaching-hand marks, 79 long finger scratches, 50 clustered overlaps and
  8 drag smears (`placement_S03_dense.json:16677-16683`). Six seeded, irregular upward events supply the trails.
  Determinism, seed+1 divergence and the one-random-draw-per-line trap are covered at `test_hp_dense.py:60-64` and
  `test_hp_dense.py:120-124`.
- **[declaration-proven]** The dark layer is a separate BaseColor-only twin over the unchanged sheen, so it does not
  replace the existing roughness/normal grease material. The selected default is Gary's exact dried-blood core
  (linear 0.155/0.007/0.005, strength 0.55, thresholds 0.45–0.75); a stronger unapproved proposal remains an
  alternate argument (`hp_dense_config.json:37-52`).
- **[inferred]** The preview is wall geometry, not an Unreal render. It proves placement/readability on paper, not
  the final daylight/exposure/material response (`previews/p12_b06_preview_report.json:23`).

## Files

All tooling/data is under `Saved/CodexFlatV3/handprints/p12_dense/`:

| File | Purpose |
|---|---|
| `hp_dense_config.json` | Band, density, event ranges and dark presets |
| `hp_dense_layout.py` → `placement_S03_dense.json` | Deterministic generator and pinned 198-row table |
| `hp_dense_preview.py` → `previews/*.png` | Old, new and side-by-side wall elevations |
| `hp_dense_core.py` | Pure gates/digests/fake-world controls |
| `hp_dense_editor.py` + wrappers/requests | Guarded material and level authoring modes |
| `test_hp_dense.py` → `test_hp_dense_report.json` | Offline positive/negative harness |

Preview to show Gary first: `previews/p12_b06_old_vs_new.png`.

## Editor safety contract

**[declaration-proven]** `hp_dense_editor.py` provides ASSET_DRY/APPLY/VERIFY plus level DRY/APPLY/REVERT_DRY/REVERT.
It refuses PIE, the wrong world, dirty packages, foreign counts, missing assets, wrong table SHA, temp actors, and
missing exact confirm strings (`hp_dense_editor.py:223-294`, `:314-327`).

**[declaration-proven]** Material APPLY backs up the target folder and records before creation; it creates at most 16
MIs per call and prints `NOT_YET_VERIFIED`. A later call reads parameters with 1e-4 tolerance. Level APPLY and REVERT
back up the umap and write their record before the first actor mutation (`hp_dense_editor.py:395-408`, `:431-442`).
Only named MI packages or the current level are saved; success follows clean-census and count read-back
(`hp_dense_editor.py:391`, `:419-423`, `:458-463`).

APPLY snapshots and replaces both the required saved `HP_S03G` sheen layer and whichever optional `HP_S03T` tint
layer it actually finds (0 or a complete twin set). REVERT restores every snapshotted actor field. The 32 created
dense MIs remain unreferenced after REVERT; no asset is permanently deleted.

## Conductor run order — only after Gary approves the preview

Each JSON is one `ExecuteProjectPythonFile` MCP call. Stop on any `STOPPED`, `ERROR`, dirty census, or unexpected count.

1. Offline: rerun `python Saved/CodexFlatV3/handprints/p12_dense/test_hp_dense.py` →
   `P12_DENSE_TESTS|ran=17|fail=0`.
2. `hp_dense_asset_dry_request.json` → `P12_DENSE_ASSET_DRY_OK`.
3. `hp_dense_asset_apply_request.json` twice, waiting after each → two `P12_DENSE_ASSET_BUILT ... NOT_YET_VERIFIED`
   markers, 16 MIs each. A third call should report `NOTHING_TO_DO`.
4. In a later call, `hp_dense_asset_verify_request.json` → `P12_DENSE_ASSET_VERIFY_SUCCESS|verified=32`.
5. `hp_dense_dry_request.json` → `P12_DENSE_DRY_OK|source_grease=1034|source_tint=0-or-1034|marks=198|spawn=396`.
6. `hp_dense_apply_request.json` → `P12_DENSE_APPLY_SUCCESS|...|marks=198|spawned=396|saved=1`.
7. Read back the clean census, then take a fresh B06 still/video. Gary judges darkness, sheen, scale and desperation.

REVERT: `hp_dense_revert_dry_request.json`, then `hp_dense_revert_request.json`; require
`P12_DENSE_REVERT_SUCCESS` and a clean census. Do not delete the retained MIs.

## Harness and open checks

- **[measured]** P12 harness: **17/17 pass**, including seeded negative controls, band mutation, foreign-layer refusal,
  exact confirm strings, lossless fake revert and static save/backup ordering (`test_hp_dense_report.json:2-3`).
- **[measured]** `py_compile` passed for core, generator, preview and editor scripts.
- **[measured]** Three older grease harnesses could not be re-established in this worktree: their auxiliary
  `Tools/FlatV3/handprints/build_handprint_placement.py`, `hp_grease_mi_worklist.json`, patch and copied source files
  are absent; the old placement pin also differs from the checked-in table. No old file was changed here.
- **[inferred / open]** The earlier obstacle-box JSON is absent, so the generator preserves the old validated material
  templates and dune-floor samples but cannot offline-prove new lamp/wave overlap. The conductor's DRY plus the first
  rendered B06 still must check this explicitly. UNCLEAR until then.
- **[inferred / open]** No current saved-level census was available offline. The tool deliberately accepts either the
  brief's no-tint state or the later conductor-log complete-tint state, but refuses any partial tint layer.
