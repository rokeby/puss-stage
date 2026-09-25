"""Save the current level only, after the Passage 3 mesh reimport dirtied it.

Reimporting the wing static meshes marks the vertical-slice map dirty because its
actors reference them. The shared import helpers require a clean editor state, so
this saves the map and nothing else, then reports the remaining dirty packages.
"""

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
    str(package) for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
if dirty_content:
    raise RuntimeError(f"Refusing to save with unrelated dirty content: {dirty_content}")

unreal.EditorLoadingAndSavingUtils.save_current_level()

remaining_maps = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
remaining_content = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
unreal.log(
    "P03_SAVE_CURRENT_LEVEL"
    f"|world={world_path}|dirty_maps={len(remaining_maps)}|dirty_content={len(remaining_content)}"
)
if remaining_maps or remaining_content:
    raise RuntimeError("Editor still reports dirty packages after saving the level")
