"""PIE, real time: what is on screen in Scene 1 after its last camera cut ends, in a PLAIN play-through? (30 Sep)

Scene 1 was lengthened to 210.8 s on 29 Sep. Its cut track still ends at frame 375 (15.0 s at 25 fps), after
which no cut covers the scene. Soft goods' PIE probe SCRUBBED into that stretch and saw the player controller
itself as the view target, at the origin (the dev grid). The transport's code claims nothing there and leaves
"the previous one" live (InfinityStageTransportController.cpp:726, :745). So something outside the transport put
the controller there, and a scrub is not how Gary walks the show. This asks the plain route: play from P01's
last 2 s through the boundary into Scene 1 (the tick claims Scene 1's Entry cut at the crossing, as in
performance), then keep playing past 15.0 s. It logs the view target and camera location EVERY tick and takes
two screenshots: Scene-local +10 s (inside the Entry cut, the reference) and +20 s (the question).

PRE-REGISTERED, before any run. At Scene-local +20 s the view target is:
  - the player controller or a pawn/spectator, camera near (0, 0, 0): continuous play shows the dev grid from
    about 15 s. CONFIRMED as a route to Gary's "empty dark box with a grid floor" that needs no scrub.
  - Scene 1's Exit Handoff camera (the last cut's camera): Sequencer KEEPS the last cut's view. Continuous play is
    safe; the dev grid needs a scrub or something else.
  - a camera bound inside LS_Animals_1 (a nested shot's own cut): the nested cuts take over; neither of the above.
  - P01's Passage rig: Sequencer restored to the transport's last claim; no dev grid.
The tick where the view target changes (expected at Scene-local 15.0 s, frame 375) is reported too. Screenshot
timing does not matter here: the question is identity, not frame timing.

SCENE 3 RUN (30 Sep, same harness; mode file {"mode": "run", "scene": "Scene 3", "end_s": 8, "shots": [2, 7],
"out": "scene3_cut_view"}). Scene 1's own cuts never took the view in play. Scene 3's root track has an interior cut,
ClamCam1 (root frames 81-1501 at 24 fps = 3.375-62.54 s), overlapping the Entry cut (0-95 = 0-3.958 s). The Master
plays LS_DevScene_03 1:1 from 468.255 s (probe_master_scene_sections.json). PRE-REGISTERED, before the run. Between
Scene-local +3.3 and +4.1 s the view target:
  - becomes ClamCam1: Sequencer's ROOT Scene cuts do drive the view in play. Scene 1's case has a local cause.
  - becomes a camera bound in LS_Clams (the nested shot): Sequencer cuts drive the view, nested outranking root.
  - stays the Entry camera through +8 s: Scene cuts do NOT drive the view in play. It generalises, and "cut into
    the scene's sequence" would never show authored scene cameras as things stand.
  - changes, but outside 3.3-4.1 s or to anything else: reported as found; the partition was incomplete.

CROSSING POP RUNS (30 Sep, same harness; {"mode": "run", "scene": "Scene 4", "end_s": 1, "shots": [],
"crossing_shots_s": 0.15, "out": "scene4_crossing_pop"}). The P01 -> Scene 1 play-through measured a camera pop at the
crossing: about 15 cm up and 9 cm forward, from the rig's bobbing height to the Entry camera's authored 150. Gary
said "no jumps". This is a PICTURE for him to judge, not a hypothesis. It screenshots EVERY tick within
crossing_shots_s either side of the Scene's first frame, and logs the camera rotation as well as the location
(rotation was not logged before, so a rotational pop is unmeasured). Screenshot stalls do not matter here; frame
identity does. Shots are listed in order with their Scene-relative time, so ScreenShotNNNNN files map by order.

One mode per MCP call, from scene1_tail_view_mode.json {"mode": "start" | "run" | "stop"}:
  start  request PIE (only in a slot the Conductor gave)
  run    in PIE: scrub to 2 s before Scene 1, then PlayForwardThroughBoundaries. A Slate post-tick callback logs
         per tick and finishes at Scene-local +21 s. Writes scene1_tail_view.json and logs
         PUSS_SCENE1_TAIL_VIEW|done|... The call returns at once; wait for the log line before the next call.
  stop   end PIE
Nothing is written to any asset or the level. Crash rules: everything inside main(); the callback keeps plain
data only and fetches the PIE world fresh every tick.
"""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexCameraPilot")
LEAD_S = 2.0
SHOTS_AT_S = (10.0, 20.0)
END_S = 21.0
MAX_TICKS = 3000


