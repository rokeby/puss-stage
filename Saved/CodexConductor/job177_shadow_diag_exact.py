"""Exact Job 176-frame runtime measurements for I1/I2/I3 in owned PIE."""
import json
import math
import os
import unreal as u

RUN = "J177-J144-SHADOW-EXACT-20261010"
OUT = "E:/PussStage/Saved/CodexConductor/job177_shadow_diag_exact.json"
ROOT = "E:/PussStage/Saved/CodexConductor/Job144InteractionHangar_20261010/"
FRACTION = 0.3198562444
WAIT = 100


def _v(v):
    return [round(float(v.x), 3), round(float(v.y), 3), round(float(v.z), 3)]


def _distv(a, b):
    return math.sqrt((a.x-b.x)**2 + (a.y-b.y)**2 + (a.z-b.z)**2)


def _plan(n):
    pin = json.load(open(ROOT + "job144_plan_I%d.json" % n, encoding="utf-8"))
    return json.load(open(pin["report"], encoding="utf-8"))["plan"]


def _camera(controller):
    actor = controller.get_view_target()
    row = {"label": str(actor.get_actor_label()), "name": str(actor.get_name()),
           "class": actor.get_class().get_name(), "location": _v(actor.get_actor_location()),
           "rotation": [round(float(x), 3) for x in (actor.get_actor_rotation().roll,
                                                      actor.get_actor_rotation().pitch,
                                                      actor.get_actor_rotation().yaw)]}
    try:
        cine = actor.get_cine_camera_component()
    except Exception:
        cine = None
    if cine:
        pp = cine.get_editor_property("post_process_settings")
        row.update(focal_mm=round(float(cine.get_editor_property("current_focal_length")), 4),
                   post_process_blend_weight=round(float(cine.get_editor_property("post_process_blend_weight")), 4),
                   auto_exposure_bias=round(float(pp.get_editor_property("auto_exposure_bias")), 4),
                   override_auto_exposure_bias=bool(pp.get_editor_property("override_auto_exposure_bias")),
                   auto_exposure_min=round(float(pp.get_editor_property("auto_exposure_min_brightness")), 4),
                   auto_exposure_max=round(float(pp.get_editor_property("auto_exposure_max_brightness")), 4))
    return actor, row


def _light(actor, camera):
    comp = list(actor.get_components_by_class(u.SpotLightComponent))[0]
    return {"label": str(actor.get_actor_label()), "name": str(actor.get_name()),
            "location": _v(actor.get_actor_location()), "camera_distance_cm": round(_distv(actor.get_actor_location(), camera.get_actor_location()), 3),
            "intensity_cd": round(float(comp.get_editor_property("intensity")), 4),
            "attenuation_radius_cm": round(float(comp.get_editor_property("attenuation_radius")), 4),
            "visible": bool(comp.is_visible()), "cast_shadows": bool(comp.get_editor_property("cast_shadows")),
            "affects_world": bool(comp.get_editor_property("affects_world"))}


def _nearest(actors, point, count=3):
    rows = []
    for actor in actors:
        d = _distv(actor.get_actor_location(), point)
        origin, extent = actor.get_actor_bounds(False, True)
        rows.append({"label": str(actor.get_actor_label()), "name": str(actor.get_name()),
                     "class": actor.get_class().get_name(), "location": _v(actor.get_actor_location()),
                     "distance_cm": round(d, 3), "bounds_origin": _v(origin), "bounds_extent": _v(extent),
                     "components": [c.get_class().get_name() for c in actor.get_components_by_class(u.ActorComponent)]})
    return sorted(rows, key=lambda r: r["distance_cm"])[:count]


def main():
    if os.path.exists(OUT):
        raise RuntimeError("JOB177_SHADOW_EXACT_FAILED|output_exists")
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    if world is None:
        raise RuntimeError("JOB177_SHADOW_EXACT_FAILED|no_owned_pie")
    roots = list(u.GameplayStatics.get_all_actors_of_class(world, u.InfinityStageShowRoot))
    if len(roots) != 1:
        raise RuntimeError("JOB177_SHADOW_EXACT_FAILED|roots=%d" % len(roots))
    transport, player = roots[0].transport, roots[0].sequence_player
    controller = u.GameplayStatics.get_player_controller(world, 0)
    segments = {}
    for name in ("I1", "I2", "I3"):
        n = int(name[1:])
        hits = [s for s in list(transport.segments) if str(s.label).startswith("Interaction %d" % n)]
        if len(hits) != 1:
            raise RuntimeError("JOB177_SHADOW_EXACT_FAILED|%s_segments=%d" % (name, len(hits)))
        segments[name] = hits[0]
    plans = {"I2": _plan(2), "I3": _plan(3)}
    original, playing = int(transport.get_current_master_frame().value), bool(transport.is_transport_playing())
    names = ["I1", "I2", "I3"]
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
                json.dump({"run": RUN, "fraction": FRACTION, "rows": state["rows"]}, h, indent=2)
            u.log("JOB177_SHADOW_EXACT_OK|run=%s|%s|report=%s" %
                  (RUN, ";".join("%s:frame=%d,cam=%s,lights=%d" % (r["passage"], r["master_frame"], r["camera"]["label"], len(r["shadow_light_candidates"])) for r in state["rows"]), OUT))
        else:
            u.log_error("JOB177_SHADOW_EXACT_FAILED|run=%s|%s" % (RUN, detail))

    def tick(_dt):
        try:
            if state["done"]:
                return
            if state["wait"]:
                state["wait"] -= 1
                if not state["wait"]:
                    name = names[state["i"]]
                    camera_actor, camera_row = _camera(controller)
                    actors = list(u.GameplayStatics.get_all_actors_of_class(world, u.Actor))
                    candidates = []
                    for actor in actors:
                        comps = list(actor.get_components_by_class(u.SpotLightComponent))
                        if not comps:
                            continue
                        comp = comps[0]
                        intensity = float(comp.get_editor_property("intensity"))
                        radius = float(comp.get_editor_property("attenuation_radius"))
                        if 7400.0 <= intensity <= 7600.0 and 4490.0 <= radius <= 4510.0:
                            candidates.append(_light(actor, camera_actor))
                    row = {"passage": name, "master_frame": state["target"], "camera": camera_row,
                           "shadow_light_candidates": candidates}
                    if name in plans:
                        plan = plans[name]
                        points = {"spot": u.Vector(*plan["spot"]["loc"]),
                                  "card": u.Vector(float(plan["shadow_sources"][0]["pose"]["Location.X"]),
                                                   float(plan["shadow_sources"][0]["pose"]["Location.Y"]),
                                                   float(plan["shadow_sources"][0]["pose"]["Location.Z"])),
                                  "curtain": u.Vector(*plan["curtain_target"]["loc"]),
                                  "wall": u.Vector(*plan["wall"]["interior_point"])}
                        row["planned_points"] = {k: _v(v) for k, v in points.items()}
                        row["nearest"] = {k: _nearest(actors, v) for k, v in points.items()}
                        row["ordered_distances_from_planned_spot_cm"] = {k: round(_distv(points["spot"], v), 3) for k, v in points.items()}
                    state["rows"].append(row)
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
    u.log("JOB177_SHADOW_EXACT_ARMED|run=%s|fraction=%.10f" % (RUN, FRACTION))


main()
