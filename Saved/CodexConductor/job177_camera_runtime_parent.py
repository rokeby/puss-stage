"""Exact-frame runtime camera attachment measurement for Job 144."""
import json
import os
import unreal as u

RUN = "J177-J144-RUNTIME-PARENT-20261010"
OUT = "E:/PussStage/Saved/CodexConductor/job177_camera_runtime_parent.json"
FRACTION = 0.3198562444
WAIT = 90


def _v(v):
    return [round(float(v.x), 4), round(float(v.y), 4), round(float(v.z), 4)]


def _r(v):
    return [round(float(v.roll), 4), round(float(v.pitch), 4), round(float(v.yaw), 4)]


if os.path.exists(OUT):
    raise RuntimeError("JOB177_RUNTIME_PARENT_FAILED|output_exists")
world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
if world is None:
    raise RuntimeError("JOB177_RUNTIME_PARENT_FAILED|no_owned_pie")
roots = list(u.GameplayStatics.get_all_actors_of_class(world, u.InfinityStageShowRoot))
if len(roots) != 1:
    raise RuntimeError("JOB177_RUNTIME_PARENT_FAILED|roots=%d" % len(roots))
transport, player = roots[0].transport, roots[0].sequence_player
controller = u.GameplayStatics.get_player_controller(world, 0)
segments = {}
for name in ("I2", "I3"):
    n = int(name[1:])
    hits = [s for s in list(transport.segments) if str(s.label).startswith("Interaction %d" % n)]
    if len(hits) != 1:
        raise RuntimeError("JOB177_RUNTIME_PARENT_FAILED|%s_segments=%d" % (name, len(hits)))
    segments[name] = hits[0]
original, playing = int(transport.get_current_master_frame().value), bool(transport.is_transport_playing())
names = ["I2", "I3"]
state = {"i": 0, "wait": 0, "rows": [], "done": False, "handle": None}


def finish(ok, detail=""):
    if state["done"]:
        return
    state["done"] = True
    try:
        transport.scrub_to_master_frame(u.FrameNumber(original))
        player.play() if playing else player.pause()
    finally:
        u.unregister_slate_post_tick_callback(state["handle"])
    if ok:
        with open(OUT, "w", encoding="utf-8") as h:
            json.dump({"run": RUN, "rows": state["rows"]}, h, indent=2)
        u.log("JOB177_RUNTIME_PARENT_OK|run=%s|rows=%s|report=%s" %
              (RUN, ";".join("%s:parent=%s,world=%s,relative=%s" %
                              (r["passage"], r["parent_label"], r["camera_world_location"], r["camera_relative_location"]) for r in state["rows"]), OUT))
    else:
        u.log_error("JOB177_RUNTIME_PARENT_FAILED|run=%s|%s" % (RUN, detail))


def tick(_dt):
    try:
        if state["done"]:
            return
        if state["wait"]:
            state["wait"] -= 1
            if not state["wait"]:
                name = names[state["i"]]
                camera = controller.get_view_target(); root = camera.get_editor_property("root_component")
                parent = camera.get_attach_parent_actor()
                state["rows"].append({"passage": name, "master_frame": state["target"],
                                      "camera_label": str(camera.get_actor_label()),
                                      "camera_world_location": _v(camera.get_actor_location()),
                                      "camera_world_rotation": _r(camera.get_actor_rotation()),
                                      "camera_relative_location": _v(root.get_editor_property("relative_location")),
                                      "camera_relative_rotation": _r(root.get_editor_property("relative_rotation")),
                                      "parent_label": str(parent.get_actor_label()) if parent else None,
                                      "parent_world_location": _v(parent.get_actor_location()) if parent else None,
                                      "parent_world_rotation": _r(parent.get_actor_rotation()) if parent else None})
                state["i"] += 1
            return
        if state["i"] >= len(names):
            finish(True); return
        name = names[state["i"]]; seg = segments[name]
        start, end = int(seg.start_frame.value), int(seg.end_frame.value)
        state["target"] = start + int(round(FRACTION * (end - start - 1000)))
        player.pause(); transport.scrub_to_master_frame(u.FrameNumber(state["target"])); state["wait"] = WAIT
    except Exception as exc:
        finish(False, repr(exc))


state["handle"] = u.register_slate_post_tick_callback(tick)
u.log("JOB177_RUNTIME_PARENT_ARMED|run=%s" % RUN)
