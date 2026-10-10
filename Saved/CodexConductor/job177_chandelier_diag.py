"""Read-only P56 runtime diagnosis in Job 177's owned PIE."""
import json
import math
import os
import unreal as u

RUN = "J177-P56-DIAG-20261010"
OUT = "E:/PussStage/Saved/CodexConductor/job177_chandelier_diag.json"
FRACTION = 0.5
WAIT = 120
BODY_LABEL = "P75 P06 Chandelier Body"
FLAME_PREFIX = "P56_P75_P06_Chandelier_Body_Candle_"


def _v(v):
    return [round(float(v.x), 3), round(float(v.y), 3), round(float(v.z), 3)]


def _r(v):
    return [round(float(v.roll), 3), round(float(v.pitch), 3), round(float(v.yaw), 3)]


def _hidden(a):
    try:
        return bool(a.is_hidden())
    except Exception:
        return None


def _asset(x):
    try:
        return x.get_path_name() if x else None
    except Exception:
        return str(x) if x else None


def _mesh(c):
    return {"name": str(c.get_name()), "static_mesh": _asset(c.get_editor_property("static_mesh")),
            "visible": bool(c.is_visible()), "active": bool(c.is_active()),
            "materials": [_asset(m) for m in c.get_materials()]}


def _niagara(c):
    row = {"name": str(c.get_name()), "asset": _asset(c.get_asset()),
           "auto_activate": bool(c.get_editor_property("auto_activate")),
           "active": bool(c.is_active()), "visible": bool(c.is_visible())}
    try:
        row["registered"] = bool(c.is_registered())
    except Exception:
        row["registered"] = None
    return row


def main():
    if os.path.exists(OUT):
        raise RuntimeError("JOB177_CHANDELIER_DIAG_FAILED|output_exists")
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    if world is None:
        raise RuntimeError("JOB177_CHANDELIER_DIAG_FAILED|no_owned_pie")
    roots = list(u.GameplayStatics.get_all_actors_of_class(world, u.InfinityStageShowRoot))
    if len(roots) != 1:
        raise RuntimeError("JOB177_CHANDELIER_DIAG_FAILED|roots=%d" % len(roots))
    transport, player = roots[0].transport, roots[0].sequence_player
    segments = [s for s in list(transport.segments) if str(s.label) == "Passage 6"]
    if len(segments) != 1:
        raise RuntimeError("JOB177_CHANDELIER_DIAG_FAILED|segments=%d" % len(segments))
    actors = {str(a.get_actor_label()): a for a in u.GameplayStatics.get_all_actors_of_class(world, u.Actor)}
    body = actors.get(BODY_LABEL)
    flames = [a for label, a in actors.items() if label.startswith(FLAME_PREFIX) and label.endswith("_Flame")]
    if body is None or len(flames) != 44:
        raise RuntimeError("JOB177_CHANDELIER_DIAG_FAILED|body=%s|flames=%d" % (body is not None, len(flames)))
    controller = u.GameplayStatics.get_player_controller(world, 0)
    seg = segments[0]; start, end = int(seg.start_frame.value), int(seg.end_frame.value)
    target = start + int(round(FRACTION * (end - start - 1000)))
    original, playing = int(transport.get_current_master_frame().value), bool(transport.is_transport_playing())
    state = {"wait": WAIT, "done": False, "handle": None}
    player.pause(); transport.scrub_to_master_frame(u.FrameNumber(target))

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
            u.log("JOB177_CHANDELIER_DIAG_OK|run=%s|frame=%d|body_meshes=%d|flames=44|active=%d|auto=%d|report=%s" %
                  (RUN, target, state["body_meshes"], state["active"], state["auto"], OUT))
        else:
            u.log_error("JOB177_CHANDELIER_DIAG_FAILED|run=%s|%s" % (RUN, detail))

    def tick(_dt):
        try:
            if state["done"]:
                return
            state["wait"] -= 1
            if state["wait"] > 0:
                return
            camera = controller.get_view_target()
            cine = None
            try:
                cine = camera.get_cine_camera_component()
            except Exception:
                pass
            camera_row = {"label": str(camera.get_actor_label()), "class": camera.get_class().get_name(),
                          "location": _v(camera.get_actor_location()), "rotation": _r(camera.get_actor_rotation())}
            if cine:
                pp = cine.get_editor_property("post_process_settings")
                camera_row.update(focal_mm=round(float(cine.get_editor_property("current_focal_length")), 4),
                                  exposure_bias=round(float(pp.get_editor_property("auto_exposure_bias")), 4),
                                  exposure_override=bool(pp.get_editor_property("override_auto_exposure_bias")))
            origin, extent = body.get_actor_bounds(False, True)
            meshes = [_mesh(c) for c in body.get_components_by_class(u.StaticMeshComponent)]
            flame_rows = []
            for actor in sorted(flames, key=lambda a: str(a.get_actor_label())):
                comps = [_niagara(c) for c in actor.get_components_by_class(u.NiagaraComponent)]
                flame_rows.append({"label": str(actor.get_actor_label()), "hidden": _hidden(actor),
                                   "location": _v(actor.get_actor_location()), "parent": str(actor.get_attach_parent_actor().get_actor_label()) if actor.get_attach_parent_actor() else None,
                                   "components": comps})
            active = sum(1 for r in flame_rows for c in r["components"] if c["active"])
            auto = sum(1 for r in flame_rows for c in r["components"] if c["auto_activate"])
            report = {"run": RUN, "master_frame": target, "camera": camera_row,
                      "body": {"label": BODY_LABEL, "hidden": _hidden(body),
                               "location": _v(body.get_actor_location()), "rotation": _r(body.get_actor_rotation()),
                               "bounds_origin": _v(origin), "bounds_extent": _v(extent), "meshes": meshes},
                      "flames": flame_rows, "active_niagara": active, "auto_activate_niagara": auto,
                      "activation_contract": "P56 tool creates attached level actors only; no activation track or activate call"}
            with open(OUT, "w", encoding="utf-8") as h:
                json.dump(report, h, indent=2)
            state.update(body_meshes=len(meshes), active=active, auto=auto)
            finish(True)
        except Exception as exc:
            finish(False, repr(exc))

    state["handle"] = u.register_slate_post_tick_callback(tick)
    u.log("JOB177_CHANDELIER_DIAG_ARMED|run=%s|frame=%d" % (RUN, target))


main()
