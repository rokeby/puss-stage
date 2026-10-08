"""PIE-only I2 gobo review stills (gobo session spec, 8 Oct): per I2 frame, scrub the Master to (I2 segment start +
frame*960 ticks) and pause; camera cuts disabled; the view target = "Shore Cast Review Camera" moved to each drape's
review pose, HFOV 50 deg; HighResShot. Restores camera pose, focal, cuts and view target; nothing saved.
GOBOREVIEW_OK|run=.. / GOBOREVIEW_FAILED."""
import datetime, json, math, os
FRAMES = [200, 225, 249, 300]
SHOTS = {"mouth": ((-2441.0, 160000.0, 510.0), 0.0), "hangar": ((13393.0, 78777.0, 510.0), -43.57)}
RES = (1600, 900); SETTLE = 45; FILE_WAIT = 600; TPF = 960


def main():
    import unreal as u
    run = "GOBOREVIEW-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    if w is None:
        u.log_error("GOBOREVIEW_FAILED|run=%s|no PIE" % run); return
    root = list(u.GameplayStatics.get_all_actors_of_class(w, u.InfinityStageShowRoot))[0]
    tr, player = root.transport, root.sequence_player
    seg = [s for s in list(tr.segments) if str(s.label).startswith("Interaction 2")][0]
    acts = {a.get_actor_label(): a for a in u.GameplayStatics.get_all_actors_of_class(w, u.Actor)}
    cam = acts.get("Shore Cast Review Camera")
    pcon = u.GameplayStatics.get_player_controller(w, 0)
    if cam is None:
        u.log_error("GOBOREVIEW_FAILED|run=%s|no review camera" % run); return
    ccc = cam.get_cine_camera_component()
    fb = ccc.get_editor_property("filmback")
    sw = float(fb.get_editor_property("sensor_width"))
    focal = sw / (2.0 * math.tan(math.radians(25.0)))
    orig = {"loc": cam.get_actor_location(), "rot": cam.get_actor_rotation(), "focal": ccc.get_editor_property("current_focal_length"),
            "focus": ccc.get_editor_property("focus_settings"), "vt": pcon.get_view_target(),
            "cuts": player.get_disable_camera_cuts() if hasattr(player, "get_disable_camera_cuts") else False,
            "frame": tr.get_current_master_frame().value}
    out = os.path.join(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()), "CodexConductor", "Captures", run)
    os.makedirs(out, exist_ok=True)
    queue = [(f, n) for f in FRAMES for n in sorted(SHOTS)]
    st = {"i": 0, "ph": "scrub", "wait": 0, "done": False, "h": None, "rows": []}

    def restore():
        cam.set_actor_location_and_rotation(orig["loc"], orig["rot"], False, True)
        ccc.set_editor_property("current_focal_length", orig["focal"]); ccc.set_editor_property("focus_settings", orig["focus"])
        player.set_disable_camera_cuts(orig["cuts"]); pcon.set_view_target_with_blend(orig["vt"], 0.0)

    def finish(ok, why=""):
        if st["done"]: return
        st["done"] = True
        try: restore()
        finally: u.unregister_slate_post_tick_callback(st["h"])
        (u.log if ok else u.log_error)("GOBOREVIEW_%s|run=%s|n=%d|dir=%s|%s" % ("OK" if ok else "FAILED", run, len(st["rows"]), out, why))

    def tick(_dt):
        try:
            if st["done"]: return
            if st["i"] >= len(queue): finish(True); return
            f, n = queue[st["i"]]
            path = os.path.join(out, "f%03d_%s.png" % (f, n)).replace("\\", "/")
            if st["ph"] == "scrub":
                player.pause()
                tr.scrub_to_master_frame(u.FrameNumber(int(seg.start_frame.value + f * TPF)))
                player.set_disable_camera_cuts(True)
                (loc, yaw) = SHOTS[n]
                cam.set_actor_location_and_rotation(u.Vector(*loc), u.Rotator(roll=0.0, pitch=0.0, yaw=yaw), False, True)
                ccc.set_editor_property("current_focal_length", focal)
                fs = ccc.get_editor_property("focus_settings"); fs.set_editor_property("focus_method", u.CameraFocusMethod.MANUAL)
                fs.set_editor_property("manual_focus_distance", 2400.0); ccc.set_editor_property("focus_settings", fs)
                pcon.set_view_target_with_blend(cam, 0.0)
                st.update(ph="settle", wait=SETTLE)
            elif st["ph"] == "settle":
                st["wait"] -= 1
                if st["wait"] <= 0:
                    u.SystemLibrary.execute_console_command(w, 'HighResShot %dx%d filename="%s"' % (RES[0], RES[1], path)); st.update(ph="file", wait=FILE_WAIT)
            else:
                st["wait"] -= 1
                if os.path.exists(path) and os.path.getsize(path) > 1000:
                    st["rows"].append("f%d_%s" % (f, n)); st.update(i=st["i"] + 1, ph="scrub")
                elif st["wait"] <= 0: finish(False, "FILE_TIMEOUT|" + path)
        except Exception as exc:  # noqa: BLE001
            finish(False, repr(exc))

    st["h"] = u.register_slate_post_tick_callback(tick)
    u.log("GOBOREVIEW_ARMED|run=%s|n=%d|focal=%.2f|sensor=%.2f" % (run, len(queue), focal, sw))


main()
