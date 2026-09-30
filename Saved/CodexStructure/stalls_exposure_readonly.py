"""Read-only, one line per stalls camera: its lens and any exposure it overrides (camera
post-process beats the unbound PPV at EV100 -3). For the mouth lanterns' intensity.
Mutates nothing."""
import unreal


def main():
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for a in sub.get_all_level_actors():
        if not isinstance(a, unreal.CineCameraActor) or "Stalls Camera" not in a.get_actor_label():
            continue
        c = a.get_cine_camera_component()
        fb = c.get_editor_property("filmback")
        st = c.get_editor_property("post_process_settings")
        w = c.get_editor_property("post_process_blend_weight")
        ev = {k: st.get_editor_property(k) for k in ("auto_exposure_method", "auto_exposure_min_brightness", "auto_exposure_max_brightness",
                                                      "auto_exposure_bias", "camera_iso", "camera_shutter_speed")}
        ov = {k: bool(st.get_editor_property("override_" + k)) for k in ("auto_exposure_method", "auto_exposure_min_brightness",
                                                                          "auto_exposure_max_brightness", "auto_exposure_bias",
                                                                          "camera_iso", "camera_shutter_speed")}
        used = {k: str(v) for k, v in ev.items() if ov[k]}
        tags = [str(t) for t in a.get_editor_property("tags")]
        unreal.log(f"STALLS|{a.get_actor_label()}|focal={c.get_editor_property('current_focal_length'):.1f}|aperture={c.get_editor_property('current_aperture'):.1f}"
                   f"|sensor={fb.get_editor_property('sensor_width'):.2f}x{fb.get_editor_property('sensor_height'):.2f}|pp_weight={w}|overrides={used}|tags={tags}")


main()
