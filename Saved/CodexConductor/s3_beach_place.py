"""Legacy v1 helpers plus the public Scene 3 beach-v2 entry point.

Dry run is the default. Dedicated runpy wrappers opt into APPLY or REVERT.
The pure guards are importable by test_s3_beach_place_plan.py without Unreal.
No mode opens Sequencer, starts/stops PIE, quits the editor, or uses Save All.
"""
import datetime
import json
import math
import os
import runpy
import shutil
import traceback

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ROOT_SEQUENCE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
RISE_PATH = "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"
ROOT_LABEL = "S3 Hangar Root"
TAG = "RigAtmos.S3Beach"
FOLDER = "RigAtmos/S3Beach"
DOCK_ORIGIN = (10921.973, 160000.0, 0.0)
DOCK_YAW = 0.0
BOX_X = (500.0, 6500.0)
BOX_Y = (-1000.0, 1000.0)
BOX_Z = (-5.0, 600.0)
CAMERA_CLEARANCE_CM = 150.0
WAVE_BANDS_X = ((4100.0, 4300.0), (4900.0, 5100.0), (5700.0, 5900.0))
CAMERA_GAP = {"x": (500.0, 3550.0), "y": (-180.0, 180.0)}


class PlanError(ValueError):
    pass


def project_file(*parts):
    if unreal is None:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    else:
        root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.normpath(os.path.join(root, *parts))


def plan_path():
    return project_file("Saved", "CodexConductor", "s3_beach_plan.json")


def record_path():
    return project_file("Saved", "CodexConductor", "s3_beach_place_record.json")


def load_plan_rows():
    with open(plan_path(), encoding="utf-8") as handle:
        return json.load(handle)["placements"]


def aabb_distance_to_point(bounds, point):
    gaps = [max(0.0, float(bounds["min"][axis]) - float(point[axis]),
                float(point[axis]) - float(bounds["max"][axis])) for axis in range(3)]
    return math.sqrt(sum(value * value for value in gaps))


def overlaps_interval(bounds, axis, interval):
    return float(bounds["max"][axis]) >= float(interval[0]) and float(bounds["min"][axis]) <= float(interval[1])


def validate_box_bounds(rows, bounds_key, label="landed S3 interior"):
    """Require every AABB to be wholly inside the declared landed box."""
    failures = []
    limits = (BOX_X, BOX_Y, BOX_Z)
    for row in rows:
        bounds = row.get(bounds_key)
        if not bounds:
            failures.append("%s has no %s" % (row["label"], bounds_key))
            continue
        for axis, interval in enumerate(limits):
            if (float(bounds["min"][axis]) < float(interval[0]) - 0.001 or
                    float(bounds["max"][axis]) > float(interval[1]) + 0.001):
                failures.append("%s %s leaves %s on axis %d" %
                                (row["label"], bounds_key, label, axis))
    if failures:
        raise PlanError("; ".join(failures))
    return rows


def world_box():
    return {
        "min": [DOCK_ORIGIN[0] + BOX_X[0], DOCK_ORIGIN[1] + BOX_Y[0], BOX_Z[0]],
        "max": [DOCK_ORIGIN[0] + BOX_X[1], DOCK_ORIGIN[1] + BOX_Y[1], BOX_Z[1]],
    }


def validate_world_bounds(rows, bounds_key="world_aabb"):
    limits = world_box()
    failures = []
    for row in rows:
        bounds = row.get(bounds_key)
        if not bounds:
            failures.append("%s has no %s" % (row["label"], bounds_key))
            continue
        for axis in range(3):
            if (float(bounds["min"][axis]) < float(limits["min"][axis]) - 0.001 or
                    float(bounds["max"][axis]) > float(limits["max"][axis]) + 0.001):
                failures.append("%s %s leaves landed S3 world box on axis %d" %
                                (row["label"], bounds_key, axis))
    if failures:
        raise PlanError("; ".join(failures))
    return rows


