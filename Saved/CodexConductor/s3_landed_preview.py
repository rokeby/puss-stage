"""Temporarily pose the Scene 3 hangar movers at their landed transforms.

UP and DOWN mutate only the three moving actors' relative transforms and never
save.  STATUS is read-only.  Sequence data is read from the asset channels;
this tool never opens, evaluates, scrubs, or plays Sequencer.
"""
import datetime
import json
import math
import os
import traceback

try:
    import unreal
except ImportError:  # The pure-math harness imports this module offline.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
RISE_PATH = "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"
MOVER_LABELS = (
    "S3 Hangar Root",
    "S3 Hangar Roof Hinge",
    "S3 Hangar Lattice Fly",
)
FAR_WALL_LABEL = "S3 Hangar Far Wall"
DOCK_ORIGIN = (10921.973, 160000.0, 0.0)
EXPECTED_FAR_WALL_INNER_X = 6500.0
CHANNEL_AXES = (
    "Location.X", "Location.Y", "Location.Z",
    "Rotation.X", "Rotation.Y", "Rotation.Z",
    "Scale.X", "Scale.Y", "Scale.Z",
)


class PreviewError(RuntimeError):
    pass


def normalize_degrees(value):
    return (float(value) + 180.0) % 360.0 - 180.0


def transform_from_channel_values(baseline, values):
    """Return a plain transform with every canonical channel applied."""
    missing = [name for name in CHANNEL_AXES if name not in values]
    if missing:
        raise PreviewError("missing transform channels: " + ", ".join(missing))
    return {
        "location": [
            float(values["Location.X"]),
            float(values["Location.Y"]),
            float(values["Location.Z"]),
        ],
        "rotation": [
            float(values["Rotation.X"]),
            float(values["Rotation.Y"]),
            float(values["Rotation.Z"]),
        ],
        "scale": [
            float(values["Scale.X"]),
            float(values["Scale.Y"]),
            float(values["Scale.Z"]),
        ],
    }


def transform_errors(got, wanted):
    location = math.sqrt(sum(
        (float(got["location"][index]) - float(wanted["location"][index])) ** 2
        for index in range(3)
    ))
    rotation = max(
        abs(normalize_degrees(
            float(got["rotation"][index]) - float(wanted["rotation"][index])
        ))
        for index in range(3)
    )
    scale = max(
        abs(float(got["scale"][index]) - float(wanted["scale"][index]))
        for index in range(3)
    )
    return {
        "location_cm": location,
        "rotation_deg": rotation,
        "scale": scale,
    }


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


def validate_far_wall_inner_x(inner_x, expected=EXPECTED_FAR_WALL_INNER_X,
                              tolerance=1.0):
    error = abs(float(inner_x) - float(expected))
    if error > tolerance:
        raise PreviewError(
            "far-wall landed inner face mismatch: x=%.6f expected=%.6f error=%.6f" %
            (float(inner_x), float(expected), error)
        )
    return error


def _record_path():
    saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    return os.path.join(saved, "CodexConductor", "s3_landed_preview_record.json")


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
        "location": [
            float(value.translation.x),
            float(value.translation.y),
            float(value.translation.z),
        ],
        "rotation": [
            float(rotation.roll),
            float(rotation.pitch),
            float(rotation.yaw),
        ],
        "scale": [
            float(value.scale3d.x),
            float(value.scale3d.y),
            float(value.scale3d.z),
        ],
    }


def _unreal_transform(value):
    return unreal.Transform(
        location=unreal.Vector(*value["location"]),
        rotation=unreal.Rotator(
            roll=value["rotation"][0],
            pitch=value["rotation"][1],
            yaw=value["rotation"][2],
        ),
        scale=unreal.Vector(*value["scale"]),
    )


