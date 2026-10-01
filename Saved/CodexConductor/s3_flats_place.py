"""Plan, apply, or revert Scene 3 wave rows and Opal Beach backdrop.

Dry run is the default.  Apply/revert are enabled only by the dedicated wrappers.
The pure guards are imported by test_s3_flats_place_plan.py without Unreal.
"""
import datetime
import json
import math
import os
import shutil
import traceback

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
RISE_PATH = "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"
DOCK_ORIGIN = (10921.973, 160000.0, 0.0)
DOCK_YAW = 0.0
BOX_X = (500.0, 6500.0)
BOX_Y = (-1000.0, 1000.0)
BOX_TOLERANCE_CM = 1.0
RING_CLEARANCE_CM = 300.0
ROOT_LABEL = "S3 Hangar Root"
FAR_WALL_LABEL = "S3 Hangar Far Wall"
WAVE_TAG = "RigAtmos.S3Waves"
BACKDROP_TAG = "RigAtmos.S3Backdrop"
BACKDROP_LABEL = "S3 Backdrop"
BACKDROP_MESH = "/Game/Scenes/Wings/FlatV3/Scene3/StaticMeshes/SM_FlatV3_S3_Backdrop"
BACKDROP_MI = "/Game/Scenes/Wings/FlatV3/Scene3/Materials/MI_S3_OpalBeach_Backdrop"
WAVE_MESH_ROOT = "/Game/Scenes/Wings/FlatV3/Scene3/StaticMeshes"
FIGURE_LABELS = (
    "Shore01_M56 Clam", "Shore02_F52 Clam", "Shore03_M59 Clam",
    "Shore04_F55 Clam", "Shore05_M53 Clam", "Shore06_F25 Clam",
)
WAVE_LAYOUT = (
    (1, "A", 4200.0, -284.2),
    (1, "B", 4200.0, 186.2),
    (2, "A", 5000.0, -234.0),
    (2, "B", 5000.0, 269.6),
    (3, "A", 5800.0, -83.3),
    (3, "B", 5800.0, 280.4),
)


class PlanError(ValueError):
    pass


def bounds_from_points(points):
    if not points:
        raise PlanError("cannot form bounds from no points")
    return {
        "min": [min(float(p[i]) for p in points) for i in range(3)],
        "max": [max(float(p[i]) for p in points) for i in range(3)],
    }


def translated_bounds(local_bounds, location):
    return {
        "min": [float(local_bounds["min"][i]) + float(location[i]) for i in range(3)],
        "max": [float(local_bounds["max"][i]) + float(location[i]) for i in range(3)],
    }


def aabb_distance(left, right):
    gaps = []
    for axis in range(3):
        gaps.append(max(0.0,
                        float(left["min"][axis]) - float(right["max"][axis]),
                        float(right["min"][axis]) - float(left["max"][axis])))
    return math.sqrt(sum(value * value for value in gaps))


def validate_box(rows):
    failures = []
    for row in rows:
        bounds = row["landed_dock_aabb"]
        if (bounds["min"][0] < BOX_X[0] - BOX_TOLERANCE_CM or
                bounds["max"][0] > BOX_X[1] + BOX_TOLERANCE_CM or
                bounds["min"][1] < BOX_Y[0] - BOX_TOLERANCE_CM or
                bounds["max"][1] > BOX_Y[1] + BOX_TOLERANCE_CM):
            failures.append({"label": row["label"], "bounds": bounds})
    if failures:
        raise PlanError("target outside landed box: " + json.dumps(failures, sort_keys=True))
    return True


def validate_wave_clearance(rows, ring_bounds):
    failures = []
    for row in rows:
        if row["kind"] != "wave":
            continue
        distance = aabb_distance(row["landed_dock_aabb"], ring_bounds)
        row["ring_aabb_distance_cm"] = round(distance, 3)
        if distance < RING_CLEARANCE_CM - 0.001:
            failures.append({"label": row["label"], "distance_cm": distance})
    if failures:
        raise PlanError("wave inside ring clearance: " + json.dumps(failures, sort_keys=True))
    return True


