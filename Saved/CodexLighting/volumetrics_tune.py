"""Tune volumetric fog for a hazy corridor and capture the Passage 1 camera view. No save."""
import json, os, unreal
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world(); assert world, "no world"
assert world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
assert ed.get_game_world() is None, "PIE active"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
fog = [a for a in sub.get_all_level_actors() if a.get_class().get_name() == "ExponentialHeightFog" and a.get_actor_label().startswith("Infinity Stage")][0]
c = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
fog.modify()
c.set_editor_property("enable_volumetric_fog", True)
c.set_editor_property("fog_density", 0.035)              # 0.5 was opaque at distance
c.set_editor_property("volumetric_fog_distance", 30000.0) # restored: the corridor is long
c.set_editor_property("volumetric_fog_extinction_scale", 1.0)
c.set_editor_property("volumetric_fog_scattering_distribution", 0.55)  # forward scatter = beams
state = {k: c.get_editor_property(k) for k in ("enable_volumetric_fog","fog_density","volumetric_fog_distance","volumetric_fog_extinction_scale","volumetric_fog_scattering_distribution")}
# Frame the Passage 1 show camera
p1 = [a for a in sub.get_all_level_actors() if a.get_class().get_name() == "InfinityStageCameraRig" and a.get_actor_label().startswith("Passage 01")][0]
cam = p1.get_editor_property("camera")
ed.set_level_viewport_camera_info(cam.get_world_location(), cam.get_world_rotation())
unreal.AutomationLibrary.take_high_res_screenshot(1920, 1080, "Volumetrics_P1")
d = {"content": [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
     "maps": [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
json.dump({"state": state, "dirty": d}, open(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting", "volumetrics_tune.json"), "w"), indent=1, default=str)
unreal.log(f"VOLUMETRICS_TUNED|{state}|dirty_content={len(d['content'])}|dirty_maps={len(d['maps'])}|saved=0")
