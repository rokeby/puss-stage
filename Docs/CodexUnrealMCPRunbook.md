# Codex + Unreal/MCP Runbook

Last validated: 28 August 2026, Unreal Engine 5.8 on Windows.

Current project: `E:\PussStage`. Current engine:
`D:\Unreal Engine\UE_5.8`. The older macOS commands below are retained only as
historical fallback notes.

This note records the reliable way a Codex session can inspect and edit the open
PussStage Unreal project. It also retains the historical Passage 1 wing-state
record from 13 August.

## Mental model

MCP is a control/transport layer. It does not own the stage-wing assignments.

For Infinity Stage, the authoritative ordered cue data is serialized in the Show Asset:

`/Game/InfinityStage/Dev/DA_InfinityStage_V1Show`

The current vertical-slice level is:

`/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice`

`AInfinityStagePassageActor` instances materialize the Show Asset's Passage rows into visible level instances. Therefore a complete wing change is:

1. Inspect the Show Asset.
2. Edit only the intended cue rows.
3. Call `materialize_passage()` on the affected Passage Actor.
4. Save the Show Asset.
5. Save the affected current level.
6. Read the Show Asset back and verify exact assignments.

Rebuilding the managed Master Sequence is necessary after timing, ordering or duration changes. A mesh-only reassignment does not require a Master rebuild.

## Standard no-UI loopback route: Unreal MCP project Python

The project MCP endpoint is configured in `.codex/config.toml`:

```toml
[mcp_servers.unreal-mcp]
url = "http://127.0.0.1:8000/mcp"
```

Editor auto-start is configured in
`Config/DefaultEditorPerProjectUserSettings.ini` with
`bAutoStartServer=True` and `ServerPortNumber=8000`. A normal project launch now
starts the listener in the same Unreal Editor process; do not start a second
Editor merely to obtain MCP.

The current standard for deterministic Show/level automation is the local MCP
project-Python executor:

- toolset:
  `MCPBlueprintsGenerator.MCPBlueprintsGeneratorToolset`
- tool: `ExecuteProjectPythonFile`
- argument: a `.py` path relative to `<Project>/Saved`, for example
  `CodexWingIntegration/remote_healthcheck.py`
- transport: the loopback-only MCP endpoint above; no desktop focus, clicks or
  clipboard are involved.

The executor is intentionally narrow. It rejects absolute paths, traversal,
non-Python files and paths outside the project `Saved/` directory. It runs the
file inside the already-open Editor and emits
`PROJECT_PYTHON_EXEC_SUCCESS|<relative-path>` only after Python returns without
an exception. Each task script must also emit its own domain-specific success
marker, because the transport marker proves execution rather than correct
authoring state.

A minimal call is:

```json
{
  "toolset_name": "MCPBlueprintsGenerator.MCPBlueprintsGeneratorToolset",
  "tool_name": "ExecuteProjectPythonFile",
  "arguments": {
    "relativeSavedPath": "CodexWingIntegration/remote_healthcheck.py"
  }
}
```

Preconditions are one canonical Editor process, the intended world open, PIE/SIE
stopped, the MCP plugin built and loaded, and a reviewed script under `Saved/`.
Run the health check first and require `PUSS_REMOTE_HEALTHCHECK_SUCCESS` with the
expected world and zero dirty packages. For an authoring change, run a separate
preflight, import/configure only the scoped content, save that content root,
mutate the Show, materialize exactly the affected actor, save only the Show and
current level, then run a separate read-only verifier.

When callable semantic Unreal MCP tools are available, still prefer them for
their supported inspect/apply/compile operations. Retain exact Unreal object
paths and never treat a successful request as proof of saved state.

Epic Python Remote Execution remains a diagnostic fallback at port 6766. The
guarded MCP project-Python executor on port 8000 is the proven Windows route and
has repeatedly verified the production world, PIE/SIE state and zero dirty
packages. Do not substitute the older multicast route unless MCP is unavailable
and that fallback passes its own discovery and health checks.

## Windows headless plugin build and test (no Editor UI)

Validated 28 August 2026. Both commands require the interactive Editor to be
**closed**: never run a second Unreal process against a map open for editing.

The project has no `Source/` directory of its own, so C++ changes mean
recompiling the plugin modules into
`Plugins/InfinityStage/Binaries/Win64/`. Live Coding or a hot-reload DLL is not a
clean verification build; restart the Editor to load the base DLLs.

