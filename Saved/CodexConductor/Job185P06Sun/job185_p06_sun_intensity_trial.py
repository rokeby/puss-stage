"""Transient owned-PIE sun-intensity intervention and still; restores exactly."""
import os
import unreal as u

OUTPUT = "E:/PussStage/Saved/CodexConductor/ApplyPass_20261010/stills/185_03_p06_sun_intensity_trial.png"
TRIAL_INTENSITY = 1.5
world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
if world is None:
    raise RuntimeError("JOB185_P06_SUN_TRIAL|NO_OWNED_PIE")
roots = list(u.GameplayStatics.get_all_actors_of_class(world, u.InfinityStageShowRoot))
if len(roots) != 1 or roots[0].sequence_player is None:
    raise RuntimeError("JOB185_P06_SUN_TRIAL|SHOW_ROOT")
root = roots[0]
transport, player = root.transport, root.sequence_player
segments = [s for s in list(transport.segments) if str(s.label) == "Passage 6"]
if len(segments) != 1:
    raise RuntimeError("JOB185_P06_SUN_TRIAL|SEGMENTS")
actors = {str(a.get_actor_label()): a for a in u.GameplayStatics.get_all_actors_of_class(world, u.Actor)}
sun = actors.get("Infinity Stage - Dusk Sun")
comp = sun.get_component_by_class(u.DirectionalLightComponent) if sun else None
if comp is None:
    raise RuntimeError("JOB185_P06_SUN_TRIAL|SUN")
start, end = int(segments[0].start_frame.value), int(segments[0].end_frame.value)
target = end - 2 * 24000
original_frame = int(transport.get_current_master_frame().value)
was_playing = bool(transport.is_transport_playing())
if os.path.exists(OUTPUT):
    raise RuntimeError("JOB185_P06_SUN_TRIAL|OUTPUT_EXISTS")
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
state = {"phase": "setup", "wait": 0, "done": False, "handle": None, "original_intensity": None}


def finish(ok, detail=""):
    if state["done"]:
        return
    state["done"] = True
    try:
        if state["original_intensity"] is not None:
            comp.set_editor_property("intensity", state["original_intensity"])
        transport.scrub_to_master_frame(u.FrameNumber(original_frame))
        player.play() if was_playing else player.pause()
    finally:
        u.unregister_slate_post_tick_callback(state["handle"])
    if ok:
        u.log("JOB185_P06_SUN_INTENSITY_TRIAL_OK|frame=%d|baseline=%.6f|trial=%.6f|restored=1|path=%s" %
              (target, state["original_intensity"], TRIAL_INTENSITY, OUTPUT))
    else:
        u.log_error("JOB185_P06_SUN_INTENSITY_TRIAL_FAILED|" + detail)


def tick(_delta):
    try:
        if state["phase"] == "setup":
            player.pause()
            transport.scrub_to_master_frame(u.FrameNumber(target))
            state.update(phase="baseline", wait=120)
        elif state["phase"] == "baseline":
            state["wait"] -= 1
            if state["wait"] <= 0:
                state["original_intensity"] = float(comp.get_editor_property("intensity"))
                comp.set_editor_property("intensity", TRIAL_INTENSITY)
                state.update(phase="trial", wait=12)
        elif state["phase"] == "trial":
            state["wait"] -= 1
            if state["wait"] <= 0:
                u.SystemLibrary.execute_console_command(world, 'HighResShot 1600x900 filename="%s"' % OUTPUT)
                state.update(phase="file", wait=600)
        else:
            state["wait"] -= 1
            if os.path.exists(OUTPUT) and os.path.getsize(OUTPUT) > 1000:
                finish(True)
            elif state["wait"] <= 0:
                finish(False, "FILE_TIMEOUT")
    except Exception as exc:
        finish(False, repr(exc))


state["handle"] = u.register_slate_post_tick_callback(tick)
u.log("JOB185_P06_SUN_INTENSITY_TRIAL_ARMED|frame=%d|trial=%.6f" % (target, TRIAL_INTENSITY))
