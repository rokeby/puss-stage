"""Capture six exact local-frame S1 stills in Job 185-owned PIE."""
import os
import unreal as u

FRAMES = [3600, 3700, 3800, 3850, 3880, 3899]
NAMES = {
    3600: "185_04_s1_frame3600_final.png",
    3700: "185_05_s1_frame3700_final.png",
    3800: "185_06_s1_frame3800_fade_start_final.png",
    3850: "185_07_s1_frame3850_final.png",
    3880: "185_08_s1_frame3880_final.png",
    3899: "185_09_s1_frame3899_black_final.png",
}
ROOT = "E:/PussStage/Saved/CodexConductor/ApplyPass_20261010/stills/"
world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
if world is None:
    raise RuntimeError("JOB185_S1_STILLS|NO_OWNED_PIE")
roots = list(u.GameplayStatics.get_all_actors_of_class(world, u.InfinityStageShowRoot))
if len(roots) != 1 or roots[0].sequence_player is None:
    raise RuntimeError("JOB185_S1_STILLS|SHOW_ROOT")
root = roots[0]
transport, player = root.transport, root.sequence_player
segments = [s for s in list(transport.segments) if str(s.label).startswith("Scene 1")]
if len(segments) != 1:
    raise RuntimeError("JOB185_S1_STILLS|SEGMENTS=%d" % len(segments))
start, end = int(segments[0].start_frame.value), int(segments[0].end_frame.value)
span = end - start
targets = [(local, min(end - 1, start + int(round(local * span / 3900.0))), ROOT + NAMES[local]) for local in FRAMES]
for _, _, output in targets:
    if os.path.exists(output):
        raise RuntimeError("JOB185_S1_STILLS|OUTPUT_EXISTS|" + output)
os.makedirs(ROOT, exist_ok=True)
original = int(transport.get_current_master_frame().value)
was_playing = bool(transport.is_transport_playing())
state = {"index": 0, "phase": "setup", "wait": 0, "done": False, "handle": None}


def finish(ok, detail=""):
    if state["done"]:
        return
    state["done"] = True
    try:
        transport.scrub_to_master_frame(u.FrameNumber(original))
        player.play() if was_playing else player.pause()
    finally:
        u.unregister_slate_post_tick_callback(state["handle"])
    if ok:
        u.log("JOB185_S1_STILLS_OK|frames=%s|segment=%d:%d|paths=%s" %
              (",".join(str(x) for x in FRAMES), start, end, ";".join(path for _, _, path in targets)))
    else:
        u.log_error("JOB185_S1_STILLS_FAILED|" + detail)


def tick(_delta):
    try:
        if state["index"] >= len(targets):
            finish(True)
            return
        local, target, output = targets[state["index"]]
        if state["phase"] == "setup":
            player.pause()
            transport.scrub_to_master_frame(u.FrameNumber(target))
            state.update(phase="settle", wait=90)
        elif state["phase"] == "settle":
            state["wait"] -= 1
            if state["wait"] <= 0:
                u.SystemLibrary.execute_console_command(world, 'HighResShot 1600x900 filename="%s"' % output)
                state.update(phase="file", wait=600)
        else:
            state["wait"] -= 1
            if os.path.exists(output) and os.path.getsize(output) > 1000:
                u.log("JOB185_S1_STILL_FRAME_OK|local=%d|master=%d|path=%s" % (local, target, output))
                state.update(index=state["index"] + 1, phase="setup", wait=0)
            elif state["wait"] <= 0:
                finish(False, "FILE_TIMEOUT|local=%d|path=%s" % (local, output))
    except Exception as exc:
        finish(False, repr(exc))


state["handle"] = u.register_slate_post_tick_callback(tick)
u.log("JOB185_S1_STILLS_ARMED|frames=%s|segment=%d:%d" % (",".join(str(x) for x in FRAMES), start, end))
