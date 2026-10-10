"""Read-only runtime measurement of the I1/I2/I3 shadow frame in owned PIE."""
import json
import math
import os

import unreal as u


RUN = "J177-J144-SHADOW-DIAG-20261010"
OUT = "E:/PussStage/Saved/CodexConductor/job177_shadow_diag.json"
LOCAL_FRAME = 712
SETTLE_TICKS = 100


def _v(v):
    return [round(float(v.x), 3), round(float(v.y), 3), round(float(v.z), 3)]


def _rot(v):
    return [round(float(v.roll), 3), round(float(v.pitch), 3), round(float(v.yaw), 3)]


def _dist(a, b):
    av, bv = a.get_actor_location(), b.get_actor_location()
    return round(math.sqrt((av.x-bv.x)**2 + (av.y-bv.y)**2 + (av.z-bv.z)**2), 3)


def _hidden(actor):
    try:
        return bool(actor.is_hidden())
    except Exception:
        try:
            return bool(actor.get_editor_property("hidden"))
        except Exception:
            return None


def _actor_row(actor):
    origin, extent = actor.get_actor_bounds(False, True)
    comps = []
    for comp in actor.get_components_by_class(u.SceneComponent):
        row = {"class": comp.get_class().get_name(), "name": str(comp.get_name())}
        for key, method in (("visible", "is_visible"), ("active", "is_active")):
            try:
                row[key] = bool(getattr(comp, method)())
            except Exception:
                row[key] = None
        comps.append(row)
    return {
        "label": str(actor.get_actor_label()),
        "class": actor.get_class().get_name(),
        "path": actor.get_path_name(),
        "hidden": _hidden(actor),
        "location": _v(actor.get_actor_location()),
        "rotation": _rot(actor.get_actor_rotation()),
        "bounds_origin": _v(origin),
        "bounds_extent": _v(extent),
        "components": comps,
    }


def _light_row(actor):
    row = _actor_row(actor)
    comps = list(actor.get_components_by_class(u.LightComponent))
    comp = comps[0] if comps else None
    if comp is not None:
        for prop in ("intensity", "attenuation_radius", "cast_shadows", "affects_world", "visible"):
            try:
                value = comp.get_editor_property(prop)
                row[prop] = round(float(value), 4) if isinstance(value, float) else bool(value) if isinstance(value, bool) else str(value)
            except Exception:
                row[prop] = None
        try:
            row["component_active"] = bool(comp.is_active())
        except Exception:
            row["component_active"] = None
    return row


def _trace(world, start_actor, target_actor):
    start, end = start_actor.get_actor_location(), target_actor.get_actor_location()
    try:
        hit = u.SystemLibrary.line_trace_single(
            world, start, end, u.TraceTypeQuery.TRACE_TYPE_QUERY1, False,
            [start_actor], u.DrawDebugTrace.NONE, True)
        actor = hit.get_actor()
        return {
            "ok": True,
            "blocking": bool(hit.is_valid_blocking_hit()),
            "hit_actor": str(actor.get_actor_label()) if actor else None,
            "hit_location": _v(hit.location),
            "trace_distance_cm": round(float(hit.distance), 3),
        }
    except Exception as exc:
        return {"ok": False, "error": repr(exc)}


def _camera_row(controller):
    view = controller.get_view_target()
    row = _actor_row(view) if view else {"label": None, "class": None}
    cine = None
    try:
        cine = view.get_cine_camera_component()
    except Exception:
        pass
    if cine is not None:
        settings = cine.get_editor_property("post_process_settings")
        row["focal_mm"] = round(float(cine.get_editor_property("current_focal_length")), 4)
        row["post_process_blend_weight"] = round(float(cine.get_editor_property("post_process_blend_weight")), 4)
        row["auto_exposure_bias"] = round(float(settings.get_editor_property("auto_exposure_bias")), 4)
        row["override_auto_exposure_bias"] = bool(settings.get_editor_property("override_auto_exposure_bias"))
        for prop in ("auto_exposure_min_brightness", "auto_exposure_max_brightness"):
            try:
                row[prop] = round(float(settings.get_editor_property(prop)), 4)
            except Exception:
                row[prop] = None
    return row


def _matches(actors, pattern):
    text = pattern.lower()
    return [a for a in actors if text in str(a.get_actor_label()).lower()]


