"""Read-only Tune 2 diagnosis for the two P04 MOODY bays."""
import json
import math
import os

import unreal


EXPECTED_PROJECT = os.path.normcase(os.path.normpath("E:/PussStage"))
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
OUTPUT = "E:/PussStage/Saved/CodexConductor/lighting_looks_moody_diagnosis.json"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def asset_id(value):
    return value.get_path_name().split(".", 1)[0] if value is not None else None


def guid_text(value):
    return str(unreal.GuidLibrary.conv_guid_to_string(value)).replace("-", "").upper()


def enum_name(value):
    text = str(value).rsplit(".", 1)[-1]
    return text.split(":", 1)[0].strip("<> ")


def transform_row(value):
    rotation = value.rotation.rotator()
    return {
        "location_cm": [float(value.translation.x), float(value.translation.y), float(value.translation.z)],
        "rotation_rpy_deg": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
        "scale": [float(value.scale3d.x), float(value.scale3d.y), float(value.scale3d.z)],
    }


def get_property(value, name):
    try:
        result = value.get_editor_property(name)
    except Exception:
        return None
    if result is None or isinstance(result, (bool, int, float, str)):
        return result
    return str(result)


def mesh_target(panel):
    transform = panel.get_editor_property("local_transform")
    origin = transform.translation
    mesh = panel.get_editor_property("mesh")
    centre = unreal.Vector(0.0, 0.0, 450.0)
    extent = None
    mesh_path = asset_id(mesh)
    if mesh is not None:
        try:
            bounds = mesh.get_bounding_box()
            centre = (bounds.min + bounds.max) * 0.5
            extent_value = (bounds.max - bounds.min) * 0.5
            extent = [float(extent_value.x), float(extent_value.y), float(extent_value.z)]
        except Exception:
            pass
    panel_rotation = transform.rotation.rotator()
    require(abs(float(panel_rotation.roll)) < 1.0e-4
            and abs(float(panel_rotation.pitch)) < 1.0e-4
            and abs(float(panel_rotation.yaw)) < 1.0e-4,
            "MOODY_PANEL_ROTATION_UNSUPPORTED")
    local_centre = unreal.Vector(
        float(origin.x) + float(centre.x) * float(transform.scale3d.x),
        float(origin.y) + float(centre.y) * float(transform.scale3d.y),
        float(origin.z) + float(centre.z) * float(transform.scale3d.z),
    )
    return {
        "mesh": mesh_path,
        "panel_transform": transform_row(transform),
        "mesh_local_centre_cm": [float(centre.x), float(centre.y), float(centre.z)],
        "target_pair_local_cm": [float(local_centre.x), float(local_centre.y), float(local_centre.z)],
        "mesh_local_extent_cm": extent,
    }


def forward_from_rpy(rotation):
    _roll, pitch, yaw = rotation
    pitch = math.radians(float(pitch))
    yaw = math.radians(float(yaw))
    return [math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch)]


def aim_row(source, rotation, target, attenuation, outer_cone):
    forward = forward_from_rpy(rotation)
    delta = [float(target[i]) - float(source[i]) for i in range(3)]
    distance = math.sqrt(sum(value * value for value in delta))
    projection = sum(delta[i] * forward[i] for i in range(3))
    miss = math.sqrt(max(0.0, distance * distance - projection * projection))
    cosine = max(-1.0, min(1.0, projection / distance)) if distance > 1.0e-9 else 1.0
    angle = math.degrees(math.acos(cosine))
    return {
        "target_distance_cm": distance,
        "target_angle_from_axis_deg": angle,
        "outer_cone_deg": float(outer_cone),
        "target_inside_outer_cone": angle <= float(outer_cone),
        "closest_axis_miss_cm": miss,
        "target_inside_attenuation": distance <= float(attenuation),
    }


project = os.path.normcase(os.path.normpath(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())))
require(project.rstrip("\\/") == EXPECTED_PROJECT.rstrip("\\/"), "WRONG_PROJECT|actual=" + project)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
world = editor.get_editor_world()
require(world is not None and asset_id(world) == EXPECTED_WORLD,
        "WRONG_WORLD|actual=" + str(asset_id(world)))
census = {
    "content": sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    "maps": sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
}
require(census == {"content": [], "maps": []}, "DIRTY_BEFORE|" + json.dumps(census, sort_keys=True))

show = unreal.load_asset(SHOW_PATH)
require(show is not None, "SHOW_MISSING")
actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
passages = [actor for actor in actors if actor.get_class().get_name() == "InfinityStagePassageActor"
            and actor.get_actor_label().startswith("Passage 04")
            and actor.get_editor_property("show_asset") == show]
require(len(passages) == 1, "P04_ACTOR_COUNT|actual=%d" % len(passages))
passage = passages[0]
actors_by_label = {}
for actor in actors:
    actors_by_label.setdefault(actor.get_actor_label(), []).append(actor)

