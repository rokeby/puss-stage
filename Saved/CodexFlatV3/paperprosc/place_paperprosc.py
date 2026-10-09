"""Guarded paper-proscenium placement tool; offline-authored and never run in Unreal by its author.

Evidence carried into the plan:
- [declaration-proven] the persistent Show level is the world authority (README.md:18-24).
- [declaration-proven] P01 stage coordinates are UE world centimetres, curtain line x=0 and lip x=-150
  (Saved/CodexStructure/make_stage_front_colliders.py:124-126).
- [measured by the predecessor tool] temporary stage-front flats use the same world frame at yaw 0/scale 1
  (Saved/CodexConductor/stage_front_wings.py:4-7).
- [measured offline] DEFAULT_TRANSFORMS centre the validated mesh bounds in StageFront_Colliders_v2 boxes;
  the harness asserts the rounded collider agreement to 0.5 cm.

Modes and confirms: DRY/APPLY/VERIFY/REVERT with '<MODE> PAPERPROSC'. APPLY/REVERT back up the .umap and
write a durable record before actor mutation. APPLY saves only the map and deliberately reports VERIFY pending;
a later clean VERIFY call performs the saved transform/mesh/material read-back.
"""
import copy
import datetime
import hashlib
import json
import math
import os
import shutil
import traceback

try:
    import unreal
except ModuleNotFoundError:  # offline harness
    unreal = None


MARK = "PAPERPROSC"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MAP_RELATIVE_FILE = "InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
TAG = "PussStage.PaperProscenium"
FOLDER = "StageFront/PaperProscenium"
PIECES = ("side_l", "side_r", "valance")
LABELS = {
    "side_l": "Paper Proscenium Side L",
    "side_r": "Paper Proscenium Side R",
    "valance": "Paper Proscenium Valance",
}
OWNERS = {"side_l": "PRO_side_L", "side_r": "PRO_side_R", "valance": "PRO_valance_C"}
MESH_DEFAULTS = {
    "side_l": "/Game/Scenes/Wings/FlatV3/Realism/T5J/SM_FlatV3_PRO_side_L_t5j",
    "side_r": "/Game/Scenes/Wings/FlatV3/Realism/T5J/SM_FlatV3_PRO_side_R_t5j",
    "valance": "/Game/Scenes/Wings/FlatV3/Realism/T5J/SM_FlatV3_PRO_valance_C_t5j",
}
MI_ROOT = "/Game/Scenes/Wings/FlatV3/Realism/Materials/Instances"
TIMBER = "/Game/Scenes/Wings/PaintedSurface/M_Wing_CanvasEdge_Master"
EDGE = "/Game/Scenes/Wings/PaintedSurface/M_Wing_CanvasEdge_Master_v3"
MATERIAL_DEFAULTS = {
    key: [MI_ROOT + "/MI_FlatV3_%s_Front" % owner,
          MI_ROOT + "/MI_FlatV3_%s_Flap" % owner, TIMBER, EDGE]
    for key, owner in OWNERS.items()
}
DEFAULT_TRANSFORMS = {
    "side_l": {"location_cm": [-58.975, -874.936, 0.0], "rotation_rpy_deg": [0.0, 0.0, 0.0],
               "scale": [1.0, 1.0, 1.0]},
    "side_r": {"location_cm": [-59.375, 874.948, 0.0], "rotation_rpy_deg": [0.0, 0.0, 0.0],
               "scale": [1.0, 1.0, 1.0]},
    "valance": {"location_cm": [-44.375, 0.0, 930.0], "rotation_rpy_deg": [0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0]},
}
VALIDATED_LOCAL_BOUNDS_CM = {
    "side_l": {"min": [-16.049951314926147, -356.1279296875, 0.0],
               "max": [-3.999945521354675, -0.00000215055298, 1080.0000190734863]},
    "side_r": {"min": [-16.050036251544952, -0.00000244381031, 0.0],
               "max": [-3.20001095533371, 323.1040954589844, 1080.0000190734863]},
    "valance": {"min": [-16.049841046333313, -1244.0842628479004, 0.0],
                "max": [-3.1999338418245316, 1244.0842628479004, 400.0]},
}
COLLIDER_BOXES_CM = {
    "side_l": {"min": [-75.0, -1231.0, 0.0], "max": [-63.0, -875.0, 1080.0]},
    "side_r": {"min": [-75.0, 875.0, 0.0], "max": [-63.0, 1198.0, 1080.0]},
    "valance": {"min": [-60.0, -1244.0, 930.0], "max": [-48.0, 1244.0, 1330.0]},
}
PROTECTED_LEVEL_BASENAMES = {"l_animals", "l_kk_children", "japanese_alley", "l_kk_void"}


