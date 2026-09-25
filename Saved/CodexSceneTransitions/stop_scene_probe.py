import builtins,unreal
if hasattr(builtins,'PUSS_SCENE_PROBE'):
    unreal.unregister_slate_post_tick_callback(builtins.PUSS_SCENE_PROBE)
    del builtins.PUSS_SCENE_PROBE
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
if w:
    r=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.InfinityStageShowRoot)[0]
    unreal.log('SCENE_PROBE_DISABLED_CUTS='+str(r.sequence_player.get_disable_camera_cuts()))
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
unreal.log('SCENE_PROBE_STOPPED')
