"""Plan, apply, or revert the Scene 3 alternating wave slides.

Dry run is the default when Unreal executes this file.  Apply/revert are selected
only through S3_WAVE_SLIDES_APPLY / S3_WAVE_SLIDES_REVERT globals.  The planner
and strike-record reader remain importable by test_s3_wave_slides_plan.py in
plain Python; importing the module offline never contacts Unreal.

The authored transform tracks live on the six wave actors in
LS_DevScene_03.  Their keys are actor-relative because every target is attached
to S3 Hangar Root.  The root's landed transform is used only to prove that each
relative key changes dock Y and nothing else; the root itself is never keyed or
modified.
"""
import datetime
import json
import math
import os
import re
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline planning harness.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ROOT_PATH = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
RISE_PATH = "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"
ROOT_LABEL = "S3 Hangar Root"
TRACK_NAME = "S3.WaveSlide"
EXPECTED_FPS = 24.0
EXPECTED_PLAYBACK = (0, 6240)
AMPLITUDE_CM = 100.0
PERIOD_FRAMES = 360
KEY_STEP_FRAMES = 3
ROW_DIRECTIONS = (1, -1, 1)
ROW_DELAYS = (0, 24, 48)
VAMP_RANGE = (3480, 4200)
WALL_Y_LIMIT_CM = 1000.0
SEAM_TOLERANCE_CM = 0.01
INTERPOLATION_TOLERANCE_CM = 0.1
COMPOSITION_TOLERANCE_CM = 0.01
ROTATION_TOLERANCE_DEG = 0.01
DOCK_ORIGIN = (10921.973, 160000.0, 0.0)
DOCK_YAW_DEG = 0.0
TARGET_LABELS = tuple(
    "S3 Wave Row%d %s" % (row, half)
    for row in (1, 2, 3)
    for half in ("A", "B")
)
CHANNEL_AXES = (
    "Location.X", "Location.Y", "Location.Z",
    "Rotation.X", "Rotation.Y", "Rotation.Z",
    "Scale.X", "Scale.Y", "Scale.Z",
)
POSE_AXES = CHANNEL_AXES[:6]

if unreal is not None:
    HERE = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexConductor",
    )
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
RECORD = os.path.join(HERE, "s3_wave_slides_record.json")


class PlanError(ValueError):
    pass


def project_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def strike_record_candidates():
    """Return the declared location first, then the measured current location."""
    return (
        os.path.join(HERE, "s3_strike_record.json"),
        os.path.join(os.path.dirname(HERE), "CodexStructure", "s3_strike_record.json"),
    )


def read_strike_frame(target_fps=EXPECTED_FPS, candidates=None):
    """Read the applied strike record and convert its seconds to a target frame.

    The strike was authored before Scene 3's 24 fps timeline pass, so its record
    carries seconds plus its then-current 30 fps display rate.  Seconds are the
    stable authority.  At 24 fps 6.133333... s is frame 147.2; the nearest
    display frame is 147 (8.333 ms early).  Refuse a half-frame ambiguity.
    """
    paths = tuple(candidates or strike_record_candidates())
    path = next((value for value in paths if os.path.isfile(value)), None)
    if path is None:
        raise PlanError("strike record not found: " + ", ".join(paths))
    try:
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle)
        strike_s = float(record["STRIKE_S"])
        source_fps = float(record["fps"])
    except Exception as exc:
        raise PlanError("strike record unreadable: %s: %s" % (path, exc))
    if not math.isfinite(strike_s) or strike_s < 0.0 or source_fps <= 0.0:
        raise PlanError("strike record timing is invalid: " + path)

    uplights = record.get("uplight_keys")
    if not isinstance(uplights, dict) or not uplights:
        raise PlanError("strike record has no uplight key evidence: " + path)
    starts = []
    for label, keys in uplights.items():
        if not isinstance(keys, list) or len(keys) < 3:
            raise PlanError("strike uplight keys are incomplete: " + str(label))
        ramp_starts = [float(keys[index][0]) for index in range(len(keys) - 1)
                       if float(keys[index][1]) == 0.0 and float(keys[index + 1][1]) > 0.0]
        if len(ramp_starts) != 1:
            raise PlanError("strike uplight ramp is ambiguous: " + str(label))
        starts.append(ramp_starts[0])
    if abs(min(starts) - strike_s) > 1.0e-6:
        raise PlanError("STRIKE_S disagrees with earliest uplight ramp")

    raw_frame = strike_s * float(target_fps)
    frame = int(round(raw_frame))
    rounding_error = abs(raw_frame - frame)
    if rounding_error >= 0.5 - 1.0e-9:
        raise PlanError("strike time is ambiguous at target display rate")
    try:
        source = os.path.relpath(path, project_root()).replace("\\", "/")
    except ValueError:
        source = path.replace("\\", "/")
    return {
        "frame": frame,
        "seconds": strike_s,
        "target_fps": float(target_fps),
        "raw_target_frame": raw_frame,
        "rounding_error_frames": rounding_error,
        "rounding_error_ms": 1000.0 * rounding_error / float(target_fps),
        "source_fps": source_fps,
        "source": source,
        "source_run": str(record.get("run", "")),
        "source_written": str(record.get("written", "")),
    }


