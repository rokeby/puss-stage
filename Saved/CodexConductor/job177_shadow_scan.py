"""Second read-only runtime scan: identify unnamed Sequencer shadow spawnables."""
import json
import math
import os
import unreal as u

RUN = "J177-J144-SHADOW-SCAN-20261010"
OUT = "E:/PussStage/Saved/CodexConductor/job177_shadow_scan.json"
LOCAL_FRAME = 712
WAIT = 90


def _v(v):
    return [round(float(v.x), 3), round(float(v.y), 3), round(float(v.z), 3)]


def _hidden(a):
    try:
        return bool(a.is_hidden())
    except Exception:
        return None


def _d(a, b):
    x, y = a.get_actor_location(), b.get_actor_location()
    return math.sqrt((x.x-y.x)**2 + (x.y-y.y)**2 + (x.z-y.z)**2)


def _row(a):
    r = {"label": str(a.get_actor_label()), "name": str(a.get_name()),
         "class": a.get_class().get_name(), "path": a.get_path_name(),
         "hidden": _hidden(a), "location": _v(a.get_actor_location())}
    lights = list(a.get_components_by_class(u.LightComponent))
    if lights:
        c = lights[0]
        r["light"] = {}
        for p in ("intensity", "attenuation_radius", "cast_shadows", "visible", "affects_world"):
            try:
                x = c.get_editor_property(p)
                r["light"][p] = round(float(x), 4) if isinstance(x, float) else bool(x)
            except Exception as e:
                r["light"][p] = "ERR:" + repr(e)
        try:
            r["light"]["active"] = bool(c.is_active())
        except Exception:
            r["light"]["active"] = None
    meshes = list(a.get_components_by_class(u.StaticMeshComponent))
    if meshes:
        r["meshes"] = []
        for c in meshes:
            try:
                mesh = c.get_editor_property("static_mesh")
                asset = mesh.get_path_name() if mesh else None
            except Exception:
                asset = None
            r["meshes"].append({"name": str(c.get_name()), "asset": asset,
                                "visible": bool(c.is_visible()), "active": bool(c.is_active())})
    return r


def main():
    if os.path.exists(OUT):
        raise RuntimeError("JOB177_SHADOW_SCAN_FAILED|output_exists")
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    if world is None:
        raise RuntimeError("JOB177_SHADOW_SCAN_FAILED|no_owned_pie")
    roots = list(u.GameplayStatics.get_all_actors_of_class(world, u.InfinityStageShowRoot))
    if len(roots) != 1:
        raise RuntimeError("JOB177_SHADOW_SCAN_FAILED|roots=%d" % len(roots))
    transport, player = roots[0].transport, roots[0].sequence_player
    controller = u.GameplayStatics.get_player_controller(world, 0)
    segments = {}
    for name in ("I1", "I2", "I3"):
        n = int(name[1:])
        hits = [s for s in list(transport.segments) if str(s.label).startswith("Interaction %d" % n)]
        if len(hits) != 1:
            raise RuntimeError("JOB177_SHADOW_SCAN_FAILED|%s_segments=%d" % (name, len(hits)))
        segments[name] = hits[0]
    original = int(transport.get_current_master_frame().value)
    playing = bool(transport.is_transport_playing())
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
                json.dump({"run": RUN, "rows": state["rows"]}, h, indent=2)
            u.log("JOB177_SHADOW_SCAN_OK|run=%s|rows=%d|report=%s" % (RUN, len(state["rows"]), OUT))
        else:
            u.log_error("JOB177_SHADOW_SCAN_FAILED|run=%s|%s" % (RUN, detail))

    def tick(_dt):
        try:
            if state["done"]:
                return
            if state["wait"]:
                state["wait"] -= 1
                if not state["wait"]:
                    name = names[state["i"]]
                    camera = controller.get_view_target()
                    actors = list(u.GameplayStatics.get_all_actors_of_class(world, u.Actor))
                    lights = [a for a in actors if list(a.get_components_by_class(u.LightComponent))]
                    nearby = [a for a in actors if _d(a, camera) <= 6000.0 and
                              (list(a.get_components_by_class(u.StaticMeshComponent)) or
                               list(a.get_components_by_class(u.LightComponent)) or
                               "camera" in a.get_class().get_name().lower())]
                    state["rows"].append({"passage": name, "master_frame": int(segments[name].start_frame.value)+LOCAL_FRAME,
                                          "camera": _row(camera),
                                          "lights": [_row(a) for a in lights],
                                          "nearby": [_row(a) for a in nearby]})
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
    u.log("JOB177_SHADOW_SCAN_ARMED|run=%s" % RUN)


main()