class PlanError(Exception):
    pass


def require(condition, reason):
    if not condition:
        raise PlanError(reason)


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _finite_vector(value, name, positive=False):
    require(isinstance(value, list) and len(value) == 3, "%s_MUST_BE_VEC3" % name)
    out = [float(x) for x in value]
    require(all(math.isfinite(x) for x in out), "%s_NONFINITE" % name)
    if positive:
        require(all(0.001 <= x <= 100.0 for x in out), "%s_SCALE_RANGE" % name)
    return out


def validate_args(args):
    require(isinstance(args, dict), "ARGS_NOT_OBJECT")
    mode = str(args.get("mode") or "").upper()
    require(mode in ("DRY", "APPLY", "VERIFY", "REVERT"), "MODE_INVALID|%r" % mode)
    want = "%s PAPERPROSC" % mode
    require(args.get("confirm") == want, "CONFIRM_MISMATCH|got=%r|want=%r" % (args.get("confirm"), want))
    meshes = copy.deepcopy(MESH_DEFAULTS)
    meshes.update(args.get("meshes") or {})
    transforms = copy.deepcopy(DEFAULT_TRANSFORMS)
    transforms.update(args.get("transforms") or {})
    require(set(meshes) == set(PIECES), "MESH_KEYS|%s" % sorted(meshes))
    require(set(transforms) == set(PIECES), "TRANSFORM_KEYS|%s" % sorted(transforms))
    rows = []
    for key in PIECES:
        mesh = str(meshes[key])
        require(mesh.startswith("/Game/Scenes/Wings/FlatV3/Realism/") and mesh.rsplit("/", 1)[-1].startswith("SM_FlatV3_PRO_"),
                "MESH_OUT_OF_SCOPE|%s|%s" % (key, mesh))
        transform = transforms[key]
        require(isinstance(transform, dict), "TRANSFORM_NOT_OBJECT|" + key)
        loc = _finite_vector(transform.get("location_cm"), key + "_LOCATION")
        rot = _finite_vector(transform.get("rotation_rpy_deg"), key + "_ROTATION")
        scale = _finite_vector(transform.get("scale"), key + "_SCALE", positive=True)
        rows.append({"key": key, "label": LABELS[key], "owner": OWNERS[key], "mesh": mesh,
                     "materials": list(MATERIAL_DEFAULTS[key]), "folder": FOLDER,
                     "tags": [TAG, TAG + "." + key],
                     "transform": {"location_cm": loc, "rotation_rpy_deg": rot, "scale": scale}})
    plan = {"mode": mode, "world": WORLD, "folder": FOLDER, "tag": TAG, "rows": rows,
            "stage_to_world": {"location_cm": [0.0, 0.0, 0.0], "rotation_rpy_deg": [0.0, 0.0, 0.0],
                               "scale": [1.0, 1.0, 1.0]},
            "stage_frame_evidence": ["Saved/CodexStructure/make_stage_front_colliders.py:124-126",
                                     "Saved/CodexConductor/stage_front_wings.py:4-7"],
            "transform_authority": "args; defaults derived from collider boxes plus validated mesh pivots"}
    plan["hash"] = canonical_hash({k: v for k, v in plan.items() if k not in ("mode", "hash")})
    plan["hash8"] = plan["hash"][:8]
    return plan


