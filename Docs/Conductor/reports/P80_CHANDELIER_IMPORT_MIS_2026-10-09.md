# P80 chandelier import + aged MI — offline delivery report

## Deliverables

- **declaration-proven** — The tool exposes `DRY`, `IMPORT`, `MAT_CHECK`, `APPLY`, and `REVERT`; mutating modes have exact confirm strings and staged-record requirements (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:3-8`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_core.py:199-218`).
- **declaration-proven** — `IMPORT` uses an explicit Interchange static-mesh-only pipeline, makes exactly one import task per call, refuses any folder delta other than the named target, and never overwrites (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:131-170`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:212-255`).
- **declaration-proven** — The body gate requires exactly 44 `SOCKET_Candle_*` sockets plus one `ChainAttach`, read through UE 5.8's `get_sockets_by_tag("")` route (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_core.py:84-98`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:177-179`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:223-226`).
- **declaration-proven** — The five texture profiles are dusty/clean colour sRGB, Masks RGBA linear `TC_MASKS`, normal linear `TC_NORMALMAP`, and roughness linear `TC_GRAYSCALE`/`LINEAR_GRAYSCALE` (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_core.py:25-31`).
- **declaration-proven** — No normal pixels are flipped: the supplied map and UE tangent-space convention are both DirectX (green/Y down), so `flip_green_channel=False` is set and read back (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_core.py:63-72`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:10-12`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:228-239`).
- **declaration-proven** — `MAT_CHECK` searches the chandelier, Stage Front, Infinity Stage, and PaintedSurface roots for one compatible existing master. `APPLY` reuses it or creates one master only; the master exposes dusty/clean textures, `UseClean`, dust/soot/peel strengths, AO from Masks B, and peel from Masks A (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:278-318`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:335-399`).
- **declaration-proven** — Every mutation takes a `Backups/PreChandelier…-<run>` prestate, checks exact dirty scope, saves named packages only, rereads saved values, and emits a run-id success marker (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:110-124`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:241-255`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:454-471`).
- **declaration-proven** — No placement code or level/Show save exists; only the seven imported packages, optional master, MI, and two mesh material bindings enter the save sets (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:241-243`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import.py:454-463`).

## Offline proof tiers

- **measured** — The offline harness passed 27/27 controls; it started zero Unreal and zero Blender processes (`Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_harness_result.json:2-4`; `Saved/CodexConductor/ChandelierImport_20261009/chandelier_import_harness_result.json:16-17`).
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
3. Set `mode=IMPORT`, `confirm="IMPORT CHANDELIER IRON3"`; invoke once and require `CHANDELIER_IMPORT_IMPORT_OK`.
4. Set `mode=MAT_CHECK` with no confirm; invoke once and inspect `chandelier_mat_check_latest.json`.
5. Set approved look values, `mode=APPLY`, `confirm="APPLY CHANDELIER IRON3"`; invoke once and require `CHANDELIER_IMPORT_APPLY_OK`.
6. Use `mode=REVERT`, `confirm="REVERT CHANDELIER IRON3"` only if deliberate permanent removal of this tool's recorded packages is wanted.

## Open acceptance boundary

- **inferred** — After the conductor's live run, acceptance still requires saved read-back markers and Gary's rendered inspection. Placement remains job 75 and is intentionally untouched (`Docs/Conductor/codex_briefs/p80_chandelier_import_mis.md:14-18`).
