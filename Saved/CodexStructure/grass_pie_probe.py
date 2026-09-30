"""PIE, read-only for the saved level (30 Sep): does HIDING a landscape stop its grass from generating? The editor
count was inconclusive: both hidden landscapes still hold their 1,467 + 1,482 grass components but zero instances,
and grass instances generate at RUNTIME around the game camera, so only a PIE read at P02 can answer. The answer
sets how hard the delete is pushed: Gary's P02 "background loaded late" is the complaint it would repair.

PRE-REGISTERED, before any run. Mode "p02" (the landscapes hidden as saved), then mode "control" at the same camera:
  - hidden instances > 0: hiding does NOT stop generation. The delete is the repair for the load complaint (the
    report also says whether those instances render: visible / recently rendered).
  - hidden = 0 and control > 0: hiding stops generation. The hide already fixed it; the delete is tidiness.
  - hidden = 0 and control = 0: the camera is out of grass range, or grass is off at this scalability
    (grass.Enable and density are reported). INCONCLUSIVE; say so, do not round it to "fixed".
A zero from "p02" alone is not a result: it needs the control's non-zero at the same camera.

Mode from GRASS_MODE (set by the runners), one per MCP call; each returns at once, then samples on a Slate
post-tick callback at 0.5 / 2 / 5 / 10 s and logs GRASS_PIE|done|run=<id>|... Wait for THAT run id's line before
the next call (an earlier run's line in the log is not this run's answer).
  here     sample at wherever the PIE camera already is. Touches nothing.
  p02      scrub the transport to the middle of the passage segment before Scene 2 (P02), hold, sample.
  control  un-hide the PIE COPIES of the landscapes, sample at the current camera, re-hide them at the end.
           The PIE world is a duplicate: nothing reaches the editor level or any asset. Run it right after "p02".
It needs a PIE session someone else already owns and has agreed to share; it never starts or ends PIE.
Writes grass_pie_<mode>_<run>.json. Crash rules: everything inside main(); the callback keeps plain data only and
fetches the PIE world fresh every tick."""
import datetime
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
SAMPLES_S = (0.5, 2.0, 5.0, 10.0)
MAX_TICKS = 5000
TICKS_PER_S = 24000.0            # Master tick resolution


