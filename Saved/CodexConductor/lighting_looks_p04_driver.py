"""Owned floating-PIE driver for P04 lighting looks, bays 1-6 through bay 7."""
import builtins
import datetime
import importlib
import json
import pathlib
import re
import sys
import time
import traceback

import unreal

BASE = pathlib.Path("E:/PussStage/Saved/CodexConductor")
CURRENT = BASE / "lighting_looks_current_run.json"
OWNER = BASE / "pie_recording_owner.json"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
HANDLE_NAME = "PUSS_LIGHTING_LOOKS_P04_HANDLE"
STATE_NAME = "PUSS_LIGHTING_LOOKS_P04_STATE"
P04_LABEL = re.compile(r"^P04 Wing (\d{3})$")
LOOKS = {1: "MOODY", 2: "MOODY", 3: "INDUSTRIAL", 4: "INDUSTRIAL",
         5: "THEATRICAL", 6: "THEATRICAL"}


def package_names(packages):
    return sorted(package.get_name() for package in packages)


def guid_text(value):
    return str(unreal.GuidLibrary.conv_guid_to_string(value)).replace("-", "").upper()


def persist(state):
    pathlib.Path(state["run_dir"], "runtime_result.json").write_text(
        json.dumps(state, indent=2), encoding="utf-8")