def wave_offset(frame, strike_frame, row, period=PERIOD_FRAMES,
                directions=ROW_DIRECTIONS, delays=ROW_DELAYS):
    row_index = int(row) - 1
    elapsed = max(0, int(frame) - int(strike_frame) - int(delays[row_index]))
    return (float(directions[row_index]) * AMPLITUDE_CM *
            math.sin(2.0 * math.pi * elapsed / float(period)))


def linear_interpolation_error_bound(period, step=KEY_STEP_FRAMES):
    """Standard max |f''| h^2 / 8 bound for linear sine interpolation."""
    angular_rate = 2.0 * math.pi / float(period)
    return AMPLITUDE_CM * angular_rate * angular_rate * float(step) ** 2 / 8.0


def _expected_actor_rows(state):
    rows = list(state.get("actors", []))
    counts = {label: 0 for label in TARGET_LABELS}
    by_label = {}
    for row in rows:
        label = str(row.get("label", ""))
        if label in counts:
            counts[label] += 1
            by_label[label] = row
    bad = {label: count for label, count in counts.items() if count != 1}
    extras = sorted(str(row.get("label", "")) for row in rows
                    if str(row.get("label", "")) not in counts)
    if bad or extras or len(rows) != 6:
        raise PlanError("wave actors are not exactly the six expected labels: bad=%s extras=%s" %
                        (json.dumps(bad, sort_keys=True), json.dumps(extras)))
    return [by_label[label] for label in TARGET_LABELS]


def plan_wave_slides(state):
    """Return the deterministic wave plan from an Unreal-free state dict."""
    fps = float(state["fps"])
    playback = [int(value) for value in state["playback"]]
    strike = dict(state["strike"])
    strike_frame = int(strike["frame"])
    period = int(state.get("period_frames", PERIOD_FRAMES))
    directions = tuple(int(value) for value in state.get("directions", ROW_DIRECTIONS))
    delays = tuple(int(value) for value in state.get("delays", ROW_DELAYS))

    if abs(fps - EXPECTED_FPS) > 0.0001:
        raise PlanError("root display rate is not 24 fps")
    if playback != list(EXPECTED_PLAYBACK):
        raise PlanError("unexpected Scene 3 playback range")
    if period <= 0:
        raise PlanError("period must be positive")
    if directions != ROW_DIRECTIONS:
        raise PlanError("row directions must be (+1,-1,+1)")
    if delays != ROW_DELAYS:
        raise PlanError("row delays must be (0,24,48)")
    if not playback[0] < strike_frame < playback[1]:
        raise PlanError("strike frame is outside Scene 3")
    if (playback[1] - strike_frame) % KEY_STEP_FRAMES:
        raise PlanError("3-frame cadence does not land on the Scene end")

    actors = _expected_actor_rows(state)
    for actor in actors:
        if str(actor.get("parent_label")) != ROOT_LABEL:
            raise PlanError(str(actor["label"]) + " is not attached to " + ROOT_LABEL)
        if int(actor.get("binding_count", 0)) > 1:
            raise PlanError(str(actor["label"]) + " resolves through multiple root bindings")
        if int(actor.get("transform_track_count", 0)) != 0:
            raise PlanError(str(actor["label"]) + " already has a transform track")

    key_frames = [strike_frame - 1] + list(
        range(strike_frame, playback[1] + 1, KEY_STEP_FRAMES))
    if key_frames[-1] != playback[1]:
        raise PlanError("last wave key is not the Scene end")
    interpolation_error = linear_interpolation_error_bound(period)
    if interpolation_error > INTERPOLATION_TOLERANCE_CM:
        raise PlanError("linear interpolation error exceeds 0.1 cm")

    row_plans = []
    for row in (1, 2, 3):
        keys = [[frame, wave_offset(frame, strike_frame, row, period, directions, delays)]
                for frame in key_frames]
        if abs(keys[0][1]) > 1.0e-9 or abs(keys[1][1]) > 1.0e-9:
            raise PlanError("pre-strike hold is not the placed pose")
        seam_first = wave_offset(VAMP_RANGE[0], strike_frame, row, period, directions, delays)
        seam_last = wave_offset(VAMP_RANGE[1], strike_frame, row, period, directions, delays)
        seam_error = abs(seam_last - seam_first)
        if seam_error > SEAM_TOLERANCE_CM:
            raise PlanError("vamp seam unequal for row %d: %.6f cm" % (row, seam_error))
        row_plans.append({
            "row": row,
            "direction": directions[row - 1],
            "delay_frames": delays[row - 1],
            "first_key": key_frames[0],
            "last_key": key_frames[-1],
            "key_count": len(key_frames),
            "keys": keys,
            "seam": {
                "frames": list(VAMP_RANGE),
                "first_cm": seam_first,
                "last_cm": seam_last,
                "error_cm": seam_error,
            },
        })

    clearance = []
    for actor in actors:
        bounds = actor.get("landed_dock_y_bounds_cm")
        if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
            raise PlanError(str(actor["label"]) + " has no landed dock-Y bounds")
        moved = [float(bounds[0]) - AMPLITUDE_CM, float(bounds[1]) + AMPLITUDE_CM]
        overhang = [max(0.0, -WALL_Y_LIMIT_CM - moved[0]),
                    max(0.0, moved[1] - WALL_Y_LIMIT_CM)]
        clearance.append({
            "label": str(actor["label"]),
            "placed_y_bounds_cm": [float(bounds[0]), float(bounds[1])],
            "swept_y_bounds_cm": moved,
            "within_walls": max(overhang) <= 1.0e-6,
            "overhang_negative_y_cm": overhang[0],
            "overhang_positive_y_cm": overhang[1],
        })

    return {
        "asset": ROOT_PATH,
        "fps": fps,
        "playback": playback,
        "strike": strike,
        "period_frames": period,
        "amplitude_cm": AMPLITUDE_CM,
        "key_step_frames": KEY_STEP_FRAMES,
        "linear_interpolation_error_bound_cm": interpolation_error,
        "rows": row_plans,
        "actors": [{
            "label": str(actor["label"]),
            "row": int(re.match(r"S3 Wave Row([123]) [AB]$", str(actor["label"])).group(1)),
            "binding_action": "reuse" if int(actor.get("binding_count", 0)) == 1 else "add",
            "actor_path": str(actor.get("actor_path", "")),
        } for actor in actors],
        "clearance": clearance,
        "all_within_walls": all(row["within_walls"] for row in clearance),
    }


