import builtins,json,pathlib,time,traceback,unreal
folder=pathlib.Path('E:/PussStage/Saved/CodexSceneTransitions')
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert editor.get_game_world() is None
assert not hasattr(builtins,'PUSS_OPENING_PROBE')
settings=unreal.load_object(None,'/Script/UnrealEd.Default__EditorPerformanceSettings')
throttle=settings.get_editor_property('bThrottleCPUWhenNotForeground')
settings.set_editor_property('bThrottleCPUWhenNotForeground',False)
state={'started':time.time(),'samples':[],'status':'starting'}
builtins.PUSS_OPENING_PROBE_STATE=state
def tick(delta):
    try:
        w=editor.get_game_world()
        if not w:
            if time.time()-state['started']<30:return
            raise RuntimeError('No PIE world')
        roots=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.InfinityStageShowRoot)
        if not roots or not roots[0].sequence_player:return
        if 'live_started' not in state:state['live_started']=time.time()
        elapsed=time.time()-state['live_started']
        if elapsed < len(state['samples'])*2+0.5:return
        r=roots[0];t=r.transport;pc=unreal.GameplayStatics.get_player_controller(w,0)
        row={'elapsed':elapsed,'frame':t.get_current_master_frame().value,'playing':t.is_transport_playing(),'view':pc.get_view_target().get_path_name(),'controller':pc.get_class().get_name(),'paused':unreal.GameplayStatics.is_game_paused(w),'curtains':[]}
        for c in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.InfinityStageCurtainRig):
            row['curtains'].append({'path':c.get_path_name(),'progress':c.curtain_progress,'active':c.curtain_active,'distance':c.curtain_distance_cm,'motion':c.curtain_motion_root.get_relative_transform().export_text(),'transform':c.get_actor_transform().export_text()})
        state['samples'].append(row)
        if len(state['samples'])==2:unreal.SystemLibrary.execute_console_command(w,'HighResShot 1280x720 filename="E:/PussStage/Saved/CodexSceneTransitions/Opening_Before.png"',pc)
        if len(state['samples'])<4:
            (folder/'opening_probe.json').write_text(json.dumps(state,indent=2));return
        state['status']='complete'
    except Exception:
        state['status']='error';state['error']=traceback.format_exc()
    settings.set_editor_property('bThrottleCPUWhenNotForeground',throttle)
    levels.editor_request_end_play()
    unreal.unregister_slate_post_tick_callback(builtins.PUSS_OPENING_PROBE)
    del builtins.PUSS_OPENING_PROBE
    (folder/'opening_probe.json').write_text(json.dumps(state,indent=2))
    unreal.log('OPENING_PROBE_'+state['status'].upper())
builtins.PUSS_OPENING_PROBE=unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
unreal.log('OPENING_PROBE_STARTED')
