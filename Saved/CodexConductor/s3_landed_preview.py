"""Temporarily pose one or more Scene hangars at their landed transforms.

STATUS is read-only. UP and DOWN mutate only the transform-bound hangar actors
and never save. Sequence data is read from the asset channels; this tool never
opens, evaluates, scrubs, or plays Sequencer.
"""
import datetime
import json
import math
import os
import re
import traceback

try:
    import unreal
except ImportError:  # The pure-math harness imports this module offline.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HANGAR_IDS = (1, 2, 3, 4, 5, 6)
RISE_PATH_TEMPLATE = "/Game/InfinityStage/RigAtmos/LS_S%d_HangarRise"
S3_FAR_WALL_LABEL = "S3 Hangar Far Wall"
S3_DOCK_ORIGIN = (10921.973, 160000.0, 0.0)
S3_EXPECTED_FAR_WALL_INNER_X = 6500.0
CHANNEL_AXES = (
    "Location.X", "Location.Y", "Location.Z",
    "Rotation.X", "Rotation.Y", "Rotation.Z",
    "Scale.X", "Scale.Y", "Scale.Z",
)


class PreviewError(RuntimeError):
    pass


def expected_mover_labels(scene):
    """Return the only accepted transform-binding pattern for a hangar."""
    scene = int(scene)
    if scene not in HANGAR_IDS:
        raise PreviewError("hangar id must be one of 1..6")
    labels = [
        "S%d Hangar Root" % scene,
        "S%d Hangar Lattice Fly" % scene,
    ]
    if scene != 6:  # S6 is deliberately roofless.
        labels.insert(1, "S%d Hangar Roof Hinge" % scene)
    return tuple(labels)


def validate_mover_pattern(scene, labels):
    """Refuse missing, extra, or duplicate transform-bound actors."""
    scene = int(scene)
    labels = tuple(str(label) for label in labels)
    expected = expected_mover_labels(scene)
    duplicates = sorted(label for label in set(labels) if labels.count(label) != 1)
    missing = sorted(set(expected) - set(labels))
    extra = sorted(set(labels) - set(expected))
    if duplicates or missing or extra:
        distinction = (
            "S6 is roofless" if scene == 6
            else "S4 is roofed like S1-S5" if scene == 4
            else "S1-S5 require root, roof hinge, and lattice fly"
        )
        raise PreviewError(
            "S%d mover pattern mismatch (%s): duplicates=%s missing=%s extra=%s" %
            (scene, distinction, duplicates, missing, extra)
        )
    return expected


def parse_hangar_ids(value):
    """Parse ``all``, ``1,3,6``, ``S1 S3 S6``, or an integer/list equivalent."""
    if value is None:
        value = "all"
    if isinstance(value, str):
        if value.strip().lower() == "all":
            return HANGAR_IDS
        tokens = [token for token in re.split(r"[\s,]+", value.strip()) if token]
    elif isinstance(value, (int, float)):
        tokens = [value]
    else:
        try:
            tokens = list(value)
        except TypeError as exc:
            raise PreviewError("hangar selection must be ids or all") from exc
    if not tokens:
        raise PreviewError("hangar selection is empty")
    result = []
    for token in tokens:
        text = str(token).strip().upper()
        if text.startswith("S"):
            text = text[1:]
        if not text.isdigit():
            raise PreviewError("invalid hangar id: %s" % token)
        scene = int(text)
        if scene not in HANGAR_IDS:
            raise PreviewError("hangar id must be one of 1..6: %s" % token)
        if scene in result:
            raise PreviewError("duplicate hangar id: S%d" % scene)
        result.append(scene)
    return tuple(result)


def record_filename(scene):
    return "s%d_landed_preview_record.json" % int(scene)


def normalize_degrees(value):
    return (float(value) + 180.0) % 360.0 - 180.0


def transform_from_channel_values(baseline, values):
    """Return a plain transform with every canonical channel applied."""
    missing = [name for name in CHANNEL_AXES if name not in values]
    if missing:
        raise PreviewError("missing transform channels: " + ", ".join(missing))
    return {
        "location": [float(values["Location.X"]), float(values["Location.Y"]), float(values["Location.Z"])],
        "rotation": [float(values["Rotation.X"]), float(values["Rotation.Y"]), float(values["Rotation.Z"])],
        "scale": [float(values["Scale.X"]), float(values["Scale.Y"]), float(values["Scale.Z"])],
    }


