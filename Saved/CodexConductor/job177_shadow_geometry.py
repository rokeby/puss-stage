"""Read-only runtime geometry/occlusion checks for Job 144 I2/I3."""
import json
import math
import os
import unreal as u

RUN = "J177-J144-GEOMETRY-20261010"
OUT = "E:/PussStage/Saved/CodexConductor/job177_shadow_geometry.json"
ROOT = "E:/PussStage/Saved/CodexConductor/Job144InteractionHangar_20261010/"
WAIT = 90
LOCAL_FRAME = 712


def _v(v):
    return [round(float(v.x), 3), round(float(v.y), 3), round(float(v.z), 3)]


def _vec(values):
    return u.Vector(float(values[0]), float(values[1]), float(values[2]))


def _dist(a, b):
    return math.sqrt((a.x-b.x)**2 + (a.y-b.y)**2 + (a.z-b.z)**2)


def _components(actor):
    return [{"class": c.get_class().get_name(), "name": str(c.get_name()),
             "visible": bool(c.is_visible()) if hasattr(c, "is_visible") else None}
            for c in actor.get_components_by_class(u.ActorComponent)]


def _actor(actor, point):
    origin, extent = actor.get_actor_bounds(False, True)
    return {"label": str(actor.get_actor_label()), "name": str(actor.get_name()),
            "class": actor.get_class().get_name(), "path": actor.get_path_name(),
            "location": _v(actor.get_actor_location()), "distance_cm": round(_dist(actor.get_actor_location(), point), 3),
            "bounds_origin": _v(origin), "bounds_extent": _v(extent), "components": _components(actor)}


def _trace(world, start, end, ignore):
    try:
        hit = u.SystemLibrary.line_trace_single(world, start, end, u.TraceTypeQuery.TRACE_TYPE_QUERY1,
                                                False, ignore, u.DrawDebugTrace.NONE, True)
        actor = hit.get_actor()
        return {"blocking": bool(hit.is_valid_blocking_hit()),
                "actor": str(actor.get_actor_label()) if actor else None,
                "actor_name": str(actor.get_name()) if actor else None,
                "location": _v(hit.location), "distance_cm": round(float(hit.distance), 3)}
    except Exception as exc:
        return {"error": repr(exc)}


def _plan(n):
    pin = json.load(open(ROOT + "job144_plan_I%d.json" % n, encoding="utf-8"))
    report = json.load(open(pin["report"], encoding="utf-8"))
    return report["plan"]


def main():
    if os.path.exists(OUT):
        raise RuntimeError("JOB177_SHADOW_GEOMETRY_FAILED|output_exists")
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    if world is None:
        raise RuntimeError("JOB177_SHADOW_GEOMETRY_FAILED|no_owned_pie")
    roots = list(u.GameplayStatics.get_all_actors_of_class(world, u.InfinityStageShowRoot))
    if len(roots) != 1:
        raise RuntimeError("JOB177_SHADOW_GEOMETRY_FAILED|roots=%d" % len(roots))
    transport, player = roots[0].transport, roots[0].sequence_player
    segments = {}
    plans = {"I2": _plan(2), "I3": _plan(3)}
    for name in plans:
        n = int(name[1:])
        hits = [s for s in list(transport.segments) if str(s.label).startswith("Interaction %d" % n)]
        if len(hits) != 1:
            raise RuntimeError("JOB177_SHADOW_GEOMETRY_FAILED|%s_segments=%d" % (name, len(hits)))
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
            u.log("JOB177_SHADOW_GEOMETRY_OK|run=%s|rows=%d|report=%s" % (RUN, len(state["rows"]), OUT))
        else:
            u.log_error("JOB177_SHADOW_GEOMETRY_FAILED|run=%s|%s" % (RUN, detail))

    def tick(_dt):
        try:
            if state["done"]:
                return
            if state["wait"]:
                state["wait"] -= 1
                if not state["wait"]:
                    name = names[state["i"]]; plan = plans[name]
                    actors = list(u.GameplayStatics.get_all_actors_of_class(world, u.Actor))
                    spot_target = _vec(plan["spot"]["loc"])
                    spots = [a for a in actors if list(a.get_components_by_class(u.SpotLightComponent))
                             and _dist(a.get_actor_location(), spot_target) < 5.0]
                    if len(spots) != 1:
                        raise RuntimeError("%s_spot_count=%d" % (name, len(spots)))
                    spot = spots[0]
                    points = {"camera_target": _vec(plan["camera_target_world"]["loc"]),
                              "card": u.Vector(float(plan["shadow_sources"][0]["pose"]["Location.X"]),
                                               float(plan["shadow_sources"][0]["pose"]["Location.Y"]),
                                               float(plan["shadow_sources"][0]["pose"]["Location.Z"])),
                              "curtain": _vec(plan["curtain_target"]["loc"]),
                              "wall": _vec(plan["wall"]["interior_point"])}
                    nearest = {}
                    traces = {}
                    for key, point in points.items():
                        rows = sorted((_actor(a, point) for a in actors), key=lambda x: x["distance_cm"])
                        nearest[key] = rows[:5]
                        traces[key] = _trace(world, spot.get_actor_location(), point, [spot])
                    state["rows"].append({"passage": name, "spot": _actor(spot, spot_target),
                                          "points": {k: _v(v) for k, v in points.items()},
                                          "nearest": nearest, "traces": traces,
                                          "distances_cm": {k: round(_dist(spot.get_actor_location(), v), 3) for k, v in points.items()}})
                    state["i"] += 1
                return
            if state["i"] >= len(names):
                finish(True); return
            name = names[state["i"]]
            player.pause()
            transport.scrub_to_master_frame(u.FrameNumber(int(segments[name].start_frame.value)+LOCAL_FRAME))
            state["wait"] = WAIT
        except Exception as exc:
            finish(False, repr(exc))

    state["handle"] = u.register_slate_post_tick_callback(tick)
    u.log("JOB177_SHADOW_GEOMETRY_ARMED|run=%s" % RUN)


main()
