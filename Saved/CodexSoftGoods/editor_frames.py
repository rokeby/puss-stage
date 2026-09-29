"""SPLIT TEST, EDITOR ONLY, PIE OFF (29 Sep): is the ~1 s stutter there with no show running? If yes, it is not the show.
Records N frame deltas of the editor's own tick through a self-unregistering Slate post-tick callback (floats only),
then logs PUSS_SOFTGOODS_FRAMES|{...} and writes cloth_gate_frames_<tag>.json (same format as the PIE benches).
Refuses while PIE runs. VALIDITY: if the mean is very slow (background throttle, non-realtime viewport), say so rather
than read a rhythm into it. Also logs the throttle cvar. Writes nothing to the world or any asset."""
import json
import os
import time

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")


def main():
    with open(os.path.join(HERE, "editor_frames_mode.json"), encoding="utf-8") as h:
        cfg = json.load(h)
    tag, count = cfg.get("tag", "editor"), int(cfg.get("frames", 450))
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None:
        unreal.log("PUSS_SOFTGOODS_EDITOR_FRAMES_STOPPED|PIE is running; this is the PIE-off split test")
        return
    throttle = unreal.SystemLibrary.get_console_variable_int_value("Slate.bAllowThrottling")
    # WALL-CLOCK deltas (time.perf_counter between callbacks). The Slate delta handed to the callback is CLAMPED at
    # 125 ms (1/8 s): every bench before 29 Sep 19:10Z read max_ms = 125.0 exactly, so spike magnitude was censored.
    state = {"t": [], "slate": [], "last": time.perf_counter(), "handle": None}

    def tick(delta):
        now = time.perf_counter()
        state["t"].append(now - state["last"])
        state["last"] = now
        state["slate"].append(float(delta))
        if len(state["t"]) < count:
            return
        unreal.unregister_slate_post_tick_callback(state["handle"])
        t = state["t"][1:]                                # the first delta spans the MCP call's own return
        ms = sorted(x * 1000 for x in t)
        clock, spikes = 0.0, []
        for x in t:
            clock += x
            if x * 1000 > 40:
                spikes.append(round(clock, 3))
        summary = {"tag": tag, "pie": False, "clock": "wall (perf_counter)", "slate_delta_max_ms": round(max(state["slate"]) * 1000, 2),
                   "slate_allow_throttling": throttle, "frames": len(t),
                   "seconds": round(sum(t), 2), "mean_ms": round(sum(ms) / len(ms), 2),
                   "median_ms": round(ms[len(ms) // 2], 2), "p95_ms": round(ms[int(len(ms) * 0.95)], 2),
                   "max_ms": round(ms[-1], 2), "over_40ms": len(spikes), "spike_times_s": spikes[:60],
                   "spike_gaps_s": [round(b - a, 3) for a, b in zip(spikes, spikes[1:])][:60]}
        with open(os.path.join(HERE, f"cloth_gate_frames_{tag}.json"), "w", encoding="utf-8") as h:
            json.dump(summary, h, indent=1)
        unreal.log("PUSS_SOFTGOODS_FRAMES|" + json.dumps(summary))

    state["handle"] = unreal.register_slate_post_tick_callback(tick)
    unreal.log(f"PUSS_SOFTGOODS_EDITOR_FRAMES|recording {count} frames, throttle={throttle}")


main()