def _rotation_matrix(rpy):
    roll, pitch, yaw = [math.radians(v) for v in rpy]
    cr, sr, cp, sp, cy, sy = math.cos(roll), math.sin(roll), math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw)
    return ((cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
            (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
            (-sp, cp * sr, cp * cr))


def transformed_bounds(bounds, transform):
    matrix = _rotation_matrix(transform["rotation_rpy_deg"])
    loc, scale = transform["location_cm"], transform["scale"]
    points = []
    for x in (bounds["min"][0], bounds["max"][0]):
        for y in (bounds["min"][1], bounds["max"][1]):
            for z in (bounds["min"][2], bounds["max"][2]):
                source = (x * scale[0], y * scale[1], z * scale[2])
                points.append([loc[i] + sum(matrix[i][j] * source[j] for j in range(3)) for i in range(3)])
    return {"min": [min(p[i] for p in points) for i in range(3)],
            "max": [max(p[i] for p in points) for i in range(3)]}


def collider_default_errors(plan, tolerance_cm=0.5):
    errors = []
    for row in plan["rows"]:
        got, want = transformed_bounds(VALIDATED_LOCAL_BOUNDS_CM[row["key"]], row["transform"]), COLLIDER_BOXES_CM[row["key"]]
        for side in ("min", "max"):
            for axis in range(3):
                if abs(got[side][axis] - want[side][axis]) > tolerance_cm:
                    errors.append("%s_%s_%d|got=%.3f|want=%.3f" %
                                  (row["key"], side, axis, got[side][axis], want[side][axis]))
    return errors


def _protected_dirty(census):
    return sorted(name for group in ("content", "maps") for name in census.get(group, [])
                  if str(name).replace("\\", "/").rsplit("/", 1)[-1].lower() in PROTECTED_LEVEL_BASENAMES)


def context_errors(mode, state):
    errors = []
    if state.get("world") != WORLD:
        errors.append("WRONG_WORLD|%s" % state.get("world"))
    if state.get("pie"):
        errors.append("PIE_OR_SIE_ACTIVE")
    if state.get("sequencer_open"):
        errors.append("SEQUENCER_IS_OPEN")
    census = state.get("census") or {"content": [], "maps": []}
    if census.get("content") or census.get("maps"):
        errors.append("DIRTY_AT_START|%s" % json.dumps(census, sort_keys=True))
    protected = _protected_dirty(census)
    if protected:
        errors.append("KLARA_LEVEL_DIRTY|%s" % protected)
    counts = state.get("label_counts") or {}
    tag_count = int(state.get("tag_count") or 0)
    if mode == "APPLY":
        clashes = {label: counts.get(label, 0) for label in LABELS.values() if counts.get(label, 0)}
        if clashes or tag_count:
            errors.append("OWNED_ACTORS_ALREADY_EXIST|labels=%s|tagged=%d" % (clashes, tag_count))
        if state.get("record_exists"):
            errors.append("APPLY_RECORD_ALREADY_EXISTS")
    elif mode in ("VERIFY", "REVERT"):
        missing = {label: counts.get(label, 0) for label in LABELS.values() if counts.get(label, 0) != 1}
        if missing or tag_count != 3:
            errors.append("OWNED_ACTORS_NOT_EXACT|labels=%s|tagged=%d" % (missing, tag_count))
        if not state.get("record_exists"):
            errors.append("APPLY_RECORD_MISSING")
    return errors


def _here():
    if unreal is not None:
        saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
        return os.path.join(saved, "CodexFlatV3", "paperprosc")
    return os.path.dirname(os.path.abspath(__file__))


def _record_path():
    return os.path.join(_here(), "paperprosc_record.json")


def _read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if exclusive:
        with open(path, "x", encoding="utf-8") as handle:
            json.dump(value, handle, indent=1, sort_keys=True)
            handle.flush(); os.fsync(handle.fileno())
    else:
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=1, sort_keys=True)
            handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
    require(_read_json(path) == json.loads(json.dumps(value, sort_keys=True)), "JSON_READBACK|" + path)


def _asset_path(value):
    if value is None:
        return None
    return str(value.get_path_name()).split(".", 1)[0]


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    names = lambda rows: sorted(str(row.get_name()).split(".", 1)[0] for row in rows)
    return {"content": names(lib.get_dirty_content_packages()), "maps": names(lib.get_dirty_map_packages())}


def _actors():
    return list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())


def _tags(actor):
    return sorted(str(value) for value in actor.get_editor_property("tags"))


