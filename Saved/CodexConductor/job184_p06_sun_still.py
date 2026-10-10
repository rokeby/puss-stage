"""Runtime-only P06 near-end still for the bounded-axis sun-disc result."""
import os
import unreal as u


RUN = "JOB184-P06-SUN-20261010"
OUTPUT = "E:/PussStage/Saved/CodexConductor/ApplyPass_20261010/stills/184_03_p06_sun_disc_end_window.png"
world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
if world is None:
    raise RuntimeError("JOB184_P06_SUN_STILL_NO_OWNED_PIE")
roots = list(u.GameplayStatics.get_all_actors_of_class(world, u.InfinityStageShowRoot))
if len(roots) != 1 or roots[0].sequence_player is None:
    raise RuntimeError("JOB184_P06_SUN_STILL_SHOW_ROOT|%d" % len(roots))
root = roots[0]
transport, player = root.transport, root.sequence_player
segments = [s for s in list(transport.segments) if str(s.label) == "Passage 6"]
if len(segments) != 1:
    raise RuntimeError("JOB184_P06_SUN_STILL_SEGMENTS|%d" % len(segments))
start = int(segments[0].start_frame.value)
end = int(segments[0].end_frame.value)
target = end - 2 * 24000
if target <= start:
    raise RuntimeError("JOB184_P06_SUN_STILL_RANGE|%d:%d" % (start, end))
actors = {str(a.get_actor_label()): a for a in u.GameplayStatics.get_all_actors_of_class(world, u.Actor)}
sun = actors.get("Infinity Stage - Dusk Sun")
sky = actors.get("Infinity Stage - Dusk Sky Atmosphere")
if sun is None or sky is None:
    raise RuntimeError("JOB184_P06_SUN_STILL_SKY_ACTORS")
sun_comp = sun.get_component_by_class(u.DirectionalLightComponent)
sky_comp = sky.get_component_by_class(u.SkyAtmosphereComponent)
if sun_comp is None or sky_comp is None:
    raise RuntimeError("JOB184_P06_SUN_STILL_SKY_COMPONENTS")
original = int(transport.get_current_master_frame().value)
was_playing = bool(transport.is_transport_playing())
if os.path.exists(OUTPUT):
    raise RuntimeError("JOB184_P06_SUN_STILL_OUTPUT_EXISTS|%s" % OUTPUT)
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
state = {"phase": "setup", "wait": 0, "done": False, "handle": None}


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
        u.log("JOB184_P06_SUN_STILL_OK|run=%s|segment=%d:%d|master_frame=%d|source_angle=%.3f|sun_visible=%s|sky_visible=%s|path=%s" %
              (RUN, start, end, target, state["source_angle"], state["sun_visible"],
               state["sky_visible"], OUTPUT))
    else:
        u.log_error("JOB184_P06_SUN_STILL_FAILED|run=%s|%s" % (RUN, detail))


def tick(_delta):
    try:
        if state["phase"] == "setup":
            player.pause()
            transport.scrub_to_master_frame(u.FrameNumber(target))
            state.update(phase="settle", wait=120)
        elif state["phase"] == "settle":
            state["wait"] -= 1
            if state["wait"] <= 0:
                state["source_angle"] = float(sun_comp.get_editor_property("light_source_angle"))
                state["sun_visible"] = bool(sun_comp.is_visible())
                state["sky_visible"] = bool(sky_comp.is_visible())
                u.SystemLibrary.execute_console_command(world, 'HighResShot 1600x900 filename="%s"' % OUTPUT)
                state.update(phase="file", wait=600)
        else:
            state["wait"] -= 1
            if os.path.exists(OUTPUT) and os.path.getsize(OUTPUT) > 1000:
                finish(True)
            elif state["wait"] <= 0:
                finish(False, "file_timeout")
    except Exception as exc:
        finish(False, repr(exc))


state["handle"] = u.register_slate_post_tick_callback(tick)
u.log("JOB184_P06_SUN_STILL_ARMED|run=%s|master_frame=%d|path=%s" % (RUN, target, OUTPUT))