rows = []
station_locations = []
for cue in show.get_editor_property("cues"):
    label = str(cue.get_editor_property("label"))
    if label not in ("P04 Wing 001", "P04 Wing 002", "P04 Wing 003"):
        continue
    pair = cue.get_editor_property("wing_pair")
    attachments = list(pair.get_editor_property("attachments"))
    probe_attachment = next((item for item in attachments
                             if str(item.get_editor_property("label")).startswith("P04 LOOK ")
                             and str(item.get_editor_property("label")).endswith(" TOP_L")), None)
    require(probe_attachment is not None, "PROTOTYPE_ATTACHMENT_MISSING|cue=" + label)
    probe_label = str(probe_attachment.get_editor_property("label"))
    probe_actors = actors_by_label.get(probe_label, [])
    require(len(probe_actors) == 1, "PROBE_ACTOR_COUNT|cue=%s|actual=%d" %
            (label, len(probe_actors)))
    probe_world = probe_actors[0].get_actor_location()
    probe_local = probe_attachment.get_editor_property("relative_transform").translation
    # TOP_L uses an identical local offset in bays 1-3, so differences between
    # these live actor locations are station spacing without depending on the
    # Python wrapper's build-specific treatment of FTransform out parameters.
    station_locations.append((label, [float(probe_world.x - probe_local.x),
                                      float(probe_world.y - probe_local.y),
                                      float(probe_world.z - probe_local.z)]))
    if label == "P04 Wing 003":
        continue
    targets = {
        "L": mesh_target(pair.get_editor_property("left")),
        "R": mesh_target(pair.get_editor_property("right")),
    }
    fixtures = []
    for attachment in attachments:
        attachment_label = str(attachment.get_editor_property("label"))
        if not attachment_label.startswith("P04 LOOK B0"):
            continue
        settings = attachment.get_editor_property("lighting")
        relative = attachment.get_editor_property("relative_transform")
        relative_row = transform_row(relative)
        fixture = {
            "label": attachment_label,
            "enabled": bool(attachment.get_editor_property("enabled")),
            "kind": enum_name(attachment.get_editor_property("kind")),
            "relative_transform": relative_row,
            "show": {
                "type": enum_name(settings.get_editor_property("type")),
                "intensity_units": enum_name(settings.get_editor_property("intensity_units")),
                "intensity": float(settings.get_editor_property("intensity")),
                "attenuation_radius_cm": float(settings.get_editor_property("attenuation_radius_cm")),
                "inner_cone_deg": float(settings.get_editor_property("inner_cone_angle_degrees")),
                "outer_cone_deg": float(settings.get_editor_property("outer_cone_angle_degrees")),
                "temperature_kelvin": float(settings.get_editor_property("temperature_kelvin")),
                "cast_shadows": bool(settings.get_editor_property("cast_shadows")),
                "light_function": asset_id(settings.get_editor_property("light_function_material")),
            },
        }
        slot = attachment_label.rsplit(" ", 1)[-1]
        # Bay 2 mirrors the LOW_SIDE transforms without renaming their slots;
        # the source's lateral sign is therefore the reliable physical side.
        side = ("L" if relative_row["location_cm"][1] < 0.0 else "R") if "LOW_SIDE" in slot else None
        if enum_name(settings.get_editor_property("type")) == "SPOT" and side:
            fixture["aim_to_panel_centre"] = aim_row(
                relative_row["location_cm"], relative_row["rotation_rpy_deg"],
                targets[side]["target_pair_local_cm"],
                fixture["show"]["attenuation_radius_cm"], fixture["show"]["outer_cone_deg"])
        live = actors_by_label.get(attachment_label, [])
        fixture["spawned_actor_count"] = len(live)
        if len(live) == 1:
            light_components = list(live[0].get_components_by_class(unreal.LightComponent))
            fixture["spawned_light_component_count"] = len(light_components)
            if len(light_components) == 1:
                component = light_components[0]
                fixture["live_component"] = {
                    "class": component.get_class().get_name(),
                    "intensity": get_property(component, "intensity"),
                    "attenuation_radius": get_property(component, "attenuation_radius"),
                    "intensity_units": get_property(component, "intensity_units"),
                    "inner_cone_angle": get_property(component, "inner_cone_angle"),
                    "outer_cone_angle": get_property(component, "outer_cone_angle"),
                }
        fixtures.append(fixture)
    rows.append({
        "cue": label,
        "targets": targets,
        "fixtures": fixtures,
    })

require(len(rows) == 2, "MOODY_CUE_COUNT|actual=%d" % len(rows))
require(len(station_locations) == 3, "STATION_COUNT|actual=%d" % len(station_locations))
spacings = []
for index in range(2):
    a = station_locations[index][1]
    b = station_locations[index + 1][1]
    spacings.append({
        "from": station_locations[index][0],
        "to": station_locations[index + 1][0],
        "straight_line_cm": math.sqrt(sum((b[i] - a[i]) ** 2 for i in range(3))),
    })

result = {
    "status": "diagnosis_only",
    "census": census,
    "distance_keying": {
        "strike_distance_cm": 150.0,
        "strike_ramp_cm": 150.0,
        "interpretation": "starts only 150 cm ahead and reaches full at the bay pass plane",
    },
    "station_locations": station_locations,
    "station_spacings": spacings,
    "rows": rows,
}
with open(OUTPUT, "w", encoding="utf-8") as handle:
    json.dump(result, handle, indent=2, sort_keys=True)
require({
    "content": sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    "maps": sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
} == census, "DIAGNOSIS_DIRTIED_PACKAGES")
unreal.log("LIGHTING_LOOKS_MOODY_DIAGNOSIS_OK|bays=2|fixtures=%d|mutated=0|output=%s" %
           (sum(len(row["fixtures"]) for row in rows), OUTPUT))
