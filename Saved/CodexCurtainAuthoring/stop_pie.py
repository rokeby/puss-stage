import unreal


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world() is not None:
    unreal.EditorLevelLibrary.editor_end_play()
    unreal.log("PUSS_CURTAIN_PIE_STOP_REQUESTED")
else:
    unreal.log("PUSS_CURTAIN_PIE_ALREADY_STOPPED")