def _state(actors=None):
    actors = _actors() if actors is None else actors
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    return {"world": world.get_outermost().get_name() if world else None,
            "pie": editor.get_game_world() is not None,
            "sequencer_open": unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None,
            "census": _census(),
            "label_counts": {label: sum(str(a.get_actor_label()) == label for a in actors) for label in LABELS.values()},
            "tag_count": sum(TAG in _tags(a) for a in actors),
            "record_exists": os.path.isfile(_record_path())}


def _require_context(mode, actors=None):
    state = _state(actors)
    errors = context_errors(mode, state)
    require(not errors, " ; ".join(errors))
    return state


def _load_meshes(plan):
    loaded = {}
    for row in plan["rows"]:
        mesh = unreal.load_asset(row["mesh"])
        require(mesh is not None and isinstance(mesh, unreal.StaticMesh), "MESH_MISSING_OR_WRONG_CLASS|" + row["mesh"])
        materials = [_asset_path(mesh.get_material(index)) for index in range(len(mesh.get_editor_property("static_materials")))]
        require(materials == row["materials"], "MESH_MATERIALS|%s|got=%s|want=%s" %
                (row["key"], materials, row["materials"]))
        loaded[row["key"]] = mesh
    return loaded


def _actor_row(actor):
    comp = actor.get_editor_property("static_mesh_component")
    loc, rot, scale = actor.get_actor_location(), actor.get_actor_rotation(), actor.get_actor_scale3d()
    return {"label": str(actor.get_actor_label()), "object_path": str(actor.get_path_name()), "tags": _tags(actor),
            "folder": str(actor.get_folder_path()),
            "transform": {"location_cm": [float(loc.x), float(loc.y), float(loc.z)],
                          "rotation_rpy_deg": [float(rot.roll), float(rot.pitch), float(rot.yaw)],
                          "scale": [float(scale.x), float(scale.y), float(scale.z)]},
            "mesh": _asset_path(comp.get_editor_property("static_mesh")),
            "materials": [_asset_path(comp.get_material(i)) for i in range(comp.get_num_materials())],
            "mobility": str(comp.get_editor_property("mobility")),
            "collision_profile": str(comp.get_collision_profile_name()),
            "collision_enabled": str(comp.get_collision_enabled()),
            "cast_shadow": bool(comp.get_editor_property("cast_shadow"))}


def _near(actual, expected, tolerance):
    return len(actual) == len(expected) and all(abs(float(a) - float(b)) <= tolerance for a, b in zip(actual, expected))


def _validate_readback(plan, actors):
    by_label = {}
    for actor in actors:
        by_label.setdefault(str(actor.get_actor_label()), []).append(actor)
    output, errors = {}, []
    for row in plan["rows"]:
        hits = by_label.get(row["label"], [])
        if len(hits) != 1:
            errors.append("LABEL_COUNT|%s|%d" % (row["label"], len(hits)))
            continue
        got = _actor_row(hits[0]); output[row["key"]] = got
        if got["tags"] != sorted(row["tags"]): errors.append("TAGS|" + row["key"])
        if got["folder"] != FOLDER: errors.append("FOLDER|%s|%s" % (row["key"], got["folder"]))
        if got["mesh"] != row["mesh"]: errors.append("MESH|%s|%s" % (row["key"], got["mesh"]))
        if got["materials"] != row["materials"]: errors.append("MATERIALS|%s|%s" % (row["key"], got["materials"]))
        if not _near(got["transform"]["location_cm"], row["transform"]["location_cm"], 0.01): errors.append("LOCATION|" + row["key"])
        if not _near(got["transform"]["rotation_rpy_deg"], row["transform"]["rotation_rpy_deg"], 0.001): errors.append("ROTATION|" + row["key"])
        if not _near(got["transform"]["scale"], row["transform"]["scale"], 0.000001): errors.append("SCALE|" + row["key"])
        if not got["mobility"].upper().endswith("STATIC"): errors.append("MOBILITY|%s|%s" % (row["key"], got["mobility"]))
        if got["collision_profile"].lower() != "nocollision": errors.append("COLLISION_PROFILE|%s|%s" % (row["key"], got["collision_profile"]))
        if not got["collision_enabled"].upper().endswith("NO_COLLISION"): errors.append("COLLISION_ENABLED|%s|%s" % (row["key"], got["collision_enabled"]))
        if not got["cast_shadow"]: errors.append("CAST_SHADOW|" + row["key"])
    require(not errors, "READBACK|" + " ; ".join(errors))
    return output


