"""Job 119: replace the four persistent S2 floor slabs with P01-floor duplicates.

Offline-authored only.  The conductor runs this later through ExecuteProjectPythonFile.
DRY plans and audits every LevelSequence.  APPLY duplicates the P01 actor, fits one
duplicate to each S2 slab, attaches it to the original actor, then moves only the old
StaticMeshComponent below stage.  This preserves actor/ancestor transform and AActor::
bHidden tracks without rebinding.  Component-bound transform/visibility is a hard stop.
REVERT restores recorded component transforms and destroys only record-owned duplicates.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import shutil

try:
    import unreal
except ImportError:  # offline harness
    unreal = None

WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP_REL = ("Content", "InfinityStage", "Dev", "Maps", "L_InfinityStage_V1VerticalSlice.umap")
SOURCE_LABEL = "Passage 01 - Opening Floor"
TARGET_LABELS = ("S2 Hangar Floor 1", "S2 Hangar Floor 2", "S2 Hangar Floor 3", "S2 Hangar Apron")
TAG = "Codex.J119.S2P01FloorReplacement"
MARK = "J119_S2_P01_FLOOR_REPLACE"
KLARA_PACKAGES = ("/Game/Scenes/L_Animals", "/Game/Scenes/L_KK_children",
                  "/Game/Scenes/Japanese_Alley", "/Game/Scenes/L_KK_Void")
MODES = ("DRY", "APPLY", "REVERT")


class Refused(RuntimeError):
    pass


def confirm_ok(mode, value):
    return mode == "DRY" or value == "%s J119S2P01FLOOR" % mode


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def v3(value):
    if hasattr(value, "to_tuple"):
        value = value.to_tuple()
    return [float(value[0]), float(value[1]), float(value[2])]


def fit_transform(source, target):
    """Fit source local mesh bounds to target local mesh bounds under target rotation.

    source/target contain actor location/scale plus unrotated local bbox min/max.  The
    caller requires identity component-relative transforms.  This preserves the exact
    target oriented box even when the two mesh assets have different local bounds.
    """
    ss = [source["bbox_max"][i] - source["bbox_min"][i] for i in range(3)]
    ts = [target["bbox_max"][i] - target["bbox_min"][i] for i in range(3)]
    if min(abs(x) for x in ss + ts) < 1e-6:
        raise ValueError("degenerate mesh bounds")
    scale = [target["scale"][i] * ts[i] / ss[i] for i in range(3)]
    sc = [(source["bbox_min"][i] + source["bbox_max"][i]) * 0.5 for i in range(3)]
    tc = [(target["bbox_min"][i] + target["bbox_max"][i]) * 0.5 for i in range(3)]
    local_delta = [tc[i] * target["scale"][i] - sc[i] * scale[i] for i in range(3)]
    roll, pitch, yaw = [math.radians(x) for x in target["rotation"]]
    if abs(roll) > 1e-6 or abs(pitch) > 1e-6:
        raise ValueError("pitched/rolled target is unsupported")
    c, s = math.cos(yaw), math.sin(yaw)
    rotated = [c * local_delta[0] - s * local_delta[1],
               s * local_delta[0] + c * local_delta[1], local_delta[2]]
    return {"location": [target["location"][i] + rotated[i] for i in range(3)],
            "rotation": list(target["rotation"]), "scale": scale}


def sequence_binding_policy(rows):
    """Return hard blockers and the actor/ancestor tracks preserved by attachment."""
    blockers, inherited = [], []
    for row in rows:
        relevant = any(word in (row.get("track_class", "") + " " + row.get("property", "")).lower()
                       for word in ("transform", "visibility", "bhidden"))
        if not relevant:
            continue
        if row.get("object_kind") == "component":
            blockers.append(row)
        else:
            inherited.append(row)
    return blockers, inherited


def _path(obj):
    return obj.get_path_name() if obj is not None else None


def _prop(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return default


def _plain(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "to_tuple"):
        return list(value.to_tuple())
    return str(value)


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def _level(actor):
    return actor.get_outermost().get_name()


def _one_component(actor):
    rows = list(actor.get_components_by_class(unreal.StaticMeshComponent))
    if len(rows) != 1:
        raise Refused("STATIC_MESH_COMPONENT_COUNT|label=%s|count=%d" % (actor.get_actor_label(), len(rows)))
    return rows[0]


def _bbox(mesh):
    box = mesh.get_bounding_box()
    return v3(box.min), v3(box.max)


def _identity_component(component):
    loc = v3(_prop(component, "relative_location"))
    rot = _prop(component, "relative_rotation")
    scl = v3(_prop(component, "relative_scale3d"))
    r = [float(rot.roll), float(rot.pitch), float(rot.yaw)]
    return max(abs(x) for x in loc + r + [scl[i] - 1.0 for i in range(3)]) <= 1e-4


def _snapshot(actor):
    component = _one_component(actor)
    mesh = _prop(component, "static_mesh")
    if mesh is None:
        raise Refused("NO_STATIC_MESH|" + str(actor.get_actor_label()))
    if not _identity_component(component):
        raise Refused("NON_IDENTITY_COMPONENT_TRANSFORM|" + str(actor.get_actor_label()))
    bmin, bmax = _bbox(mesh)
    rot = actor.get_actor_rotation()
    origin, extent = unreal.SystemLibrary.get_actor_bounds(actor, False)
    return {
        "label": str(actor.get_actor_label()), "actor_path": _path(actor), "level": _level(actor),
        "actor_class": _path(actor.get_class()), "component_path": _path(component), "mesh": _path(mesh),
        "materials": [_path(component.get_material(i)) for i in range(int(component.get_num_materials()))],
        "location": v3(actor.get_actor_location()),
        "rotation": [float(rot.roll), float(rot.pitch), float(rot.yaw)], "scale": v3(actor.get_actor_scale3d()),
        "bbox_min": bmin, "bbox_max": bmax,
        "world_bounds": {"origin": v3(origin), "extent": v3(extent),
                         "min": [v3(origin)[i] - v3(extent)[i] for i in range(3)],
                         "max": [v3(origin)[i] + v3(extent)[i] for i in range(3)]},
        "component_relative_location": v3(_prop(component, "relative_location")),
        "component_settings": {
            name: _plain(_prop(component, name)) for name in
            ("mobility", "collision_profile_name", "collision_enabled", "cast_shadow", "visible", "hidden_in_game")
        },
        "parent_actor": _path(actor.get_attach_parent_actor()),
        "tags": sorted(str(x) for x in list(_prop(actor, "tags", ()) or ())),
    }


def _actors_by_label():
    rows = {}
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        rows.setdefault(str(actor.get_actor_label()), []).append(actor)
    return rows


def _one(rows, label):
    found = rows.get(label, [])
    if len(found) != 1:
        raise Refused("ACTOR_COUNT|label=%s|count=%d" % (label, len(found)))
    return found[0]


def _track_property(track):
    return "%s|%s" % (_plain(_prop(track, "property_name", "")), _plain(_prop(track, "property_path", "")))


def _sequence_audit(world, targets):
    target_objects = {}
    for actor in targets:
        target_objects[_path(actor)] = (str(actor.get_actor_label()), "actor")
        target_objects[_path(_one_component(actor))] = (str(actor.get_actor_label()), "component")
        parent = actor.get_attach_parent_actor()
        while parent is not None:
            target_objects.setdefault(_path(parent), (str(actor.get_actor_label()), "ancestor_actor"))
            parent = parent.get_attach_parent_actor()
    rows, unclear = [], []
    for asset_path in unreal.EditorAssetLibrary.list_assets("/Game", True, False):
        data = unreal.EditorAssetLibrary.find_asset_data(asset_path)
        class_name = str(_prop(_prop(data, "asset_class_path"), "asset_name", ""))
        if class_name != "LevelSequence":
            continue
        sequence = unreal.load_asset(asset_path)
        try:
            bindings = list(sequence.get_bindings())
        except Exception as exc:
            unclear.append({"sequence": asset_path, "error": repr(exc)})
            continue
        for binding in bindings:
            try:
                objects = list(sequence.locate_bound_objects(binding.get_id(), world))
            except Exception as exc:
                unclear.append({"sequence": asset_path, "binding": str(binding.get_name()), "error": repr(exc)})
                continue
            for obj in objects:
                hit = target_objects.get(_path(obj))
                if not hit:
                    continue
                for track in list(binding.get_tracks()):
                    rows.append({"sequence": asset_path, "binding": str(binding.get_name()),
                                 "bound_object": _path(obj), "target_label": hit[0], "object_kind": hit[1],
                                 "track_class": track.get_class().get_name(), "property": _track_property(track)})
    return rows, unclear


def _bounds_close(a, b, tolerance):
    return all(abs(a[part][i] - b[part][i]) <= tolerance for part in ("origin", "extent") for i in range(3))


def _write_json(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.flush(); os.fsync(handle.fileno())
    with open(path, encoding="utf-8") as handle:
        if digest(json.load(handle)) != digest(value):
            raise Refused("JSON_READBACK_MISMATCH|" + path)


def _backup(run, stem, record=None):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    source = os.path.join(project, *UMAP_REL)
    out = os.path.join(project, "Backups", "%s-%s" % (stem, run))
    os.makedirs(out)
    shutil.copy2(source, out)
    if record and os.path.exists(record):
        shutil.copy2(record, out)
    return out


def _require_context():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        raise Refused("PIE_OR_SIE_RUNNING")
    world = editor.get_editor_world()
    if world is None or world.get_outermost().get_name() != WORLD:
        raise Refused("WRONG_WORLD|%s" % (world.get_outermost().get_name() if world else None))
    return world


def _save_level_only():
    before = _census()
    allowed = ([WORLD], [WORLD.rsplit("/", 1)[-1]])
    if before["content"] or before["maps"] not in allowed:
        raise Refused("DIRTY_SCOPE_BEFORE_SAVE|%s|NOTHING_SAVED_DONT_SAVE_RESTART" % json.dumps(before))
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        raise Refused("LEVEL_SAVE_FAILED")
    after = _census()
    if after != {"content": [], "maps": []}:
        raise Refused("DIRTY_AFTER_SAVE|" + json.dumps(after))
    return before, after


def _owned_actors():
    return [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
            if TAG in [str(x) for x in list(_prop(a, "tags", ()) or ())]]


def _make_plan(args, world):
    labels = _actors_by_label()
    source_actor = _one(labels, SOURCE_LABEL)
    targets = [_one(labels, label) for label in TARGET_LABELS]
    for actor in [source_actor] + targets:
        if _level(actor) != WORLD:
            raise Refused("ACTOR_NOT_PERSISTENT|label=%s|level=%s" % (actor.get_actor_label(), _level(actor)))
    source = _snapshot(source_actor)
    target_rows = [_snapshot(actor) for actor in targets]
    sequence_rows, unclear = _sequence_audit(world, targets)
    blockers, inherited = sequence_binding_policy(sequence_rows)
    replacements = []
    for row in target_rows:
        fitted = fit_transform(source, row)
        replacements.append({"old": row, "new_label": "J119 P01 replacement - " + row["label"],
                             "new_transform": fitted,
                             "scale_ratio_vs_p01": [fitted["scale"][i] / source["scale"][i] for i in range(3)]})
    return {"schema": 1, "world": WORLD, "source": source, "replacements": replacements,
            "component_below_offset_cm": float(args["component_below_offset_cm"]),
            "sequence_bindings": sequence_rows, "sequence_scan_unclear": unclear,
            "sequence_component_blockers": blockers, "sequence_inherited_tracks": inherited,
            "save_allowlist": [WORLD], "klara_packages_forbidden": list(KLARA_PACKAGES),
            "texel_density": {"status": "inferred", "basis": "same P01 mesh and material interface; live mapping and stills pending",
                              "apply_ack_required": True},
            "stills_plan": [
                "Matched P01 and S2 grazing-angle stills with identical exposure and camera height.",
                "S2 wide still proving Floor 1-3 plus Apron have no gaps/overlap at boundaries.",
                "Before/during/after every S2 floor visibility section; replacements must follow AActor::bHidden.",
                "Hangar rise/move start, midpoint and end; replacements must remain attached and aligned.",
                "Collision walk/trace across all four joins after visual approval.",
            ]}, source_actor, targets


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    args_path = os.path.join(here, "j119_s2_p01_floor_replace_args.json")
    record_path = os.path.join(here, "j119_s2_p01_floor_replace_record.json")
    with open(args_path, encoding="utf-8") as handle:
        args = json.load(handle)
    mode = str(args.get("mode", "DRY")).upper()
    run = "J119S2P01-%s" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    if mode not in MODES:
        raise Refused("BAD_MODE|" + mode)
    if not confirm_ok(mode, str(args.get("confirm", ""))):
        raise Refused("CONFIRM_REQUIRED|%s J119S2P01FLOOR" % mode)
    world = _require_context()
    initial = _census()
    if mode != "DRY" and initial != {"content": [], "maps": []}:
        raise Refused("DIRTY_AT_START|" + json.dumps(initial))

    if mode == "REVERT":
        if not os.path.exists(record_path):
            raise Refused("REVERT_RECORD_MISSING")
        with open(record_path, encoding="utf-8") as handle:
            record = json.load(handle)
        if record.get("state") not in ("save_attempted", "applied") or record.get("world") != WORLD:
            raise Refused("REVERT_RECORD_CONTEXT")
        owned = {_path(a): a for a in _owned_actors()}
        if sorted(owned) != sorted(row["created_actor_path"] for row in record["actors"]):
            raise Refused("REVERT_OWNERSHIP_DRIFT")
        labels = _actors_by_label()
        backup = _backup(run, "PreJ119S2P01FloorRevert", record_path)
        for row in record["actors"]:
            old = _one(labels, row["old_label"])
            component = _one_component(old)
            current = v3(_prop(component, "relative_location"))
            if any(abs(current[i] - row["shifted_component_relative_location"][i]) > 0.02 for i in range(3)):
                raise Refused("REVERT_OLD_COMPONENT_DRIFT|" + row["old_label"])
            component.set_editor_property("relative_location", unreal.Vector(*row["old_component_relative_location"]))
            unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(owned[row["created_actor_path"]])
        save_before, final = _save_level_only()
        archived = record_path + ".reverted-" + run
        os.rename(record_path, archived)
        unreal.log("%s_REVERT_OK|run=%s|saved=%s|klara_saved=0|backup=%s|record=%s|census_before_save=%s|census_after=%s" %
                   (MARK, run, WORLD, backup, archived, json.dumps(save_before), json.dumps(final)))
        return

    if _owned_actors() or os.path.exists(record_path):
        raise Refused("ACTIVE_RECORD_OR_OWNED_ACTORS")
    plan, source_actor, targets = _make_plan(args, world)
    plan["plan_sha256"] = digest(plan)
    if mode == "DRY":
        final = _census()
        if initial != final:
            raise Refused("DRY_DIRTIED_PACKAGES|before=%s|after=%s" % (json.dumps(initial), json.dumps(final)))
        output = os.path.join(here, "j119_dry_%s.json" % run)
        _write_json(output, {"run": run, "mode": mode, "census_before": initial, "census_after": final, "plan": plan}, True)
        unreal.log("%s_DRY_OK|run=%s|mutated=0|floors=4|bindings=%d|blockers=%d|unclear=%d|plan_sha256=%s|report=%s" %
                   (MARK, run, len(plan["sequence_bindings"]), len(plan["sequence_component_blockers"]),
                    len(plan["sequence_scan_unclear"]), plan["plan_sha256"], output))
        return

    if str(args.get("plan_sha256", "")) != plan["plan_sha256"]:
        raise Refused("PLAN_DIGEST_MISMATCH|expected=%s" % plan["plan_sha256"])
    if plan["sequence_component_blockers"]:
        raise Refused("COMPONENT_SEQUENCE_BINDING_BLOCKS_APPLY|" + json.dumps(plan["sequence_component_blockers"]))
    if plan["sequence_scan_unclear"] and not bool(args.get("ack_sequence_scan_unclear", False)):
        raise Refused("SEQUENCE_SCAN_UNCLEAR_ACK_REQUIRED|" + json.dumps(plan["sequence_scan_unclear"]))
    if not bool(args.get("ack_texel_density_inferred", False)):
        raise Refused("TEXEL_DENSITY_INFERRED_ACK_REQUIRED")

    backup = _backup(run, "PreJ119S2P01Floor")
    record = {"schema": 1, "run": run, "world": WORLD, "backup": backup, "plan": plan,
              "actors": [], "applied": False}
    _write_json(record_path, record, True)  # durable before first mutation
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    offset = float(plan["component_below_offset_cm"])
    for target_actor, item in zip(targets, plan["replacements"]):
        duplicate = subsystem.duplicate_actor(source_actor, world, unreal.Vector(0, 0, 0))
        if duplicate is None or _level(duplicate) != WORLD:
            raise Refused("DUPLICATE_FAILED_OR_NOT_PERSISTENT|NOTHING_SAVED_DONT_SAVE_RESTART")
        transform = item["new_transform"]
        duplicate.set_actor_label(item["new_label"])
        duplicate.tags = list(_prop(duplicate, "tags", ()) or ()) + [unreal.Name(TAG)]
        duplicate.set_actor_location(unreal.Vector(*transform["location"]), False, True)
        duplicate.set_actor_rotation(unreal.Rotator(roll=transform["rotation"][0], pitch=transform["rotation"][1],
                                                     yaw=transform["rotation"][2]), False)
        duplicate.set_actor_scale3d(unreal.Vector(*transform["scale"]))
        duplicate.attach_to_actor(target_actor, "", unreal.AttachmentRule.KEEP_WORLD,
                                  unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
        old_component = _one_component(target_actor)
        old_location = v3(_prop(old_component, "relative_location"))
        shifted = [old_location[0], old_location[1], old_location[2] - offset]
        old_component.set_editor_property("relative_location", unreal.Vector(*shifted))
        record["actors"].append({"old_label": item["old"]["label"], "old_actor_path": item["old"]["actor_path"],
                                 "old_component_path": item["old"]["component_path"],
                                 "old_component_relative_location": old_location,
                                 "shifted_component_relative_location": shifted,
                                 "created_actor_path": _path(duplicate), "created_label": item["new_label"]})
        _write_json(record_path, record)
        got = _snapshot(duplicate)
        if (got["actor_class"] != plan["source"]["actor_class"] or
                got["mesh"] != plan["source"]["mesh"] or
                got["materials"] != plan["source"]["materials"] or
                got["component_settings"] != plan["source"]["component_settings"]):
            raise Refused("P01_COMPONENT_COPY_READBACK|%s|NOTHING_SAVED_DONT_SAVE_RESTART" % item["new_label"])
        if not _bounds_close(got["world_bounds"], item["old"]["world_bounds"], float(args["bounds_tolerance_cm"])):
            raise Refused("FOOTPRINT_READBACK|%s|got=%s|want=%s|NOTHING_SAVED_DONT_SAVE_RESTART" %
                          (item["new_label"], json.dumps(got["world_bounds"]), json.dumps(item["old"]["world_bounds"])))

    record["state"] = "save_attempted"
    _write_json(record_path, record)
    save_before, final = _save_level_only()
    # Saved-state read-back from the still-open saved persistent world; no reload of the open map.
    owned = {_path(a): a for a in _owned_actors()}
    if sorted(owned) != sorted(row["created_actor_path"] for row in record["actors"]):
        raise Refused("POST_SAVE_OWNERSHIP_READBACK")
    for row in record["actors"]:
        if _level(owned[row["created_actor_path"]]) != WORLD:
            raise Refused("POST_SAVE_LEVEL_READBACK")
    record["applied"] = True
    record["state"] = "applied"
    record["census_before_save"] = save_before
    record["post_save_census"] = final
    record["read_back"] = {"owned_actor_count": len(owned), "persistent_only": True,
                           "note": "current-world read-back after targeted save; map reload intentionally forbidden"}
    _write_json(record_path, record)
    unreal.log("%s_APPLY_OK|run=%s|created=4|saved=%s|klara_saved=0|backup=%s|record=%s|census_after=%s|readback=1" %
               (MARK, run, WORLD, backup, record_path, json.dumps(final)))


if unreal is not None:
    try:
        main()
    except Exception as exc:
        unreal.log_error("%s_FAILED|%r" % (MARK, exc))
        raise
