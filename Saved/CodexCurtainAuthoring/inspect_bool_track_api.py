import inspect
import json
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"


def describe(owner, attribute):
    value = getattr(owner, attribute, None)
    row = {"exists": value is not None}
    if value is None:
        return row
    row["repr"] = str(value)
    try:
        row["signature"] = str(inspect.signature(value))
    except Exception as exc:
        row["signature_error"] = str(exc)
    row["doc"] = getattr(value, "__doc__", "") or ""
    return row


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
world_path = world.get_path_name().split(".", 1)[0]
if world_path != EXPECTED_WORLD:
    raise RuntimeError(f"Unexpected editor world: {world_path}")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE is active")
before_content = [
    str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
before_maps = [
    str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
]
if before_content or before_maps:
    raise RuntimeError(
        f"Inspection requires a clean editor: content={before_content}, maps={before_maps}"
    )

payload = {
    "status": "ok",
    "world": world_path,
    "bool_channel_methods": sorted(
        name for name in dir(unreal.MovieSceneScriptingBoolChannel)
        if not name.startswith("_")
    ),
    "bool_key_methods": sorted(
        name for name in dir(unreal.MovieSceneScriptingBoolKey)
        if not name.startswith("_")
    ),
    "targets": {
        "channel_add_key": describe(
            unreal.MovieSceneScriptingBoolChannel, "add_key"
        ),
        "channel_set_default": describe(
            unreal.MovieSceneScriptingBoolChannel, "set_default"
        ),
        "channel_get_default": describe(
            unreal.MovieSceneScriptingBoolChannel, "get_default"
        ),
        "track_set_property": describe(
            unreal.MovieSceneBoolTrack, "set_property_name_and_path"
        ),
    },
}

after_content = [
    str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
after_maps = [
    str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
]
if after_content != before_content or after_maps != before_maps:
    raise RuntimeError(
        f"Inspection changed dirty state: before={before_content}/{before_maps}, "
        f"after={after_content}/{after_maps}"
    )
payload["dirty_content"] = after_content
payload["dirty_maps"] = after_maps

output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCurtainAuthoring",
    "inspect_bool_track_api.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log("PUSS_CURTAIN_BOOL_API_INSPECT_SUCCESS|dirty_content=0|dirty_maps=0")
