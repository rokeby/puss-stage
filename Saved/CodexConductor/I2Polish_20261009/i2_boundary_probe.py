"""P39 PIE-only, read-only frame-step camera probe for every Scene->Interaction seam.

The probe changes only the live PIE transport playhead.  It records the original
frame/performance/play state, pauses, scrubs one display frame at a time, samples
the player view target on the following Slate tick, then restores the original
frame and performance mode.  It never saves or ends PIE.
"""

import datetime
import json
import os


HERE = os.path.dirname(os.path.abspath(__file__))
PAD = int(globals().get("I2_BOUNDARY_PAD", 2))


def main():
    import unreal as u
    run = "I2BOUNDARY-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    lib = u.EditorLoadingAndSavingUtils

    def census():
        return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
                "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}

    c0 = census()
    if c0 != {"content": [], "maps": []}:
        u.log_error("I2_BOUNDARY_PROBE_FAILED|run=%s|DIRTY_AT_START|%s" % (run, json.dumps(c0)))
        return
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    if world is None:
        u.log_error("I2_BOUNDARY_PROBE_FAILED|run=%s|PIE_REQUIRED" % run)
        return
    roots = list(u.GameplayStatics.get_all_actors_of_class(world, u.InfinityStageShowRoot))
    if len(roots) != 1:
        u.log_error("I2_BOUNDARY_PROBE_FAILED|run=%s|SHOW_ROOT_COUNT=%d" % (run, len(roots)))
        return
    root = roots[0]
    transport = root.transport
    segments = list(transport.segments)
    seams = []
    for index in range(len(segments) - 1):
        left, right = segments[index], segments[index + 1]
        ll, rl = str(left.label), str(right.label)
        if ll.startswith("Scene ") and rl.startswith("Interaction "):
            boundary_ticks = int(right.start_frame.value)
            seams.append({"left": ll, "right": rl, "boundary_ticks": boundary_ticks})
    if not seams:
        u.log_error("I2_BOUNDARY_PROBE_FAILED|run=%s|NO_SCENE_INTERACTION_SEAMS" % run)
        return
    tick_rate = 24000
    display_rate = 25
    ticks_per_frame = tick_rate // display_rate
    original_frame = int(transport.get_current_master_frame().value)
    original_pm = bool(transport.get_editor_property("performance_mode"))
    player = root.sequence_player
    try:
        original_playing = bool(player.is_playing())
    except Exception:
        original_playing = False
    pc = u.GameplayStatics.get_player_controller(world, 0)
    manager = u.GameplayStatics.get_player_camera_manager(world, 0)
    queue = []
    for seam_index, seam in enumerate(seams):
        boundary_display = int(round(seam["boundary_ticks"] / float(ticks_per_frame)))
        seam["boundary_display_frame"] = boundary_display
        for offset in range(-PAD, PAD + 1):
            queue.append({"seam_index": seam_index, "offset": offset,
                          "display_frame": boundary_display + offset,
                          "master_ticks": (boundary_display + offset) * ticks_per_frame})
    state = {"index": 0, "handle": None, "done": False}
    rows = []

    def finish(ok, why=""):
        if state["done"]:
            return
        state["done"] = True
        try:
            player.pause()
            transport.set_editor_property("performance_mode", False)
            transport.scrub_to_master_frame(u.FrameNumber(original_frame))
            transport.set_editor_property("performance_mode", original_pm)
            if original_playing:
                player.play()
        finally:
            if state["handle"] is not None:
                u.unregister_slate_post_tick_callback(state["handle"])
        c1 = census()
        out = {"run": run, "pad": PAD, "ticks_per_frame": ticks_per_frame, "seams": seams,
               "rows": rows, "restored": {"frame": original_frame, "performance_mode": original_pm,
                                             "was_playing": original_playing},
               "census_before": c0, "census_after": c1, "census_unchanged": c0 == c1}
        path = os.path.join(HERE, "i2_boundary_probe_%s.json" % run)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(out, handle, indent=1, sort_keys=True)
            handle.write("\n")
        changes = []
        for seam_index, seam in enumerate(seams):
            subset = [r for r in rows if r["seam_index"] == seam_index]
            for idx, row in enumerate(subset):
                if idx == 0 or row["view_target"] != subset[idx - 1]["view_target"]:
                    changes.append([seam["left"], seam["right"], row["offset"], row["view_target"]])
        if ok and c0 == c1:
            u.log("I2_BOUNDARY_PROBE_OK|run=%s|seams=%d|rows=%d|changes=%s|restored=1|dirty=0|file=%s" % (
                run, len(seams), len(rows), json.dumps(changes), path))
        else:
            u.log_error("I2_BOUNDARY_PROBE_FAILED|run=%s|why=%s|census_unchanged=%d|file=%s" % (
                run, why, int(c0 == c1), path))

    def issue_next():
        if state["index"] >= len(queue):
            finish(True)
            return
        item = queue[state["index"]]
        transport.scrub_to_master_frame(u.FrameNumber(int(item["master_ticks"])))

    def tick(_delta):
        try:
            item = queue[state["index"]]
            vt = pc.get_view_target() if pc else None
            loc = manager.get_camera_location() if manager else None
            rows.append({"seam_index": item["seam_index"], "offset": item["offset"],
                         "display_frame": item["display_frame"], "master_ticks": item["master_ticks"],
                         "transport_ticks": int(transport.get_current_master_frame().value),
                         "view_target": vt.get_actor_label() if vt else None,
                         "camera_cm": None if loc is None else [float(loc.x), float(loc.y), float(loc.z)]})
            state["index"] += 1
            issue_next()
        except Exception as exc:
            finish(False, "%s: %s" % (type(exc).__name__, exc))

    try:
        player.pause()
        transport.set_editor_property("performance_mode", False)
        issue_next()
        state["handle"] = u.register_slate_post_tick_callback(tick)
        u.log("I2_BOUNDARY_PROBE_STARTED|run=%s|seams=%d|frames_per_seam=%d" % (run, len(seams), PAD * 2 + 1))
    except Exception as exc:
        finish(False, "START %s: %s" % (type(exc).__name__, exc))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("I2_BOUNDARY_PROBE_FAILED|%s: %s" % (type(exc).__name__, exc))