def main():
    with open(os.path.join(HERE, "scene1_tail_view_mode.json"), encoding="utf-8") as h:
        cfg = json.load(h)
    mode = cfg["mode"]
    scene_prefix = cfg.get("scene", "Scene 1")
    end_s = float(cfg.get("end_s", END_S))
    shots_at_s = [float(x) for x in cfg.get("shots", SHOTS_AT_S)]
    out_name = cfg.get("out", "scene1_tail_view")
    crossing_window_s = float(cfg.get("crossing_shots_s", 0.0))
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if mode == "start":
        if editor.get_game_world() is None:
            unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
        unreal.log("PUSS_SCENE1_TAIL_VIEW|start requested")
        return
    if mode == "stop":
        if editor.get_game_world() is not None:
            unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
        unreal.log("PUSS_SCENE1_TAIL_VIEW|stop requested")
        return

    world = editor.get_game_world()
    if world is None:
        unreal.log("PUSS_SCENE1_TAIL_VIEW|refused: PIE is not running")
        return
    roots = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot)
    transport = roots[0].get_editor_property("transport") if roots else None
    if transport is None:
        unreal.log("PUSS_SCENE1_TAIL_VIEW|refused: no transport")
        return
    segments = transport.get_editor_property("segments")
    scene1 = [i for i, s in enumerate(segments) if str(s.get_editor_property("label")).startswith(scene_prefix + " ")]
    if len(scene1) != 1 or scene1[0] == 0:
        unreal.log("PUSS_SCENE1_TAIL_VIEW|refused: expected one %s segment after another, found %s" % (scene_prefix, scene1))
        return
    index = scene1[0]
    start = segments[index].get_editor_property("start_frame").value
    end = segments[index].get_editor_property("end_frame").value
    previous_label = str(segments[index - 1].get_editor_property("label"))
    ticks_per_s = 24000.0                                   # Master tick resolution (24 kHz)
    scrub = transport.scrub_to_master_frame(unreal.FrameNumber(int(start - LEAD_S * ticks_per_s)))
    play = transport.play_forward_through_boundaries()
    state = {"rows": [], "shots": [], "crossing_shots": [], "handle": None}
    pending_shots = list(shots_at_s)

    def finish(note):
        unreal.unregister_slate_post_tick_callback(state["handle"])
        rows = state["rows"]
        changes = [r for i, r in enumerate(rows) if i == 0 or r["view_target"] != rows[i - 1]["view_target"]]
        at_20 = next((r for r in rows if r["scene_s"] is not None and r["scene_s"] >= 20.0), None)
        out = {"scene": scene_prefix, "scene_segment": index, "previous_segment": previous_label, "start_frame": start, "end_frame": end,
               "scrub": str(scrub), "play": str(play), "shots_at_scene_s": state["shots"],
               "crossing_shots_in_order": state["crossing_shots"],
               "view_target_changes": changes, "at_20s": at_20, "rows": rows, "note": note}
        with open(os.path.join(HERE, out_name + ".json"), "w", encoding="utf-8") as h:
            json.dump(out, h, indent=1)
        unreal.log("PUSS_SCENE1_TAIL_VIEW|done|%s|%s|at_20s=%s|changes=%s|shots=%s" % (
            scene_prefix, note,
            (at_20["view_target"], at_20["camera_xyz"]) if at_20 else None,
            [(c["scene_s"], c["view_target"]) for c in changes],
            state["shots"]))

    def tick(delta):
        w = editor.get_game_world()                          # fetched fresh: never touch a PIE world that has ended
        if w is None:
            return finish("PIE ended early")
        roots_now = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.InfinityStageShowRoot)
        tr = roots_now[0].get_editor_property("transport") if roots_now else None
        if tr is None:
            return finish("transport gone")
        frame = tr.get_current_master_frame().value
        scene_s = round((frame - start) / ticks_per_s, 3) if frame >= start else None
        relative_s = round((frame - start) / ticks_per_s, 3)
        pc = unreal.GameplayStatics.get_player_controller(w, 0)
        vt = pc.get_view_target() if pc else None
        pcm = pc.get_editor_property("player_camera_manager") if pc else None
        cam = pcm.get_camera_location() if pcm else None
        rot = pcm.get_camera_rotation() if pcm else None
        state["rows"].append({
            "tick": len(state["rows"]), "dt_ms": round(delta * 1000, 2), "master": frame, "scene_s": scene_s,
            "segment": tr.get_editor_property("selected_segment_index"),
            "view_target": "%s (%s) '%s'" % (vt.get_name(), vt.get_class().get_name(), vt.get_actor_label())
            if vt else None,
            "camera_xyz": [round(cam.x), round(cam.y), round(cam.z)] if cam else None,
            "camera_xyz_precise": [round(cam.x, 2), round(cam.y, 2), round(cam.z, 2)] if cam else None,
            "camera_pyr": [round(rot.pitch, 3), round(rot.yaw, 3), round(rot.roll, 3)] if rot else None,
            "relative_s": relative_s})
        if crossing_window_s > 0.0 and abs(relative_s) <= crossing_window_s:
            unreal.SystemLibrary.execute_console_command(w, "shot")
            state["crossing_shots"].append({"tick": len(state["rows"]) - 1, "relative_s": relative_s})
        if scene_s is not None and pending_shots and scene_s >= pending_shots[0]:
            unreal.SystemLibrary.execute_console_command(w, "shot")
            state["shots"].append(scene_s)
            pending_shots.pop(0)
        if scene_s is not None and scene_s >= end_s:
            return finish("ok")
        if len(state["rows"]) > MAX_TICKS:
            return finish("did not reach Scene-local %.0f s within %d ticks" % (end_s, MAX_TICKS))

    state["handle"] = unreal.register_slate_post_tick_callback(tick)
    unreal.log("PUSS_SCENE1_TAIL_VIEW|armed|%s|segment=%d|previous='%s'|start=%d (%.3f s)|scrub=%s|play=%s"
               % (scene_prefix, index, previous_label, start, start / ticks_per_s, scrub, play))


main()
