"""End the conductor's OWN PIE (only after a look-bench restore). Logs the census after."""
import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if ed.get_game_world() is None:
    unreal.log("CONDUCTOR_PIE_END|no PIE running")
else:
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    unreal.log("CONDUCTOR_PIE_END_REQUESTED")
