"""PIE-only probe (no saves): for each Scene 3 offset (seconds) scrub the Master, pause, wait SETTLE ticks, log the player
camera location/rotation/FOV and view-target label.  Args pie_cam_probe_args.json {"segment": "Scene 3", "offsets": [..]}.
CAMPROBE_ROW|run=..|t=..|... then CAMPROBE_OK|run=.. / CAMPROBE_FAILED."""
import datetime, json, os
SETTLE = 20


def main():
    import unreal as u
    a = json.load(open("E:/PussStage/Saved/CodexConductor/pie_cam_probe_args.json"))
    run = "CAMPROBE-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    if w is None:
        u.log_error("CAMPROBE_FAILED|run=%s|no PIE" % run); return
    root = list(u.GameplayStatics.get_all_actors_of_class(w, u.InfinityStageShowRoot))[0]
    tr, player = root.transport, root.sequence_player
    seg = [s for s in list(tr.segments) if str(s.label).startswith(a.get("segment", "Scene 3"))][0]
    tps = 24000
    pcm = u.GameplayStatics.get_player_camera_manager(w, 0)
    queue = list(a["offsets"])
    st = {"i": 0, "wait": -1, "done": False, "h": None}

    def tick(_dt):
        try:
            if st["done"]: return
            if st["i"] >= len(queue):
                st["done"] = True; u.unregister_slate_post_tick_callback(st["h"]); u.log("CAMPROBE_OK|run=%s|n=%d" % (run, len(queue))); return
            t = queue[st["i"]]
            if st["wait"] < 0:
                player.pause(); tr.scrub_to_master_frame(u.FrameNumber(int(seg.start_frame.value + t * tps))); st["wait"] = SETTLE
            elif st["wait"] == 0:
                l, r = pcm.get_camera_location(), pcm.get_camera_rotation()
                vt = u.GameplayStatics.get_player_controller(w, 0).get_view_target()
                u.log("CAMPROBE_ROW|run=%s|t=%.2f|loc=%.0f,%.0f,%.0f|rot=p%.1f,y%.1f|fov=%.1f|vt=%s" % (
                    run, t, l.x, l.y, l.z, r.pitch, r.yaw, pcm.get_fov_angle(), vt.get_actor_label() if vt else None))
                st["i"] += 1; st["wait"] = -1
            else:
                st["wait"] -= 1
        except Exception as exc:  # noqa: BLE001
            st["done"] = True; u.unregister_slate_post_tick_callback(st["h"]); u.log_error("CAMPROBE_FAILED|run=%s|%r" % (run, exc))

    st["h"] = u.register_slate_post_tick_callback(tick)
    u.log("CAMPROBE_ARMED|run=%s|n=%d" % (run, len(queue)))


main()