def transform_errors(got, wanted):
    location = math.sqrt(sum(
        (float(got["location"][index]) - float(wanted["location"][index])) ** 2
        for index in range(3)
    ))
    rotation = max(
        abs(normalize_degrees(float(got["rotation"][index]) - float(wanted["rotation"][index])))
        for index in range(3)
    )
    scale = max(
        abs(float(got["scale"][index]) - float(wanted["scale"][index]))
        for index in range(3)
    )
    return {"location_cm": location, "rotation_deg": rotation, "scale": scale}


def validate_pose_errors(rows, location_limit=0.01, rotation_limit=0.001,
                         scale_limit=0.000001):
    if not rows:
        raise PreviewError("no pose error rows")
    worst = {
        "location_cm": max(float(row["location_cm"]) for row in rows),
        "rotation_deg": max(float(row["rotation_deg"]) for row in rows),
        "scale": max(float(row["scale"]) for row in rows),
    }
    if (worst["location_cm"] > location_limit or
            worst["rotation_deg"] > rotation_limit or
            worst["scale"] > scale_limit):
        raise PreviewError(
            "pose mismatch: location_cm=%.9f rotation_deg=%.9f scale=%.9f" %
            (worst["location_cm"], worst["rotation_deg"], worst["scale"])
        )
    return worst


def validate_rest_composition(rows, location_limit=1.0):
    if not rows:
        raise PreviewError("no rest-composition rows")
    worst = max(rows, key=lambda row: float(row["location_cm"]))
    if float(worst["location_cm"]) > location_limit:
        raise PreviewError(
            "rest composition mismatch: label=%s location_cm=%.9f" %
            (worst.get("label"), float(worst["location_cm"]))
        )
    return {
        "status": "PASS",
        "limit_cm": location_limit,
        "max_location_error_cm": float(worst["location_cm"]),
        "worst_actor": worst.get("label"),
        "max_rotation_error_deg": max(float(row["rotation_deg"]) for row in rows),
        "max_scale_error": max(float(row["scale"]) for row in rows),
        "actor_count": len(rows),
    }


def validate_far_wall_inner_x(inner_x, expected=S3_EXPECTED_FAR_WALL_INNER_X,
                              tolerance=1.0):
    error = abs(float(inner_x) - float(expected))
    if error > tolerance:
        raise PreviewError(
            "S3 far-wall landed inner face mismatch: x=%.6f expected=%.6f error=%.6f" %
            (float(inner_x), float(expected), error)
        )
    return error


def _record_path(scene):
    saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    return os.path.join(saved, "CodexConductor", record_filename(scene))


def _frame_value(value):
    if hasattr(value, "frame_number"):
        return int(value.frame_number.value)
    if hasattr(value, "value"):
        return int(value.value)
    return int(value)


def _channel_name(channel):
    try:
        return str(channel.get_name())
    except Exception:
        return str(channel.channel_name)


def _canonical_channel_name(name):
    for candidate in CHANNEL_AXES:
        if name == candidate or name.startswith(candidate + "_"):
            return candidate
    return None


def _plain_transform(value):
    rotation = value.rotation.rotator()
    return {
        "location": [float(value.translation.x), float(value.translation.y), float(value.translation.z)],
        "rotation": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
        "scale": [float(value.scale3d.x), float(value.scale3d.y), float(value.scale3d.z)],
    }


def _unreal_transform(value):
    return unreal.Transform(
        location=unreal.Vector(*value["location"]),
        rotation=unreal.Rotator(
            roll=value["rotation"][0], pitch=value["rotation"][1], yaw=value["rotation"][2]),
        scale=unreal.Vector(*value["scale"]),
    )


def _current_relative_plain(actor):
    parent = actor.get_attach_parent_actor()
    value = actor.root_component.get_relative_transform() if parent else actor.get_actor_transform()
    return _plain_transform(value)


