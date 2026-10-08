import json
def main():
    import unreal
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    unreal.log("PIE_DT|%.5f" % unreal.GameplayStatics.get_world_delta_seconds(w))
main()
