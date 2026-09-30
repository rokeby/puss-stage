"""PIE, real time: how many frames after a transition's first frame is its drape DRAWN? (30 Sep, the frame-count test.)

The hypothesis: the five transition drapes are SPAWNABLES. They do not exist until their Interaction's first frame, and a
freshly spawned Geometry Cache decodes its first frame asynchronously, so for a few frames nothing is drawn and the
Passage behind shows first ("misloaded wings followed by cloth", Gary's run-through).

PRE-REGISTERED, before any run:
  - The drape is drawn by the Interaction's first frame (tick 0 or 1): NO FAULT, and fix (a) is not needed for this reason.
  - The drape is drawn later than tick 2: CONFIRMED.
  - DENSITY CHECK (the Conductor): the run is repeated with DENSE screenshots (ticks 0-8 every tick) and SPARSE ones
    (ticks 0, 4, 8). If the first-drawn tick differs between them, the screenshot stalls the frames and the instrument
    is in the answer: report that, not a count.

One mode per MCP call, from drape_first_frame_mode.json {"mode": ..., "density": "dense"|"sparse", "interaction": 1}:
  start   request PIE (Gary is away; the Conductor scheduled the editor for this)
  run     in PIE: scrub to 1.5 s BEFORE Interaction N's first frame, then PlayForwardThroughBoundaries, so the show
          crosses the boundary at real time as in performance. A Slate post-tick callback then logs per tick (cheap):
          master frame, segment, whether a GeometryCacheActor exists at the mouth, and its visibility. It issues
          `shot` only at the density's ticks after the first frame inside the Interaction. It writes
          drape_first_frame_<density>.json and logs PUSS_SOFTGOODS_DRAPE_FIRST_FRAME|... when done. The call returns at
          once; wait for the log line before calling again (every MCP call is itself a hitch).
  stop    end PIE
Offline, Scripts/analyse_drape_first_frame.py reads the screenshots (Saved/Screenshots/WindowsEditor/) and finds the
first tick at which the drape's red fills the frame centre. Crash rules: all inside main(); nothing kept at module level.
"""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")
MOUTHS = {1: (0.0, 80000.0), 2: (0.0, 160000.0), 3: (0.0, 240000.0), 4: (0.0, 320000.0), 5: (0.0, 400000.0)}
DENSITY = {"dense": list(range(0, 9)) + [20], "sparse": [0, 4, 8, 20],   # tick 20 = the "surely drawn" reference
           "boundary": [0, 1, 2, 3]}                                          # Look & camera's tick-1 view-target check
TICKS_AFTER = 20


