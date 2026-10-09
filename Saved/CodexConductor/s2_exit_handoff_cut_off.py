"""Guarded DRY/APPLY/REVERT for the Scene 2 root exit-handoff camera cut.

APPLY deactivates exactly one camera-cut section; it never removes a section.
APPLY and REVERT save only LS_DevScene_02.  DRY is read-only and reports every
root camera cut plus the root sequence's nested-shot coverage.
"""
from __future__ import print_function

import datetime
import hashlib
import json
import os
import re
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness imports the planner.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ROOT_PATH = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_02"
TARGET_CAMERA = "Scene 2 \u2014 External Sound \u2014 Exit Handoff Camera"
TARGET_RANGE = [3866, 3891]
NESTED_PATH = "/Game/InfinityStage/KlaraHookin/LS_NEW_SHRINE_S2Hangar"
NESTED_FINAL_CAMERA = "CineCameraActor2"
NESTED_END = 3892
APPLY_CONFIRM = "DEACTIVATE S2 EXIT HANDOFF CUT"
REVERT_CONFIRM = "REACTIVATE S2 EXIT HANDOFF CUT"

if unreal is not None:
    HERE = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexConductor",
    )
else:
    HERE = os.path.dirname(os.path.abspath(__file__))

ARGS_PATH = os.path.join(HERE, "s2_exit_handoff_cut_off_args.json")
PLAN_PATH = os.path.join(HERE, "s2_exit_handoff_cut_off_plan.json")
RECORD_PATH = os.path.join(HERE, "s2_exit_handoff_cut_off_record.json")


class PlanError(ValueError):
    pass


def plan_change(state):
    """Pure planner used by both the live tool and the offline harness."""
    root_cuts = list(state.get("root_cuts") or [])
    if len(root_cuts) != 2:
        raise PlanError("ROOT_CUT_COUNT|got=%d|want=2" % len(root_cuts))
    matches = [row for row in root_cuts
               if row.get("camera") == TARGET_CAMERA
               and list(row.get("range") or []) == TARGET_RANGE]
    if len(matches) != 1:
        raise PlanError("TARGET_COUNT|got=%d|want=1" % len(matches))
    target = matches[0]
    if not target.get("binding_guid"):
        raise PlanError("TARGET_GUID_EMPTY")
    if not bool(target.get("active")):
        raise PlanError("TARGET_ALREADY_INACTIVE")
    nested = [row for row in list(state.get("nested_coverage") or [])
              if row.get("sequence") == NESTED_PATH
              and bool(row.get("active"))
              and int((row.get("range") or [0, -1])[1]) == NESTED_END
              and row.get("final_camera") == NESTED_FINAL_CAMERA]
    if len(nested) != 1:
        raise PlanError("NESTED_COVERAGE_COUNT|got=%d|want=1" % len(nested))
    return {
        "asset": ROOT_PATH,
        "operation": "set_is_active(False)",
        "target": dict(target),
        "nested_coverage": dict(nested[0]),
    }


def _write_json(path, value, exclusive=False):
    mode = "x" if exclusive else "w"
    with open(path, mode, encoding="utf-8") as handle:
        json.dump(value, handle, indent=1, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _package_path(value):
    return str(value.get_path_name()).split(".", 1)[0]


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {
        "content": sorted(_package_path(p) for p in lib.get_dirty_content_packages()),
        "maps": sorted(_package_path(p) for p in lib.get_dirty_map_packages()),
    }


def stop(run, reason):
    unreal.log_error("S2_EXIT_CUT_STOPPED|run=%s|%s" % (run, reason))
    raise RuntimeError(reason)


def guid_text(value):
    """Stable FGuid text; never use str(FGuid), which is a wrapper address."""
    try:
        return str(unreal.GuidLibrary.conv_guid_to_string(value))
    except Exception:
        return str(value.export_text())


def section_range(section):
    return [
        int(section.get_start_frame()) if section.has_start_frame() else None,
        int(section.get_end_frame()) if section.has_end_frame() else None,
    ]


def binding_names(sequence):
    return {guid_text(binding.get_id()): str(binding.get_display_name())
            for binding in sequence.get_bindings()}


def one_cut_track(sequence, run):
    tracks = list(sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack))
    if len(tracks) != 1:
        stop(run, "CUT_TRACK_COUNT|got=%d|want=1" % len(tracks))
    return tracks[0]