def _current_relative_plain(actor):
    parent = actor.get_attach_parent_actor()
    value = (actor.root_component.get_relative_transform()
             if parent else actor.get_actor_transform())
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
        "Location.X": baseline["location"][0],
        "Location.Y": baseline["location"][1],
        "Location.Z": baseline["location"][2],
        "Rotation.X": baseline["rotation"][0],
        "Rotation.Y": baseline["rotation"][1],
        "Rotation.Z": baseline["rotation"][2],
        "Scale.X": baseline["scale"][0],
        "Scale.Y": baseline["scale"][1],
        "Scale.Z": baseline["scale"][2],
    }
    first_values = dict(baseline_values)
    last_values = dict(baseline_values)
    fps = (float(sequence.get_display_rate().numerator) /
           float(sequence.get_display_rate().denominator))
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
            first = keys[0]
            last = keys[-1]
            first_values[name] = float(first.get_value())
            last_values[name] = float(last.get_value())
            source = "first/last key"
            first_frame = _frame_value(first.get_time())
            last_frame = _frame_value(last.get_time())
        elif default_value is not None:
            first_values[name] = default_value
            last_values[name] = default_value
            source = "channel default (no keys)"
            first_frame = None
            last_frame = None
        else:
            source = "current relative/world baseline (no keys or default)"
            first_frame = None
            last_frame = None
        rows.append({
            "property": name,
            "raw_channel": raw_name,
            "source": source,
            "first_frame": first_frame,
            "last_frame": last_frame,
            "first_seconds": (float(first_frame) / fps if first_frame is not None else None),
            "last_seconds": (float(last_frame) / fps if last_frame is not None else None),
            "rest_value": first_values[name],
            "landed_value": last_values[name],
        })
    missing = [name for name in CHANNEL_AXES if name not in seen]
    if missing:
        raise PreviewError(
            "%s transform track is missing channels: %s" %
            (actor.get_actor_label(), ", ".join(missing))
        )
    return {
        "binding": str(binding.get_display_name()),
        "track": str(track.get_display_name()),
        "channels": rows,
        "rest": transform_from_channel_values(baseline, first_values),
        "landed": transform_from_channel_values(baseline, last_values),
    }


def _one_actor(index, label):
    matches = index.get(label, [])
    if len(matches) != 1:
        raise PreviewError(
            "expected exactly one actor labelled %s, found %d" % (label, len(matches))
        )
    return matches[0]


def _actor_index():
    actors = list(unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem).get_all_level_actors())
    index = {}
    for actor in actors:
        index.setdefault(actor.get_actor_label(), []).append(actor)
    return actors, index


def _sequence_plan(index):
    movers = {label: _one_actor(index, label) for label in MOVER_LABELS}
    rise = unreal.load_asset(RISE_PATH)
    if rise is None or not isinstance(rise, unreal.LevelSequence):
        raise PreviewError("LS_S3_HangarRise did not load as a LevelSequence")
    bindings = {}
    for binding in rise.get_bindings():
        if binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack):
            bindings.setdefault(str(binding.get_display_name()), []).append(binding)
    rows = {}
    for label in MOVER_LABELS:
        matches = bindings.get(label, [])
        if len(matches) != 1:
            raise PreviewError(
                "expected exactly one transform binding named %s, found %d" %
                (label, len(matches))
            )
        rows[label] = _read_binding_transform(matches[0], movers[label], rise)
    return movers, rows


def _in_rest_check_scope(label):
    return (
        label in (
            "S3 Hangar Deck", "S3 Hangar Far Wall", "S3 Hangar Left Wall",
            "S3 Hangar Right Wall", "S3 Hangar Roof",
        )
        or label.startswith("S3 Hangar Lattice Beam ")
        or label.startswith("S3 Hangar Lattice Rail ")
        or label.startswith("S3 Strike ")
        or label.startswith("S3 Practical ")
    )


def _rest_composition_check(actors, rows):
    overrides = {label: _unreal_transform(rows[label]["rest"]) for label in MOVER_LABELS}
    cache = {}

    def predicted_world(actor):
        label = actor.get_actor_label()
        if label in cache:
            return cache[label]
        parent = actor.get_attach_parent_actor()
        if label in overrides:
            local_or_world = overrides[label]
        else:
            local_or_world = (actor.root_component.get_relative_transform()
                              if parent else actor.get_actor_transform())
        value = (unreal.MathLibrary.compose_transforms(local_or_world, predicted_world(parent))
                 if parent else local_or_world)
        cache[label] = value
        return value

    errors = []
    for actor in sorted(
            (actor for actor in actors if _in_rest_check_scope(actor.get_actor_label())),
            key=lambda value: value.get_actor_label()):
        got = _plain_transform(actor.get_actor_transform())
        wanted = _plain_transform(predicted_world(actor))
        row = transform_errors(got, wanted)
        row["label"] = actor.get_actor_label()
        errors.append(row)
    return validate_rest_composition(errors)


