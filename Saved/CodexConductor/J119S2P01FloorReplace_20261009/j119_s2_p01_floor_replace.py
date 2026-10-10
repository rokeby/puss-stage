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
P02_TARGET_LABELS = ("Passage 02 - Floor Near", "Passage 02 - Floor Left",
                     "Passage 02 - Floor Right", "Passage 02 - Floor Far")
P02_TAG = "Codex.J129.P02P01FloorReplacement"
P02_MARK = "J129_P02_P01_FLOOR_REPLACE"
KLARA_PACKAGES = ("/Game/Scenes/L_Animals", "/Game/Scenes/L_KK_children",
                  "/Game/Scenes/Japanese_Alley", "/Game/Scenes/L_KK_Void")
MODES = ("DRY", "APPLY", "REVERT")


class Refused(RuntimeError):
    pass


def confirm_ok(mode, value):
    return mode == "DRY" or value == "%s J119S2P01FLOOR" % mode


def p02_confirm_ok(mode, value):
    return mode == "DRY" or value == "%s J129P02P01FLOOR" % mode


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


def actor_transform_for_component_world(component_world, component_relative):
    """Solve an actor transform for a duplicated component's desired world transform.

    P01's floor component is intentionally scaled relative to its actor.  Duplication
    preserves that relative transform, so treating it as identity compounds the scale.
    The representation is exact for the current zero-rotation component contract and
    refuses rotations/shear rather than silently approximating them.
    """
    rel_rotation = [float(x) for x in component_relative["rotation"]]
    if max(abs(x) for x in rel_rotation) > 1e-4:
        raise ValueError("unsupported source component rotation")
    rel_scale = [float(x) for x in component_relative["scale"]]
    if min(abs(x) for x in rel_scale) <= 1e-6:
        raise ValueError("degenerate source component scale")
    actor_scale = [float(component_world["scale"][i]) / rel_scale[i] for i in range(3)]
    rotation = [float(x) for x in component_world["rotation"]]
    if abs(rotation[0]) > 1e-6 or abs(rotation[1]) > 1e-6:
        raise ValueError("pitched/rolled component world transform is unsupported")
    yaw = math.radians(rotation[2])
    c, s = math.cos(yaw), math.sin(yaw)
    rel_location = [float(component_relative["location"][i]) * actor_scale[i] for i in range(3)]
    offset = [c * rel_location[0] - s * rel_location[1],
              s * rel_location[0] + c * rel_location[1], rel_location[2]]
    return {"location": [float(component_world["location"][i]) - offset[i] for i in range(3)],
            "rotation": rotation, "scale": actor_scale}


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