def _package_path(value):
    name = str(value.get_name())
    return name if name.startswith("/") else "/" + name


def package_census():
    return {
        "maps": sorted(_package_path(value) for value in
                       unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
        "content": sorted(_package_path(value) for value in
                          unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    }


def stop(run, reason):
    unreal.log_error("S3_WAVE_SLIDES_STOPPED|run=%s|%s" % (run, reason))
    raise RuntimeError(reason)


def _modify(value):
    method = getattr(value, "modify", None)
    if method is not None:
        method()


def guid_text(value):
    return str(unreal.GuidLibrary.conv_guid_to_string(value))


def object_path(value):
    return str(value.get_path_name())


def frame_value(value):
    if hasattr(value, "frame_number"):
        return int(value.frame_number.value)
    if hasattr(value, "value"):
        return int(value.value)
    return int(value)


def canonical_channel_name(channel):
    try:
        name = str(channel.get_name())
    except Exception:
        name = str(channel.get_editor_property("channel_name"))
    name = re.sub(r"_\d+$", "", name)
    return name if name in CHANNEL_AXES else None


def _plain_transform(value):
    rotation = value.rotation.rotator()
    return {
        "location": [float(value.translation.x), float(value.translation.y), float(value.translation.z)],
        "rotation_rpy": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
        "scale": [float(value.scale3d.x), float(value.scale3d.y), float(value.scale3d.z)],
    }


def _unreal_transform(row):
    return unreal.Transform(
        location=unreal.Vector(*row["location"]),
        rotation=unreal.Rotator(roll=row["rotation_rpy"][0],
                                pitch=row["rotation_rpy"][1],
                                yaw=row["rotation_rpy"][2]),
        scale=unreal.Vector(*row.get("scale", [1.0, 1.0, 1.0])),
    )


def _distance(left, right):
    return math.sqrt(sum((float(left[index]) - float(right[index])) ** 2 for index in range(3)))


def _rotation_error(left, right):
    def quaternion(rotation):
        roll, pitch, yaw = (math.radians(float(value)) * 0.5 for value in rotation)
        sr, cr = math.sin(roll), math.cos(roll)
        sp, cp = math.sin(pitch), math.cos(pitch)
        sy, cy = math.sin(yaw), math.cos(yaw)
        return (
            cr * cp * cy + sr * sp * sy,
            sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy,
        )
    q1, q2 = quaternion(left), quaternion(right)
    dot = abs(sum(q1[index] * q2[index] for index in range(4)))
    return math.degrees(2.0 * math.acos(max(-1.0, min(1.0, dot))))


def _dock_transform():
    return unreal.Transform(
        location=unreal.Vector(*DOCK_ORIGIN),
        rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=DOCK_YAW_DEG),
    )


def _binding_is_root(binding):
    try:
        parent = binding.get_parent()
        return parent is None or not parent.is_valid()
    except Exception:
        return True


def bindings_for_actor(sequence, actor, world, run):
    found = []
    wanted = object_path(actor)
    for binding in sequence.get_bindings():
        if not _binding_is_root(binding):
            continue
        try:
            resolved = [object_path(value) for value in sequence.locate_bound_objects(binding, world)]
        except Exception as exc:
            stop(run, "reason=BINDING_RESOLUTION_FAILED|detail=" + str(exc))
        if wanted in resolved:
            if resolved != [wanted]:
                stop(run, "reason=BINDING_NOT_ONE_TO_ONE|actor=%s|resolved=%s" %
                     (wanted, json.dumps(resolved)))
            found.append(binding)
    return found


def _actor_index(world):
    rows = {}
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        rows.setdefault(str(actor.get_actor_label()), []).append(actor)
    return rows


def _one_actor(index, label, run):
    found = index.get(label, [])
    if len(found) != 1:
        stop(run, "reason=ACTOR_COUNT|label=%s|count=%d" % (label, len(found)))
    return found[0]


def _transform_values(value, baseline):
    result = dict(baseline)
    plain = _plain_transform(value)
    result.update({
        "Location.X": plain["location"][0], "Location.Y": plain["location"][1],
        "Location.Z": plain["location"][2], "Rotation.X": plain["rotation_rpy"][0],
        "Rotation.Y": plain["rotation_rpy"][1], "Rotation.Z": plain["rotation_rpy"][2],
        "Scale.X": plain["scale"][0], "Scale.Y": plain["scale"][1],
        "Scale.Z": plain["scale"][2],
    })
    return result


def _make_transform(values):
    return unreal.Transform(
        location=unreal.Vector(values["Location.X"], values["Location.Y"], values["Location.Z"]),
        rotation=unreal.Rotator(roll=values["Rotation.X"], pitch=values["Rotation.Y"],
                                yaw=values["Rotation.Z"]),
        scale=unreal.Vector(values["Scale.X"], values["Scale.Y"], values["Scale.Z"]),
    )


def root_rest_landed(rise, root, run):
    bindings = [binding for binding in rise.get_bindings()
                if str(binding.get_display_name()) == ROOT_LABEL and
                binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack)]
    if len(bindings) != 1:
        stop(run, "reason=ROOT_RISE_BINDING_COUNT|count=%d" % len(bindings))
    tracks = list(bindings[0].find_tracks_by_type(unreal.MovieScene3DTransformTrack))
    if len(tracks) != 1 or len(tracks[0].get_sections()) != 1:
        stop(run, "reason=ROOT_RISE_TRACK_SHAPE")
    baseline_transform = root.get_actor_transform()
    baseline = _transform_values(baseline_transform, {})
    first, last = dict(baseline), dict(baseline)
    for channel in tracks[0].get_sections()[0].get_all_channels():
        name = canonical_channel_name(channel)
        if name is None:
            continue
        keys = sorted(channel.get_keys(), key=lambda key: frame_value(key.get_time()))
        if keys:
            first[name], last[name] = float(keys[0].get_value()), float(keys[-1].get_value())
        else:
            try:
                if channel.has_default():
                    first[name] = last[name] = float(channel.get_default())
            except Exception:
                pass
    return _make_transform(first), _make_transform(last)


