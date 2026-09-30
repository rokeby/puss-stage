"""STUTTER TEST (30 Sep; Gary: "fix the stutter by that test"), fresh editor, PIE off, camera parked. ONE MCP call arms a
Slate post-tick state machine that runs four 60 s phases with no further MCP traffic (every MCP call is itself a 40-80 ms
hitch), then writes stutter_abab_<run>.json and logs STUTTER_ABAB|done|run=<id>. Wait for THAT file; do not poll the editor.

The hypothesis under test: the celestial rig's ApplyCyclePhase (unconditional writes to sun rotation, sun/moon/sky/fog)
causes the ~1 Hz cluster rhythm. Declaration-proven call paths in the editor (read 30 Sep): the rig never ticks
(InfinityStageCelestialRig.cpp:49 bCanEverTick = false); per-frame it is reached ONLY from the Master's Passage track while
Sequencer evaluates (MovieSceneInfinityPassageTrack.cpp:187); the Cue Desk's timer is one-shot (SInfinityStageCueDesk.cpp
:1531-1543). So:
  P = the Master PLAYING inside its longest Passage section (camera-cut lock OFF, so the viewport stays parked):
      the celestial path runs every frame (together with everything else the Master evaluates)
  X = Sequencer CLOSED: no per-frame celestial call exists at all
Order P1 X1 P2 X2 (A/B/A/B). Each phase: 5 s settle after the switch (excluded), then 60 s recorded.
Frames: WALL-CLOCK deltas (Slate's delta is clamped at 125 ms). Spike = frame > 40 ms. CLUSTER START = a spike more than
0.3 s after the previous spike. Decisive for "the rhythm lives in Master evaluation": X has >= 90% fewer cluster starts
than the P before it, TWICE, and P2 restores them. Clusters in X at ~1 Hz instead REFUTE the celestial hypothesis for the
idle rhythm, by construction (no call path there). Even a decisive P/X split implicates Sequencer evaluation as a whole,
not the celestial rig alone; isolating it needs patch C (held).
Guards: no PIE, Sequencer closed at start. Restores the camera-cut lock setting and closes Sequencer at the end. Writes
nothing to the world or any asset. Everything inside main(); the callback keeps plain data only."""
import datetime
import json
import os
import statistics
import time

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
PHASES = ("P1", "X1", "P2", "X2")
MEASURE_S, SETTLE_S, SPIKE_MS, CLUSTER_GAP_S, LEAD_IN_S = 60.0, 5.0, 40.0, 0.3, 10.0


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    lib = unreal.LevelSequenceEditorBlueprintLibrary
    if ed.get_game_world() is not None or lib.get_current_level_sequence():
        unreal.log_error(f"STUTTER_ABAB|refused|run={run}|PIE running or Sequencer open")
        return
    world = ed.get_editor_world()
    everyone = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
    census = {"capture_actors": [a.get_actor_label() for a in everyone if a.get_components_by_class(unreal.SceneCaptureComponent2D)],
              "temp_actors": [a.get_actor_label() for a in everyone if a.get_actor_label().startswith(("ZZ_", "TEMP_"))],
              "slate_allow_throttling": unreal.SystemLibrary.get_console_variable_int_value("Slate.bAllowThrottling"),
              "dirty": [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
              + [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]}
    del everyone
    master = unreal.load_asset(MASTER)
    rate = master.get_display_rate()
    fps = rate.numerator / float(rate.denominator)
    best = None
    for track in master.get_tracks():
        if track.get_class().get_name() != "MovieSceneInfinityPassageTrack":
            continue
        for s in track.get_sections():
            a, b = s.get_start_frame_seconds(), s.get_end_frame_seconds()
            if best is None or b - a > best[1] - best[0]:
                best = (a, b)
    del master
    if best is None or best[1] - best[0] < LEAD_IN_S + MEASURE_S + SETTLE_S + 2.0:
        unreal.log_error(f"STUTTER_ABAB|refused|run={run}|no Passage section long enough: {best}")
        return
    start_frame = int(round((best[0] + LEAD_IN_S) * fps))
    lock_before = bool(lib.is_camera_cut_locked_to_viewport())
    st = {"phase": -1, "t0": 0.0, "last": time.perf_counter(), "rows": {p: [] for p in PHASES}, "handle": None, "notes": []}

    def begin(i):
        st["phase"], st["t0"] = i, time.perf_counter()
        name = PHASES[i]
        if name.startswith("P"):
            lib.open_level_sequence(unreal.load_asset(MASTER))
            lib.set_lock_camera_cut_to_viewport(False)
            lib.set_current_time(start_frame)
            lib.play()
            st["notes"].append(f"{name}: open+play from display frame {start_frame}")
        else:
            if lib.get_current_level_sequence():
                lib.pause()
                lib.close_level_sequence()
            st["notes"].append(f"{name}: sequencer closed={lib.get_current_level_sequence() is None}")

    def stats(rows):
        if not rows:
            return {"frames": 0}
        ms = [dt * 1000.0 for _, dt in rows]
        spikes = [t for t, dt in rows if dt * 1000.0 > SPIKE_MS]
        starts = [t for k, t in enumerate(spikes) if k == 0 or t - spikes[k - 1] > CLUSTER_GAP_S]
        gaps = [round(b - a, 3) for a, b in zip(starts, starts[1:])]
        srt = sorted(ms)
        return {"frames": len(ms), "seconds": round(sum(dt for _, dt in rows), 2), "mean_ms": round(statistics.mean(ms), 2),
                "median_ms": round(statistics.median(ms), 2), "p95_ms": round(srt[int(0.95 * (len(srt) - 1))], 2), "max_ms": round(srt[-1], 1),
                "spikes": len(spikes), "cluster_starts": len(starts), "cluster_starts_per_min": round(60.0 * len(starts) / max(1.0, sum(dt for _, dt in rows)), 1),
                "median_gap_s": statistics.median(gaps) if gaps else None, "cluster_start_times_s": [round(t, 2) for t in starts]}

    def finish(why):
        unreal.unregister_slate_post_tick_callback(st["handle"])
        if lib.get_current_level_sequence():
            lib.pause()
            lib.close_level_sequence()
        lib.set_lock_camera_cut_to_viewport(lock_before)
        res = {p: stats(st["rows"][p]) for p in PHASES}
        c = {p: res[p].get("cluster_starts", 0) for p in PHASES}
        red1 = 1.0 - c["X1"] / c["P1"] if c["P1"] else None
        red2 = 1.0 - c["X2"] / c["P2"] if c["P2"] else None
        verdict = {"reduction_X1_vs_P1": round(red1, 3) if red1 is not None else None, "reduction_X2_vs_P2": round(red2, 3) if red2 is not None else None,
                   "restored_P2_vs_P1": round(c["P2"] / c["P1"], 2) if c["P1"] else None,
                   "decisive_master_evaluation": bool(red1 is not None and red2 is not None and red1 >= 0.9 and red2 >= 0.9 and c["P1"] and c["P2"] >= 0.5 * c["P1"]),
                   "idle_clusters_per_min": [res["X1"].get("cluster_starts_per_min"), res["X2"].get("cluster_starts_per_min")]}
        out = {"run": run, "why": why, "passage_section_s": [round(best[0], 2), round(best[1], 2)], "fps": fps, "start_frame": start_frame,
               "census": census, "camera_lock_before": lock_before, "notes": st["notes"], "phases": res, "verdict": verdict,
               "definitions": {"spike_ms": SPIKE_MS, "cluster_gap_s": CLUSTER_GAP_S, "settle_s": SETTLE_S, "measure_s": MEASURE_S}}
        with open(os.path.join(HERE, f"stutter_abab_{run}.json"), "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        unreal.log(f"STUTTER_ABAB|done|run={run}|{why}|clusters={c}|verdict={json.dumps(verdict)}")

    def tick(_delta):
        now = time.perf_counter()
        dt, st["last"] = now - st["last"], now
        if ed.get_game_world() is not None:
            return finish("PIE started mid-test: INVALID")
        if st["phase"] < 0:
            return begin(0)
        el = now - st["t0"]
        if el > SETTLE_S:
            st["rows"][PHASES[st["phase"]]].append((el - SETTLE_S, dt))
        if el >= SETTLE_S + MEASURE_S:
            if st["phase"] + 1 < len(PHASES):
                begin(st["phase"] + 1)
            else:
                finish("ok")

    st["handle"] = unreal.register_slate_post_tick_callback(tick)
    unreal.log(f"STUTTER_ABAB|armed|run={run}|section={best}|fps={fps}|start_frame={start_frame}|census={json.dumps(census)}")


main()