def _read_binding_transform(binding, actor, sequence):
    tracks = list(binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack))
    if len(tracks) != 1 or len(tracks[0].get_sections()) != 1:
        raise PreviewError(
            "%s has %d transform tracks or an unexpected section count" %
            (actor.get_actor_label(), len(tracks))
        )
    track = tracks[0]
    section = track.get_sections()[0]
    baseline = _current_relative_plain(actor)
    baseline_values = {
        "Location.X": baseline["location"][0], "Location.Y": baseline["location"][1],
        "Location.Z": baseline["location"][2], "Rotation.X": baseline["rotation"][0],
        "Rotation.Y": baseline["rotation"][1], "Rotation.Z": baseline["rotation"][2],
        "Scale.X": baseline["scale"][0], "Scale.Y": baseline["scale"][1],
        "Scale.Z": baseline["scale"][2],
    }
    first_values = dict(baseline_values)
    last_values = dict(baseline_values)
    fps = float(sequence.get_display_rate().numerator) / float(sequence.get_display_rate().denominator)
    rows = []
    seen = set()
    for channel in section.get_all_channels():
        raw_name = _channel_name(channel)
        name = _canonical_channel_name(raw_name)
        if name is None:
            continue
        seen.add(name)
        keys = sorted(list(channel.get_keys()), key=lambda key: _frame_value(key.get_time()))
        default_value = None
        try:
            if channel.has_default():
                default_value = float(channel.get_default())
        except Exception:
            pass
        if keys:
            first, last = keys[0], keys[-1]
            first_values[name], last_values[name] = float(first.get_value()), float(last.get_value())
            source = "first/last key"
            first_frame, last_frame = _frame_value(first.get_time()), _frame_value(last.get_time())
        elif default_value is not None:
            first_values[name] = last_values[name] = default_value
            source, first_frame, last_frame = "channel default (no keys)", None, None
        else:
            source, first_frame, last_frame = "current relative/world baseline (no keys or default)", None, None
        rows.append({
            "property": name, "raw_channel": raw_name, "source": source,
            "first_frame": first_frame, "last_frame": last_frame,
            "first_seconds": float(first_frame) / fps if first_frame is not None else None,
            "last_seconds": float(last_frame) / fps if last_frame is not None else None,
            "rest_value": first_values[name], "landed_value": last_values[name],
        })
    missing = [name for name in CHANNEL_AXES if name not in seen]
    if missing:
        raise PreviewError(
            "%s transform track is missing channels: %s" %
            (actor.get_actor_label(), ", ".join(missing))
        )
    return {
        "binding": str(binding.get_display_name()), "track": str(track.get_display_name()),
        "channels": rows,
        "rest": transform_from_channel_values(baseline, first_values),
        "landed": transform_from_channel_values(baseline, last_values),
    }


def _one_actor(index, label):
    matches = index.get(label, [])
    if len(matches) != 1:
        raise PreviewError("expected exactly one actor labelled %s, found %d" % (label, len(matches)))
    return matches[0]


def _actor_index():
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    index = {}
    for actor in actors:
        index.setdefault(actor.get_actor_label(), []).append(actor)
    return actors, index


def _sequence_plan(scene, actors, index):
    path = RISE_PATH_TEMPLATE % scene
    rise = unreal.load_asset(path)
    if rise is None or not isinstance(rise, unreal.LevelSequence):
        raise PreviewError("S%d rise did not load as a LevelSequence: %s" % (scene, path))
    transform_bindings = [
        binding for binding in rise.get_bindings()
        if binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack)
    ]
    mover_labels = validate_mover_pattern(
        scene, [str(binding.get_display_name()) for binding in transform_bindings])
    bindings = {}
    for binding in transform_bindings:
        bindings.setdefault(str(binding.get_display_name()), []).append(binding)
    movers = {label: _one_actor(index, label) for label in mover_labels}
    rows = {}
    for label in mover_labels:
        matches = bindings.get(label, [])
        if len(matches) != 1:
            raise PreviewError(
                "S%d expected exactly one transform binding named %s, found %d" %
                (scene, label, len(matches))
            )
        rows[label] = _read_binding_transform(matches[0], movers[label], rise)
    root = movers["S%d Hangar Root" % scene]
    subtree = []
    for actor in actors:
        cursor, seen = actor, set()
        while cursor is not None and cursor not in seen:
            if cursor == root:
                subtree.append(actor)
                break
            seen.add(cursor)
            cursor = cursor.get_attach_parent_actor()
    if not subtree:
        raise PreviewError("S%d hangar root subtree is empty" % scene)
    return {
        "scene": scene, "rise_path": path, "mover_labels": mover_labels,
        "movers": movers, "rows": rows, "subtree": subtree,
    }


