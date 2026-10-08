"""PIE-only close-up stills of the S3 shoreguys' live cloth (v3, 8 Oct): pattern = MiScalars/pearl_variant_shots.py
(move + focus the CURRENT view-target cine camera, HighResShot, wait for the file, restore). Run after the transport is
paused in S3 (pvs_scrub style). Per figure "<id> Clam": front-3/4 and back-3/4 at head height, 230 cm.
Nothing saved; editor world untouched. CLOTHSHOT_OK|run=.. / CLOTHSHOT_FAILED."""
import datetime, json, math, os
FIGS = ["Shore01_M56", "Shore02_F52", "Shore03_M59", "Shore04_F55", "Shore06_F25"]
SHOTS = (("front", 35.0, 8.0, 230.0), ("back", 200.0, 15.0, 230.0))
RES = (1600, 900); SETTLE = 40; FILE_WAIT = 600


def main():
    import unreal as u
    run = "CLOTHSHOT-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    if world is None:
        u.log_error("CLOTHSHOT_FAILED|run=%s|no PIE" % run); return
    acts = {a.get_actor_label(): a for a in u.GameplayStatics.get_all_actors_of_class(world, u.Actor)}
    pcon = u.GameplayStatics.get_player_controller(world, 0)
    cam = pcon.get_view_target()
    ccc = cam.get_cine_camera_component() if hasattr(cam, "get_cine_camera_component") else None
    if ccc is None:
        u.log_error("CLOTHSHOT_FAILED|run=%s|no cine view target" % run); return
    orig = {"loc": cam.get_actor_location(), "rot": cam.get_actor_rotation(), "focus": ccc.get_editor_property("focus_settings"),
            "ap": ccc.get_editor_property("current_aperture")}
    out = os.path.join(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()), "CodexConductor", "Captures", run)
    os.makedirs(out, exist_ok=True)
    queue = []
    for f in FIGS:
        a = acts.get(f + " Clam")
        if a is None:
            continue
        o, e = a.get_actor_bounds(False)
        tgt = u.Vector(o.x, o.y, o.z + e.z * 0.45)
        fwd = a.get_actor_forward_vector()
        base = math.degrees(math.atan2(fwd.y, fwd.x))
        for s in SHOTS:
            queue.append((f, s, tgt, base))
    st = {"i": 0, "phase": "setup", "wait": 0, "rows": [], "done": False, "h": None}

    def aim(tgt, base, s):
        _n, yaw_d, el_d, dist = s
        yaw, el = math.radians(base + yaw_d), math.radians(el_d)
        loc = u.Vector(tgt.x + dist * math.cos(el) * math.cos(yaw), tgt.y + dist * math.cos(el) * math.sin(yaw), tgt.z + dist * math.sin(el))
        cam.set_actor_location_and_rotation(loc, u.MathLibrary.find_look_at_rotation(loc, tgt), False, True)
        fs = ccc.get_editor_property("focus_settings")
        fs.set_editor_property("focus_method", u.CameraFocusMethod.MANUAL)
        fs.set_editor_property("manual_focus_distance", float(dist))
        ccc.set_editor_property("focus_settings", fs)
        ccc.set_editor_property("current_aperture", 8.0)

    def finish(ok, why=""):
        if st["done"]: return
        st["done"] = True
        try:
            cam.set_actor_location_and_rotation(orig["loc"], orig["rot"], False, True)
            ccc.set_editor_property("focus_settings", orig["focus"]); ccc.set_editor_property("current_aperture", orig["ap"])
        finally:
            u.unregister_slate_post_tick_callback(st["h"])
        if ok: u.log("CLOTHSHOT_OK|run=%s|n=%d|dir=%s" % (run, len(st["rows"]), out))
        else: u.log_error("CLOTHSHOT_FAILED|run=%s|%s|restored=1" % (run, why))

    def tick(_dt):
        try:
            if st["done"]: return
            if u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world() is None:
                st["done"] = True; u.unregister_slate_post_tick_callback(st["h"]); return
            if st["i"] >= len(queue): finish(True); return
            f, s, tgt, base = queue[st["i"]]
            path = os.path.join(out, "%s__%s.png" % (f, s[0])).replace("\\", "/")
            if st["phase"] == "setup":
                aim(tgt, base, s); st.update(phase="settle", wait=SETTLE)
            elif st["phase"] == "settle":
                st["wait"] -= 1
                if st["wait"] <= 0:
                    u.SystemLibrary.execute_console_command(world, 'HighResShot %dx%d filename="%s"' % (RES[0], RES[1], path))
                    st.update(phase="file", wait=FILE_WAIT)
            else:
                st["wait"] -= 1
                if os.path.exists(path) and os.path.getsize(path) > 1000:
                    st["rows"].append(f + "/" + s[0]); st.update(i=st["i"] + 1, phase="setup")
                elif st["wait"] <= 0:
                    finish(False, "FILE_TIMEOUT|" + path)
        except Exception as exc:  # noqa: BLE001
            finish(False, repr(exc))

    st["h"] = u.register_slate_post_tick_callback(tick)
    u.log("CLOTHSHOT_ARMED|run=%s|n=%d" % (run, len(queue)))


main()
