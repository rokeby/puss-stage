import unreal
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert editor.get_game_world() is None
seq=unreal.load_asset('/Game/InfinityStage/Dev/Sequences/LS_DevScene_03')
assert unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
unreal.LevelSequenceEditorBlueprintLibrary.pause()
unreal.LevelSequenceEditorBlueprintLibrary.set_lock_camera_cut_to_viewport(True)
dirty=[p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
assert not dirty,dirty
unreal.log('SCENE_TRANSITION_DELIVERY_READY|scene=LS_DevScene_03|frame=0|pie=0|dirty=0')