def validate_plan(rows, cameras, existing_labels=None, bounds_key="estimated_aabb"):
    existing_labels = existing_labels or {}
    failures = []
    labels = [row["label"] for row in rows]
    if len(labels) != len(set(labels)):
        failures.append("duplicate planned labels")
    collisions = sorted(label for label in labels if int(existing_labels.get(label, 0)) != 0)
    if collisions:
        failures.append("labels already exist: " + ", ".join(collisions))
    if not cameras:
        failures.append("no S3 Shot cameras")
    for row in rows:
        bounds = row.get(bounds_key)
        if not bounds:
            failures.append("%s has no %s" % (row["label"], bounds_key))
            continue
        for band in WAVE_BANDS_X:
            if overlaps_interval(bounds, 0, band):
                failures.append("%s enters wave band %.0f..%.0f" % (row["label"], band[0], band[1]))
        if (overlaps_interval(bounds, 0, CAMERA_GAP["x"]) and
                overlaps_interval(bounds, 1, CAMERA_GAP["y"])):
            failures.append("%s enters camera-side ring gap" % row["label"])
        nearest = None
        for camera in cameras:
            distance = aabb_distance_to_point(bounds, camera["location"])
            nearest = distance if nearest is None else min(nearest, distance)
            if distance < CAMERA_CLEARANCE_CM - 0.001:
                failures.append("%s is %.3f cm from %s" % (row["label"], distance, camera["label"]))
        row["nearest_camera_clearance_cm"] = None if nearest is None else round(nearest, 3)
    if failures:
        raise PlanError("; ".join(failures))
    validate_box_bounds(rows, bounds_key)
    return rows


def package_census():
    def names(packages):
        return sorted(str(package.get_path_name()).split(".", 1)[0] for package in packages)
    return {
        "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
        "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    }


def vector(value):
    return [float(value.x), float(value.y), float(value.z)]


def transform_plain(value):
    rotation = value.rotation.rotator()
    return {
        "location": vector(value.translation),
        "rotation": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
        "scale": vector(value.scale3d),
    }


def transform_from_plain(value):
    return unreal.Transform(
        location=unreal.Vector(*value["location"]),
        rotation=unreal.Rotator(roll=value["rotation"][0], pitch=value["rotation"][1], yaw=value["rotation"][2]),
        scale=unreal.Vector(*value["scale"]),
    )


def distance(left, right):
    return math.sqrt((left.x - right.x) ** 2 + (left.y - right.y) ** 2 + (left.z - right.z) ** 2)


def rotation_error(left, right):
    delta = unreal.MathLibrary.normalized_delta_rotator(left, right)
    return max(abs(float(delta.pitch)), abs(float(delta.yaw)), abs(float(delta.roll)))


def frame_value(value):
    if hasattr(value, "frame_number"):
        return int(value.frame_number.value)
    if hasattr(value, "value"):
        return int(value.value)
    return int(value)


def canonical_channel_name(name):
    for candidate in ("Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y",
                      "Rotation.Z", "Scale.X", "Scale.Y", "Scale.Z"):
        if name == candidate or name.startswith(candidate + "_"):
            return candidate
    return None


def transform_values(value):
    rotation = value.rotation.rotator()
    return {
        "Location.X": float(value.translation.x), "Location.Y": float(value.translation.y),
        "Location.Z": float(value.translation.z), "Rotation.X": float(rotation.roll),
        "Rotation.Y": float(rotation.pitch), "Rotation.Z": float(rotation.yaw),
        "Scale.X": float(value.scale3d.x), "Scale.Y": float(value.scale3d.y),
        "Scale.Z": float(value.scale3d.z),
    }


def make_transform(values):
    return unreal.Transform(
        location=unreal.Vector(values["Location.X"], values["Location.Y"], values["Location.Z"]),
        rotation=unreal.Rotator(roll=values["Rotation.X"], pitch=values["Rotation.Y"], yaw=values["Rotation.Z"]),
        scale=unreal.Vector(values["Scale.X"], values["Scale.Y"], values["Scale.Z"]),
    )


def sequence_rest_landed(binding, actor):
    tracks = list(binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack))
    if len(tracks) != 1 or len(tracks[0].get_sections()) != 1:
        raise PlanError("unexpected S3 Hangar Root transform track")
    parent = actor.get_attach_parent_actor()
    baseline = actor.root_component.get_relative_transform() if parent else actor.get_actor_transform()
    first_values = transform_values(baseline)
    last_values = dict(first_values)
    for channel in tracks[0].get_sections()[0].get_all_channels():
        try:
            raw_name = str(channel.get_name())
        except Exception:
            raw_name = str(channel.channel_name)
        name = canonical_channel_name(raw_name)
        if name is None:
            continue
        keys = sorted(list(channel.get_keys()), key=lambda key: frame_value(key.get_time()))
        if keys:
            first_values[name] = float(keys[0].get_value())
            last_values[name] = float(keys[-1].get_value())
        else:
            try:
                if channel.has_default():
                    first_values[name] = last_values[name] = float(channel.get_default())
            except Exception:
                pass
    return make_transform(first_values), make_transform(last_values)


