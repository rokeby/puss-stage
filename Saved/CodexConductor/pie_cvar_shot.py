"""PIE bench (no saves): set console variables in the PIE world (args), pause, HighResShot. Args pie_cvar_shot_args.json
{"cvars":["r.Lumen.HardwareRayTracing 1"], "shot": true}.  PIE_CVAR_OK|..."""
import json
def main():
    import unreal
    a = json.load(open("E:/PussStage/Saved/CodexConductor/pie_cvar_shot_args.json"))
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    root = list(unreal.GameplayStatics.get_all_actors_of_class(w, unreal.InfinityStageShowRoot))[0]
    root.sequence_player.pause()
    for c in a.get("cvars", []):
        unreal.SystemLibrary.execute_console_command(w, c)
    if a.get("shot"):
        unreal.SystemLibrary.execute_console_command(w, "HighResShot 1600x900")
    unreal.log("PIE_CVAR_OK|%s" % a)
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("PIE_CVAR_FAILED|%r" % (exc,))
