"""PIE-ONLY exposure bench (no editor-world write, no save; PIE state vanishes when PIE ends).
Args pie_exposure_bench_args.json {"run","phase":"jump"|"weight"|"shot","segment","offset_s","label","weight","path"}
  jump:   pause + scrub to <segment> start + offset_s
  weight: set the PIE copy of <label> PostProcessVolume BlendWeight (paused, so Sequencer does not rewrite it)
  shot:   HighResShot 1600x900 to path
Markers PIEEXP_OK|run=..|phase=.. / PIEEXP_FAILED|run=..|..."""
import json


def main():
    import unreal
    a = json.load(open("E:/PussStage/Saved/CodexConductor/pie_exposure_bench_args.json", encoding="utf-8"))
    run, ph = a["run"], a["phase"]
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world is None:
        unreal.log_error("PIEEXP_FAILED|run=%s|reason=NO_PIE" % run)
        return
    root = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))[0]
    if ph == "jump":
        segs = [s for s in list(root.transport.segments) if s.type == unreal.InfinityCueType.SCENE
                and (str(s.label) == a["segment"] or str(s.label).startswith(a["segment"] + " "))]
        target = int(segs[0].start_frame.value) + int(round(float(a["offset_s"]) * 24000))
        root.sequence_player.pause()
        res = root.transport.scrub_to_master_frame(unreal.FrameNumber(target))
        if res != unreal.InfinityTransportResult.SUCCEEDED:
            unreal.log_error("PIEEXP_FAILED|run=%s|phase=jump|%s" % (run, res))
            return
        unreal.log("PIEEXP_OK|run=%s|phase=jump|frame=%d" % (run, int(root.transport.get_current_master_frame().value)))
    elif ph == "weight":
        vols = [v for v in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.PostProcessVolume)
                if str(v.get_actor_label()) == a["label"]]
        if len(vols) != 1:
            unreal.log_error("PIEEXP_FAILED|run=%s|phase=weight|count=%d" % (run, len(vols)))
            return
        before = vols[0].blend_weight
        vols[0].blend_weight = float(a["weight"])
        unreal.log("PIEEXP_OK|run=%s|phase=weight|before=%.4f|after=%.4f" % (run, before, vols[0].blend_weight))
    elif ph == "shot":
        unreal.SystemLibrary.execute_console_command(world, 'HighResShot 1600x900 filename="%s"' % a["path"])
        unreal.log("PIEEXP_OK|run=%s|phase=shot|path=%s" % (run, a["path"]))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("PIEEXP_FAILED|reason=EXC|%r" % (exc,))
