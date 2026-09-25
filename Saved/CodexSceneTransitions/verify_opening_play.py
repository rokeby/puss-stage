import builtins,json,pathlib,time,traceback,unreal
folder=pathlib.Path('E:/PussStage/Saved/CodexSceneTransitions')
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert editor.get_game_world() is None
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert not hasattr(builtins,'PUSS_OPENING_VERIFY')
settings=unreal.load_object(None,'/Script/UnrealEd.Default__EditorPerformanceSettings')
throttle=settings.get_editor_property('bThrottleCPUWhenNotForeground')
settings.set_editor_property('bThrottleCPUWhenNotForeground',False)
state={'started':time.time(),'status':'starting','samples':[],'renders':[],'errors':[]};ctx={}
def persist():(folder/'opening_verification.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
def capture(name):
    target=ctx['pc'].get_view_target();filename=folder/(name+'.png')
    unreal.SystemLibrary.execute_console_command(ctx['world'],'HighResShot 1280x720 filename="'+filename.as_posix()+'"',ctx['pc'])
    state['renders'].append({'file':str(filename),'view':target.get_actor_label(),'frame':ctx['transport'].get_current_master_frame().value})
def finish(status):
    state['status']=status;persist()
    settings.set_editor_property('bThrottleCPUWhenNotForeground',throttle)
    levels.editor_request_end_play()
    unreal.unregister_slate_post_tick_callback(builtins.PUSS_OPENING_VERIFY)
    del builtins.PUSS_OPENING_VERIFY
    unreal.log('OPENING_PLAYBACK_'+status.upper())
def tick(delta):
    if state.get('inside'):return
    state['inside']=True
    try:
        if time.time()-state['started']>90:raise RuntimeError('Opening test timed out')
        w=editor.get_game_world()
        if not w:return
        if state['status']=='starting':
            roots=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.InfinityStageShowRoot)
            if not roots or not roots[0].sequence_player:return
            root=roots[0];t=root.transport;pc=unreal.GameplayStatics.get_player_controller(w,0)
            assert pc.get_class().get_name()=='InfinityStageShowPlayerController'
            assert t.is_transport_playing()
            assert t.get_current_master_frame().value<24000,'PIE did not start at opening'
            ctx.update(world=w,root=root,transport=t,pc=pc,passage=t.segments[1],scene=t.segments[2])
            ctx['camera']=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.InfinityStageCameraRig) if a.passage_actor and unreal.GuidLibrary.conv_guid_to_string(a.passage_actor.passage_guid)==unreal.GuidLibrary.conv_guid_to_string(ctx['passage'].segment_guid))
            state['status']='opening';state['last_sample']=-1
        t=ctx['transport'];pc=ctx['pc'];frame=t.get_current_master_frame().value
        seconds=frame/24000.0
        if state['status']=='opening':
            assert pc.get_view_target()==ctx['camera'],str(pc.get_view_target())
            if int(seconds)!=state['last_sample']:
                curtains=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.InfinityStageCurtainRig)
                row={'seconds':seconds,'frame':frame,'playing':t.is_transport_playing(),'camera':pc.get_view_target().get_actor_label(),'curtains':[{'progress':c.curtain_progress,'distance':c.curtain_distance_cm,'transform':c.get_actor_transform().export_text()} for c in curtains]}
                state['samples'].append(row);state['last_sample']=int(seconds);persist()
            if seconds>0.5 and not state.get('closed'):
                c=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.InfinityStageCurtainRig)[0]
                assert abs(c.curtain_progress-1)<0.001 and c.curtain_distance_cm==100
                capture('Opening_Closed_After');state['closed']=True
            if seconds>3.9 and not state.get('rising'):
                c=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.InfinityStageCurtainRig)[0]
                assert 0<c.curtain_progress<1
                capture('Opening_Rising_After');state['rising']=True
            if seconds>7 and not state.get('open'):
                c=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.InfinityStageCurtainRig)[0]
                assert abs(c.curtain_progress)<0.001
                capture('Opening_Revealed_After');state['open']=True
            if not t.is_transport_playing():
                assert abs(frame-ctx['passage'].start_frame.value)<=1
                assert not unreal.GameplayStatics.get_all_actors_of_class(w,unreal.InfinityStageCurtainRig),'Opening curtain persisted into Passage 1'
                state['held_frame']=frame;state['held_time']=time.time();state['status']='hold';persist()
        elif state['status']=='hold' and time.time()-state['held_time']>2:
            assert t.get_current_master_frame().value==state['held_frame'] and not t.is_transport_playing()
            pc.toggle_show_playback();assert t.is_transport_playing()
            state['status']='go';state['go_time']=time.time()
        elif state['status']=='go' and time.time()-state['go_time']>2:
            assert frame>state['held_frame']+24000
            state['go_frame']=frame
            pc.advance_show_segment()
            assert t.get_current_master_frame().value==ctx['scene'].start_frame.value and t.is_transport_playing()
            state['advance_immediate_view']={'path':pc.get_view_target().get_path_name(),'class':pc.get_view_target().get_class().get_name(),'label':pc.get_view_target().get_actor_label()}
            state['right_arrow_scene_frame']=t.get_current_master_frame().value
            state['status']='settle';state['settle_time']=time.time();persist()
        elif state['status']=='settle' and time.time()-state['settle_time']>2:
            state['advance_settled_view']={'path':pc.get_view_target().get_path_name(),'class':pc.get_view_target().get_class().get_name(),'label':pc.get_view_target().get_actor_label()}
            assert pc.get_view_target()!=ctx['camera'] and pc.get_view_target().get_component_by_class(unreal.CameraComponent),state['advance_settled_view']
            assert all(pathlib.Path(r['file']).is_file() for r in state['renders'])
            finish('passed')
    except Exception:state['errors'].append(traceback.format_exc());finish('failed')
    finally:state['inside']=False
builtins.PUSS_OPENING_VERIFY=unreal.register_slate_post_tick_callback(tick)
persist();levels.editor_request_begin_play()
unreal.log('OPENING_PLAYBACK_STARTED')
