"""Read-only probe for Gary's "blur only while moving" (P02 and other passages, not P01).

Reads, and changes nothing:
  - every PostProcessVolume: enabled, unbound, priority, blend weight, and the motion-blur,
    DoF and screen-percentage overrides and values;
  - every camera component in the level (camera rigs, cine cameras): its own
    post-process overrides for the same fields, blend weight, focus, aperture, focal length;
  - console variables for screen percentage, anti-aliasing / TSR, motion blur and velocity.
Writes motion_blur_probe.json. Settings are Rig's and Look & camera's; this only reports them.
"""
import importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)

PP_FIELDS = [
    "override_motion_blur_amount", "motion_blur_amount", "override_motion_blur_max", "motion_blur_max",
    "override_motion_blur_per_object_size", "motion_blur_per_object_size",
    "override_motion_blur_target_fps", "motion_blur_target_fps",
    "override_depth_of_field_fstop", "depth_of_field_fstop",
    "override_depth_of_field_focal_distance", "depth_of_field_focal_distance",
    "override_screen_percentage", "screen_percentage",
]
CVARS = [
    "r.ScreenPercentage", "r.ScreenPercentage.Default", "r.ScreenPercentage.Mode",
    "r.SecondaryScreenPercentage.GameViewport", "r.DynamicRes.OperationMode",
    "r.AntiAliasingMethod", "r.TemporalAA.Upsampling", "r.TSR.History.ScreenPercentage",
    "r.TSR.History.UpdateQuality", "r.TSR.ShadingRejection.Flickering",
    "r.MotionBlurQuality", "r.MotionBlur.Amount", "r.MotionBlur.Max", "r.MotionBlur.TargetFPS",
    "r.DefaultFeature.MotionBlur", "r.DefaultFeature.AntiAliasing",
    "r.VelocityOutputPass", "r.Velocity.EnableVertexDeformation", "r.BasePassOutputsVelocity",
]


def pp_fields(settings):
    out = {}
    for f in PP_FIELDS:
        try:
            v = settings.get_editor_property(f)
            out[f] = v if isinstance(v, (bool, int, float)) else str(v)
        except Exception:  # noqa: BLE001
            pass
    return out


wm.editor_ready()
before = wm.dirty()
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
out = {"volumes": [], "cameras": [], "cvars": {}}
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if isinstance(a, unreal.PostProcessVolume):
        rec = {"label": a.get_actor_label()}
        for p in ("enabled", "unbound", "priority", "blend_weight", "blend_radius"):
            try:
                v = a.get_editor_property(p)
                rec[p] = v if isinstance(v, (bool, int, float)) else str(v)
            except Exception:  # noqa: BLE001
                pass
        rec.update(pp_fields(a.get_editor_property("settings")))
        out["volumes"].append(rec)
    for cam in a.get_components_by_class(unreal.CameraComponent):
        rec = {"actor": a.get_actor_label(), "component": cam.get_name(), "class": cam.get_class().get_name()}
        for p in ("post_process_blend_weight", "field_of_view"):
            try:
                rec[p] = cam.get_editor_property(p)
            except Exception:  # noqa: BLE001
                pass
        if isinstance(cam, unreal.CineCameraComponent):
            for p in ("current_aperture", "current_focal_length"):
                try:
                    rec[p] = cam.get_editor_property(p)
                except Exception:  # noqa: BLE001
                    pass
            try:
                fs = cam.get_editor_property("focus_settings")
                rec["focus_method"] = str(fs.get_editor_property("focus_method"))
                rec["manual_focus_cm"] = fs.get_editor_property("manual_focus_distance")
            except Exception:  # noqa: BLE001
                pass
        rec.update(pp_fields(cam.get_editor_property("post_process_settings")))
        out["cameras"].append(rec)
for cv in CVARS:
    try:
        out["cvars"][cv] = unreal.SystemLibrary.get_console_variable_float_value(cv)
    except Exception as exc:  # noqa: BLE001
        out["cvars"][cv] = f"ERR {exc!r}"[:60]
wm.require(wm.dirty() == before, "probe changed the dirty set")
wm.write_json("motion_blur_probe.json", out)
unreal.log(f"PUSS_WING_MOTIONBLUR_PROBE_SUCCESS|volumes={len(out['volumes'])}|cameras={len(out['cameras'])}")
