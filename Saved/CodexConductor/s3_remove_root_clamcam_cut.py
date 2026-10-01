"""Dry-run, apply, or revert removal of the retired root ClamCam1 cut.

Dry run is the default.  The dedicated wrappers beside this file are the only
intended way to set S3_CLAMCUT_APPLY or S3_CLAMCUT_REVERT.  Pure planning
helpers remain importable by test_s3_remove_root_clamcam_cut.py without Unreal.

This tool never opens or evaluates Sequencer, loads a level, enters PIE, or
saves a map.  Apply/revert save exactly LS_DevScene_03.
"""
import datetime
import json
import os
import re
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline planning harness.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ROOT_PATH = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
CLAM_NAME = "ClamCam1"
EXPECTED_RANGE = [81, 1501]

if unreal is not None:
    HERE = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexConductor",
    )
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
RECORD = os.path.join(HERE, "s3_remove_root_clamcam_cut_record.json")


class PlanError(ValueError):
    pass


def plan_removal(state):
    """Return the deterministic removal plan from an Unreal-free state dict."""
    matches = list(state.get("matches", []))
    if len(matches) != 1:
        raise PlanError("root ClamCam1 cut count is %d, expected 1" % len(matches))
    target = matches[0]
    if bool(target.get("active")):
        raise PlanError("root ClamCam1 cut is active")
    target_range = list(target.get("range", []))
    if target_range != EXPECTED_RANGE:
        raise PlanError("root ClamCam1 cut range is %r, expected %r" %
                        (target_range, EXPECTED_RANGE))
    binding_guid = str(target.get("binding_guid") or "")
    if not binding_guid:
        raise PlanError("root ClamCam1 cut has no binding GUID")
    if not bool(target.get("binding_exists")):
        raise PlanError("root ClamCam1 binding does not exist")
    return {
        "asset": ROOT_PATH,
        "binding": CLAM_NAME,
        "binding_guid": binding_guid,
        "range": list(EXPECTED_RANGE),
        "active": False,
        "operations": [{"op": "remove_section", "target": "root ClamCam1 cut"}],
    }


def _package_path(value):
    return str(value.get_path_name()).split(".", 1)[0]


