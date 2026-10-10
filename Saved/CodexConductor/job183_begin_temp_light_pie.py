"""Start owned PIE with only Job 183's temporary-light map dirtiness."""
import unreal


LABEL = "JOB183 TEMP Stage Front Neutral Review Light"
TAG = "JOB183_STAGEFRONT_NEUTRAL_TEMP"
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world() is not None:
    raise RuntimeError("JOB183_TEMP_PIE_REFUSED|existing_pie")
content = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
maps = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
owned = [a for a in actors if str(a.get_actor_label()) == LABEL and
         TAG in {str(t) for t in a.get_editor_property("tags")}]
if content or maps != ["/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"] or len(owned) != 1:
    raise RuntimeError("JOB183_TEMP_PIE_REFUSED|content=%s|maps=%s|owned=%d" % (content, maps, len(owned)))
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
unreal.log("JOB183_TEMP_LIGHT_PIE_START_REQUESTED|owned=true|temp_light=1|saved=false")