def _snapshot(actor, component_world=False):
    component = _one_component(actor)
    mesh = _prop(component, "static_mesh")
    if mesh is None:
        raise Refused("NO_STATIC_MESH|" + str(actor.get_actor_label()))
    if not component_world and not _identity_component(component):
        raise Refused("NON_IDENTITY_COMPONENT_TRANSFORM|" + str(actor.get_actor_label()))
    relative_location = v3(_prop(component, "relative_location"))
    relative_rotation_value = _prop(component, "relative_rotation")
    relative_rotation = [float(relative_rotation_value.roll), float(relative_rotation_value.pitch),
                         float(relative_rotation_value.yaw)]
    relative_scale = v3(_prop(component, "relative_scale3d"))
    if component_world:
        if max(abs(x) for x in relative_rotation) > 1e-4:
            raise Refused("UNSUPPORTED_SOURCE_COMPONENT_ROTATION|%s|%s" %
                          (actor.get_actor_label(), relative_rotation))
        if min(abs(x) for x in relative_scale) <= 1e-6:
            raise Refused("DEGENERATE_SOURCE_COMPONENT_SCALE|%s|%s" %
                          (actor.get_actor_label(), relative_scale))
        transform = component.get_component_transform()
        transform_rotation = transform.rotation.rotator()
        location = v3(transform.translation)
        rotation = [float(transform_rotation.roll), float(transform_rotation.pitch), float(transform_rotation.yaw)]
        scale = v3(transform.scale3d)
    else:
        actor_rotation = actor.get_actor_rotation()
        location = v3(actor.get_actor_location())
        rotation = [float(actor_rotation.roll), float(actor_rotation.pitch), float(actor_rotation.yaw)]
        scale = v3(actor.get_actor_scale3d())
    bmin, bmax = _bbox(mesh)
    origin, extent = unreal.SystemLibrary.get_actor_bounds(actor, False)
    return {
        "label": str(actor.get_actor_label()), "actor_path": _path(actor), "level": _level(actor),
        "actor_class": _path(actor.get_class()), "component_path": _path(component), "mesh": _path(mesh),
        "materials": [_path(component.get_material(i)) for i in range(int(component.get_num_materials()))],
        "location": location, "rotation": rotation, "scale": scale,
        "bbox_min": bmin, "bbox_max": bmax,
        "world_bounds": {"origin": v3(origin), "extent": v3(extent),
                         "min": [v3(origin)[i] - v3(extent)[i] for i in range(3)],
                         "max": [v3(origin)[i] + v3(extent)[i] for i in range(3)]},
        "component_relative_location": relative_location,
        "component_relative_transform": {"location": relative_location, "rotation": relative_rotation,
                                         "scale": relative_scale},
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


def _bounds_for_row(row):
    if abs(row["rotation"][0]) > 1e-6 or abs(row["rotation"][1]) > 1e-6:
        raise Refused("P02_PITCHED_OR_ROLLED_SEGMENT|" + json.dumps(row))
    radians = math.radians(row["rotation"][2])
    c, s = math.cos(radians), math.sin(radians)
    points = []
    for x in (row["bbox_min"][0], row["bbox_max"][0]):
        for y in (row["bbox_min"][1], row["bbox_max"][1]):
            for z in (row["bbox_min"][2], row["bbox_max"][2]):
                local = [x * row["scale"][0], y * row["scale"][1], z * row["scale"][2]]
                points.append([row["location"][0] + c * local[0] - s * local[1],
                               row["location"][1] + s * local[0] + c * local[1],
                               row["location"][2] + local[2]])
    low = [min(point[i] for point in points) for i in range(3)]
    high = [max(point[i] for point in points) for i in range(3)]
    return {"min": low, "max": high,
            "origin": [(low[i] + high[i]) * 0.5 for i in range(3)],
            "extent": [(high[i] - low[i]) * 0.5 for i in range(3)]}


def _p02_components(actor):
    return [component for component in actor.get_components_by_class(unreal.StaticMeshComponent)
            if _prop(component, "static_mesh") is not None]


def _p02_segments(targets):
    """One replacement per existing route segment, or per ISM instance when boards are instanced."""
    rows = []
    for actor in targets:
        components = _p02_components(actor)
        if not components:
            raise Refused("P02_NO_STATIC_MESH_COMPONENT|" + str(actor.get_actor_label()))
        for component_index, component in enumerate(components):
            mesh = _prop(component, "static_mesh")
            bmin, bmax = _bbox(mesh)
            count = int(component.get_instance_count()) if hasattr(component, "get_instance_count") else 0
            if count:
                transforms = [(instance_index, component.get_instance_transform(instance_index, True))
                              for instance_index in range(count)]
                construction = "instanced_board_per_instance"
            else:
                transforms = [(None, component.get_component_transform())]
                construction = "route_static_mesh_component"
            for instance_index, transform in transforms:
                rotation = transform.rotation.rotator()
                row = {
                    "target_label": str(actor.get_actor_label()), "target_actor_path": _path(actor),
                    "target_component_path": _path(component), "component_index": component_index,
                    "instance_index": instance_index, "construction": construction, "mesh": _path(mesh),
                    "location": v3(transform.translation),
                    "rotation": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
                    "scale": v3(transform.scale3d), "bbox_min": bmin, "bbox_max": bmax,
                }
                row["world_bounds"] = _bounds_for_row(row)
                rows.append(row)
    if not rows:
        raise Refused("P02_NO_ROUTE_SEGMENTS")
    return rows


def _sequence_audit_p02(world, targets):
    target_objects = {}
    for actor in targets:
        target_objects[_path(actor)] = (str(actor.get_actor_label()), "actor")
        for component in _p02_components(actor):
            target_objects[_path(component)] = (str(actor.get_actor_label()), "component")
        parent = actor.get_attach_parent_actor()
        while parent is not None:
            target_objects.setdefault(_path(parent), (str(actor.get_actor_label()), "ancestor_actor"))
            parent = parent.get_attach_parent_actor()
    rows, unclear = [], []
    for asset_path in unreal.EditorAssetLibrary.list_assets("/Game", True, False):
        data = unreal.EditorAssetLibrary.find_asset_data(asset_path)
        if str(_prop(_prop(data, "asset_class_path"), "asset_name", "")) != "LevelSequence":
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
                if hit:
                    for track in list(binding.get_tracks()):
                        rows.append({"sequence": asset_path, "binding": str(binding.get_name()),
                                     "bound_object": _path(obj), "target_label": hit[0], "object_kind": hit[1],
                                     "track_class": track.get_class().get_name(), "property": _track_property(track)})
    return rows, unclear


def _p02_passage_actor():
    rows = [actor for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
            if actor.get_class().get_name() == "InfinityStagePassageActor" and
            str(actor.get_actor_label()).startswith("Passage 02")]
    if len(rows) != 1 or _level(rows[0]) != WORLD:
        raise Refused("P02_PASSAGE_ACTOR_COUNT_OR_LEVEL|count=%d" % len(rows))
    return rows[0]


def _owned_p02():
    return [actor for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
            if P02_TAG in [str(value) for value in list(_prop(actor, "tags", ()) or ())]]


def _p02_plan(args, world):
    labels = _actors_by_label()
    source_actor = _one(labels, SOURCE_LABEL)
    targets = [_one(labels, label) for label in P02_TARGET_LABELS]
    for actor in [source_actor] + targets:
        if _level(actor) != WORLD:
            raise Refused("ACTOR_NOT_PERSISTENT|label=%s|level=%s" % (actor.get_actor_label(), _level(actor)))
    source = _snapshot(source_actor, component_world=True)
    segments = _p02_segments(targets)
    replacements = []
    for index, segment in enumerate(segments):
        fitted = fit_transform(source, segment)
        actor_transform = actor_transform_for_component_world(fitted, source["component_relative_transform"])
        replacements.append({"segment": segment,
                             "new_label": "J129 P01 route segment %03d - %s" % (index + 1, segment["target_label"]),
                             "new_transform": actor_transform, "expected_component_world_transform": fitted,
                             "scale_ratio_vs_p01_component_world":
                                 [fitted["scale"][i] / source["scale"][i] for i in range(3)]})
    sequence_rows, unclear = _sequence_audit_p02(world, targets)
    blockers, inherited = sequence_binding_policy(sequence_rows)
    passage = _p02_passage_actor()
    plan = {
        "schema": 2, "target": "P02", "world": WORLD, "source": source,
        "target_actor_labels": list(P02_TARGET_LABELS), "route_segments": len(segments),
        "construction_methods": sorted(set(row["construction"] for row in segments)),
        "construction_contract": "duplicate the P01 floor actor once per existing P02 route component/ISM instance; never one corridor plane",
        "source_component_transform_contract": "preserve P01 component-relative location/scale; solve actor transform from desired component world transform; refuse any component-relative rotation",
        "replacements": replacements, "component_below_offset_cm": float(args["component_below_offset_cm"]),
        "sequence_bindings": sequence_rows, "sequence_scan_unclear": unclear,
        "sequence_component_blockers": blockers, "sequence_inherited_tracks": inherited,
        "passage_materialization": {"actor": _path(passage), "label": str(passage.get_actor_label()),
                                    "apply_and_revert_required": True},
        "save_allowlist": [WORLD], "klara_packages_forbidden": list(KLARA_PACKAGES),
        "texel_density": {"status": "inferred", "basis": "same P01 mesh/material per route segment; live mapping and stills pending",
                          "apply_ack_required": True},
        "stills_plan": [
            "Matched P01/P02 grazing-angle stills with identical exposure and camera height.",
            "P02 full route stills proving every Near/Left/Right/Far segment is covered without a corridor-spanning plane.",
            "Every P02 floor visibility section before/during/after; replacements must inherit AActor::bHidden.",
            "Passage 02 start/mid/end after materialize_passage; route joins and any curve must remain aligned.",
            "Collision walk/trace across every segment join after visual approval.",
        ],
    }
    return plan, source_actor, targets, passage


def _p02_component_map(targets):
    return {_path(component): component for actor in targets for component in _p02_components(actor)}


def _main_p02(args, here):
    mode = str(args.get("mode", "DRY")).upper()
    run = "J129P02P01-%s" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    record_path = os.path.join(here, "j129_p02_p01_floor_replace_record.json")
    if mode not in MODES:
        raise Refused("BAD_MODE|" + mode)
    if not p02_confirm_ok(mode, str(args.get("confirm", ""))):
        raise Refused("CONFIRM_REQUIRED|%s J129P02P01FLOOR" % mode)
    world = _require_context()
    initial = _census()
    if mode != "DRY" and initial != {"content": [], "maps": []}:
        raise Refused("DIRTY_AT_START|" + json.dumps(initial))

    if mode == "REVERT":
        if not os.path.exists(record_path):
            raise Refused("REVERT_RECORD_MISSING")
        with open(record_path, encoding="utf-8") as handle:
            record = json.load(handle)
        if record.get("state") not in ("save_attempted", "applied") or record.get("world") != WORLD or record.get("target") != "P02":
            raise Refused("REVERT_RECORD_CONTEXT")
        owned = {_path(actor): actor for actor in _owned_p02()}
        if sorted(owned) != sorted(row["created_actor_path"] for row in record["actors"]):
            raise Refused("REVERT_OWNERSHIP_DRIFT")
        labels = _actors_by_label()
        targets = [_one(labels, label) for label in P02_TARGET_LABELS]
        components = _p02_component_map(targets)
        backup = _backup(run, "PreJ129P02P01FloorRevert", record_path)
        for row in record["components"]:
            component = components.get(row["component_path"])
            if component is None:
                raise Refused("REVERT_COMPONENT_MISSING|" + row["component_path"])
            current = v3(_prop(component, "relative_location"))
            if any(abs(current[i] - row["shifted_relative_location"][i]) > 0.02 for i in range(3)):
                raise Refused("REVERT_COMPONENT_DRIFT|" + row["component_path"])
            component.set_editor_property("relative_location", unreal.Vector(*row["old_relative_location"]))
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        for actor in owned.values():
            if not subsystem.destroy_actor(actor):
                raise Refused("P02_REVERT_DESTROY_FAILED|NOTHING_SAVED_DONT_SAVE_RESTART|" + _path(actor))
        passage = _p02_passage_actor()
        if not bool(passage.materialize_passage()):
            raise Refused("P02_REVERT_MATERIALIZE_FAILED|NOTHING_SAVED_DONT_SAVE_RESTART")
        save_before, final = _save_level_only()
        archived = record_path + ".reverted-" + run
        os.rename(record_path, archived)
        unreal.log("%s_REVERT_OK|run=%s|restored_components=%d|destroyed=%d|materialized=1|saved=%s|klara_saved=0|backup=%s|record=%s|census_before_save=%s|census_after=%s" %
                   (P02_MARK, run, len(record["components"]), len(owned), WORLD, backup, archived,
                    json.dumps(save_before), json.dumps(final)))
        return

    if _owned_p02() or os.path.exists(record_path):
        raise Refused("ACTIVE_P02_RECORD_OR_OWNED_ACTORS")
    plan, source_actor, targets, passage = _p02_plan(args, world)
    plan["plan_sha256"] = digest(plan)
    if mode == "DRY":
        final = _census()
        if initial != final:
            raise Refused("DRY_DIRTIED_PACKAGES|before=%s|after=%s" % (json.dumps(initial), json.dumps(final)))
        output = os.path.join(here, "j129_p02_dry_%s.json" % run)
        _write_json(output, {"run": run, "mode": mode, "census_before": initial, "census_after": final, "plan": plan}, True)
        unreal.log("%s_DRY_OK|run=%s|mutated=0|target_actors=4|route_segments=%d|bindings=%d|blockers=%d|unclear=%d|plan_sha256=%s|report=%s" %
                   (P02_MARK, run, plan["route_segments"], len(plan["sequence_bindings"]),
                    len(plan["sequence_component_blockers"]), len(plan["sequence_scan_unclear"]),
                    plan["plan_sha256"], output))
        return
    if str(args.get("plan_sha256", "")) != plan["plan_sha256"]:
        raise Refused("PLAN_DIGEST_MISMATCH|expected=%s" % plan["plan_sha256"])
    if plan["sequence_component_blockers"]:
        raise Refused("COMPONENT_SEQUENCE_BINDING_BLOCKS_APPLY|" + json.dumps(plan["sequence_component_blockers"]))
    if plan["sequence_scan_unclear"] and not bool(args.get("ack_sequence_scan_unclear", False)):
        raise Refused("SEQUENCE_SCAN_UNCLEAR_ACK_REQUIRED|" + json.dumps(plan["sequence_scan_unclear"]))
    if not bool(args.get("ack_texel_density_inferred", False)):
        raise Refused("TEXEL_DENSITY_INFERRED_ACK_REQUIRED")

    backup = _backup(run, "PreJ129P02P01Floor")
    record = {"schema": 2, "target": "P02", "run": run, "world": WORLD, "backup": backup,
              "plan": plan, "components": [], "actors": [], "applied": False, "state": "applying"}
    _write_json(record_path, record, True)
    offset = float(plan["component_below_offset_cm"])
    component_map = _p02_component_map(targets)
    for component_path, component in sorted(component_map.items()):
        old = v3(_prop(component, "relative_location"))
        shifted = [old[0], old[1], old[2] - offset]
        record["components"].append({"component_path": component_path, "old_relative_location": old,
                                     "shifted_relative_location": shifted})
        component.set_editor_property("relative_location", unreal.Vector(*shifted))
        _write_json(record_path, record)
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    target_by_path = {_path(actor): actor for actor in targets}
    for item in plan["replacements"]:
        target_actor = target_by_path[item["segment"]["target_actor_path"]]
        duplicate = subsystem.duplicate_actor(source_actor, world, unreal.Vector(0, 0, 0))
        if duplicate is None or _level(duplicate) != WORLD:
            raise Refused("DUPLICATE_FAILED_OR_NOT_PERSISTENT|NOTHING_SAVED_DONT_SAVE_RESTART")
        transform = item["new_transform"]
        duplicate.set_actor_label(item["new_label"])
        duplicate.tags = list(_prop(duplicate, "tags", ()) or ()) + [unreal.Name(P02_TAG)]
        duplicate.set_actor_location(unreal.Vector(*transform["location"]), False, True)
        duplicate.set_actor_rotation(unreal.Rotator(roll=transform["rotation"][0], pitch=transform["rotation"][1],
                                                     yaw=transform["rotation"][2]), False)
        duplicate.set_actor_scale3d(unreal.Vector(*transform["scale"]))
        duplicate.attach_to_actor(target_actor, "", unreal.AttachmentRule.KEEP_WORLD,
                                  unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
        record["actors"].append({"created_actor_path": _path(duplicate), "created_label": item["new_label"],
                                 "target_actor_path": item["segment"]["target_actor_path"],
                                 "expected_world_bounds": item["segment"]["world_bounds"]})
        _write_json(record_path, record)
        got = _snapshot(duplicate, component_world=True)
        if (got["actor_class"] != plan["source"]["actor_class"] or got["mesh"] != plan["source"]["mesh"] or
                got["materials"] != plan["source"]["materials"] or
                got["component_settings"] != plan["source"]["component_settings"]):
            raise Refused("P01_COMPONENT_COPY_READBACK|%s|NOTHING_SAVED_DONT_SAVE_RESTART" % item["new_label"])
        if not _bounds_close(got["world_bounds"], item["segment"]["world_bounds"], float(args["bounds_tolerance_cm"])):
            raise Refused("P02_SEGMENT_FOOTPRINT_READBACK|%s|got=%s|want=%s|NOTHING_SAVED_DONT_SAVE_RESTART" %
                          (item["new_label"], json.dumps(got["world_bounds"]), json.dumps(item["segment"]["world_bounds"])))
    if not bool(passage.materialize_passage()):
        raise Refused("P02_MATERIALIZE_FAILED|NOTHING_SAVED_DONT_SAVE_RESTART")
    for row in record["components"]:
        component = component_map.get(row["component_path"])
        current = v3(_prop(component, "relative_location")) if component is not None else None
        if current is None or any(abs(current[i] - row["shifted_relative_location"][i]) > 0.02 for i in range(3)):
            raise Refused("P02_COMPONENT_POST_MATERIALIZE_READBACK|%s|NOTHING_SAVED_DONT_SAVE_RESTART" % row["component_path"])
    record["state"] = "save_attempted"
    _write_json(record_path, record)
    save_before, final = _save_level_only()
    owned = {_path(actor): actor for actor in _owned_p02()}
    if sorted(owned) != sorted(row["created_actor_path"] for row in record["actors"]):
        raise Refused("POST_SAVE_OWNERSHIP_READBACK")
    for row in record["actors"]:
        actor = owned[row["created_actor_path"]]
        if _level(actor) != WORLD or _path(actor.get_attach_parent_actor()) != row["target_actor_path"]:
            raise Refused("POST_SAVE_LEVEL_OR_ATTACHMENT_READBACK|" + row["created_actor_path"])
        got = _snapshot(actor, component_world=True)
        if (got["mesh"] != plan["source"]["mesh"] or got["materials"] != plan["source"]["materials"] or
                not _bounds_close(got["world_bounds"], row["expected_world_bounds"], float(args["bounds_tolerance_cm"]))):
            raise Refused("POST_SAVE_P02_SEGMENT_READBACK|" + row["created_actor_path"])
    record["applied"] = True
    record["state"] = "applied"
    record["census_before_save"] = save_before
    record["post_save_census"] = final
    record["read_back"] = {"owned_actor_count": len(owned), "persistent_only": True, "materialized": True,
                           "note": "current-world read-back after targeted save; map reload intentionally forbidden"}
    _write_json(record_path, record)
    unreal.log("%s_APPLY_OK|run=%s|created=%d|target_actors=4|materialized=1|saved=%s|klara_saved=0|backup=%s|record=%s|census_after=%s|readback=1" %
               (P02_MARK, run, len(owned), WORLD, backup, record_path, json.dumps(final)))


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    args_path = os.path.join(here, "j119_s2_p01_floor_replace_args.json")
    record_path = os.path.join(here, "j119_s2_p01_floor_replace_record.json")
    with open(args_path, encoding="utf-8") as handle:
        args = json.load(handle)
    target = str(args.get("target", "S2")).upper()
    if target == "P02":
        return _main_p02(args, here)
    if target != "S2":
        raise Refused("BAD_TARGET|%s|expected=S2|P02" % target)
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
