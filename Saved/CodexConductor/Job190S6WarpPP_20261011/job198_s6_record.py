"""Arm and own a 10 s S6 PIE window from about 62.5% to 67.1%; GO is separate."""
import builtins
import datetime
import json
import pathlib
import time
import traceback

import unreal


RUN = "J198-S6-RECORD-A3"
HERE = pathlib.Path(__file__).resolve().parent
RESULT = HERE / "job198_s6_record_A3_result.json"
OWNER = HERE.parent / "pie_recording_owner.json"
HANDLE = "PUSS_JOB198_S6_RECORD_HANDLE"
STATE = "PUSS_JOB198_S6_RECORD_STATE"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"maps": sorted(p.get_name() for p in lib.get_dirty_map_packages()),
            "content": sorted(p.get_name() for p in lib.get_dirty_content_packages())}


def persist(state):
    RESULT.write_text(json.dumps({k: v for k, v in state.items() if not k.startswith("_")},
                                 indent=2, sort_keys=True), encoding="utf-8")


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


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
    state = {"run": RUN, "status": "waiting_pie", "dirty_before": dirty, "errors": [],
             "go": False, "phase_started": time.monotonic(), "screen_messages_disabled": False,
             "started_utc": utc_now()}
    OWNER.write_text(json.dumps({"active": True, "owner": RUN}), encoding="utf-8")
    persist(state)

    def finish():
        state["dirty_after"] = census()
        if state["dirty_after"] != state["dirty_before"]:
            state["errors"].append("dirty census changed")
        state["status"] = "passed" if not state["errors"] else "failed"
        state["finished_utc"] = utc_now()
        OWNER.write_text(json.dumps({"active": False, "owner": RUN, "status": state["status"]}), encoding="utf-8")
        persist(state)
        handle = getattr(builtins, HANDLE, None)
        if handle is not None:
            unreal.unregister_slate_post_tick_callback(handle)
            delattr(builtins, HANDLE)
        marker = "JOB198_S6_RECORD_OK" if state["status"] == "passed" else "JOB198_S6_RECORD_FAILED"
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
                rows = [row for row in root.transport.segments
                        if str(row.label).lower().startswith("scene 6")]
                if len(rows) != 1:
                    request_stop("S6 segment count %d" % len(rows)); return
                start = int(rows[0].start_frame.value)
                end = int(rows[0].end_frame.value)
                duration = end - start
                state["segment"] = {"label": str(rows[0].label), "start": start, "end": end,
                                    "duration_ticks": duration}
                state["from"] = start + int(round(duration * 0.625))
                state["to"] = state["from"] + 10 * 24000
                state["fraction_from"] = (state["from"] - start) / float(duration)
                state["fraction_to"] = (state["to"] - start) / float(duration)
                if state["fraction_to"] > 0.70:
                    request_stop("record window exceeds 70 percent"); return
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
                    state["ready_utc"] = utc_now()
                    persist(state)
                    unreal.log("JOB198_S6_RECORD_READY|run=%s|from=%d|to=%d|fraction=%.4f-%.4f" %
                               (RUN, state["from"], state["to"], state["fraction_from"], state["fraction_to"]))
                return
            if state["status"] == "ready":
                root.sequence_player.pause()
                if not state.get("go"):
                    return
                root.sequence_player.play()
                state["status"] = "playing"
                state["play_started_monotonic"] = time.monotonic()
                state["play_started_utc"] = utc_now()
                persist(state)
                unreal.log("JOB198_S6_RECORD_PLAYING|run=%s|frame=%d" %
                           (RUN, int(root.transport.get_current_master_frame().value)))
                return
            if state["status"] == "playing":
                frame = int(root.transport.get_current_master_frame().value)
                if frame >= state["to"]:
                    state["actual_end"] = frame
                    state["play_finished_utc"] = utc_now()
                    root.sequence_player.pause()
                    request_stop()
                elif time.monotonic() - state["play_started_monotonic"] > 20:
                    request_stop("playback timed out at %d" % frame)
        except Exception:
            request_stop(traceback.format_exc())
        finally:
            state["_inside"] = False

    setattr(builtins, STATE, state)
    handle = unreal.register_slate_post_tick_callback(tick)
    setattr(builtins, HANDLE, handle)
    result = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
    unreal.log("JOB198_S6_RECORD_ARMED|run=%s|result=%s" % (RUN, result))


try:
    arm()
except Exception as exc:
    unreal.log_error("JOB198_S6_RECORD_FAILED|run=%s|%r" % (RUN, exc))
    raise
