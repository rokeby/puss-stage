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


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
world_path = object_path(world).split(".", 1)[0]
if world_path != EXPECTED_WORLD or editor.get_game_world() is not None:
    raise RuntimeError(f"Unsafe editor state: world={world_path}, game_world={editor.get_game_world()}")

dirty_content = [str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
dirty_maps = [str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if dirty_content or dirty_maps:
    raise RuntimeError(f"Inspection requires clean editor: {dirty_content}/{dirty_maps}")

cdo = unreal.get_default_object(unreal.InfinityStageCurtainRig)
property_names = (
    "curtain_active",
    "follow_player_camera",
    "use_authored_open_closed_transforms",
    "curtain_distance_cm",
    "curtain_open_relative_transform",
    "curtain_closed_relative_transform",
    "curtain_progress",
    "curtain_mesh",
)
properties = {}
for property_name in property_names:
    try:
        value = cdo.get_editor_property(property_name)
        properties[property_name] = object_path(value)
    except Exception as exc:
        properties[property_name] = f"<error: {exc}>"

curtain_mesh = cdo.get_editor_property("curtain_mesh")
float_section_class = getattr(unreal, "MovieSceneFloatSection", None)
payload = {
    "status": "ok",
    "world": world_path,
    "native_class": object_path(unreal.InfinityStageCurtainRig),
    "properties": properties,
    "curtain_mesh_class": curtain_mesh.get_class().get_name(),
    "curtain_static_mesh": object_path(curtain_mesh.get_editor_property("static_mesh")),
    "float_section_exists": float_section_class is not None,
    "float_section_channel_methods": sorted(
        name for name in dir(float_section_class) if "channel" in name.lower()
    ) if float_section_class is not None else [],
    "float_section_range_methods": sorted(
        name for name in dir(float_section_class) if "range" in name.lower() or "frame" in name.lower()
    ) if float_section_class is not None else [],
}

output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCurtainAuthoring",
    "inspect_rig_and_float_api.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log("PUSS_CURTAIN_RIG_FLOAT_API_SUCCESS|dirty_content=0|dirty_maps=0")
