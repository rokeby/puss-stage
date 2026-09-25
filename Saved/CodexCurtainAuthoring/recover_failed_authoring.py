import json
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
BLUEPRINT_PATH = "/Game/InfinityStage/Interactions/BP_InfinityStageSequenceCurtain"


def package_path(value):
    try:
        return value.get_path_name().split(".", 1)[0]
    except Exception:
        return str(value).split(".", 1)[0]


def package_name(value):
    try:
        return str(value.get_name())
    except Exception:
        return str(value)


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world_path = package_path(editor.get_editor_world())
if world_path != EXPECTED_WORLD or editor.get_game_world() is not None:
    raise RuntimeError(f"Unsafe editor state: world={world_path}, game_world={editor.get_game_world()}")

dirty_before = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
dirty_maps_before = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
]
if set(dirty_before) != {BLUEPRINT_PATH} or dirty_maps_before:
    raise RuntimeError(
        f"Refusing cleanup outside exact failed Blueprint scope: "
        f"content={dirty_before}, maps={dirty_maps_before}"
    )
if not unreal.EditorAssetLibrary.does_asset_exist(BLUEPRINT_PATH):
    raise RuntimeError(f"Expected failed Blueprint is absent: {BLUEPRINT_PATH}")
if not unreal.EditorAssetLibrary.delete_asset(BLUEPRINT_PATH):
    raise RuntimeError(f"Could not delete failed Blueprint: {BLUEPRINT_PATH}")

dirty_after = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
dirty_maps_after = [
    package_name(value)
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
]
if dirty_after or dirty_maps_after or unreal.EditorAssetLibrary.does_asset_exist(BLUEPRINT_PATH):
    raise RuntimeError(
        f"Failed Blueprint cleanup incomplete: content={dirty_after}, "
        f"maps={dirty_maps_after}, exists={unreal.EditorAssetLibrary.does_asset_exist(BLUEPRINT_PATH)}"
    )

payload = {
    "status": "ok",
    "world": world_path,
    "deleted": BLUEPRINT_PATH,
    "dirty_before": dirty_before,
    "dirty_maps_before": dirty_maps_before,
    "dirty_after": dirty_after,
    "dirty_maps_after": dirty_maps_after,
    "transform_doc": getattr(unreal.Transform, "__doc__", "") or "",
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCurtainAuthoring",
    "recover_failed_authoring.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(
    "PUSS_CURTAIN_FAILED_AUTHORING_RECOVERED"
    f"|deleted={BLUEPRINT_PATH}|dirty_content=0|dirty_maps=0"
)
