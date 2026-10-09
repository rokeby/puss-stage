"""READ-ONLY PIE probe (9 Oct): which camera is live across the S2 -> I2 boundary?  Gary: "i2 with the boy shadow
initially cut to P03? then glitched back to P02".  Offline facts [I2ENTRY-230602, P27 record]: the Master has NO
camera-cut sections within +-400 frames of I2 (master 18255); I2's own cuts are hangar [0,1250) / mouth [1250,2226).
So this MEASURES it: performance mode off (original to a file first), scrub the Master to I2 start - LEAD frames,
play, and on every slate tick log the master frame, the view target label, camera location and the player's
current sub-sequence; after TICKS ticks pause and restore performance mode.  Writes only a JSON under Saved.
Never ends PIE, never saves.  Markers I2VT_STARTED|run=.. then I2VT_OK|run=..|file=.. / I2VT_FAILED|run=..
"""
import datetime
import json

LEAD = int(globals().get("I2VT_LEAD", 50))          # master frames (25 fps) before I2 start
TICKS = int(globals().get("I2VT_TICKS", 240))
HERE = "E:/PussStage/Saved/CodexConductor/I2Order_20261008/"


def main():
    import unreal as u
    run = "I2VT-" + datetime.datetime.now().strftime("%H%M%S")
    w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    if w is None:
        u.log_error("I2VT_FAILED|run=%s|no PIE" % run)
        return
    root = list(u.GameplayStatics.get_all_actors_of_class(w, u.InfinityStageShowRoot))[0]
    tr = root.transport
    segs = [s for s in list(tr.segments) if str(s.label).startswith("Interaction 2")]
    if len(segs) != 1:
        u.log_error("I2VT_FAILED|run=%s|I2 segments %d" % (run, len(segs)))
        return
    a = int(segs[0].start_frame.value)
    ticks_per_frame = 24000 // 25        # transport master frames are 24000-tick (i2_drape_probe SCRUB, measured)
    target = a - LEAD * ticks_per_frame
    orig = bool(tr.get_editor_property("performance_mode"))
    json.dump({"performance_mode": orig}, open(HERE + "i2vt_state.json", "w"))
    pc = u.GameplayStatics.get_player_controller(w, 0)
    cm = u.GameplayStatics.get_player_camera_manager(w, 0)
    rows = []
    st = {"n": 0, "h": None, "done": False}

    def finish(ok, why=""):
        if st["done"]:
            return
        st["done"] = True
        try:
            root.sequence_player.pause()
        finally:
            if st["h"] is not None:
                u.unregister_slate_post_tick_callback(st["h"])
        p = HERE + "i2_entry_viewtarget_%s.json" % run
        json.dump({"run": run, "i2_start": a, "ticks_per_frame": ticks_per_frame, "rows": rows}, open(p, "w"), indent=0)
        changes = [r for i, r in enumerate(rows) if i == 0 or r["vt"] != rows[i - 1]["vt"]]
        if ok:
            u.log("I2VT_OK|run=%s|rows=%d|vt_changes=%s|pm=%s(restored)|file=%s" % (
                run, len(rows), json.dumps([(r["f"], r["vt"]) for r in changes]), orig, p))
        else:
            u.log_error("I2VT_FAILED|run=%s|%s|file=%s" % (run, why, p))

    def tick(dt):
        try:
            vt = pc.get_view_target() if pc else None
            cl = cm.get_camera_location()
            rows.append({"t": st["n"], "f": int(tr.get_current_master_frame().value), "vt": vt.get_actor_label() if vt else None,
                         "cam": [round(cl.x), round(cl.y), round(cl.z)]})
            st["n"] += 1
            if st["n"] >= TICKS:
                finish(True)
        except Exception as exc:  # noqa: BLE001
            finish(False, "%s: %s" % (type(exc).__name__, exc))

    try:
        tr.set_editor_property("performance_mode", False)
        res = tr.scrub_to_master_frame(u.FrameNumber(target))
        root.sequence_player.play()
    except Exception as exc:  # noqa: BLE001
        u.log_error("I2VT_FAILED|run=%s|start %s: %s" % (run, type(exc).__name__, exc))
        return
    finally:
        tr.set_editor_property("performance_mode", orig)      # as the other probes: only the scrub runs unlocked
    st["h"] = u.register_slate_post_tick_callback(tick)
    u.log("I2VT_STARTED|run=%s|scrub=%s|target=%d|i2_start=%d" % (run, res, target, a))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("I2VT_FAILED|%s: %s" % (type(exc).__name__, exc))
