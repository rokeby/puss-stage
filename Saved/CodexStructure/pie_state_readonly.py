"""READ-ONLY: is PIE running, and what do the editor/game worlds report? Marker PIE_STATE."""
import unreal


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    gw, ew = ed.get_game_world(), ed.get_editor_world()
    unreal.log(f"PIE_STATE|game_world={gw.get_path_name() if gw else None}|editor_world={ew.get_path_name() if ew else None}")


main()