def _backup(run):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    source = os.path.join(project, "Content", *MAP_RELATIVE_FILE.split("/"))
    require(os.path.isfile(source), "BACKUP_SOURCE_MISSING|" + source)
    folder = os.path.join(project, "Backups", "PrePaperProsc-" + run)
    require(not os.path.exists(folder), "BACKUP_EXISTS|" + folder)
    destination = os.path.join(folder, "Content", *MAP_RELATIVE_FILE.split("/"))
    os.makedirs(os.path.dirname(destination))
    shutil.copy2(source, destination)
    require(os.path.isfile(destination) and os.path.getsize(destination) == os.path.getsize(source), "BACKUP_READBACK")
    return folder, os.path.relpath(destination, folder).replace("\\", "/")


def _pre_save_exact_map():
    census = _census()
    protected = _protected_dirty(census)
    require(not protected, "KLARA_LEVEL_DIRTY_BEFORE_SAVE|%s|NOTHING_SAVED" % protected)
    require(census == {"content": [], "maps": [WORLD]}, "DIRTY_SET_NOT_EXACT|%s|NOTHING_SAVED" %
            json.dumps(census, sort_keys=True))


def _save_map():
    _pre_save_exact_map()
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    require(unreal.EditorLoadingAndSavingUtils.save_map(world, WORLD), "MAP_SAVE_FAILED")
    require(_census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % json.dumps(_census(), sort_keys=True))


def _spawn(plan, meshes):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    made = []
    for row in plan["rows"]:
        t = row["transform"]
        loc = unreal.Vector(*t["location_cm"])
        roll, pitch, yaw = t["rotation_rpy_deg"]
        actor = subsystem.spawn_actor_from_class(unreal.StaticMeshActor, loc,
                                                 unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw))
        require(actor is not None, "SPAWN_FAILED|" + row["key"])
        actor.modify(); actor.set_actor_label(row["label"])
        actor.modify(); actor.set_folder_path(unreal.Name(FOLDER))
        actor.modify(); actor.set_editor_property("tags", [unreal.Name(value) for value in row["tags"]])
        actor.modify(); actor.set_actor_scale3d(unreal.Vector(*t["scale"]))
        comp = actor.get_editor_property("static_mesh_component")
        comp.modify(); comp.set_mobility(unreal.ComponentMobility.STATIC)
        comp.modify(); comp.set_static_mesh(meshes[row["key"]])
        comp.modify(); comp.set_collision_profile_name("NoCollision")
        comp.modify(); comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        comp.modify(); comp.set_cast_shadow(True)
        made.append(actor)
    return made


def _apply(run, plan, meshes):
    backup, copied = _backup(run)
    record = {"schema_version": 1, "mode": "APPLY", "run": run, "world": WORLD, "tag": TAG,
              "plan_hash": plan["hash"], "plan": plan, "backup": backup, "backup_file": copied,
              "applied": False, "verified": False, "actors": {}}
    _write_json(_record_path(), record, exclusive=True)
    _spawn(plan, meshes)
    readback = _validate_readback(plan, _actors())
    record["actors"] = readback
    _write_json(_record_path(), record)
    _save_map()
    record.update({"applied": True, "saved_census": _census()})
    _write_json(_record_path(), record)
    unreal.log("PAPERPROSC_APPLY_SAVED|run=%s|plan=%s|actors=3|backup=%s|verify=pending" %
               (run, plan["hash8"], backup))


def _verify(run, plan):
    record = _read_json(_record_path())
    require(record.get("applied") and record.get("world") == WORLD and record.get("tag") == TAG,
            "APPLY_RECORD_INVALID")
    require(record.get("plan_hash") == plan["hash"], "PLAN_DRIFT|record=%s|args=%s" %
            (str(record.get("plan_hash"))[:8], plan["hash8"]))
    readback = _validate_readback(plan, _actors())
    require(_census() == {"content": [], "maps": []}, "VERIFY_DIRTIED_PACKAGES|%s" % _census())
    record.update({"verified": True, "verify_run": run, "verified_readback": readback})
    _write_json(_record_path(), record)
    unreal.log("PAPERPROSC_VERIFY_OK|run=%s|applied_run=%s|plan=%s|actors=3|materials=12|dirty=0" %
               (run, record["run"], plan["hash8"]))