def _bounds_points(minimum, maximum):
    return [unreal.Vector(x, y, z) for x in (minimum.x, maximum.x)
            for y in (minimum.y, maximum.y) for z in (minimum.z, maximum.z)]


def landed_dock_y_bounds(actor, relative, root_landed, dock, run):
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    mesh = component.get_editor_property("static_mesh") if component else None
    if mesh is None:
        stop(run, "reason=WAVE_STATIC_MESH_MISSING|label=" + actor.get_actor_label())
    world = unreal.MathLibrary.compose_transforms(relative, root_landed)
    ys = []
    bounds = mesh.get_bounding_box()
    for point in _bounds_points(bounds.min, bounds.max):
        world_point = unreal.MathLibrary.transform_location(world, point)
        dock_point = unreal.MathLibrary.inverse_transform_location(dock, world_point)
        ys.append(float(dock_point.y))
    return [min(ys), max(ys)]


def live_state(sequence, rise, world, run):
    rate = sequence.get_display_rate()
    fps = float(rate.numerator) / float(rate.denominator)
    strike = read_strike_frame(fps)
    index = _actor_index(world)
    root = _one_actor(index, ROOT_LABEL, run)
    _, landed = root_rest_landed(rise, root, run)
    dock = _dock_transform()
    actors = []
    runtime = {}
    for label in TARGET_LABELS:
        actor = _one_actor(index, label, run)
        parent = actor.get_attach_parent_actor()
        if parent is None or str(parent.get_actor_label()) != ROOT_LABEL:
            stop(run, "reason=WAVE_PARENT|label=" + label)
        relative = actor.get_editor_property("root_component").get_relative_transform()
        bindings = bindings_for_actor(sequence, actor, world, run)
        if len(bindings) > 1:
            stop(run, "reason=WAVE_BINDING_COUNT|label=%s|count=%d" % (label, len(bindings)))
        tracks = (list(bindings[0].find_tracks_by_type(unreal.MovieScene3DTransformTrack))
                  if bindings else [])
        plain = _plain_transform(relative)
        row = {
            "label": label,
            "actor_path": object_path(actor),
            "parent_label": ROOT_LABEL,
            "binding_count": len(bindings),
            "binding_guid": guid_text(bindings[0].get_id()) if bindings else None,
            "transform_track_count": len(tracks),
            "placed_relative": plain,
            "landed_dock_y_bounds_cm": landed_dock_y_bounds(actor, relative, landed, dock, run),
        }
        actors.append(row)
        runtime[label] = {"actor": actor, "binding": bindings[0] if bindings else None,
                          "relative": relative}
    return ({
        "fps": fps,
        "playback": [int(sequence.get_playback_start()), int(sequence.get_playback_end())],
        "strike": strike,
        "actors": actors,
    }, runtime, landed, dock)


