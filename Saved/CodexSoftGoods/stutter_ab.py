"""PIE-ONLY stutter A/B (29 Sep), Rig's toggle list. The first bench showed ~1-1.5 s periodic hitches owned by
"Render Lights and Shadows" across P01's 338 shadow casters. Which periodic thing drives it: wing/gust motion (b) or
the 432 flicker light functions (a), and is it VSM cache invalidation?

NEVER starts PIE; touches no asset; every change is PIE-time and transient, and `restore` puts it all back.
One mode per MCP call, from stutter_ab_mode.json ({"mode": ..., "tag": ..., ...}):
  status    transport playing?, current Master frame, and the cvars below: RUN FIRST (if the transport was PAUSED
            during the first bench, the wings were already frozen while the spikes persisted)
  pause     Transport.PauseTransport()   (freezes wing mechanism + gusts, which integrate from the Master frame)
  resume    Transport.ResumeForward()
  cmd       run ONE whitelisted console command from cfg["cmd"]; the first time a cvar is changed its original value
            is stored in stutter_ab_restore.json
  frames    record cfg["frames"] (default 300) frame deltas; logs PUSS_SOFTGOODS_FRAMES|{...} (same format as the
            cloth bench) and writes cloth_gate_frames_<tag>.json
  restore   ShowFlags back to default (2), cvars back to their stored originals, transport back to its state at the
            first `status`
Crash rules: all inside functions; the frame recorder holds floats only and unregisters itself.
"""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")
RESTORE = os.path.join(HERE, "stutter_ab_restore.json")
CVARS = ("r.Shadow.Virtual.Cache", "r.Shadow.Virtual.OnePassProjection.MaxLightsPerPixel")
SHOWFLAGS = ("ShowFlag.LightFunctions", "ShowFlag.DynamicShadows")


def allowed(cmd):
    parts = cmd.split()
    return len(parts) == 2 and parts[0] in CVARS + SHOWFLAGS and parts[1].lstrip("-").isdigit()


def load_restore():
    try:
        with open(RESTORE, encoding="utf-8") as h:
            return json.load(h)
    except (OSError, ValueError):
        return {}


def save_restore(state):
    with open(RESTORE, "w", encoding="utf-8") as h:
        json.dump(state, h, indent=1)


def transport(world):
    roots = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot)
    return roots[0].get_editor_property("transport") if roots else None


def record_frames(tag, count):
    state = {"t": [], "handle": None}

    def tick(delta):
        state["t"].append(float(delta))
        if len(state["t"]) < count:
            return
        unreal.unregister_slate_post_tick_callback(state["handle"])
        t = state["t"]
        ms = sorted(x * 1000 for x in t)
        clock, spikes = 0.0, []
        for x in t:
            clock += x
            if x * 1000 > 40:
                spikes.append(round(clock, 3))
        summary = {"tag": tag, "frames": len(t), "seconds": round(sum(t), 2), "mean_ms": round(sum(ms) / len(ms), 2),
                   "median_ms": round(ms[len(ms) // 2], 2), "p95_ms": round(ms[int(len(ms) * 0.95)], 2),
                   "max_ms": round(ms[-1], 2), "over_40ms": len(spikes), "spike_times_s": spikes[:40],
                   "spike_gaps_s": [round(b - a, 3) for a, b in zip(spikes, spikes[1:])][:40]}
        with open(os.path.join(HERE, f"cloth_gate_frames_{tag or 'untagged'}.json"), "w", encoding="utf-8") as h:
            json.dump(summary, h, indent=1)
        unreal.log("PUSS_SOFTGOODS_FRAMES|" + json.dumps(summary))

    state["handle"] = unreal.register_slate_post_tick_callback(tick)


def main():
    with open(os.path.join(HERE, "stutter_ab_mode.json"), encoding="utf-8") as h:
        cfg = json.load(h)
    mode, tag = cfg.get("mode", "status"), cfg.get("tag", "")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world is None:
        unreal.log("PUSS_SOFTGOODS_STUTTER_AB_STOPPED|no PIE world; this script never starts PIE")
        return
    tr = transport(world)
    report = {"mode": mode, "tag": tag}
    restore = load_restore()
    if mode == "status":
        playing = bool(tr.is_transport_playing()) if tr else None
        report.update({"playing": playing, "frame": tr.get_current_master_frame().value if tr else None,
                       "cvars": {c: unreal.SystemLibrary.get_console_variable_int_value(c) for c in CVARS}})
        restore.setdefault("transport_playing", playing)
        save_restore(restore)
    elif mode == "pause" and tr:
        report["result"] = str(tr.pause_transport())
    elif mode == "resume" and tr:
        report["result"] = str(tr.resume_forward())
    elif mode == "cmd":
        cmd = cfg.get("cmd", "")
        if not allowed(cmd):
            report["refused"] = cmd
        else:
            name = cmd.split()[0]
            if name in CVARS and name not in restore.get("cvars", {}):
                restore.setdefault("cvars", {})[name] = unreal.SystemLibrary.get_console_variable_int_value(name)
                save_restore(restore)
            if name in SHOWFLAGS:
                restore.setdefault("showflags", [])
                if name not in restore["showflags"]:
                    restore["showflags"].append(name)
                    save_restore(restore)
            unreal.SystemLibrary.execute_console_command(world, cmd)
            report["ran"] = cmd
    elif mode == "frames":
        record_frames(tag, int(cfg.get("frames", 300)))
    elif mode == "restore":
        ran = []
        for name in restore.get("showflags", []):
            unreal.SystemLibrary.execute_console_command(world, f"{name} 2")
            ran.append(f"{name} 2")
        for name, value in restore.get("cvars", {}).items():
            unreal.SystemLibrary.execute_console_command(world, f"{name} {value}")
            ran.append(f"{name} {value}")
        if tr and restore.get("transport_playing") is not None:
            now = bool(tr.is_transport_playing())
            if now != restore["transport_playing"]:
                ran.append(str(tr.resume_forward() if restore["transport_playing"] else tr.pause_transport()))
        report["ran"] = ran
        os.remove(RESTORE) if os.path.exists(RESTORE) else None
    del tr, world
    unreal.log(f"PUSS_SOFTGOODS_STUTTER_AB|{mode}|{tag}|" + json.dumps(report, default=str))


main()
