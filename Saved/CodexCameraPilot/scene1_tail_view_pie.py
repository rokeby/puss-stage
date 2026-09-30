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
        mode = json.load(h)["mode"]
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
    scene1 = [i for i, s in enumerate(segments) if str(s.get_editor_property("label")).startswith("Scene 1")]
    if len(scene1) != 1 or scene1[0] == 0:
        unreal.log("PUSS_SCENE1_TAIL_VIEW|refused: expected one Scene 1 segment after another, found %s" % scene1)
        return
    index = scene1[0]
    start = segments[index].get_editor_property("start_frame").value
    end = segments[index].get_editor_property("end_frame").value
    previous_label = str(segments[index - 1].get_editor_property("label"))
    ticks_per_s = 24000.0                                   # Master tick resolution (24 kHz)
    scrub = transport.scrub_to_master_frame(unreal.FrameNumber(int(start - LEAD_S * ticks_per_s)))
    play = transport.play_forward_through_boundaries()
    state = {"rows": [], "shots": [], "handle": None}
    pending_shots = list(SHOTS_AT_S)

    def finish(note):
        unreal.unregister_slate_post_tick_callback(state["handle"])
        rows = state["rows"]
        changes = [r for i, r in enumerate(rows) if i == 0 or r["view_target"] != rows[i - 1]["view_target"]]
        at_20 = next((r for r in rows if r["scene_s"] is not None and r["scene_s"] >= 20.0), None)
        out = {"scene_segment": index, "previous_segment": previous_label, "start_frame": start, "end_frame": end,
               "scrub": str(scrub), "play": str(play), "shots_at_scene_s": state["shots"],
               "view_target_changes": changes, "at_20s": at_20, "rows": rows, "note": note}
        with open(os.path.join(HERE, "scene1_tail_view.json"), "w", encoding="utf-8") as h:
            json.dump(out, h, indent=1)
        unreal.log("PUSS_SCENE1_TAIL_VIEW|done|%s|at_20s=%s|changes=%s|shots=%s" % (
            note,
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
        pc = unreal.GameplayStatics.get_player_controller(w, 0)
        vt = pc.get_view_target() if pc else None
        pcm = pc.get_editor_property("player_camera_manager") if pc else None
        cam = pcm.get_camera_location() if pcm else None
        state["rows"].append({
            "tick": len(state["rows"]), "dt_ms": round(delta * 1000, 2), "master": frame, "scene_s": scene_s,
            "segment": tr.get_editor_property("selected_segment_index"),
            "view_target": "%s (%s) '%s'" % (vt.get_name(), vt.get_class().get_name(), vt.get_actor_label())
            if vt else None,
            "camera_xyz": [round(cam.x), round(cam.y), round(cam.z)] if cam else None})
        if scene_s is not None and pending_shots and scene_s >= pending_shots[0]:
            unreal.SystemLibrary.execute_console_command(w, "shot")
            state["shots"].append(scene_s)
            pending_shots.pop(0)
        if scene_s is not None and scene_s >= END_S:
            return finish("ok")
        if len(state["rows"]) > MAX_TICKS:
            return finish("did not reach Scene-local %.0f s within %d ticks" % (END_S, MAX_TICKS))

    state["handle"] = unreal.register_slate_post_tick_callback(tick)
    unreal.log("PUSS_SCENE1_TAIL_VIEW|armed|scene1_segment=%d|previous='%s'|start=%d|scrub=%s|play=%s"
               % (index, previous_label, start, scrub, play))


main()
