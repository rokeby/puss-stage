"""Plan, apply, or revert the six hangar exit doorway shells.

Default execution is DRY and read-only.  APPLY and REVERT are available only
through the HANGAR_EXIT_DOORS_APPLY / HANGAR_EXIT_DOORS_REVERT globals used by
the small runner files beside this module.  Importing this module in ordinary
Python never contacts Unreal.

PASS 1 deliberately stops APPLY when a proposed opening intersects a separate
backdrop.  A reviewed Y offset can be supplied in
hangar_exit_doors_overrides.json; the offset must move the entire opening clear
of that backdrop.  Exact UV cropping is not guessed.
"""
import datetime
import json
import math
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
PROBE_NAME = "hangar_exit_doorways_probe.json"
OVERRIDES_NAME = "hangar_exit_doors_overrides.json"
RECORD_NAME = "hangar_exit_doors_record.json"
CUBE_PATH = "/Engine/BasicShapes/Cube.Cube"
BLACK_PATH = "/Engine/EngineMaterials/BlackUnlitMaterial.BlackUnlitMaterial"
STATIC_MESH_LOCAL_BOUNDS_CM = {
    CUBE_PATH: {"min": [-50.0, -50.0, -50.0], "max": [50.0, 50.0, 50.0]},
}
DOOR_WIDTH_CM = 300.0
DOOR_HEIGHT_CM = 450.0
SEAM_CM = 1.0
READBACK_TOLERANCE_CM = 0.1
REQUIRED_TESTS = (
    "InfinityStage.Editor.SavedMasterMatchesShow",
    "InfinityStage.Editor.SceneCutBindingsResolve",
)


if unreal is not None:
    HERE = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexConductor",
    )
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
PROBE_PATH = os.path.join(HERE, PROBE_NAME)
OVERRIDES_PATH = os.path.join(HERE, OVERRIDES_NAME)
RECORD_PATH = os.path.join(HERE, RECORD_NAME)


class PlanError(ValueError):
    pass


def _bounds_overlap_yz(bounds, y0, y1, z0, z1):
    return not (float(bounds["max"][1]) <= y0 or float(bounds["min"][1]) >= y1 or
                float(bounds["max"][2]) <= z0 or float(bounds["min"][2]) >= z1)


def _one_wall_material(scene):
    walls = scene.get("far_walls", [])
    if len(walls) != 1:
        raise PlanError("S%d far-wall count is %d, expected 1" %
                        (scene["scene"], len(walls)))
    components = [row for row in walls[0].get("components", [])
                  if row.get("static_mesh")]
    if len(components) != 1:
        raise PlanError("S%d far wall does not have exactly one mesh component" % scene["scene"])
    slots = components[0].get("materials", [])
    slot0 = [row.get("material") for row in slots if int(row.get("slot", -1)) == 0]
    if len(slot0) != 1 or not slot0[0]:
        raise PlanError("S%d far wall has no unique material slot 0" % scene["scene"])
    return slot0[0], components[0].get("static_mesh"), walls[0], components[0]


