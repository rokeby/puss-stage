"""Read-only-at-source runtime probe for Job 185's P06 sun-disc diagnosis."""
import json
import unreal as u

OUT = u.Paths.project_saved_dir() + "CodexConductor/Job185P06Sun/probe.json"


def read(obj, name):
    try:
        value = obj.get_editor_property(name)
        if hasattr(value, "x") and hasattr(value, "y"):
            return str(value)
        return value if isinstance(value, (bool, int, float, str)) or value is None else str(value)
    except Exception as exc:
        return "ERROR:" + repr(exc)


world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
if world is None:
    raise RuntimeError("JOB185_P06_SUN_PROBE|NO_OWNED_PIE")
roots = list(u.GameplayStatics.get_all_actors_of_class(world, u.InfinityStageShowRoot))
if len(roots) != 1 or roots[0].sequence_player is None:
    raise RuntimeError("JOB185_P06_SUN_PROBE|SHOW_ROOTS=%d" % len(roots))
root = roots[0]
transport, player = root.transport, root.sequence_player
segments = [s for s in list(transport.segments) if str(s.label) == "Passage 6"]
if len(segments) != 1:
    raise RuntimeError("JOB185_P06_SUN_PROBE|SEGMENTS=%d" % len(segments))
start, end = int(segments[0].start_frame.value), int(segments[0].end_frame.value)
target = start + int(round(0.25 * 24000))
original = int(transport.get_current_master_frame().value)
was_playing = bool(transport.is_transport_playing())
state = {"phase": "setup", "wait": 0, "done": False, "handle": None}


def actor_row(actor):
    comp = actor.get_component_by_class(u.DirectionalLightComponent)
    return {
        "label": str(actor.get_actor_label()), "class": str(actor.get_class().get_path_name()),
        "hidden": read(actor, "hidden"), "hidden_in_game": read(actor, "hidden_in_game"),
        "actor_hidden_method": bool(actor.is_hidden()) if hasattr(actor, "is_hidden") else None,
        "component_visible": bool(comp.is_visible()) if comp else None,
        "component_active": bool(comp.is_active()) if comp else None,
        "atmosphere_sun_light": read(comp, "atmosphere_sun_light") if comp else None,
        "atmosphere_sun_light_index": read(comp, "atmosphere_sun_light_index") if comp else None,
        "light_source_angle": read(comp, "light_source_angle") if comp else None,
        "intensity": read(comp, "intensity") if comp else None,
        "temperature": read(comp, "temperature") if comp else None,
        "rotation": str(actor.get_actor_rotation()),
        "forward": str(actor.get_actor_forward_vector()),
    }


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
        u.log("JOB185_P06_SUN_PROBE_OK|frame=%d|path=%s" % (target, OUT))
    else:
        u.log_error("JOB185_P06_SUN_PROBE_FAILED|" + detail)


def tick(_delta):
    try:
        if state["phase"] == "setup":
            player.pause()
            transport.scrub_to_master_frame(u.FrameNumber(target))
            state.update(phase="settle", wait=120)
            return
        state["wait"] -= 1
        if state["wait"] > 0:
            return
        actors = list(u.GameplayStatics.get_all_actors_of_class(world, u.Actor))
        directionals = [actor_row(a) for a in actors if a.get_component_by_class(u.DirectionalLightComponent)]
        skies = []
        for actor in actors:
            comp = actor.get_component_by_class(u.SkyAtmosphereComponent)
            if not comp:
                continue
            skies.append({
                "label": str(actor.get_actor_label()), "class": str(actor.get_class().get_path_name()),
                "hidden": read(actor, "hidden"), "hidden_in_game": read(actor, "hidden_in_game"),
                "actor_hidden_method": bool(actor.is_hidden()) if hasattr(actor, "is_hidden") else None,
                "component_visible": bool(comp.is_visible()), "component_active": bool(comp.is_active()),
                "transform_mode": read(comp, "transform_mode"), "bottom_radius": read(comp, "bottom_radius"),
            })
        controller = u.GameplayStatics.get_player_controller(world, 0)
        view = controller.get_view_target() if controller else None
        cine = view.get_component_by_class(u.CineCameraComponent) if view else None
        pp = cine.get_editor_property("post_process_settings") if cine else None
        exposure = {name: read(pp, name) for name in (
            "override_auto_exposure_method", "auto_exposure_method", "override_auto_exposure_bias",
            "auto_exposure_bias", "override_auto_exposure_min_brightness", "auto_exposure_min_brightness",
            "override_auto_exposure_max_brightness", "auto_exposure_max_brightness", "override_auto_exposure_low_percent",
            "auto_exposure_low_percent", "override_auto_exposure_high_percent", "auto_exposure_high_percent")}
        report = {"frame": target, "segment": [start, end], "directionals": directionals, "skies": skies,
                  "view_target": str(view.get_actor_label()) if view else None,
                  "camera_post_process_blend_weight": read(cine, "post_process_blend_weight") if cine else None,
                  "exposure": exposure,
                  "sky_hidden_policy_note": "P18 editor-only temporary hide is not expected to set PIE bHidden; runtime values above decide."}
        with open(OUT, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
        finish(True)
    except Exception as exc:
        finish(False, repr(exc))


state["handle"] = u.register_slate_post_tick_callback(tick)
u.log("JOB185_P06_SUN_PROBE_ARMED|frame=%d" % target)