```bat
"D:\Unreal Engine\UE_5.8\Engine\Build\BatchFiles\Build.bat" PussStageEditor Win64 Development -Project="E:\PussStage\PussStage.uproject" -waitmutex -NoUBA
```

```bat
"D:\Unreal Engine\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" "E:\PussStage\PussStage.uproject" -Unattended -NoP4 -NullRHI -NoSplash -ExecCmds="Automation RunTests InfinityStage; Quit" -TestExit="Automation Test Queue Empty" -AbsLog="E:\PussStage\Saved\Logs\<RunName>.log" -stdout -FullStdOutLogOutput
```

Require `**** TEST COMPLETE. EXIT CODE: 0 ****` and zero `Result={Fail}` lines.
The process exit code is `0` on success and `3` when any test fails.

An `Error`-level log emitted during a test fails that test even when its
assertions pass. A test that deliberately exercises a refusal path must declare
it, for example
`AddExpectedErrorPlain(TEXT("keeping the previous materialization"))`.

This route builds and tests only; it opens no map and saves no content. Use the
loopback MCP route above for anything that reads or writes authoring data.

The latest full run is 42/43. `SavedFixturePIE` failed its fully-lowered curtain
check at the hidden-changeover marker, although the focused post-staging rerun
passed. Retain both logs and do not describe the suite as green until the full
run passes consistently.

## Historical last-resort fallback: the open Editor's Python executor

The Unreal window has a `Python` executor at the bottom beside **Output Log**. It accepts either Python source or an absolute `.py` filename. A reliable workflow is:

1. Stop PIE before editing authoring data.
2. Write a temporary, deterministic script under the project `Saved/` directory.
3. Bring Unreal to the front and visually confirm the Python executor is visible.
4. Click the executor, select all, paste the script's absolute path, and press Return.
5. Check Unreal's native log for the filename, errors and a unique success marker.
6. Run a separate read-only verifier through the same executor.
7. Remove the temporary helper scripts after verification.

For the older macOS layout used during validation:

- macOS logical display size: `1920 x 1080`
- `screencapture` image size: `3840 x 2160` (Retina 2x)
- Python executor click point in CoreGraphics logical coordinates: approximately `(520, 1063)`

Coordinates are only a historical macOS fallback and are layout-dependent. Do
not reuse them on Windows. Take a screenshot before any UI-driven fallback and
use it only after the user has authorized control of the open Editor.

Paste the absolute script path as one clipboard value. Avoid typing long Python programs directly into the one-line field. A stale or incorrectly focused input can corrupt the pasted text; one observed symptom was an unrelated string being evaluated as Python and producing `SyntaxError`. A failed launch should leave no success marker and no package timestamp change.

## Unreal logging

The current Windows live editor log is:

`E:\PussStage\Saved\Logs\PussStage.log`

Command-line tests should always use a named `-AbsLog` beneath
`E:\PussStage\Saved\Logs\`. Search the named log for the test result and the
task's explicit success marker; do not infer success from process completion
alone.

The older macOS live editor log was:

`~/Library/Logs/Unreal Engine/PussStageEditor/PussStage.log`

There may be multiple numbered or backup logs, so locate the active file by recent modification time or by searching all files for the unique marker/script filename.

Useful checks:

```sh
rg -n 'MY_TASK_SUCCESS|MyScript.py|LogPython: Error|Traceback' \
  "$HOME/Library/Logs/Unreal Engine/PussStageEditor/PussStage.log"
```

Also compare the target `.uasset`/`.umap` modification times before and after a save. Neither log success nor timestamps alone replace reading back the actual Unreal properties.

## Safe Unreal Python patterns

Load exact object paths and assert every assumption before editing:

```python
show = unreal.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
if show is None:
    raise RuntimeError("Show Asset did not load")

mesh = unreal.load_asset("/Game/Wings/StaticMeshes/SM_L_1_roccoco")
if mesh is None or not isinstance(mesh, unreal.StaticMesh):
    raise RuntimeError("Expected Static Mesh did not load")
