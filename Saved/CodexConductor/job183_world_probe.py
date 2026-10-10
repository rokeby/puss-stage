"""Read-only editor/PIE world identity probe for Job 183."""
import unreal


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
editor_world = editor.get_editor_world()
game_world = editor.get_game_world()
unreal.log("JOB183_WORLD_PROBE|editor=%s|game=%s" % (
    editor_world.get_path_name() if editor_world is not None else "NONE",
    game_world.get_path_name() if game_world is not None else "NONE"))
