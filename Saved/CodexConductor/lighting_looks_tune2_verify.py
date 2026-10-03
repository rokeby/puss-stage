"""Independent saved/live read-back for Lighting Looks Tune 3."""
import json
import os

import unreal

EXPECTED_PROJECT = os.path.normcase(os.path.normpath("E:/PussStage"))
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
BASE = "E:/PussStage/Saved/CodexConductor"
RECORD_PATH = BASE + "/lighting_looks_revert_record.json"
REPORT_PATH = BASE + "/lighting_looks_tune3_verify.json"
PREFIX = "P04 LOOK "


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def asset_id(value):
    return value.get_path_name().split(".", 1)[0] if value is not None else None


def enum_name(value):
    text = str(value).rsplit(".", 1)[-1]
    return text.split(":", 1)[0].strip("<> ")


def census():
    return {
        "content": sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


project = os.path.normcase(os.path.normpath(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())))
require(project.rstrip("\\/") == EXPECTED_PROJECT.rstrip("\\/"), "WRONG_PROJECT|actual=" + project)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
world = editor.get_editor_world()
require(world is not None and asset_id(world) == EXPECTED_WORLD,
        "WRONG_WORLD|actual=" + str(asset_id(world)))
before_census = census()
require(before_census == {"content": [], "maps": []},
        "DIRTY_BEFORE|" + json.dumps(before_census, sort_keys=True))
require(os.path.isfile(RECORD_PATH), "ACTIVE_REVERT_RECORD_MISSING")
with open(RECORD_PATH, encoding="utf-8") as handle:
    record = json.load(handle)
require(record.get("status") == "saved_readback_verified",
        "RECORD_STATUS|actual=" + str(record.get("status")))
backup = record.get("backup", {})
require(os.path.isdir(backup.get("root", "")), "BACKUP_ROOT_MISSING")
require(len(backup.get("packages", [])) == 2
        and all(os.path.isfile(row["backup"]) for row in backup["packages"]),
        "BACKUP_FILES_MISSING")

show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
require(show is not None, "SHOW_MISSING")
actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
actors_by_label = {}
for actor in actors:
    actors_by_label.setdefault(actor.get_actor_label(), []).append(actor)

rows = []
all_lights = 0
all_props = 0
all_shadow_casters = 0
target_shadow_casters = 0
dead_by_look = {"MOODY": 0, "INDUSTRIAL": 0, "THEATRICAL": 0}
for cue in show.get_editor_property("cues"):
    cue_label = str(cue.get_editor_property("label"))
    is_p04 = cue_label.startswith("P04 Wing ")
    attachments = list(cue.get_editor_property("wing_pair").get_editor_property("attachments"))
    if is_p04:
        for attachment in attachments:
            if enum_name(attachment.get_editor_property("kind")) != "LIGHT":
                continue
            settings = attachment.get_editor_property("lighting")
            if bool(attachment.get_editor_property("enabled")) and bool(settings.get_editor_property("cast_shadows")):
                all_shadow_casters += 1
    if cue_label not in tuple("P04 Wing %03d" % value for value in range(1, 7)):
        continue
    prototype = [item for item in attachments
                 if str(item.get_editor_property("label")).startswith(PREFIX)]
    light_rows = []
    prop_rows = []
    for attachment in prototype:
        label = str(attachment.get_editor_property("label"))
        kind = enum_name(attachment.get_editor_property("kind"))
        matches = actors_by_label.get(label, [])
        require(len(matches) == 1, "LIVE_ACTOR_COUNT|label=%s|actual=%d" % (label, len(matches)))
        if kind == "LIGHT":
            settings = attachment.get_editor_property("lighting")
            drama = settings.get_editor_property("drama")
            intensity = float(settings.get_editor_property("intensity"))
            require(abs(float(drama.get_editor_property("strike_distance_cm")) - 650.0) < 1.0e-6,
                    "STRIKE_DISTANCE_READBACK|label=" + label)
            require(abs(float(drama.get_editor_property("strike_ramp_cm")) - 150.0) < 1.0e-6,
                    "STRIKE_RAMP_READBACK|label=" + label)
            if bool(settings.get_editor_property("cast_shadows")):
                target_shadow_casters += 1
            light_components = list(matches[0].get_components_by_class(unreal.LightComponent))
            require(len(light_components) == 1, "LIVE_LIGHT_COMPONENT_COUNT|label=" + label)
            require(abs(float(light_components[0].get_editor_property("intensity")) - intensity) < 1.0e-4,
                    "LIVE_LIGHT_INTENSITY_MISMATCH|label=" + label)
            if " PRACTICAL_" in label:
                look = label.split()[3]
                if intensity == 0.0 and look in dead_by_look:
                    dead_by_look[look] += 1
            light_rows.append({"label": label, "intensity": intensity,
                               "units": enum_name(settings.get_editor_property("intensity_units"))})
            all_lights += 1
        elif kind == "PROP":
            mesh = attachment.get_editor_property("mesh")
            components = list(matches[0].get_components_by_class(unreal.StaticMeshComponent))
            require(len(components) == 1, "LIVE_PROP_COMPONENT_COUNT|label=" + label)
            require(asset_id(components[0].get_editor_property("static_mesh")) == asset_id(mesh),
                    "LIVE_PROP_MESH_MISMATCH|label=" + label)
            prop_rows.append({"label": label, "mesh": asset_id(mesh)})
            all_props += 1
        else:
            raise RuntimeError("PROTOTYPE_KIND_UNEXPECTED|label=%s|kind=%s" % (label, kind))
    require(len(prop_rows) == 2, "PRACTICAL_PROP_COUNT|cue=%s|actual=%d" %
            (cue_label, len(prop_rows)))
    rows.append({"cue": cue_label, "lights": light_rows, "practical_props": prop_rows})

require(len(rows) == 6, "TARGET_CUE_COUNT|actual=%d" % len(rows))
require(all_lights == 40, "LIGHT_COUNT|actual=%d" % all_lights)
require(all_props == 12, "PROP_COUNT|actual=%d" % all_props)
require(target_shadow_casters == 12, "TARGET_SHADOW_COUNT|actual=%d" % target_shadow_casters)
require(all_shadow_casters == 43, "P04_SHADOW_COUNT|actual=%d" % all_shadow_casters)
require(all(count == 1 for count in dead_by_look.values()),
        "DEAD_PRACTICAL_COUNT|expected_one_each|actual=" +
        json.dumps(dead_by_look, sort_keys=True))
after_census = census()
require(after_census == before_census, "VERIFY_DIRTIED_PACKAGES|" + json.dumps(after_census, sort_keys=True))

result = {
    "ok": True,
    "status": "saved_live_readback_verified",
    "record_run": record.get("run"),
    "backup": backup,
    "rows": rows,
    "counts": {"lights": all_lights, "practical_props": all_props,
               "target_shadow_casters": target_shadow_casters,
               "p04_shadow_casters": all_shadow_casters},
    "dead_by_look": dead_by_look,
    "census": after_census,
}
with open(REPORT_PATH, "w", encoding="utf-8") as handle:
    json.dump(result, handle, indent=2, sort_keys=True)
unreal.log("LIGHTING_LOOKS_TUNE3_VERIFY_OK|lights=%d|practical_props=%d|dead=%s|p04_shadow=%d|census=clean|output=%s" %
           (all_lights, all_props, json.dumps(dead_by_look, separators=(",", ":"), sort_keys=True),
            all_shadow_casters, REPORT_PATH))
