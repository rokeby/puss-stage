"""EDITOR BENCH, NO PIE, NO SAVES (29 Sep): does the baked Opening drape actually fall, and what does it look like
from the stalls? Gary: "The opening curtain doesn't seem to have its fall away animation triggered ... the texture and
lighting is bad".

One mode per MCP call, from opening_bench_mode.json ({"mode": ..., "frame": N}):
  open    open LS_Opening_Curtain_Baked in Sequencer (its spawnable drape appears in the editor world, transient)
  frame   set the Sequencer time to N; read the spawned GeometryCacheActor: IsPlaying, animation/elapsed time, running
          flag, actor bounds; and queue a high-res screenshot FROM the "Opening — Stalls Camera" actor
          (Saved/CodexSoftGoods/OpeningBench/f<N>.png; it is written on the next frame, so one frame per call)
  close   close the sequence (Sequencer restores state) and report the dirty set, which must be []
PROOF of the fall: bounds Zmax about 1020 cm at frame 10 (hang), much lower by 150, about 85 at 350 (pile), with the
animation time advancing. If the bounds do not move, the section is not driving the cache.
Crash rules: all inside main(); no UE objects at module level.
"""
import json
import os

import unreal

SEQ = "/Game/InfinityStage/Interactions/LS_Opening_Curtain_Baked"
CAMERA_LABEL = "Opening — Stalls Camera"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")


def dirty():
    return sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
        sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())


def main():
    with open(os.path.join(HERE, "opening_bench_mode.json"), encoding="utf-8") as h:
        cfg = json.load(h)
    mode = cfg.get("mode")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        unreal.log("PUSS_SOFTGOODS_OPENING_BENCH_STOPPED|PIE is running; this bench is editor-only")
        return
    lib = unreal.LevelSequenceEditorBlueprintLibrary
    report = {"mode": mode}
    if mode == "open":
        report["dirty_before"] = dirty()
        report["opened"] = lib.open_level_sequence(unreal.load_asset(SEQ))
    elif mode == "frame":
        frame = int(cfg.get("frame", 0))
        lib.set_current_time(frame)
        report["frame"] = frame
        ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        actors = ss.get_all_level_actors()
        drapes = [a for a in actors if a.get_class().get_name() == "GeometryCacheActor"]
        cams = [a for a in actors if a.get_actor_label() == CAMERA_LABEL]
        report["drapes"] = len(drapes)
        if drapes:
            comp = drapes[0].get_editor_property("geometry_cache_component")
            origin, extent = drapes[0].get_actor_bounds(False)
            report.update({"is_playing": comp.is_playing(), "animation_time": comp.get_animation_time(),
                           "elapsed_time": comp.get_elapsed_time(), "duration": comp.get_duration(),
                           "running": comp.get_editor_property("running"),
                           "zmin": round(origin.z - extent.z, 1), "zmax": round(origin.z + extent.z, 1),
                           "xmin": round(origin.x - extent.x, 1), "xmax": round(origin.x + extent.x, 1)})
            del comp
        if cams:
            out_dir = os.path.join(HERE, "OpeningBench")
            os.makedirs(out_dir, exist_ok=True)
            report["screenshot"] = os.path.join(out_dir, f"f{frame:04d}.png")
            unreal.AutomationLibrary.take_high_res_screenshot(1600, 900, report["screenshot"], camera=cams[0])
        del actors, drapes, cams
    elif mode == "close":
        lib.close_level_sequence()
        report["dirty_after"] = dirty()
    del editor
    with open(os.path.join(HERE, f"opening_bench_{mode}.json"), "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    unreal.log("PUSS_SOFTGOODS_OPENING_BENCH|" + json.dumps(report, default=str))


main()