def _measure(world, controller, passage, master_frame):
    actors = list(u.GameplayStatics.get_all_actors_of_class(world, u.Actor))
    lights = [a for a in actors if "shadow" in str(a.get_actor_label()).lower()
              and list(a.get_components_by_class(u.LightComponent))]
    cards = _matches(actors, "Shadow Card")
    drapes = _matches(actors, "Hangar Drape")
    walls = [a for a in actors if "Hangar Far Wall" in str(a.get_actor_label())]
    visible_lights = [a for a in lights if not _hidden(a)]
    shadow = visible_lights[0] if len(visible_lights) == 1 else None
    row = {
        "passage": passage,
        "local_frame": LOCAL_FRAME,
        "master_frame": master_frame,
        "view_target": _camera_row(controller),
        "shadow_lights": [_light_row(a) for a in lights],
        "cards": [_actor_row(a) for a in cards],
        "drapes": [_actor_row(a) for a in drapes],
        "far_walls": [_actor_row(a) for a in walls],
        "visible_shadow_light_count": len(visible_lights),
    }
    if shadow is not None:
        row["selected_shadow_light"] = str(shadow.get_actor_label())
        row["distances_cm"] = {
            "light_to_cards": {str(a.get_actor_label()): _dist(shadow, a) for a in cards},
            "light_to_drapes": {str(a.get_actor_label()): _dist(shadow, a) for a in drapes},
            "light_to_walls": {str(a.get_actor_label()): _dist(shadow, a) for a in walls},
        }
        row["visibility_traces"] = {
            "to_cards": {str(a.get_actor_label()): _trace(world, shadow, a) for a in cards},
            "to_drapes": {str(a.get_actor_label()): _trace(world, shadow, a) for a in drapes},
            "to_walls": {str(a.get_actor_label()): _trace(world, shadow, a) for a in walls},
        }
    return row


def main():
    if os.path.exists(OUT):
        raise RuntimeError("JOB177_SHADOW_DIAG_FAILED|output_exists")
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    if world is None:
        raise RuntimeError("JOB177_SHADOW_DIAG_FAILED|no_owned_pie")
    roots = list(u.GameplayStatics.get_all_actors_of_class(world, u.InfinityStageShowRoot))
    if len(roots) != 1:
        raise RuntimeError("JOB177_SHADOW_DIAG_FAILED|show_roots=%d" % len(roots))
    transport, player = roots[0].transport, roots[0].sequence_player
    controller = u.GameplayStatics.get_player_controller(world, 0)
    if controller is None:
        raise RuntimeError("JOB177_SHADOW_DIAG_FAILED|no_controller")
    segments = {}
    for name in ("I1", "I2", "I3"):
        n = int(name[1:])
        hits = [s for s in list(transport.segments) if str(s.label).startswith("Interaction %d" % n)]
        if len(hits) != 1:
            raise RuntimeError("JOB177_SHADOW_DIAG_FAILED|%s_segments=%d" % (name, len(hits)))
        segments[name] = hits[0]
    original_frame = int(transport.get_current_master_frame().value)
    was_playing = bool(transport.is_transport_playing())
    state = {"index": 0, "wait": 0, "rows": [], "handle": None, "done": False}
    names = ["I1", "I2", "I3"]

    def finish(ok, detail=""):
        if state["done"]:
            return
        state["done"] = True
        try:
            transport.scrub_to_master_frame(u.FrameNumber(original_frame))
            player.play() if was_playing else player.pause()
        finally:
            u.unregister_slate_post_tick_callback(state["handle"])
        if ok:
            with open(OUT, "w", encoding="utf-8") as handle:
                json.dump({"run": RUN, "rows": state["rows"]}, handle, indent=2)
            summary = ";".join("%s:cam=%s,light=%s,visible=%d" % (
                r["passage"], r["view_target"].get("label"), r.get("selected_shadow_light"),
                r["visible_shadow_light_count"]) for r in state["rows"])
            u.log("JOB177_SHADOW_DIAG_OK|run=%s|%s|report=%s" % (RUN, summary, OUT))
        else:
            u.log_error("JOB177_SHADOW_DIAG_FAILED|run=%s|%s" % (RUN, detail))

    def tick(_delta):
        try:
            if state["done"]:
                return
            if state["wait"] > 0:
                state["wait"] -= 1
                if state["wait"] == 0:
                    name = names[state["index"]]
                    seg = segments[name]
                    frame = int(seg.start_frame.value) + LOCAL_FRAME
                    state["rows"].append(_measure(world, controller, name, frame))
                    state["index"] += 1
                return
            if state["index"] >= len(names):
                finish(True)
                return
            name = names[state["index"]]
            seg = segments[name]
            frame = int(seg.start_frame.value) + LOCAL_FRAME
            player.pause()
            transport.scrub_to_master_frame(u.FrameNumber(frame))
            state["wait"] = SETTLE_TICKS
        except Exception as exc:
            finish(False, repr(exc))

    state["handle"] = u.register_slate_post_tick_callback(tick)
    u.log("JOB177_SHADOW_DIAG_ARMED|run=%s|local_frame=%d" % (RUN, LOCAL_FRAME))


main()