def actor_index(actors):
    result = {}
    for actor in actors:
        result.setdefault(str(actor.get_actor_label()), []).append(actor)
    return result


def one_actor(index, label):
    matches = index.get(label, [])
    if len(matches) != 1:
        raise PlanError("expected exactly one actor labelled %s, found %d" % (label, len(matches)))
    return matches[0]


def unreal_box_points(minimum, maximum):
    return [unreal.Vector(x, y, z) for x in (minimum.x, maximum.x)
            for y in (minimum.y, maximum.y) for z in (minimum.z, maximum.z)]


def transformed_mesh_bounds(mesh, transform):
    box = mesh.get_bounding_box()
    points = [vector(unreal.MathLibrary.transform_location(transform, point))
              for point in unreal_box_points(box.min, box.max)]
    return {
        "min": [min(point[axis] for point in points) for axis in range(3)],
        "max": [max(point[axis] for point in points) for axis in range(3)],
    }


def shot_cameras_dock(sequence, dock):
    rows = []
    for binding in sequence.get_spawnables():
        label = str(binding.get_display_name())
        if not label.startswith("S3 Shot B"):
            continue
        template = binding.get_object_template()
        if template is None or not isinstance(template, unreal.CineCameraActor):
            raise PlanError("S3 Shot template is not a CineCameraActor: " + label)
        root = template.get_editor_property("root_component")
        location = root.get_editor_property("relative_location")
        dock_location = unreal.MathLibrary.inverse_transform_location(dock, location)
        rows.append({"label": label, "location": vector(dock_location)})
    expected = ["S3 Shot B%02d" % number for number in range(2, 13)]
    if sorted(row["label"] for row in rows) != expected:
        raise PlanError("unexpected S3 Shot camera labels: " + json.dumps(sorted(row["label"] for row in rows)))
    return rows


def assert_context(apply, revert):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    world_path = world.get_outermost().get_name() if world else None
    if world_path != EXPECTED_WORLD:
        raise PlanError("WRONG_WORLD|world=%s" % world_path)
    if editor.get_game_world() is not None:
        raise PlanError("PIE_OR_SIE_ACTIVE")
    census = package_census()
    if census["maps"] or census["content"]:
        raise PlanError("DIRTY_BEFORE|census=" + json.dumps(census, sort_keys=True))
    if apply and os.path.exists(record_path()):
        raise PlanError("APPLY_RECORD_ALREADY_EXISTS")
    if revert and not os.path.isfile(record_path()):
        raise PlanError("REVERT_RECORD_ABSENT")


def live_plan():
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    index = actor_index(actors)
    root = one_actor(index, ROOT_LABEL)
    sequence = unreal.load_asset(ROOT_SEQUENCE)
    if not isinstance(sequence, unreal.LevelSequence):
        raise PlanError("S3 root sequence missing")
    dock = unreal.Transform(location=unreal.Vector(*DOCK_ORIGIN),
                            rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=DOCK_YAW))
    root_current = root.get_actor_transform()
    if rotation_error(root_current.rotation.rotator(), dock.rotation.rotator()) > 0.01:
        raise PlanError("S3 Hangar Root current world rotation is not landed")
    cameras = shot_cameras_dock(sequence, dock)
    rows = load_plan_rows()
    runtime = []
    report_rows = []
    for source in rows:
        row = dict(source)
        mesh = unreal.load_asset(row["mesh_path"])
        material = unreal.load_asset(row["material_path"]) if row.get("material_path") else None
        if not isinstance(mesh, unreal.StaticMesh):
            raise PlanError("mesh missing or wrong class: " + row["mesh_path"])
        if row.get("material_path") and material is None:
            raise PlanError("material missing: " + row["material_path"])
        dock_transform = transform_from_plain(row["transform"])
        row["aabb"] = transformed_mesh_bounds(mesh, dock_transform)
        wanted_world_dock = unreal.MathLibrary.compose_transforms(dock_transform, dock)
        relative_current = unreal.MathLibrary.make_relative_transform(wanted_world_dock, root_current)
        wanted_world_current = unreal.MathLibrary.compose_transforms(relative_current, root_current)
        row["world_transform"] = transform_plain(wanted_world_current)
        row["world_aabb"] = transformed_mesh_bounds(mesh, wanted_world_current)
        report_rows.append(row)
        runtime.append({"row": row, "mesh": mesh, "material": material,
                        "relative_current": relative_current, "world": wanted_world_current})
    existing = {row["label"]: len(index.get(row["label"], [])) for row in report_rows}
    validate_plan(report_rows, cameras, existing, bounds_key="aabb")
    validate_world_bounds(report_rows)
    return {
        "cameras": cameras,
        "rows": report_rows,
        "source_plan": os.path.basename(plan_path()),
        "exact_bounds_from_unreal": True,
        "root_current_world_transform": transform_plain(root_current),
        "landed_world_box": world_box(),
    }, runtime, root


