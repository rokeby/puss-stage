import json
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
if world is None:
    raise RuntimeError("No editor world is open")
world_path = world.get_path_name().split(".", 1)[0]
if world_path != EXPECTED_WORLD:
    raise RuntimeError(f"Unexpected editor world: {world_path}")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE is active")

dirty_content_before = [
    str(package)
    for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
dirty_maps_before = [
    str(package)
    for package in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
]
if dirty_content_before or dirty_maps_before:
    raise RuntimeError(
        "Editor is not clean before Cue Desk verification: "
        f"content={dirty_content_before}, maps={dirty_maps_before}"
    )

unreal.SystemLibrary.execute_console_command(world, "InfinityStage.OpenCueDesk")

dirty_content_after = [
    str(package)
    for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
dirty_maps_after = [
    str(package)
    for package in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
]
if dirty_content_after or dirty_maps_after:
    raise RuntimeError(
        "Opening the Cue Desk dirtied packages: "
        f"content={dirty_content_after}, maps={dirty_maps_after}"
    )

payload = {
    "status": "ok",
    "world": world_path,
    "cue_desk_open_command": True,
    "dirty_content_before": dirty_content_before,
    "dirty_maps_before": dirty_maps_before,
    "dirty_content_after": dirty_content_after,
    "dirty_maps_after": dirty_maps_after,
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCueDeskTransformUI",
    "verify_cue_desk_transform_ui.json",
)
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(
    "CUE_DESK_TRANSFORM_UI_MCP_VERIFY_SUCCESS"
    f"|world={world_path}|cue_desk_open=1|dirty_content=0|dirty_maps=0"
)