def _pose_error_rows(movers, wanted):
    result = []
    for label in MOVER_LABELS:
        row = transform_errors(_current_relative_plain(movers[label]), wanted[label])
        row["label"] = label
        result.append(row)
    return result


def _set_relative_transform(actor, value):
    actor.modify()
    actor.set_actor_relative_location(unreal.Vector(*value["location"]), False, True)
    actor.set_actor_relative_rotation(
        unreal.Rotator(
            roll=value["rotation"][0],
            pitch=value["rotation"][1],
            yaw=value["rotation"][2],
        ),
        False,
        True,
    )
    actor.set_actor_relative_scale3d(unreal.Vector(*value["scale"]))


def _box_corners(minimum, maximum):
    return [
        unreal.Vector(x, y, z)
        for x in (minimum.x, maximum.x)
        for y in (minimum.y, maximum.y)
        for z in (minimum.z, maximum.z)
    ]


def _actor_local_bound_points(actor):
    actor_world = actor.get_actor_transform()
    points = []
    for component in actor.get_components_by_class(unreal.StaticMeshComponent):
        mesh = component.get_editor_property("static_mesh")
        if mesh is None:
            continue
        box = mesh.get_bounding_box()
        component_world = unreal.Transform(
            location=component.get_world_location(),
            rotation=component.get_world_rotation(),
            scale=component.get_world_scale(),
        )
        for mesh_point in _box_corners(box.min, box.max):
            world_point = unreal.MathLibrary.transform_location(component_world, mesh_point)
            points.append(unreal.MathLibrary.inverse_transform_location(actor_world, world_point))
    if not points:
        raise PreviewError("S3 Hangar Far Wall has no static-mesh bounds")
    return points


def _far_wall_inner_x(index):
    far_wall = _one_actor(index, FAR_WALL_LABEL)
    world = far_wall.get_actor_transform()
    dock = unreal.Transform(
        location=unreal.Vector(*DOCK_ORIGIN),
        rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0),
    )
    dock_x = []
    for point in _actor_local_bound_points(far_wall):
        world_point = unreal.MathLibrary.transform_location(world, point)
        dock_point = unreal.MathLibrary.inverse_transform_location(dock, world_point)
        dock_x.append(float(dock_point.x))
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


def _run_status(run, movers, rows, record, save_check):
    rest = {label: rows[label]["rest"] for label in MOVER_LABELS}
    landed = {label: rows[label]["landed"] for label in MOVER_LABELS}
    rest_errors = _pose_error_rows(movers, rest)
    landed_errors = _pose_error_rows(movers, landed)
    rest_worst = {
        key: max(float(row[key]) for row in rest_errors)
        for key in ("location_cm", "rotation_deg", "scale")
    }
    landed_worst = {
        key: max(float(row[key]) for row in landed_errors)
        for key in ("location_cm", "rotation_deg", "scale")
    }
    at_rest = (rest_worst["location_cm"] <= 0.01 and
               rest_worst["rotation_deg"] <= 0.001 and
               rest_worst["scale"] <= 0.000001)
    at_landed = (landed_worst["location_cm"] <= 0.01 and
                 landed_worst["rotation_deg"] <= 0.001 and
                 landed_worst["scale"] <= 0.000001)
    if save_check:
        if not os.path.exists(record) and at_rest:
            unreal.log(
                "S3_PREVIEW_SAFE_TO_SAVE|run=%s|max_err_cm=%.9f|max_err_deg=%.9f" %
                (run, rest_worst["location_cm"], rest_worst["rotation_deg"])
            )
        else:
            unreal.log_warning(
                "S3_PREVIEW_UP_DO_NOT_SAVE|run=%s|record=%s|at_rest=%s|max_err_cm=%.9f" %
                (run, str(os.path.exists(record)).lower(), str(at_rest).lower(),
                 rest_worst["location_cm"])
            )
        return
    pose = "REST" if at_rest else ("LANDED" if at_landed else "OTHER")
    unreal.log(
        "S3_PREVIEW|run=%s|status|up=%s|pose=%s|record=%s|rest_err_cm=%.9f|landed_err_cm=%.9f" %
        (run, str(os.path.exists(record)).lower(), pose,
         str(os.path.exists(record)).lower(), rest_worst["location_cm"],
         landed_worst["location_cm"])
    )


