import json, pathlib, time
import unreal
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert editor.get_editor_world().get_path_name().startswith('/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.')
def p(o): return o.get_path_name() if o else None
def v(o,k):
    try:
        x=o.get_editor_property(k)
        return x.export_text() if hasattr(x,'export_text') else str(x)
    except Exception as e:return str(e)
out={'time':time.time(),'editor_world':p(editor.get_editor_world()),'game_world':p(editor.get_game_world()),'dirty':[p(x) for x in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())],'worlds':[]}
for w in [editor.get_editor_world(),editor.get_game_world()]:
    if not w:continue
    row={'world':p(w),'roots':[],'curtains':[],'players':[]}
    pc=unreal.GameplayStatics.get_player_controller(w,0)
    if pc:
        row['controller']={'path':p(pc),'class':pc.get_class().get_name(),'view':p(pc.get_view_target()),'pawn':p(pc.get_pawn()),'paused':unreal.GameplayStatics.is_game_paused(w),'camera_location':str(pc.player_camera_manager.get_camera_location()),'camera_rotation':str(pc.player_camera_manager.get_camera_rotation())}
    for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.InfinityStageShowRoot):
        t=a.transport
        row['roots'].append({'path':p(a),'playback':v(a,'playback_settings'),'frame':t.get_current_master_frame().value,'playing':t.is_transport_playing(),'selected':v(t,'selected_segment_index'),'last_result':v(t,'last_result'),'segments':[s.export_text() for s in t.segments[:4]]})
    for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.InfinityStageCurtainRig):
        row['curtains'].append({'path':p(a),'transform':a.get_actor_transform().export_text(),'progress':v(a,'curtain_progress'),'active':v(a,'curtain_active'),'distance':v(a,'curtain_distance_cm')})
    for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.LevelSequenceActor):
        player=a.sequence_player
        row['players'].append({'path':p(a),'sequence':p(a.get_sequence()),'playing':player.is_playing() if player else None,'time':player.get_current_time().export_text() if player else None})
    out['worlds'].append(row)
pathlib.Path('E:/PussStage/Saved/CodexSceneTransitions/stalled_opening.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
unreal.log('OPENING_LIVE_INSPECTION_SUCCESS|game='+str(out['game_world']))
