"""Dry-run, apply, or revert the Scene 3 beat markers and camera retirement.

Dry run is the default.  The dedicated wrappers beside this file are the only
intended way to set S3_BEATS_APPLY or S3_BEATS_REVERT.  Pure planning helpers
remain importable by test_s3_beats_plan.py without Unreal.

This tool never opens Sequencer, evaluates a sequence, loads a level, or saves a
map.  Apply/revert save exactly LS_DevScene_03 and LS_Clams.
"""
import datetime
import json
import re
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline planning harness.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ROOT_PATH = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
CLAMS_PATH = "/Game/Scenes/LS_Clams"
ENTRY_NAME = "Scene 3 — External Sound — Entry Handoff Camera"
EXIT_NAME = "Scene 3 — External Sound — Exit Handoff Camera"
CLAM_NAME = "ClamCam1"
WIDE_NAME = "S3 Wide"
FORBIDDEN_MARKER = "InfinityStage.HiddenChangeover"
EXPECTED_FPS = 24.0
EXPECTED_PLAYBACK = (0, 6240)
EXPECTED_EXIT_HOLD = 24
WIDE_START = 95
BEAT_MARKERS = (
    (0, "S3 B01 Arrive - strike"),
    (360, "S3 B02 Figures sway - wide to figures"),
    (960, "S3 B03 Clam on pedestal (shut)"),
    (1440, "S3 B04 Agitation builds - waves"),
    (2880, "S3 B05 Clam opens slowly"),
    (3000, "S3 B06 Close-up of opening"),
    (3480, "S3 B07 Pearl glows - song of forgetting"),
    (4200, "S3 B08 Figures calm"),
    (4680, "S3 B09 Calm swaying (animation start)"),
    (5040, "S3 B10 Defocus - Puss's thoughts"),
    (5520, "S3 B11 Pearl rises to camera"),
    (5880, "S3 B12 Float out - to curtain"),
)

if unreal is not None:
    HERE = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexConductor",
    )
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
RECORD = os.path.join(HERE, "s3_beats_record.json")


class PlanError(ValueError):
    pass


def validate_range_operations(operations):
    """Reject the SetStart/SetEnd failure mode that clamps against the old range."""
    split = [row for row in operations if row.get("op") in ("set_start", "set_end")]
    ranges = [row for row in operations if row.get("op") == "set_range"]
    if split:
        raise PlanError("split set_start/set_end is forbidden")
    if len(ranges) != 1 or ranges[0].get("target") != "S3 Wide cut":
        raise PlanError("S3 Wide cut requires exactly one set_range operation")
    value = ranges[0].get("range")
    if not isinstance(value, (list, tuple)) or len(value) != 2 or value[1] <= value[0]:
        raise PlanError("invalid S3 Wide range")
    return True