def track_space_rows(actor_row, row_plan, root_landed, dock, run):
    baseline = _unreal_transform(actor_row["placed_relative"])
    base_world = unreal.MathLibrary.compose_transforms(baseline, root_landed)
    base_plain = _plain_transform(base_world)
    base_dock_location = unreal.MathLibrary.inverse_transform_location(
        dock, unreal.Vector(*base_plain["location"]))
    rows = []
    for frame, offset in row_plan["keys"]:
        wanted_dock_location = unreal.Vector(base_dock_location.x,
                                             base_dock_location.y + float(offset),
                                             base_dock_location.z)
        wanted_world_location = unreal.MathLibrary.transform_location(dock, wanted_dock_location)
        wanted_world = unreal.Transform(
            location=wanted_world_location,
            rotation=base_world.rotation.rotator(),
            scale=base_world.scale3d,
        )
        local = unreal.MathLibrary.make_relative_transform(wanted_world, root_landed)
        composed = unreal.MathLibrary.compose_transforms(local, root_landed)
        composed_plain = _plain_transform(composed)
        composed_dock = unreal.MathLibrary.inverse_transform_location(
            dock, unreal.Vector(*composed_plain["location"]))
        delta = [float(composed_dock.x - base_dock_location.x),
                 float(composed_dock.y - base_dock_location.y),
                 float(composed_dock.z - base_dock_location.z)]
        if (abs(delta[0]) > COMPOSITION_TOLERANCE_CM or
                abs(delta[2]) > COMPOSITION_TOLERANCE_CM or
                abs(delta[1] - float(offset)) > COMPOSITION_TOLERANCE_CM or
                _rotation_error(composed_plain["rotation_rpy"],
                                base_plain["rotation_rpy"]) > ROTATION_TOLERANCE_DEG):
            stop(run, "reason=LANDED_COMPOSITION|label=%s|frame=%d|delta=%s" %
                 (actor_row["label"], frame, json.dumps(delta)))
        plain = _plain_transform(local)
        if _rotation_error(plain["rotation_rpy"],
                           actor_row["placed_relative"]["rotation_rpy"]) > ROTATION_TOLERANCE_DEG:
            stop(run, "reason=RELATIVE_ROTATION_CHANGED|label=%s|frame=%d" %
                 (actor_row["label"], frame))
        rows.append({"frame": int(frame), "offset_cm": float(offset), **plain})
    return rows


