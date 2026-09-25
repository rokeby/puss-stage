import unreal
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
p1 = [a for a in sub.get_all_level_actors() if a.get_class().get_name() == "InfinityStageCameraRig" and a.get_actor_label().startswith("Passage 01")][0]
cam = p1.get_editor_property("camera")
unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(cam.get_world_location(), cam.get_world_rotation())
unreal.AutomationLibrary.take_high_res_screenshot(1920, 1080, "NightLights_P1Camera_B")
unreal.log("PUSS_CAPTURE_REQUESTED|NightLights_P1Camera_B")