def write_owner(state, active, note):
    OWNER.write_text(json.dumps({
        "active": active,
        "note": note,
        "run_id": state["run_id"],
        "run_dir": state["run_dir"],
        "started_utc": state["started_utc"],
        "updated_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    }, indent=2), encoding="utf-8")


def request_shot(world, state, bay_number, target_frame, actual_frame):
    look = LOOKS[bay_number]
    safe = "P04_bay_%d_%s" % (bay_number, look)
    path = pathlib.Path(state["run_dir"], "shots", safe + ".png")
    command = 'HighResShot 1280x720 filename="%s"' % path.as_posix()
    unreal.SystemLibrary.execute_console_command(world, command)
    state["shots"].append({
        "bay": bay_number,
        "look": look,
        "label": "P04 bay %d - %s" % (bay_number, look),
        "target_frame": target_frame,
        "actual_frame": actual_frame,
        "error_frames": actual_frame - target_frame,
        "path_requested": path.as_posix(),
        "command": command,
    })
    unreal.log("LIGHTING_LOOKS_PIE_SHOT|bay=%d|look=%s|target=%d|actual=%d|path=%s" %
               (bay_number, look, target_frame, actual_frame, path.as_posix()))


def request_sequence_frame(world, state, actual_frame):
    bay_number = 1
    for candidate, threshold in enumerate(state["plan"]["pass_frames"][:6], start=1):
        if actual_frame >= threshold:
            bay_number = candidate
    index = len(state["sequence_frames"])
    path = pathlib.Path(state["run_dir"], "sequence", "frame_%04d.png" % index)
    command = 'HighResShot 1280x720 filename="%s"' % path.as_posix()
    unreal.SystemLibrary.execute_console_command(world, command)
    state["sequence_frames"].append({
        "index": index,
        "master_frame": actual_frame,
        "bay": bay_number,
        "look": LOOKS[bay_number],
        "label": "P04 bay %d - %s" % (bay_number, LOOKS[bay_number]),
        "path_requested": path.as_posix(),
        "command": command,
    })
    unreal.log("LIGHTING_LOOKS_PIE_SEQUENCE_FRAME|index=%d|bay=%d|look=%s|frame=%d|path=%s" %
               (index, bay_number, LOOKS[bay_number], actual_frame, path.as_posix()))


def add_label_event(state, bay_number, frame):
    state["label_events"].append({
        "bay": bay_number,
        "look": LOOKS[bay_number],
        "label": "P04 bay %d - %s" % (bay_number, LOOKS[bay_number]),
        "master_frame": frame,
        "wall": time.monotonic(),
    })
    unreal.log("LIGHTING_LOOKS_PIE_LABEL|bay=%d|look=%s|frame=%d" %
               (bay_number, LOOKS[bay_number], frame))


def stop_owned_pie(state, status, world, error=None):
    if error:
        state["errors"].append(error)
    state["final_status"] = status
    state["status"] = "stopping_owned_pie"
    state["ended_wall"] = time.monotonic()
    state["stop_requested_wall"] = time.monotonic()
    if world is not None and state.get("screen_messages_disabled"):
        unreal.SystemLibrary.execute_console_command(world, "EnableAllScreenMessages")
        state["screen_messages_disabled"] = False
        state["screen_messages_restored"] = True
    write_owner(state, True, "end requested for this run's owned PIE")
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    persist(state)


def finalize_after_pie(state):
    state["finished_utc"] = datetime.datetime.now(datetime.UTC).isoformat()
    state["dirty_maps_after"] = package_names(
        unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    state["dirty_content_after"] = package_names(
        unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    if state["dirty_maps_after"] or state["dirty_content_after"]:
        state["errors"].append("post-PIE census dirty")
        state["final_status"] = "failed"
    state["status"] = state["final_status"]
    pathlib.Path(state["run_dir"], "capture_stop.json").write_text(
        json.dumps({"status": state["status"], "finished_utc": state["finished_utc"]}, indent=2),
        encoding="utf-8")
    write_owner(state, False, "owned P04 lighting-look PIE ended; census recorded")
    persist(state)
    unreal.unregister_slate_post_tick_callback(getattr(builtins, HANDLE_NAME))
    delattr(builtins, HANDLE_NAME)
    unreal.log("LIGHTING_LOOKS_PIE_COMPLETE|status=%s|shots=%d|dirty_maps=%d|dirty_content=%d|run_dir=%s" %
               (state["status"], len(state["shots"]), len(state["dirty_maps_after"]),
                len(state["dirty_content_after"]), state["run_dir"]))


def build_plan(transport):
    segments = list(transport.segments)
    matches = [segment for segment in segments
               if segment.type == unreal.InfinityCueType.WING_PAIR
               and str(segment.label) == "Passage 4"]
    if len(matches) != 1:
        raise RuntimeError("expected exactly one runtime Passage 4 segment")
    passage_segment = matches[0]
    show = unreal.load_asset(SHOW_PATH)
    if show is None:
        raise RuntimeError("Show asset failed to load")
    settings_rows = [row for row in show.get_editor_property("passage_settings")
                     if str(row.get_editor_property("label")) == "Passage 4"]
    if len(settings_rows) != 1:
        raise RuntimeError("expected exactly one Show Passage 4 settings row")
    settings = settings_rows[0]
    cues = list(show.get_editor_property("cues"))
    first_guid = guid_text(settings.get_editor_property("first_cue_guid"))
    last_guid = guid_text(settings.get_editor_property("last_cue_guid"))
    first = [i for i, cue in enumerate(cues)
             if guid_text(cue.get_editor_property("cue_guid")) == first_guid]
    last = [i for i, cue in enumerate(cues)
            if guid_text(cue.get_editor_property("cue_guid")) == last_guid]
    if len(first) != 1 or len(last) != 1 or first[0] > last[0]:
        raise RuntimeError("P04 cue span is invalid")
    span = cues[first[0]:last[0] + 1]
    if len(span) < 7:
        raise RuntimeError("P04 has fewer than seven bays")
    for bay_number, cue in enumerate(span[:7], start=1):
        expected = "P04 Wing %03d" % bay_number
        if str(cue.get_editor_property("label")) != expected:
            raise RuntimeError("expected %s at P04 ordinal %d" % (expected, bay_number))
    frame = passage_segment.start_frame.value + int(
        settings.get_editor_property("lead_in_frames").value)
    pass_frames = []
    for ordinal, cue in enumerate(span[:7]):
        pass_frames.append(frame)
        if ordinal < 6:
            pair = cue.get_editor_property("wing_pair")
            interval = int(pair.get_editor_property("interval_to_next").value)
            if interval <= 0:
                raise RuntimeError("non-positive P04 bay interval at ordinal %d" % (ordinal + 1))
            frame += interval
    target_end = pass_frames[6] + 24000
    if target_end >= passage_segment.end_frame.value:
        raise RuntimeError("bay 7 plus one second is outside Passage 4")
    return {
        "segment_label": str(passage_segment.label),
        "segment_start": passage_segment.start_frame.value,
        "segment_end": passage_segment.end_frame.value,
        "pass_frames": pass_frames,
        "target_end": target_end,
        "cue_labels": [str(cue.get_editor_property("label")) for cue in span[:7]],
    }


def tick(_delta):
    state = getattr(builtins, STATE_NAME)
    if state.get("inside"):
        return
    state["inside"] = True
    world = None
    try:
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_game_world()
        if time.monotonic() - state["started_monotonic"] > 300.0:
            raise RuntimeError("P04 lighting-look recording timed out")
        if state["status"] == "stopping_owned_pie":
            if world is None:
                finalize_after_pie(state)
            elif time.monotonic() - state["stop_requested_wall"] > 20.0:
                raise RuntimeError("owned PIE did not end within 20 seconds")
            return
        if state["status"] == "waiting_for_pie":
            if world is None:
                capture_failure = pathlib.Path(state["run_dir"], "capture_failed.json")
                if capture_failure.exists():
                    state["errors"].append("capture failed before PIE appeared")
                    state["final_status"] = "failed"
                    state["status"] = "failed_without_pie"
                    pathlib.Path(state["run_dir"], "capture_stop.json").write_text(
                        json.dumps({"status": state["status"]}, indent=2), encoding="utf-8")
                    write_owner(state, False, "capture failed before this run observed PIE")
                    persist(state)
                    unreal.unregister_slate_post_tick_callback(getattr(builtins, HANDLE_NAME))
                    delattr(builtins, HANDLE_NAME)
                return
            state["pie_observed"] = True
            roots = list(unreal.GameplayStatics.get_all_actors_of_class(
                world, unreal.InfinityStageShowRoot))
            if len(roots) != 1 or not roots[0].sequence_player:
                return
            root = roots[0]
            player = root.sequence_player
            transport = root.transport
            player.pause()
            transport.set_editor_property("performance_mode", False)
            if transport.get_editor_property("performance_mode"):
                raise RuntimeError("performance mode remained ON")
            state["plan"] = build_plan(transport)
            unreal.SystemLibrary.execute_console_command(world, "DisableAllScreenMessages")
            state["screen_messages_disabled"] = True
            state["screen_messages_restored"] = False
            state["status"] = "waiting_for_capture"
            state["pie_ready_wall"] = time.monotonic()
            persist(state)
            unreal.log("LIGHTING_LOOKS_PIE_READY|plan=" +
                       json.dumps(state["plan"], separators=(",", ":")))
            return
        if state["status"] == "waiting_for_capture":
            if pathlib.Path(state["run_dir"], "capture_failed.json").exists():
                raise RuntimeError("capture failed before transport start")
            if not pathlib.Path(state["run_dir"], "capture_ready.json").exists():
                if time.monotonic() - state["pie_ready_wall"] > 45.0:
                    raise RuntimeError("capture was not ready within 45 seconds")
                return
            roots = list(unreal.GameplayStatics.get_all_actors_of_class(
                world, unreal.InfinityStageShowRoot))
            root = roots[0]
            player = root.sequence_player
            transport = root.transport
            player.pause()
            transport.scrub_to_master_frame(unreal.FrameNumber(state["plan"]["segment_start"]))
            player.set_play_rate(1.0)
            transport.play_forward_to_boundary()
            state["actual_start"] = transport.get_current_master_frame().value
            state["started_wall"] = time.monotonic()
            state["status"] = "running"
            add_label_event(state, 1, state["actual_start"])
            state["next_label_bay"] = 2
            state["next_shot_bay"] = 1
            state["next_sequence_frame"] = state["actual_start"]
            persist(state)
            unreal.log("LIGHTING_LOOKS_PIE_TRANSPORT_START|from=%d|to=%d|rate=1.0" %
                       (state["plan"]["segment_start"], state["plan"]["target_end"]))
            return
        roots = list(unreal.GameplayStatics.get_all_actors_of_class(
            world, unreal.InfinityStageShowRoot))
        if len(roots) != 1 or not roots[0].sequence_player:
            raise RuntimeError("lost runtime Show Root/player")
        root = roots[0]
        transport = root.transport
        player = root.sequence_player
        frame = transport.get_current_master_frame().value
        while state["next_label_bay"] <= 6:
            bay = state["next_label_bay"]
            threshold = state["plan"]["pass_frames"][bay - 1]
            if frame < threshold:
                break
            add_label_event(state, bay, frame)
            state["next_label_bay"] += 1
        requested_still = False
        while state["next_shot_bay"] <= 6:
            bay = state["next_shot_bay"]
            target = state["plan"]["pass_frames"][bay - 1]
            if frame < target:
                break
            request_shot(world, state, bay, target, frame)
            state["next_shot_bay"] += 1
            requested_still = True
            persist(state)
            break
        if (not requested_still and frame >= state["next_sequence_frame"]
                and frame < state["plan"]["target_end"]):
            request_sequence_frame(world, state, frame)
            state["next_sequence_frame"] = frame + 24000
            persist(state)
        if frame >= state["plan"]["target_end"]:
            player.pause()
            state["actual_end"] = frame
            if len(state["shots"]) != 6:
                raise RuntimeError("expected six requested shots, got %d" % len(state["shots"]))
            if len(state["sequence_frames"]) < 24:
                raise RuntimeError("expected at least 24 sequence frames, got %d" %
                                   len(state["sequence_frames"]))
            stop_owned_pie(state, "passed", world)
            return
        if not transport.is_transport_playing():
            transport.play_forward_to_boundary()
            unreal.log("LIGHTING_LOOKS_PIE_CONTINUE|frame=%d|rate=1.0" % frame)
    except Exception:
        error = traceback.format_exc()
        if state.get("status") == "stopping_owned_pie":
            state["errors"].append(error)
            state["final_status"] = "failed"
            persist(state)
        elif world is not None and state.get("pie_observed"):
            stop_owned_pie(state, "failed", world, error)
        else:
            state["errors"].append(error)
            state["final_status"] = "failed"
            persist(state)
    finally:
        state["inside"] = False


if hasattr(builtins, HANDLE_NAME):
    raise RuntimeError("a P04 lighting-look recording callback is already registered")
current = json.loads(CURRENT.read_text(encoding="utf-8"))
run_dir = pathlib.Path(current["run_dir"])
if not run_dir.is_dir():
    raise RuntimeError("prepared LightingLooks run directory is absent")
(run_dir / "sequence").mkdir(parents=True, exist_ok=True)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE is already active; refusing to arm")
dirty_maps = package_names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
dirty_content = package_names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
if dirty_maps or dirty_content:
    raise RuntimeError("pre-PIE census is not clean")
purged = []
for name, module in list(sys.modules.items()):
    filename = getattr(module, "__file__", None)
    if filename and pathlib.Path(filename).as_posix().lower().startswith("e:/pussstage/saved/"):
        purged.append(name)
        sys.modules.pop(name, None)
importlib.invalidate_caches()
state = {
    "status": "waiting_for_pie",
    "final_status": None,
    "run_id": current["run_id"],
    "run_dir": current["run_dir"],
    "started_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    "started_monotonic": time.monotonic(),
    "dirty_maps_before": dirty_maps,
    "dirty_content_before": dirty_content,
    "shots": [],
    "sequence_frames": [],
    "label_events": [],
    "errors": [],
    "purged_saved_modules": purged,
    "inside": False,
    "pie_observed": False,
    "screen_messages_disabled": False,
    "screen_messages_restored": False,
    "start_api": "PussStage Play menu -> owned editor PIE",
}
setattr(builtins, STATE_NAME, state)
write_owner(state, True, "P04 lighting-look owner armed before floating PIE")
persist(state)
setattr(builtins, HANDLE_NAME, unreal.register_slate_post_tick_callback(tick))
unreal.log("LIGHTING_LOOKS_PIE_DRIVER_ARMED|mode=OwnedEditorPIE|size=1280x720|run_dir=" +
           state["run_dir"])
