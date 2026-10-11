"""End only the PIE explicitly started and retained by Job 185."""
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world() is None:
    raise RuntimeError("JOB185_END_OWNED_PIE_REFUSED|no_pie")
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
unreal.log("JOB185_END_OWNED_PIE_REQUESTED|owned=true")
