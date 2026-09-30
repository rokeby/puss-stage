"""Read-only: does the show's sequence player ignore Sequencer camera cuts? (30 Sep)

The Scene 1 play-through (scene1_tail_view.json) held Scene 1's Entry camera for 21 s: the Exit cut at 14 s and
LS_Animals_1's own cuts never took the view. The transport claims only at boundaries, and its registry touches
only the Passage track (MovieSceneInfinityPassageTrack.cpp:120-160), so the question is the player's own
PlaybackSettings (an instance property of the ShowRoot actor, InfinityStageShowRoot.cpp:17-33).
Plain property reads only. Success marker: PUSS_SHOW_PLAYER_CUTS
"""
import unreal


def main():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    roots = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot)
    out = []
    for root in roots:
        settings = root.get_editor_property("playback_settings")
        values = {}
        for name in ("disable_camera_cuts", "auto_play", "restore_state", "pause_at_end"):
            try:
                values[name] = settings.get_editor_property(name)
            except Exception as error:  # a property name may differ in 5.8
                values[name] = "unreadable: %s" % error
        out.append("%s %s" % (root.get_actor_label(), values))
    unreal.log("PUSS_SHOW_PLAYER_CUTS|roots=%d|%s" % (len(roots), " ; ".join(out)))


main()
