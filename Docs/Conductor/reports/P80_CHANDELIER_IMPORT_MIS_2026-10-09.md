# P80 chandelier import + aged MI — offline delivery report

## Job 82 import-staging correction (9 Oct)

- **declaration-proven** — `IMPORT` now requires the exact `asset` name of one of seven declared assets. Missing, list-valued/two-asset, comma-joined, and unknown selectors are refused before Unreal mutation (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_core.py:33-41`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_core.py:189-201`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_core.py:229-237`).
- **declaration-proven** — One execution imports only the selected asset, reads back its mesh/socket or texture settings, calls `unreal.SystemLibrary.collect_garbage()`, requires that exact one package to be dirty, saves only that package, then requires a zero-dirty census and performs saved-state read-back (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:213-284`).
- **declaration-proven** — The record remains `importing` across partial calls and becomes `imported` only when its selector census is exactly 7/7. `MAT_CHECK` and `APPLY` still require the completed `imported` state; their implementation is otherwise unchanged (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:272-284`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_core.py:236-240`).
- **declaration-proven** — Texture calls default `max_texture_size` to 4096, set it after import, and verify it both before GC/save and after targeted save (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_core.py:252-258`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:248-270`).
- **inferred** — Capping each 8192 base-colour mip chain at 4096 removes 75% of its maximum mip texels. For both maps together that is a theoretical 512 MiB reduction if resident as RGBA8, or about 64–128 MiB for block-compressed BC1/BC3-or-BC7 chains; actual show residency depends on cooked pixel format, mip generation, and streaming and therefore is not measured offline.
- **measured** — The revised offline harness passes 37/37, including the requested positive one-asset call and negative two-asset/unknown-asset refusals; it started no Unreal or Blender process (`Saved/CodexConductor/ChandelierImport_20261009/test_chandelier_import_offline.py:104-125`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_harness_result.json:2-4`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_harness_result.json:16-17`).
- **inferred** — The Unreal API path, GC behavior, texture-setting read-back, targeted save, and persisted reload have not run in this offline job. The conductor must treat each live marker as required evidence, not assume it from the harness.

### Ordered conductor IMPORT calls

For each row, set `mode` to `IMPORT`, `confirm` to `IMPORT CHANDELIER IRON3`, `asset` to the exact value below, and keep `max_texture_size` at `4096`. Invoke the existing request once and require `CHANDELIER_IMPORT_IMPORT_OK` with the matching `asset`, `saved=1`, `gc=1`, and `dirty_after=0+0` before advancing.

1. `SM_Chandelier_Iron3`
2. `SM_Chandelier_Iron3_Chain`
3. `T_Chandelier_Iron3_Masks`
4. `T_Chandelier_Iron3_N`
5. `T_Chandelier_Iron3_Roughness`
6. `T_Chandelier_Iron3_BaseColor_Dusty`
7. `T_Chandelier_Iron3_BaseColor_Clean`

The first two calls are meshes, the next three are the 4096 maps, and each 8192 base-colour map runs alone last. After call 7, require `completed=7/7|state=imported`; only then run the unchanged `MAT_CHECK` and `APPLY` steps below.

## Deliverables

