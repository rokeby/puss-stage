import json
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"


def object_path(value):
    if value is None:
        return ""
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def describe(owner, attribute):
    value = getattr(owner, attribute, None)
    return {
        "exists": value is not None,
        "doc": getattr(value, "__doc__", "") or "",
        "text_signature": getattr(value, "__text_signature__", "") or "",
    }


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
world_path = object_path(world).split(".", 1)[0]
if world_path != EXPECTED_WORLD:
    raise RuntimeError(f"Unexpected editor world: {world_path}")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE is active")

before_content = [str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
before_maps = [str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if before_content or before_maps:
    raise RuntimeError(f"Inspection requires a clean editor: content={before_content}, maps={before_maps}")

sequence = unreal.load_asset("/Game/InfinityStage/Interactions/LS_Interaction_Template")
if not sequence:
    raise RuntimeError("Missing template sequence")

targets = (
    ("BlueprintEditorLibrary.create_blueprint_asset_with_parent", unreal.BlueprintEditorLibrary, "create_blueprint_asset_with_parent"),
    ("BlueprintEditorLibrary.compile_blueprint", unreal.BlueprintEditorLibrary, "compile_blueprint"),
    ("Blueprint.generated_class", unreal.Blueprint, "generated_class"),
    ("LevelSequence.add_spawnable_from_class", sequence, "add_spawnable_from_class"),
    ("LevelSequence.add_root_folder_to_sequence", sequence, "add_root_folder_to_sequence"),
    ("MovieSceneBindingProxy.add_track", unreal.MovieSceneBindingProxy, "add_track"),
    ("MovieSceneBindingProxy.set_display_name", unreal.MovieSceneBindingProxy, "set_display_name"),
    ("MovieSceneFloatTrack.add_section", unreal.MovieSceneFloatTrack, "add_section"),
    ("MovieSceneFloatTrack.set_property_name_and_path", unreal.MovieSceneFloatTrack, "set_property_name_and_path"),
    ("MovieSceneSection.set_range", unreal.MovieSceneSection, "set_range"),
    ("MovieSceneSection.get_channels", unreal.MovieSceneSection, "get_channels"),
    ("MovieSceneScriptingFloatChannel.add_key", unreal.MovieSceneScriptingFloatChannel, "add_key"),
    ("MovieSceneScriptingFloatKey.get_time", unreal.MovieSceneScriptingFloatKey, "get_time"),
    ("MovieSceneScriptingFloatKey.get_value", unreal.MovieSceneScriptingFloatKey, "get_value"),
    ("MovieSceneFolder.constructor", unreal, "MovieSceneFolder"),
    ("MovieSceneFolder.set_folder_name", unreal.MovieSceneFolder, "set_folder_name"),
    ("MovieSceneFolder.add_child_object_binding", unreal.MovieSceneFolder, "add_child_object_binding"),
)

payload = {
    "status": "ok",
    "world": world_path,
    "targets": {name: describe(owner, attribute) for name, owner, attribute in targets},
    "blueprint_generated_names": sorted(
        name for name in dir(unreal.Blueprint) if "generated" in name.lower() or "class" in name.lower()
    ),
    "binding_display_names": sorted(name for name in dir(unreal.MovieSceneBindingProxy) if "display" in name.lower()),
    "key_interpolation_names": sorted(name for name in dir(unreal.MovieSceneKeyInterpolation) if name.isupper()),
}

after_content = [str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
after_maps = [str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if after_content != before_content or after_maps != before_maps:
    raise RuntimeError(
        f"Inspection changed dirty state: before={before_content}/{before_maps}, after={after_content}/{after_maps}"
    )
payload["dirty_content"] = after_content
payload["dirty_maps"] = after_maps

output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCurtainAuthoring",
    "inspect_api_signatures.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log("PUSS_CURTAIN_API_SIGNATURES_SUCCESS|dirty_content=0|dirty_maps=0")
