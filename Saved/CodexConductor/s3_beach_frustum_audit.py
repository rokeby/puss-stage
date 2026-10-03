"""Read-only live audit of the placed S3 beach and marble liners.

Reads the APPLY records, verifies every recorded actor against the open level,
and tests each live world AABB against the B02/B03 cine-camera frusta.  It does
not evaluate Sequencer, mutate actors, save packages, or control PIE.
"""
import datetime
import itertools
import json
import math
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQUENCE_PATH = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
SHOT_LABELS = ("S3 Shot B02", "S3 Shot B03")
BASE = os.path.normpath(os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexConductor",
))
BEACH_RECORD = os.path.join(BASE, "s3_beach_place_record.json")
MARBLE_RECORD = os.path.join(BASE, "s3_walls_marble_record.json")
REPORT_PATH = os.path.join(BASE, "s3_beach_frustum_audit_report.json")


def package_census():
    def names(packages):
        return sorted(str(package.get_path_name()).split(".", 1)[0] for package in packages)
    return {
        "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
        "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    }


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def vector_row(value):
    return [float(value.x), float(value.y), float(value.z)]


def rotator_row(value):
    return [float(value.roll), float(value.pitch), float(value.yaw)]


def property_probe(obj, names):
    attempts = []
    for name in names:
        try:
            return {"value": bool(obj.get_editor_property(name)), "source": name}
        except Exception as exc:
            attempts.append("%s:%s" % (name, type(exc).__name__))
    return {"value": None, "source": None, "attempts": attempts}


def method_probe(obj, names):
    attempts = []
    for name in names:
        try:
            method = getattr(obj, name)
            return {"value": bool(method()), "source": name + "()"}
        except Exception as exc:
            attempts.append("%s:%s" % (name, type(exc).__name__))
    return {"value": None, "source": None, "attempts": attempts}


def actor_aabb(actor):
    origin, extent = actor.get_actor_bounds(False, True)
    minimum = unreal.Vector(origin.x - extent.x, origin.y - extent.y, origin.z - extent.z)
    maximum = unreal.Vector(origin.x + extent.x, origin.y + extent.y, origin.z + extent.z)
    return origin, extent, minimum, maximum


def camera_rows(sequence):
    rows = {}
    bindings = {str(binding.get_display_name()): binding for binding in sequence.get_spawnables()}
    for label in SHOT_LABELS:
        binding = bindings.get(label)
        if binding is None:
            raise RuntimeError("SHOT_BINDING_MISSING|" + label)
        actor = binding.get_object_template()
        root = actor.get_editor_property("root_component") if actor is not None else None
        component = actor.get_cine_camera_component() if actor is not None else None
        if actor is None or root is None or component is None:
            raise RuntimeError("SHOT_TEMPLATE_INCOMPLETE|" + label)
        if root.get_attach_parent() is not None:
            raise RuntimeError("SHOT_TEMPLATE_ATTACHED|" + label)
        location = root.get_editor_property("relative_location")
        rotation = root.get_editor_property("relative_rotation")
        filmback = component.get_editor_property("filmback")
        sensor_width = float(filmback.get_editor_property("sensor_width"))
        sensor_height = float(filmback.get_editor_property("sensor_height"))
        focal = float(component.get_editor_property("current_focal_length"))
        hfov = math.degrees(2.0 * math.atan(sensor_width / (2.0 * focal)))
        vfov = math.degrees(2.0 * math.atan(sensor_height / (2.0 * focal)))
        rows[label] = {
            "location_cm": vector_row(location),
            "rotation_rpy_deg": rotator_row(rotation),
            "focal_length_mm": focal,
            "sensor_width_mm": sensor_width,
            "sensor_height_mm": sensor_height,
            "hfov_deg": hfov,
            "vfov_deg": vfov,
        }
    return rows


def frustum_intersection(minimum, maximum, camera):
    transform = unreal.Transform(
        location=unreal.Vector(*camera["location_cm"]),
        rotation=unreal.Rotator(
            roll=camera["rotation_rpy_deg"][0],
            pitch=camera["rotation_rpy_deg"][1],
            yaw=camera["rotation_rpy_deg"][2],
        ),
    )
    world_corners = [
        unreal.Vector(x, y, z)
        for x, y, z in itertools.product(
            (minimum.x, maximum.x),
            (minimum.y, maximum.y),
            (minimum.z, maximum.z),
        )
    ]
    local = [unreal.MathLibrary.inverse_transform_location(transform, point)
             for point in world_corners]
    tan_h = math.tan(math.radians(camera["hfov_deg"] * 0.5))
    tan_v = math.tan(math.radians(camera["vfov_deg"] * 0.5))
    plane_values = {
        "near": [point.x - 1.0 for point in local],
        "left": [point.x * tan_h + point.y for point in local],
        "right": [point.x * tan_h - point.y for point in local],
        "bottom": [point.x * tan_v + point.z for point in local],
        "top": [point.x * tan_v - point.z for point in local],
    }
    outside_planes = [name for name, values in plane_values.items() if max(values) < 0.0]
    center = unreal.Vector(
        (minimum.x + maximum.x) * 0.5,
        (minimum.y + maximum.y) * 0.5,
        (minimum.z + maximum.z) * 0.5,
    )
    center_local = unreal.MathLibrary.inverse_transform_location(transform, center)
    return {
        "intersects": not outside_planes,
        "outside_planes": outside_planes,
        "camera_local_center_cm": vector_row(center_local),
        "camera_local_corner_min_cm": [
            min(point.x for point in local), min(point.y for point in local), min(point.z for point in local)
        ],
        "camera_local_corner_max_cm": [
            max(point.x for point in local), max(point.y for point in local), max(point.z for point in local)
        ],
    }


def live_actor_row(actor, cameras):
    origin, extent, minimum, maximum = actor_aabb(actor)
    parent = actor.get_attach_parent_actor()
    components = []
    for component in actor.get_components_by_class(unreal.PrimitiveComponent):
        components.append({
            "name": str(component.get_name()),
            "class": str(component.get_class().get_name()),
            "visible": property_probe(component, ("visible",)),
            "hidden_in_game": property_probe(component, ("hidden_in_game",)),
            "is_visible_method": method_probe(component, ("is_visible",)),
        })
    return {
        "label": str(actor.get_actor_label()),
        "object_path": str(actor.get_path_name()),
        "class": str(actor.get_class().get_name()),
        "attach_parent": str(parent.get_actor_label()) if parent else None,
        "actor_hidden": method_probe(actor, ("is_hidden", "get_is_hidden")),
        "actor_hidden_in_game": property_probe(actor, ("hidden", "hidden_in_game")),
        "world_location_cm": vector_row(actor.get_actor_location()),
        "world_rotation_rpy_deg": rotator_row(actor.get_actor_rotation()),
        "world_scale": vector_row(actor.get_actor_scale3d()),
        "world_bounds": {
            "origin_cm": vector_row(origin),
            "extent_cm": vector_row(extent),
            "min_cm": vector_row(minimum),
            "max_cm": vector_row(maximum),
        },
        "components": components,
        "frustum": {
            label: frustum_intersection(minimum, maximum, camera)
            for label, camera in cameras.items()
        },
    }


def one_actor(index, label):
    matches = index.get(label, [])
    if len(matches) != 1:
        raise RuntimeError("ACTOR_COUNT|label=%s|count=%d" % (label, len(matches)))
    return matches[0]


def main():
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    world_path = str(world.get_outermost().get_name()) if world else None
    if world_path != EXPECTED_WORLD:
        raise RuntimeError("WRONG_WORLD|" + str(world_path))
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE_OR_SIE_ACTIVE")
    before = package_census()
    if before != {"maps": [], "content": []}:
        raise RuntimeError("DIRTY_BEFORE|" + json.dumps(before, sort_keys=True))

    beach_record = read_json(BEACH_RECORD)
    marble_record = read_json(MARBLE_RECORD)
    if not beach_record.get("applied") or not marble_record.get("applied"):
        raise RuntimeError("APPLY_RECORD_NOT_LANDED")
    sequence = unreal.load_asset(SEQUENCE_PATH)
    if not isinstance(sequence, unreal.LevelSequence):
        raise RuntimeError("SEQUENCE_LOAD_FAILED")
    cameras = camera_rows(sequence)
    index = {}
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        index.setdefault(str(actor.get_actor_label()), []).append(actor)

    beach = []
    for recorded in beach_record.get("spawned", []):
        actor = one_actor(index, str(recorded["label"]))
        if str(actor.get_path_name()) != str(recorded["object_path"]):
            raise RuntimeError("BEACH_OBJECT_PATH_DRIFT|" + str(recorded["label"]))
        row = live_actor_row(actor, cameras)
        row["record_kind"] = recorded.get("kind")
        row["mesh_path_recorded"] = recorded.get("mesh_path")
        beach.append(row)

    plan_by_liner = {row["liner_label"]: row for row in marble_record["plan"]["rows"]}
    marble = []
    for recorded in marble_record.get("spawned", []):
        label = str(recorded["label"])
        actor = one_actor(index, label)
        if str(actor.get_path_name()) != str(recorded["object_path"]):
            raise RuntimeError("MARBLE_OBJECT_PATH_DRIFT|" + label)
        plan = plan_by_liner[label]
        row = live_actor_row(actor, cameras)
        row.update({
            "source_wall_label": plan["wall_label"],
            "face_changed": "inner face",
            "strategy": plan["strategy"],
            "mutates_wall_slots": bool(plan["mutates_wall_slots"]),
            "source_material": plan["source_material"],
            "source_wall_live": live_actor_row(one_actor(index, plan["wall_label"]), cameras),
        })
        marble.append(row)

    after = package_census()
    if after != before:
        raise RuntimeError("CENSUS_CHANGED|before=%s|after=%s" %
                           (json.dumps(before, sort_keys=True), json.dumps(after, sort_keys=True)))
    report = {
        "run": run,
        "status": "passed",
        "world": world_path,
        "dirty_before": before,
        "dirty_after": after,
        "cameras": cameras,
        "beach_actors": beach,
        "marble_liners": marble,
        "beach_record": BEACH_RECORD.replace("\\", "/"),
        "marble_record": MARBLE_RECORD.replace("\\", "/"),
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    unreal.log(
        "S3_BEACH_FRUSTUM_AUDIT_OK|run=%s|beach=%d|marble=%d|census=%s|report=%s"
        % (run, len(beach), len(marble), json.dumps(after, separators=(",", ":")),
           REPORT_PATH.replace("\\", "/"))
    )


main()