def add_transform_track(binding, rows, run):
    _modify(binding)
    track = binding.add_track(unreal.MovieScene3DTransformTrack)
    if track is None:
        stop(run, "reason=ADD_TRANSFORM_TRACK_FAILED")
    _modify(track)
    track.set_display_name(TRACK_NAME)
    section = track.add_section()
    if section is None:
        stop(run, "reason=ADD_TRANSFORM_SECTION_FAILED")
    _modify(section)
    section.set_range(rows[0]["frame"], rows[-1]["frame"] + 1)
    channels = {}
    for channel in section.get_all_channels():
        name = canonical_channel_name(channel)
        if name:
            if name in channels:
                stop(run, "reason=DUPLICATE_CHANNEL|name=" + name)
            channels[name] = channel
    missing = sorted(set(CHANNEL_AXES) - set(channels))
    if missing:
        stop(run, "reason=MISSING_CHANNELS|names=" + ",".join(missing))
    for name, value in zip(CHANNEL_AXES[6:], rows[0]["scale"]):
        _modify(channels[name])
        channels[name].set_default(float(value))
    linear = unreal.MovieSceneKeyInterpolation.LINEAR
    for row in rows:
        values = {
            "Location.X": row["location"][0], "Location.Y": row["location"][1],
            "Location.Z": row["location"][2], "Rotation.X": row["rotation_rpy"][0],
            "Rotation.Y": row["rotation_rpy"][1], "Rotation.Z": row["rotation_rpy"][2],
        }
        for name in POSE_AXES:
            _modify(channels[name])
            made = channels[name].add_key(
                unreal.FrameNumber(int(row["frame"])), float(values[name]),
                time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                interpolation=linear,
            )
            if made is None:
                stop(run, "reason=ADD_KEY_FAILED|channel=%s|frame=%d" %
                     (name, row["frame"]))
    return track


def transform_readback(binding, expected, run):
    tracks = list(binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack))
    if len(tracks) != 1 or str(tracks[0].get_display_name()) != TRACK_NAME:
        stop(run, "reason=TRANSFORM_TRACK_READBACK")
    sections = list(tracks[0].get_sections())
    if len(sections) != 1:
        stop(run, "reason=TRANSFORM_SECTION_COUNT")
    channels = {canonical_channel_name(channel): channel for channel in sections[0].get_all_channels()
                if canonical_channel_name(channel)}
    wanted_frames = [row["frame"] for row in expected]
    summary = {}
    for name in POSE_AXES:
        keys = list(channels[name].get_keys())
        frames = [frame_value(key.get_time()) for key in keys]
        if frames != wanted_frames:
            stop(run, "reason=KEY_FRAME_READBACK|channel=" + name)
        wanted_values = []
        axis = {"X": 0, "Y": 1, "Z": 2}[name[-1]]
        field = "location" if name.startswith("Location") else "rotation_rpy"
        wanted_values = [float(row[field][axis]) for row in expected]
        got_values = [float(key.get_value()) for key in keys]
        if any(abs(left - right) > 0.001 for left, right in zip(got_values, wanted_values)):
            stop(run, "reason=KEY_VALUE_READBACK|channel=" + name)
        summary[name] = {"count": len(keys),
                         "first": [frames[0], got_values[0]],
                         "last": [frames[-1], got_values[-1]]}
    return summary


def _asset_filename(project, package, extension):
    return os.path.join(project, "Content", *package[len("/Game/"):].split("/")) + extension


def backup_assets(project, include_level, stamp, run):
    backup = os.path.join(project, "Backups", "PreS3WaveSlides-" + stamp.strftime("%Y%m%d-%H%M%S"))
    if os.path.exists(backup):
        stop(run, "reason=BACKUP_EXISTS|path=" + backup)
    sources = [_asset_filename(project, ROOT_PATH, ".uasset")]
    if include_level:
        sources.append(_asset_filename(project, EXPECTED_WORLD, ".umap"))
    missing = [path for path in sources if not os.path.isfile(path)]
    if missing:
        stop(run, "reason=BACKUP_SOURCE_MISSING|files=" + json.dumps(missing))
    os.makedirs(backup)
    copied = []
    content = os.path.join(project, "Content")
    for source in sources:
        relative = os.path.relpath(source, content)
        destination = os.path.join(backup, "Content", relative)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)
        if os.path.getsize(source) != os.path.getsize(destination):
            stop(run, "reason=BACKUP_SIZE_MISMATCH|file=" + source)
        copied.append(relative.replace("\\", "/"))
    return backup, copied


