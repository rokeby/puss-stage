"""Capture exact S1 frames and census live light components in Job 184-owned PIE."""
import json
import math
import os
import unreal as u


RUN = "JOB184-S1-LUMINANCE-AFTER-20261010"
ROOT = "E:/PussStage/Saved/CodexConductor/ApplyPass_20261010/stills"
REPORT = "E:/PussStage/Saved/CodexConductor/job184_s1_luminance_light_probe_after.json"
FRAMES = [3600, 3700, 3800, 3880, 3899]
OUTPUTS = {
    3600: ROOT + "/184_09_s1_frame3600_after.png",
    3700: ROOT + "/184_10_s1_frame3700_after.png",
    3800: ROOT + "/184_11_s1_frame3800_after.png",
    3880: ROOT + "/184_12_s1_frame3880_after.png",
    3899: ROOT + "/184_13_s1_frame3899_end_after.png",
}


def vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def distance(a, b):
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def safe_property(obj, name):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return None


world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
if world is None:
    raise RuntimeError("JOB184_S1_PROBE_NO_OWNED_PIE")
roots = list(u.GameplayStatics.get_all_actors_of_class(world, u.InfinityStageShowRoot))
if len(roots) != 1 or roots[0].sequence_player is None:
    raise RuntimeError("JOB184_S1_PROBE_SHOW_ROOT|%d" % len(roots))
root = roots[0]
transport, player = root.transport, root.sequence_player
segments = [s for s in list(transport.segments) if str(s.label).startswith("Scene 1")]
if len(segments) != 1:
    raise RuntimeError("JOB184_S1_PROBE_SEGMENTS|%d" % len(segments))
start, end = int(segments[0].start_frame.value), int(segments[0].end_frame.value)
span = end - start
original = int(transport.get_current_master_frame().value)
was_playing = bool(transport.is_transport_playing())
controller = u.GameplayStatics.get_player_controller(world, 0)
manager = u.GameplayStatics.get_player_camera_manager(world, 0)
if controller is None or manager is None:
    raise RuntimeError("JOB184_S1_PROBE_CAMERA")
for output in OUTPUTS.values():
    if os.path.exists(output):
        raise RuntimeError("JOB184_S1_PROBE_OUTPUT_EXISTS|%s" % output)
os.makedirs(ROOT, exist_ok=True)
actors = list(u.GameplayStatics.get_all_actors_of_class(world, u.Actor))
state = {"index": 0, "phase": "pose", "wait": 0, "done": False, "handle": None, "rows": []}


def target_for(local_frame):
    target = start + int(round(local_frame * span / 3900.0))
    return min(target, end - 1)


def light_rows():
    camera_location = vec(manager.get_camera_location())
    rows = []
    for actor in actors:
        components = list(actor.get_components_by_class(u.LightComponentBase))
        for component in components:
            intensity = float(component.get_editor_property("intensity"))
            visible = bool(component.is_visible())
            active = bool(component.is_active())
            actor_location = vec(actor.get_actor_location())
            hidden = safe_property(actor, "hidden")
            affects_world = safe_property(component, "affects_world")
            rows.append({
                "actor_label": str(actor.get_actor_label()),
                "actor_class": actor.get_class().get_name(),
                "component_name": str(component.get_name()),
                "component_class": component.get_class().get_name(),
                "intensity": intensity,
                "visible": visible,
                "active": active,
                "actor_hidden": None if hidden is None else bool(hidden),
                "affects_world": None if affects_world is None else bool(affects_world),
                "actor_location_cm": actor_location,
                "camera_distance_cm": distance(camera_location, actor_location),
                # LightComponentBase.is_active() is false for rendering lights in this UE 5.8
                # runtime; visible/intensity/affects_world are the measured on-state surface.
                "runtime_on": bool(intensity > 1.0e-4 and visible and hidden is not True and
                                   affects_world is not False),
            })
    return sorted(rows, key=lambda row: (not row["runtime_on"], row["camera_distance_cm"], row["actor_label"], row["component_name"]))


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
        with open(REPORT, "x", encoding="utf-8") as handle:
            json.dump({"run": RUN, "segment": [start, end], "frames": state["rows"]}, handle,
                      indent=2, sort_keys=True)
        row3880 = next(row for row in state["rows"] if row["local_frame"] == 3880)
        u.log("JOB184_S1_LUMINANCE_LIGHT_PROBE_OK|run=%s|frames=5|on3880=%d|segment=%d:%d|report=%s" %
              (RUN, row3880["runtime_on_count"], start, end, REPORT))
    else:
        u.log_error("JOB184_S1_LUMINANCE_LIGHT_PROBE_FAILED|run=%s|%s" % (RUN, detail))


def tick(_delta):
    try:
        if state["phase"] == "pose":
            local_frame = FRAMES[state["index"]]
            player.pause()
            transport.scrub_to_master_frame(u.FrameNumber(target_for(local_frame)))
            state.update(phase="settle", wait=90)
        elif state["phase"] == "settle":
            state["wait"] -= 1
            if state["wait"] <= 0:
                local_frame = FRAMES[state["index"]]
                rows = light_rows()
                output = OUTPUTS[local_frame]
                state["rows"].append({
                    "local_frame": local_frame,
                    "master_frame": target_for(local_frame),
                    "output": output,
                    "camera_location_cm": vec(manager.get_camera_location()),
                    "runtime_on_count": sum(row["runtime_on"] for row in rows),
                    "lights": rows,
                })
                u.SystemLibrary.execute_console_command(world, 'HighResShot 1600x900 filename="%s"' % output)
                state.update(phase="file", wait=600)
        else:
            state["wait"] -= 1
            local_frame = FRAMES[state["index"]]
            output = OUTPUTS[local_frame]
            if os.path.exists(output) and os.path.getsize(output) > 1000:
                state["index"] += 1
                if state["index"] >= len(FRAMES):
                    finish(True)
                else:
                    state["phase"] = "pose"
            elif state["wait"] <= 0:
                finish(False, "file_timeout|%s" % output)
    except Exception as exc:
        finish(False, repr(exc))


state["handle"] = u.register_slate_post_tick_callback(tick)
u.log("JOB184_S1_LUMINANCE_LIGHT_PROBE_ARMED|run=%s|frames=%s|segment=%d:%d" %
      (RUN, ",".join(str(frame) for frame in FRAMES), start, end))
