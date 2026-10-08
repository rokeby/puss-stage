"""READ-ONLY in PIE: one sample of the Master frame (ticks) + Scene-3 seconds + wall clock. PIE_TAP|..."""
import time
def main():
    import unreal
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    root = list(unreal.GameplayStatics.get_all_actors_of_class(w, unreal.InfinityStageShowRoot))[0]
    f = root.transport.get_current_master_frame().value
    unreal.log("PIE_TAP|wall=%.2f|master=%d|s3_s=%.2f|playing=%s|rate=%s" % (time.time(), f, (f - 18884545) / 24000.0,
               root.sequence_player.is_playing(), root.sequence_player.get_play_rate()))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("PIE_TAP_FAILED|%r" % (exc,))
