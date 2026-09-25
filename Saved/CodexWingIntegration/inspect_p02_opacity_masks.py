"""Read-only inventory of Passage 2 wing meshes and material texture parameters."""

import json
import os

import unreal


SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
LABEL_PREFIX = "P02 Wing "
EXPECTED_ROWS = 23


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def asset_path(value):
    if value is None:
        return None
    if hasattr(value, "get_path_name"):
        return value.get_path_name().split(".", 1)[0]
    return str(value)


def serialized_texture_parameters(material):
    values = {}
    if not isinstance(material, unreal.MaterialInstanceConstant):
        return values
    for item in material.get_editor_property("texture_parameter_values"):
        info = item.get_editor_property("parameter_info")
        name = str(info.get_editor_property("name"))
        values[name] = asset_path(item.get_editor_property("parameter_value"))
    return values


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
require(world is not None, "No editor world is open")
world_path = world.get_path_name().split(".", 1)[0]
require(world_path == EXPECTED_WORLD, f"Unexpected world: {world_path}")
require(editor.get_game_world() is None, "PIE/SIE is active")
require(
    not list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    "Dirty content exists before inspection",
)
require(
    not list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    "Dirty maps exist before inspection",
)

show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
require(show is not None, f"Show Asset did not load: {SHOW_PATH}")
cues = list(show.get_editor_property("cues"))
rows = []
mesh_usage = {}
override_usage = {}

for cue_index, cue in enumerate(cues):
    label = str(cue.get_editor_property("label"))
    if not label.startswith(LABEL_PREFIX):
        continue
    pair = cue.get_editor_property("wing_pair")
    roles = ("left", "right", "top") if bool(pair.get_editor_property("has_top")) else ("left", "right")
    row = {"cue_index": cue_index, "label": label, "roles": {}}
    for role in roles:
        panel = pair.get_editor_property(role)
        mesh = panel.get_editor_property("mesh")
        mesh_name = asset_path(mesh)
        overrides = [asset_path(value) for value in panel.get_editor_property("material_overrides")]
        row["roles"][role] = {"mesh": mesh_name, "material_overrides": overrides}
        if mesh_name:
            mesh_usage.setdefault(mesh_name, []).append(f"{label}:{role}")
        for override in overrides:
            if override:
                override_usage.setdefault(override, []).append(f"{label}:{role}")
    rows.append(row)

require(len(rows) == EXPECTED_ROWS, f"Expected {EXPECTED_ROWS} rows, found {len(rows)}")
require(
    {row["label"] for row in rows}
    == {f"{LABEL_PREFIX}{ordinal:03d}" for ordinal in range(1, EXPECTED_ROWS + 1)},
    "Passage 2 label set changed",
)

materials = {}
meshes = {}

def record_material(material, usage):
    material_name = asset_path(material)
    if not material_name:
        return
    entry = materials.setdefault(
        material_name,
        {
            "class": material.get_class().get_name(),
            "parent": asset_path(material.get_editor_property("parent"))
            if isinstance(material, unreal.MaterialInstanceConstant)
            else None,
            "texture_parameters": serialized_texture_parameters(material),
            "used_by": [],
        },
    )
    entry["used_by"].append(usage)


for mesh_name, uses in sorted(mesh_usage.items()):
    mesh = unreal.EditorAssetLibrary.load_asset(mesh_name)
    require(isinstance(mesh, unreal.StaticMesh), f"Expected StaticMesh: {mesh_name}")
    slots = []
    for slot_index, slot in enumerate(mesh.get_editor_property("static_materials")):
        material = slot.get_editor_property("material_interface")
        material_name = asset_path(material)
        slot_name = str(slot.get_editor_property("material_slot_name"))
        slots.append({"index": slot_index, "slot_name": slot_name, "material": material_name})
        if material is not None:
            record_material(material, f"{mesh_name}:slot{slot_index}:{slot_name}")
    meshes[mesh_name] = {"used_by": uses, "slots": slots}

for override_name, uses in sorted(override_usage.items()):
    material = unreal.EditorAssetLibrary.load_asset(override_name)
    require(material is not None, f"Material override did not load: {override_name}")
    for use in uses:
        record_material(material, f"ShowOverride:{use}")

bamboo_assignments = []
for material_name, detail in sorted(materials.items()):
    for parameter_name, texture_name in sorted(detail["texture_parameters"].items()):
        if texture_name and "bamboo" in texture_name.lower():
            bamboo_assignments.append(
                {
                    "material": material_name,
                    "parameter": parameter_name,
                    "texture": texture_name,
                    "used_by": detail["used_by"],
                }
            )

payload = {
    "status": "ok",
    "world": world_path,
    "show_asset": SHOW_PATH,
    "row_count": len(rows),
    "rows": rows,
    "unique_mesh_count": len(meshes),
    "unique_material_count": len(materials),
    "meshes": meshes,
    "materials": materials,
    "bamboo_assignment_count": len(bamboo_assignments),
    "bamboo_assignments": bamboo_assignments,
}

output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexWingIntegration",
    "inspect_p02_opacity_masks.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

require(
    not list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    "Inspection dirtied content",
)
require(
    not list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    "Inspection dirtied a map",
)
unreal.log(
    "P02_OPACITY_INSPECT_SUCCESS"
    f"|rows={len(rows)}|meshes={len(meshes)}|materials={len(materials)}"
    f"|bamboo_assignments={len(bamboo_assignments)}|dirty=0"
)
