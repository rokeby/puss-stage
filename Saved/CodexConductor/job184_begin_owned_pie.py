"""Start Job 184's own PIE only from a clean, non-PIE editor."""
import unreal


RUN = "JOB184-LIVE-20261010"
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world() is not None:
    raise RuntimeError("JOB184_PIE_START_REFUSED|existing_pie")
dirty_content = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
dirty_maps = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if dirty_content or dirty_maps:
    raise RuntimeError("JOB184_PIE_START_REFUSED|content=%s|maps=%s" % (dirty_content, dirty_maps))
result = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
unreal.log("JOB184_PIE_START_REQUESTED|run=%s|result=%s|owned=true" % (RUN, result))
