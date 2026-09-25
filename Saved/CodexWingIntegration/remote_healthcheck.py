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

dirty_content = [
    str(package)
    for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
dirty_maps = [
    str(package)
    for package in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
]
payload = {
    "status": "ok",
    "world": world_path,
    "dirty_content": dirty_content,
    "dirty_maps": dirty_maps,
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexWingIntegration",
    "remote_healthcheck.json",
)
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)
unreal.log(
    "PUSS_REMOTE_HEALTHCHECK_SUCCESS"
    f"|world={world_path}|dirty_content={len(dirty_content)}|dirty_maps={len(dirty_maps)}"
)
