import json
import os

import unreal


SEQUENCE_PATHS = [
    "/Game/InfinityStage/Interactions/LS_Interaction_Template",
    "/Game/InfinityStage/Interactions/LS_Interaction_01_WashingTheBoy",
]


def vector_payload(value):
    return [float(value.x), float(value.y), float(value.z)]


def rotator_payload(value):
    return [float(value.pitch), float(value.yaw), float(value.roll)]


def transform_payload(value):
    return {
        "translation": vector_payload(value.translation),
        "scale": vector_payload(value.scale3d),
        "rotation": [float(value.rotation.x), float(value.rotation.y), float(value.rotation.z), float(value.rotation.w)],
    }


rows = []
for path in SEQUENCE_PATHS:
    sequence = unreal.load_asset(path)
    bindings = list(sequence.get_spawnables()) if sequence is not None else []
    if len(bindings) != 1:
        raise RuntimeError(f"{path} spawnable count is {len(bindings)}")
    template = bindings[0].get_object_template()
    rows.append({
        "path": path,
        "template": template.get_path_name(),
        "active": bool(template.get_editor_property("curtain_active")),
        "follow_camera": bool(template.get_editor_property("follow_player_camera")),
        "distance_cm": float(template.get_editor_property("curtain_distance_cm")),
        "use_authored_transforms": bool(template.get_editor_property("use_authored_open_closed_transforms")),
        "open_transform": transform_payload(template.get_editor_property("curtain_open_relative_transform")),
        "closed_transform": transform_payload(template.get_editor_property("curtain_closed_relative_transform")),
        "progress": float(template.get_editor_property("curtain_progress")),
    })

payload = {"rows": rows}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCurtainAuthoring",
    "inspect_curtain_template_values.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(f"PUSS_CURTAIN_TEMPLATE_VALUES|rows={len(rows)}")
