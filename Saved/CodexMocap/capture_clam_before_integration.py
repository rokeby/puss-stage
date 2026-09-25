import builtins
import pathlib
import unreal
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
camera=next(a for a in actors if a.get_actor_label()=='ClamCam1')
seq=unreal.load_asset('/Game/Scenes/LS_Clams')
unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
unreal.LevelSequenceEditorBlueprintLibrary.pause()
builtins.PUSS_CLAM_BEFORE_TASK=unreal.AutomationLibrary.take_high_res_screenshot(2560,1440,'E:/PussStage/Saved/CodexMocap/Clam_Before_Shore_Cast.png',camera=camera,delay=1.0)
unreal.log('CLAM_BEFORE_INTEGRATION_CAPTURE_REQUESTED')
