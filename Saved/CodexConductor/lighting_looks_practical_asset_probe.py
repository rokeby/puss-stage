"""Read-only candidate practical-mesh inventory for Tune 2."""
import json
import os
import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
OUTPUT = "E:/PussStage/Saved/CodexConductor/lighting_looks_practical_asset_probe.json"
CANDIDATES = [
    "/Game/KK_S2_Shrine/StarterContent/Props/SM_Lamp_Ceiling",
    "/Game/KK_S2_Shrine/StarterContent/Props/SM_Lamp_Wall",
    "/Game/KK_S2_Shrine/StarterContent/Shapes/Shape_Tube",
    "/Engine/BasicShapes/Sphere",
    "/Engine/BasicShapes/Cylinder",
    "/Engine/BasicShapes/Cone",
]


def asset_id(value):
    return value.get_path_name().split(".", 1)[0] if value is not None else None


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world() is not None:
    raise RuntimeError("PIE_OR_SIE_ACTIVE")
world = editor.get_editor_world()
if world is None or asset_id(world) != EXPECTED_WORLD:
    raise RuntimeError("WRONG_WORLD|actual=" + str(asset_id(world)))
census = {
    "content": sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    "maps": sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
}
if census != {"content": [], "maps": []}:
    raise RuntimeError("DIRTY_BEFORE|" + json.dumps(census, sort_keys=True))
rows = []
for path in CANDIDATES:
    mesh = unreal.load_asset(path)
    row = {"path": path, "loaded": mesh is not None}
    if mesh is not None:
        bounds = mesh.get_bounding_box()
        size = bounds.max - bounds.min
        row["class"] = mesh.get_class().get_name()
        row["size_cm"] = [float(size.x), float(size.y), float(size.z)]
        row["materials"] = [asset_id(mesh.get_material(index))
                            for index in range(len(mesh.get_editor_property("static_materials")))]
    rows.append(row)
after = {
    "content": sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    "maps": sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
}
if after != census:
    raise RuntimeError("PROBE_DIRTIED_PACKAGES|" + json.dumps(after, sort_keys=True))
with open(OUTPUT, "w", encoding="utf-8") as handle:
    json.dump({"rows": rows, "census": census}, handle, indent=2, sort_keys=True)
unreal.log("LIGHTING_LOOKS_PRACTICAL_ASSET_PROBE_OK|rows=%d|mutated=0|output=%s" %
           (len(rows), OUTPUT))
