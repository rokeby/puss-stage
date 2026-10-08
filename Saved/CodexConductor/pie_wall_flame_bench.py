"""PIE-only bench (Gary 8 Oct: "sounds good"): a REFLECTION-ONLY flame on the S3 handprint wall shot. Reuses an existing
dark "S3 Choir Glint" point light (0 cd, hidden) -> moves it low beside/behind the CURRENT view camera, sets
SpecularScale 1 / DiffuseScale 0, small source, warm 2200 K, and captures variants via HighResShot. Run after the
transport is paused on the B06 wall shot (pie_seg_goto + pause). Everything restored; nothing saved.
WALLFLAME_OK|run=.. / WALLFLAME_FAILED."""
import datetime, os
VARIANTS = [("a_as_is", 0.0), ("b_flame_subtle", 400.0), ("c_flame_strong", 1500.0)]
OFFSET = (-60.0, 90.0, -70.0)     # camera-local: behind, right, below (cm)
RES = (1600, 900); SETTLE = 30; FILE_WAIT = 600


def main():
    import unreal as u
    run = "WALLFLAME-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    if w is None:
        u.log_error("WALLFLAME_FAILED|run=%s|no PIE" % run); return
    lights = [a for a in u.GameplayStatics.get_all_actors_of_class(w, u.Actor) if str(a.get_actor_label()).startswith("S3 Choir Glint")]
    if not lights:
        u.log_error("WALLFLAME_FAILED|run=%s|no S3 Choir Glint" % run); return
    la = lights[0]; lc = la.get_component_by_class(u.PointLightComponent)
    cam = u.GameplayStatics.get_player_camera_manager(w, 0)
    cl, cr = cam.get_camera_location(), cam.get_camera_rotation()
    f, r, up = u.MathLibrary.get_forward_vector(cr), u.MathLibrary.get_right_vector(cr), u.MathLibrary.get_up_vector(cr)
    # v2 (8 Oct): mirror geometry. Trace from the camera along its forward axis to the wall; the light sits on the
    # REFLECTED view ray from the hit point, so its specular image lands at frame centre on the marks.
    end = u.Vector(cl.x + f.x * 5000, cl.y + f.y * 5000, cl.z + f.z * 5000)
    hit = u.SystemLibrary.line_trace_single(w, cl, end, u.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [], u.DrawDebugTrace.NONE, True)
    hr = hit[1] if isinstance(hit, tuple) else hit
    bh = hr.to_tuple() if hr is not None and hasattr(hr, "to_tuple") else None
    if not bh or not bh[0]:
        u.log_error("WALLFLAME_FAILED|run=%s|no wall hit|%r" % (run, type(hit))); return
    u.log("WALLFLAME_HIT|actor=%s" % (bh[9].get_actor_label() if len(bh) > 9 and bh[9] else "?"))
    P, N = bh[4], bh[7]      # HitResult tuple: (blocking, initial_overlap, time, distance, location, impact_point, normal, impact_normal, ...)
    d = f; dn = d.x * N.x + d.y * N.y + d.z * N.z
    rr = u.Vector(d.x - 2 * dn * N.x, d.y - 2 * dn * N.y, d.z - 2 * dn * N.z)
    DIST = 400.0
    pos = u.Vector(P.x + rr.x * DIST, P.y + rr.y * DIST, P.z + rr.z * DIST)
    u.log("WALLFLAME_GEOM|hit=%s|normal=%s|reflect=%s" % (P, N, rr))
    orig = {"loc": la.get_actor_location(), "hid": la.get_editor_property("hidden"), "int": lc.intensity,
            "vis": lc.is_visible(), "spec": lc.get_editor_property("specular_scale"), "diff": lc.get_editor_property("diffuse_scale"),
            "rad": lc.get_editor_property("source_radius"), "temp": lc.get_editor_property("temperature"),
            "ut": lc.get_editor_property("use_temperature")}
    out = os.path.join(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()), "CodexConductor", "Captures", run)
    os.makedirs(out, exist_ok=True)
    st = {"i": 0, "ph": "set", "wait": 0, "done": False, "h": None, "rows": []}

    def restore():
        la.set_actor_location(orig["loc"], False, True); la.set_actor_hidden_in_game(orig["hid"])
        lc.set_intensity(orig["int"]); lc.set_visibility(orig["vis"], False)
        for k, n in (("spec", "specular_scale"), ("diff", "diffuse_scale"), ("rad", "source_radius"), ("temp", "temperature"), ("ut", "use_temperature")):
            lc.set_editor_property(n, orig[k])

    def finish(ok, why=""):
        if st["done"]: return
        st["done"] = True
        try: restore()
        finally: u.unregister_slate_post_tick_callback(st["h"])
        (u.log if ok else u.log_error)("WALLFLAME_%s|run=%s|n=%d|dir=%s|%s" % ("OK" if ok else "FAILED", run, len(st["rows"]), out, why))

    def tick(_dt):
        try:
            if st["done"]: return
            if st["i"] >= len(VARIANTS): finish(True); return
            name, cd = VARIANTS[st["i"]]
            path = os.path.join(out, name + ".png").replace("\\", "/")
            if st["ph"] == "set":
                if cd > 0:
                    la.set_actor_location(pos, False, True); la.set_actor_hidden_in_game(False); lc.set_visibility(True, False)
                    lc.set_editor_property("diffuse_scale", 0.0); lc.set_editor_property("specular_scale", 1.0)
                    lc.set_editor_property("source_radius", 3.0); lc.set_editor_property("use_temperature", True)
                    lc.set_editor_property("temperature", 2200.0); lc.set_intensity(cd)
                else:
                    restore()
                st.update(ph="settle", wait=SETTLE)
            elif st["ph"] == "settle":
                st["wait"] -= 1
                if st["wait"] <= 0:
                    u.SystemLibrary.execute_console_command(w, 'HighResShot %dx%d filename="%s"' % (RES[0], RES[1], path)); st.update(ph="file", wait=FILE_WAIT)
            else:
                st["wait"] -= 1
                if os.path.exists(path) and os.path.getsize(path) > 1000:
                    st["rows"].append(name); st.update(i=st["i"] + 1, ph="set")
                elif st["wait"] <= 0: finish(False, "FILE_TIMEOUT|" + path)
        except Exception as exc:  # noqa: BLE001
            finish(False, repr(exc))

    st["h"] = u.register_slate_post_tick_callback(tick)
    u.log("WALLFLAME_ARMED|run=%s|light=%s|pos=%s" % (run, la.get_actor_label(), pos))


main()