def package_filename(package_name, is_map=False):
    extension = ".umap" if is_map else ".uasset"
    return os.path.join(project_file("Content"), *package_name[len("/Game/"):].split("/")) + extension


def backup_level(prefix):
    source = package_filename(EXPECTED_WORLD, True)
    if not os.path.isfile(source):
        raise PlanError("LEVEL_BACKUP_SOURCE_MISSING|path=" + source)
    backup = project_file("Backups", prefix + datetime.datetime.now().strftime("%Y%m%d-%H%M"))
    if os.path.exists(backup):
        raise PlanError("BACKUP_EXISTS|path=" + backup)
    relative = os.path.relpath(source, project_file("Content"))
    destination = os.path.join(backup, "Content", relative)
    os.makedirs(os.path.dirname(destination))
    shutil.copy2(source, destination)
    return backup, relative.replace("\\", "/")


def write_record(value, exclusive=False):
    mode = "x" if exclusive else "w"
    with open(record_path(), mode, encoding="utf-8") as handle:
        json.dump(value, handle, indent=1, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())


def save_level_clean():
    census = package_census()
    if census["content"] or census["maps"] != [EXPECTED_WORLD]:
        raise PlanError("DIRTY_CENSUS_NOT_EXACT_LEVEL|census=" + json.dumps(census, sort_keys=True))
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        raise PlanError("LEVEL_SAVE_FAILED")
    after = package_census()
    if after["maps"] or after["content"]:
        raise PlanError("POST_SAVE_DIRTY|census=" + json.dumps(after, sort_keys=True))
    return after


def apply_plan(run, report, runtime, root):
    backup, copied = backup_level("PreS3Beach-")
    record = {"run": run, "world": EXPECTED_WORLD, "backup": backup, "backup_file": copied,
              "tag": TAG, "plan": report, "spawned": [], "applied": False}
    write_record(record, exclusive=True)
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for item in runtime:
        row = item["row"]
        transform = item["world"]
        actor = subsystem.spawn_actor_from_class(unreal.StaticMeshActor, transform.translation,
                                                 transform.rotation.rotator())
        if actor is None:
            raise PlanError("SPAWN_FAILED|label=" + row["label"])
        actor.modify(); actor.set_actor_label(row["label"])
        actor.modify(); actor.set_folder_path(FOLDER)
        actor.modify(); actor.set_editor_property("tags", [unreal.Name(TAG), unreal.Name("S3Beach." + row["kind"])])
        component = actor.get_editor_property("static_mesh_component")
        component.modify(); component.set_mobility(unreal.ComponentMobility.MOVABLE)
        component.modify(); component.set_editor_property("static_mesh", item["mesh"])
        if item["material"] is not None:
            component.modify(); component.set_material(0, item["material"])
        actor.modify(); actor.set_actor_scale3d(transform.scale3d)
        actor.modify(); actor.attach_to_actor(root, unreal.Name(""), unreal.AttachmentRule.KEEP_WORLD,
                                              unreal.AttachmentRule.KEEP_WORLD,
                                              unreal.AttachmentRule.KEEP_WORLD, False)
        if actor.get_attach_parent_actor() is not root:
            raise PlanError("PARENT_READBACK_MISMATCH|label=" + row["label"])
        if distance(actor.get_actor_transform().translation, transform.translation) > 1.0:
            raise PlanError("LOCATION_READBACK_MISMATCH|label=" + row["label"])
        tags = [str(value) for value in actor.get_editor_property("tags")]
        if TAG not in tags:
            raise PlanError("TAG_READBACK_MISMATCH|label=" + row["label"])
        actual_mesh = component.get_editor_property("static_mesh")
        if actual_mesh is None or str(actual_mesh.get_path_name()).split(".", 1)[0] != row["mesh_path"]:
            raise PlanError("MESH_READBACK_MISMATCH|label=" + row["label"])
        origin, extent = actor.get_actor_bounds(False, True)
        actual_bounds = {"min": [origin.x - extent.x, origin.y - extent.y, origin.z - extent.z],
                         "max": [origin.x + extent.x, origin.y + extent.y, origin.z + extent.z]}
        validate_world_bounds([{"label": row["label"], "world_aabb": actual_bounds}])
        record["spawned"].append({"label": row["label"], "object_path": actor.get_path_name(),
                                  "mesh_path": row["mesh_path"], "kind": row["kind"],
                                  "world_location_cm": vector(actor.get_actor_location()),
                                  "world_aabb": actual_bounds})
        write_record(record)
    if len(record["spawned"]) != len(runtime):
        raise PlanError("SPAWN_COUNT_MISMATCH")
    census = save_level_clean()
    record["applied"] = True
    write_record(record)
    unreal.log("S3_BEACH_DONE|run=%s|applied|actors=%d|backup=%s|census=%s" %
               (run, len(runtime), backup, json.dumps(census, separators=(",", ":"), sort_keys=True)))