def validate_labels(existing_labels, planned_labels):
    collisions = sorted(label for label in planned_labels if int(existing_labels.get(label, 0)) != 0)
    if collisions:
        raise PlanError("label already present: " + ", ".join(collisions))
    return True


def validate_backdrop_handedness(measurement):
    bounds_y = measurement["bounds_y_cm"]
    bounds_z = measurement["bounds_z_cm"]
    normal = measurement["normal"]
    if (abs(float(bounds_y[0]) + 1000.0) > 1.0 or
            abs(float(bounds_y[1]) - 1000.0) > 1.0 or
            abs(float(bounds_z[0])) > 1.0 or
            abs(float(bounds_z[1]) - 3000.0) > 1.0):
        raise PlanError("backdrop bounds mismatch: " + json.dumps(measurement, sort_keys=True))
    if float(measurement["du_dY"]) <= 0.0:
        raise PlanError("backdrop du/dY is not positive: " + json.dumps(measurement, sort_keys=True))
    if float(measurement["dv_dZ"]) >= 0.0:
        raise PlanError("backdrop dv/dZ is not negative: " + json.dumps(measurement, sort_keys=True))
    if float(normal[0]) > -0.99 or abs(float(normal[1])) > 0.02 or abs(float(normal[2])) > 0.02:
        raise PlanError("backdrop Front normal is not -X: " + json.dumps(measurement, sort_keys=True))
    return True


def validate_plan(rows, ring_bounds, existing_labels, handedness):
    validate_labels(existing_labels, [row["label"] for row in rows])
    validate_box(rows)
    validate_wave_clearance(rows, ring_bounds)
    validate_backdrop_handedness(handedness)
    return handedness


def project_file(*parts):
    if unreal is None:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    else:
        root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.normpath(os.path.join(root, *parts))


def load_wave_bounds():
    path = project_file("DerivedAssets", "FlatV3", "Scene3", "waves", "validation_summary.json")
    with open(path, encoding="utf-8") as handle:
        validation = json.load(handle)
    result = {}
    for name, row in validation["assets"].items():
        bounds = row["fbx_validation"]["bounds_m"]
        result[name] = {
            "min": [float(value) * 100.0 for value in bounds["min"]],
            "max": [float(value) * 100.0 for value in bounds["max"]],
        }
    return result


def load_backdrop_bounds():
    path = project_file("DerivedAssets", "FlatV3", "Scene3", "backdrop",
                        "SM_FlatV3_S3_Backdrop_validation.json")
    with open(path, encoding="utf-8") as handle:
        validation = json.load(handle)
    bounds = validation["checks"]["bottom_centre_origin"]["bounds_m"]
    return {
        "min": [float(value) * 100.0 for value in bounds["min"]],
        "max": [float(value) * 100.0 for value in bounds["max"]],
    }


def offline_wave_rows():
    bounds_by_name = load_wave_bounds()
    rows = []
    for row_number, half, x, y in WAVE_LAYOUT:
        name = "S3_WaveRow%d_%s" % (row_number, half)
        location = [x, y, -5.0]
        rows.append({
            "kind": "wave",
            "row": row_number,
            "half": half,
            "label": "S3 Wave Row%d %s" % (row_number, half),
            "tag": WAVE_TAG,
            "folder": "RigAtmos/S3Waves",
            "parent_label": ROOT_LABEL,
            "mesh_path": "%s/SM_FlatV3_%s" % (WAVE_MESH_ROOT, name),
            "material_path": None,
            "landed_dock_transform": {
                "location": location,
                "rotation": [0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0],
            },
            "landed_dock_aabb": translated_bounds(bounds_by_name[name], location),
        })
    return rows


def package_census():
    def names(packages):
        return sorted(str(p.get_name()).split(".", 1)[0] for p in packages)
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


