"""PIE-only bench (no saves, PIE copies only): pause, HighResShot; then hide the S3 wave flats in the PIE world and shoot
again (shows whether the waves occlude the clam). Args pie_occlusion_bench_args.json {"phase":"shotA"|"hide_and_shotB"|"unhide"}.
PIE_OCC_OK|phase."""
import json
def main():
    import unreal
    ph = json.load(open("E:/PussStage/Saved/CodexConductor/pie_occlusion_bench_args.json"))["phase"]
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    root = list(unreal.GameplayStatics.get_all_actors_of_class(w, unreal.InfinityStageShowRoot))[0]
    root.sequence_player.pause()
    waves = [a for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)
             if any(s in a.get_name() + str(a.get_actor_label() if hasattr(a, "get_actor_label") else "") for s in ("WaveV3_L", "WaveV3 L", "Wave Row", "Wave Split", "Wave_Row", "Wave_Split"))]
    if ph == "hide_and_shotB":
        for a in waves:
            a.set_actor_hidden_in_game(True)
    if ph == "unhide":
        for a in waves:
            a.set_actor_hidden_in_game(False)
    if ph in ("shotA", "hide_and_shotB"):
        unreal.SystemLibrary.execute_console_command(w, "HighResShot 1600x900")
    unreal.log("PIE_OCC_OK|%s|waves=%d" % (ph, len(waves)))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("PIE_OCC_FAILED|%r" % (exc,))
