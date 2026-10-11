"""Own one PIE, capture the seven requested P05->S5 whiteout stills, then end only that PIE."""
import builtins
import datetime
import json
import pathlib
import sys
import time
import traceback

import unreal

HERE = pathlib.Path(__file__).resolve().parent
AUDIT = HERE.parent / "Job191TransitionAudit_20261011"
if str(AUDIT) not in sys.path:
    sys.path.insert(0, str(AUDIT))
import seam_audit_core

RUN = "J197-S5-STILLS-A1"
OUT = pathlib.Path("E:/PussStage/Saved/CodexConductor/ApplyPass_20261010/stills")
RESULT = HERE / "job197_s5_stills_result.json"
OWNER = HERE.parent / "pie_recording_owner.json"
HANDLE = "PUSS_JOB197_S5_STILLS_HANDLE"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SAMPLES = [("minus10s", -10.0), ("minus5s", -5.0), ("minus1s", -1.0),
           ("seam", 0.0), ("plus1s", 1.0), ("plus3s", 3.0)]

def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"maps": sorted(p.get_name() for p in lib.get_dirty_map_packages()),
            "content": sorted(p.get_name() for p in lib.get_dirty_content_packages())}

def write(value):
    RESULT.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")

def finish(state):
    state["dirty_after"] = census()
    if state["dirty_after"] != state["dirty_before"]:
        state["errors"].append("dirty census changed")
    state["status"] = "passed" if not state["errors"] and len(state["captures"]) == len(SAMPLES) else "failed"
    state["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    OWNER.write_text(json.dumps({"active": False, "owner": RUN, "status": state["status"]}), encoding="utf-8")
    write(state)
    handle = getattr(builtins, HANDLE, None)
    if handle is not None:
        unreal.unregister_slate_post_tick_callback(handle)
        delattr(builtins, HANDLE)
    marker = "JOB197_S5_STILLS_OK" if state["status"] == "passed" else "JOB197_S5_STILLS_FAILED"
    seam = next((row for row in state["captures"] if row["key"] == "seam"), {})
    unreal.log("%s|run=%s|frames=%d|seam_mean_luminance=%.3f|dirty_maps=%d|dirty_content=%d|result=%s" %
               (marker, RUN, len(state["captures"]), float(seam.get("mean_luminance", -1)),
                len(state["dirty_after"]["maps"]), len(state["dirty_after"]["content"]), RESULT.as_posix()))

def arm():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE already active")
    world = editor.get_editor_world()
    if world is None or str(world.get_path_name()).split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("wrong editor world")
    dirty = census()
    if dirty != {"maps": [], "content": []}:
        raise RuntimeError("dirty before %r" % dirty)
    if OWNER.exists():
        try:
            if json.loads(OWNER.read_text(encoding="utf-8")).get("active"):
                raise RuntimeError("another PIE owner is active")
        except json.JSONDecodeError:
            raise RuntimeError("unreadable PIE owner")
    OUT.mkdir(parents=True, exist_ok=True)
    paths = [OUT / ("197_P05_S5_%s.png" % key) for key, _ in SAMPLES]
    existing = [path.as_posix() for path in paths if path.exists()]
    if existing:
        raise RuntimeError("evidence paths already exist %r" % existing)
    state = {"run": RUN, "status": "waiting_pie", "phase_started": time.monotonic(),
             "dirty_before": dirty, "errors": [], "captures": [], "sample_index": 0,
             "paths": [p.as_posix() for p in paths], "screen_messages_disabled": False}
    OWNER.write_text(json.dumps({"active": True, "owner": RUN}), encoding="utf-8")
    write(state)

    def stop(reason=None):
        if reason:
            state["errors"].append(reason)
        game = editor.get_game_world()
        if game is not None and state.get("screen_messages_disabled"):
            unreal.SystemLibrary.execute_console_command(game, "EnableAllScreenMessages")
            state["screen_messages_disabled"] = False
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
        state["status"] = "waiting_end"
        state["phase_started"] = time.monotonic()

    def tick(_delta=0.0):
        if state.get("inside"):
            return
        state["inside"] = True
        try:
            game = editor.get_game_world()
            if state["status"] == "waiting_end":
                if game is None:
                    finish(state)
                elif time.monotonic() - state["phase_started"] > 45:
                    state["errors"].append("owned PIE did not end")
                    finish(state)
                return
            if game is None:
                if time.monotonic() - state["phase_started"] > 45:
                    stop("owned PIE did not start")
                return
            roots = list(unreal.GameplayStatics.get_all_actors_of_class(game, unreal.InfinityStageShowRoot))
            if len(roots) != 1 or roots[0].transport is None or roots[0].sequence_player is None:
                return
            root = roots[0]
            if state["status"] == "waiting_pie":
                root.sequence_player.pause()
                segments = list(root.transport.segments)
                p5 = [row for row in segments if str(row.label).lower().startswith("passage 5") or str(row.label).lower().startswith("passage 05")]
                if len(p5) != 1:
                    stop("P05 segment count %d" % len(p5)); return
                state["seam_frame"] = int(p5[0].end_frame.value)
                state["targets"] = [state["seam_frame"] + int(seconds * 24000) for _, seconds in SAMPLES]
                unreal.SystemLibrary.execute_console_command(game, "DisableAllScreenMessages")
                state["screen_messages_disabled"] = True
                state["status"] = "scrub"
            if state["status"] == "scrub":
                root.sequence_player.pause()
                target = state["targets"][state["sample_index"]]
                if "SUCCEEDED" not in str(root.transport.scrub_to_master_frame(unreal.FrameNumber(target))).upper():
                    stop("scrub failed %d" % target); return
                state["wait"] = 75
                state["status"] = "settle"
                return
            if state["status"] == "settle":
                state["wait"] -= 1
                if state["wait"] > 0:
                    return
                i = state["sample_index"]
                target = state["targets"][i]
                actual = int(root.transport.get_current_master_frame().value)
                if abs(actual - target) > 1:
                    stop("frame drift target=%d actual=%d" % (target, actual)); return
                path = state["paths"][i]
                unreal.SystemLibrary.execute_console_command(game, 'HighResShot 1600x900 filename="%s"' % path)
                state.update(status="wait_file", file_started=time.monotonic(), last_size=-1, stable=0)
                return
            if state["status"] == "wait_file":
                i = state["sample_index"]
                path = pathlib.Path(state["paths"][i])
                size = path.stat().st_size if path.is_file() else -1
                if size > 1000 and size == state["last_size"]:
                    state["stable"] += 1
                else:
                    state["stable"], state["last_size"] = 0, size
                if state["stable"] >= 4:
                    key = SAMPLES[i][0]
                    state["captures"].append({"key": key, "target_frame": state["targets"][i],
                                              "actual_frame": int(root.transport.get_current_master_frame().value),
                                              "path": path.as_posix(), "bytes": size,
                                              "mean_luminance": seam_audit_core.png_mean_luminance(path)})
                    state["sample_index"] += 1
                    write(state)
                    if state["sample_index"] == len(SAMPLES):
                        stop()
                    else:
                        state["status"] = "scrub"
                elif time.monotonic() - state["file_started"] > 45:
                    stop("file timeout %s" % path)
        except Exception:
            stop(traceback.format_exc())
        finally:
            state["inside"] = False

    handle = unreal.register_slate_post_tick_callback(tick)
    setattr(builtins, HANDLE, handle)
    result = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
    unreal.log("JOB197_S5_STILLS_ARMED|run=%s|result=%s" % (RUN, result))

try:
    arm()
except Exception as exc:
    unreal.log_error("JOB197_S5_STILLS_FAILED|run=%s|%r" % (RUN, exc))
    raise
