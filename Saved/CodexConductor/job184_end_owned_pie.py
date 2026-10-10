"""End only the PIE explicitly started by Job 184 in this session."""
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world() is None:
    raise RuntimeError("JOB184_END_OWNED_PIE_REFUSED|no_pie")
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
unreal.log("JOB184_END_OWNED_PIE_REQUESTED|owner=JOB184-LIVE-20261010")