def plan_beats(state, operations=None):
    """Return the deterministic Step B plan from an Unreal-free state dict."""
    fps = float(state["fps"])
    playback = [int(v) for v in state["playback"]]
    if abs(fps - EXPECTED_FPS) > 0.0001:
        raise PlanError("root display rate is not 24 fps")
    if playback != list(EXPECTED_PLAYBACK):
        raise PlanError("Step A is not applied: playback=%s" % playback)

    markers = [(int(row[0]), str(row[1])) for row in state.get("markers", [])]
    labels = [label for _, label in markers]
    if FORBIDDEN_MARKER in labels:
        raise PlanError("forbidden HiddenChangeover marker exists")
    if any(label.startswith("S3 B") for label in labels):
        raise PlanError("an existing S3 B marker makes this non-idempotent")
    if len(labels) != len(set((frame, label) for frame, label in markers)):
        raise PlanError("duplicate existing marker rows")
    if not state.get("entry_source_available"):
        raise PlanError("Entry Handoff source camera is unavailable")
    if state.get("wide_binding_exists"):
        raise PlanError("S3 Wide binding already exists")

    exit_cut = state["exit_cut"]
    root_clam = state["root_clam_cut"]
    nested_clam = state["nested_clam_cut"]
    for name, cut in (("Exit", exit_cut), ("root ClamCam1", root_clam),
                      ("nested ClamCam1", nested_clam)):
        if cut.get("start") is None or cut.get("end") is None:
            raise PlanError("%s cut has an open range" % name)
    # The Exit's CURRENT length is not its designed hold: a retained Exit starts where the last
    # interior cut ends (run 135651 read it stretched from ClamCam1's end to the new 6240 end).
    # The designed hold is 24 display frames (1 s); rematch_only restores it once S3 Wide is last.
    exit_hold = EXPECTED_EXIT_HOLD
    if int(exit_cut["end"]) != playback[1]:
        raise PlanError("Exit cut does not end at the playback end")
    if int(exit_cut["start"]) > playback[1] - exit_hold:
        raise PlanError("Exit cut is shorter than the designed hold")
    if not bool(root_clam.get("active")) or not bool(nested_clam.get("active")):
        raise PlanError("a ClamCam1 cut is already inactive")

    wide_end = playback[1] - exit_hold
    if int(root_clam["end"]) > wide_end:
        raise PlanError("retired root ClamCam1 ends after S3 Wide")
    if WIDE_START >= wide_end:
        raise PlanError("S3 Wide has an empty range")
    if any(frame < playback[0] or frame >= playback[1] for frame, _ in BEAT_MARKERS):
        raise PlanError("a beat marker is outside playback")

    planned_operations = operations or [
        {"op": "add_spawnable_from_instance", "target": WIDE_NAME, "source": ENTRY_NAME},
        {"op": "set_range", "target": "S3 Wide cut", "range": [WIDE_START, wide_end]},
        {"op": "set_is_active", "target": "root ClamCam1 cut", "value": False},
        {"op": "set_is_active", "target": "nested ClamCam1 cut", "value": False},
        {"op": "add_markers", "target": ROOT_PATH, "markers": [list(v) for v in BEAT_MARKERS]},
    ]
    validate_range_operations(planned_operations)
    return {
        "root": ROOT_PATH,
        "nested": CLAMS_PATH,
        "playback": playback,
        "fps": fps,
        "exit_hold_frames": exit_hold,
        "wide_range": [WIDE_START, wide_end],
        "root_clam_range": [int(root_clam["start"]), int(root_clam["end"])],
        "nested_clam_range": [int(nested_clam["start"]), int(nested_clam["end"])],
        "markers": [list(v) for v in BEAT_MARKERS],
        "operations": planned_operations,
    }


def _package_path(value):
    return str(value.get_path_name()).split(".", 1)[0]


