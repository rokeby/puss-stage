"""Abort only the matching owned Flat V3 ST PIE after an external gate failure."""
import builtins
import json
import pathlib
import time

import unreal


CONDUCTOR = pathlib.Path("E:/PussStage/Saved/CodexConductor")
CURRENT = CONDUCTOR / "pie_recording_current_run.json"
OWNER = CONDUCTOR / "pie_recording_owner.json"
STATE_NAME = "PUSS_FLATV3_ST_PIE_STATE"

current = json.loads(CURRENT.read_text(encoding="utf-8"))
owner = json.loads(OWNER.read_text(encoding="utf-8"))
state = getattr(builtins, STATE_NAME, None)
if state is None or current.get("kind") != "flatv3_st_pie_stills":
    raise RuntimeError("ST_PIE_ABORT_STATE_ABSENT")
if (not owner.get("active") or owner.get("kind") != "flatv3_st_pie_stills" or
        owner.get("run_dir") != current.get("run_dir") or
        owner.get("run_id") != current.get("run_id") or
        state.get("run_id") != current.get("run_id")):
    raise RuntimeError("ST_PIE_ABORT_OWNER_MISMATCH")
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if not state.get("pie_observed") or world is None:
    raise RuntimeError("ST_PIE_ABORT_UNOBSERVED; refusing to end play")

# The normal driver owns camera teardown by direct reference.  This external
# abort is the exceptional recovery path: remove only its uniquely named class
# of transient CineCamera actors, and only from the observed PIE game world.
editor_world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
for camera in list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.CineCameraActor)):
    if camera.get_world() is editor_world:
        raise RuntimeError("ST_PIE_ABORT_EDITOR_CAMERA_REFUSED")
    if str(camera.get_actor_label()).startswith("FlatV3_ST_PIE_"):
        camera.destroy_actor()
if state.get("screen_messages_disabled"):
    unreal.SystemLibrary.execute_console_command(world, "EnableAllScreenMessages")
    state["screen_messages_disabled"] = False
    state["screen_messages_restored"] = True
state["errors"].append("external abort path requested")
state["final_status"] = "failed"
state["status"] = "stopping_owned_pie"
state["stop_requested_wall"] = time.monotonic()
unreal.log("FLATV3_ST_PIE_ABORT run=%s reason=external_gate_failure" % state["run_id"])
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
