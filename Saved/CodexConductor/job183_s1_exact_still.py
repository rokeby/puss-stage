"""Runtime-only still at an exact post-shrink S1 local frame in Job 183-owned PIE."""
import json
import os
import unreal as u

HERE = "E:/PussStage/Saved/CodexConductor/"
args = json.load(open(HERE + "job183_s1_exact_still_args.json", encoding="utf-8"))
local_frame = int(args["local_frame"])
output = str(args["output"]).replace("\\", "/")
run = str(args["run_id"])
if local_frame not in (3600, 3700, 3800, 3880, 3899):
    raise RuntimeError("JOB183_S1_EXACT_BAD_FRAME|%d" % local_frame)
world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
if world is None:
    raise RuntimeError("JOB183_S1_EXACT_NO_OWNED_PIE")
roots = list(u.GameplayStatics.get_all_actors_of_class(world, u.InfinityStageShowRoot))
if len(roots) != 1 or roots[0].sequence_player is None:
    raise RuntimeError("JOB183_S1_EXACT_SHOW_ROOT|%d" % len(roots))
root = roots[0]; transport = root.transport; player = root.sequence_player
segments = [s for s in list(transport.segments) if str(s.label).startswith("Scene 1")]
if len(segments) != 1:
    raise RuntimeError("JOB183_S1_EXACT_SEGMENTS|%d" % len(segments))
start = int(segments[0].start_frame.value); end = int(segments[0].end_frame.value)
span = end - start
target = start + int(round(local_frame * span / 3900.0))
if target >= end:
    target = end - 1
original = int(transport.get_current_master_frame().value)
was_playing = bool(transport.is_transport_playing())
os.makedirs(os.path.dirname(output), exist_ok=True)
if os.path.exists(output):
    raise RuntimeError("JOB183_S1_EXACT_OUTPUT_EXISTS|%s" % output)
state = {"phase": "setup", "wait": 0, "done": False, "handle": None}

def finish(ok, detail=""):
    if state["done"]: return
    state["done"] = True
    try:
        transport.scrub_to_master_frame(u.FrameNumber(original))
        player.play() if was_playing else player.pause()
    finally:
        u.unregister_slate_post_tick_callback(state["handle"])
    if ok:
        u.log("JOB183_S1_EXACT_STILL_OK|run=%s|local_frame=%d|segment=%d:%d|master_frame=%d|path=%s" %
              (run, local_frame, start, end, target, output))
    else:
        u.log_error("JOB183_S1_EXACT_STILL_FAILED|run=%s|%s" % (run, detail))

def tick(_delta):
    try:
        if state["phase"] == "setup":
            player.pause(); transport.scrub_to_master_frame(u.FrameNumber(target))
            state.update(phase="settle", wait=90)
        elif state["phase"] == "settle":
            state["wait"] -= 1
            if state["wait"] <= 0:
                u.SystemLibrary.execute_console_command(world, 'HighResShot 1600x900 filename="%s"' % output)
                state.update(phase="file", wait=600)
        else:
            state["wait"] -= 1
            if os.path.exists(output) and os.path.getsize(output) > 1000: finish(True)
            elif state["wait"] <= 0: finish(False, "file_timeout")
    except Exception as exc:
        finish(False, repr(exc))

state["handle"] = u.register_slate_post_tick_callback(tick)
u.log("JOB183_S1_EXACT_STILL_ARMED|run=%s|local_frame=%d|segment=%d:%d|master_frame=%d|path=%s" %
      (run, local_frame, start, end, target, output))