def _rest_composition_check(plan):
    rows, mover_labels = plan["rows"], plan["mover_labels"]
    overrides = {label: _unreal_transform(rows[label]["rest"]) for label in mover_labels}
    cache = {}

    def predicted_world(actor):
        label = actor.get_actor_label()
        if actor in cache:
            return cache[actor]
        parent = actor.get_attach_parent_actor()
        if label in overrides:
            local_or_world = overrides[label]
        else:
            local_or_world = actor.root_component.get_relative_transform() if parent else actor.get_actor_transform()
        value = (unreal.MathLibrary.compose_transforms(local_or_world, predicted_world(parent))
                 if parent else local_or_world)
        cache[actor] = value
        return value

    errors = []
    for actor in sorted(plan["subtree"], key=lambda value: value.get_actor_label()):
        row = transform_errors(_plain_transform(actor.get_actor_transform()),
                               _plain_transform(predicted_world(actor)))
        row["label"] = actor.get_actor_label()
        errors.append(row)
    return validate_rest_composition(errors)


def _pose_error_rows(plan, wanted):
    result = []
    for label in plan["mover_labels"]:
        row = transform_errors(_current_relative_plain(plan["movers"][label]), wanted[label])
        row["label"] = label
        result.append(row)
    return result


def _set_relative_transform(actor, value):
    actor.modify()
    actor.set_actor_relative_location(unreal.Vector(*value["location"]), False, True)
    actor.set_actor_relative_rotation(
        unreal.Rotator(roll=value["rotation"][0], pitch=value["rotation"][1],
                       yaw=value["rotation"][2]), False, True)
    actor.set_actor_relative_scale3d(unreal.Vector(*value["scale"]))


def _box_corners(minimum, maximum):
    return [unreal.Vector(x, y, z) for x in (minimum.x, maximum.x)
            for y in (minimum.y, maximum.y) for z in (minimum.z, maximum.z)]


def _actor_local_bound_points(actor):
    actor_world, points = actor.get_actor_transform(), []
    for component in actor.get_components_by_class(unreal.StaticMeshComponent):
        mesh = component.get_editor_property("static_mesh")
        if mesh is None:
            continue
        box = mesh.get_bounding_box()
        component_world = unreal.Transform(
            location=component.get_world_location(), rotation=component.get_world_rotation(),
            scale=component.get_world_scale())
        for mesh_point in _box_corners(box.min, box.max):
            world_point = unreal.MathLibrary.transform_location(component_world, mesh_point)
            points.append(unreal.MathLibrary.inverse_transform_location(actor_world, world_point))
    if not points:
        raise PreviewError("S3 Hangar Far Wall has no static-mesh bounds")
    return points


