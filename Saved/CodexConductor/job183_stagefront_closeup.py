"""Runtime-only mesh-bounds close-up for an already-owned Job 183 PIE."""
import json
import math
import os

import unreal as u


HERE = "E:/PussStage/Saved/CodexConductor/"
ARGS_PATH = HERE + "job183_stagefront_closeup_args.json"
SETTLE_TICKS = 90
FILE_WAIT_TICKS = 600


def main():
    args = json.load(open(ARGS_PATH, encoding="utf-8"))
    run = str(args["run_id"])
    target_label = str(args["target_actor_label"])
    output = str(args["output"]).replace("\\", "/")
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    if world is None:
        raise RuntimeError("JOB183_STAGEFRONT_CLOSEUP_FAILED|run=%s|no_owned_pie" % run)
    actors = {str(a.get_actor_label()): a for a in u.GameplayStatics.get_all_actors_of_class(world, u.Actor)}
    target = actors.get(target_label)
    camera = actors.get(str(args.get("review_camera_actor_label", "Shore Cast Review Camera")))
    if target is None or camera is None:
        raise RuntimeError("JOB183_STAGEFRONT_CLOSEUP_FAILED|run=%s|target=%s|camera=%s" %
                           (run, target is not None, camera is not None))
    roots = list(u.GameplayStatics.get_all_actors_of_class(world, u.InfinityStageShowRoot))
    if len(roots) != 1:
        raise RuntimeError("JOB183_STAGEFRONT_CLOSEUP_FAILED|run=%s|show_roots=%d" % (run, len(roots)))
    root = roots[0]
    transport, player = root.transport, root.sequence_player
    segments = [s for s in list(transport.segments) if str(s.label).startswith("Opening")]
    if len(segments) != 1:
        raise RuntimeError("JOB183_STAGEFRONT_CLOSEUP_FAILED|run=%s|opening_segments=%d" % (run, len(segments)))
    seg = segments[0]
    start, end = int(seg.start_frame.value), int(seg.end_frame.value)
    fraction = float(args.get("fraction", 0.5))
    frame = start + int(round(fraction * (end - start - 1000)))
    controller = u.GameplayStatics.get_player_controller(world, 0)
    manager = controller.player_camera_manager if controller is not None else None
    cine = camera.get_cine_camera_component()
    if controller is None or manager is None or cine is None:
        raise RuntimeError("JOB183_STAGEFRONT_CLOSEUP_FAILED|run=%s|camera_runtime" % run)
    original = {
        "loc": camera.get_actor_location(), "rot": camera.get_actor_rotation(),
        "focal": cine.get_editor_property("current_focal_length"),
        "pp_weight": cine.get_editor_property("post_process_blend_weight"),
        "view": controller.get_view_target(),
        "cuts": player.get_disable_camera_cuts() if hasattr(player, "get_disable_camera_cuts") else False,
        "frame": int(transport.get_current_master_frame().value),
        "playing": bool(transport.is_transport_playing()),
    }
    if os.path.exists(output):
        raise RuntimeError("JOB183_STAGEFRONT_CLOSEUP_FAILED|run=%s|output_exists" % run)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    state = {"phase": "setup", "wait": 0, "handle": None, "done": False,
             "bounds": None, "review": None}

    def restore():
        camera.set_actor_location_and_rotation(original["loc"], original["rot"], False, True)
        cine.set_editor_property("current_focal_length", original["focal"])
        cine.set_editor_property("post_process_blend_weight", original["pp_weight"])
        if hasattr(player, "set_disable_camera_cuts"):
            player.set_disable_camera_cuts(original["cuts"])
        controller.set_view_target_with_blend(original["view"], 0.0)
        transport.scrub_to_master_frame(u.FrameNumber(original["frame"]))
        player.play() if original["playing"] else player.pause()

    def finish(ok, detail=""):
        if state["done"]:
            return
        state["done"] = True
        try:
            restore()
        finally:
            u.unregister_slate_post_tick_callback(state["handle"])
        if ok:
            b = state["bounds"]
            r = state["review"]
            u.log("JOB183_STAGEFRONT_CLOSEUP_OK|run=%s|target=%s|frame=%d|origin=%s|extent=%s|distance=%.3f|fov=%.3f|exposure_override=0|path=%s" %
                  (run, target_label, frame, b[0], b[1], r["distance"], r["fov"], output))
        else:
            u.log_error("JOB183_STAGEFRONT_CLOSEUP_FAILED|run=%s|%s" % (run, detail))

    def tick(_delta):
        try:
            if state["done"]:
                return
            if state["phase"] == "setup":
                player.pause()
                transport.scrub_to_master_frame(u.FrameNumber(frame))
                state.update(phase="source_wait", wait=10)
                return
            if state["phase"] == "source_wait":
                state["wait"] -= 1
                if state["wait"] > 0:
                    return
                origin, extent = target.get_actor_bounds(False, False)
                source = manager.get_camera_location()
                direction = source - origin
                length = max(1.0, direction.length())
                direction = direction / length
                fov = max(20.0, min(90.0, float(manager.get_fov_angle())))
                aspect = float(args.get("aspect", 1600.0 / 900.0))
                vfov = 2.0 * math.atan(math.tan(math.radians(fov) * 0.5) / aspect)
                margin = float(args.get("margin", 1.18))
                distance = margin * max(float(extent.y) / math.tan(math.radians(fov) * 0.5),
                                        float(extent.z) / math.tan(vfov * 0.5), 100.0)
                location = origin + direction * distance
                rotation = u.MathLibrary.find_look_at_rotation(location, origin)
                filmback = cine.get_editor_property("filmback")
                sensor_width = float(filmback.get_editor_property("sensor_width"))
                focal = sensor_width / (2.0 * math.tan(math.radians(fov) * 0.5))
                cine.set_editor_property("current_focal_length", focal)
                cine.set_editor_property("post_process_blend_weight", 0.0)
                if hasattr(player, "set_disable_camera_cuts"):
                    player.set_disable_camera_cuts(True)
                camera.set_actor_location_and_rotation(location, rotation, False, True)
                controller.set_view_target_with_blend(camera, 0.0)
                state["bounds"] = ([origin.x, origin.y, origin.z], [extent.x, extent.y, extent.z])
                state["review"] = {"distance": distance, "fov": fov}
                state.update(phase="settle", wait=SETTLE_TICKS)
                return
            if state["phase"] == "settle":
                state["wait"] -= 1
                if state["wait"] <= 0:
                    u.SystemLibrary.execute_console_command(world, 'HighResShot 1600x900 filename="%s"' % output)
                    state.update(phase="file", wait=FILE_WAIT_TICKS)
                return
            state["wait"] -= 1
            if os.path.isfile(output) and os.path.getsize(output) > 1000:
                finish(True)
            elif state["wait"] <= 0:
                finish(False, "file_timeout|" + output)
        except Exception as exc:
            finish(False, repr(exc))

    state["handle"] = u.register_slate_post_tick_callback(tick)
    u.log("JOB183_STAGEFRONT_CLOSEUP_ARMED|run=%s|target=%s|frame=%d|path=%s" %
          (run, target_label, frame, output))


main()
