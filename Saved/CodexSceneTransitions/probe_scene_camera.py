import builtins,json,pathlib,time,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None
out={'api':[n for n in dir(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)) if 'play' in n.lower() or 'simul' in n.lower()]}
folder=pathlib.Path('E:/PussStage/Saved/CodexSceneTransitions')
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
unreal.LevelSequenceEditorBlueprintLibrary.pause()
unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
levels.eject_pilot_level_actor()
prefs=unreal.load_object(None,'/Script/UnrealEd.Default__EditorPerformanceSettings')
throttle=prefs.get_editor_property('bThrottleCPUWhenNotForeground');prefs.set_editor_property('bThrottleCPUWhenNotForeground',False)
def tick(delta):
    w=ed.get_game_world()
    if not w:return
    if 'first' not in out:
        root=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.InfinityStageShowRoot)[0]
        t=root.transport;pc=unreal.GameplayStatics.get_player_controller(w,0)
        unreal.SystemLibrary.execute_console_command(w,'Log LogTemp Verbose',pc)
        out['manage_before']=str(pc.get_editor_property('auto_manage_active_camera_target'))
        t.set_editor_property('performance_mode',False)
        t.scrub_to_master_frame(t.segments[2].start_frame)
        out['after_scrub']=pc.get_view_target().get_path_name()
        t.play_forward_to_boundary()
        out['active_camera']=str(root.sequence_player.get_active_camera_component())
        out['first']=time.time();out['initial']=pc.get_view_target().get_path_name();return
    if time.time()-out['first']<2:return
    root=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.InfinityStageShowRoot)[0]
    pc=unreal.GameplayStatics.get_player_controller(w,0)
    out['view']=pc.get_view_target().get_path_name();out['frame']=root.transport.get_current_master_frame().value
    out['active_after']=str(root.sequence_player.get_active_camera_component())
    out['player_time']=root.sequence_player.get_current_time().export_text()
    out['master_rates']={'display':root.master_sequence.get_display_rate().export_text(),'tick':root.master_sequence.get_tick_resolution().export_text(),'show_display':root.show_asset.display_rate.export_text(),'show_tick':root.show_asset.tick_resolution.export_text()}
    out['disable_camera_cuts']=root.sequence_player.get_disable_camera_cuts()
    out['playback']=root.get_editor_property('playback_settings').export_text()
    seq=unreal.load_asset('/Game/InfinityStage/Dev/Sequences/LS_DevScene_01')
    out['sequence']=seq.get_path_name();out['bindings']=[]
    for b in seq.get_bindings():
        out['bindings'].append({'name':b.get_name(),'id':unreal.GuidLibrary.conv_guid_to_string(b.get_id()),'game_objects':[o.get_path_name() for o in seq.locate_bound_objects(b,w)],'editor_objects':[o.get_path_name() for o in seq.locate_bound_objects(b,ed.get_editor_world())]})
    out['track_methods']=[n for n in dir(seq.get_tracks()[0]) if 'eval' in n or 'enable' in n or 'disable' in n]
    out['player_methods']=[n for n in dir(root.sequence_player) if 'camera' in n]
    out['cuts']=[{'start':s.get_start_frame(),'end':s.get_end_frame(),'id':s.get_camera_binding_id().export_text(),'objects':[o.get_path_name() for o in root.sequence_player.get_bound_objects(s.get_camera_binding_id())]} for t in seq.get_tracks() if isinstance(t,unreal.MovieSceneCameraCutTrack) for s in t.get_sections()]
    out['cameras']=[{'path':a.get_path_name(),'tags':[str(s) for s in a.tags]} for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.CineCameraActor)]
    (folder/'scene_camera_probe.json').write_text(json.dumps(out,indent=2))
    prefs.set_editor_property('bThrottleCPUWhenNotForeground',throttle)
    levels.editor_request_end_play();unreal.unregister_slate_post_tick_callback(builtins.PUSS_SCENE_PROBE);del builtins.PUSS_SCENE_PROBE
    unreal.log('SCENE_CAMERA_PROBE_COMPLETE')
builtins.PUSS_SCENE_PROBE=unreal.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
