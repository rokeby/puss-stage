import unreal
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
out = {}
for a in sub.get_all_level_actors():
    if a.get_class().get_name() != "InfinityStageCameraRig": continue
    cam = a.get_editor_property("camera"); s = cam.get_editor_property("post_process_settings")
    out[a.get_actor_label()[:10]] = {"pp_blend": float(cam.get_editor_property("post_process_blend_weight")),
        "ov_method": bool(s.get_editor_property("override_auto_exposure_method")), "method": str(s.get_editor_property("auto_exposure_method")),
        "ov_min": bool(s.get_editor_property("override_auto_exposure_min_brightness")), "min": float(s.get_editor_property("auto_exposure_min_brightness")),
        "ov_max": bool(s.get_editor_property("override_auto_exposure_max_brightness")), "max": float(s.get_editor_property("auto_exposure_max_brightness")),
        "ov_bias": bool(s.get_editor_property("override_auto_exposure_bias")), "bias": float(s.get_editor_property("auto_exposure_bias")),
        "ov_phys": bool(s.get_editor_property("override_auto_exposure_apply_physical_camera_exposure")), "phys": bool(s.get_editor_property("auto_exposure_apply_physical_camera_exposure")),
        "ov_iso": bool(s.get_editor_property("override_camera_iso")), "iso": float(s.get_editor_property("camera_iso")),
        "ov_shutter": bool(s.get_editor_property("override_camera_shutter_speed")), "shutter": float(s.get_editor_property("camera_shutter_speed")),
        "fstop": float(cam.get_editor_property("current_aperture"))}
unreal.log("PUSS_CAM_PP|" + str(out))