def _run_up(run, actors, index, movers, rows, record):
    if os.path.exists(record):
        raise PreviewError("UP record already exists: " + record)
    rest_check = _rest_composition_check(actors, rows)
    sequence_rest = {label: rows[label]["rest"] for label in MOVER_LABELS}
    rest_pose_errors = _pose_error_rows(movers, sequence_rest)
    validate_pose_errors(rest_pose_errors)
    actual_rest = {label: _current_relative_plain(movers[label]) for label in MOVER_LABELS}
    landed = {label: rows[label]["landed"] for label in MOVER_LABELS}
    value = {
        "run": run,
        "written": datetime.datetime.now().isoformat(timespec="seconds"),
        "world": EXPECTED_WORLD,
        "rise_asset": RISE_PATH,
        "rest_transforms": actual_rest,
        "sequence_rest_transforms": sequence_rest,
        "landed_transforms": landed,
        "binding_channels": {label: rows[label]["channels"] for label in MOVER_LABELS},
        "rest_pose_check": rest_check,
    }
    _write_record(value, record)
    for label in MOVER_LABELS:
        _set_relative_transform(movers[label], landed[label])
    readback = validate_pose_errors(_pose_error_rows(movers, landed))
    far_wall_x = _far_wall_inner_x(index)
    far_wall_error = validate_far_wall_inner_x(far_wall_x)
    unreal.log(
        "S3_PREVIEW_UP_DONE|run=%s|record=%s|max_err_cm=%.9f|far_wall_inner_x=%.6f|far_wall_err_cm=%.6f|rest_err_cm=%.9f" %
        (run, os.path.basename(record), readback["location_cm"], far_wall_x,
         far_wall_error, rest_check["max_location_error_cm"])
    )


def _run_down(run, actors, movers, rows, record):
    if not os.path.exists(record):
        raise PreviewError("DOWN record does not exist: " + record)
    value = _load_record(record)
    if value.get("world") != EXPECTED_WORLD:
        raise PreviewError("record world mismatch")
    rest = value.get("rest_transforms")
    if not isinstance(rest, dict) or sorted(rest) != sorted(MOVER_LABELS):
        raise PreviewError("record mover set mismatch")
    for label in MOVER_LABELS:
        _set_relative_transform(movers[label], rest[label])
    readback = validate_pose_errors(_pose_error_rows(movers, rest))
    rest_check = _rest_composition_check(actors, rows)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    archived = record + ".done-" + stamp
    if os.path.exists(archived):
        raise PreviewError("record archive already exists: " + archived)
    os.rename(record, archived)
    unreal.log(
        "S3_PREVIEW_DOWN_DONE|run=%s|max_err_cm=%.9f|max_err_deg=%.9f|record=%s|rest_err_cm=%.9f" %
        (run, readback["location_cm"], readback["rotation_deg"],
         os.path.basename(archived), rest_check["max_location_error_cm"])
    )


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    mode = str(globals().get("S3_LANDED_PREVIEW_MODE", "")).upper()
    save_check = bool(globals().get("S3_LANDED_PREVIEW_SAVE_CHECK"))
    try:
        if mode not in ("STATUS", "UP", "DOWN"):
            raise PreviewError("mode must be STATUS, UP, or DOWN")
        if save_check and mode != "STATUS":
            raise PreviewError("save check requires STATUS mode")
        _assert_context()
        actors, index = _actor_index()
        movers, rows = _sequence_plan(index)
        record = _record_path()
        if mode == "STATUS":
            _run_status(run, movers, rows, record, save_check)
        elif mode == "UP":
            _run_up(run, actors, index, movers, rows, record)
        else:
            _run_down(run, actors, movers, rows, record)
    except Exception:
        unreal.log_error(
            "S3_PREVIEW_ERROR|run=%s|mode=%s|traceback=%s" %
            (run, mode or "NONE", traceback.format_exc().replace("\n", "\\n"))
        )


if unreal is not None:
    main()