def distance(a, b):
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def rotation_error(a, b):
    delta = unreal.MathLibrary.normalized_delta_rotator(a, b)
    return max(abs(float(delta.pitch)), abs(float(delta.yaw)), abs(float(delta.roll)))


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


def frame_value(value):
    if hasattr(value, "frame_number"):
        return int(value.frame_number.value)
    if hasattr(value, "value"):
        return int(value.value)
    return int(value)


def canonical_channel_name(name):
    axes = (
        "Location.X", "Location.Y", "Location.Z",
        "Rotation.X", "Rotation.Y", "Rotation.Z",
        "Scale.X", "Scale.Y", "Scale.Z",
    )
    for candidate in axes:
        if name == candidate or name.startswith(candidate + "_"):
            return candidate
    return None


def transform_values(value):
    rotation = value.rotation.rotator()
    return {
        "Location.X": float(value.translation.x),
        "Location.Y": float(value.translation.y),
        "Location.Z": float(value.translation.z),
        "Rotation.X": float(rotation.roll),
        "Rotation.Y": float(rotation.pitch),
        "Rotation.Z": float(rotation.yaw),
        "Scale.X": float(value.scale3d.x),
        "Scale.Y": float(value.scale3d.y),
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
        raise PlanError("unexpected transform track count for " + actor.get_actor_label())
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


def least_squares_slope(independent, dependent, label):
    if len(independent) != len(dependent) or len(independent) < 3:
        raise PlanError("invalid regression input for %s: %d samples" %
                        (label, len(independent)))
    mean_x = sum(independent) / len(independent)
    mean_y = sum(dependent) / len(dependent)
    denominator = sum((value - mean_x) ** 2 for value in independent)
    if denominator <= 1e-9:
        raise PlanError("degenerate regression axis for " + label)
    return sum((x - mean_x) * (y - mean_y)
               for x, y in zip(independent, dependent)) / denominator


def measure_backdrop_handedness(mesh):
    section = unreal.ProceduralMeshLibrary.get_section_from_static_mesh(mesh, 0, 0)
    if not isinstance(section, tuple) or len(section) < 5:
        raise PlanError("backdrop LOD0 section read-back returned an unexpected value")
    vertices, triangles, normals, uvs, tangents = section[:5]
    if len(vertices) < 3 or len(vertices) != len(uvs) or len(vertices) != len(normals):
        raise PlanError("backdrop LOD0 section arrays do not align")
    ys = [float(point.y) for point in vertices]
    zs = [float(point.z) for point in vertices]
    us = [float(uv.x) for uv in uvs]
    vs = [float(uv.y) for uv in uvs]
    normal = [sum(float(value.x) for value in normals) / len(normals),
              sum(float(value.y) for value in normals) / len(normals),
              sum(float(value.z) for value in normals) / len(normals)]
    length = math.sqrt(sum(value * value for value in normal))
    if length <= 1e-9:
        raise PlanError("backdrop mean Front normal is degenerate")
    normal = [value / length for value in normal]
    return {
        "bounds_y_cm": [min(ys), max(ys)],
        "bounds_z_cm": [min(zs), max(zs)],
        "du_dY": least_squares_slope(ys, us, "du/dY"),
        "dv_dZ": least_squares_slope(zs, vs, "dv/dZ"),
        "normal": normal,
        "vertices": len(vertices),
        "triangles": len(triangles) // 3,
    }


def unreal_box_points(minimum, maximum):
    return [unreal.Vector(x, y, z) for x in (minimum.x, maximum.x)
            for y in (minimum.y, maximum.y) for z in (minimum.z, maximum.z)]


def transformed_mesh_bounds(mesh, transform):
    box = mesh.get_bounding_box()
    return bounds_from_points([vector(unreal.MathLibrary.transform_location(transform, point))
                               for point in unreal_box_points(box.min, box.max)])


def current_ring_bounds(index, dock):
    points = []
    for label in FIGURE_LABELS:
        actor = one_actor(index, label)
        origin, extent = actor.get_actor_bounds(False, True)
        minimum = unreal.Vector(origin.x - extent.x, origin.y - extent.y, origin.z - extent.z)
        maximum = unreal.Vector(origin.x + extent.x, origin.y + extent.y, origin.z + extent.z)
        for point in unreal_box_points(minimum, maximum):
            points.append(vector(unreal.MathLibrary.inverse_transform_location(dock, point)))
    return bounds_from_points(points)


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
    if revert and not os.path.isfile(record_path()):
        raise PlanError("REVERT_RECORD_ABSENT")
    if apply and os.path.exists(record_path()):
        raise PlanError("APPLY_RECORD_ALREADY_EXISTS")
    return world


def record_path():
    if unreal is None:
        here = os.path.dirname(os.path.abspath(__file__))
    else:
        here = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexConductor")
    return os.path.join(here, "s3_flats_place_record.json")


def live_plan(run):
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    index = actor_index(actors)
    root = one_actor(index, ROOT_LABEL)
    far_wall = one_actor(index, FAR_WALL_LABEL)
    rise = unreal.load_asset(RISE_PATH)
    if not isinstance(rise, unreal.LevelSequence):
        raise PlanError("S3 hangar rise LevelSequence missing")
    bindings = [binding for binding in rise.get_bindings()
                if str(binding.get_display_name()) == ROOT_LABEL and
                binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack)]
    if len(bindings) != 1:
        raise PlanError("expected one S3 Hangar Root transform binding, found %d" % len(bindings))
    root_rest, root_landed = sequence_rest_landed(bindings[0], root)
    root_current = root.get_actor_transform()
    root_rest_error = {
        "location_cm": distance(root_current.translation, root_rest.translation),
        "rotation_deg": rotation_error(root_current.rotation.rotator(), root_rest.rotation.rotator()),
    }
    if root_rest_error["location_cm"] > 1.0 or root_rest_error["rotation_deg"] > 0.05:
        raise PlanError("root rest pose mismatch: " + json.dumps(root_rest_error, sort_keys=True))

    def predicted(actor, root_override):
        if actor is root:
            return root_override
        parent = actor.get_attach_parent_actor()
        local_or_world = actor.root_component.get_relative_transform() if parent else actor.get_actor_transform()
        return unreal.MathLibrary.compose_transforms(local_or_world, predicted(parent, root_override)) if parent else local_or_world

    far_rest = predicted(far_wall, root_rest)
    far_landed = predicted(far_wall, root_landed)
    dock = unreal.Transform(location=unreal.Vector(*DOCK_ORIGIN),
                            rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=DOCK_YAW))
    ring_bounds = current_ring_bounds(index, dock)
    backdrop_mesh = unreal.load_asset(BACKDROP_MESH)
    handedness = (measure_backdrop_handedness(backdrop_mesh)
                  if isinstance(backdrop_mesh, unreal.StaticMesh) else None)
    backdrop_transform = {
        "location": [6497.0, 0.0, -5.0],
        "rotation": [0.0, 0.0, 0.0],
        "scale": [1.0, 1.0, 1.0],
    }
    rows = offline_wave_rows()
    backdrop_unreal = transform_from_plain(backdrop_transform)
    rows.append({
        "kind": "backdrop",
        "label": BACKDROP_LABEL,
        "tag": BACKDROP_TAG,
        "folder": "RigAtmos/S3Backdrop",
        "parent_label": FAR_WALL_LABEL,
        "mesh_path": BACKDROP_MESH,
        "material_path": BACKDROP_MI,
        "landed_dock_transform": backdrop_transform,
        "landed_dock_aabb": (transformed_mesh_bounds(backdrop_mesh, backdrop_unreal)
                             if isinstance(backdrop_mesh, unreal.StaticMesh)
                             else translated_bounds(load_backdrop_bounds(),
                                                    backdrop_transform["location"])),
    })
    existing = {label: len(index.get(label, [])) for label in [row["label"] for row in rows]}
    validate_labels(existing, [row["label"] for row in rows])
    validate_box(rows)
    validate_wave_clearance(rows, ring_bounds)
    blockers = []
    if handedness is None:
        blockers.append("Revision 2 backdrop mesh is not imported; Unreal LOD0 handedness gate cannot run: " +
                        BACKDROP_MESH)
    else:
        validate_backdrop_handedness(handedness)
        unreal.log("S3_BACKDROP_HANDEDNESS|run=%s|du_dY=%.9g|dv_dZ=%.9g|normal=%s" %
                   (run, handedness["du_dY"], handedness["dv_dZ"],
                    ",".join("%.6f" % value for value in handedness["normal"])))
    parent_state = {
        ROOT_LABEL: {"actor": root, "rest": root_rest, "landed": root_landed},
        FAR_WALL_LABEL: {"actor": far_wall, "rest": far_rest, "landed": far_landed},
    }
    runtime_rows = []
    report_rows = []
    for row in rows:
        parent = parent_state[row["parent_label"]]
        dock_wanted = transform_from_plain(row["landed_dock_transform"])
        world_wanted = unreal.MathLibrary.compose_transforms(dock_wanted, dock)
        relative = unreal.MathLibrary.make_relative_transform(world_wanted, parent["landed"])
        rest_world = unreal.MathLibrary.compose_transforms(relative, parent["rest"])
        asset_ready = bool(unreal.EditorAssetLibrary.does_asset_exist(row["mesh_path"]))
        material_ready = row["material_path"] is None or bool(
            unreal.EditorAssetLibrary.does_asset_exist(row["material_path"]))
        report = dict(row)
        report.update({
            "relative_to_parent_for_landed_pose": transform_plain(relative),
            "composed_rest_world_transform": transform_plain(rest_world),
            "mesh_exists": asset_ready,
            "material_exists": material_ready,
        })
        report_rows.append(report)
        runtime_rows.append({"report": report, "parent": parent["actor"],
                             "relative": relative, "rest_world": rest_world})
    report = {
        "dock_frame": {"origin_world_cm": list(DOCK_ORIGIN), "yaw_deg": DOCK_YAW},
        "root_rest_error": root_rest_error,
        "ring_outer_figure_aabb_dock_cm": ring_bounds,
        "backdrop_handedness": {
            "verdict": "PASS" if handedness is not None else "NOT_RUN_MESH_ABSENT",
            "lod0_section_measurement": handedness,
            "cottages_check": "darker cottages remain on screen-right (+Y dock)",
        },
        "blockers": blockers,
        "rows": report_rows,
    }
    return report, runtime_rows