def package_census():
    return {
        "maps": sorted(_package_path(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
        "content": sorted(_package_path(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    }


def stop(run, reason):
    unreal.log_error("S3_BEATS_STOPPED|run=%s|%s" % (run, reason))
    raise RuntimeError(reason)


def guid_text(value):
    return str(unreal.GuidLibrary.conv_guid_to_string(value))


def binding_map(sequence):
    return {guid_text(binding.get_id()): binding for binding in sequence.get_bindings()}


def one_binding(sequence, name, run, spawnable=None):
    spawnables = {guid_text(binding.get_id()) for binding in sequence.get_spawnables()}
    found = [binding for binding in sequence.get_bindings() if str(binding.get_display_name()) == name]
    if spawnable is not None:
        found = [binding for binding in found if (guid_text(binding.get_id()) in spawnables) == spawnable]
    if len(found) != 1:
        stop(run, "reason=BINDING_COUNT|asset=%s|name=%s|count=%d" %
             (_package_path(sequence), name, len(found)))
    return found[0]


def one_cut_track(sequence, run):
    tracks = list(sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack))
    if len(tracks) != 1:
        stop(run, "reason=CUT_TRACK_COUNT|asset=%s|count=%d" % (_package_path(sequence), len(tracks)))
    return tracks[0]


def section_range(section):
    return [
        int(section.get_start_frame()) if section.has_start_frame() else None,
        int(section.get_end_frame()) if section.has_end_frame() else None,
    ]


def cut_rows(sequence):
    bindings = binding_map(sequence)
    rows = []
    for track_index, track in enumerate(sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack)):
        for section_index, section in enumerate(track.get_sections()):
            camera_id = section.get_camera_binding_id().get_editor_property("guid")
            binding = bindings.get(guid_text(camera_id))
            rows.append({
                "track_index": track_index,
                "section_index": section_index,
                "binding": str(binding.get_display_name()) if binding else None,
                "binding_guid": guid_text(camera_id),
                "range": section_range(section),
                "active": bool(section.is_active()),
            })
    return rows


def one_cut(sequence, name, run):
    bindings = binding_map(sequence)
    found = []
    for track in sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack):
        for section in track.get_sections():
            camera_id = section.get_camera_binding_id().get_editor_property("guid")
            binding = bindings.get(guid_text(camera_id))
            if binding is not None and str(binding.get_display_name()) == name:
                found.append((track, section, binding))
    if len(found) != 1:
        stop(run, "reason=CUT_COUNT|asset=%s|name=%s|count=%d" %
             (_package_path(sequence), name, len(found)))
    return found[0]


def marker_rows(sequence):
    marked = unreal.MovieSceneSequenceExtensions.get_marked_frames_from_sequence(
        sequence, unreal.MovieSceneTimeUnit.DISPLAY_RATE
    )
    return sorted((int(row.frame_number.value), str(row.label)) for row in marked)


def _scalar(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    try:
        return float(value)
    except Exception:
        return str(value)


def channel_row(channel):
    try:
        name = str(channel.get_name())
    except Exception:
        name = str(channel.get_editor_property("channel_name"))
    # Scripting channel proxies are renumbered on every read (Location.X_0 -> Location.X_6,
    # MovieSceneScriptingFloatChannel_0 -> _12; diff run 145950). Compare without the suffix.
    name = re.sub(r"_\d+$", "", name)
    keys = []
    for key in channel.get_keys():
        time = key.get_time()
        frame = int(time.frame_number.value if hasattr(time, "frame_number") else time.value)
        keys.append([frame, _scalar(key.get_value())])
    row = {"name": name, "keys": keys}
    try:
        if channel.has_default():
            row["default"] = _scalar(channel.get_default())
    except Exception:
        pass
    return row


def track_row(track, ignore_cut_active_guid=None):
    row = {"class": track.get_class().get_name(), "name": str(track.get_display_name()), "sections": []}
    for section in track.get_sections():
        active = bool(section.is_active())
        camera_guid = None
        if isinstance(section, unreal.MovieSceneCameraCutSection):
            camera_guid = guid_text(section.get_camera_binding_id().get_editor_property("guid"))
            if camera_guid == ignore_cut_active_guid:
                active = "TARGET_IGNORED"
        row["sections"].append({
            "range": section_range(section),
            "active": active,
            "camera_guid": camera_guid,
            "channels": [channel_row(channel) for channel in section.get_all_channels()],
        })
    return row


def binding_fingerprint(sequence, only_guids=None):
    spawnables = {guid_text(binding.get_id()) for binding in sequence.get_spawnables()}
    rows = []
    for binding in sequence.get_bindings():
        identity = guid_text(binding.get_id())
        if only_guids is not None and identity not in only_guids:
            continue
        rows.append({
            "guid": identity,
            "name": str(binding.get_display_name()),
            "spawnable": identity in spawnables,
            "tracks": [track_row(track) for track in binding.get_tracks()],
        })
    return sorted(rows, key=lambda row: row["guid"])


def top_track_fingerprint(sequence, include_cut=True, ignore_cut_active_guid=None):
    tracks = list(sequence.get_tracks())
    if not include_cut:
        tracks = [track for track in tracks if not isinstance(track, unreal.MovieSceneCameraCutTrack)]
    return [track_row(track, ignore_cut_active_guid) for track in tracks]


def camera_snapshot(actor):
    # Measured on a spawnable's object template (probe 141959): get_actor_transform() reads
    # zero and get_cine_camera_component()/get_components_by_class() return nothing; the pose
    # is the ROOT component's relative transform and the camera is the 'camera_component'
    # property. Read both actors that way (an unattached level actor's root relative = world).
    root = actor.get_editor_property("root_component")
    if root is None or root.get_attach_parent() is not None:
        raise RuntimeError("reason=CAMERA_ROOT_UNREADABLE_OR_ATTACHED|actor=%s" % actor.get_name())
    location = root.get_editor_property("relative_location")
    rotation = root.get_editor_property("relative_rotation")
    scale = root.get_editor_property("relative_scale3d")
    camera = actor.get_cine_camera_component() or actor.get_editor_property("camera_component")
    if camera is None:
        raise RuntimeError("reason=CINE_CAMERA_COMPONENT_UNREADABLE|actor=%s" % actor.get_name())
    result = {
        "transform": {
            "location": [float(location.x), float(location.y), float(location.z)],
            "rotation": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
            "scale": [float(scale.x), float(scale.y), float(scale.z)],
        },
        "current_focal_length": float(camera.get_editor_property("current_focal_length")),
        "current_aperture": float(camera.get_editor_property("current_aperture")),
    }
    for struct_name, fields in (
        ("filmback", ("sensor_width", "sensor_height", "sensor_aspect_ratio")),
        ("lens_settings", ("min_focal_length", "max_focal_length", "min_f_stop", "max_f_stop", "minimum_focus_distance")),
        ("focus_settings", ("focus_method", "manual_focus_distance")),
    ):
        struct = camera.get_editor_property(struct_name)
        result[struct_name] = {}
        for field in fields:
            try:
                result[struct_name][field] = _scalar(struct.get_editor_property(field))
            except Exception:
                pass
    return result


def snapshots_close(left, right, tolerance=0.001):
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(snapshots_close(left[k], right[k], tolerance) for k in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(snapshots_close(a, b, tolerance) for a, b in zip(left, right))
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) <= tolerance
    return left == right


def _context(run, revert, apply):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        stop(run, "reason=PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    if world is None or world.get_outermost().get_name() != EXPECTED_WORLD:
        stop(run, "reason=WRONG_WORLD")
    census = package_census()
    if census["maps"] or census["content"]:
        stop(run, "reason=DIRTY_BEFORE|census=" + json.dumps(census, sort_keys=True))
    if revert and not os.path.exists(RECORD):
        stop(run, "reason=REVERT_RECORD_ABSENT")
    if apply and os.path.exists(RECORD):
        stop(run, "reason=APPLY_RECORD_ALREADY_EXISTS")
    return world


def one_level_camera(name, run):
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    found = [actor for actor in actors
             if isinstance(actor, unreal.CineCameraActor) and actor.get_actor_label() == name]
    if len(found) != 1:
        stop(run, "reason=ENTRY_CAMERA_COUNT|count=%d" % len(found))
    return found[0]


def live_state(root, clams, run):
    rate = root.get_display_rate()
    fps = float(rate.numerator) / float(rate.denominator)
    _, exit_cut, _ = one_cut(root, EXIT_NAME, run)
    _, root_clam, _ = one_cut(root, CLAM_NAME, run)
    _, nested_clam, _ = one_cut(clams, CLAM_NAME, run)
    wide = [binding for binding in root.get_bindings() if str(binding.get_display_name()) == WIDE_NAME]
    state = {
        "fps": fps,
        "playback": [int(root.get_playback_start()), int(root.get_playback_end())],
        "markers": marker_rows(root),
        "entry_source_available": one_level_camera(ENTRY_NAME, run) is not None,
        "wide_binding_exists": bool(wide),
        "exit_cut": {"start": section_range(exit_cut)[0], "end": section_range(exit_cut)[1],
                     "active": bool(exit_cut.is_active())},
        "root_clam_cut": {"start": section_range(root_clam)[0], "end": section_range(root_clam)[1],
                          "active": bool(root_clam.is_active())},
        "nested_clam_cut": {"start": section_range(nested_clam)[0], "end": section_range(nested_clam)[1],
                            "active": bool(nested_clam.is_active())},
    }
    return state


def _asset_filename(project, package):
    return os.path.join(project, "Content", *package[len("/Game/"):].split("/")) + ".uasset"


def backup_assets(project, prefix, stamp, run):
    backup = os.path.join(project, "Backups", prefix + stamp.strftime("%Y%m%d-%H%M"))
    if os.path.exists(backup):
        stop(run, "reason=BACKUP_EXISTS|path=" + backup)
    sources = [_asset_filename(project, ROOT_PATH), _asset_filename(project, CLAMS_PATH)]
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
        copied.append(relative.replace("\\", "/"))
    return backup, copied


def write_record(record, run):
    try:
        with open(RECORD, "x", encoding="utf-8") as handle:
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


def add_markers(sequence):
    for frame, label in BEAT_MARKERS:
        marked = unreal.MovieSceneMarkedFrame()
        marked.frame_number = unreal.FrameNumber(value=frame)
        marked.label = label
        unreal.MovieSceneSequenceExtensions.add_marked_frame_to_sequence(
            sequence, marked, unreal.MovieSceneTimeUnit.DISPLAY_RATE
        )


def replace_markers(sequence, rows):
    sequence.delete_marked_frames()
    for frame, label in rows:
        marked = unreal.MovieSceneMarkedFrame()
        marked.frame_number = unreal.FrameNumber(value=int(frame))
        marked.label = str(label)
        unreal.MovieSceneSequenceExtensions.add_marked_frame_to_sequence(
            sequence, marked, unreal.MovieSceneTimeUnit.DISPLAY_RATE
        )


def exact_dirty(run):
    census = package_census()
    expected = sorted([ROOT_PATH, CLAMS_PATH])
    if census["maps"] or census["content"] != expected:
        stop(run, "reason=DIRTY_CENSUS|census=" + json.dumps(census, sort_keys=True))
    return census


def exact_save(root, clams, run):
    saved = {
        ROOT_PATH: bool(unreal.EditorAssetLibrary.save_asset(ROOT_PATH, only_if_is_dirty=False)),
        CLAMS_PATH: bool(unreal.EditorAssetLibrary.save_asset(CLAMS_PATH, only_if_is_dirty=False)),
    }
    if not all(saved.values()):
        stop(run, "reason=SAVE_FAILED|saved=" + json.dumps(saved, sort_keys=True))
    census = package_census()
    if census["maps"] or census["content"]:
        stop(run, "reason=POST_SAVE_DIRTY|census=" + json.dumps(census, sort_keys=True))
    return census


def apply_plan(root, clams, plan, run):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    stamp = datetime.datetime.now()
    backup, copied = backup_assets(project, "PreS3Beats-", stamp, run)
    entry = one_level_camera(ENTRY_NAME, run)
    _, root_clam, _ = one_cut(root, CLAM_NAME, run)
    _, nested_clam, nested_binding = one_cut(clams, CLAM_NAME, run)
    root_before_guids = {guid_text(binding.get_id()) for binding in root.get_bindings()}
    before = {
        "root_cuts": cut_rows(root),
        "nested_cuts": cut_rows(clams),
        "markers": [list(row) for row in marker_rows(root)],
        "root_bindings": binding_fingerprint(root),
        "root_non_cut_tracks": top_track_fingerprint(root, include_cut=False),
        "nested_bindings": binding_fingerprint(clams),
        "nested_tracks_ignoring_clam_active": top_track_fingerprint(
            clams, include_cut=True, ignore_cut_active_guid=guid_text(nested_binding.get_id())
        ),
        "entry_camera": camera_snapshot(entry),
    }
    record = {
        "written": stamp.isoformat(timespec="seconds"),
        "run": run,
        "world": EXPECTED_WORLD,
        "backup": backup,
        "backup_files": copied,
        "plan": plan,
        "before": before,
    }
    write_record(record, run)

    wide = root.add_spawnable_from_instance(entry)
    if wide is None:
        stop(run, "reason=ADD_SPAWNABLE_FAILED")
    wide.set_display_name(WIDE_NAME)
    template = wide.get_object_template()
    if template is None or not isinstance(template, unreal.CineCameraActor):
        stop(run, "reason=WIDE_TEMPLATE_NOT_CINE_CAMERA")
    if not snapshots_close(camera_snapshot(template), before["entry_camera"]):
        stop(run, "reason=WIDE_TEMPLATE_COPY_MISMATCH")
    cut_track = one_cut_track(root, run)
    wide_cut = cut_track.add_section()
    wide_cut.set_camera_binding_id(root.get_binding_id(wide))
    # Intentional single range call. Never split this into start/end setters.
    wide_cut.set_range(plan["wide_range"][0], plan["wide_range"][1])
    root_clam.set_is_active(False)
    nested_clam.set_is_active(False)
    add_markers(root)

    _, read_root_clam, _ = one_cut(root, CLAM_NAME, run)
    _, read_nested_clam, read_nested_binding = one_cut(clams, CLAM_NAME, run)
    _, read_wide_cut, read_wide_binding = one_cut(root, WIDE_NAME, run)
    expected_markers = sorted(before["markers"] + [list(row) for row in BEAT_MARKERS])
    if section_range(read_wide_cut) != plan["wide_range"] or not read_wide_cut.is_active():
        stop(run, "reason=WIDE_CUT_READBACK")
    if read_root_clam.is_active() or read_nested_clam.is_active():
        stop(run, "reason=CLAM_CUT_ACTIVE_READBACK")
    if marker_rows(root) != [tuple(row) for row in expected_markers]:
        stop(run, "reason=MARKER_READBACK")
    if guid_text(read_wide_binding.get_id()) not in {guid_text(binding.get_id()) for binding in root.get_spawnables()}:
        stop(run, "reason=WIDE_NOT_SPAWNABLE")
    if not snapshots_close(camera_snapshot(read_wide_binding.get_object_template()), before["entry_camera"]):
        stop(run, "reason=WIDE_TEMPLATE_READBACK")
    if binding_fingerprint(root, root_before_guids) != before["root_bindings"]:
        stop(run, "reason=EXISTING_ROOT_BINDINGS_CHANGED")
    if top_track_fingerprint(root, include_cut=False) != before["root_non_cut_tracks"]:
        stop(run, "reason=ROOT_NON_CUT_TRACKS_CHANGED")
    if binding_fingerprint(clams) != before["nested_bindings"]:
        stop(run, "reason=NESTED_BINDINGS_CHANGED")
    if top_track_fingerprint(clams, include_cut=True,
                             ignore_cut_active_guid=guid_text(read_nested_binding.get_id())) != \
            before["nested_tracks_ignoring_clam_active"]:
        stop(run, "reason=NESTED_NON_TARGET_DATA_CHANGED")

    exact_dirty(run)
    census = exact_save(root, clams, run)
    record["after"] = {
        "root_cuts": cut_rows(root),
        "nested_cuts": cut_rows(clams),
        "markers": [list(row) for row in marker_rows(root)],
        "wide_guid": guid_text(read_wide_binding.get_id()),
    }
    with open(RECORD, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=1, sort_keys=True)
    unreal.log("S3_BEATS_DONE|run=%s|applied|backup=%s|census=%s" %
               (run, backup, json.dumps(census, separators=(",", ":"), sort_keys=True)))


def revert(root, clams, run):
    record = read_record(run)
    if record.get("world") != EXPECTED_WORLD:
        stop(run, "reason=RECORD_WORLD_MISMATCH")
    if cut_rows(root) != record.get("after", {}).get("root_cuts") or \
            cut_rows(clams) != record.get("after", {}).get("nested_cuts") or \
            [list(row) for row in marker_rows(root)] != record.get("after", {}).get("markers"):
        stop(run, "reason=CURRENT_STATE_DOES_NOT_MATCH_RECORDED_AFTER")
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    stamp = datetime.datetime.now()
    backup, _ = backup_assets(project, "PreS3BeatsRevert-", stamp, run)

    wide_track, wide_cut, wide_binding = one_cut(root, WIDE_NAME, run)
    _, root_clam, _ = one_cut(root, CLAM_NAME, run)
    _, nested_clam, _ = one_cut(clams, CLAM_NAME, run)
    wide_track.remove_section(wide_cut)
    extensions = getattr(unreal, "MovieSceneBindingExtensions", None)
    if extensions is None or not hasattr(extensions, "remove"):
        stop(run, "reason=BINDING_REMOVE_UNAVAILABLE")
    extensions.remove(wide_binding)
    root_clam.set_is_active(bool(next(row["active"] for row in record["before"]["root_cuts"]
                                           if row["binding"] == CLAM_NAME)))
    nested_clam.set_is_active(bool(next(row["active"] for row in record["before"]["nested_cuts"]
                                             if row["binding"] == CLAM_NAME)))
    replace_markers(root, record["before"]["markers"])

    if cut_rows(root) != record["before"]["root_cuts"] or \
            cut_rows(clams) != record["before"]["nested_cuts"] or \
            [list(row) for row in marker_rows(root)] != record["before"]["markers"]:
        stop(run, "reason=REVERT_READBACK")
    exact_dirty(run)
    census = exact_save(root, clams, run)
    archived = RECORD + ".reverted-" + stamp.strftime("%Y%m%d-%H%M%S")
    os.rename(RECORD, archived)
    unreal.log("S3_BEATS_DONE|run=%s|reverted|backup=%s|record=%s|census=%s" %
               (run, backup, os.path.basename(archived),
                json.dumps(census, separators=(",", ":"), sort_keys=True)))


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    apply = bool(globals().get("S3_BEATS_APPLY"))
    do_revert = bool(globals().get("S3_BEATS_REVERT"))
    if apply and do_revert:
        stop(run, "reason=APPLY_AND_REVERT_BOTH_SET")
    _context(run, do_revert, apply)
    root = unreal.load_asset(ROOT_PATH)
    clams = unreal.load_asset(CLAMS_PATH)
    if root is None or clams is None:
        stop(run, "reason=SEQUENCE_LOAD_FAILED")
    if do_revert:
        revert(root, clams, run)
        return
    try:
        plan = plan_beats(live_state(root, clams, run))
    except PlanError as exc:
        stop(run, "reason=PLAN_REFUSED|detail=" + str(exc))
    compact = json.dumps(plan, separators=(",", ":"), sort_keys=True)
    if not apply:
        census = package_census()
        if census["maps"] or census["content"]:
            stop(run, "reason=DRY_RUN_DIRTIED_PACKAGES|census=" + json.dumps(census, sort_keys=True))
        unreal.log("S3_BEATS_DRY_RUN_OK|run=%s|mutated=0|plan=%s" % (run, compact))
        return
    apply_plan(root, clams, plan, run)


if unreal is not None:
    main()