def write_record(record, mode, run):
    try:
        with open(RECORD, mode, encoding="utf-8") as handle:
            json.dump(record, handle, indent=1, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception as exc:
        stop(run, "reason=RECORD_WRITE_FAILED|detail=" + str(exc))


def read_record(run):
    try:
        with open(RECORD, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        stop(run, "reason=RECORD_READ_FAILED|detail=" + str(exc))


def _allowed_dirty(run):
    census = package_census()
    if census["content"] != [ROOT_PATH] or any(path != EXPECTED_WORLD for path in census["maps"]):
        stop(run, "reason=DIRTY_CENSUS|census=" + json.dumps(census, sort_keys=True))
    return census


def _save_sequence_only(run):
    if not unreal.EditorAssetLibrary.save_asset(ROOT_PATH, only_if_is_dirty=False):
        stop(run, "reason=SEQUENCE_SAVE_FAILED")
    census = package_census()
    if census["content"] or any(path != EXPECTED_WORLD for path in census["maps"]):
        stop(run, "reason=POST_SAVE_CENSUS|census=" + json.dumps(census, sort_keys=True))
    return census


def apply_plan(sequence, world, state, runtime, plan, root_landed, dock, run):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    stamp = datetime.datetime.now()
    include_level = any(row["binding_action"] == "add" for row in plan["actors"])
    backup, copied = backup_assets(project, include_level, stamp, run)
    record = {
        "written": stamp.isoformat(timespec="seconds"), "run": run,
        "world": EXPECTED_WORLD, "asset": ROOT_PATH,
        "backup": backup, "backup_files": copied,
        "plan_summary": {
            "strike": plan["strike"], "period_frames": plan["period_frames"],
            "amplitude_cm": plan["amplitude_cm"], "key_step_frames": plan["key_step_frames"],
            "linear_interpolation_error_bound_cm": plan["linear_interpolation_error_bound_cm"],
            "rows": [{key: row[key] for key in
                      ("row", "direction", "delay_frames", "first_key", "last_key",
                       "key_count", "seam")} for row in plan["rows"]],
            "clearance": plan["clearance"], "all_within_walls": plan["all_within_walls"],
        },
        "targets": [],
    }
    write_record(record, "x", run)
    row_plans = {row["row"]: row for row in plan["rows"]}
    state_by_label = {row["label"]: row for row in state["actors"]}
    for target in plan["actors"]:
        label = target["label"]
        live = runtime[label]
        binding = live["binding"]
        created = binding is None
        if created:
            _modify(sequence)
            binding = sequence.add_possessable(live["actor"])
        if binding is None or not binding.is_valid():
            stop(run, "reason=ADD_OR_REUSE_BINDING_FAILED|label=" + label)
        if binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack):
            stop(run, "reason=TRANSFORM_TRACK_APPEARED|label=" + label)
        expected = track_space_rows(state_by_label[label], row_plans[target["row"]],
                                    root_landed, dock, run)
        add_transform_track(binding, expected, run)
        readback = transform_readback(binding, expected, run)
        resolved = [object_path(value) for value in sequence.locate_bound_objects(binding, world)]
        if resolved != [target["actor_path"]]:
            stop(run, "reason=BINDING_READBACK|label=%s|resolved=%s" %
                 (label, json.dumps(resolved)))
        record["targets"].append({
            "label": label, "actor_path": target["actor_path"], "row": target["row"],
            "binding_guid": guid_text(binding.get_id()), "binding_created": created,
            "track_name": TRACK_NAME, "readback": readback,
        })
        write_record(record, "w", run)
    if len(record["targets"]) != 6:
        stop(run, "reason=TARGET_COUNT_AFTER_APPLY")
    dirty = _allowed_dirty(run)
    census = _save_sequence_only(run)
    record["applied"] = True
    record["dirty_before_save"] = dirty
    record["post_save_census"] = census
    record["required_tests"] = [
        "InfinityStage.Editor.SavedMasterMatchesShow",
        "InfinityStage.Editor.SceneCutBindingsResolve",
    ]
    write_record(record, "w", run)
    unreal.log("S3_WAVE_SLIDES_DONE|run=%s|applied|backup=%s|targets=6|census=%s|tests_required_singly=%s" %
               (run, backup, json.dumps(census, separators=(",", ":"), sort_keys=True),
                ",".join(record["required_tests"])))


def _binding_by_guid(sequence, identity):
    found = [binding for binding in sequence.get_bindings()
             if guid_text(binding.get_id()) == identity]
    return found[0] if len(found) == 1 else None


def revert(sequence, world, run):
    record = read_record(run)
    if (record.get("world") != EXPECTED_WORLD or record.get("asset") != ROOT_PATH or
            not record.get("applied") or len(record.get("targets", [])) != 6):
        stop(run, "reason=REVERT_RECORD_CONTEXT")
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    stamp = datetime.datetime.now()
    include_level = any(row.get("binding_created") for row in record["targets"])
    backup, _ = backup_assets(project, include_level, stamp, run)
    for row in record["targets"]:
        binding = _binding_by_guid(sequence, row["binding_guid"])
        if binding is None:
            stop(run, "reason=REVERT_BINDING_ABSENT|label=" + row["label"])
        resolved = [object_path(value) for value in sequence.locate_bound_objects(binding, world)]
        if resolved != [row["actor_path"]]:
            stop(run, "reason=REVERT_BINDING_CHANGED|label=" + row["label"])
        tracks = list(binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack))
        if len(tracks) != 1 or str(tracks[0].get_display_name()) != TRACK_NAME:
            stop(run, "reason=REVERT_TRACK_CHANGED|label=" + row["label"])
        _modify(sequence)
        _modify(binding)
        if row["binding_created"]:
            binding.remove()
        elif not binding.remove_track(tracks[0]):
            stop(run, "reason=REMOVE_TRACK_FAILED|label=" + row["label"])
    for row in record["targets"]:
        binding = _binding_by_guid(sequence, row["binding_guid"])
        if row["binding_created"] and binding is not None:
            stop(run, "reason=REVERT_CREATED_BINDING_REMAINS|label=" + row["label"])
        if not row["binding_created"]:
            if binding is None or binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack):
                stop(run, "reason=REVERT_REUSED_BINDING_MISMATCH|label=" + row["label"])
    dirty = _allowed_dirty(run)
    census = _save_sequence_only(run)
    archived = RECORD + ".reverted-" + stamp.strftime("%Y%m%d-%H%M%S")
    os.rename(RECORD, archived)
    unreal.log("S3_WAVE_SLIDES_DONE|run=%s|reverted|backup=%s|record=%s|dirty=%s|census=%s" %
               (run, backup, os.path.basename(archived),
                json.dumps(dirty, separators=(",", ":"), sort_keys=True),
                json.dumps(census, separators=(",", ":"), sort_keys=True)))


