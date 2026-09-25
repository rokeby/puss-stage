"""Discard only the verifier-induced dirty production map package; never save it."""

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"


def package_name(value):
    try:
        return str(value.get_name())
    except Exception:
        return str(value)


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
world_path = world.get_path_name().split(".", 1)[0] if world is not None else ""
if world_path != EXPECTED_WORLD or editor.get_game_world() is not None:
    raise RuntimeError(f"Unsafe editor state: world={world_path}, game_world={editor.get_game_world()}")

dirty_content = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
dirty_maps = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
actual_content = [package_name(value) for value in dirty_content]
actual_maps = [package_name(value) for value in dirty_maps]
if actual_content or actual_maps != [EXPECTED_WORLD]:
    raise RuntimeError(
        f"Refusing unexpected discard scope: content={actual_content}, maps={actual_maps}"
    )

result = unreal.EditorLoadingAndSavingUtils.reload_packages(dirty_maps)
if result is False:
    raise RuntimeError("reload_packages returned false")

remaining_content = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
remaining_maps = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
]
reloaded_world = editor.get_editor_world()
reloaded_world_path = (
    reloaded_world.get_path_name().split(".", 1)[0] if reloaded_world is not None else ""
)
if remaining_content or remaining_maps or reloaded_world_path != EXPECTED_WORLD:
    raise RuntimeError(
        f"Dirty-map discard incomplete: content={remaining_content}, maps={remaining_maps}, "
        f"world={reloaded_world_path}"
    )

unreal.log(
    "PUSS_CURTAIN_VERIFY_MAP_DIRTY_DISCARDED"
    f"|map={EXPECTED_WORLD}|saved=0|dirty_content=0|dirty_maps=0"
)
