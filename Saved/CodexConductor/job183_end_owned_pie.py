"""End only the PIE explicitly started by Job 183 in this session."""
import unreal
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world() is None:
    raise RuntimeError("JOB183_END_OWNED_PIE_REFUSED|no_pie")
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
unreal.log("JOB183_END_OWNED_PIE_REQUESTED|owner=JOB183-LIVE-20261010")