def revert_plan(run):
    with open(record_path(), encoding="utf-8") as handle:
        record = json.load(handle)
    if record.get("world") != EXPECTED_WORLD or not record.get("applied") or record.get("tag") != TAG:
        raise PlanError("REVERT_RECORD_INVALID")
    index = actor_index(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    targets = []
    for row in record.get("spawned", []):
        actor = one_actor(index, row["label"])
        tags = [str(value) for value in actor.get_editor_property("tags")]
        if TAG not in tags or actor.get_path_name() != row["object_path"]:
            raise PlanError("REVERT_OWNERSHIP_MISMATCH|label=" + row["label"])
        targets.append(actor)
    if len(targets) != len(record.get("spawned", [])) or not targets:
        raise PlanError("REVERT_TARGET_COUNT")
    backup, _ = backup_level("PreS3BeachRevert-")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in targets:
        actor.modify()
        if not subsystem.destroy_actor(actor):
            raise PlanError("DESTROY_FAILED|label=" + actor.get_actor_label())
    remaining = actor_index(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    survivors = [row["label"] for row in record["spawned"] if remaining.get(row["label"])]
    if survivors:
        raise PlanError("REVERT_SURVIVORS|labels=" + json.dumps(survivors))
    census = save_level_clean()
    archived = record_path() + ".reverted-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    os.rename(record_path(), archived)
    unreal.log("S3_BEACH_DONE|run=%s|reverted|actors=%d|backup=%s|record=%s|census=%s" %
               (run, len(targets), backup, os.path.basename(archived),
                json.dumps(census, separators=(",", ":"), sort_keys=True)))


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    apply = bool(globals().get("S3_BEACH_APPLY"))
    revert = bool(globals().get("S3_BEACH_REVERT"))
    try:
        if apply and revert:
            raise PlanError("APPLY_AND_REVERT_BOTH_SET")
        assert_context(apply, revert)
        if revert:
            revert_plan(run)
            return
        report, runtime, root = live_plan()
        unreal.log("S3_BEACH_PLAN|run=%s|%s" %
                   (run, json.dumps(report, separators=(",", ":"), sort_keys=True)))
        if not apply:
            after = package_census()
            if after["maps"] or after["content"]:
                raise PlanError("DRY_RUN_DIRTIED_PACKAGES|census=" + json.dumps(after, sort_keys=True))
            unreal.log("S3_BEACH_DRY_RUN_OK|run=%s|mutated=0|actors=%d|camera_clearance_cm=150" %
                       (run, len(runtime)))
            return
        apply_plan(run, report, runtime, root)
    except PlanError as exc:
        unreal.log_error("S3_BEACH_%s_STOPPED|run=%s|reason=%s|census=%s" %
                         ("REVERT" if revert else ("APPLY" if apply else "DRY_RUN"), run, str(exc),
                          json.dumps(package_census(), separators=(",", ":"), sort_keys=True)))
    except Exception:
        unreal.log_error("S3_BEACH_ERROR|run=%s|traceback=%s|census=%s" %
                         (run, traceback.format_exc().replace("\n", "\\n"),
                          json.dumps(package_census(), separators=(",", ":"), sort_keys=True)))


if unreal is not None:
    # Revision 3 Oct: the public tool path now runs the v2 replacement.  Keep
    # this module's v1 implementation above as provenance and for exact legacy
    # plan/record interpretation; all live execution delegates to v2.
    _v2 = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "s3_beach_v2.py"))
    _v2["main"](bool(globals().get("S3_BEACH_APPLY")),
                bool(globals().get("S3_BEACH_REVERT")))