def package_filename(package_name, is_map=False):
    if not package_name.startswith("/Game/"):
        return None
    content = project_file("Content")
    extension = ".umap" if is_map else ".uasset"
    return os.path.join(content, *package_name[len("/Game/"):].split("/")) + extension


def backup_level_and_parents(runtime_rows, prefix):
    stamp = datetime.datetime.now()
    backup = project_file("Backups", prefix + stamp.strftime("%Y%m%d-%H%M"))
    if os.path.exists(backup):
        raise PlanError("BACKUP_EXISTS|path=" + backup)
    packages = {EXPECTED_WORLD: True}
    for row in runtime_rows:
        packages[str(row["parent"].get_outermost().get_name()).split(".", 1)[0]] = False
    sources = []
    for package, is_map in packages.items():
        filename = package_filename(package, is_map)
        if filename and os.path.isfile(filename):
            sources.append(filename)
    level_file = package_filename(EXPECTED_WORLD, True)
    if level_file not in sources:
        raise PlanError("LEVEL_BACKUP_SOURCE_MISSING|path=" + str(level_file))
    os.makedirs(backup)
    copied = []
    content = project_file("Content")
    for source in sorted(set(sources)):
        relative = os.path.relpath(source, content)
        destination = os.path.join(backup, "Content", relative)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(relative.replace("\\", "/"))
    return backup, copied


