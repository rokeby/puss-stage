"""READ-ONLY PIE probe for I2 (9 Oct): is the held hangar camera in front of the hangar drape?
Phase SCRUB: performance mode off (original to a file first) -> scrub the Master to I2 frame PROBE_FRAME -> pause ->
restore performance mode. Phase PROBE (a later call): the view camera's location/forward/FOV, the hangar drape actor(s)
(label contains "Drape"), their visibility, world bounds, and the signed distance of the 8 bound corners along the
camera's forward axis (all > 0 = in front; mixed = camera inside; all < 0 = behind); GeometryCache components'
playing state; the hangar shadow-play spot's light function. Nothing is written. Markers I2PROBE_*|run=..."""
import datetime
import json
import math
import os

PHASE = globals().get("I2P_PHASE", "SCRUB")
PROBE_FRAME = int(globals().get("I2P_FRAME", 200))
HERE = "E:/PussStage/Saved/CodexConductor/I2Order_20261008/"


def main():
    import unreal as u
    run = "I2PROBE-" + datetime.datetime.now().strftime("%H%M%S")
    w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    if w is None:
        u.log_error("I2PROBE_FAILED|run=%s|no PIE" % run)
        return
    root = list(u.GameplayStatics.get_all_actors_of_class(w, u.InfinityStageShowRoot))[0]
    tr = root.transport
    if PHASE == "SCRUB":
        segs = [s for s in list(tr.segments) if str(s.label).startswith("Interaction 2")]
        if len(segs) != 1:
            u.log_error("I2PROBE_FAILED|run=%s|I2 segments %d" % (run, len(segs)))
            return
        a = int(segs[0].start_frame.value)
        target = a + int(round(PROBE_FRAME * 24000 / 25.0))
        state = HERE + "i2_drape_probe_state.json"
        orig = bool(tr.get_editor_property("performance_mode"))
        json.dump({"performance_mode": orig}, open(state, "w"))
        try:
            tr.set_editor_property("performance_mode", False)
            res = tr.scrub_to_master_frame(u.FrameNumber(target))
            root.sequence_player.pause()
        finally:
            tr.set_editor_property("performance_mode", orig)
        u.log("I2PROBE_SCRUB_OK|run=%s|res=%s|now=%d|target=%d|pm=%s(restored)"
              % (run, res, int(tr.get_current_master_frame().value), target, orig))
        return
    pc = u.GameplayStatics.get_player_controller(w, 0)
    cm = u.GameplayStatics.get_player_camera_manager(w, 0)
    vt = pc.get_view_target() if pc else None
    cl, cr = cm.get_camera_location(), cm.get_camera_rotation()
    fwd = u.MathLibrary.get_forward_vector(cr)
    out = {"run": run, "frame": PROBE_FRAME, "view_target": vt.get_actor_label() if vt else None,
           "cam": [cl.x, cl.y, cl.z], "rot": [cr.roll, cr.pitch, cr.yaw], "fov": float(cm.get_fov_angle()), "drapes": [],
           "spots": []}
    for a in u.GameplayStatics.get_all_actors_of_class(w, u.Actor):
        lab = a.get_actor_label()
        # spawnables carry their TEMPLATE label in PIE (the spots came back as "Spot Light"), so match GC actors by class too
        if "Drape" in lab or "Curtain" in lab or isinstance(a, u.GeometryCacheActor):
            o, e = a.get_actor_bounds(False)
            ds = []
            for sx in (-1, 1):
                for sy in (-1, 1):
                    for sz in (-1, 1):
                        p = u.Vector(o.x + sx * e.x, o.y + sy * e.y, o.z + sz * e.z)
                        ds.append(round((p.x - cl.x) * fwd.x + (p.y - cl.y) * fwd.y + (p.z - cl.z) * fwd.z, 1))
            gcs = []
            for c in a.get_components_by_class(u.GeometryCacheComponent):
                gca = c.get_editor_property("geometry_cache")
                row = {"comp": c.get_name(), "visible": bool(c.is_visible()),
                       "asset": gca.get_path_name() if gca else None,
                       "hidden_in_game": bool(c.get_editor_property("hidden_in_game"))}
                for fn in ("is_playing", "get_animation_time", "get_playback_speed", "get_duration"):
                    try:
                        row[fn] = getattr(c, fn)()
                    except Exception as exc:  # noqa: BLE001
                        row[fn] = "ERR %s" % type(exc).__name__
                gcs.append(row)
            out["drapes"].append({"label": lab, "class": a.get_class().get_name(), "hidden": bool(a.get_editor_property("hidden")),
                                  "origin": [o.x, o.y, o.z], "extent": [e.x, e.y, e.z],
                                  "dist_along_fwd_min_max": [min(ds), max(ds)], "gc": gcs})
        if "Shadow Play Spot" in lab or "Spot Light" == lab[:10]:
            lc = a.get_component_by_class(u.LightComponent)
            if lc:
                lf = lc.get_editor_property("light_function_material")
                out["spots"].append({"label": lab, "intensity": float(lc.get_editor_property("intensity")),
                                     "lf": lf.get_path_name() if lf else None, "visible": bool(lc.is_visible()),
                                     "loc": [a.get_actor_location().x, a.get_actor_location().y, a.get_actor_location().z]})
    p = HERE + "i2_drape_probe_%s.json" % run
    json.dump(out, open(p, "w"), indent=1, default=str)
    u.log("I2PROBE_OK|run=%s|cam=%s|drapes=%s|file=%s" % (run, [round(x) for x in out["cam"]],
          json.dumps([(d["label"], d["hidden"], d["dist_along_fwd_min_max"]) for d in out["drapes"]]), p))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("I2PROBE_FAILED|%s: %s" % (type(exc).__name__, exc))
