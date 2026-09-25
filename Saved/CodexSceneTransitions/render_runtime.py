import builtins
import json
import pathlib
import time
import traceback
import unreal

folder=pathlib.Path('E:/PussStage/Saved/CodexSceneTransitions')
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert editor.get_game_world() is None
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
prefs=unreal.find_object(None,'/Script/UnrealEd.Default__EditorPerformanceSettings')
original=prefs.get_editor_property('bThrottleCPUWhenNotForeground')
prefs.set_editor_property('bThrottleCPUWhenNotForeground',False)
state={'status':'starting','started':time.time(),'renders':[],'errors':[]}
ctx={}
def persist():(folder/'render_result.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
def finish(status):
    state['status']=status;persist()
    if ctx.get('player'):ctx['player'].pause()
    prefs.set_editor_property('bThrottleCPUWhenNotForeground',original)
    levels.editor_request_end_play()
    unreal.unregister_slate_post_tick_callback(builtins.PUSS_TRANSITION_RENDER_HANDLE)
    del builtins.PUSS_TRANSITION_RENDER_HANDLE
    unreal.log('SCENE_TRANSITION_RENDER_'+status.upper())
def tick(delta):
    if state.get('inside'):return
    state['inside']=True
    try:
        if time.time()-state['started']>180:raise RuntimeError('Render verification timed out')
        if state['status']=='starting':
            world=editor.get_game_world()
            if not world:return
            roots=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.InfinityStageShowRoot)
            if not roots or not roots[0].sequence_player:return
            root=roots[0];player=root.sequence_player;transport=root.transport
            player.pause();transport.set_editor_property('performance_mode',False)
            scenes=[s for s in transport.segments if s.type==unreal.InfinityCueType.SCENE]
            scene=scenes[2]
            transport.scrub_to_master_frame(unreal.FrameNumber(scene.start_frame.value-24000))
            transport.play_forward_to_boundary()
            ctx.update(root=root,player=player,transport=transport,world=world,pc=unreal.GameplayStatics.get_player_controller(world,0),scene=scene)
            state['status']='entry';return
        frame=ctx['transport'].get_current_master_frame().value
        offset=(frame-ctx['scene'].start_frame.value)/24000
        if state['status']=='entry' and offset>1:
            camera=ctx['pc'].get_view_target()
            assert isinstance(camera,unreal.CineCameraActor),camera
            file=folder/'Passage3_Into_Scene3.png'
            unreal.SystemLibrary.execute_console_command(ctx['world'],'HighResShot 1600x900 filename="'+file.as_posix()+'"',ctx['pc'])
            state['renders'].append({'file':str(file),'camera':camera.get_actor_label(),'master_tick':frame,'scene_seconds':offset})
            state['status']='shore';persist();return
        if state['status']=='shore' and offset>30:
            camera=ctx['pc'].get_view_target()
            assert camera.get_actor_label()=='ClamCam1',camera.get_actor_label()
            file=folder/'Scene3_Shore_From_Show.png'
            unreal.SystemLibrary.execute_console_command(ctx['world'],'HighResShot 1600x900 filename="'+file.as_posix()+'"',ctx['pc'])
            state['renders'].append({'file':str(file),'camera':camera.get_actor_label(),'master_tick':frame,'scene_seconds':offset})
            state['status']='settle';state['settle_start']=time.time();persist();return
        if state['status']=='settle' and time.time()-state['settle_start']>4:
            assert all(pathlib.Path(r['file']).is_file() for r in state['renders']),state
            finish('passed')
    except Exception:state['errors'].append(traceback.format_exc());finish('failed')
    finally:state['inside']=False
builtins.PUSS_TRANSITION_RENDER_HANDLE=unreal.register_slate_post_tick_callback(tick)
persist();levels.editor_request_begin_play()
unreal.log('SCENE_TRANSITION_RENDER_STARTED')
