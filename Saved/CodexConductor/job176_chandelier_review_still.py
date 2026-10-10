"""Runtime-only close review of Job 176's P56 chandelier in owned PIE."""
import json
import os

import unreal as u


HERE = "E:/PussStage/Saved/CodexConductor/"
ARGS_PATH = HERE + "job176_chandelier_review_still_args.json"
SETTLE_TICKS = 120
FILE_WAIT_TICKS = 600


def _local_point(actor, values):
    origin = actor.get_actor_location()
    return (origin + actor.get_actor_forward_vector() * float(values[0])
            + actor.get_actor_right_vector() * float(values[1])
            + actor.get_actor_up_vector() * float(values[2]))


def main():
    args = json.load(open(ARGS_PATH, encoding="utf-8"))
    run = str(args["run_id"])
    passage = str(args["passage"])
    fraction = float(args["fraction"])
    output = str(args["output"]).replace("\\", "/")
    if passage.upper() != "P6" or not (0.0 <= fraction < 1.0):
        raise RuntimeError("JOB176_CHANDELIER_REVIEW_FAILED|run=%s|bad_passage_or_fraction" % run)
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    if world is None:
        raise RuntimeError("JOB176_CHANDELIER_REVIEW_FAILED|run=%s|no_owned_pie" % run)
    roots = list(u.GameplayStatics.get_all_actors_of_class(world, u.InfinityStageShowRoot))
    if len(roots) != 1:
        raise RuntimeError("JOB176_CHANDELIER_REVIEW_FAILED|run=%s|show_roots=%d" % (run, len(roots)))
    show_root = roots[0]
    transport = show_root.transport
    player = show_root.sequence_player
    segments = [s for s in list(transport.segments) if str(s.label) == "Passage 6"]
    if len(segments) != 1:
        raise RuntimeError("JOB176_CHANDELIER_REVIEW_FAILED|run=%s|segments=%d" % (run, len(segments)))
    actors = {str(a.get_actor_label()): a for a in u.GameplayStatics.get_all_actors_of_class(world, u.Actor)}
    body = actors.get(str(args["body_actor_label"]))
    camera = actors.get(str(args["camera_actor_label"]))
    flames = [a for label, a in actors.items() if label.startswith("P56_P75_P06_Chandelier_Body_Candle_") and label.endswith("_Flame")]
    if body is None or camera is None or len(flames) != 44:
        raise RuntimeError("JOB176_CHANDELIER_REVIEW_FAILED|run=%s|body=%s|camera=%s|flames=%d" %
                           (run, body is not None, camera is not None, len(flames)))
    cine = camera.get_cine_camera_component()
    controller = u.GameplayStatics.get_player_controller(world, 0)
    if cine is None or controller is None:
        raise RuntimeError("JOB176_CHANDELIER_REVIEW_FAILED|run=%s|cine=%s|controller=%s" %
                           (run, cine is not None, controller is not None))
    seg = segments[0]
    start, end = int(seg.start_frame.value), int(seg.end_frame.value)
    target_frame = start + int(round(fraction * (end - start - 1000)))
    original = {
        "loc": camera.get_actor_location(),
        "rot": camera.get_actor_rotation(),
        "focal": cine.get_editor_property("current_focal_length"),
        "pp_weight": cine.get_editor_property("post_process_blend_weight"),
        "pp_bias": cine.get_editor_property("post_process_settings").get_editor_property("auto_exposure_bias"),
        "pp_bias_override": cine.get_editor_property("post_process_settings").get_editor_property("override_auto_exposure_bias"),
        "view": controller.get_view_target(),
        "cuts": player.get_disable_camera_cuts() if hasattr(player, "get_disable_camera_cuts") else False,
        "frame": int(transport.get_current_master_frame().value),
        "playing": bool(transport.is_transport_playing()),
    }
    location = _local_point(body, args["camera_offset_local_cm"])
    target = _local_point(body, args["target_offset_local_cm"])
    rotation = u.MathLibrary.find_look_at_rotation(location, target)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    if os.path.exists(output):
        raise RuntimeError("JOB176_CHANDELIER_REVIEW_FAILED|run=%s|output_exists" % run)
    state = {"phase": "setup", "wait": 0, "handle": None, "done": False}

    def restore():
        camera.set_actor_location_and_rotation(original["loc"], original["rot"], False, True)
        cine.set_editor_property("current_focal_length", original["focal"])
        settings = cine.get_editor_property("post_process_settings")
        settings.set_editor_property("auto_exposure_bias", original["pp_bias"])
        settings.set_editor_property("override_auto_exposure_bias", original["pp_bias_override"])
        cine.set_editor_property("post_process_settings", settings)
        cine.set_editor_property("post_process_blend_weight", original["pp_weight"])
        if hasattr(player, "set_disable_camera_cuts"):
            player.set_disable_camera_cuts(original["cuts"])
        controller.set_view_target_with_blend(original["view"], 0.0)
        transport.scrub_to_master_frame(u.FrameNumber(original["frame"]))
        if original["playing"]:
            player.play()
        else:
            player.pause()

    def finish(ok, detail=""):
        if state["done"]:
            return
        state["done"] = True
        active_components = 0
        for flame in flames:
            for component in flame.get_components_by_class(u.NiagaraComponent):
                if component.is_active():
                    active_components += 1
        try:
            restore()
        finally:
            u.unregister_slate_post_tick_callback(state["handle"])
        if ok:
            u.log("JOB176_CHANDELIER_REVIEW_OK|run=%s|passage=%s|fraction=%.6f|frame=%d|flame_actors=44|active_niagara=%d|path=%s|runtime_camera_only=true" %
                  (run, passage, fraction, target_frame, active_components, output))
        else:
            u.log_error("JOB176_CHANDELIER_REVIEW_FAILED|run=%s|%s" % (run, detail))

    def tick(_delta):
        try:
            if state["done"]:
                return
            if state["phase"] == "setup":
                player.pause()
                transport.scrub_to_master_frame(u.FrameNumber(target_frame))
                if hasattr(player, "set_disable_camera_cuts"):
                    player.set_disable_camera_cuts(True)
                camera.set_actor_location_and_rotation(location, rotation, False, True)
                cine.set_editor_property("current_focal_length", float(args["focal_mm"]))
                settings = cine.get_editor_property("post_process_settings")
                settings.set_editor_property("override_auto_exposure_bias", True)
                settings.set_editor_property("auto_exposure_bias", float(args["exposure_bias"]))
                cine.set_editor_property("post_process_settings", settings)
                cine.set_editor_property("post_process_blend_weight", 1.0)
                controller.set_view_target_with_blend(camera, 0.0)
                state.update(phase="settle", wait=SETTLE_TICKS)
            elif state["phase"] == "settle":
                state["wait"] -= 1
                if state["wait"] <= 0:
                    u.SystemLibrary.execute_console_command(world, 'HighResShot 1600x900 filename="%s"' % output)
                    state.update(phase="file", wait=FILE_WAIT_TICKS)
            else:
                state["wait"] -= 1
                if os.path.exists(output) and os.path.getsize(output) > 1000:
                    finish(True)
                elif state["wait"] <= 0:
                    finish(False, "file_timeout|" + output)
        except Exception as exc:
            finish(False, repr(exc))

    state["handle"] = u.register_slate_post_tick_callback(tick)
    u.log("JOB176_CHANDELIER_REVIEW_ARMED|run=%s|passage=%s|fraction=%.6f|frame=%d|flame_actors=44|path=%s" %
          (run, passage, fraction, target_frame, output))


main()
