"""Dry-run, apply, or revert the Scene 3 B07 vamp orbit.

Dry run is the default.  Apply/revert are selected only when this file is
executed through runpy with S3_VAMP_APPLY or S3_VAMP_REVERT set.  The pure
planner remains importable by test_s3_vamp_plan.py without Unreal.

This tool never opens/evaluates/scrubs Sequencer, enters PIE, or saves a map.
Apply/revert touch and save exactly LS_DevScene_03.
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
BINDING_NAME = "S3 Shot B07"
TRACK_NAME = "S3.VampOrbit"
EXPECTED_FPS = 24.0
EXPECTED_PLAYBACK = (0, 6240)
START_FRAME = 3480
END_FRAME = 4200
SECTION_RANGE = (START_FRAME, END_FRAME + 1)
VAMP_MARKERS = (
    (START_FRAME, "InfinityStage.VampStart"),
    (END_FRAME, "InfinityStage.VampEnd"),
)
CLAM_CENTRE_DOCK = (3500.0, 0.0, 105.0)
RADIUS_CM = 200.0
CAMERA_Z_DOCK = 120.0
DOCK_ORIGIN = (10921.973, 160000.0, 0.0)
DOCK_YAW_DEG = 0.0
FOCAL_MM = 85.0
APERTURE = 1.4
FOCUS_CM = 200.0
MAX_ADJACENT_ROTATION_DEG = 1.0
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
RECORD = os.path.join(HERE, "s3_vamp_record.json")


class PlanError(ValueError):
    pass


def distance(left, right):
    return math.sqrt(sum((float(left[i]) - float(right[i])) ** 2 for i in range(3)))


def rotation_error(left, right):
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

    left_quat = quaternion(left)
    right_quat = quaternion(right)
    dot = abs(sum(left_quat[i] * right_quat[i] for i in range(4)))
    return math.degrees(2.0 * math.acos(max(-1.0, min(1.0, dot))))


def unwind_degrees(value, reference):
    value = float(value)
    return value + 360.0 * round((float(reference) - value) / 360.0)


def _dock_to_world(point):
    yaw = math.radians(DOCK_YAW_DEG)
    return [
        DOCK_ORIGIN[0] + math.cos(yaw) * float(point[0]) - math.sin(yaw) * float(point[1]),
        DOCK_ORIGIN[1] + math.sin(yaw) * float(point[0]) + math.cos(yaw) * float(point[1]),
        DOCK_ORIGIN[2] + float(point[2]),
    ]


def _look_rotation(source, target):
    dx = float(target[0]) - float(source[0])
    dy = float(target[1]) - float(source[1])
    dz = float(target[2]) - float(source[2])
    horizontal = math.hypot(dx, dy)
    if horizontal < 1.0e-9 and abs(dz) < 1.0e-9:
        raise PlanError("camera and clam centre are coincident")
    return [0.0, math.degrees(math.atan2(dz, horizontal)), math.degrees(math.atan2(dy, dx))]


def orbit_pose(frame):
    """Return the specified B07 world-space orbit pose at one display frame."""
    frame = int(frame)
    theta = math.radians(180.0 + 360.0 * (frame - START_FRAME) / float(END_FRAME - START_FRAME))
    dock = [
        CLAM_CENTRE_DOCK[0] + RADIUS_CM * math.cos(theta),
        CLAM_CENTRE_DOCK[1] + RADIUS_CM * math.sin(theta),
        CAMERA_Z_DOCK,
    ]
    target_world = _dock_to_world(CLAM_CENTRE_DOCK)
    world = _dock_to_world(dock)
    rotation = _look_rotation(world, target_world)
    rotation[2] = DOCK_YAW_DEG + 360.0 * (frame - START_FRAME) / float(END_FRAME - START_FRAME)
    return {
        "frame": frame,
        "angle_deg": 180.0 + 360.0 * (frame - START_FRAME) / float(END_FRAME - START_FRAME),
        "dock_location_cm": dock,
        "world_location_cm": world,
        "world_rotation_rpy_deg": rotation,
    }


def _pose_with_override(frame, overrides):
    pose = orbit_pose(frame)
    override = overrides.get(str(frame), overrides.get(frame))
    if override:
        if "dock_location_cm" in override:
            pose["dock_location_cm"] = [float(value) for value in override["dock_location_cm"]]
            pose["world_location_cm"] = _dock_to_world(pose["dock_location_cm"])
            pose["world_rotation_rpy_deg"] = _look_rotation(
                pose["world_location_cm"], _dock_to_world(CLAM_CENTRE_DOCK))
        if "world_location_cm" in override:
            pose["world_location_cm"] = [float(value) for value in override["world_location_cm"]]
        if "world_rotation_rpy_deg" in override:
            pose["world_rotation_rpy_deg"] = [float(value) for value in override["world_rotation_rpy_deg"]]
    return pose


def plan_vamp(state):
    """Return the deterministic marker/orbit plan from an Unreal-free state dict."""
    if abs(float(state["fps"]) - EXPECTED_FPS) > 0.0001:
        raise PlanError("root display rate is not 24 fps")
    if [int(value) for value in state["playback"]] != list(EXPECTED_PLAYBACK):
        raise PlanError("unexpected root playback range")
    if int(state["binding_count"]) != 1 or not bool(state["binding_spawnable"]):
        raise PlanError("S3 Shot B07 is not exactly one spawnable binding")
    if [int(value) for value in state["cut_range"]] != [START_FRAME, END_FRAME]:
        raise PlanError("B07 cut is not [3480,4200]")
    if int(state["transform_track_count"]) != 0:
        raise PlanError("B07 already has a transform track")
    existing_vamp = [row for row in state.get("markers", [])
                     if str(row[1]).lower() in {label.lower() for _, label in VAMP_MARKERS}]
    if existing_vamp:
        raise PlanError("an InfinityStage Vamp marker already exists")

    requested_span = [int(value) for value in state.get("requested_span", [START_FRAME, END_FRAME])]
    if requested_span != [START_FRAME, END_FRAME]:
        raise PlanError("wrong orbit frame span")
    overrides = state.get("pose_overrides", {})
    keys = [_pose_with_override(frame, overrides)
            for frame in range(requested_span[0], requested_span[1] + 1)]
    if len(keys) != 721 or keys[0]["frame"] != START_FRAME or keys[-1]["frame"] != END_FRAME:
        raise PlanError("orbit must contain frames 3480..4200 inclusive")
    for row in keys:
        radius = math.hypot(
            float(row["dock_location_cm"][0]) - CLAM_CENTRE_DOCK[0],
            float(row["dock_location_cm"][1]) - CLAM_CENTRE_DOCK[1],
        )
        if abs(radius - RADIUS_CM) > 0.5:
            raise PlanError("orbit radius drift at frame %d" % row["frame"])
    for previous, current in zip(keys, keys[1:]):
        for axis, (left, right) in enumerate(zip(
                previous["world_rotation_rpy_deg"], current["world_rotation_rpy_deg"])):
            if abs(float(right) - float(left)) > MAX_ADJACENT_ROTATION_DEG:
                raise PlanError(
                    "rotation channel jump at frames %d..%d axis %d" %
                    (previous["frame"], current["frame"], axis))
    seam_location = distance(keys[0]["world_location_cm"], keys[-1]["world_location_cm"])
    seam_rotation = rotation_error(
        keys[0]["world_rotation_rpy_deg"], keys[-1]["world_rotation_rpy_deg"])
    if seam_location > 0.01 or seam_rotation > 0.01:
        raise PlanError("orbit seam mismatch")

    return {
        "asset": ROOT_PATH,
        "binding": BINDING_NAME,
        "markers": [list(row) for row in VAMP_MARKERS],
        "section_range": list(SECTION_RANGE),
        "lens": {"focal_mm": FOCAL_MM, "aperture": APERTURE, "focus_cm": FOCUS_CM},
        "keys": keys,
        "key_count": len(keys),
        "seam": {"location_cm": seam_location, "rotation_deg": seam_rotation},
        "poses": {"first": keys[0], "mid": keys[len(keys) // 2], "last": keys[-1]},
    }


def _package_path(value):
    name = value.get_name()
    return name if name.startswith("/") else "/" + name


def package_census():
    return {
        "maps": sorted(_package_path(value) for value in
                       unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
        "content": sorted(_package_path(value) for value in
                          unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    }


def stop(run, reason):
    unreal.log_error("S3_VAMP_STOPPED|run=%s|%s" % (run, reason))
    raise RuntimeError(reason)


def _modify(value):
    method = getattr(value, "modify", None)
    if method is not None:
        method()


def guid_text(value):
    return str(unreal.GuidLibrary.conv_guid_to_string(value))


def frame_value(value):
    if hasattr(value, "frame_number"):
        return int(value.frame_number.value)
    if hasattr(value, "value"):
        return int(value.value)
    return int(value)


def section_range(section):
    return [
        int(section.get_start_frame()) if section.has_start_frame() else None,
        int(section.get_end_frame()) if section.has_end_frame() else None,
    ]


def marker_rows(sequence):
    values = unreal.MovieSceneSequenceExtensions.get_marked_frames_from_sequence(
        sequence, unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    return sorted([int(row.frame_number.value), str(row.label)] for row in values)


def replace_markers(sequence, rows):
    _modify(sequence)
    sequence.delete_marked_frames()
    for frame, label in rows:
        marked = unreal.MovieSceneMarkedFrame()
        marked.frame_number = unreal.FrameNumber(value=int(frame))
        marked.label = str(label)
        unreal.MovieSceneSequenceExtensions.add_marked_frame_to_sequence(
            sequence, marked, unreal.MovieSceneTimeUnit.DISPLAY_RATE)


def canonical_channel_name(channel):
    try:
        name = str(channel.get_name())
    except Exception:
        name = str(channel.get_editor_property("channel_name"))
    name = re.sub(r"_\d+$", "", name)
    return name if name in CHANNEL_AXES else None


def _scalar(value):
    try:
        return float(value)
    except Exception:
        return str(value)


def channel_row(channel):
    name = canonical_channel_name(channel)
    keys = []
    for key in channel.get_keys():
        keys.append([frame_value(key.get_time()), _scalar(key.get_value())])
    row = {"name": name, "keys": keys}
    try:
        if channel.has_default():
            row["default"] = _scalar(channel.get_default())
    except Exception:
        pass
    return row


def track_row(track):
    return {
        "class": track.get_class().get_name(),
        "display_name": str(track.get_display_name()),
        "sections": [{
            "class": section.get_class().get_name(),
            "range": section_range(section),
            "active": bool(section.is_active()),
            "channels": [channel_row(channel) for channel in section.get_all_channels()],
        } for section in track.get_sections()],
    }


def binding_fingerprint(sequence, exclude_guid=None):
    spawnables = {guid_text(binding.get_id()) for binding in sequence.get_spawnables()}
    rows = []
    for binding in sequence.get_bindings():
        identity = guid_text(binding.get_id())
        if identity == exclude_guid:
            continue  # The target binding is verified separately, section-by-section.
        rows.append({
            "guid": identity,
            "name": str(binding.get_display_name()),
            "spawnable": identity in spawnables,
            "tracks": [track_row(track) for track in binding.get_tracks()],
        })
    return sorted(rows, key=lambda row: row["guid"])


def top_track_fingerprint(sequence):
    return [track_row(track) for track in sequence.get_tracks()]


def one_binding(sequence, run):
    spawnables = {guid_text(binding.get_id()) for binding in sequence.get_spawnables()}
    found = [binding for binding in sequence.get_bindings()
             if str(binding.get_display_name()) == BINDING_NAME]
    if len(found) != 1 or guid_text(found[0].get_id()) not in spawnables:
        stop(run, "reason=B07_SPAWNABLE_COUNT|count=%d" % len(found))
    return found[0]


def cut_rows(sequence):
    bindings = {guid_text(binding.get_id()): binding for binding in sequence.get_bindings()}
    rows = []
    for track in sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack):
        for section in track.get_sections():
            identity = guid_text(section.get_camera_binding_id().get_editor_property("guid"))
            binding = bindings.get(identity)
            rows.append({
                "binding": str(binding.get_display_name()) if binding else None,
                "binding_guid": identity,
                "range": section_range(section),
                "active": bool(section.is_active()),
            })
    return sorted(rows, key=lambda row: (row["range"], row["binding_guid"]))


def camera_snapshot(template):
    root = template.get_editor_property("root_component")
    camera = template.get_cine_camera_component() or template.get_editor_property("camera_component")
    if root is None or camera is None:
        raise RuntimeError("camera template root or camera_component is unreadable")
    location = root.get_editor_property("relative_location")
    rotation = root.get_editor_property("relative_rotation")
    scale = root.get_editor_property("relative_scale3d")
    focus = camera.get_editor_property("focus_settings")
    return {
        "root_relative": {
            "location": [float(location.x), float(location.y), float(location.z)],
            "rotation_rpy": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
            "scale": [float(scale.x), float(scale.y), float(scale.z)],
            "attached": root.get_attach_parent() is not None,
        },
        "focal_mm": float(camera.get_editor_property("current_focal_length")),
        "aperture": float(camera.get_editor_property("current_aperture")),
        "focus_cm": float(focus.get_editor_property("manual_focus_distance")),
        "focus_method": str(focus.get_editor_property("focus_method")),
    }


def _binding_has_parent(binding):
    try:
        parent = binding.get_parent()
        return parent is not None and parent.is_valid()
    except Exception:
        return False


def live_state(sequence, binding, run):
    rate = sequence.get_display_rate()
    identity = guid_text(binding.get_id())
    cuts = [row for row in cut_rows(sequence) if row["binding_guid"] == identity]
    if len(cuts) != 1:
        stop(run, "reason=B07_CUT_COUNT|count=%d" % len(cuts))
    template = binding.get_object_template()
    if template is None or not isinstance(template, unreal.CineCameraActor):
        stop(run, "reason=B07_TEMPLATE_NOT_CINE_CAMERA")
    snapshot = camera_snapshot(template)
    return {
        "fps": float(rate.numerator) / float(rate.denominator),
        "playback": [int(sequence.get_playback_start()), int(sequence.get_playback_end())],
        "binding_count": 1,
        "binding_spawnable": True,
        "binding_guid": identity,
        "binding_parented": _binding_has_parent(binding),
        "template_root_attached": snapshot["root_relative"]["attached"],
        "cut_range": cuts[0]["range"],
        "transform_track_count": len(binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack)),
        "markers": marker_rows(sequence),
        "camera": snapshot,
    }


def _context(run, apply, do_revert):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        stop(run, "reason=PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    if world is None or world.get_outermost().get_name() != EXPECTED_WORLD:
        stop(run, "reason=WRONG_WORLD")
    census = package_census()
    if census["maps"] or census["content"]:
        stop(run, "reason=DIRTY_BEFORE|census=" + json.dumps(census, sort_keys=True))
    if apply and os.path.exists(RECORD):
        stop(run, "reason=APPLY_RECORD_ALREADY_EXISTS")
    if do_revert and not os.path.isfile(RECORD):
        stop(run, "reason=REVERT_RECORD_ABSENT")


def _asset_filename(project):
    return os.path.join(project, "Content", *ROOT_PATH[len("/Game/"):].split("/")) + ".uasset"


def backup_asset(project, prefix, stamp, run):
    backup = os.path.join(project, "Backups", prefix + stamp.strftime("%Y%m%d-%H%M"))
    if os.path.exists(backup):
        stop(run, "reason=BACKUP_EXISTS|path=" + backup)
    source = _asset_filename(project)
    if not os.path.isfile(source):
        stop(run, "reason=BACKUP_SOURCE_MISSING|file=" + source)
    relative = os.path.relpath(source, os.path.join(project, "Content"))
    destination = os.path.join(backup, "Content", relative)
    os.makedirs(os.path.dirname(destination), exist_ok=False)
    shutil.copy2(source, destination)
    if os.path.getsize(source) != os.path.getsize(destination):
        stop(run, "reason=BACKUP_SIZE_MISMATCH")
    return backup, relative.replace("\\", "/")


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


def _plain_transform(value):
    rotation = value.rotation.rotator()
    return {
        "location": [float(value.translation.x), float(value.translation.y), float(value.translation.z)],
        "rotation_rpy": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
        "scale": [float(value.scale3d.x), float(value.scale3d.y), float(value.scale3d.z)],
    }


def _unreal_transform(location, rotation, scale=(1.0, 1.0, 1.0)):
    return unreal.Transform(
        location=unreal.Vector(*location),
        rotation=unreal.Rotator(roll=rotation[0], pitch=rotation[1], yaw=rotation[2]),
        scale=unreal.Vector(*scale),
    )


def _parent_world(binding, template, run):
    root = template.get_editor_property("root_component")
    if root.get_attach_parent() is None and not _binding_has_parent(binding):
        return unreal.Transform(), "world"
    try:
        parent_binding = binding.get_parent()
        parent_template = parent_binding.get_object_template() if parent_binding and parent_binding.is_valid() else None
        if parent_template is not None:
            parent_root = parent_template.get_editor_property("root_component")
            location = parent_root.get_editor_property("relative_location")
            rotation = parent_root.get_editor_property("relative_rotation")
            scale = parent_root.get_editor_property("relative_scale3d")
            return _unreal_transform(
                [location.x, location.y, location.z],
                [rotation.roll, rotation.pitch, rotation.yaw],
                [scale.x, scale.y, scale.z],
            ), "binding_parent"
        attach = root.get_attach_parent()
        if attach is not None:
            return attach.get_component_transform(), "template_attach_parent"
    except Exception as exc:
        stop(run, "reason=PARENT_SPACE_UNRESOLVED|detail=" + str(exc))
    stop(run, "reason=PARENT_SPACE_UNRESOLVED")


def track_space_rows(plan, parent_world, source, run):
    rows = []
    for row in plan["keys"]:
        wanted = _unreal_transform(row["world_location_cm"], row["world_rotation_rpy_deg"])
        local = (wanted if source == "world"
                 else unreal.MathLibrary.make_relative_transform(wanted, parent_world))
        composed = (local if source == "world"
                    else unreal.MathLibrary.compose_transforms(local, parent_world))
        plain = _plain_transform(local)
        if rows:
            plain["rotation_rpy"] = [
                unwind_degrees(value, rows[-1]["rotation_rpy"][axis])
                for axis, value in enumerate(plain["rotation_rpy"])
            ]
        round_trip = _plain_transform(composed)
        if (distance(round_trip["location"], row["world_location_cm"]) > 0.01 or
                rotation_error(round_trip["rotation_rpy"], row["world_rotation_rpy_deg"]) > 0.01):
            stop(run, "reason=TRACK_SPACE_COMPOSITION|frame=%d" % row["frame"])
        rows.append({
            "frame": row["frame"],
            "location": plain["location"],
            "rotation_rpy": plain["rotation_rpy"],
            "world_location_cm": round_trip["location"],
            "world_rotation_rpy_deg": round_trip["rotation_rpy"],
        })
    for previous, current in zip(rows, rows[1:]):
        for axis, (left, right) in enumerate(zip(
                previous["rotation_rpy"], current["rotation_rpy"])):
            if abs(float(right) - float(left)) > MAX_ADJACENT_ROTATION_DEG:
                stop(run, "reason=TRACK_SPACE_ROTATION_JUMP|frames=%d..%d|axis=%d" %
                     (previous["frame"], current["frame"], axis))
    return rows


def _camera_apply(template, lens):
    _modify(template)
    camera = template.get_cine_camera_component() or template.get_editor_property("camera_component")
    _modify(camera)
    camera.set_editor_property("current_focal_length", float(lens["focal_mm"]))
    camera.set_editor_property("current_aperture", float(lens["aperture"]))
    focus = camera.get_editor_property("focus_settings")
    focus.set_editor_property("focus_method", unreal.CameraFocusMethod.MANUAL)
    focus.set_editor_property("manual_focus_distance", float(lens["focus_cm"]))
    camera.set_editor_property("focus_settings", focus)


def _camera_restore(template, snapshot):
    _modify(template)
    camera = template.get_cine_camera_component() or template.get_editor_property("camera_component")
    _modify(camera)
    camera.set_editor_property("current_focal_length", float(snapshot["focal_mm"]))
    camera.set_editor_property("current_aperture", float(snapshot["aperture"]))
    focus = camera.get_editor_property("focus_settings")
    focus_method = snapshot["focus_method"].split(".")[-1].split(":")[0].strip(" <>')")
    if hasattr(unreal.CameraFocusMethod, focus_method):
        focus.set_editor_property("focus_method", getattr(unreal.CameraFocusMethod, focus_method))
    else:
        stop("revert", "reason=FOCUS_METHOD_UNRESOLVED|value=" + snapshot["focus_method"])
    focus.set_editor_property("manual_focus_distance", float(snapshot["focus_cm"]))
    camera.set_editor_property("focus_settings", focus)


def add_transform_track(binding, rows, template, run):
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
    section.set_range(*SECTION_RANGE)
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
    root = template.get_editor_property("root_component")
    scale = root.get_editor_property("relative_scale3d")
    for name, value in zip(CHANNEL_AXES[6:], (scale.x, scale.y, scale.z)):
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
                unreal.FrameNumber(row["frame"]), float(values[name]),
                time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                interpolation=linear,
            )
            if made is None:
                stop(run, "reason=ADD_KEY_FAILED|channel=%s|frame=%d" % (name, row["frame"]))
    return track


def transform_readback(binding, expected_rows, parent_world, source, run):
    tracks = list(binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack))
    if len(tracks) != 1 or str(tracks[0].get_display_name()) != TRACK_NAME:
        stop(run, "reason=TRANSFORM_TRACK_READBACK|count=%d" % len(tracks))
    sections = list(tracks[0].get_sections())
    if len(sections) != 1 or section_range(sections[0]) != list(SECTION_RANGE):
        stop(run, "reason=TRANSFORM_SECTION_READBACK")
    channels = {canonical_channel_name(channel): channel for channel in sections[0].get_all_channels()
                if canonical_channel_name(channel)}
    report = {}
    for name in POSE_AXES:
        keys = list(channels[name].get_keys())
        frames = [frame_value(key.get_time()) for key in keys]
        if frames != list(range(START_FRAME, END_FRAME + 1)):
            stop(run, "reason=KEY_FRAME_READBACK|channel=" + name)
        report[name] = {
            "count": len(keys),
            "first": [frames[0], float(keys[0].get_value())],
            "mid": [frames[len(keys) // 2], float(keys[len(keys) // 2].get_value())],
            "last": [frames[-1], float(keys[-1].get_value())],
        }
    for index in (0, len(expected_rows) // 2, len(expected_rows) - 1):
        row = expected_rows[index]
        values = {
            name: float(channels[name].get_keys()[index].get_value()) for name in POSE_AXES
        }
        local = _unreal_transform(
            [values["Location.X"], values["Location.Y"], values["Location.Z"]],
            [values["Rotation.X"], values["Rotation.Y"], values["Rotation.Z"]],
        )
        composed = (local if source == "world"
                    else unreal.MathLibrary.compose_transforms(local, parent_world))
        plain = _plain_transform(composed)
        if (distance(plain["location"], row["world_location_cm"]) > 0.01 or
                rotation_error(plain["rotation_rpy"], row["world_rotation_rpy_deg"]) > 0.01):
            stop(run, "reason=COMPOSED_KEY_READBACK|frame=%d" % row["frame"])
    first_world = expected_rows[0]
    last_world = expected_rows[-1]
    if (distance(first_world["world_location_cm"], last_world["world_location_cm"]) > 0.01 or
            rotation_error(first_world["world_rotation_rpy_deg"],
                           last_world["world_rotation_rpy_deg"]) > 0.01):
        stop(run, "reason=SEAM_READBACK")
    return {"track": track_row(tracks[0]), "channels": report}


def exact_dirty(run):
    census = package_census()
    if census["maps"] or census["content"] != [ROOT_PATH]:
        stop(run, "reason=DIRTY_CENSUS|census=" + json.dumps(census, sort_keys=True))
    return census


def exact_save(run):
    if not unreal.EditorAssetLibrary.save_asset(ROOT_PATH, only_if_is_dirty=False):
        stop(run, "reason=SAVE_FAILED")
    census = package_census()
    if census["maps"] or census["content"]:
        stop(run, "reason=POST_SAVE_DIRTY|census=" + json.dumps(census, sort_keys=True))
    return census


def apply_plan(sequence, binding, plan, state, run):
    identity = state["binding_guid"]
    before = {
        "markers": marker_rows(sequence),
        "cuts": cut_rows(sequence),
        "other_bindings": binding_fingerprint(sequence, exclude_guid=identity),
        "top_tracks": top_track_fingerprint(sequence),
        "target_tracks": [track_row(track) for track in binding.get_tracks()],
        "camera": camera_snapshot(binding.get_object_template()),
    }
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    stamp = datetime.datetime.now()
    backup, copied = backup_asset(project, "PreS3Vamp-", stamp, run)
    record = {
        "written": stamp.isoformat(timespec="seconds"), "run": run,
        "world": EXPECTED_WORLD, "asset": ROOT_PATH, "binding_guid": identity,
        "backup": backup, "backup_file": copied,
        "plan_summary": {key: plan[key] for key in ("markers", "section_range", "lens", "key_count", "seam", "poses")},
        "before": before,
    }
    write_record(record, "x", run)

    template = binding.get_object_template()
    parent_world, space_source = _parent_world(binding, template, run)
    rows = track_space_rows(plan, parent_world, space_source, run)
    _modify(sequence)
    replace_markers(sequence, before["markers"] + plan["markers"])
    add_transform_track(binding, rows, template, run)
    _camera_apply(template, plan["lens"])

    wanted_markers = sorted(before["markers"] + plan["markers"])
    if marker_rows(sequence) != wanted_markers:
        stop(run, "reason=MARKER_READBACK")
    readback = transform_readback(binding, rows, parent_world, space_source, run)
    camera = camera_snapshot(template)
    if (abs(camera["focal_mm"] - FOCAL_MM) > 0.001 or
            abs(camera["aperture"] - APERTURE) > 0.001 or
            abs(camera["focus_cm"] - FOCUS_CM) > 0.001 or "MANUAL" not in camera["focus_method"].upper()):
        stop(run, "reason=LENS_READBACK")
    if cut_rows(sequence) != before["cuts"] or top_track_fingerprint(sequence) != before["top_tracks"]:
        stop(run, "reason=NON_TARGET_TOP_DATA_CHANGED")
    if binding_fingerprint(sequence, exclude_guid=identity) != before["other_bindings"]:
        stop(run, "reason=OTHER_BINDINGS_CHANGED")
    dirty = exact_dirty(run)
    census = exact_save(run)
    record["after"] = {
        "markers": marker_rows(sequence), "camera": camera, "transform": readback,
        "track_space": space_source, "dirty_before_save": dirty, "post_save_census": census,
    }
    write_record(record, "w", run)
    unreal.log("S3_VAMP_DONE|run=%s|applied|backup=%s|keys=%d|space=%s|census=%s" %
               (run, backup, plan["key_count"], space_source,
                json.dumps(census, separators=(",", ":"), sort_keys=True)))


def revert(sequence, binding, run):
    record = read_record(run)
    identity = guid_text(binding.get_id())
    if (record.get("world") != EXPECTED_WORLD or record.get("asset") != ROOT_PATH or
            record.get("binding_guid") != identity):
        stop(run, "reason=RECORD_CONTEXT_MISMATCH")
    before = record["before"]
    if marker_rows(sequence) != record.get("after", {}).get("markers"):
        stop(run, "reason=CURRENT_MARKERS_CHANGED")
    if cut_rows(sequence) != before["cuts"] or top_track_fingerprint(sequence) != before["top_tracks"]:
        stop(run, "reason=CURRENT_TOP_DATA_CHANGED")
    if binding_fingerprint(sequence, exclude_guid=identity) != before["other_bindings"]:
        stop(run, "reason=CURRENT_OTHER_BINDINGS_CHANGED")
    tracks = list(binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack))
    if len(tracks) != 1 or str(tracks[0].get_display_name()) != TRACK_NAME:
        stop(run, "reason=CURRENT_TRANSFORM_TRACK_MISMATCH")

    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    stamp = datetime.datetime.now()
    backup, _ = backup_asset(project, "PreS3VampRevert-", stamp, run)
    _modify(sequence)
    _modify(binding)
    if not binding.remove_track(tracks[0]):
        stop(run, "reason=REMOVE_TRANSFORM_TRACK_FAILED")
    replace_markers(sequence, before["markers"])
    _camera_restore(binding.get_object_template(), before["camera"])
    if ([track_row(track) for track in binding.get_tracks()] != before["target_tracks"] or
            marker_rows(sequence) != before["markers"] or
            camera_snapshot(binding.get_object_template()) != before["camera"] or
            cut_rows(sequence) != before["cuts"] or
            top_track_fingerprint(sequence) != before["top_tracks"] or
            binding_fingerprint(sequence, exclude_guid=identity) != before["other_bindings"]):
        stop(run, "reason=REVERT_READBACK")
    exact_dirty(run)
    census = exact_save(run)
    archived = RECORD + ".reverted-" + stamp.strftime("%Y%m%d-%H%M%S")
    os.rename(RECORD, archived)
    unreal.log("S3_VAMP_DONE|run=%s|reverted|backup=%s|record=%s|census=%s" %
               (run, backup, os.path.basename(archived),
                json.dumps(census, separators=(",", ":"), sort_keys=True)))


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    apply = bool(globals().get("S3_VAMP_APPLY"))
    do_revert = bool(globals().get("S3_VAMP_REVERT"))
    if apply and do_revert:
        stop(run, "reason=APPLY_AND_REVERT_BOTH_SET")
    _context(run, apply, do_revert)
    sequence = unreal.load_asset(ROOT_PATH)
    if sequence is None or not isinstance(sequence, unreal.LevelSequence):
        stop(run, "reason=SEQUENCE_LOAD_FAILED")
    binding = one_binding(sequence, run)
    if do_revert:
        revert(sequence, binding, run)
        return
    state = live_state(sequence, binding, run)
    try:
        plan = plan_vamp(state)
    except PlanError as exc:
        stop(run, "reason=PLAN_REFUSED|detail=" + str(exc))
    parent_world, space_source = _parent_world(binding, binding.get_object_template(), run)
    track_rows = track_space_rows(plan, parent_world, space_source, run)
    if not apply:
        census = package_census()
        if census["maps"] or census["content"]:
            stop(run, "reason=DRY_RUN_DIRTIED_PACKAGES|census=" + json.dumps(census, sort_keys=True))
        summary = {
            "asset": ROOT_PATH, "binding": BINDING_NAME, "binding_guid": state["binding_guid"],
            "markers": plan["markers"], "keys": plan["key_count"], "lens": plan["lens"],
            "seam": plan["seam"], "track_space": space_source,
            "first": track_rows[0], "mid": track_rows[len(track_rows) // 2], "last": track_rows[-1],
            "census": census,
        }
        unreal.log("S3_VAMP_DRY_RUN_OK|run=%s|mutated=0|summary=%s" %
                   (run, json.dumps(summary, separators=(",", ":"), sort_keys=True)))
        return
    apply_plan(sequence, binding, plan, state, run)


if unreal is not None:
    main()
