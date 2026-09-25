"""STAGE 1 (no save): freeze the celestial rig at midnight for editor and PIE, disable per-Passage
day/night animation, and give the Moon forward-shading priority. Records before-state."""
import json, os
import unreal
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting")
def require(c, m):
    if not c: raise RuntimeError(m)
def pkg(v): return v.get_path_name().split(".", 1)[0] if v is not None and hasattr(v, "get_path_name") else None
def dirty():
    return {"content": sorted({pkg(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}),
            "maps": sorted({pkg(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()})}
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem); world = ed.get_editor_world()
require(world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "Unexpected world")
require(ed.get_game_world() is None, "PIE active")
backup = open(os.path.join(OUT, "backup_folder.txt"), encoding="utf-8").read().strip()
require(os.path.isfile(os.path.join(unreal.Paths.project_dir(), backup, "DA_InfinityStage_V1Show.uasset")), "backup missing")
d0 = dirty(); require(not d0["content"] and not d0["maps"], f"Dirty before mutation: {d0}")
before = {}
# 1. Celestial rig
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
rigs = [a for a in sub.get_all_level_actors() if a.get_class().get_name() == "InfinityStageCelestialRig"]
require(len(rigs) == 1, f"Expected one celestial rig, found {len(rigs)}")
rig = rigs[0]
before["rig"] = {n: rig.get_editor_property(n) for n in ("use_manual_editor_lighting", "editor_preview_time_hours", "initial_phase_cycles")}
rig.modify()
rig.set_editor_property("use_manual_editor_lighting", True)
rig.set_editor_property("editor_preview_time_hours", 0.0)
rig.set_editor_property("initial_phase_cycles", 0.0)
rig.apply_editor_preview_lighting()
# 2. Moon forward-shading priority
moons = [a for a in sub.get_all_level_actors() if a.get_actor_label() == "Infinity Stage - Moon"]
require(len(moons) == 1, "Moon actor not unique")
moon_comp = moons[0].get_component_by_class(unreal.DirectionalLightComponent)
before["moon_forward_shading_priority"] = int(moon_comp.get_editor_property("forward_shading_priority"))
moons[0].modify(); moon_comp.set_editor_property("forward_shading_priority", 1)
# 3. Show passage temporality
show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH); require(show, "Show did not load")
settings = list(show.get_editor_property("passage_settings")); require(len(settings) == 6, f"Expected 6 passages, found {len(settings)}")
before["passages"] = []
for i, ps in enumerate(settings):
    cc = ps.get_editor_property("celestial_cycle")
    before["passages"].append({"animate": bool(cc.get_editor_property("animate")), "entry_phase_offset_cycles": float(cc.get_editor_property("entry_phase_offset_cycles"))})
    cc.set_editor_property("animate", False); cc.set_editor_property("entry_phase_offset_cycles", 0.0)
    ps.set_editor_property("celestial_cycle", cc); settings[i] = ps
show.modify(); show.set_editor_property("passage_settings", settings)
# read-back
after = {"rig": {n: rig.get_editor_property(n) for n in ("use_manual_editor_lighting", "editor_preview_time_hours", "initial_phase_cycles",
         "current_normalized_phase", "current_daylight_amount", "current_stars_amount")},
         "moon_forward_shading_priority": int(moon_comp.get_editor_property("forward_shading_priority")),
         "passages": [{"animate": bool(ps.get_editor_property("celestial_cycle").get_editor_property("animate")),
                       "entry_phase_offset_cycles": float(ps.get_editor_property("celestial_cycle").get_editor_property("entry_phase_offset_cycles"))}
                      for ps in show.get_editor_property("passage_settings")]}
require(after["rig"]["current_daylight_amount"] == 0.0 and after["rig"]["current_normalized_phase"] == 0.0, f"Rig did not settle at midnight: {after['rig']}")
require(all(not p["animate"] and p["entry_phase_offset_cycles"] == 0.0 for p in after["passages"]), "Passage temporality not frozen")
d1 = dirty(); require(set(d1["content"]) <= {SHOW_PATH} and set(d1["maps"]) <= {EXPECTED_WORLD}, f"Unexpected dirty: {d1}")
with open(os.path.join(OUT, "apply_night_stage1_result.json"), "w", encoding="utf-8") as fh:
    json.dump({"status": "ok", "saved": False, "backup": backup, "before": before, "after": after, "dirty": d1}, fh, indent=1, default=str)
unreal.AutomationLibrary.take_high_res_screenshot(1920, 1080, "NightLighting_Stage1_Viewport")
unreal.log(f"NIGHT_LIGHTING_STAGE1_SUCCESS|phase={after['rig']['current_normalized_phase']}|daylight={after['rig']['current_daylight_amount']}|stars={after['rig']['current_stars_amount']}|passages_frozen=6|saved=0")
