"""Start only Job 185's owned PIE from a clean vertical-slice editor."""
import unreal

WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world() is not None:
    raise RuntimeError("JOB185_PIE_START_REFUSED|existing_pie")
world = editor.get_editor_world()
if world.get_outermost().get_name() != WORLD:
    raise RuntimeError("JOB185_PIE_START_REFUSED|wrong_world=" + world.get_outermost().get_name())
content = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
maps = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if content or maps:
    raise RuntimeError("JOB185_PIE_START_REFUSED|content=%s|maps=%s" % (content, maps))
result = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
unreal.log("JOB185_PIE_START_REQUESTED|result=%s|owned=true" % result)