def package_census():
    return {
        "maps": sorted(_package_path(p) for p in
                       unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
        "content": sorted(_package_path(p) for p in
                          unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    }


def stop(run, reason):
    unreal.log_error("S3_CLAMCUT_STOPPED|run=%s|%s" % (run, reason))
    raise RuntimeError(reason)


def guid_text(value):
    return str(unreal.GuidLibrary.conv_guid_to_string(value))


def binding_map(sequence):
    return {guid_text(binding.get_id()): binding for binding in sequence.get_bindings()}


def one_cut_track(sequence, run):
    tracks = list(sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack))
    if len(tracks) != 1:
        stop(run, "reason=CUT_TRACK_COUNT|asset=%s|count=%d" %
             (_package_path(sequence), len(tracks)))
    return tracks[0]


def section_range(section):
    return [
        int(section.get_start_frame()) if section.has_start_frame() else None,
        int(section.get_end_frame()) if section.has_end_frame() else None,
    ]


def target_candidates(sequence, cut_track):
    bindings = binding_map(sequence)
    found = []
    for section in cut_track.get_sections():
        camera_id = section.get_camera_binding_id().get_editor_property("guid")
        identity = guid_text(camera_id)
        binding = bindings.get(identity)
        if binding is not None and str(binding.get_display_name()) == CLAM_NAME:
            found.append((section, binding, identity))
    return found


def live_plan_state(sequence, cut_track):
    rows = []
    for section, binding, identity in target_candidates(sequence, cut_track):
        rows.append({
            "range": section_range(section),
            "active": bool(section.is_active()),
            "binding_guid": identity,
            "binding_exists": binding is not None,
        })
    return {"matches": rows}


def one_target(sequence, cut_track, run):
    found = target_candidates(sequence, cut_track)
    if len(found) != 1:
        stop(run, "reason=TARGET_CUT_COUNT|asset=%s|count=%d" %
             (_package_path(sequence), len(found)))
    return found[0]


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
    # Scripting channel proxies are renumbered on every read.  Compare the
    # stable part of Location.X_0 / MovieSceneScriptingFloatChannel_12.
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


def section_row(section, camera_guid=None):
    return {
        "range": section_range(section),
        "active": bool(section.is_active()),
        "camera_guid": camera_guid,
        "channels": [channel_row(channel) for channel in section.get_all_channels()],
    }


def track_row(track):
    row = {
        "class": track.get_class().get_name(),
        "name": str(track.get_display_name()),
        "sections": [],
    }
    for section in track.get_sections():
        camera_guid = None
        if isinstance(section, unreal.MovieSceneCameraCutSection):
            camera_guid = guid_text(
                section.get_camera_binding_id().get_editor_property("guid")
            )
        row["sections"].append(section_row(section, camera_guid))
    return row


def camera_snapshot(actor):
    # A spawnable camera template reads its pose from the unattached root's
    # relative transform.  get_actor_transform() is zero for that template, and
    # the reliable camera fallback is the camera_component property.
    root = actor.get_editor_property("root_component")
    if root is None or root.get_attach_parent() is not None:
        raise RuntimeError("reason=CAMERA_ROOT_UNREADABLE_OR_ATTACHED|actor=%s" %
                           actor.get_name())
    location = root.get_editor_property("relative_location")
    rotation = root.get_editor_property("relative_rotation")
    scale = root.get_editor_property("relative_scale3d")
    camera = actor.get_cine_camera_component() or actor.get_editor_property("camera_component")
    if camera is None:
        raise RuntimeError("reason=CINE_CAMERA_COMPONENT_UNREADABLE|actor=%s" %
                           actor.get_name())
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
        ("lens_settings", ("min_focal_length", "max_focal_length", "min_f_stop",
                           "max_f_stop", "minimum_focus_distance")),
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


def binding_fingerprint(sequence):
    spawnables = {guid_text(binding.get_id()) for binding in sequence.get_spawnables()}
    rows = []
    for binding in sequence.get_bindings():
        identity = guid_text(binding.get_id())
        row = {
            "guid": identity,
            "name": str(binding.get_display_name()),
            "spawnable": identity in spawnables,
            "tracks": [track_row(track) for track in binding.get_tracks()],
        }
        if identity in spawnables:
            template = binding.get_object_template()
            if template is not None and isinstance(template, unreal.CineCameraActor):
                row["camera_template"] = camera_snapshot(template)
        rows.append(row)
    return sorted(rows, key=lambda item: item["guid"])


def other_cut_fingerprint(cut_track, excluded_guid=None):
    # Exclude by camera binding GUID, never by wrapper equality: get_sections() returns fresh
    # wrappers each call, so `section == excluded_section` left the ClamCam1 row in "before"
    # and tripped OTHER_CUTS_CHANGED after a correct removal (run 154306). Sorted, so section
    # order cannot matter either.
    rows = []
    for section in cut_track.get_sections():
        identity = guid_text(section.get_camera_binding_id().get_editor_property("guid"))
        if excluded_guid is not None and identity == excluded_guid:
            continue
        rows.append(section_row(section, identity))
    return strip_guid(rows, excluded_guid)


def strip_guid(rows, excluded_guid):
    rows = [row for row in (rows or []) if excluded_guid is None or row.get("camera_guid") != excluded_guid]
    return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True))