def main():
    with open(os.path.join(HERE, "drape_first_frame_mode.json"), encoding="utf-8") as h:
        cfg = json.load(h)
    mode, density, n = cfg["mode"], cfg.get("density", "dense"), int(cfg.get("interaction", 1))
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if mode == "start":
        if editor.get_game_world() is None:
            unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
        unreal.log("PUSS_SOFTGOODS_DRAPE_FIRST_FRAME|start requested")
        return
    if mode == "stop":
        if editor.get_game_world() is not None:
            unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
        unreal.log("PUSS_SOFTGOODS_DRAPE_FIRST_FRAME|stop requested")
        return
    world = editor.get_game_world()
    if world is None:
        unreal.log("PUSS_SOFTGOODS_DRAPE_FIRST_FRAME|refused: PIE is not running")
        return
    roots = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot)
    transport = roots[0].get_editor_property("transport") if roots else None
    if transport is None:
        unreal.log("PUSS_SOFTGOODS_DRAPE_FIRST_FRAME|refused: no transport")
        return
    segs = transport.get_editor_property("segments")
    idx = [i for i, s in enumerate(segs) if "Interaction" in str(s.get_editor_property("label"))]
    if len(idx) < n:
        unreal.log(f"PUSS_SOFTGOODS_DRAPE_FIRST_FRAME|refused: found {len(idx)} Interaction segments")
        return
    seg_index = idx[n - 1]
    start = segs[seg_index].get_editor_property("start_frame").value
    lead = int(round(1.5 * 24000))                       # 1.5 s before, in 24 kHz ticks
    scrub = transport.scrub_to_master_frame(unreal.FrameNumber(start - lead))
    play = transport.play_forward_through_boundaries()
    mx, my = MOUTHS[n]
    # Look & camera's discriminator (30 Sep): which actor the view is on, and where the camera is, every tick. If tick 1
    # names a pawn or spectator (not a camera) at the x = 0 dev grid, Sequencer restored its pre-animated view target
    # when Scene 1's cut ended. The transport's INFINITY_VIEW_TARGET line is Verbose only, so raise that category.
    unreal.SystemLibrary.execute_console_command(world, "log LogInfinityStageTransport Verbose")
    shots = set(DENSITY[density])
    state = {"rows": [], "t0": None, "handle": None, "shots": []}

    def drape_state(w):
        best = None
        for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.GeometryCacheActor):
            loc = a.get_actor_location()
            d = ((loc.x - mx) ** 2 + (loc.y - my) ** 2) ** 0.5
            if d < 500.0 and (best is None or d < best[0]):
                comp = a.get_editor_property("geometry_cache_component")
                try:
                    t = round(float(comp.get_animation_time()), 4)
                except Exception:  # noqa: BLE001
                    t = None
                best = (d, bool(comp.is_visible()), t)
        return best

    def finish(note):
        unreal.unregister_slate_post_tick_callback(state["handle"])
        out = {"density": density, "interaction": n, "segment_index": seg_index, "start_frame": start,
               "scrub": str(scrub), "play": str(play), "shots_at_k": state["shots"], "rows": state["rows"], "note": note}
        with open(os.path.join(HERE, f"drape_first_frame_{density}.json"), "w", encoding="utf-8") as h:
            json.dump(out, h, indent=1)
        first_exists = next((r["k"] for r in state["rows"] if r["k"] is not None and r["drape_exists"]), None)
        unreal.log(f"PUSS_SOFTGOODS_DRAPE_FIRST_FRAME|done|{note}|density={density}|first_k_actor_exists={first_exists}"
                   f"|shots={state['shots']}")

    def tick(delta):
        w = editor.get_game_world()                       # fetched fresh: never touch a PIE world that has ended
        if w is None:
            return finish("PIE ended early")
        roots_now = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.InfinityStageShowRoot)
        tr = roots_now[0].get_editor_property("transport") if roots_now else None
        if tr is None:
            return finish("transport gone")
        frame = tr.get_current_master_frame().value
        inside = frame >= start
        if inside and state["t0"] is None:
            state["t0"] = len(state["rows"])
        k = None if state["t0"] is None else len(state["rows"]) - state["t0"]
        ds = drape_state(w)
        pc = unreal.GameplayStatics.get_player_controller(w, 0)
        vt = pc.get_view_target() if pc else None
        pcm = pc.get_editor_property("player_camera_manager") if pc else None
        cam = pcm.get_camera_location() if pcm else None
        try:
            blend = float(pcm.get_editor_property("blend_time_to_go")) if pcm else None
        except Exception:  # noqa: BLE001
            blend = "n/a"
        state["rows"].append({"tick": len(state["rows"]), "k": k, "dt_ms": round(delta * 1000, 2), "master": frame,
                              "segment": tr.get_editor_property("selected_segment_index"),
                              "drape_exists": ds is not None, "drape_visible": ds[1] if ds else None,
                              "drape_anim_time": ds[2] if ds else None,
                              "view_target": f"{vt.get_name()} ({vt.get_class().get_name()})" if vt else None,
                              "camera_xyz": [round(cam.x), round(cam.y), round(cam.z)] if cam else None,
                              "blend_time_to_go": blend})
        if k is not None and k in shots:
            unreal.SystemLibrary.execute_console_command(w, "shot")
            state["shots"].append(k)
        if k is not None and k >= TICKS_AFTER:
            return finish("ok")
        if len(state["rows"]) > 600:                      # never reached the Interaction: stop rather than run forever
            return finish("never crossed into the Interaction within 600 ticks")

    state["handle"] = unreal.register_slate_post_tick_callback(tick)
    unreal.log(f"PUSS_SOFTGOODS_DRAPE_FIRST_FRAME|armed|density={density}|segment={seg_index}|start={start}"
               f"|scrub={scrub}|play={play}")


main()
