import json
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MESH_PATH = (
    "/Game/Scenes/Wings/FireSafetyCurtain/StaticMeshes/"
    "SM_FireSafetyCurtain_01.SM_FireSafetyCurtain_01"
)
BLUEPRINT_PATH = "/Game/InfinityStage/Interactions/BP_InfinityStageSequenceCurtain"


def object_path(value):
    if value is None:
        return ""
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def property_value(value, name):
    try:
        result = value.get_editor_property(name)
        if hasattr(result, "get_path_name"):
            return object_path(result)
        if isinstance(result, (bool, int, float, str)):
            return result
        return str(result)
    except Exception as exc:
        return f"<unavailable: {exc}>"


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
world_path = object_path(world).split(".", 1)[0]
if world_path != EXPECTED_WORLD:
    raise RuntimeError(f"Unexpected editor world: {world_path}")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE is active")

dirty_content = [
    str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
dirty_maps = [
    str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
]
if dirty_content or dirty_maps:
    raise RuntimeError(
        f"Inspection requires a clean editor: content={dirty_content}, maps={dirty_maps}"
    )

mesh = unreal.load_asset(MESH_PATH)
if not mesh:
    raise RuntimeError(f"Missing curtain mesh: {MESH_PATH}")
blueprint = unreal.load_asset(BLUEPRINT_PATH)
if not blueprint:
    raise RuntimeError(f"Missing curtain Blueprint: {BLUEPRINT_PATH}")

material_rows = []
for slot_index, slot in enumerate(mesh.get_editor_property("static_materials")):
    interface = slot.get_editor_property("material_interface")
    base_material = None
    if interface and hasattr(interface, "get_base_material"):
        try:
            base_material = interface.get_base_material()
        except Exception:
            base_material = None
    if base_material is None and interface and interface.get_class().get_name() == "Material":
        base_material = interface
    material_rows.append(
        {
            "slot_index": slot_index,
            "slot_name": str(slot.get_editor_property("material_slot_name")),
            "interface": object_path(interface),
            "interface_class": interface.get_class().get_name() if interface else "",
            "base_material": object_path(base_material),
            "base_two_sided": property_value(base_material, "two_sided")
            if base_material
            else "",
            "base_blend_mode": property_value(base_material, "blend_mode")
            if base_material
            else "",
            "instance_base_overrides": property_value(
                interface, "base_property_overrides"
            )
            if interface
            else "",
        }
    )

generated_class = blueprint.generated_class()
cdo = unreal.get_default_object(generated_class)
component = cdo.get_editor_property("curtain_mesh")
motion_root = cdo.get_editor_property("curtain_motion_root")

component_row = {
    "path": object_path(component),
    "static_mesh": object_path(component.get_editor_property("static_mesh")),
    "visible": property_value(component, "visible"),
    "hidden_in_game": property_value(component, "hidden_in_game"),
    "reverse_culling": property_value(component, "reverse_culling"),
    "relative_location": property_value(component, "relative_location"),
    "relative_rotation": property_value(component, "relative_rotation"),
    "relative_scale3d": property_value(component, "relative_scale3d"),
    "override_materials": property_value(component, "override_materials"),
}

payload = {
    "status": "ok",
    "world": world_path,
    "mesh": MESH_PATH,
    "mesh_bounds": str(mesh.get_bounds()),
    "materials": material_rows,
    "blueprint": BLUEPRINT_PATH,
    "blueprint_defaults": {
        "curtain_active": property_value(cdo, "curtain_active"),
        "follow_player_camera": property_value(cdo, "follow_player_camera"),
        "curtain_distance_cm": property_value(cdo, "curtain_distance_cm"),
        "use_authored_transforms": property_value(
            cdo, "use_authored_open_closed_transforms"
        ),
        "open_transform": property_value(cdo, "curtain_open_relative_transform"),
        "closed_transform": property_value(cdo, "curtain_closed_relative_transform"),
        "motion_root": object_path(motion_root),
    },
    "component": component_row,
    "dirty_content": dirty_content,
    "dirty_maps": dirty_maps,
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCurtainAuthoring",
    "inspect_curtain_renderability.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(
    "PUSS_CURTAIN_RENDERABILITY_INSPECT_SUCCESS"
    f"|materials={len(material_rows)}|dirty_content=0|dirty_maps=0"
)
