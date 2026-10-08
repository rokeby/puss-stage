# P19 curtain stream to Alembic recovery — 8 October 2026

## Outcome

- **declaration-proven:** `Tools/CurtainBake/stream_to_abc.py` now provides guarded `DRY`, `APPLY`, and `REVERT` modes. APPLY requires an id-bound confirmation, creates `Backups/PreCurtainStreamToAbc-<run>/record.json` before changing either target, and emits a run-id success marker only after output hash checks (`Tools/CurtainBake/stream_to_abc.py:675-749`).
- **declaration-proven:** the tool performs no cloth solve. It converts the completed world-space float stream to a local-space PC2 cache, drives one mesh through Blender's Mesh Cache modifier, and exports through the same selected-object VIEWPORT Alembic settings as the crashed bake (`Tools/CurtainBake/stream_to_abc.py:510-609`; `E:\PussStage\.claude\worktrees\agent-a40d86303acede5de\Scripts\bake_curtain_drop.py:1088-1094`).
- **measured:** the ordinary-Python harness passed **6/6** controls: three positive round-trip/topology/stream controls and three negative byte-count/topology/frozen-frame refusals (`Tools/CurtainBake/test_stream_to_abc.py:14-71`).
- **measured:** a real DRY over `unfurl_sleight_b1hop10_p02_stream.f32` returned `CURTAIN_STREAM_TO_ABC_DRY_OK|...|writes=0`. It found exactly 390 changing, non-zero frames, 45,430 vertices, 44,908 quads, and a 412-by-109 source grid. DRY wrote no files (`Tools/CurtainBake/stream_to_abc.py:790-810`).
- **measured:** Blender/APPLY was **not run**, as the brief forbids it before the pending reboot. Therefore `<id>.abc`, reconstructed `<id>.json`, Blender Alembic read-back, and rendered acceptance remain unproved.

## Exact reconstruction contract

- **declaration-proven:** the launcher fixes 30 fps production data at `RELEASE_FRAME=240`, `FRAMES=390`, `SHOW_START=210`, and `ABC_START=210`; it explicitly clears `RELEASE_AUTO`, so the adaptive branch that can move those values cannot run (`E:\PussStage\Saved\CodexSoftGoods\run_prod_unfurl.ps1:20-23`; `E:\PussStage\.claude\worktrees\agent-a40d86303acede5de\Scripts\bake_curtain_drop.py:873-877,969-980`).
- **declaration-proven:** the original scene uses 30 fps, object and mesh name `Curtain_<id>`, and object translation `(0,0,0.2 m)` (`E:\PussStage\.claude\worktrees\agent-a40d86303acede5de\Scripts\bake_curtain_drop.py:278-296`). The stream is explicitly world-space (`...\bake_curtain_drop.py:930-955`). The recovery therefore subtracts 0.2 m from PC2 vertex Z and restores the original +0.2 m object translation; rotation is zero and scale is one (`Tools/CurtainBake/stream_to_abc.py:510-519,542-594`).
- **declaration-proven:** the launcher selects the plain 18.8 m × 10 m, fullness-2, 15-quads-per-bolt pattern (`E:\PussStage\Saved\CodexSoftGoods\run_prod_unfurl.ps1:13-20`). Its UV0 is the normalized flat pattern and its quads use deterministic row-major winding (`Scripts/build_curtain_chaos_pattern.py:186-205`). The tool rebuilds that UV layer only after requiring every face in the stream sidecar to match the deterministic grid (`Tools/CurtainBake/stream_to_abc.py:87-108,532-539`).
- **declaration-proven:** the reconstructed report supplies `show_start`, `frames`, `release_frame`, held/final checkpoint AABBs, `track_m`, `fullness`, and `drop_m`, which are the fields the current import plan reads (`Saved/CodexSoftGoods/import_passing_bake.py:175-183`). It also carries reconstructed `top_z`, rig limits, hashes, and `reconstructed_from_stream: true` (`Tools/CurtainBake/stream_to_abc.py:237-461`). Original solve seconds and final Blender-only fold-size are explicitly recorded as unavailable rather than invented.
- **declaration-proven:** APPLY stages the Alembic in the backup, imports it back into a clean Blender scene, and compares all 45,430 world-space vertices at frames 210, 239, and 390 within `1e-5 m`; it also requires one mesh and the complete UV loop layer before publication (`Tools/CurtainBake/stream_to_abc.py:595-647,713-749`).

## Safety and acceptance boundary

- **declaration-proven:** the exact dirty-package census is N/A with empty map/content/package sets because this tool never opens Unreal and names zero Unreal packages (`Tools/CurtainBake/stream_to_abc.py:698-705`). It saves only the two named filesystem artifacts.
- **declaration-proven:** REVERT refuses if either published file has changed. It restores any pre-existing file from the backup; if none existed, it moves generated files into `reverted_generated` instead of permanently deleting them (`Tools/CurtainBake/stream_to_abc.py:753-788`).
- **measured:** stream-derived gates currently fail U2 and U7: pre-release maximum vertex motion is **72.26 mm/frame** (limit 1.5), and the final 30-frame maximum is **390.57 mm/frame** (limit 2.0). The stream does prove the heading held, the hem reached 0.2007 m by R+60, and all 390 frames are finite/non-zero/changing. This is a recovery result, **not** a passing bake verdict.
- **declaration-proven:** the Unreal importer will refuse this new artifact until acceptance is rerun and binds the new JSON and ABC hashes (`Saved/CodexSoftGoods/import_passing_bake.py:146-174`). Do not add it to `acceptance.json` by hand.