```

For nested Unreal structs such as cue → wing pair → panel, update the nested value and explicitly assign each changed struct back to its parent. Finally assign the full `cues` array back to the Show Asset. Do not assume mutating a Python-side nested struct view will serialize automatically.

Make scripts idempotent. Target rows by a stable label/passage identity, assert the expected row count, and assign the intended final values directly. This makes a rerun safe after a failure halfway through.

In UE 5.8, `str(FGuid)` may render an address-like struct description rather
than a stable GUID. Do not use that string for identity or fingerprints. Prefer
the stable cue labels plus exact expected indexes/counts; if a GUID is required,
serialize its numeric fields explicitly.

The Python field for `FInfinityPanelDesign::LocalTransform` is
`local_transform`, not `transform`. Preserve each row's existing transform and
facing policy when a task changes only its mesh and material/image settings.

Avoid `MaterialEditingLibrary.get_material_instance_*_parameter_value()` in a
read-only verifier on this build: it marked every inspected material instance
dirty. Read the serialized `texture_parameter_values` and
`scalar_parameter_values` arrays instead. Material recompilation can also mark
new instances dirty shortly after the first import save; if that happens,
assert that every dirty package is under the just-imported content root, perform
one recursive targeted settle-save of that root, and re-check that the whole
Editor is clean. Never broaden this to **Save All**.

`InfinityStageShowAsset` does not expose `mark_package_dirty()` to Unreal Python in this build. Calling it caused an `AttributeError`. It is redundant when editor properties are changed and the asset is explicitly saved.

The proven save calls are:

```python
unreal.EditorAssetLibrary.save_asset(show_path, only_if_is_dirty=False)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
```

`EditorLevelLibrary.save_current_level()` still works but is deprecated in UE
5.8. Saving the level may show a source-control checkout warning even when
Unreal subsequently writes the package successfully. Confirm the `Saving
Package`/`Moving output files` log lines, unique marker and Unreal read-back.

Avoid **Save All** when the editor already contains unrelated dirty packages. Save only the Show Asset and the affected level. Be aware that saving the current level also persists any pre-existing unsaved edits in that level; inspect the dirty state and confirm scope with the user when it is not already authorized.

## Materializing an affected Passage

The Passage 1 actor used during validation had:

- label: `Passage 01 — Fixed Wings`
- class name: `InfinityStagePassageActor`
- Show Asset: `/Game/InfinityStage/Dev/DA_InfinityStage_V1Show`

The actor can be found with `EditorActorSubsystem.get_all_level_actors()`. Match class, label and Show Asset before calling `materialize_passage()`. Assert exactly one actor matched and require a truthy return value. Materialization preserves the prior visible instances if its own implementation reports failure, but the automation should still abort and avoid claiming success.

## Passage 1 wing state recorded on 13 August 2026

Passage 1 contains 48 labeled wing-pair cues (`P01 Wing 001` through `P01 Wing 048`). They now repeat this three-row sequence:

1. Left `/Game/Wings/StaticMeshes/SM_L_1_roccoco`; Right `/Game/Wings/StaticMeshes/SM_R__1_roccoco`
2. Left `/Game/Wings/StaticMeshes/SM_L_pillar1_bw`; Right `/Game/Wings/StaticMeshes/SM_R_Pillar1_bw`
3. Left `/Game/Wings/StaticMeshes/SM_L_Pillar2_bw`; Right `/Game/Wings/StaticMeshes/SM_R_Pillar2_bw`

All 48 rows have `has_top = True` and use:

`/Game/Wings/MiscOriginal/StaticMeshes/SM_Ceiling_bw`

The saved distribution is 16 Rococo pairs, 16 Pillar1 BW pairs and 16 Pillar2 BW pairs. Left/right handedness is preserved. The change was materialized once and both the Show Asset and vertical-slice level were saved.

The successful mutation marker was:

```text
P01_REASSIGN_SUCCESS|rows=48|rococo=16|pillar1_bw=16|pillar2_bw=16|tops=48|materialized=1|level_saved=1
```

The independent read-back marker was:

```text
P01_VERIFY_SUCCESS|rows=48|pattern=rococo,pillar1_bw,pillar2_bw|top=SM_Ceiling_bw
```

## Checklist for future mutations

- Confirm correct project, map, editor mode and Unreal version.
- Stop PIE.
- Inspect authoritative data and exact asset paths.
- Note pre-existing dirty packages; avoid broad saves.
- Use a deterministic/idempotent script with count and identity assertions.
- Assign nested Unreal structs back to their parents.
- Materialize exactly the affected Passage Actor(s).
- Save the precise Show Asset and affected level.
- Search the active Unreal log for errors and a unique success marker.
- Read all affected rows back from Unreal and compare exact object paths.
- Remove temporary scripts; retain this runbook and update it with newly proven behavior.
