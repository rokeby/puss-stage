"""Read-only P04 panel transform probe for the lighting-look aim gate."""
import json
import os
import unreal

EXPECTED_PROJECT = os.path.normcase(os.path.normpath("E:/PussStage"))
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"


def asset_id(value):
    return value.get_path_name().split(".", 1)[0] if value is not None else None


def transform_row(value):
    rotation = value.rotation.rotator()
    return {
        "location_cm": [float(value.translation.x), float(value.translation.y), float(value.translation.z)],
        "rotation_rpy_deg": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
        "scale": [float(value.scale3d.x), float(value.scale3d.y), float(value.scale3d.z)],
    }


project = os.path.normcase(os.path.normpath(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())))
if project.rstrip("\\/") != EXPECTED_PROJECT.rstrip("\\/"):
    raise RuntimeError("WRONG_PROJECT|actual=" + project)
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
show = unreal.load_asset(SHOW_PATH)
if show is None:
    raise RuntimeError("SHOW_MISSING")

rows = []
for index, cue in enumerate(show.get_editor_property("cues")):
    label = str(cue.get_editor_property("label"))
    if not label.startswith("P04 Wing 00"):
        continue
    suffix = int(label.rsplit(" ", 1)[1])
    if suffix > 7:
        continue
    pair = cue.get_editor_property("wing_pair")
    row = {
        "index": index,
        "label": label,
        "has_top": bool(pair.get_editor_property("has_top")),
        "occurrence": transform_row(pair.get_editor_property("occurrence_offset")),
        "left": transform_row(pair.get_editor_property("left").get_editor_property("local_transform")),
        "right": transform_row(pair.get_editor_property("right").get_editor_property("local_transform")),
        "top": transform_row(pair.get_editor_property("top").get_editor_property("local_transform")),
    }
    rows.append(row)

if len(rows) != 7:
    raise RuntimeError("P04_BAY_1_TO_7_COUNT|actual=%d" % len(rows))
output = "E:/PussStage/Saved/CodexConductor/lighting_looks_top_probe.json"
with open(output, "w", encoding="utf-8") as handle:
    json.dump({"rows": rows, "census": census}, handle, indent=2)
unreal.log("LIGHTING_LOOKS_TOP_PROBE_OK|rows=%d|output=%s" % (len(rows), output))