def _context(run, apply, do_revert):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        stop(run, "reason=PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    if world is None or world.get_outermost().get_name() != EXPECTED_WORLD:
        stop(run, "reason=WRONG_WORLD")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        stop(run, "reason=SEQUENCER_IS_OPEN")
    census = package_census()
    if census["maps"] or census["content"]:
        stop(run, "reason=DIRTY_BEFORE|census=" + json.dumps(census, sort_keys=True))
    if apply and os.path.exists(RECORD):
        stop(run, "reason=APPLY_RECORD_ALREADY_EXISTS")
    if do_revert and not os.path.isfile(RECORD):
        stop(run, "reason=REVERT_RECORD_ABSENT")
    return world


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    apply = bool(globals().get("S3_WAVE_SLIDES_APPLY"))
    do_revert = bool(globals().get("S3_WAVE_SLIDES_REVERT"))
    if apply and do_revert:
        stop(run, "reason=APPLY_AND_REVERT_BOTH_SET")
    world = _context(run, apply, do_revert)
    sequence = unreal.load_asset(ROOT_PATH)
    rise = unreal.load_asset(RISE_PATH)
    if sequence is None or not isinstance(sequence, unreal.LevelSequence):
        stop(run, "reason=ROOT_SEQUENCE_LOAD_FAILED")
    if rise is None or not isinstance(rise, unreal.LevelSequence):
        stop(run, "reason=RISE_SEQUENCE_LOAD_FAILED")
    if do_revert:
        revert(sequence, world, run)
        return
    state, runtime, root_landed, dock = live_state(sequence, rise, world, run)
    try:
        plan = plan_wave_slides(state)
    except PlanError as exc:
        stop(run, "reason=PLAN_REFUSED|detail=" + str(exc))
    state_by_label = {row["label"]: row for row in state["actors"]}
    row_plans = {row["row"]: row for row in plan["rows"]}
    composition = {}
    for target in plan["actors"]:
        rows = track_space_rows(state_by_label[target["label"]], row_plans[target["row"]],
                                root_landed, dock, run)
        composition[target["label"]] = {
            "first": rows[0], "last": rows[-1], "keys": len(rows),
        }
    if not apply:
        census = package_census()
        if census["maps"] or census["content"]:
            stop(run, "reason=DRY_RUN_DIRTIED_PACKAGES|census=" + json.dumps(census, sort_keys=True))
        summary = {
            "asset": ROOT_PATH, "strike": plan["strike"],
            "rows": [{key: row[key] for key in
                      ("row", "direction", "delay_frames", "first_key", "last_key", "seam")}
                     for row in plan["rows"]],
            "linear_interpolation_error_bound_cm": plan["linear_interpolation_error_bound_cm"],
            "clearance": plan["clearance"], "all_within_walls": plan["all_within_walls"],
            "composition": composition, "census": census,
        }
        unreal.log("S3_WAVE_SLIDES_DRY_RUN_OK|run=%s|mutated=0|summary=%s" %
                   (run, json.dumps(summary, separators=(",", ":"), sort_keys=True)))
        return
    apply_plan(sequence, world, state, runtime, plan, root_landed, dock, run)


if unreal is not None:
    main()
