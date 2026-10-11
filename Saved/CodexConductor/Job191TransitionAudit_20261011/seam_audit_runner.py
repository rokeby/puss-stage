"""Job 191 read-only owned-PIE seam contact-sheet runner.

One invocation from a clean editor starts its own PIE, captures 64 audience-POV
stills across 16 Master boundaries, ends only that owned PIE, checks the dirty
census, and writes JSON plus one HTML contact sheet per seam. It never saves an
asset or level.

Markers: JOB191_SEAM_AUDIT_ARMED, JOB191_SEAM_FRAME,
JOB191_SEAM_AUDIT_OK, JOB191_SEAM_AUDIT_FAILED.
"""

from __future__ import annotations

import builtins
import datetime
import importlib
import json
import pathlib
import sys
import time
import traceback

import unreal


HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import seam_audit_core as core
importlib.reload(core)

ARGS = HERE / "seam_audit_args.json"
RUNS = HERE / "runs"
OWNER = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / "CodexConductor" / "pie_recording_owner.json"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HANDLE_NAME = "PUSS_JOB191_SEAM_AUDIT_HANDLE"
STATE_NAME = "PUSS_JOB191_SEAM_AUDIT_STATE"
BEGIN_TIMEOUT = 45.0
END_TIMEOUT = 45.0
REPOSE_TICKS = 30
SETTLE_TICKS = 45
FILE_TIMEOUT = 45.0
FILE_STABLE_TICKS = 4


def package_names(packages):
    return sorted(str(p.get_name()).split(".", 1)[0] for p in packages)


def census():
    return {"maps": package_names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
            "content": package_names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())}


def package_name(value):
    return str(value.get_path_name()).split(".", 1)[0]


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def write_json(path, value):
    text = json.dumps(value, indent=2, sort_keys=True, default=str)
    path.write_text(text, encoding="utf-8")
    if json.loads(path.read_text(encoding="utf-8")) != json.loads(text):
        raise RuntimeError("JSON read-back failed: %s" % path)


def write_owner(state, active, note):
    write_json(OWNER, {"active": bool(active), "owner": "Job191SeamAudit", "run_id": state["run"],
                       "run_dir": state["run_dir"], "note": note, "updated_utc": utc_now()})


def owner_active():
    if not OWNER.exists():
        return False
    try:
        return bool(json.loads(OWNER.read_text(encoding="utf-8")).get("active"))
    except Exception:
        return True


def vec(value):
    return [float(value.x), float(value.y), float(value.z)]


def camera_state(world):
    controller = unreal.GameplayStatics.get_player_controller(world, 0)
    manager = unreal.GameplayStatics.get_player_camera_manager(world, 0)
    if controller is None or manager is None:
        raise RuntimeError("player controller/camera manager did not resolve")
    target = controller.get_view_target()
    location, rotation = manager.get_camera_location(), manager.get_camera_rotation()
    return ({"location": vec(location),
             "rotation": {"pitch": float(rotation.pitch), "yaw": float(rotation.yaw), "roll": float(rotation.roll)},
             "fov_deg": float(manager.get_fov_angle())},
            {"path": str(target.get_path_name()) if target else None,
             "label": str(target.get_actor_label()) if target else None,
             "class": str(target.get_class().get_name()) if target else None})


def runtime_root(world):
    roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
    if len(roots) != 1 or roots[0].transport is None or roots[0].sequence_player is None:
        raise RuntimeError("expected one runtime Show Root, got %d" % len(roots))
    return roots[0]


def build_plan(root):
    segments = [{"label": str(segment.label), "start": int(segment.start_frame.value),
                 "end": int(segment.end_frame.value)} for segment in list(root.transport.segments)]
    return core.plan_seams(segments)


def flatten_samples(plan, shots_dir):
    rows = []
    for seam in plan["seams"]:
        for sample in seam["samples"]:
            name = "%02d_%s_%s.png" % (seam["order"], seam["kind"], sample["key"])
            sample["path"] = (shots_dir / name).as_posix()
            rows.append((seam, sample))
    return rows


def finish_files(state):
    flagged = 0
    for seam in state["plan"]["seams"]:
        seam["analysis"] = core.analyze_seam(seam, state["thresholds"])
        flagged += int(seam["analysis"]["flagged"])
        seam_dir = pathlib.Path(state["run_dir"]) / "seams" / seam["id"]
        seam_dir.mkdir(parents=True, exist_ok=False)
        (seam_dir / "contact_sheet.html").write_text(core.contact_sheet_html(seam), encoding="utf-8")
    state["flagged_seams"] = flagged
    state["captured_frames"] = sum(len(seam["samples"]) for seam in state["plan"]["seams"])
    (pathlib.Path(state["run_dir"]) / "index.html").write_text(
        core.index_html(state["run"], state["plan"]["seams"]), encoding="utf-8")
    write_json(pathlib.Path(state["run_dir"]) / "seam_audit_result.json",
               {key: value for key, value in state.items() if not key.startswith("_")})