def camera_cuts(sequence, cut_track):
    if cut_track is None:  # [meas B1M-S2EXITCUT-DRY-20261009-100440] nested sequences may have no Camera Cuts track
        return []
    names = binding_names(sequence)
    rows = []
    for index, section in enumerate(cut_track.get_sections()):
        object_id = section.get_camera_binding_id()
        identity = guid_text(object_id.get_editor_property("guid"))
        rows.append({
            "section_index": index,
            "range": section_range(section),
            "active": bool(section.is_active()),
            "binding_guid": identity,
            "camera": names.get(identity),
        })
    return rows


def final_camera(sequence, depth=0):
    if sequence is None or depth > 4:
        return None
    end = int(sequence.get_playback_end())
    cuts = [row for row in camera_cuts(sequence, one_cut_track_soft(sequence))
            if row["active"] and row["range"][0] <= end - 1 < row["range"][1]]
    if len(cuts) == 1:
        return cuts[0]["camera"]
    nested = nested_coverage(sequence, depth + 1)
    tails = [row for row in nested
             if row["active"] and row["range"][0] <= end - 1 < row["range"][1]]
    return tails[0].get("final_camera") if len(tails) == 1 else None


def one_cut_track_soft(sequence):
    tracks = list(sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack))
    if len(tracks) != 1:
        return None
    return tracks[0]


def nested_coverage(sequence, depth=0):
    rows = []
    for track_index, track in enumerate(sequence.get_tracks()):
        if track.get_class().get_name() not in (
                "MovieSceneSubTrack", "MovieSceneCinematicShotTrack"):
            continue
        for section_index, section in enumerate(track.get_sections()):
            sub = section.get_sequence()
            rows.append({
                "track_index": track_index,
                "section_index": section_index,
                "track_class": track.get_class().get_name(),
                "range": section_range(section),
                "active": bool(section.is_active()),
                "sequence": _package_path(sub) if sub else None,
                "final_camera": final_camera(sub, depth + 1) if sub else None,
            })
    return rows


def live_state(sequence, cut_track):
    return {
        "root_cuts": camera_cuts(sequence, cut_track),
        "nested_coverage": nested_coverage(sequence),
    }


