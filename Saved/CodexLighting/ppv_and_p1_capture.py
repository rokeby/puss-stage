"""Read-only PPV/exposure details; then move the level viewport to the Passage 1 camera rig's viewpoint and capture."""
import json, os
import unreal
def props(o, names):
    out = {}
    for n in names:
        try:
            v = o.get_editor_property(n); out[n] = v if isinstance(v, (int, float, bool, str)) else str(v)
        except Exception: pass
    return out
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
res = {"ppv": [], "rigs": []}
for a in sub.get_all_level_actors():
    cls = a.get_class().get_name()
    if cls == "PostProcessVolume":
        s = a.get_editor_property("settings")
        rec = {"label": a.get_actor_label(), "location": str(a.get_actor_location()), "bounds": str(a.get_actor_bounds(False)),
               "unbound": bool(a.get_editor_property("unbound")), "enabled": bool(a.get_editor_property("enabled")),
               "priority": float(a.get_editor_property("priority")), "blend_weight": float(a.get_editor_property("blend_weight"))}
        rec["exposure"] = props(s, ["override_auto_exposure_method", "auto_exposure_method", "override_auto_exposure_bias", "auto_exposure_bias",
                                    "override_auto_exposure_min_brightness", "auto_exposure_min_brightness", "override_auto_exposure_max_brightness",
                                    "auto_exposure_max_brightness", "override_auto_exposure_apply_physical_camera_exposure", "auto_exposure_apply_physical_camera_exposure"])
        res["ppv"].append(rec)
    if cls == "InfinityStageCameraRig":
        res["rigs"].append({"label": a.get_actor_label(), "loc": str(a.get_actor_location()), "rot": str(a.get_actor_rotation())})
p1 = [a for a in sub.get_all_level_actors() if a.get_class().get_name() == "InfinityStageCameraRig" and a.get_actor_label().startswith("Passage 01")]
if p1:
    cam = p1[0].get_editor_property("camera") if True else None
    loc, rot = p1[0].get_actor_location(), p1[0].get_actor_rotation()
    try:
        loc, rot = cam.get_world_location(), cam.get_world_rotation()
    except Exception: pass
    unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(loc, rot)
    res["viewport_set_to"] = {"loc": str(loc), "rot": str(rot)}
    unreal.AutomationLibrary.take_high_res_screenshot(1920, 1080, "NightLighting_P1CameraView")
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting", "ppv_capture.json")
with open(out, "w", encoding="utf-8") as fh: json.dump(res, fh, indent=1, default=str)
unreal.log(f"PUSS_PPV_CAPTURE_SUCCESS|ppv={len(res['ppv'])}|rigs={len(res['rigs'])}|p1={'yes' if p1 else 'no'}")
