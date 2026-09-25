import json
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
CURTAIN_ASSET = "/Game/Scenes/Wings/FireSafetyCurtain/StaticMeshes/SM_FireSafetyCurtain_01"
SEQUENCE_PATH = "/Game/InfinityStage/Interactions/LS_Interaction_Template"


def object_path(value):
    if value is None:
        return ""
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def filtered_dir(value, terms):
    return sorted(name for name in dir(value) if any(term in name.lower() for term in terms))


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

mesh = unreal.load_asset(CURTAIN_ASSET)
sequence = unreal.load_asset(SEQUENCE_PATH)
if not mesh or not sequence:
    raise RuntimeError(f"Missing inspection asset: mesh={mesh}, sequence={sequence}")

bounds = {}
for label, callable_value in (
    ("get_bounding_box", lambda: mesh.get_bounding_box()),
    ("get_bounds", lambda: mesh.get_bounds()),
    ("editor_static_mesh_bounds", lambda: unreal.EditorStaticMeshLibrary.get_bounding_box(mesh)),
):
    try:
        bounds[label] = str(callable_value())
    except Exception as exc:
        bounds[f"{label}_error"] = str(exc)

class_rows = {}
for name in (
    "LevelSequence",
    "MovieSceneBindingProxy",
    "MovieSceneFloatTrack",
    "MovieSceneBoolTrack",
    "MovieSceneFolder",
    "MovieSceneScriptingFloatChannel",
    "BlueprintFactory",
    "BlueprintEditorLibrary",
    "SubobjectDataSubsystem",
):
    value = getattr(unreal, name, None)
    class_rows[name] = filtered_dir(
        value,
        ("spawn", "binding", "track", "section", "channel", "key", "folder", "property", "blueprint", "subobject", "parent"),
    ) if value is not None else ["<missing>"]

payload = {
    "status": "ok",
    "world": world_path,
    "mesh": object_path(mesh),
    "mesh_bounds": bounds,
    "mesh_methods": filtered_dir(mesh, ("bound", "box", "extent", "socket")),
    "sequence": object_path(sequence),
    "sequence_methods": filtered_dir(sequence, ("spawn", "binding", "track", "folder", "possess")),
    "movie_scene_methods": filtered_dir(sequence.get_movie_scene(), ("spawn", "binding", "track", "folder", "possess")),
    "classes": class_rows,
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
    "inspect_authoring_api.json",
)
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(
    "PUSS_CURTAIN_AUTHORING_API_SUCCESS"
    f"|mesh={CURTAIN_ASSET}|dirty_content=0|dirty_maps=0"
)