import builtins
import json
import math
import pathlib
import time
import traceback
import unreal

folder=pathlib.Path('E:/PussStage/Saved/CodexSceneTransitions')
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert editor.get_game_world() is None
assert not hasattr(builtins,'PUSS_TRANSITION_QC_HANDLE')
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
settings=unreal.load_object(None,'/Script/UnrealEd.Default__EditorPerformanceSettings')
original_throttle=settings.get_editor_property('bThrottleCPUWhenNotForeground')
settings.set_editor_property('bThrottleCPUWhenNotForeground',False)
unreal.LevelSequenceEditorBlueprintLibrary.pause()
unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
levels.eject_pilot_level_actor()
state={'status':'starting','started':time.time(),'transitions':[],'samples':[],'errors':[]}
builtins.PUSS_TRANSITION_QC_STATE=state
context={}
def persist():
    (folder/'opening_transition_regression.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
def finish(status):
    state['status']=status;state['finished']=time.time();persist()
    if context.get('player'):context['player'].pause()
    settings.set_editor_property('bThrottleCPUWhenNotForeground',original_throttle)
    levels.editor_request_end_play()
    unreal.unregister_slate_post_tick_callback(builtins.PUSS_TRANSITION_QC_HANDLE)
    del builtins.PUSS_TRANSITION_QC_HANDLE
    unreal.log('SCENE_TRANSITION_RUNTIME_'+status.upper()+'|boundaries='+str(len(state['transitions']))+'|shore_samples='+str(len(state['samples'])))
def current_camera():
    pc=context['pc'];target=pc.get_view_target()
    cam=target.get_component_by_class(unreal.CineCameraComponent) if target else None
    return {'label':target.get_actor_label() if target else None,'path':target.get_path_name() if target else None,'position':list(cam.get_world_location().to_tuple()) if cam else None,'rotation':list(cam.get_world_rotation().to_tuple()) if cam else None,'focal':cam.current_focal_length if cam else None,'owner':str(context['root'].get_current_camera_owner())}
def cue_next():
    index=state.get('test_index',0)
    if index>=len(context['passages']):
        # Test the real nested LS_Clams through the one Show player, preserving
        # native bindings (no extra player or binding override in this verifier).
        scene=context['segments'][context['passages'][2]+1]
        state['shore_scene_start']=scene.start_frame.value
        seq=unreal.load_asset('/Game/InfinityStage/Dev/Sequences/LS_DevScene_03')
        child=next(s for t in seq.get_tracks() if isinstance(t,unreal.MovieSceneSubTrack) for s in t.get_sections() if s.get_sequence() and s.get_sequence().get_name()=='LS_Clams')
        state['shore_start']=scene.start_frame.value+round(child.get_start_frame()/seq.get_display_rate().numerator*24000)+48000
        context['transport'].scrub_to_master_frame(unreal.FrameNumber(state['shore_start']))
        context['transport'].play_forward_to_boundary()
        state['status']='shore';state['phase_started']=time.time();persist();return
    segment_index=context['passages'][index]
    scene=context['segments'][segment_index+1]
    transport=context['transport']
    transport.scrub_to_master_frame(unreal.FrameNumber(scene.start_frame.value-24000))
    context['player'].set_play_rate(1.0)
    state['current']={'passage_index':segment_index,'scene':str(scene.label),'boundary':scene.start_frame.value,'scene_end':scene.end_frame.value,'before':current_camera()}
    transport.play_forward_to_boundary()
    state['phase_started']=time.time();state['status']='boundary';persist()
def tick(delta):
    if state.get('inside'):return
    state['inside']=True
    try:
        if time.time()-state['started']>240:raise RuntimeError('Runtime transition validation timed out')
        if state['status']=='starting':
            world=editor.get_game_world()
            if not world:return
            roots=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.InfinityStageShowRoot)
            if not roots or not roots[0].sequence_player:return
            assert len(roots)==1
            root=roots[0];player=root.sequence_player;transport=root.transport
            assert transport.auto_play_scene_after_passage
            pc=unreal.GameplayStatics.get_player_controller(world,0)
            assert pc,'No PlayerController in test world'
            player.pause();transport.set_editor_property('performance_mode',False)
            segments=list(transport.segments)
            context.update(world=world,root=root,player=player,transport=transport,pc=pc,segments=segments,passages=[i for i,s in enumerate(segments) if s.type==unreal.InfinityCueType.WING_PAIR])
            assert len(context['passages'])==6
            state['world']=world.get_path_name();state['player']=player.get_path_name()
            state['segments']=[{'label':str(s.label),'start':s.start_frame.value,'end':s.end_frame.value,'type':str(s.type)} for s in segments]
            cue_next();return
        transport=context['transport'];frame=transport.get_current_master_frame().value
        if state['status']=='boundary':
            row=state['current']
            if frame<row['boundary']+24000 and time.time()-state['phase_started']<8:return
            row.update(after_frame=frame,playing=transport.is_transport_playing(),after=current_camera())
            assert row['playing'] and frame>row['boundary'],row
            assert row['after']['path']!=row['before']['path'],row
            assert 'InfinityStageCameraRig' not in (row['after']['path'] or ''),row
            state['transitions'].append(row)
            # Verify that the same ordinary Play operation holds at the Scene
            # end, without playing the curtain or the following Passage.
            transport.scrub_to_master_frame(unreal.FrameNumber(row['scene_end']-12000))
            transport.play_forward_to_boundary()
            state['status']='hold';state['phase_started']=time.time();persist();return
        if state['status']=='hold':
            row=state['transitions'][-1]
            if transport.is_transport_playing() and time.time()-state['phase_started']<8:return
            row['held_at']=frame
            assert not transport.is_transport_playing() and abs(frame-row['scene_end'])<=1,row
            state['test_index']=state.get('test_index',0)+1
            cue_next();return
        if state['status']=='shore':
            actors=unreal.GameplayStatics.get_all_actors_of_class(context['world'],unreal.Actor)
            shore=sorted([a for a in actors if a.get_actor_label().startswith('Shore') and a.get_actor_label().endswith(' Clam')],key=lambda a:a.get_actor_label())
            assert len(shore)==6
            poses=[]
            for actor in shore:
                body=next(c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()=='Body')
                cloth=actor.get_component_by_class(unreal.ChaosClothComponent)
                assert cloth.get_attach_parent()==body and str(cloth.get_attach_socket_name())=='head'
                poses.append({'label':actor.get_actor_label(),'head':list(body.get_socket_transform('head').translation.to_tuple()),'simulation':cloth.is_simulation_enabled()})
            if not state['samples'] or frame!=state['samples'][-1]['frame']:
                state['samples'].append({'frame':frame,'camera':current_camera(),'characters':poses})
            if frame>=state['shore_start']+120000:
                for i,actor in enumerate(shore):
                    positions=[s['characters'][i]['head'] for s in state['samples']]
                    extent=max(max(p[k] for p in positions)-min(p[k] for p in positions) for k in range(3))
                    assert extent>0.5,(actor.get_actor_label(),'stationary',extent)
                state['shore_camera']=current_camera()
                assert 'ClamCam' in (state['shore_camera']['label'] or ''),state['shore_camera']
                finish('passed')
    except Exception:
        state['errors'].append(traceback.format_exc());finish('failed')
    finally:state['inside']=False
builtins.PUSS_TRANSITION_QC_HANDLE=unreal.register_slate_post_tick_callback(tick)
persist();levels.editor_request_begin_play()
unreal.log('SCENE_TRANSITION_RUNTIME_STARTED')