def _s3_far_wall_inner_x(index):
    far_wall = _one_actor(index, S3_FAR_WALL_LABEL)
    world = far_wall.get_actor_transform()
    dock = unreal.Transform(location=unreal.Vector(*S3_DOCK_ORIGIN),
                            rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    dock_x = []
    for point in _actor_local_bound_points(far_wall):
        world_point = unreal.MathLibrary.transform_location(world, point)
        dock_x.append(float(unreal.MathLibrary.inverse_transform_location(dock, world_point).x))
    return min(dock_x)


def _assert_context():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    world_path = world.get_outermost().get_name() if world is not None else None
    if world_path != EXPECTED_WORLD:
        raise PreviewError("unexpected editor world: %s" % world_path)
    if editor.get_game_world() is not None:
        raise PreviewError("PIE_OR_SIE_ACTIVE")


def _write_record(record, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x", encoding="utf-8") as handle:
        json.dump(record, handle, indent=1, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())


def _load_record(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _plan_log_value(plan):
    return {
        "rise_asset": plan["rise_path"],
        "movers": [{"label": label, "rest": plan["rows"][label]["rest"],
                    "landed": plan["rows"][label]["landed"]}
                   for label in plan["mover_labels"]],
    }


def _status_for_plan(run, plan):
    scene, record = plan["scene"], _record_path(plan["scene"])
    rest = {label: plan["rows"][label]["rest"] for label in plan["mover_labels"]}
    landed = {label: plan["rows"][label]["landed"] for label in plan["mover_labels"]}
    rest_errors, landed_errors = _pose_error_rows(plan, rest), _pose_error_rows(plan, landed)
    rest_worst = {key: max(float(row[key]) for row in rest_errors)
                  for key in ("location_cm", "rotation_deg", "scale")}
    landed_worst = {key: max(float(row[key]) for row in landed_errors)
                    for key in ("location_cm", "rotation_deg", "scale")}
    at_rest = (rest_worst["location_cm"] <= 0.01 and rest_worst["rotation_deg"] <= 0.001
               and rest_worst["scale"] <= 0.000001)
    at_landed = (landed_worst["location_cm"] <= 0.01 and landed_worst["rotation_deg"] <= 0.001
                 and landed_worst["scale"] <= 0.000001)
    pose = "REST" if at_rest else ("LANDED" if at_landed else "OTHER")
    unreal.log("HANGAR_PREVIEW_PLAN|run=%s|S%d|%s" %
               (run, scene, json.dumps(_plan_log_value(plan), sort_keys=True)))
    unreal.log(
        "HANGAR_PREVIEW|run=%s|S%d|status|up=%s|pose=%s|record=%s|rest_err_cm=%.9f|landed_err_cm=%.9f" %
        (run, scene, str(os.path.exists(record)).lower(), pose,
         str(os.path.exists(record)).lower(), rest_worst["location_cm"],
         landed_worst["location_cm"]))
    return {"scene": scene, "record_exists": os.path.exists(record), "at_rest": at_rest,
            "at_landed": at_landed, "rest_worst": rest_worst,
            "landed_worst": landed_worst}


def landed_save_check(states):
    """The level is safe to save only while every preview is recorded and LANDED."""
    if not states:
        raise PreviewError("save check has no hangar states")
    safe = all(state["record_exists"] and state["at_landed"] for state in states)
    max_err = max(float(state["landed_worst"]["location_cm"]) for state in states)
    blocked = ["S%d(record=%s,at_landed=%s)" %
               (state["scene"], str(state["record_exists"]).lower(),
                str(state["at_landed"]).lower())
               for state in states if not state["record_exists"] or not state["at_landed"]]
    return safe, max_err, blocked


def _run_status(run, plans, save_check):
    states = [_status_for_plan(run, plan) for plan in plans]
    if not save_check:
        return
    safe, max_err, blocked = landed_save_check(states)
    if safe:
        unreal.log("HANGAR_PREVIEW_SAFE_TO_SAVE|run=%s|hangars=%s|max_err_cm=%.9f" %
                   (run, ",".join("S%d" % state["scene"] for state in states), max_err))
    else:
        unreal.log_warning("HANGAR_PREVIEW_UP_DO_NOT_SAVE|run=%s|blocked=%s|max_err_cm=%.9f" %
                           (run, ",".join(blocked), max_err))


def _run_up(run, plans, index):
    prepared = []
    for plan in plans:
        scene, record = plan["scene"], _record_path(plan["scene"])
        if os.path.exists(record):
            raise PreviewError("S%d UP record already exists: %s" % (scene, record))
        rest_check = _rest_composition_check(plan)
        sequence_rest = {label: plan["rows"][label]["rest"] for label in plan["mover_labels"]}
        validate_pose_errors(_pose_error_rows(plan, sequence_rest))
        actual_rest = {label: _current_relative_plain(plan["movers"][label])
                       for label in plan["mover_labels"]}
        landed = {label: plan["rows"][label]["landed"] for label in plan["mover_labels"]}
        value = {
            "run": run, "written": datetime.datetime.now().isoformat(timespec="seconds"),
            "world": EXPECTED_WORLD, "scene": scene, "rise_asset": plan["rise_path"],
            "mover_labels": list(plan["mover_labels"]), "rest_transforms": actual_rest,
            "sequence_rest_transforms": sequence_rest, "landed_transforms": landed,
            "binding_channels": {label: plan["rows"][label]["channels"]
                                 for label in plan["mover_labels"]},
            "rest_pose_check": rest_check,
        }
        prepared.append((plan, record, value, landed, rest_check))

    # All records become durable before the first transform changes. A mid-run
    # exception therefore remains recoverable by DOWN without deleting anything.
    for _plan, record, value, _landed, _rest_check in prepared:
        _write_record(value, record)
    for plan, _record, _value, landed, _rest_check in prepared:
        for label in plan["mover_labels"]:
            _set_relative_transform(plan["movers"][label], landed[label])

    for plan, record, _value, landed, rest_check in prepared:
        scene = plan["scene"]
        readback = validate_pose_errors(_pose_error_rows(plan, landed))
        suffix = ""
        if scene == 3:
            far_wall_x = _s3_far_wall_inner_x(index)
            far_wall_error = validate_far_wall_inner_x(far_wall_x)
            suffix = "|far_wall_inner_x=%.6f|far_wall_err_cm=%.6f" % (far_wall_x, far_wall_error)
        unreal.log(
            "HANGAR_PREVIEW_UP_DONE|run=%s|S%d|record=%s|max_err_cm=%.9f|rest_err_cm=%.9f%s" %
            (run, scene, os.path.basename(record), readback["location_cm"],
             rest_check["max_location_error_cm"], suffix))


def _run_down(run, plans):
    prepared = []
    for plan in plans:
        scene, record = plan["scene"], _record_path(plan["scene"])
        if not os.path.exists(record):
            raise PreviewError("S%d DOWN record does not exist: %s" % (scene, record))
        value = _load_record(record)
        if value.get("world") != EXPECTED_WORLD:
            raise PreviewError("S%d record world mismatch" % scene)
        if value.get("rise_asset") != plan["rise_path"]:
            raise PreviewError("S%d record rise asset mismatch" % scene)
        rest = value.get("rest_transforms")
        if (not isinstance(rest, dict) or sorted(rest) != sorted(plan["mover_labels"])
                or sorted(value.get("mover_labels", [])) != sorted(plan["mover_labels"])):
            raise PreviewError("S%d record mover set mismatch" % scene)
        prepared.append((plan, record, rest))
    for plan, _record, rest in prepared:
        for label in plan["mover_labels"]:
            _set_relative_transform(plan["movers"][label], rest[label])
    verified = []
    for plan, record, rest in prepared:
        verified.append((plan, record, validate_pose_errors(_pose_error_rows(plan, rest)),
                         _rest_composition_check(plan)))
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    archives = []
    for plan, record, _readback, _rest_check in verified:
        archived = record + ".done-" + stamp
        if os.path.exists(archived):
            raise PreviewError("S%d record archive already exists: %s" % (plan["scene"], archived))
        archives.append(archived)
    for (_plan, record, _readback, _rest_check), archived in zip(verified, archives):
        os.rename(record, archived)
    for (plan, _record, readback, rest_check), archived in zip(verified, archives):
        unreal.log(
            "HANGAR_PREVIEW_DOWN_DONE|run=%s|S%d|max_err_cm=%.9f|max_err_deg=%.9f|record=%s|rest_err_cm=%.9f" %
            (run, plan["scene"], readback["location_cm"], readback["rotation_deg"],
             os.path.basename(archived), rest_check["max_location_error_cm"]))


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    mode = str(globals().get("HANGAR_LANDED_PREVIEW_MODE",
                             globals().get("S3_LANDED_PREVIEW_MODE", ""))).upper()
    selection = globals().get("HANGAR_LANDED_PREVIEW_IDS",
                              globals().get("S3_LANDED_PREVIEW_IDS", "all"))
    save_check = bool(globals().get("HANGAR_LANDED_PREVIEW_SAVE_CHECK",
                                    globals().get("S3_LANDED_PREVIEW_SAVE_CHECK")))
    try:
        if mode not in ("STATUS", "UP", "DOWN"):
            raise PreviewError("mode must be STATUS, UP, or DOWN")
        if save_check and mode != "STATUS":
            raise PreviewError("save check requires STATUS mode")
        scenes = HANGAR_IDS if save_check else parse_hangar_ids(selection)
        _assert_context()
        actors, index = _actor_index()
        plans = [_sequence_plan(scene, actors, index) for scene in scenes]
        if mode == "STATUS":
            _run_status(run, plans, save_check)
        elif mode == "UP":
            _run_up(run, plans, index)
        else:
            _run_down(run, plans)
    except Exception:
        unreal.log_error(
            "HANGAR_PREVIEW_ERROR|run=%s|mode=%s|selection=%s|traceback=%s" %
            (run, mode or "NONE", selection, traceback.format_exc().replace("\n", "\\n")))


if unreal is not None:
    main()
