# Job 131 stage-front 3D tools

Offline-authored only. The author did not run Unreal or Blender. The conductor
runs each request through `MCPBlueprintsGenerator.MCPBlueprintsGeneratorToolset`
tool `ExecuteProjectPythonFile` after editing the appropriate args JSON.

## Boundary

`IMPORT` accepts exactly one selector and performs exactly one
`import_asset_tasks([task])` call, followed by garbage collection and a targeted
save. Textures are capped at 4096. Interchange pipeline objects are used because
UE 5.8 ignores `FbxImportUI`. A multi-object FBX that creates more than the one
expected package is a hard stop; no stray is deleted.

The current source set is intentionally incomplete. These scene-prepared,
single-object files must be exported later from the approved Blender authority:

- `SM_StageFront_Crest.fbx` with the v3 rotation/scale baked into mesh data;
- `SM_StageFront_Column.fbx`, centred, bottomed and normalized to 14 m;
- `SM_StageFront_CatCandelabra.fbx`, centred, bottomed and normalized to 5.5 m.

Do not substitute the raw Rodin GLBs: they do not embody those assembly-space
preparations. The three architecture FBXs and all required texture sets exist.

## Ordered execution

1. Run the import tool `DRY` using `stage_front_3d_import_run.py`.
2. For each available selector below, set mode `IMPORT`, confirm
   `IMPORT STAGEFRONT3D`, and execute **one selector in one MCP call**. Return to
   the editor/event loop between calls; never wrap these in one project-Python
   loop.
3. After all six mesh selectors and their 30 texture selectors exist, run one
   `MATERIAL` call per piece with confirm `MATERIAL STAGEFRONT3D`. An existing
   `master_path` is only reused after parameter read-back; otherwise the default
   master is created. Every MI is create-only. Existing material nodes are never
   changed or deleted.
4. Run import `VERIFY`.
5. Run placement `DRY`, then `APPLY` with `APPLY STAGEFRONT3D`.
6. In a later clean call, run placement `VERIFY`. Only after that read-back is
   the saved assembly verified.

Piece order: `arch`, `wall`, `gilt`, `crest`, `column`, `cat`.

For each piece, selectors are:

```text
mesh:<piece>
tex:<piece>:BaseColor_Dusty
tex:<piece>:BaseColor_Clean
tex:<piece>:Masks
tex:<piece>:N
tex:<piece>:Roughness
```

Import rollback is `REVERT STAGEFRONT3D`; placement rollback is
`REVERT STAGEFRONT3D PLACE`. Both require the durable ownership record, create a
new backup first, refuse foreign references/ownership drift, and affect only
recorded packages or tagged actors.

## Offline harness

```powershell
python Saved\CodexConductor\StageFront3D_20261010\test_stage_front_3d_offline.py
```

Expected: `STAGEFRONT3D_HARNESS_PASS|pass=41|fail=0|unreal=0|blender=0`.
