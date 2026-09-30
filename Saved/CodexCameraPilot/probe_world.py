"""Read-only: which world the editor has open, and whether PIE is running. Marker: PUSS_WORLD_PROBE"""
import unreal


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    game = editor.get_game_world()
    unreal.log("PUSS_WORLD_PROBE|editor=%s|pie=%s" % (world.get_path_name() if world else None,
                                                     game.get_path_name() if game else None))


main()