def finalize(state):
    state["finished_utc"] = utc_now()
    state["dirty_after"] = census()
    if state["dirty_after"] != state["dirty_before"]:
        state["errors"].append("dirty census changed %r -> %r" % (state["dirty_before"], state["dirty_after"]))
    state["status"] = "passed" if not state["errors"] and state.get("captured_frames") == 64 else "failed"
    try:
        finish_files(state) if "captured_frames" not in state else write_json(
            pathlib.Path(state["run_dir"]) / "seam_audit_result.json",
            {key: value for key, value in state.items() if not key.startswith("_")})
    except Exception:
        state["errors"].append("final evidence write failed: " + traceback.format_exc())
        state["status"] = "failed"
    write_owner(state, False, "owned PIE ended; seam audit finalized with status %s" % state["status"])
    handle = getattr(builtins, HANDLE_NAME, None)
    if handle is not None:
        unreal.unregister_slate_post_tick_callback(handle)
        delattr(builtins, HANDLE_NAME)
    marker = "JOB191_SEAM_AUDIT_OK" if state["status"] == "passed" else "JOB191_SEAM_AUDIT_FAILED"
    unreal.log(("%s|run=%s|seams=%d|frames=%d|flagged=%d|dirty_maps=%d|dirty_content=%d|dir=%s" %
                (marker, state["run"], len(state.get("plan", {}).get("seams", [])), state.get("captured_frames", 0),
                 state.get("flagged_seams", 0), len(state["dirty_after"]["maps"]),
                 len(state["dirty_after"]["content"]), state["run_dir"])))


def request_stop(state, reason=None):
    if reason:
        state["errors"].append(reason)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world is not None and state.get("screen_messages_disabled"):
        unreal.SystemLibrary.execute_console_command(world, "EnableAllScreenMessages")
        state["screen_messages_disabled"] = False
    write_owner(state, True, "ending this run's owned PIE")
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    state["phase"] = "wait_end"
    state["phase_started"] = time.monotonic()


