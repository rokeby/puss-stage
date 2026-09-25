import builtins,time,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_editor_world().get_path_name().startswith('/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.')
assert ed.get_game_world() is None
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
start=time.time()
def tick(delta):
    if time.time()-start<2:return
    unreal.unregister_slate_post_tick_callback(builtins.PUSS_OPENING_QUIT)
    del builtins.PUSS_OPENING_QUIT
    unreal.SystemLibrary.quit_editor()
builtins.PUSS_OPENING_QUIT=unreal.register_slate_post_tick_callback(tick)
unreal.log('OPENING_EDITOR_CLEAN_QUIT_SCHEDULED')
