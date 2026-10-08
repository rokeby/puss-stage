"""PIE only, no writes: pause, scrub the Master to Scene 1 start, play. Marker S1PLAY_OK|run=..."""
import datetime
import unreal
run = datetime.datetime.now().strftime("%H%M%S")
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if world is None:
    unreal.log_error("S1PLAY_FAILED|run=%s|no PIE" % run)
else:
    roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
    root = roots[0] if len(roots) == 1 else None
    segs = [s for s in list(root.transport.segments) if s.type == unreal.InfinityCueType.SCENE
            and (str(s.label) == "Scene 1" or str(s.label).startswith("Scene 1 "))] if root else []
    if len(segs) != 1:
        unreal.log_error("S1PLAY_FAILED|run=%s|roots=%d segs=%d" % (run, len(roots), len(segs)))
    else:
        a = int(segs[0].start_frame.value)
        root.sequence_player.pause()
        ok = root.transport.scrub_to_master_frame(unreal.FrameNumber(a))
        root.sequence_player.play()
        unreal.log("S1PLAY_OK|run=%s|start=%d|scrub=%s|playing=%s" % (run, a, ok, root.transport.is_transport_playing()))