def arm():
    args = json.loads(ARGS.read_text(encoding="utf-8"))
    run, resolution, thresholds = core.validate_args(args)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        raise RuntimeError("JOB191_SEAM_AUDIT_FAILED|run=%s|PIE already active; refusing ownership" % run)
    world = editor.get_editor_world()
    if world is None or package_name(world) != EXPECTED_WORLD:
        raise RuntimeError("JOB191_SEAM_AUDIT_FAILED|run=%s|wrong editor world" % run)
    dirty = census()
    if dirty["maps"] or dirty["content"]:
        raise RuntimeError("JOB191_SEAM_AUDIT_FAILED|run=%s|dirty editor %r" % (run, dirty))
    if owner_active():
        raise RuntimeError("JOB191_SEAM_AUDIT_FAILED|run=%s|another PIE owner is active" % run)
    handles = sorted(name for name in dir(builtins) if name.startswith("PUSS_") and name.endswith("_HANDLE"))
    if handles:
        raise RuntimeError("JOB191_SEAM_AUDIT_FAILED|run=%s|tick handles armed %r" % (run, handles))
    run_dir = RUNS / run
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "shots").mkdir()
    state = {"schema": 1, "run": run, "run_dir": run_dir.as_posix(), "status": "starting_owned_pie",
             "phase": "wait_pie", "phase_started": time.monotonic(), "started_utc": utc_now(),
             "resolution": resolution, "thresholds": thresholds, "dirty_before": dirty, "errors": [],
             "screen_messages_disabled": False}
    write_owner(state, True, "Job 191 ownership armed before PIE start")
    write_json(run_dir / "seam_audit_result.json", {key: value for key, value in state.items() if not key.startswith("_")})

    def tick(_delta=0.0):
        if state.get("_inside") or state.get("status") in ("passed", "failed"):
            return
        state["_inside"] = True
        try:
            now = time.monotonic()
            game = editor.get_game_world()
            phase = state["phase"]
            if phase == "wait_pie":
                if game is None:
                    if now - state["phase_started"] > BEGIN_TIMEOUT:
                        state["errors"].append("owned PIE did not start within timeout")
                        state["phase"] = "wait_end"
                    return
                root = runtime_root(game)
                root.sequence_player.pause()
                state["plan"] = build_plan(root)
                state["_samples"] = flatten_samples(state["plan"], run_dir / "shots")
                state["sample_index"] = 0
                unreal.SystemLibrary.execute_console_command(game, "DisableAllScreenMessages")
                state["screen_messages_disabled"] = True
                state["phase"] = "scrub"
                state["status"] = "capturing"
                return
            if phase == "wait_end":
                if game is None:
                    finalize(state)
                elif now - state["phase_started"] > END_TIMEOUT:
                    state["errors"].append("owned PIE did not end within timeout")
                    finalize(state)
                return
            if game is None:
                state["errors"].append("owned PIE vanished during capture")
                state["phase"] = "wait_end"
                state["phase_started"] = now
                return
            root = runtime_root(game)
            seam, sample = state["_samples"][state["sample_index"]]
            if phase == "scrub":
                root.sequence_player.pause()
                result = root.transport.scrub_to_master_frame(unreal.FrameNumber(int(sample["target_frame"])))
                if "SUCCEEDED" not in str(result).upper():
                    request_stop(state, "scrub failed at %s: %s" % (sample["target_frame"], result))
                    return
                state["wait_ticks"] = REPOSE_TICKS
                state["phase"] = "repose"
                return
            if phase == "repose":
                state["wait_ticks"] -= 1
                if state["wait_ticks"] <= 0:
                    result = root.transport.scrub_to_master_frame(unreal.FrameNumber(int(sample["target_frame"])))
                    if "SUCCEEDED" not in str(result).upper():
                        request_stop(state, "re-scrub failed at %s: %s" % (sample["target_frame"], result))
                        return
                    state["wait_ticks"] = SETTLE_TICKS
                    state["phase"] = "settle"
                return
            if phase == "settle":
                state["wait_ticks"] -= 1
                if state["wait_ticks"] > 0:
                    return
                actual = int(root.transport.get_current_master_frame().value)
                if abs(actual - int(sample["target_frame"])) > 1:
                    request_stop(state, "frame drift before capture: target=%d actual=%d" % (sample["target_frame"], actual))
                    return
                camera, target = camera_state(game)
                sample.update(actual_frame=actual, camera=camera, view_target=target, captured_utc=utc_now())
                width, height = state["resolution"]
                command = 'HighResShot %dx%d filename="%s"' % (width, height, sample["path"])
                sample["command"] = command
                unreal.SystemLibrary.execute_console_command(game, command)
                state.update(phase="wait_file", file_started=now, last_size=-1, stable_ticks=0)
                return
            if phase == "wait_file":
                path = pathlib.Path(sample["path"])
                size = path.stat().st_size if path.is_file() else -1
                if size > 1000 and size == state["last_size"]:
                    state["stable_ticks"] += 1
                else:
                    state["stable_ticks"], state["last_size"] = 0, size
                if state["stable_ticks"] >= FILE_STABLE_TICKS:
                    sample["bytes"] = size
                    sample["mean_luminance"] = core.png_mean_luminance(path)
                    unreal.log("JOB191_SEAM_FRAME|run=%s|seam=%s|sample=%s|frame=%d|view=%s|luma=%.3f|path=%s" %
                               (state["run"], seam["id"], sample["key"], sample["actual_frame"],
                                sample["view_target"].get("label"), sample["mean_luminance"], sample["path"]))
                    state["sample_index"] += 1
                    if state["sample_index"] >= len(state["_samples"]):
                        finish_files(state)
                        request_stop(state)
                    else:
                        state["phase"] = "scrub"
                    return
                if now - state["file_started"] > FILE_TIMEOUT:
                    request_stop(state, "capture timeout: %s" % sample["path"])
                return
            request_stop(state, "unknown phase %s" % phase)
        except Exception:
            try:
                request_stop(state, traceback.format_exc())
            except Exception:
                state["errors"].append("failure while stopping: " + traceback.format_exc())
                finalize(state)
        finally:
            state["_inside"] = False

    handle = unreal.register_slate_post_tick_callback(tick)
    setattr(builtins, HANDLE_NAME, handle)
    setattr(builtins, STATE_NAME, state)
    result = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
    unreal.log("JOB191_SEAM_AUDIT_ARMED|run=%s|result=%s|dir=%s" % (run, result, run_dir.as_posix()))


try:
    arm()
except Exception as exc:
    if "JOB191_SEAM_AUDIT_FAILED|" not in str(exc):
        unreal.log_error("JOB191_SEAM_AUDIT_FAILED|%r" % (exc,))
    raise