def _rotation_matrix(rotation_rpy):
    roll, pitch, yaw = [math.radians(float(value)) for value in rotation_rpy]
    sr, cr = math.sin(roll), math.cos(roll)
    sp, cp = math.sin(pitch), math.cos(pitch)
    sy, cy = math.sin(yaw), math.cos(yaw)
    return (
        (cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
        (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
        (-sp, cp * sr, cp * cr),
    )


def _matrix_vector(matrix, vector):
    return [sum(matrix[row][axis] * vector[axis] for axis in range(3))
            for row in range(3)]


def _inverse_rotate(matrix, vector):
    return [sum(matrix[axis][column] * vector[axis] for axis in range(3))
            for column in range(3)]


def _transform_row(row, description):
    transform = row.get("transform") or {}
    try:
        return (
            [float(value) for value in transform["world_location_cm"]],
            [float(value) for value in transform["world_rotation_rpy"]],
            [float(value) for value in transform["world_scale"]],
        )
    except (KeyError, TypeError, ValueError):
        raise PlanError("%s has no usable world transform" % description)


def _mesh_local_bounds(component, mesh, scene_number):
    bounds = (component.get("static_mesh_local_bounds_cm") or
              component.get("mesh_local_bounds_cm") or
              STATIC_MESH_LOCAL_BOUNDS_CM.get(mesh))
    try:
        minimum = [float(value) for value in bounds["min"]]
        maximum = [float(value) for value in bounds["max"]]
    except (KeyError, TypeError, ValueError):
        raise PlanError("S%d far wall has no usable static-mesh local bounds" % scene_number)
    if len(minimum) != 3 or len(maximum) != 3 or any(
            maximum[axis] <= minimum[axis] for axis in range(3)):
        raise PlanError("S%d far wall static-mesh local bounds are invalid" % scene_number)
    return minimum, maximum


def _wall_bounds_in_root(scene, wall, component, mesh):
    """Return the wall OBB expressed as an AABB in its hangar-root frame."""
    n = int(scene["scene"])
    root = scene.get("root") or {}
    root_location, root_rotation, root_scale = _transform_row(root, "S%d hangar root" % n)
    # The probed far wall is a StaticMeshActor, so its StaticMeshComponent is
    # the actor root.  Prefer a future component transform if the probe records
    # one, and otherwise use that root-component actor transform.
    component_frame = component if component.get("transform") else wall
    wall_location, wall_rotation, wall_scale = _transform_row(
        component_frame, "S%d far-wall mesh component" % n)
    if any(abs(value) <= 1.0e-9 for value in root_scale + wall_scale):
        raise PlanError("S%d far wall or hangar root has zero scale" % n)
    local_min, local_max = _mesh_local_bounds(component, mesh, n)
    wall_matrix = _rotation_matrix(wall_rotation)
    root_matrix = _rotation_matrix(root_rotation)
    points = []
    for x in (local_min[0], local_max[0]):
        for y in (local_min[1], local_max[1]):
            for z in (local_min[2], local_max[2]):
                scaled = [x * wall_scale[0], y * wall_scale[1], z * wall_scale[2]]
                world_offset = _matrix_vector(wall_matrix, scaled)
                world = [wall_location[axis] + world_offset[axis] for axis in range(3)]
                relative_world = [world[axis] - root_location[axis] for axis in range(3)]
                unrotated = _inverse_rotate(root_matrix, relative_world)
                points.append([unrotated[axis] / root_scale[axis] for axis in range(3)])
    return {
        "min": [min(point[axis] for point in points) for axis in range(3)],
        "max": [max(point[axis] for point in points) for axis in range(3)],
    }


def _override_offsets(overrides):
    rows = {} if overrides is None else overrides.get("scenes", {})
    result = {}
    for key, value in rows.items():
        try:
            scene = int(key)
            result[scene] = float(value["door_offset_y_cm"])
        except (KeyError, TypeError, ValueError):
            raise PlanError("invalid override for scene %r" % key)
    if any(scene not in range(1, 7) for scene in result):
        raise PlanError("override scene must be 1..6")
    return result


def plan_doors(probe, overrides=None):
    """Build the deterministic, Unreal-free doorway plan."""
    if int(probe.get("schema_version", 0)) != 1:
        raise PlanError("probe schema_version is not 1")
    if probe.get("world") != EXPECTED_WORLD:
        raise PlanError("probe world mismatch")
    if probe.get("census_before") != probe.get("census_after"):
        raise PlanError("probe package census changed")
    scenes = list(probe.get("scenes", []))
    if sorted(int(row.get("scene", -1)) for row in scenes) != list(range(1, 7)):
        raise PlanError("probe must contain exactly scenes 1..6")
    offsets = _override_offsets(overrides)
    plans = []
    questions = []
    for scene in sorted(scenes, key=lambda row: int(row["scene"])):
        n = int(scene["scene"])
        if int(scene.get("root_count", 0)) != 1:
            raise PlanError("S%d root count is not 1" % n)
        if scene.get("landed_preview_root_up") is not True:
            raise PlanError("S%d landed preview root is not UP" % n)
        if int(scene.get("exit_camera_count", 0)) != 1:
            raise PlanError("S%d Exit camera count is not 1" % n)
        wall_material, wall_mesh, wall, wall_component = _one_wall_material(scene)
        hangar = scene.get("hangar", {})
        required = ("depth", "half_w", "height", "wall_t", "roof", "hinge_z")
        if any(key not in hangar for key in required):
            raise PlanError("S%d hangar dimensions are incomplete" % n)
        depth = float(hangar["depth"])
        half_w = float(hangar["half_w"])
        height = float(hangar["height"])
        wall_t = float(hangar["wall_t"])
        floor_z = float(hangar["hinge_z"])
        if min(depth, half_w, height, wall_t) <= 0.0 or height <= DOOR_HEIGHT_CM:
            raise PlanError("S%d hangar dimensions cannot contain the door" % n)
        wall_bounds = _wall_bounds_in_root(scene, wall, wall_component, wall_mesh)
        measured_size = [float(wall_bounds["max"][axis]) - float(wall_bounds["min"][axis])
                         for axis in range(3)]
        expected_size = [wall_t, 2.0 * (half_w + wall_t), height]
        if any(abs(left - right) > 2.0 for left, right in
               zip(measured_size, expected_size)):
            raise PlanError("S%d far-wall size disagrees with the builder: measured=%r expected=%r" %
                            (n, measured_size, expected_size))

        offset = offsets.get(n, 0.0)
        opening_y0 = offset - DOOR_WIDTH_CM / 2.0
        opening_y1 = offset + DOOR_WIDTH_CM / 2.0
        wall_y0, wall_y1 = float(wall_bounds["min"][1]), float(wall_bounds["max"][1])
        if opening_y0 <= wall_y0 + SEAM_CM or opening_y1 >= wall_y1 - SEAM_CM:
            raise PlanError("S%d door offset leaves no side-wall margin" % n)
        opening_z0, opening_z1 = floor_z, floor_z + DOOR_HEIGHT_CM
        crossing = []
        for backdrop in scene.get("backdrops", []):
            bounds = backdrop.get("bounds_dock_cm")
            if bounds and _bounds_overlap_yz(bounds, opening_y0, opening_y1,
                                             opening_z0, opening_z1):
                crossing.append(str(backdrop.get("label")))
        if crossing:
            questions.append({
                "scene": n,
                "reason": "backdrop_uv_match_required",
                "backdrops": crossing,
                "draft_offset_y_cm": offset,
            })

        x = (float(wall_bounds["min"][0]) + float(wall_bounds["max"][0])) / 2.0
        left_width = opening_y0 - wall_y0
        right_width = wall_y1 - opening_y1
        header_height = height - DOOR_HEIGHT_CM
        pieces = [
            {"role": "above", "label": "S%d Hangar Far Wall Above Exit" % n,
             "location_cm": [x, 0.0, floor_z + DOOR_HEIGHT_CM + header_height / 2.0],
             "size_cm": [wall_t, wall_y1 - wall_y0, header_height], "material": wall_material},
            {"role": "left", "label": "S%d Hangar Far Wall Left of Exit" % n,
             "location_cm": [x, wall_y0 + left_width / 2.0, floor_z + DOOR_HEIGHT_CM / 2.0],
             "size_cm": [wall_t, left_width, DOOR_HEIGHT_CM], "material": wall_material},
            {"role": "right", "label": "S%d Hangar Far Wall Right of Exit" % n,
             "location_cm": [x, opening_y1 + right_width / 2.0, floor_z + DOOR_HEIGHT_CM / 2.0],
             "size_cm": [wall_t, right_width, DOOR_HEIGHT_CM], "material": wall_material},
            {"role": "leaf", "label": "S%d Hangar Exit Door Leaf" % n,
             "location_cm": [x - 0.05, offset, floor_z + DOOR_HEIGHT_CM / 2.0],
             "size_cm": [wall_t, DOOR_WIDTH_CM - SEAM_CM, DOOR_HEIGHT_CM - SEAM_CM],
             "material": wall_material, "state": "closed"},
            {"role": "black", "label": "S%d Hangar Exit Black" % n,
             "location_cm": [float(wall_bounds["max"][0]) + 2.0, offset,
                             floor_z + DOOR_HEIGHT_CM / 2.0],
             "size_cm": [2.0, DOOR_WIDTH_CM, DOOR_HEIGHT_CM], "material": BLACK_PATH},
        ]
        plans.append({
            "scene": n,
            "root_label": "S%d Hangar Root" % n,
            "source_wall_label": "S%d Hangar Far Wall" % n,
            "wall_material": wall_material,
            "wall_mesh": wall_mesh,
            "wall_bounds_root_cm": wall_bounds,
            "piece_coordinate_frame": "hangar_root",
            "door_offset_y_cm": offset,
            "door_center_dock_cm": [depth, offset, floor_z + DOOR_HEIGHT_CM / 2.0],
            "camera_to_door_distance_cm": scene.get("camera_to_door_distance_cm"),
            "straight_walk": scene.get("straight_walk"),
            "roof": bool(hangar["roof"]),
            "backdrop_crossings": crossing,
            "surface_strategy": "far_wall_material" if not crossing else "UNRESOLVED_BACKDROP_UV",
            "pieces": pieces,
        })
    return {
        "world": EXPECTED_WORLD,
        "probe_run": probe.get("run"),
        "door_cm": {"width": DOOR_WIDTH_CM, "height": DOOR_HEIGHT_CM, "seam": SEAM_CM},
        "scenes": plans,
        "open_questions": questions,
        "apply_ready": not questions,
        "required_tests": list(REQUIRED_TESTS),
    }


def _load_json(path, required=True):
    if not os.path.isfile(path):
        if required:
            raise PlanError("required file is absent: " + path)
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def package_census():
    def names(values):
        return sorted(str(value.get_name()).split(".", 1)[0] for value in values)
    return {
        "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def stop(run, reason):
    unreal.log_error("HANGAR_EXIT_DOORS_STOPPED|run=%s|%s" % (run, reason))
    raise RuntimeError(reason)


def actor_index():
    result = {}
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        result.setdefault(str(actor.get_actor_label()), []).append(actor)
    return result


def one_actor(index, label, run):
    rows = index.get(label, [])
    if len(rows) != 1:
        stop(run, "reason=ACTOR_COUNT|label=%s|count=%d" % (label, len(rows)))
    return rows[0]


def _plain_actor(actor):
    parent = actor.get_attach_parent_actor()
    component = actor.get_editor_property("static_mesh_component")
    return {
        "label": str(actor.get_actor_label()),
        "parent_label": str(parent.get_actor_label()) if parent else None,
        "location": [float(value) for value in actor.get_actor_location().to_tuple()],
        "rotation": [float(actor.get_actor_rotation().roll), float(actor.get_actor_rotation().pitch),
                     float(actor.get_actor_rotation().yaw)],
        "scale": [float(value) for value in actor.get_actor_scale3d().to_tuple()],
        "mesh": str(component.get_editor_property("static_mesh").get_path_name()),
        "material": str(component.get_material(0).get_path_name()),
        "tags": [str(tag) for tag in actor.tags],
    }


def _plain_pose(actor):
    return {
        "location": [float(value) for value in actor.get_actor_location().to_tuple()],
        "rotation": [float(actor.get_actor_rotation().roll), float(actor.get_actor_rotation().pitch),
                     float(actor.get_actor_rotation().yaw)],
        "scale": [float(value) for value in actor.get_actor_scale3d().to_tuple()],
    }


def _same_vector(left, right, tolerance=READBACK_TOLERANCE_CM):
    return max(abs(float(left[index]) - float(right[index])) for index in range(3)) <= tolerance


def _set_root_local(actor, root, location, size):
    actor.attach_to_actor(root, unreal.Name("None"), unreal.AttachmentRule.KEEP_WORLD,
                          unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
    actor.set_actor_relative_location(unreal.Vector(*location), False, True)
    actor.set_actor_relative_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0), False, True)
    actor.set_actor_relative_scale3d(unreal.Vector(size[0] / 100.0, size[1] / 100.0, size[2] / 100.0))


def _spawn_piece(subsystem, root, piece, cube, material):
    actor = subsystem.spawn_actor_from_class(unreal.StaticMeshActor, root.get_actor_location(),
                                             root.get_actor_rotation(), False)
    actor.set_actor_label(piece["label"])
    component = actor.get_editor_property("static_mesh_component")
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    component.set_static_mesh(cube)
    component.set_material(0, material)
    component.set_cast_shadow(piece["role"] != "black")
    _set_root_local(actor, root, piece["location_cm"], piece["size_cm"])
    actor.tags = [unreal.Name("HangarExitDoor"), unreal.Name("HangarExit.%s" % piece["role"])]
    return actor


def _context(run):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        stop(run, "reason=PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
        stop(run, "reason=WRONG_WORLD")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        stop(run, "reason=SEQUENCER_IS_OPEN")
    census = package_census()
    if census != {"content": [], "maps": []}:
        stop(run, "reason=DIRTY_BEFORE|census=" + json.dumps(census, sort_keys=True))
    return world


def _level_disk_path():
    relative = EXPECTED_WORLD.removeprefix("/Game/").replace("/", os.sep) + ".umap"
    return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()), relative)


def _backup(run, purpose):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    folder = os.path.join(project, "Backups", "%s-%s" % (purpose, run))
    os.makedirs(folder, exist_ok=False)
    source = _level_disk_path()
    if not os.path.isfile(source):
        stop(run, "reason=LEVEL_BACKUP_SOURCE_MISSING|path=" + source)
    target = os.path.join(folder, os.path.basename(source))
    shutil.copy2(source, target)
    with open(os.path.join(folder, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump({"run": run, "world": EXPECTED_WORLD, "source": source,
                   "backup": target, "bytes": os.path.getsize(target)}, handle, indent=2)
    return folder


def _save_level_only(run):
    census = package_census()
    if census != {"content": [], "maps": [EXPECTED_WORLD]}:
        stop(run, "reason=TOUCHED_CENSUS|census=" + json.dumps(census, sort_keys=True))
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        stop(run, "reason=LEVEL_SAVE_FAILED")
    final = package_census()
    if final != {"content": [], "maps": []}:
        stop(run, "reason=DIRTY_AFTER_SAVE|census=" + json.dumps(final, sort_keys=True))
    return final


def _write_record(record, mode="w"):
    with open(RECORD_PATH, mode, encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)


def apply_plan(plan, run):
    if not plan["apply_ready"]:
        stop(run, "reason=UNRESOLVED_BACKDROP_UV|questions=" +
             json.dumps(plan["open_questions"], separators=(",", ":"), sort_keys=True))
    if os.path.exists(RECORD_PATH):
        stop(run, "reason=APPLY_RECORD_ALREADY_EXISTS")
    cube = unreal.load_asset(CUBE_PATH)
    black = unreal.load_asset(BLACK_PATH)
    if cube is None or black is None:
        stop(run, "reason=REQUIRED_ENGINE_ASSET_MISSING")
    index = actor_index()
    root_before = {}
    originals = []
    all_new_labels = []
    for scene in plan["scenes"]:
        root = one_actor(index, scene["root_label"], run)
        wall = one_actor(index, scene["source_wall_label"], run)
        root_before[str(scene["scene"])] = _plain_pose(root)
        wall_before = _plain_actor(wall)
        if (wall_before["mesh"] != scene["wall_mesh"] or
                wall_before["material"] != scene["wall_material"]):
            stop(run, "reason=LIVE_WALL_SURFACE_CHANGED|scene=%d" % scene["scene"])
        originals.append({"scene": scene["scene"], "actor": wall_before})
        all_new_labels.extend(piece["label"] for piece in scene["pieces"])
    conflicts = [label for label in all_new_labels if label in index]
    if conflicts:
        stop(run, "reason=TARGET_LABELS_ALREADY_EXIST|labels=" + json.dumps(conflicts))

    backup = _backup(run, "PreHangarExitDoors")
    record = {"schema_version": 1, "run": run, "world": EXPECTED_WORLD,
              "backup": backup, "probe_run": plan["probe_run"], "plan": plan,
              "root_before": root_before, "originals": originals, "created": [],
              "applied": False, "required_tests": list(REQUIRED_TESTS)}
    _write_record(record, "x")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for scene in plan["scenes"]:
        index = actor_index()
        root = one_actor(index, scene["root_label"], run)
        wall = one_actor(index, scene["source_wall_label"], run)
        source_material = unreal.load_asset(scene["wall_material"])
        if source_material is None:
            stop(run, "reason=WALL_MATERIAL_LOAD_FAILED|scene=%d" % scene["scene"])
        above = next(piece for piece in scene["pieces"] if piece["role"] == "above")
        wall.set_actor_label(above["label"])
        component = wall.get_editor_property("static_mesh_component")
        component.set_static_mesh(cube)
        component.set_material(0, source_material)
        _set_root_local(wall, root, above["location_cm"], above["size_cm"])
        record["created"].append({"scene": scene["scene"], "label": above["label"],
                                  "reused_original": True})
        for piece in scene["pieces"]:
            if piece["role"] == "above":
                continue
            material = black if piece["role"] == "black" else source_material
            _spawn_piece(subsystem, root, piece, cube, material)
            record["created"].append({"scene": scene["scene"], "label": piece["label"],
                                      "reused_original": False})
        _write_record(record)
    final = _save_level_only(run)
    index = actor_index()
    for scene in plan["scenes"]:
        root = one_actor(index, scene["root_label"], run)
        before = root_before[str(scene["scene"])]
        now = _plain_pose(root)
        if (not _same_vector(before["location"], now["location"]) or
                not _same_vector(before["rotation"], now["rotation"], 0.001) or
                not _same_vector(before["scale"], now["scale"], 0.000001)):
            stop(run, "reason=ROOT_MOVED|scene=%d" % scene["scene"])
        for piece in scene["pieces"]:
            actor = one_actor(index, piece["label"], run)
            location = list(actor.root_component.get_editor_property("relative_location").to_tuple())
            if not _same_vector(location, piece["location_cm"]):
                stop(run, "reason=PIECE_READBACK|label=" + piece["label"])
    record["applied"] = True
    record["post_save_census"] = final
    record["landed_preview_roots_unchanged"] = True
    _write_record(record)
    unreal.log("HANGAR_EXIT_DOORS_APPLY_OK|run=%s|scenes=6|state=closed|backup=%s|census=%s|tests_required_singly=%s" %
               (run, backup, json.dumps(final, separators=(",", ":")), ",".join(REQUIRED_TESTS)))


def _restore_actor(actor, row, index, run):
    parent = one_actor(index, row["parent_label"], run) if row.get("parent_label") else None
    actor.detach_from_actor(unreal.DetachmentRule.KEEP_WORLD,
                            unreal.DetachmentRule.KEEP_WORLD,
                            unreal.DetachmentRule.KEEP_WORLD)
    actor.set_actor_location(unreal.Vector(*row["location"]), False, True)
    actor.set_actor_rotation(unreal.Rotator(roll=row["rotation"][0], pitch=row["rotation"][1],
                                            yaw=row["rotation"][2]), False)
    actor.set_actor_scale3d(unreal.Vector(*row["scale"]))
    if parent:
        actor.attach_to_actor(parent, unreal.Name("None"), unreal.AttachmentRule.KEEP_WORLD,
                              unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
    actor.set_actor_label(row["label"])
    actor.tags = [unreal.Name(value) for value in row.get("tags", [])]
    component = actor.get_editor_property("static_mesh_component")
    component.set_static_mesh(unreal.load_asset(row["mesh"]))
    component.set_material(0, unreal.load_asset(row["material"]))


def revert_plan(run):
    record = _load_json(RECORD_PATH)
    if record.get("world") != EXPECTED_WORLD or not record.get("applied"):
        stop(run, "reason=REVERT_RECORD_CONTEXT")
    backup = _backup(run, "PreHangarExitDoorsRevert")
    index = actor_index()
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    originals = {int(row["scene"]): row["actor"] for row in record["originals"]}
    for scene in record["plan"]["scenes"]:
        n = int(scene["scene"])
        for piece in scene["pieces"]:
            found = index.get(piece["label"], [])
            if len(found) != 1:
                stop(run, "reason=REVERT_PIECE_COUNT|label=%s|count=%d" %
                     (piece["label"], len(found)))
            if piece["role"] == "above":
                _restore_actor(found[0], originals[n], index, run)
            else:
                subsystem.destroy_actor(found[0])
        index = actor_index()
    final = _save_level_only(run)
    index = actor_index()
    for n in range(1, 7):
        one_actor(index, "S%d Hangar Far Wall" % n, run)
        for suffix in ("Above Exit", "Left of Exit", "Right of Exit"):
            if "S%d Hangar Far Wall %s" % (n, suffix) in index:
                stop(run, "reason=REVERT_LABEL_REMAINS|scene=%d" % n)
    archived = RECORD_PATH + ".reverted-" + run
    os.rename(RECORD_PATH, archived)
    unreal.log("HANGAR_EXIT_DOORS_REVERT_OK|run=%s|scenes=6|backup=%s|record=%s|census=%s|tests_required_singly=%s" %
               (run, backup, os.path.basename(archived),
                json.dumps(final, separators=(",", ":")), ",".join(REQUIRED_TESTS)))


def main():
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    apply = bool(globals().get("HANGAR_EXIT_DOORS_APPLY"))
    revert = bool(globals().get("HANGAR_EXIT_DOORS_REVERT"))
    if apply and revert:
        stop(run, "reason=APPLY_AND_REVERT_BOTH_SET")
    _context(run)
    if revert:
        revert_plan(run)
        return
    try:
        probe = _load_json(PROBE_PATH)
        overrides = _load_json(OVERRIDES_PATH, required=False)
        plan = plan_doors(probe, overrides)
    except PlanError as exc:
        stop(run, "reason=PLAN_REFUSED|detail=" + str(exc))
    if not apply:
        final = package_census()
        if final != {"content": [], "maps": []}:
            stop(run, "reason=DRY_RUN_DIRTIED_PACKAGES|census=" + json.dumps(final, sort_keys=True))
        unreal.log("HANGAR_EXIT_DOORS_DRY_OK|run=%s|mutated=0|apply_ready=%d|plan=%s" %
                   (run, int(plan["apply_ready"]),
                    json.dumps(plan, separators=(",", ":"), sort_keys=True)))
        return
    apply_plan(plan, run)


if unreal is not None:
    main()