def _context(run, do_revert, apply):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        stop(run, "reason=PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    if world is None or world.get_outermost().get_name() != EXPECTED_WORLD:
        stop(run, "reason=WRONG_WORLD")
    census = package_census()
    if census["maps"] or census["content"]:
        stop(run, "reason=DIRTY_BEFORE|census=" + json.dumps(census, sort_keys=True))
    if do_revert and not os.path.exists(RECORD):
        stop(run, "reason=REVERT_RECORD_ABSENT")
    if apply and os.path.exists(RECORD):
        stop(run, "reason=APPLY_RECORD_ALREADY_EXISTS")


def _asset_filename(project, package):
    return os.path.join(project, "Content", *package[len("/Game/"):].split("/")) + ".uasset"


def backup_asset(project, prefix, stamp, run):
    backup = os.path.join(project, "Backups", prefix + stamp.strftime("%Y%m%d-%H%M"))
    if os.path.exists(backup):
        stop(run, "reason=BACKUP_EXISTS|path=" + backup)
    source = _asset_filename(project, ROOT_PATH)
    if not os.path.isfile(source):
        stop(run, "reason=BACKUP_SOURCE_MISSING|file=" + source)
    content = os.path.join(project, "Content")
    relative = os.path.relpath(source, content)
    destination = os.path.join(backup, "Content", relative)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    shutil.copy2(source, destination)
    return backup, relative.replace("\\", "/")


def write_record(record, run):
    try:
        with open(RECORD, "x", encoding="utf-8") as handle:
            json.dump(record, handle, indent=1, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception as exc:
        stop(run, "reason=RECORD_WRITE_FAILED|detail=" + str(exc))


def update_record(record, run):
    try:
        with open(RECORD, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=1, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception as exc:
        stop(run, "reason=RECORD_UPDATE_FAILED|detail=" + str(exc))


def read_record(run):
    try:
        with open(RECORD, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        stop(run, "reason=RECORD_READ_FAILED|detail=" + str(exc))


def exact_dirty(run):
    census = package_census()
    if census["maps"] or census["content"] != [ROOT_PATH]:
        stop(run, "reason=DIRTY_CENSUS|census=" + json.dumps(census, sort_keys=True))
    return census


def exact_save(run):
    saved = bool(unreal.EditorAssetLibrary.save_asset(ROOT_PATH, only_if_is_dirty=False))
    if not saved:
        stop(run, "reason=SAVE_FAILED|asset=" + ROOT_PATH)
    census = package_census()
    if census["maps"] or census["content"]:
        stop(run, "reason=POST_SAVE_DIRTY|census=" + json.dumps(census, sort_keys=True))
    return census


def verify_removed(sequence, cut_track, other_cuts, bindings, binding_guid, run):
    if target_candidates(sequence, cut_track):
        stop(run, "reason=CLAM_CUT_STILL_PRESENT")
    if other_cut_fingerprint(cut_track, binding_guid) != strip_guid(other_cuts, binding_guid):
        stop(run, "reason=OTHER_CUTS_CHANGED")
    if binding_fingerprint(sequence) != bindings:
        stop(run, "reason=BINDINGS_CHANGED")
    binding = binding_map(sequence).get(binding_guid)
    if binding is None or str(binding.get_display_name()) != CLAM_NAME:
        stop(run, "reason=CLAM_BINDING_MISSING")
    return binding


def apply_plan(sequence, cut_track, plan, run):
    section, binding, identity = one_target(sequence, cut_track, run)
    if identity != plan["binding_guid"] or section_range(section) != plan["range"] or \
            bool(section.is_active()) != plan["active"]:
        stop(run, "reason=TARGET_CHANGED_AFTER_PLAN")

    other_cuts = other_cut_fingerprint(cut_track, excluded_guid=identity)
    bindings = binding_fingerprint(sequence)
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    stamp = datetime.datetime.now()
    backup, copied = backup_asset(project, "PreS3RemoveClamCut-", stamp, run)
    record = {
        "written": stamp.isoformat(timespec="seconds"),
        "run": run,
        "world": EXPECTED_WORLD,
        "asset": ROOT_PATH,
        "backup": backup,
        "backup_file": copied,
        "target": {
            "range": list(plan["range"]),
            "active": bool(plan["active"]),
            "binding_guid": identity,
        },
        "before": {
            "other_cut_sections": other_cuts,
            "bindings": bindings,
        },
    }
    write_record(record, run)

    cut_track.remove_section(section)
    verify_removed(sequence, cut_track, other_cuts, bindings, identity, run)
    dirty = exact_dirty(run)
    census = exact_save(run)
    verify_removed(sequence, cut_track, other_cuts, bindings, identity, run)
    record["after"] = {
        "other_cut_sections": other_cut_fingerprint(cut_track, excluded_guid=identity),
        "bindings": binding_fingerprint(sequence),
        "dirty_before_save": dirty,
        "post_save_census": census,
    }
    update_record(record, run)
    unreal.log("S3_CLAMCUT_DONE|run=%s|applied|backup=%s|census=%s" %
               (run, backup, json.dumps(census, separators=(",", ":"), sort_keys=True)))


def revert(sequence, cut_track, run):
    record = read_record(run)
    if record.get("world") != EXPECTED_WORLD or record.get("asset") != ROOT_PATH:
        stop(run, "reason=RECORD_CONTEXT_MISMATCH")
    target = record.get("target", {})
    other_cuts = record.get("before", {}).get("other_cut_sections")
    bindings = record.get("before", {}).get("bindings")
    identity = str(target.get("binding_guid") or "")
    if list(target.get("range", [])) != EXPECTED_RANGE or bool(target.get("active")):
        stop(run, "reason=RECORD_TARGET_MISMATCH")
    binding = verify_removed(sequence, cut_track, other_cuts, bindings, identity, run)

    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    stamp = datetime.datetime.now()
    backup, _ = backup_asset(project, "PreS3RemoveClamCutRevert-", stamp, run)

    section = cut_track.add_section()
    section.set_camera_binding_id(sequence.get_binding_id(binding))
    # Intentional single range call.  Never split this into start/end setters.
    section.set_range(target["range"][0], target["range"][1])
    section.set_is_active(bool(target["active"]))

    matches = target_candidates(sequence, cut_track)
    if len(matches) != 1:
        stop(run, "reason=REVERT_TARGET_COUNT|count=%d" % len(matches))
    read_section, read_binding, read_identity = matches[0]
    if read_identity != identity or read_binding is None or \
            section_range(read_section) != EXPECTED_RANGE or read_section.is_active():
        stop(run, "reason=REVERT_TARGET_READBACK")
    if other_cut_fingerprint(cut_track, excluded_guid=identity) != strip_guid(other_cuts, identity):
        stop(run, "reason=REVERT_OTHER_CUTS_CHANGED")
    if binding_fingerprint(sequence) != bindings:
        stop(run, "reason=REVERT_BINDINGS_CHANGED")

    exact_dirty(run)
    census = exact_save(run)
    archived = RECORD + ".reverted-" + stamp.strftime("%Y%m%d-%H%M%S")
    os.rename(RECORD, archived)
    unreal.log("S3_CLAMCUT_DONE|run=%s|reverted|backup=%s|record=%s|census=%s" %
               (run, backup, os.path.basename(archived),
                json.dumps(census, separators=(",", ":"), sort_keys=True)))


def finish_unsaved(sequence, cut_track, run):
    # FINISH: an apply removed the section, then a guard fault stopped it before the save
    # (run 154306). Verify the UNSAVED state against the record with the fixed guards; save
    # only if every one passes. Nothing is changed here except the save.
    record = read_record(run)
    if record.get("world") != EXPECTED_WORLD or record.get("asset") != ROOT_PATH or "after" in record:
        stop(run, "reason=FINISH_RECORD_MISMATCH")
    target = record.get("target", {})
    identity = str(target.get("binding_guid") or "")
    if list(target.get("range", [])) != EXPECTED_RANGE or bool(target.get("active")):
        stop(run, "reason=FINISH_RECORD_TARGET_MISMATCH")
    before = record.get("before", {})
    verify_removed(sequence, cut_track, before.get("other_cut_sections"), before.get("bindings"), identity, run)
    dirty = exact_dirty(run)
    census = exact_save(run)
    verify_removed(sequence, cut_track, before.get("other_cut_sections"), before.get("bindings"), identity, run)
    record["after"] = {
        "other_cut_sections": other_cut_fingerprint(cut_track, excluded_guid=identity),
        "bindings": binding_fingerprint(sequence),
        "dirty_before_save": dirty,
        "post_save_census": census,
        "finished_by_run": run,
    }
    update_record(record, run)
    unreal.log("S3_CLAMCUT_DONE|run=%s|finished|apply_run=%s|backup=%s|census=%s" %
               (run, record.get("run"), record.get("backup"),
                json.dumps(census, separators=(",", ":"), sort_keys=True)))


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    apply = bool(globals().get("S3_CLAMCUT_APPLY"))
    do_revert = bool(globals().get("S3_CLAMCUT_REVERT"))
    finish = bool(globals().get("S3_CLAMCUT_FINISH"))
    if sum((apply, do_revert, finish)) > 1:
        stop(run, "reason=MORE_THAN_ONE_MODE_SET")
    if finish:
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        if editor.get_game_world() is not None:
            stop(run, "reason=PIE_OR_SIE_ACTIVE")
        sequence = unreal.load_asset(ROOT_PATH)
        if sequence is None:
            stop(run, "reason=SEQUENCE_LOAD_FAILED")
        finish_unsaved(sequence, one_cut_track(sequence, run), run)
        return
    _context(run, do_revert, apply)
    sequence = unreal.load_asset(ROOT_PATH)
    if sequence is None:
        stop(run, "reason=SEQUENCE_LOAD_FAILED")
    cut_track = one_cut_track(sequence, run)
    if do_revert:
        revert(sequence, cut_track, run)
        return
    try:
        plan = plan_removal(live_plan_state(sequence, cut_track))
    except PlanError as exc:
        stop(run, "reason=PLAN_REFUSED|detail=" + str(exc))
    compact = json.dumps(plan, separators=(",", ":"), sort_keys=True)
    if not apply:
        census = package_census()
        if census["maps"] or census["content"]:
            stop(run, "reason=DRY_RUN_DIRTIED_PACKAGES|census=" +
                 json.dumps(census, sort_keys=True))
        unreal.log("S3_CLAMCUT_DRY_RUN_OK|run=%s|mutated=0|plan=%s" % (run, compact))
        return
    apply_plan(sequence, cut_track, plan, run)


if unreal is not None:
    main()