def main():
    mode = globals().get("GRASS_MODE", "here")
    run = datetime.datetime.now().strftime("%H%M%S")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_game_world()
    if world is None or "UEDPIE" not in world.get_path_name():
        unreal.log(f"GRASS_PIE|refused|run={run}|PIE is not running (this probe never starts it)")
        return
    if mode not in ("here", "p02", "control"):
        unreal.log(f"GRASS_PIE|refused|run={run}|unknown mode {mode}")
        return

    def landscapes(w):
        return [a for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.LandscapeProxy)]

    def grass_of(a):
        if hasattr(unreal, "GrassInstancedStaticMeshComponent"):
            return list(a.get_components_by_class(unreal.GrassInstancedStaticMeshComponent))
        return [c for c in a.get_components_by_class(unreal.InstancedStaticMeshComponent) if "Grass" in c.get_class().get_name()]

    def sample(w, t):
        pc = unreal.GameplayStatics.get_player_controller(w, 0)
        pcm = pc.get_editor_property("player_camera_manager") if pc else None
        cam = pcm.get_camera_location() if pcm else None
        rows = []
        for a in landscapes(w):
            comps = grass_of(a)
            inst = [c.get_instance_count() for c in comps]
            rendered = 0
            for c, n in zip(comps, inst):
                try:
                    rendered += 1 if n and c.was_recently_rendered(0.5) else 0
                except Exception:  # noqa: BLE001
                    rendered = -1
                    break
            o, e = a.get_actor_bounds(False)
            dist = None
            if cam:
                dx, dy = max(abs(cam.x - o.x) - e.x, 0.0), max(abs(cam.y - o.y) - e.y, 0.0)
                dist = round((dx * dx + dy * dy) ** 0.5 / 100.0, 1)
            rows.append({"label": a.get_actor_label(), "hidden": bool(a.get_editor_property("hidden")), "grass_components": len(comps),
                         "populated": sum(1 for n in inst if n), "instances": sum(inst), "visible_populated": sum(1 for c, n in zip(comps, inst) if n and c.is_visible()),
                         "recently_rendered_populated": rendered, "camera_to_bounds_m": dist})
        return {"t_s": t, "camera_xyz": [round(cam.x), round(cam.y), round(cam.z)] if cam else None, "landscapes": rows}

    cvars = {}
    for name in ("grass.Enable", "grass.DensityScale", "grass.CullDistanceScale", "sg.FoliageQuality"):
        try:
            cvars[name] = unreal.SystemLibrary.get_console_variable_float_value(name)
        except Exception:  # noqa: BLE001
            cvars[name] = None

    note = ""
    if mode == "p02":
        roots = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot)
        transport = roots[0].get_editor_property("transport") if roots else None
        if transport is None:
            unreal.log(f"GRASS_PIE|refused|run={run}|no transport")
            return
        segs = transport.get_editor_property("segments")
        labels = [str(s.get_editor_property("label")) for s in segs]
        s2 = [i for i, l in enumerate(labels) if l.startswith("Scene 2")]
        if len(s2) != 1 or s2[0] == 0 or labels[s2[0] - 1].startswith("Scene"):
            unreal.log(f"GRASS_PIE|refused|run={run}|expected one Scene 2 segment after a passage, labels={labels}")
            return
        seg = segs[s2[0] - 1]
        start, end = seg.get_editor_property("start_frame").value, seg.get_editor_property("end_frame").value
        scrub = transport.scrub_to_master_frame(unreal.FrameNumber(int((start + end) / 2)))
        note = f"scrubbed to the middle of '{labels[s2[0] - 1]}' ({(end - start) / TICKS_PER_S / 2:.1f} s in): {scrub}"
    elif mode == "control":
        for a in landscapes(world):
            a.set_actor_hidden_in_game(False)
        note = "PIE copies un-hidden for the control; re-hidden at the end"

    state = {"handle": None, "elapsed": 0.0, "ticks": 0, "samples": []}
    pending = list(SAMPLES_S)

    def finish(why):
        unreal.unregister_slate_post_tick_callback(state["handle"])
        w = editor.get_game_world()
        if mode == "control" and w is not None:
            for a in landscapes(w):
                a.set_actor_hidden_in_game(True)
        out = {"mode": mode, "run": run, "note": note, "why": why, "cvars": cvars, "samples": state["samples"]}
        with open(os.path.join(HERE, f"grass_pie_{mode}_{run}.json"), "w", encoding="utf-8") as h:
            json.dump(out, h, indent=1)
        last = state["samples"][-1] if state["samples"] else None
        summary = [(r["label"], r["hidden"], r["instances"], r["recently_rendered_populated"], r["camera_to_bounds_m"]) for r in last["landscapes"]] if last else None
        unreal.log(f"GRASS_PIE|done|run={run}|mode={mode}|{why}|camera={last['camera_xyz'] if last else None}|"
                   f"(label, hidden, instances, rendered, cam_to_bounds_m)={summary}|"
                   f"instances_over_time={[sum(r['instances'] for r in s['landscapes']) for s in state['samples']]}|cvars={cvars}")

    def tick(delta):
        w = editor.get_game_world()                    # fetched fresh: never touch a PIE world that has ended
        if w is None:
            return finish("PIE ended early")
        state["elapsed"] += delta
        state["ticks"] += 1
        if pending and state["elapsed"] >= pending[0]:
            state["samples"].append(sample(w, round(state["elapsed"], 2)))
            pending.pop(0)
        if not pending:
            return finish("ok")
        if state["ticks"] > MAX_TICKS:
            return finish(f"only {len(state['samples'])} samples within {MAX_TICKS} ticks")

    state["handle"] = unreal.register_slate_post_tick_callback(tick)
    unreal.log(f"GRASS_PIE|armed|run={run}|mode={mode}|{note}")


main()
