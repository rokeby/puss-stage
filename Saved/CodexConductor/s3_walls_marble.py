"""Draft, apply, or revert marble liners on Scene 3's inner side walls.

The tool copies the live Clam_Pedastal material onto two new, thin inner-face
liners. It never changes the existing wall material slots, the far wall, the
plinth, or any material asset. Dry run is the default; wrappers opt into writes.
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
SOURCE_LABEL = "Clam_Pedastal"
TARGETS = (
    {"wall_label": "S3 Hangar Left Wall", "liner_label": "S3 Marble Inner Wall Left", "interior_sign": 1.0},
    {"wall_label": "S3 Hangar Right Wall", "liner_label": "S3 Marble Inner Wall Right", "interior_sign": -1.0},
)
FAR_WALL_LABEL = "S3 Hangar Far Wall"
CUBE = "/Engine/BasicShapes/Cube"
EXPECTED_STEEL = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_01/Materials/M_Metal_Black_01_Mat"
DISK_PLINTH_MI = "/Game/Fab/Megascans/3D/Roman_Marble_Plinth_tg0pfjxda/Raw/tg0pfjxda_tier_0/Materials/MI_tg0pfjxda"
WALL_THICKNESS_CM = 50.0
LINER_THICKNESS_CM = 1.0
TAG = "RigAtmos.S3MarbleLiner"
FOLDER = "RigAtmos/S3Marble"


class PlanError(ValueError):
    pass


def project_file(*parts):
    if unreal is None:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    else:
        root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.normpath(os.path.join(root, *parts))


def record_path():
    return project_file("Saved", "CodexConductor", "s3_walls_marble_record.json")


def normalize_asset_path(value):
    if value is None:
        return None
    try:
        value = value.get_path_name()
    except Exception:
        pass
    return str(value).split(".", 1)[0]


def validate_strategy(rows, source_material, wall_materials, existing_labels=None):
    existing_labels = existing_labels or {}
    failures = []
    expected_walls = {row["wall_label"] for row in TARGETS}
    got_walls = {row["wall_label"] for row in rows}
    if got_walls != expected_walls:
        failures.append("targets must be exactly the two S3 side walls")
    if FAR_WALL_LABEL in got_walls:
        failures.append("far wall must remain untouched")
    if not source_material:
        failures.append("plinth material is absent")
    labels = [row["liner_label"] for row in rows]
    if len(labels) != len(set(labels)):
        failures.append("duplicate liner labels")
    collisions = [label for label in labels if int(existing_labels.get(label, 0)) != 0]
    if collisions:
        failures.append("liner labels already exist: " + ", ".join(sorted(collisions)))
    for row in rows:
        if row.get("strategy") != "inner_face_liner":
            failures.append(row["wall_label"] + " is not an inner-face liner")
        if float(row.get("liner_thickness_cm", 0.0)) <= 0.0 or float(row["liner_thickness_cm"]) > 2.0:
            failures.append(row["wall_label"] + " liner thickness is not 0..2 cm")
        if float(row.get("interior_sign", 0.0)) not in (-1.0, 1.0):
            failures.append(row["wall_label"] + " has invalid interior sign")
        if row.get("mutates_wall_slots"):
            failures.append(row["wall_label"] + " would mutate wall slots")
        materials = wall_materials.get(row["wall_label"], [])
        if not materials:
            failures.append(row["wall_label"] + " has no readable current material")
        elif any(material != EXPECTED_STEEL for material in materials):
            failures.append(row["wall_label"] + " is no longer the declared black-steel baseline")
    if failures:
        raise PlanError("; ".join(failures))
    return rows


def package_census():
    def names(packages):
        return sorted(str(package.get_path_name()).split(".", 1)[0] for package in packages)
    return {
        "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
        "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    }


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


def static_mesh_components(actor):
    return list(actor.get_components_by_class(unreal.StaticMeshComponent))


def material_paths(actor):
    rows = []
    for component in static_mesh_components(actor):
        for material in component.get_materials():
            path = normalize_asset_path(material)
            if path:
                rows.append(path)
    return rows


def vector(value):
    return [float(value.x), float(value.y), float(value.z)]


def transform_plain(value):
    rotation = value.rotation.rotator()
    return {
        "location": vector(value.translation),
        "rotation": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
        "scale": vector(value.scale3d),
    }


def point_distance(left, right):
    return math.sqrt((left.x - right.x) ** 2 + (left.y - right.y) ** 2 + (left.z - right.z) ** 2)


def right_axis(transform):
    origin = transform.translation
    point = unreal.MathLibrary.transform_location(transform, unreal.Vector(0.0, 1.0, 0.0))
    delta = unreal.Vector(point.x - origin.x, point.y - origin.y, point.z - origin.z)
    length = math.sqrt(delta.x * delta.x + delta.y * delta.y + delta.z * delta.z)
    if length <= 1e-6:
        raise PlanError("wall transform has degenerate local Y axis")
    return unreal.Vector(delta.x / length, delta.y / length, delta.z / length)


def wall_snapshot(actor):
    components = static_mesh_components(actor)
    if len(components) != 1:
        raise PlanError("%s expected one StaticMeshComponent, found %d" %
                        (actor.get_actor_label(), len(components)))
    component = components[0]
    mesh = component.get_editor_property("static_mesh")
    if mesh is None:
        raise PlanError(actor.get_actor_label() + " has no static mesh")
    return {
        "label": actor.get_actor_label(),
        "object_path": actor.get_path_name(),
        "parent_label": actor.get_attach_parent_actor().get_actor_label() if actor.get_attach_parent_actor() else None,
        "transform": transform_plain(actor.get_actor_transform()),
        "mesh_path": normalize_asset_path(mesh),
        "materials": material_paths(actor),
    }


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
    pedestal = one_actor(index, SOURCE_LABEL)
    source_materials = sorted(set(material_paths(pedestal)))
    if len(source_materials) != 1:
        raise PlanError("Clam_Pedastal must expose exactly one unique material, found " +
                        json.dumps(source_materials))
    source_material = source_materials[0]
    material = unreal.load_asset(source_material)
    cube = unreal.load_asset(CUBE)
    if material is None or not isinstance(cube, unreal.StaticMesh):
        raise PlanError("plinth material or Engine Cube failed to load")
    rows = []
    runtime = []
    wall_materials = {}
    for spec in TARGETS:
        wall = one_actor(index, spec["wall_label"])
        before = wall_snapshot(wall)
        wall_materials[spec["wall_label"]] = before["materials"]
        transform = wall.get_actor_transform()
        axis = right_axis(transform)
        offset = spec["interior_sign"] * (WALL_THICKNESS_CM + LINER_THICKNESS_CM) * 0.5
        location = unreal.Vector(transform.translation.x + axis.x * offset,
                                 transform.translation.y + axis.y * offset,
                                 transform.translation.z + axis.z * offset)
        scale = unreal.Vector(transform.scale3d.x, LINER_THICKNESS_CM / 100.0, transform.scale3d.z)
        liner_transform = unreal.Transform(location=location, rotation=transform.rotation.rotator(), scale=scale)
        row = {
            "wall_label": spec["wall_label"], "liner_label": spec["liner_label"],
            "interior_sign": spec["interior_sign"], "strategy": "inner_face_liner",
            "liner_thickness_cm": LINER_THICKNESS_CM, "mutates_wall_slots": False,
            "wall_before": before, "liner_world_transform": transform_plain(liner_transform),
            "source_material": source_material,
        }
        rows.append(row)
        runtime.append({"row": row, "wall": wall, "transform": liner_transform})
    existing = {spec["liner_label"]: len(index.get(spec["liner_label"], [])) for spec in TARGETS}
    validate_strategy(rows, source_material, wall_materials, existing)
    return {
        "source_actor": SOURCE_LABEL,
        "source_material": source_material,
        "disk_candidate_matches_live": source_material == DISK_PLINTH_MI,
        "wall_baseline": EXPECTED_STEEL,
        "rows": rows,
        "far_wall_touched": False,
        "wall_slots_mutated": False,
    }, runtime, material, cube


def package_filename(package_name):
    return os.path.join(project_file("Content"), *package_name[len("/Game/"):].split("/")) + ".umap"


def backup_level(prefix):
    source = package_filename(EXPECTED_WORLD)
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
    with open(record_path(), "x" if exclusive else "w", encoding="utf-8") as handle:
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


def apply_plan(run, report, runtime, material, cube):
    backup, copied = backup_level("PreS3WallsMarble-")
    record = {"run": run, "world": EXPECTED_WORLD, "backup": backup, "backup_file": copied,
              "tag": TAG, "plan": report, "spawned": [], "applied": False}
    write_record(record, exclusive=True)
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for item in runtime:
        row = item["row"]
        transform = item["transform"]
        wall = item["wall"]
        actor = subsystem.spawn_actor_from_class(unreal.StaticMeshActor, transform.translation,
                                                 transform.rotation.rotator())
        if actor is None:
            raise PlanError("SPAWN_FAILED|label=" + row["liner_label"])
        actor.modify(); actor.set_actor_label(row["liner_label"])
        actor.modify(); actor.set_folder_path(FOLDER)
        actor.modify(); actor.set_editor_property("tags", [unreal.Name(TAG), unreal.Name("S3.Marble.InnerFace")])
        component = actor.get_editor_property("static_mesh_component")
        component.modify(); component.set_mobility(unreal.ComponentMobility.MOVABLE)
        component.modify(); component.set_editor_property("static_mesh", cube)
        component.modify(); component.set_material(0, material)
        actor.modify(); actor.set_actor_scale3d(transform.scale3d)
        actor.modify(); actor.attach_to_actor(wall, unreal.Name(""), unreal.AttachmentRule.KEEP_WORLD,
                                              unreal.AttachmentRule.KEEP_WORLD,
                                              unreal.AttachmentRule.KEEP_WORLD, False)
        if actor.get_attach_parent_actor() is not wall:
            raise PlanError("PARENT_READBACK_MISMATCH|label=" + row["liner_label"])
        if point_distance(actor.get_actor_transform().translation, transform.translation) > 0.5:
            raise PlanError("TRANSFORM_READBACK_MISMATCH|label=" + row["liner_label"])
        if normalize_asset_path(component.get_material(0)) != report["source_material"]:
            raise PlanError("MATERIAL_READBACK_MISMATCH|label=" + row["liner_label"])
        if material_paths(wall) != row["wall_before"]["materials"]:
            raise PlanError("WALL_SLOT_CHANGED|label=" + row["wall_label"])
        record["spawned"].append({"label": row["liner_label"], "object_path": actor.get_path_name(),
                                  "wall_label": row["wall_label"], "material": report["source_material"]})
        write_record(record)
    if len(record["spawned"]) != 2:
        raise PlanError("SPAWN_COUNT_MISMATCH")
    census = save_level_clean()
    record["applied"] = True
    write_record(record)
    unreal.log("S3_WALLS_MARBLE_DONE|run=%s|applied|liners=2|backup=%s|material=%s|census=%s" %
               (run, backup, report["source_material"],
                json.dumps(census, separators=(",", ":"), sort_keys=True)))


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
    if len(targets) != 2:
        raise PlanError("REVERT_TARGET_COUNT|count=%d" % len(targets))
    backup, _ = backup_level("PreS3WallsMarbleRevert-")
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
    unreal.log("S3_WALLS_MARBLE_DONE|run=%s|reverted|liners=2|backup=%s|record=%s|census=%s" %
               (run, backup, os.path.basename(archived),
                json.dumps(census, separators=(",", ":"), sort_keys=True)))


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    apply = bool(globals().get("S3_WALLS_MARBLE_APPLY"))
    revert = bool(globals().get("S3_WALLS_MARBLE_REVERT"))
    try:
        if apply and revert:
            raise PlanError("APPLY_AND_REVERT_BOTH_SET")
        assert_context(apply, revert)
        if revert:
            revert_plan(run)
            return
        report, runtime, material, cube = live_plan()
        unreal.log("S3_WALLS_MARBLE_PLAN|run=%s|%s" %
                   (run, json.dumps(report, separators=(",", ":"), sort_keys=True)))
        if not apply:
            after = package_census()
            if after["maps"] or after["content"]:
                raise PlanError("DRY_RUN_DIRTIED_PACKAGES|census=" + json.dumps(after, sort_keys=True))
            unreal.log("S3_WALLS_MARBLE_DRY_RUN_OK|run=%s|mutated=0|liners=2|inner_faces_only=1" % run)
            return
        apply_plan(run, report, runtime, material, cube)
    except PlanError as exc:
        unreal.log_error("S3_WALLS_MARBLE_%s_STOPPED|run=%s|reason=%s|census=%s" %
                         ("REVERT" if revert else ("APPLY" if apply else "DRY_RUN"), run, str(exc),
                          json.dumps(package_census(), separators=(",", ":"), sort_keys=True)))
    except Exception:
        unreal.log_error("S3_WALLS_MARBLE_ERROR|run=%s|traceback=%s|census=%s" %
                         (run, traceback.format_exc().replace("\n", "\\n"),
                          json.dumps(package_census(), separators=(",", ":"), sort_keys=True)))


if unreal is not None:
    main()
