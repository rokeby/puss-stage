"""Owned floating-PIE still capture for the S3 beach at reviewed beat times."""
import builtins
import datetime
import json
import pathlib
import time
import traceback

import unreal


BASE = pathlib.Path("E:/PussStage/Saved/CodexConductor")
PROFILE = str(globals().get("S3_CAPTURE_PROFILE", "legacy"))
OUT_ROOT = (BASE / "S3Daylight") if PROFILE in ("daylight", "waves") else (BASE / "S3BeachStills" / "PIE")
CURRENT = BASE / "pie_recording_current_run.json"
OWNER = BASE / "pie_recording_owner.json"
SEQUENCE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HANDLE_NAME = "PUSS_S3_BEACH_PIE_STILLS_HANDLE"
STATE_NAME = "PUSS_S3_BEACH_PIE_STILLS_STATE"
MASTER_TICKS_PER_SECOND = 24000
DISPLAY_FRAMES_PER_SECOND = 24


def package_names(packages):
    return sorted(str(package.get_name()).split(".", 1)[0] for package in packages)


def persist(state):
    pathlib.Path(state["run_dir"], "runtime_result.json").write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )


def write_owner(state, active, note):
    OWNER.write_text(json.dumps({
        "active": active,
        "note": note,
        "run_dir": state["run_dir"],
        "run_id": state["run_id"],
        "started_utc": state["started_utc"],
        "updated_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    }, indent=2), encoding="utf-8")


def owner_matches(state):
    current = json.loads(OWNER.read_text(encoding="utf-8"))
    return bool(current.get("active")) and current.get("run_dir") == state["run_dir"] \
        and current.get("run_id") == state["run_id"]


def unregister():
    if hasattr(builtins, HANDLE_NAME):
        unreal.unregister_slate_post_tick_callback(getattr(builtins, HANDLE_NAME))
        delattr(builtins, HANDLE_NAME)


def finalize(state, status, error=None):
    if error:
        state["errors"].append(error)
    state["finished_utc"] = datetime.datetime.now(datetime.UTC).isoformat()
    state["dirty_maps_after"] = package_names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    state["dirty_content_after"] = package_names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    for job in state.get("jobs", []):
        path = pathlib.Path(job["path"])
        job["exists"] = path.is_file()
        job["bytes"] = path.stat().st_size if path.is_file() else 0
        if not job["exists"] or job["bytes"] <= 1000:
            state["errors"].append("missing or undersized still: " + job["path"])
    if state["dirty_maps_after"] or state["dirty_content_after"]:
        state["errors"].append("post-PIE census dirty")
    if state["errors"]:
        status = "failed"
    state["status"] = status
    write_owner(state, False, "this run's owned PIE ended; post-PIE census recorded")
    persist(state)
    unregister()
    unreal.log("S3_BEACH_PIE_STILLS_COMPLETE|run=%s|status=%s|files=%d|dirty_maps=%d|dirty_content=%d|run_dir=%s" %
               (state["run_id"], status, sum(1 for row in state.get("jobs", []) if row.get("exists")),
                len(state["dirty_maps_after"]), len(state["dirty_content_after"]), state["run_dir"]))


def restore_messages(world, state):
    if world is not None and state.get("screen_messages_disabled"):
        unreal.SystemLibrary.execute_console_command(world, "EnableAllScreenMessages")
        state["screen_messages_disabled"] = False
        state["screen_messages_restored"] = True


def request_end_our_pie(state, status, error=None, world=None):
    if error:
        state["errors"].append(error)
    restore_messages(world, state)
    if not state.get("pie_observed"):
        finalize(state, "failed", "refused to end PIE: this run never observed its game world")
        return
    if not owner_matches(state):
        finalize(state, "failed", "refused to end PIE: ownership flag no longer matches this run")
        return
    state["final_status"] = status
    state["status"] = "stopping_owned_pie"
    state["stop_requested_wall"] = time.monotonic()
    write_owner(state, True, "end requested for this run's observed owned PIE")
    persist(state)
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()


def marker_rows(sequence):
    marked = unreal.MovieSceneSequenceExtensions.get_marked_frames_from_sequence(
        sequence, unreal.MovieSceneTimeUnit.DISPLAY_RATE
    )
    return sorted((int(row.frame_number.value), str(row.label)) for row in marked)


def begin_job(world, root, state, index):
    job = state["jobs"][index]
    state["job_index"] = index
    root.sequence_player.pause()
    result = root.transport.scrub_to_master_frame(unreal.FrameNumber(job["master_frame"]))
    job["scrub_result"] = str(result)
    job["actual_frame_after_scrub"] = root.transport.get_current_master_frame().value
    job["phase"] = "settle"
    job["settle_ticks"] = 0
    job["close_positioned"] = False
    job["started_wall"] = time.monotonic()
    state["status"] = "capturing"
    unreal.log("S3_BEACH_PIE_STILL_JUMP|run=%s|label=%s|master_frame=%d|actual=%d" %
               (state["run_id"], job["label"], job["master_frame"], job["actual_frame_after_scrub"]))
    persist(state)


def position_marble_close(world, job):
    walls = [actor for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
             if str(actor.get_actor_label()) == "S3 Marble Inner Wall Left"]
    if len(walls) != 1:
        raise RuntimeError("expected one runtime left marble liner, found %d" % len(walls))
    controller = unreal.GameplayStatics.get_player_controller(world, 0)
    if controller is None:
        raise RuntimeError("runtime player controller is absent")
    camera = controller.get_view_target()
    if camera is None:
        raise RuntimeError("runtime view target is absent")
    bounds = walls[0].get_actor_bounds(False, True)
    target = bounds[0]
    camera_location = camera.get_actor_location()
    away = camera_location - target
    distance = float(away.length())
    if distance < 1.0:
        raise RuntimeError("camera and marble liner centre coincide")
    close_location = target + away * (425.0 / distance)
    close_rotation = unreal.MathLibrary.find_look_at_rotation(close_location, target)
    camera.set_actor_location(close_location, False, False)
    camera.set_actor_rotation(close_rotation, False)
    job["camera_mode"] = "runtime_view_target_marble_close"
    job["camera_actor"] = str(camera.get_path_name())
    job["marble_actor"] = str(walls[0].get_path_name())
    job["marble_target"] = [float(target.x), float(target.y), float(target.z)]
    job["camera_location"] = [float(close_location.x), float(close_location.y), float(close_location.z)]
    job["camera_rotation"] = [float(close_rotation.roll), float(close_rotation.pitch), float(close_rotation.yaw)]


def tick(_delta):
    state = getattr(builtins, STATE_NAME)
    if state.get("inside"):
        return
    state["inside"] = True
    world = None
    try:
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_game_world()
        if time.monotonic() - state["started_monotonic"] > 180.0:
            raise RuntimeError("owned S3 still run timed out after 180 seconds")

        if state["status"] == "stopping_owned_pie":
            if world is None:
                finalize(state, state.get("final_status") or "failed")
            elif time.monotonic() - state["stop_requested_wall"] > 20.0:
                raise RuntimeError("owned PIE did not end within 20 seconds")
            return

        if state["status"] == "waiting_for_owned_pie":
            if world is None:
                return
            if not owner_matches(state):
                raise RuntimeError("ownership flag does not match after PIE appeared")
            state["pie_observed"] = True
            roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
            if len(roots) != 1 or not roots[0].sequence_player:
                return
            root = roots[0]
            root.sequence_player.pause()
            root.transport.set_editor_property("performance_mode", False)
            if root.transport.get_editor_property("performance_mode"):
                raise RuntimeError("performance mode remained ON in owned PIE")
            segments = list(root.transport.segments)
            scenes = [segment for segment in segments if segment.type == unreal.InfinityCueType.SCENE]
            if len(scenes) != 6:
                raise RuntimeError("expected six Scene segments, found %d" % len(scenes))
            scene = scenes[2]
            sequence = unreal.load_asset(SEQUENCE)
            markers = marker_rows(sequence)
            wanted = {
                "B02": next((frame for frame, label in markers if label.startswith("S3 B02 ")), None),
                "B03": next((frame for frame, label in markers if label.startswith("S3 B03 ")), None),
            }
            if wanted != {"B02": 360, "B03": 960}:
                raise RuntimeError("S3 marker drift: " + json.dumps(wanted, sort_keys=True))
            if PROFILE == "daylight":
                seconds = [
                    ("S3_B02_plus_2s", wanted["B02"] / DISPLAY_FRAMES_PER_SECOND + 2.0,
                     "B02 marker +2 s", "sequence"),
                    ("S3_B03_plus_2s", wanted["B03"] / DISPLAY_FRAMES_PER_SECOND + 2.0,
                     "B03 marker +2 s", "sequence"),
                    ("S3_Marble_Wall_Close", wanted["B03"] / DISPLAY_FRAMES_PER_SECOND + 2.0,
                     "runtime close view of left marble liner at B03 +2 s", "marble_close"),
                ]
            elif PROFILE == "waves":
                seconds = [
                    ("S3_plus_40s_B04_area_waves", 40.0,
                     "Scene 3 +40 s in the requested B04 area showing split waves", "sequence"),
                ]
            else:
                seconds = [
                    ("S3_B02_plus_2s", wanted["B02"] / DISPLAY_FRAMES_PER_SECOND + 2.0,
                     "B02 marker +2 s", "sequence"),
                    ("S3_B03_plus_2s", wanted["B03"] / DISPLAY_FRAMES_PER_SECOND + 2.0,
                     "B03 marker +2 s", "sequence"),
                    ("S3_plus_40s_B04_area", 40.0, "Scene 3 +40 s (requested B04 area)", "sequence"),
                ]
            state["scene_segment"] = {
                "label": str(scene.label), "start": scene.start_frame.value, "end": scene.end_frame.value,
            }
            state["markers_display_rate"] = wanted
            state["jobs"] = []
            for label, offset, note, camera_mode in seconds:
                path = pathlib.Path(state["run_dir"], label + ".png")
                state["jobs"].append({
                    "label": label,
                    "note": note,
                    "scene_seconds": offset,
                    "master_frame": scene.start_frame.value + int(round(offset * MASTER_TICKS_PER_SECOND)),
                    "path": path.as_posix(),
                    "camera_mode": camera_mode,
                    "phase": "pending",
                })
            unreal.SystemLibrary.execute_console_command(world, "DisableAllScreenMessages")
            state["screen_messages_disabled"] = True
            state["screen_messages_restored"] = False
            unreal.log("S3_BEACH_PIE_STILLS_READY|run=%s|world=%s|jobs=%s" %
                       (state["run_id"], world.get_path_name(),
                        json.dumps(state["jobs"], separators=(",", ":"))))
            begin_job(world, root, state, 0)
            return

        if world is None:
            finalize(state, "failed", "owned PIE ended before still capture completed")
            return
        roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
        if len(roots) != 1 or not roots[0].sequence_player:
            raise RuntimeError("lost runtime Show Root/player")
        root = roots[0]
        job = state["jobs"][state["job_index"]]
        if job["phase"] == "settle":
            job["settle_ticks"] += 1
            if (job.get("camera_mode") == "marble_close" and not job.get("close_positioned")
                    and job["settle_ticks"] >= 6):
                position_marble_close(world, job)
                job["close_positioned"] = True
                job["settle_ticks"] = 0
                persist(state)
                return
            if job["settle_ticks"] < 12:
                return
            command = 'HighResShot 1600x900 filename="%s"' % job["path"]
            unreal.SystemLibrary.execute_console_command(world, command)
            job["command"] = command
            job["phase"] = "wait_file"
            job["last_size"] = -1
            job["stable_ticks"] = 0
            job["issued_wall"] = time.monotonic()
            unreal.log("S3_BEACH_PIE_STILL_REQUESTED|run=%s|label=%s|path=%s" %
                       (state["run_id"], job["label"], job["path"]))
            persist(state)
            return
        if job["phase"] == "wait_file":
            path = pathlib.Path(job["path"])
            size = path.stat().st_size if path.is_file() else -1
            if size > 1000 and size == job["last_size"]:
                job["stable_ticks"] += 1
            else:
                job["stable_ticks"] = 0
                job["last_size"] = size
            if job["stable_ticks"] >= 4:
                job["phase"] = "complete"
                job["bytes"] = size
                job["completed_wall"] = time.monotonic()
                unreal.log("S3_BEACH_PIE_STILL_FILE|run=%s|label=%s|bytes=%d|path=%s" %
                           (state["run_id"], job["label"], size, job["path"]))
                if state["job_index"] + 1 < len(state["jobs"]):
                    begin_job(world, root, state, state["job_index"] + 1)
                else:
                    request_end_our_pie(state, "passed", world=world)
                return
            if time.monotonic() - job["issued_wall"] > 45.0:
                raise RuntimeError("still capture timed out: " + job["path"])
    except Exception:
        error = traceback.format_exc()
        if world is not None and state.get("pie_observed") and owner_matches(state):
            request_end_our_pie(state, "failed", error, world)
        else:
            finalize(state, "failed", error)
    finally:
        state["inside"] = False


if hasattr(builtins, HANDLE_NAME):
    raise RuntimeError("an S3 beach PIE still callback is already registered")
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
editor_world = editor.get_editor_world()
if editor_world is None or str(editor_world.get_outermost().get_name()) != EXPECTED_WORLD:
    raise RuntimeError("wrong editor world")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE is already active; refusing to arm")
dirty_maps = package_names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
dirty_content = package_names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
if dirty_maps or dirty_content:
    raise RuntimeError("pre-PIE census is not clean")
if OWNER.exists() and json.loads(OWNER.read_text(encoding="utf-8")).get("active"):
    raise RuntimeError("another PIE ownership flag is active")

stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d_%H%M%S")
run_id = "S3-%s-PIE-%s" % (PROFILE.upper(), stamp)
run_dir = OUT_ROOT / stamp
run_dir.mkdir(parents=True, exist_ok=False)
CURRENT.write_text(json.dumps({
    "run_dir": run_dir.as_posix(),
    "run_id": run_id,
    "prepared_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    "status": "owned_s3_beach_pie_armed",
}, indent=2), encoding="utf-8")
state = {
    "run_id": run_id,
    "run_dir": run_dir.as_posix(),
    "status": "waiting_for_owned_pie",
    "capture_profile": PROFILE,
    "final_status": None,
    "started_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    "started_monotonic": time.monotonic(),
    "dirty_maps_before": dirty_maps,
    "dirty_content_before": dirty_content,
    "pie_observed": False,
    "inside": False,
    "jobs": [],
    "errors": [],
    "screen_messages_disabled": False,
    "screen_messages_restored": False,
    "start_api": {
        "play_mode": "PlayMode_InEditorFloating",
        "begin_script": "CodexConductor/pie_recording_begin_owned_play.py",
        "resolution": [1600, 900],
    },
}
setattr(builtins, STATE_NAME, state)
write_owner(state, True, "owner flag written before starting this S3 beach PIE")
persist(state)
setattr(builtins, HANDLE_NAME, unreal.register_slate_post_tick_callback(tick))
unreal.log("S3_PIE_STILLS_ARMED|run=%s|profile=%s|mode=PlayMode_InEditorFloating|resolution=1600x900|run_dir=%s" %
           (run_id, PROFILE, run_dir.as_posix()))