- **declaration-proven** — The tool exposes `DRY`, `IMPORT`, `MAT_CHECK`, `APPLY`, and `REVERT`; mutating modes have exact confirm strings and staged-record requirements (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:3-8`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_core.py:199-218`).
- **declaration-proven** — `IMPORT` uses an explicit Interchange static-mesh-only pipeline for mesh selections, makes exactly one import task per execution, refuses any folder delta other than the named target, and never overwrites (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:134-173`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:213-284`).
- **declaration-proven** — The body gate requires exactly 44 `SOCKET_Candle_*` sockets plus one `ChainAttach`, read through UE 5.8's `get_sockets_by_tag("")` route (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_core.py:84-98`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:177-179`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:223-226`).
- **declaration-proven** — The five texture profiles are dusty/clean colour sRGB, Masks RGBA linear `TC_MASKS`, normal linear `TC_NORMALMAP`, and roughness linear `TC_GRAYSCALE`/`LINEAR_GRAYSCALE` (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_core.py:25-31`).
- **declaration-proven** — No normal pixels are flipped: the supplied map and UE tangent-space convention are both DirectX (green/Y down), so `flip_green_channel=False` is set and read back (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_core.py:63-72`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:10-12`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:228-239`).
- **declaration-proven** — `MAT_CHECK` searches the chandelier, Stage Front, Infinity Stage, and PaintedSurface roots for one compatible existing master. `APPLY` reuses it or creates one master only; the master exposes dusty/clean textures, `UseClean`, dust/soot/peel strengths, AO from Masks B, and peel from Masks A (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:278-318`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:335-399`).
- **declaration-proven** — Every mutation takes a `Backups/PreChandelier…-<run>` prestate, checks exact dirty scope, saves named packages only, rereads saved values, and emits a run-id success marker (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:110-124`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:241-255`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:454-471`).
- **declaration-proven** — No placement code or level/Show save exists; only the seven imported packages, optional master, MI, and two mesh material bindings enter the save sets (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:241-243`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:454-463`).

## Offline proof tiers

- **measured** — The offline harness passed 37/37 controls; it started zero Unreal and zero Blender processes (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_harness_result.json:2-4`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_harness_result.json:16-17`).
- **measured** — Positive controls covered the 44+1 socket contract, complete synthetic sources, preview output, and import-module loading without Unreal; negative controls covered wrong socket count, bad sRGB/normal flip, existing-target overwrite, missing input, missing confirm, and pre-import APPLY (`Saved/CodexConductor/ChandelierImport_20261009/test_chandelier_import_offline.py:69-126`).
- **measured** — The named production FBXs/maps/chain JSON are absent in this git worktree, so a live `DRY` here will refuse at the source gate (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_harness_result.json:5-15`).
- **measured** — A worktree commit could not be created because this session cannot create the shared Git worktree `index.lock`; all deliverables remain uncommitted (`Saved/CodexConductor/ChandelierImport_20261009/P80_COMMIT_STATUS.txt:1`).
- **inferred** — The Interchange override, socket API, material-expression APIs, saved asset read-back, and MCP transport should work from current repo precedents, but were not executed because the brief forbids Unreal (`Docs/Conductor/codex_briefs/_house_rules.md:3-4`; `Docs/Conductor/codex_briefs/p80_chandelier_import_mis.md:3-6`).
- **inferred** — Visual aging quality is not accepted. The configurable preview utility models the same dust/soot/peel defaults, but production maps were unavailable and Gary retains look approval (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_preview.py:13-42`).
- **inferred** — No binary, saved-Unreal, runtime, rendered, package, or placement claim is made; the harness evidence is offline-only (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_harness_result.json:2-4`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_harness_result.json:16-17`).

## Ordered conductor run

1. Populate the two declared `DerivedAssets` source directories, then optionally render the look sheet offline:
   `python Saved/CodexConductor/ChandelierImport_20261009/chandelier_preview.py --dusty <Dusty> --clean <Clean> --masks <Masks> --out Saved/CodexConductor/ChandelierImport_20261009/chandelier_preview.png`
2. Keep `chandelier_import_args.json` at `{"mode":"DRY",...}` and invoke:
   `python Saved/CodexMocap/mcp_request.py tools/call --params-file Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_request.json`
3. Run the seven one-asset IMPORT calls in the Job 82 ordered table above; require each per-asset success marker and the final `completed=7/7|state=imported`.
4. Set `mode=MAT_CHECK` with no confirm; invoke once and inspect `chandelier_mat_check_latest.json`.
5. Set approved look values, `mode=APPLY`, `confirm="APPLY CHANDELIER IRON3"`; invoke once and require `CHANDELIER_IMPORT_APPLY_OK`.
6. Use `mode=REVERT`, `confirm="REVERT CHANDELIER IRON3"` only if deliberate permanent removal of this tool's recorded packages is wanted.

## Open acceptance boundary

- **inferred** — After the conductor's live run, acceptance still requires saved read-back markers and Gary's rendered inspection. Placement remains job 75 and is intentionally untouched (`Docs/Conductor/codex_briefs/p80_chandelier_import_mis.md:14-18`).