## Run after the reboot, in order

Use a new run id if any step is repeated.

```powershell
Set-Location E:\PussStage
$Id = 'unfurl_sleight_b1hop10_p02'
$Run = 'p19-p02-recover-20261008a'
$Blender = 'C:\Program Files\Blender Foundation\Blender 4.4\blender.exe'
$Tool = 'E:\PussStage\Tools\CurtainBake\stream_to_abc.py'
$Stream = "E:\PussStage\Saved\CodexSoftGoods\DropBake\${Id}_stream.f32"
$Sidecar = "E:\PussStage\Saved\CodexSoftGoods\DropBake\${Id}_stream.json"
$Out = 'E:\PussStage\Saved\CodexSoftGoods\DropBake'
```

1. **Harness (no Blender):**

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -m unittest -v Tools/CurtainBake/test_stream_to_abc.py
```

2. **DRY (Blender headless, zero writes):**

```powershell
& $Blender -b --factory-startup --python $Tool -- --mode DRY --run-id $Run --project-root E:\PussStage --stream $Stream --sidecar $Sidecar --out-dir $Out --id $Id --frames 390 --abc-start 210 --show-start 210 --release-frame 240 --track-m 18.8 --drop-m 10 --fullness 2 --quads-per-bolt 15 --brail-frames 120
```

Require `CURTAIN_STREAM_TO_ABC_DRY_OK|run=<run>|id=<id>|writes=0`.

3. **APPLY (Blender headless):**

```powershell
& $Blender -b --factory-startup --python $Tool -- --mode APPLY --confirm "APPLY_STREAM_TO_ABC:$Id" --run-id $Run --project-root E:\PussStage --stream $Stream --sidecar $Sidecar --out-dir $Out --id $Id --frames 390 --abc-start 210 --show-start 210 --release-frame 240 --track-m 18.8 --drop-m 10 --fullness 2 --quads-per-bolt 15 --brail-frames 120
```

Require `CURTAIN_STREAM_TO_ABC_SUCCESS`, then inspect `Backups/PreCurtainStreamToAbc-$Run/record.json`; its status must be `applied_and_read_back` and all three Alembic frame checks must be below `1e-5 m`.

4. **Only after the tool passes:** rerun the existing bake acceptance/report chain. The measured U2/U7 failures above need an explicit conductor/Gary disposition; recovery does not waive them.

5. **REVERT if required (recoverable, no permanent deletion):**

```powershell
python -B $Tool --mode REVERT --confirm "REVERT_STREAM_TO_ABC:$Id" --run-id $Run --project-root E:\PussStage --stream $Stream --sidecar $Sidecar --out-dir $Out --id $Id
```

Require `CURTAIN_STREAM_TO_ABC_REVERT_SUCCESS`.

## Open questions

1. **measured:** does Gary/conductor accept a recovered cache whose stream-derived stillness gates U2 and U7 are red, or should it remain an unaccepted forensic artifact?
2. **inferred:** the geometry and sampling can be reproduced exactly from the stream, but Alembic container bytes cannot be compared with the crashed export because that export never completed. The mandatory Blender import/read-back is the available equivalence proof.

## For W&T (bake owner): finishing-touches analysis after the reboot, 8 Oct evening (relayed by Conductor 5)
- [measured] Stream complete: 212,612,400 B = 390 × 45,430 × 12. Blender crashed AFTER the solve (no OpenGL).
- [measured] stream_to_abc DRY OK, but unfurl gates fail:
  - pass: U1 bunched 0.835 m, U3 heading 0, U4 hem 0.20 m at R+60, U5 hang profile (23 folds, flare 1.0),
    U6 hem/stretch 0.995;
  - FAIL U2 still-before-release 72 mm (the approved scout e4 also fails it, at 105 mm);
  - FAIL U7 settled-at-end 390 mm (scout e4: 1.15 mm).
- [measured] U7 is JITTER, not sway. From ~frame 270 the median vertex step is 5-8 mm/frame and 40-65% of vertices
  reverse direction every frame. Over the last 1 s, median path 263 mm vs net 14 mm. ~80% of vertices move >2
  mm/frame. The drop 240→266 is clean.
- [inferred] Cause: production is 9× the scout resolution (45,430 vs 5,106 verts; 9.1 vs 27.4 cm quads) with the same
  QUALITY 20 and SELF_DIST 0.03 m (0.33× edge; the log warns >0.2), and VERTEX_MASS_SCOUT 1.0 per vertex.
- Options:
  - (a) offline salvage: temporal low-pass of the stream from ~frame 266, then stream_to_abc APPLY; minutes; verify by
    re-measuring U7 + a collider-penetration check;
  - (b) re-bake with QUALITY ~40, SELF_DIST ~0.015-0.018 m, mass scaled to the mesh (~7 h+);
  - (c) both.
