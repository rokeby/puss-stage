"""Pin the show's exposure: min == max EV100 on the unbound PostProcessVolume (no save). Edit EV100 below to retune."""
import unreal
EV100 = -3.0
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
ppvs = [a for a in sub.get_all_level_actors() if a.get_class().get_name() == "PostProcessVolume"]
assert len(ppvs) == 1, f"expected one PPV, found {len(ppvs)}"
ppv = ppvs[0]; s = ppv.get_editor_property("settings")
ppv.modify(); ppv.set_editor_property("unbound", True)
s.set_editor_property("override_auto_exposure_method", True); s.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM)
s.set_editor_property("override_auto_exposure_min_brightness", True); s.set_editor_property("auto_exposure_min_brightness", EV100)
s.set_editor_property("override_auto_exposure_max_brightness", True); s.set_editor_property("auto_exposure_max_brightness", EV100)
s.set_editor_property("override_auto_exposure_bias", True); s.set_editor_property("auto_exposure_bias", 0.0)
s.set_editor_property("override_auto_exposure_apply_physical_camera_exposure", True); s.set_editor_property("auto_exposure_apply_physical_camera_exposure", False)
ppv.set_editor_property("settings", s)
s2 = ppv.get_editor_property("settings")
unreal.log(f"FIXED_EXPOSURE_SET|ev100={s2.get_editor_property('auto_exposure_min_brightness')}..{s2.get_editor_property('auto_exposure_max_brightness')}|bias={s2.get_editor_property('auto_exposure_bias')}|unbound={ppv.get_editor_property('unbound')}|saved=0")