def write_record(value):
    with open(record_path(), "x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=1, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())


def save_record(value):
    with open(record_path(), "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=1, sort_keys=True)


def exact_level_dirty():
    census = package_census()
    if census["content"] or census["maps"] != [EXPECTED_WORLD]:
        raise PlanError("DIRTY_CENSUS_NOT_EXACT_LEVEL|census=" + json.dumps(census, sort_keys=True))
    return census


def save_level_clean():
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        raise PlanError("LEVEL_SAVE_FAILED")
    census = package_census()
    if census["maps"] or census["content"]:
        raise PlanError("POST_SAVE_DIRTY|census=" + json.dumps(census, sort_keys=True))
    return census


def apply_plan(run, report, runtime_rows):
    unavailable = [row["report"]["label"] for row in runtime_rows
                   if not row["report"]["mesh_exists"] or not row["report"]["material_exists"]]
    if unavailable:
        raise PlanError("TARGET_ASSETS_NOT_READY|labels=" + json.dumps(unavailable))
    backup, copied = backup_level_and_parents(runtime_rows, "PreS3FlatsPlace-")
    record = {
        "run": run,
        "written": datetime.datetime.now().isoformat(timespec="seconds"),
        "world": EXPECTED_WORLD,
        "backup": backup,
        "backup_files": copied,
        "plan": report,
        "spawned": [],
    }
    write_record(record)
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for runtime in runtime_rows:
        row = runtime["report"]
        mesh = unreal.load_asset(row["mesh_path"])
        material = unreal.load_asset(row["material_path"]) if row["material_path"] else None
        actor = subsystem.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(), unreal.Rotator())
        if actor is None:
            raise PlanError("SPAWN_FAILED|label=" + row["label"])
        actor.modify(); actor.set_actor_label(row["label"])
        actor.modify(); actor.set_folder_path(row["folder"])
        actor.modify(); actor.set_editor_property("tags", [unreal.Name(row["tag"])])
        component = actor.get_editor_property("static_mesh_component")
        component.modify(); component.set_mobility(unreal.ComponentMobility.MOVABLE)
        component.modify(); component.set_editor_property("static_mesh", mesh)
        if material is not None:
            component.modify(); component.set_material(0, material)
        actor.modify(); actor.set_actor_transform(runtime["relative"], False, True)
        actor.modify(); actor.attach_to_actor(
            runtime["parent"], unreal.Name(""),
            unreal.AttachmentRule.KEEP_RELATIVE, unreal.AttachmentRule.KEEP_RELATIVE,
            unreal.AttachmentRule.KEEP_RELATIVE, False)
        current = actor.get_actor_transform()
        location_error = distance(current.translation, runtime["rest_world"].translation)
        angle_error = rotation_error(current.rotation.rotator(), runtime["rest_world"].rotation.rotator())
        if location_error > 1.0 or angle_error > 0.05:
            raise PlanError("REST_COMPOSITION_MISMATCH|label=%s|cm=%g|deg=%g" %
                            (row["label"], location_error, angle_error))
        if str(actor.get_attach_parent_actor().get_actor_label()) != row["parent_label"]:
            raise PlanError("PARENT_READBACK_MISMATCH|label=" + row["label"])
        tags = [str(value) for value in actor.get_editor_property("tags")]
        if row["tag"] not in tags:
            raise PlanError("TAG_READBACK_MISMATCH|label=" + row["label"])
        record["spawned"].append({
            "label": row["label"], "tag": row["tag"], "object_path": actor.get_path_name(),
            "parent_label": row["parent_label"], "mesh_path": row["mesh_path"],
        })
        save_record(record)
    if len(record["spawned"]) != 7:
        raise PlanError("SPAWN_COUNT_MISMATCH|count=%d" % len(record["spawned"]))
    exact_level_dirty()
    census = save_level_clean()
    record["applied"] = True
    save_record(record)
    unreal.log("S3_FLATS_PLACE_DONE|run=%s|applied|backup=%s|census=%s" %
               (run, backup, json.dumps(census, separators=(",", ":"), sort_keys=True)))


def revert_plan(run):
    with open(record_path(), encoding="utf-8") as handle:
        record = json.load(handle)
    if record.get("world") != EXPECTED_WORLD or not record.get("applied"):
        raise PlanError("REVERT_RECORD_INVALID")
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    index = actor_index(actors)
    targets = []
    for row in record.get("spawned", []):
        matches = index.get(row["label"], [])
        if len(matches) != 1:
            raise PlanError("REVERT_LABEL_COUNT|label=%s|count=%d" % (row["label"], len(matches)))
        actor = matches[0]
        tags = [str(value) for value in actor.get_editor_property("tags")]
        if row["tag"] not in tags or actor.get_path_name() != row["object_path"]:
            raise PlanError("REVERT_OWNERSHIP_MISMATCH|label=" + row["label"])
        targets.append(actor)
    if len(targets) != 7:
        raise PlanError("REVERT_TARGET_COUNT|count=%d" % len(targets))
    runtime_stub = [{"parent": actor} for actor in targets]
    backup, _ = backup_level_and_parents(runtime_stub, "PreS3FlatsPlaceRevert-")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in targets:
        actor.modify()
        if not subsystem.destroy_actor(actor):
            raise PlanError("DESTROY_FAILED|label=" + actor.get_actor_label())
    remaining = actor_index(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    survivors = [row["label"] for row in record["spawned"] if remaining.get(row["label"])]
    if survivors:
        raise PlanError("REVERT_SURVIVORS|labels=" + json.dumps(survivors))
    exact_level_dirty()
    census = save_level_clean()
    archived = record_path() + ".reverted-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    os.rename(record_path(), archived)
    unreal.log("S3_FLATS_PLACE_DONE|run=%s|reverted|backup=%s|record=%s|census=%s" %
               (run, backup, os.path.basename(archived),
                json.dumps(census, separators=(",", ":"), sort_keys=True)))


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    apply = bool(globals().get("S3_FLATS_PLACE_APPLY"))
    revert = bool(globals().get("S3_FLATS_PLACE_REVERT"))
    try:
        if globals().get("S3_FLATS_REVISION") != 2:
            raise PlanError("REVISION_2_WRAPPER_REQUIRED")
        if apply and revert:
            raise PlanError("APPLY_AND_REVERT_BOTH_SET")
        assert_context(apply, revert)
        if revert:
            revert_plan(run)
            return
        report, runtime_rows = live_plan(run)
        unreal.log("S3_FLATS_PLACE_PLAN|run=%s|%s" %
                   (run, json.dumps(report, separators=(",", ":"), sort_keys=True)))
        if report.get("blockers"):
            raise PlanError("; ".join(report["blockers"]))
        if not apply:
            after = package_census()
            if after["maps"] or after["content"]:
                raise PlanError("DRY_RUN_DIRTIED_PACKAGES|census=" + json.dumps(after, sort_keys=True))
            unreal.log("S3_FLATS_PLACE_DRY_RUN_OK|run=%s|mutated=0|waves=6|backdrop=1|handedness=PASS" % run)
            return
        apply_plan(run, report, runtime_rows)
    except PlanError as exc:
        unreal.log_error("S3_FLATS_PLACE_%s_STOPPED|run=%s|mutated=0|reason=%s|census=%s" %
                         ("REVERT" if revert else ("APPLY" if apply else "DRY_RUN"), run, str(exc),
                          json.dumps(package_census(), separators=(",", ":"), sort_keys=True)))
    except Exception:
        unreal.log_error("S3_FLATS_PLACE_ERROR|run=%s|traceback=%s|census=%s" %
                         (run, traceback.format_exc().replace("\n", "\\n"),
                          json.dumps(package_census(), separators=(",", ":"), sort_keys=True)))


if unreal is not None:
    main()