def _revert(run, plan):
    record = _read_json(_record_path())
    require(record.get("applied") and record.get("world") == WORLD and record.get("tag") == TAG,
            "APPLY_RECORD_INVALID")
    require(record.get("plan_hash") == plan["hash"], "PLAN_DRIFT")
    current = _validate_readback(plan, _actors())
    require(all(current[key]["object_path"] == record.get("actors", {}).get(key, {}).get("object_path") for key in PIECES),
            "OWNERSHIP_OBJECT_PATH_DRIFT")
    backup, copied = _backup(run)
    revert_path = os.path.join(_here(), "paperprosc_revert_%s.json" % run)
    revert_record = {"schema_version": 1, "mode": "REVERT", "run": run, "apply_run": record["run"],
                     "plan_hash": plan["hash"], "backup": backup, "backup_file": copied, "reverted": False}
    _write_json(revert_path, revert_record, exclusive=True)
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    targets = [actor for actor in _actors() if TAG in _tags(actor)]
    require(len(targets) == 3, "REVERT_TAG_COUNT|%d" % len(targets))
    for actor in targets:
        require(str(actor.get_actor_label()) in LABELS.values(), "REVERT_FOREIGN_TAGGED_ACTOR|" + str(actor.get_actor_label()))
        actor.modify()
        require(subsystem.destroy_actor(actor), "DESTROY_FAILED|" + str(actor.get_actor_label()))
    survivors = [actor for actor in _actors() if TAG in _tags(actor) or str(actor.get_actor_label()) in LABELS.values()]
    require(not survivors, "REVERT_SURVIVORS|%s" % [str(actor.get_actor_label()) for actor in survivors])
    _save_map()
    archived = _record_path() + ".reverted-" + run
    os.rename(_record_path(), archived)
    revert_record.update({"reverted": True, "archived_apply_record": archived, "saved_census": _census()})
    _write_json(revert_path, revert_record)
    unreal.log("PAPERPROSC_REVERT_OK|run=%s|apply_run=%s|plan=%s|actors=0|backup=%s|record=%s" %
               (run, record["run"], plan["hash8"], backup, revert_path))


def main():
    run = datetime.datetime.now().strftime("PAPERPROSC-%Y%m%d-%H%M%S")
    mode = "UNKNOWN"
    try:
        args = _read_json(os.path.join(_here(), "paperprosc_args.json"))
        plan = validate_args(args); mode = plan["mode"]
        actors = _actors()
        _require_context(mode, actors)
        meshes = _load_meshes(plan)
        if mode == "DRY":
            report = {"run": run, "mode": mode, "plan": plan, "existing_tagged": _state(actors)["tag_count"],
                      "collider_default_errors": collider_default_errors(plan), "mutated": False}
            _write_json(os.path.join(_here(), "paperprosc_report_DRY_%s.json" % run), report)
            require(_census() == {"content": [], "maps": []}, "DRY_DIRTIED_PACKAGES|%s" % _census())
            unreal.log("PAPERPROSC_DRY_OK|run=%s|plan=%s|actors=3|mutated=0" % (run, plan["hash8"]))
        elif mode == "APPLY":
            _apply(run, plan, meshes)
        elif mode == "VERIFY":
            _verify(run, plan)
        else:
            _revert(run, plan)
    except PlanError as exc:
        unreal.log_error("PAPERPROSC_%s_STOPPED|run=%s|reason=%s|census=%s" %
                         (mode, run, str(exc), json.dumps(_census(), separators=(",", ":"), sort_keys=True)))
    except Exception:
        unreal.log_error("PAPERPROSC_%s_ERROR|run=%s|traceback=%s|census=%s" %
                         (mode, run, traceback.format_exc().replace("\n", "\\n"),
                          json.dumps(_census(), separators=(",", ":"), sort_keys=True)))


if unreal is not None:
    main()
