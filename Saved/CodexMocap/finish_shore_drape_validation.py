import builtins
import json
import pathlib
import unreal
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
assert not hasattr(builtins,'PUSS_CLAM_SHORE_RUNTIME_HANDLE')
assert not hasattr(builtins,'PUSS_CLAM_SHORE_QC_HANDLE')
runtime=json.loads((folder/'shore_clam_runtime_qc.json').read_text(encoding='utf-8'))
assert runtime['status']=='passed' and not runtime['errors']
settings=unreal.get_default_object(unreal.load_class(None,'/Script/UnrealEd.EditorPerformanceSettings'))
original=json.loads((folder/'shore_simulation_temporary_settings.json').read_text(encoding='utf-8'))['throttle_cpu_when_not_foreground_original']
settings.set_editor_property('bThrottleCPUWhenNotForeground',original)
assert settings.get_editor_property('bThrottleCPUWhenNotForeground')==original
(folder/'shore_simulation_temporary_settings.json').write_text(json.dumps({'throttle_cpu_when_not_foreground_original':original,'restored':True,'saved_to_config':False},indent=2),encoding='utf-8')
dirty=list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
assert not dirty,[p.get_path_name() for p in dirty]
unreal.log('SHORE_DRAPE_DELIVERY_COMPLETE|runtime_passed_after_reload|six_moving_bodies|no_detached_cloth|background_throttle_restored|zero_dirty_packages')
