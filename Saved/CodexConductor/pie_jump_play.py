"""PIE transport helper (read-only to assets): scrub the Master to <segment label> start + offset_s and PLAY.
Args pie_jump_play_args.json {"run","segment","offset_s"}. Markers PIEJUMP_OK|run=..|frame=.. / PIEJUMP_FAILED|run=..|..."""
import json


def main():
    import unreal
    a = json.load(open("E:/PussStage/Saved/CodexConductor/pie_jump_play_args.json", encoding="utf-8"))
    run = a["run"]
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world is None:
        unreal.log_error("PIEJUMP_FAILED|run=%s|reason=NO_PIE" % run)
        return
    roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
    if len(roots) != 1:
        unreal.log_error("PIEJUMP_FAILED|run=%s|reason=ROOTS_%d" % (run, len(roots)))
        return
    root = roots[0]
    segs = [s for s in list(root.transport.segments) if s.type == unreal.InfinityCueType.SCENE
            and (str(s.label) == a["segment"] or str(s.label).startswith(a["segment"] + " "))]
    if len(segs) != 1:
        unreal.log_error("PIEJUMP_FAILED|run=%s|reason=SEGMENTS_%d" % (run, len(segs)))
        return
    target = int(segs[0].start_frame.value) + int(round(float(a["offset_s"]) * 24000))
    root.sequence_player.pause()
    res = root.transport.scrub_to_master_frame(unreal.FrameNumber(target))
    if res != unreal.InfinityTransportResult.SUCCEEDED:
        unreal.log_error("PIEJUMP_FAILED|run=%s|reason=SCRUB|%s" % (run, res))
        return
    root.sequence_player.play()
    unreal.log("PIEJUMP_OK|run=%s|segment_start=%d|frame=%d" % (run, int(segs[0].start_frame.value), target))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("PIEJUMP_FAILED|reason=EXC|%r" % (exc,))
