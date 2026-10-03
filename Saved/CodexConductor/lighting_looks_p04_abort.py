"""End only the P04 lighting-look PIE whose in-memory ownership matches disk."""
import builtins
import json
import pathlib
import time

import unreal

BASE = pathlib.Path("E:/PussStage/Saved/CodexConductor")
CURRENT = BASE / "lighting_looks_current_run.json"
OWNER = BASE / "pie_recording_owner.json"
STATE_NAME = "PUSS_LIGHTING_LOOKS_P04_STATE"
current = json.loads(CURRENT.read_text(encoding="utf-8"))
owner = json.loads(OWNER.read_text(encoding="utf-8"))
state = getattr(builtins, STATE_NAME, None)
if state is None:
    raise RuntimeError("owned P04 lighting-look state is absent")
if not owner.get("active") or owner.get("run_dir") != current.get("run_dir"):
    raise RuntimeError("ownership flag does not match current run")
if state.get("run_dir") != current.get("run_dir") or state.get("run_id") != current.get("run_id"):
    raise RuntimeError("in-memory ownership state does not match current run")
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if not state.get("pie_observed") or world is None:
    raise RuntimeError("this run has not observed a live PIE world; refusing to end play")
if state.get("screen_messages_disabled"):
    unreal.SystemLibrary.execute_console_command(world, "EnableAllScreenMessages")
    state["screen_messages_disabled"] = False
    state["screen_messages_restored"] = True
state["errors"].append("external abort requested for the matching owned P04 PIE")
state["final_status"] = "failed"
state["status"] = "stopping_owned_pie"
state["ended_wall"] = time.monotonic()
state["stop_requested_wall"] = time.monotonic()
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
unreal.log("LIGHTING_LOOKS_PIE_ABORT|run=" + state["run_id"])

