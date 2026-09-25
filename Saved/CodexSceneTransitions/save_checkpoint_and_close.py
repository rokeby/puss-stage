import json
import pathlib
import time
import unreal

folder=pathlib.Path('E:/PussStage/Saved/CodexSceneTransitions')
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert editor.get_game_world() is None
world=editor.get_editor_world()
assert world.get_path_name().startswith('/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.')
expected={'/Game/InfinityStage/Dev/DA_InfinityStage_V1Show','/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master'}
dirty=list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
assert {p.get_path_name() for p in dirty}.issubset(expected)
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
for package in dirty:
    assert unreal.EditorAssetLibrary.save_asset(package.get_path_name(),False)
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
(folder/'restart_checkpoint.json').write_text(json.dumps({'saved':[p.get_path_name() for p in dirty],'utc':time.time(),'world':world.get_path_name()},indent=2),encoding='utf-8')
unreal.log('SCENE_TRANSITION_RESTART_CHECKPOINT_SAVED|dirty=0')
deadline=time.monotonic()+3
def quit_after_response(delta):
    if time.monotonic()<deadline:return
    unreal.unregister_slate_post_tick_callback(handle)
    unreal.SystemLibrary.quit_editor()
handle=unreal.register_slate_post_tick_callback(quit_after_response)
