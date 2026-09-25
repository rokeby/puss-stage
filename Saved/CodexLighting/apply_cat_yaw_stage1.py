"""STAGE 1 (no save): yaw the shadow cat -90 on every camera rig (vendor mesh faces +Y), align P6's cat
placement to P2-P5, re-evaluate placement, and capture a side view of the P1 cat."""
import json, os
import unreal
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting")
def vec(v): return [round(v.x,2), round(v.y,2), round(v.z,2)]
def rot(r): return [round(r.pitch,3), round(r.yaw,3), round(r.roll,3)]
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None, "PIE active"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
before, after = {}, {}
p1 = None
for a in sub.get_all_level_actors():
    if a.get_class().get_name() != "InfinityStageCameraRig": continue
    label = a.get_actor_label()
    before[label] = {"rot_off": rot(a.get_editor_property("shadow_cat_rotation_offset")), "pos_off": vec(a.get_editor_property("shadow_cat_position_offset")),
                     "scale": float(a.get_editor_property("shadow_cat_uniform_scale"))}
    a.modify()
    a.set_editor_property("shadow_cat_rotation_offset", unreal.Rotator(roll=0.0, pitch=0.0, yaw=-90.0))
    if label.startswith("Passage 06"):
        a.set_editor_property("shadow_cat_uniform_scale", 7.0)
        a.set_editor_property("shadow_cat_position_offset", unreal.Vector(0.0, 0.0, -175.88))
    a.configure_shadow_cat() if hasattr(a, "configure_shadow_cat") else None
    # re-run construction so BuildShadowCatRelativeTransform is applied
    a.set_actor_transform(a.get_actor_transform(), False, False)
    after[label] = {"rot_off": rot(a.get_editor_property("shadow_cat_rotation_offset")), "pos_off": vec(a.get_editor_property("shadow_cat_position_offset")),
                    "scale": float(a.get_editor_property("shadow_cat_uniform_scale"))}
    cat = a.get_editor_property("shadow_cat").get_editor_property("child_actor") if a.get_editor_property("shadow_cat") else None
    after[label]["cat_world_rot"] = rot(cat.get_actor_rotation()) if cat else None
    after[label]["cat_comp_rel_rot"] = rot(a.get_editor_property("shadow_cat").get_editor_property("relative_rotation"))
    if label.startswith("Passage 01"): p1 = a
with open(os.path.join(OUT, "apply_cat_yaw_result.json"), "w", encoding="utf-8") as fh:
    json.dump({"status": "ok", "saved": False, "before": before, "after": after}, fh, indent=1)
if p1:
    cat = p1.get_editor_property("shadow_cat").get_editor_property("child_actor")
    target = cat.get_actor_location() if cat else p1.get_actor_location()
    eye = target + unreal.Vector(-350.0, 520.0, 160.0)
    look = unreal.MathLibrary.find_look_at_rotation(eye, target + unreal.Vector(0, 0, 60))
    ed.set_level_viewport_camera_info(eye, look)
    unreal.AutomationLibrary.take_high_res_screenshot(1920, 1080, "ShadowCat_Yaw_SideView")
ok = all(v["cat_comp_rel_rot"][1] == -90.0 for v in after.values())
unreal.log(f"SHADOW_CAT_YAW_STAGE1_{'SUCCESS' if ok else 'PROBLEMS'}|rigs={len(after)}|comp_yaw={[v['cat_comp_rel_rot'][1] for v in after.values()]}|saved=0")
