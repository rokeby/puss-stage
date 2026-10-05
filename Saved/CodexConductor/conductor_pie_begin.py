"""Conductor's OWN PIE for captures (Gary authorised for the night of 5 Oct). Refuses if PIE runs or the census is dirty."""
import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
lib = unreal.EditorLoadingAndSavingUtils
if ed.get_game_world() is not None:
    raise RuntimeError("PIE already active; refusing")
if list(lib.get_dirty_content_packages()):
    raise RuntimeError("dirty content packages; refusing")  # a dirty MAP is allowed: look-bench PREPARE dirties it by design
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
unreal.log("CONDUCTOR_PIE_BEGIN_REQUESTED")