def state_digest(state):
    payload = json.dumps(state, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_context(run):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        stop(run, "PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    if world is None or _package_path(world) != EXPECTED_WORLD:
        stop(run, "WRONG_WORLD|got=%s" % (_package_path(world) if world else None))
    current = census()
    if current != {"content": [], "maps": []}:
        stop(run, "DIRTY_BEFORE|census=" + json.dumps(current, sort_keys=True))


def locate_target(sequence, cut_track, expected, run):
    rows = camera_cuts(sequence, cut_track)
    matches = [(section, row) for section, row in zip(cut_track.get_sections(), rows)
               if row["camera"] == TARGET_CAMERA and row["range"] == TARGET_RANGE]
    if len(matches) != 1:
        stop(run, "TARGET_COUNT_LIVE|got=%d|want=1" % len(matches))
    section, row = matches[0]
    if row != expected:
        stop(run, "TARGET_DRIFT|got=%s|want=%s" % (
            json.dumps(row, sort_keys=True), json.dumps(expected, sort_keys=True)))
    return section


def asset_filename():
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.join(project, "Content", *ROOT_PATH[len("/Game/"):].split("/")) + ".uasset"


def backup_asset(run, revert=False):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    safe_run = re.sub(r"[^A-Za-z0-9_.-]", "_", run)
    prefix = "PreS2ExitHandoffCutOffRevert-" if revert else "PreS2ExitHandoffCutOff-"
    backup = os.path.join(project, "Backups", prefix + safe_run)
    if os.path.exists(backup):
        stop(run, "BACKUP_EXISTS|path=" + backup)
    source = asset_filename()
    if not os.path.isfile(source):
        stop(run, "BACKUP_SOURCE_MISSING|path=" + source)
    relative = os.path.relpath(source, os.path.join(project, "Content"))
    destination = os.path.join(backup, "Content", relative)
    os.makedirs(os.path.dirname(destination), exist_ok=False)
    shutil.copy2(source, destination)
    return backup, relative.replace("\\", "/")


def require_exact_dirty(run):
    current = census()
    expected = {"content": [ROOT_PATH], "maps": []}
    if current != expected:
        stop(run, "DIRTY_AFTER_MUTATION|got=%s|want=%s" % (
            json.dumps(current, sort_keys=True), json.dumps(expected, sort_keys=True)))
    return current


def save_only_root(run):
    if not unreal.EditorAssetLibrary.save_asset(ROOT_PATH, only_if_is_dirty=False):
        stop(run, "SAVE_FAILED|asset=" + ROOT_PATH)
    current = census()
    if current != {"content": [], "maps": []}:
        stop(run, "DIRTY_AFTER_SAVE|census=" + json.dumps(current, sort_keys=True))
    return current


def dry(run, sequence, cut_track):
    state = live_state(sequence, cut_track)
    report = {
        "schema": "s2_exit_handoff_cut_off_dry/1",
        "run": run,
        "written_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "asset": ROOT_PATH,
        "census": census(),
        "root_cuts": state["root_cuts"],
        "nested_coverage": state["nested_coverage"],
        "state_digest": state_digest(state),
    }
    try:
        report["plan"] = plan_change(state)
        report["apply_ready"] = True
        report["refusals"] = []
    except PlanError as exc:
        report["apply_ready"] = False
        report["refusals"] = [str(exc)]
    path = os.path.join(HERE, "s2_exit_handoff_cut_off_dry_%s.json" % run)
    _write_json(path, report)
    _write_json(PLAN_PATH, report)
    if census() != {"content": [], "maps": []}:
        stop(run, "DRY_DIRTIED_PACKAGES|census=" + json.dumps(census(), sort_keys=True))
    marker = "S2_EXIT_CUT_DRY_OK" if report["apply_ready"] else "S2_EXIT_CUT_DRY_REFUSED"
    unreal.log("%s|run=%s|apply_ready=%d|root_cuts=%d|nested=%d|file=%s" % (
        marker, run, int(report["apply_ready"]), len(report["root_cuts"]),
        len(report["nested_coverage"]), path))


def apply(run, args, sequence, cut_track):
    if str(args.get("confirm") or "") != APPLY_CONFIRM:
        stop(run, "CONFIRM_MISMATCH|want=" + APPLY_CONFIRM)
    dry_run = str(args.get("dry_run") or "")
    dry_path = os.path.join(HERE, "s2_exit_handoff_cut_off_dry_%s.json" % dry_run)
    if not dry_run or not os.path.isfile(dry_path):
        stop(run, "DRY_REPORT_MISSING|dry_run=" + dry_run)
    report = _read_json(dry_path)
    if not report.get("apply_ready") or report.get("asset") != ROOT_PATH:
        stop(run, "DRY_NOT_APPLY_READY|dry_run=" + dry_run)
    if os.path.exists(RECORD_PATH):
        stop(run, "RECORD_ALREADY_EXISTS")
    state = live_state(sequence, cut_track)
    if state_digest(state) != report.get("state_digest"):
        stop(run, "DRY_STATE_DRIFT|dry_run=" + dry_run)
    plan = plan_change(state)
    section = locate_target(sequence, cut_track, plan["target"], run)
    backup, copied = backup_asset(run)
    record = {
        "schema": "s2_exit_handoff_cut_off_record/1",
        "status": "prepared",
        "written_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "run": run,
        "dry_run": dry_run,
        "world": EXPECTED_WORLD,
        "asset": ROOT_PATH,
        "backup": backup,
        "backup_file": copied,
        "before": state,
        "before_digest": state_digest(state),
        "target": plan["target"],
    }
    _write_json(RECORD_PATH, record, exclusive=True)
    try:
        sequence.modify()
        section.set_is_active(False)
        after = live_state(sequence, cut_track)
        changed = [row for row in after["root_cuts"]
                   if row["camera"] == TARGET_CAMERA and row["range"] == TARGET_RANGE]
        if len(changed) != 1 or changed[0]["active"]:
            raise RuntimeError("TARGET_READBACK_NOT_INACTIVE")
        expected_after = json.loads(json.dumps(state))
        expected_after["root_cuts"][plan["target"]["section_index"]]["active"] = False
        if after != expected_after:
            raise RuntimeError("NON_TARGET_STATE_CHANGED")
        dirty = require_exact_dirty(run)
        post_save = save_only_root(run)
        readback = live_state(sequence, cut_track)
        if readback != expected_after:
            raise RuntimeError("POST_SAVE_READBACK_MISMATCH")
        record.update({"status": "applied", "after": readback,
                       "after_digest": state_digest(readback),
                       "dirty_before_save": dirty, "post_save_census": post_save})
        _write_json(RECORD_PATH, record)
    except Exception as exc:
        try:
            section.set_is_active(True)
            unreal.EditorAssetLibrary.save_asset(ROOT_PATH, only_if_is_dirty=False)
            record.update({"status": "apply_failed_restored", "failure": str(exc),
                           "containment_census": census()})
            _write_json(RECORD_PATH, record)
        finally:
            stop(run, "APPLY_FAILED_RESTORED|detail=" + str(exc))
    unreal.log("S2_EXIT_CUT_APPLY_OK|run=%s|dry_run=%s|active=0|saved=%s|backup=%s|dirty=0" % (
        run, dry_run, ROOT_PATH, backup))


def revert(run, args, sequence, cut_track):
    if str(args.get("confirm") or "") != REVERT_CONFIRM:
        stop(run, "CONFIRM_MISMATCH|want=" + REVERT_CONFIRM)
    if not os.path.isfile(RECORD_PATH):
        stop(run, "RECORD_MISSING")
    record = _read_json(RECORD_PATH)
    if record.get("status") != "applied" or record.get("world") != EXPECTED_WORLD \
            or record.get("asset") != ROOT_PATH:
        stop(run, "RECORD_CONTEXT_OR_STATUS_MISMATCH")
    state = live_state(sequence, cut_track)
    if state_digest(state) != record.get("after_digest"):
        stop(run, "APPLIED_STATE_DRIFT")
    target = dict(record["target"])
    target["active"] = False
    section = locate_target(sequence, cut_track, target, run)
    backup, _ = backup_asset(run, revert=True)
    try:
        sequence.modify()
        section.set_is_active(True)
        restored = live_state(sequence, cut_track)
        if state_digest(restored) != record.get("before_digest"):
            raise RuntimeError("BEFORE_STATE_NOT_RESTORED")
        dirty = require_exact_dirty(run)
        post_save = save_only_root(run)
        if state_digest(live_state(sequence, cut_track)) != record.get("before_digest"):
            raise RuntimeError("POST_SAVE_REVERT_READBACK_MISMATCH")
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        record.update({"status": "reverted", "revert_run": run, "revert_backup": backup,
                       "revert_dirty_before_save": dirty,
                       "revert_post_save_census": post_save})
        archived = RECORD_PATH + ".reverted-" + stamp
        _write_json(RECORD_PATH, record)
        os.rename(RECORD_PATH, archived)
    except Exception as exc:
        try:
            section.set_is_active(False)
            unreal.EditorAssetLibrary.save_asset(ROOT_PATH, only_if_is_dirty=False)
        finally:
            stop(run, "REVERT_FAILED_RESTORED_APPLIED|detail=" + str(exc))
    unreal.log("S2_EXIT_CUT_REVERT_OK|run=%s|active=1|saved=%s|backup=%s|record=%s|dirty=0" % (
        run, ROOT_PATH, backup, archived))


def main():
    if not os.path.isfile(ARGS_PATH):
        raise RuntimeError("S2_EXIT_CUT_STOPPED|ARGS_MISSING")
    args = _read_json(ARGS_PATH)
    mode = str(args.get("mode") or "DRY").upper()
    run = str(args.get("run") or "").strip()
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_.-]{5,100}$", run):
        raise RuntimeError("S2_EXIT_CUT_STOPPED|INVALID_RUN")
    if mode not in ("DRY", "APPLY", "REVERT"):
        stop(run, "INVALID_MODE|mode=" + mode)
    validate_context(run)
    sequence = unreal.load_asset(ROOT_PATH)
    if sequence is None:
        stop(run, "SEQUENCE_LOAD_FAILED")
    cut_track = one_cut_track(sequence, run)
    if mode == "DRY":
        dry(run, sequence, cut_track)
    elif mode == "APPLY":
        apply(run, args, sequence, cut_track)
    else:
        revert(run, args, sequence, cut_track)


if unreal is not None:
    try:
        main()
    except Exception as exc:
        if "S2_EXIT_CUT_STOPPED" not in str(exc):
            unreal.log_error("S2_EXIT_CUT_FAILED|%s: %s" % (type(exc).__name__, exc))
        raise
