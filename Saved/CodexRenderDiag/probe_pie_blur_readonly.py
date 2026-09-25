"""Read-only: why PIE looks softer than the editor viewport. Dumps every camera rig's lens/DoF/motion-blur
state, the PostProcessVolume overrides, the Master sequence's Focus Distance keys, and the render CVars
that govern resolution, AA, DoF, motion blur and texture streaming. Writes nothing to assets."""
import json, os
import unreal
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexRenderDiag", "pie_blur_probe.json")
def g(o, n):
    try: return o.get_editor_property(n)
    except Exception as e: return f"ERR {type(e).__name__}"
def pp(s, names):
    return {n: (bool(g(s, "override_" + n)), str(g(s, n))) for n in names}
PP = ["depth_of_field_fstop", "depth_of_field_focal_distance", "depth_of_field_min_fstop", "depth_of_field_blade_count",
      "depth_of_field_depth_blur_amount", "depth_of_field_depth_blur_radius", "depth_of_field_sensor_width",
      "motion_blur_amount", "motion_blur_max", "motion_blur_per_object_size", "motion_blur_target_fps",
      "screen_percentage_mode_desktop", "screen_percentage_mode_mobile", "bloom_intensity", "sharpen"]
rep = {"rigs": {}, "ppv": {}, "cvars": {}, "sequence_focus": {}}
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for a in sub.get_all_level_actors():
    cls = a.get_class().get_name()
    if cls == "InfinityStageCameraRig":
        cam = a.get_editor_property("camera"); fs = g(cam, "focus_settings")
        rep["rigs"][a.get_actor_label()] = {
            "fstop": g(cam, "current_aperture"), "focal_length_mm": g(cam, "current_focal_length"),
            "focus_method": str(g(fs, "focus_method")), "manual_focus_distance_cm": g(fs, "manual_focus_distance"),
            "smooth_focus": g(fs, "smooth_focus_changes"), "sensor_w": g(g(cam, "filmback"), "sensor_width"),
            "lens_min_fstop": g(g(cam, "lens_settings"), "min_f_stop"), "pp_blend": g(cam, "post_process_blend_weight"),
            "pp": pp(g(cam, "post_process_settings"), PP)}
    elif cls == "PostProcessVolume":
        rep["ppv"][a.get_actor_label()] = {"unbound": g(a, "unbound"), "enabled": g(a, "enabled"), "blend_weight": g(a, "blend_weight"),
                                          "priority": g(a, "priority"), "pp": pp(g(a, "settings"), PP)}
# Focus Distance keys on every Passage track section of the Master sequence
try:
    seq = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master")
    for tr in seq.get_tracks():
        if "Passage" not in tr.get_class().get_name(): continue
        for sec in tr.get_sections():
            row = {}
            try:
                for ch in sec.get_all_channels():
                    name = str(g(ch, "channel_name"))
                    if "Focus" in name or "FocalLength" in name:
                        keys = ch.get_keys()
                        row[name] = {"default": str(g(ch, "default")), "keys": [(str(k.get_time().frame_number.value), k.get_value()) for k in keys[:8]], "num_keys": len(keys)}
            except Exception as e:
                row["error"] = repr(e)
            rep["sequence_focus"][sec.get_name()] = row
except Exception as e:
    rep["sequence_focus"]["error"] = repr(e)
CV_F = ["r.ScreenPercentage", "r.SecondaryScreenPercentage.GameViewport", "r.MipMapLODBias", "r.Streaming.MipBias", "r.MotionBlur.Max", "r.MotionBlur.Amount", "r.Tonemapper.Sharpen"]
CV_I = ["r.AntiAliasingMethod", "r.TemporalAA.Upsampling", "r.TSR.History.ScreenPercentage", "r.MotionBlurQuality", "r.DefaultFeature.MotionBlur",
        "r.DepthOfFieldQuality", "r.DOF.Gather.RingCount", "r.Streaming.PoolSize", "r.Streaming.LimitPoolSizeToVRAM", "r.Streaming.FullyLoadUsedTextures",
        "sg.ResolutionQuality", "sg.AntiAliasingQuality", "sg.PostProcessQuality", "sg.TextureQuality", "sg.EffectsQuality", "sg.ShadowQuality", "sg.GlobalIlluminationQuality", "sg.ReflectionQuality",
        "r.Shadow.Virtual.OnePassProjection.MaxLightsPerPixel", "r.Upscale.Quality", "r.Lumen.Reflections.Allow", "r.VolumetricFog", "r.Nanite"]
for n in CV_F:
    try: rep["cvars"][n] = unreal.SystemLibrary.get_console_variable_float_value(n)
    except Exception as e: rep["cvars"][n] = repr(e)
for n in CV_I:
    try: rep["cvars"][n] = unreal.SystemLibrary.get_console_variable_int_value(n)
    except Exception as e: rep["cvars"][n] = repr(e)
json.dump(rep, open(OUT, "w", encoding="utf-8"), indent=1, default=str)
unreal.log(f"PUSS_PIE_BLUR_PROBE_SUCCESS|rigs={len(rep['rigs'])}|ppv={len(rep['ppv'])}|sections={len(rep['sequence_focus'])}")
