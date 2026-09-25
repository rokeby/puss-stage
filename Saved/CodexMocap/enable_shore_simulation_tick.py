import builtins
import json
import pathlib
import unreal
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
settings=unreal.get_default_object(unreal.load_class(None,'/Script/UnrealEd.EditorPerformanceSettings'))
old=settings.get_editor_property('bThrottleCPUWhenNotForeground')
if not hasattr(builtins,'PUSS_SHORE_BACKGROUND_THROTTLE_ORIGINAL'):
    builtins.PUSS_SHORE_BACKGROUND_THROTTLE_ORIGINAL=old
    (folder/'shore_simulation_temporary_settings.json').write_text(json.dumps({'throttle_cpu_when_not_foreground_original':old,'restore_when_validation_finishes':True}),encoding='utf-8')
settings.set_editor_property('bThrottleCPUWhenNotForeground',False)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_set_viewport_realtime(True)
unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(300)
unreal.LevelSequenceEditorBlueprintLibrary.play()
unreal.log('SHORE_BACKGROUND_SIMULATION_TICK_ENABLED|previous='+str(old))
