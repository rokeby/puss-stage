"""PIE-ONLY cloth-gate measurement (29 Sep): which switch removes the six Shore drapes' 13.4 ms stall
(`FChaosClothComponentEndTickFunction_ExecuteTick (6)` / `CPU Stall - Wait For Event`, conductor's dumpframe 12:54)?

NEVER starts PIE and never touches an asset or the editor level: it acts only on the PIE copies of the six
ChaosClothComponents, so everything it does ends with the PIE session. Gary starts PIE (or okays it).
One mode per MCP call, read from cloth_gate_mode.json next to this file ({"mode": ..., "tag": ...}):
  status       report the six components' enabled/suspended state
  to_passage   ask the transport for the next segment (Opening -> Passage 1), "in a passage" as it was measured
  dump         `stat dumpframe -ms=1` (the dump lands in the log on the next frame)
  set_suspend  SuspendSimulation() on all six (holds the last pose)
  set_disable  ResumeSimulation() + SetEnableSimulation(False) (skinned pose)
  set_restore  SetEnableSimulation(True) + ResumeSimulation()
  hitch_on     t.HitchFrameTimeThreshold <ms> + `stat dumphitches`: the engine logs the stat tree of every frame
               over the threshold, which names the owner of Gary's ~1 Hz "40 -> 12 fps" stutter (a different
               signature from the cloth's constant 13.4 ms floor)
  hitch_off    `stat dumphitches` again (it toggles)
  frames       record N frame deltas via a self-unregistering Slate post-tick callback (floats only), then log
               mean/p95/max, the frames over 40 ms and the INTERVALS between them. Periodic spikes = a finding.
               Issue NO other call until its PUSS_SOFTGOODS_FRAMES line appears: every MCP call is itself a hitch.
Procedure (each line one call): to_passage, frames, hitch_on, dump, dump, set_suspend, frames, dump, dump,
set_disable, dump, dump, set_restore, dump, hitch_off, then `python Scripts/parse_cloth_dumps.py`.
Hitches logged within ~1 s of a PUSS_SOFTGOODS_CLOTH_GATE marker are self-inflicted by the MCP call; ignore them. Each call logs PUSS_SOFTGOODS_CLOTH_GATE|<mode>|<tag>|<state>,
which the parser uses to label the dumps that follow it. Crash rules: all inside main(), nothing kept at module level.
"""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")


def pie_world():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    return editor.get_game_world()


def cloth_components(world):
    rows = []
    for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
        for comp in actor.get_components_by_class(unreal.ActorComponent):
            if comp.get_class().get_name() == "ChaosClothComponent":
                rows.append((actor, comp))
    return rows


def record_frames(tag, count):
    """Collect `count` frame deltas (floats only, no UE objects held), then unregister and log a summary."""
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
        gaps = [round(b - a, 3) for a, b in zip(spikes, spikes[1:])]
        summary = {"tag": tag, "frames": len(t), "seconds": round(sum(t), 2), "mean_ms": round(sum(ms) / len(ms), 2),
                   "median_ms": round(ms[len(ms) // 2], 2), "p95_ms": round(ms[int(len(ms) * 0.95)], 2),
                   "max_ms": round(ms[-1], 2), "over_40ms": len(spikes), "spike_times_s": spikes[:40],
                   "spike_gaps_s": gaps[:40]}
        with open(os.path.join(HERE, f"cloth_gate_frames_{tag or 'untagged'}.json"), "w", encoding="utf-8") as h:
            json.dump(summary, h, indent=1)
        unreal.log("PUSS_SOFTGOODS_FRAMES|" + json.dumps(summary))

    state["handle"] = unreal.register_slate_post_tick_callback(tick)


def main():
    with open(os.path.join(HERE, "cloth_gate_mode.json"), encoding="utf-8") as h:
        cfg = json.load(h)
    mode, tag = cfg.get("mode", "status"), cfg.get("tag", "")
    world = pie_world()
    if world is None:
        unreal.log("PUSS_SOFTGOODS_CLOTH_GATE_STOPPED|no PIE world: this script never starts PIE; ask Gary")
        return
    report = {"mode": mode, "tag": tag, "components": []}
    rows = cloth_components(world)
    report["count"] = len(rows)
    if mode == "to_passage":
        roots = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot)
        transport = roots[0].get_editor_property("transport") if roots else None
        report["jump"] = str(transport.jump_to_next_segment()) if transport else "no transport"
        del roots, transport
    for actor, comp in rows:
        if mode == "set_suspend":
            comp.suspend_simulation()
        elif mode == "set_disable":
            comp.resume_simulation()
            comp.set_enable_simulation(False)
        elif mode == "set_restore":
            comp.set_enable_simulation(True)
            comp.resume_simulation()
        report["components"].append({"actor": actor.get_actor_label(), "class": actor.get_class().get_name(),
                                     "enabled": comp.is_simulation_enabled(),
                                     "suspended": comp.is_simulation_suspended()})
    del rows
    state = ";".join(f"{c['actor']}:{'E' if c['enabled'] else 'e'}{'S' if c['suspended'] else 's'}"
                     for c in report["components"])
    unreal.log(f"PUSS_SOFTGOODS_CLOTH_GATE|{mode}|{tag}|n={report['count']}|{state}")
    if mode == "dump":
        unreal.SystemLibrary.execute_console_command(world, "stat dumpframe -ms=1")
    elif mode == "hitch_on":
        unreal.SystemLibrary.execute_console_command(world, f"t.HitchFrameTimeThreshold {int(cfg.get('hitch_ms', 45))}")
        unreal.SystemLibrary.execute_console_command(world, "stat dumphitches")
    elif mode == "hitch_off":
        unreal.SystemLibrary.execute_console_command(world, "stat dumphitches")
    elif mode == "frames":
        record_frames(tag, int(cfg.get("frames", 300)))
    del world
    with open(os.path.join(HERE, f"cloth_gate_{mode}.json"), "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)


main()
