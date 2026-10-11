"""Arm and own a P05->S5 real-time PIE window; a second script supplies GO."""
import builtins
import datetime
import json
import pathlib
import time
import traceback

import unreal

RUN = "J197-S5-RECORD-A2"
HERE = pathlib.Path(__file__).resolve().parent
RESULT = HERE / "job197_s5_record_A2_result.json"
OWNER = HERE.parent / "pie_recording_owner.json"
HANDLE = "PUSS_JOB197_S5_RECORD_HANDLE"
STATE = "PUSS_JOB197_S5_RECORD_STATE"

def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"maps": sorted(p.get_name() for p in lib.get_dirty_map_packages()),
            "content": sorted(p.get_name() for p in lib.get_dirty_content_packages())}

def persist(state):
    RESULT.write_text(json.dumps({k: v for k, v in state.items() if not k.startswith("_")},
                                 indent=2, sort_keys=True), encoding="utf-8")

def arm():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE already active")
    dirty = census()
    if dirty != {"maps": [], "content": []}:
        raise RuntimeError("dirty before %r" % dirty)
    if OWNER.exists():
        try:
            if json.loads(OWNER.read_text(encoding="utf-8")).get("active"):
                raise RuntimeError("another PIE owner is active")
        except json.JSONDecodeError:
            raise RuntimeError("unreadable PIE owner")
    state = {"run": RUN, "status": "waiting_pie", "dirty_before": dirty, "errors": [],
             "go": False, "phase_started": time.monotonic(), "screen_messages_disabled": False,
             "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    OWNER.write_text(json.dumps({"active": True, "owner": RUN}), encoding="utf-8")
    persist(state)

    def finish():
        state["dirty_after"] = census()
        if state["dirty_after"] != state["dirty_before"]:
            state["errors"].append("dirty census changed")
        state["status"] = "passed" if not state["errors"] else "failed"
        state["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        OWNER.write_text(json.dumps({"active": False, "owner": RUN, "status": state["status"]}), encoding="utf-8")
        persist(state)
        handle = getattr(builtins, HANDLE, None)
        if handle is not None:
            unreal.unregister_slate_post_tick_callback(handle)
            delattr(builtins, HANDLE)
        marker = "JOB197_S5_RECORD_OK" if state["status"] == "passed" else "JOB197_S5_RECORD_FAILED"
        unreal.log("%s|run=%s|start=%s|end=%s|dirty_maps=%d|dirty_content=%d|result=%s" %
                   (marker, RUN, state.get("actual_start"), state.get("actual_end"),
                    len(state["dirty_after"]["maps"]), len(state["dirty_after"]["content"]), RESULT.as_posix()))

    def request_stop(reason=None):
        if reason:
            state["errors"].append(reason)
        game = editor.get_game_world()
        if game is not None and state.get("screen_messages_disabled"):
            unreal.SystemLibrary.execute_console_command(game, "EnableAllScreenMessages")
            state["screen_messages_disabled"] = False
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
        state["status"] = "waiting_end"
        state["phase_started"] = time.monotonic()
        persist(state)

    def tick(_delta=0.0):
        if state.get("_inside"):
            return
        state["_inside"] = True
        try:
            game = editor.get_game_world()
            if state["status"] == "waiting_end":
                if game is None:
                    finish()
                elif time.monotonic() - state["phase_started"] > 45:
                    state["errors"].append("owned PIE did not end")
                    finish()
                return
            if game is None:
                if time.monotonic() - state["phase_started"] > 45:
                    request_stop("owned PIE did not start")
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
                    request_stop("P05 segment count %d" % len(p5)); return
                state["seam"] = int(p5[0].end_frame.value)
                state["from"] = state["seam"] - 10 * 24000
                state["to"] = state["seam"] + 5 * 24000
                if "SUCCEEDED" not in str(root.transport.scrub_to_master_frame(unreal.FrameNumber(state["from"]))).upper():
                    request_stop("scrub failed"); return
                unreal.SystemLibrary.execute_console_command(game, "DisableAllScreenMessages")
                state["screen_messages_disabled"] = True
                state["wait"] = 120
                state["status"] = "settle"
                persist(state)
                return
            if state["status"] == "settle":
                root.sequence_player.pause()
                state["wait"] -= 1
                if state["wait"] <= 0:
                    state["status"] = "ready"
                    state["actual_start"] = int(root.transport.get_current_master_frame().value)
                    persist(state)
                    unreal.log("JOB197_S5_RECORD_READY|run=%s|from=%d|seam=%d|to=%d" %
                               (RUN, state["from"], state["seam"], state["to"]))
                return
            if state["status"] == "ready":
                root.sequence_player.pause()
                if not state.get("go"):
                    return
                root.sequence_player.play()
                state["status"] = "playing"
                state["play_started_monotonic"] = time.monotonic()
                persist(state)
                unreal.log("JOB197_S5_RECORD_PLAYING|run=%s|frame=%d" %
                           (RUN, int(root.transport.get_current_master_frame().value)))
                return
            if state["status"] == "playing":
                frame = int(root.transport.get_current_master_frame().value)
                if frame >= state["to"]:
                    state["actual_end"] = frame
                    root.sequence_player.pause()
                    request_stop()
                elif time.monotonic() - state["play_started_monotonic"] > 25:
                    request_stop("playback timed out at %d" % frame)
        except Exception:
            request_stop(traceback.format_exc())
        finally:
            state["_inside"] = False

    setattr(builtins, STATE, state)
    handle = unreal.register_slate_post_tick_callback(tick)
    setattr(builtins, HANDLE, handle)
    result = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
    unreal.log("JOB197_S5_RECORD_ARMED|run=%s|result=%s" % (RUN, result))

try:
    arm()
except Exception as exc:
    unreal.log_error("JOB197_S5_RECORD_FAILED|run=%s|%r" % (RUN, exc))
    raise
