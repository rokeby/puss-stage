import builtins
import unreal
assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
assert not hasattr(builtins,'PUSS_CLAM_SHORE_QC_HANDLE')
unreal.LevelSequenceEditorBlueprintLibrary.pause()
unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(300)
camera=next(a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if a.get_actor_label()=='Shore Cast Review Camera')
builtins.PUSS_SHORE_REVIEW_CAMERA_RESTORE=(camera.get_actor_transform(),camera.get_cine_camera_component().get_editor_property('current_focal_length'))
position=unreal.Vector(13350,159360,110)
rotation=unreal.MathLibrary.find_look_at_rotation(position,unreal.Vector(13490,159780,95))
camera.set_actor_location_and_rotation(position,rotation,False,True)
camera.get_cine_camera_component().set_editor_property('current_focal_length',50.0)
builtins.PUSS_SHORE_CLOSEUP_TASK=unreal.AutomationLibrary.take_high_res_screenshot(1920,1080,'E:/PussStage/Saved/CodexMocap/Shore_Cloth_Corrected_Closeup.png',camera=camera,delay=3.0)
unreal.log('SHORE_CORRECTED_CLOTH_CLOSEUP_REQUESTED|camera_restore_required')
