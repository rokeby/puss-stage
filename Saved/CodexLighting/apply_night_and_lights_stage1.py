"""STAGE 1 (no save): deepest-night rig for editor and PIE, pinned night exposure, and a per-wing-pair
stage-light set authored from lighting_plan.json via the plugin's ReplicateLightAttachments (which mints
attachment GUIDs), then per-row in-place variation. Materializes all six Passages. Captures the P1 camera view."""
import json
import os

import unreal

SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
LIGHTING_ROOT = "/Game/InfinityStage/Lighting"
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting")
SLOT_COUNT = 10


def require(c, m):
    if not c:
        raise RuntimeError(m)


def pkg(v):
    return v.get_path_name().split(".", 1)[0] if v is not None and hasattr(v, "get_path_name") else None


def dirty():
    return {"content": sorted({pkg(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}),
            "maps": sorted({pkg(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()})}


ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
require(world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "Unexpected world")
require(ed.get_game_world() is None, "PIE active")
backup = open(os.path.join(OUT, "backup_folder.txt"), encoding="utf-8").read().strip()
require(os.path.isfile(os.path.join(unreal.Paths.project_dir(), backup, "DA_InfinityStage_V1Show.uasset")), "backup missing")
d0 = dirty()
require(set(d0["content"]) <= {SHOW_PATH} and set(d0["maps"]) <= {EXPECTED_WORLD}, f"Out-of-scope dirty before mutation: {d0}")
plan = json.load(open(os.path.join(OUT, "lighting_plan.json"), encoding="utf-8"))
flicker = {}
for name in ("Steady", "Slow", "Breath", "Hum", "Buzz", "Fault"):
    mi = unreal.EditorAssetLibrary.load_asset(f"{LIGHTING_ROOT}/MI_LF_Flicker_{name}")
    require(mi is not None, f"Flicker instance missing: {name}")
    flicker[name] = mi

sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = sub.get_all_level_actors()
before = {}

# ---- 1. Celestial rig: deepest night, frozen, for editor and PIE ----
rigs = [a for a in actors if a.get_class().get_name() == "InfinityStageCelestialRig"]
require(len(rigs) == 1, "Expected exactly one celestial rig")
rig = rigs[0]
RIG_PROPS = ("use_manual_editor_lighting", "editor_preview_time_hours", "initial_phase_cycles", "maximum_sun_intensity",
             "maximum_moon_intensity", "day_sky_light_intensity", "night_sky_light_intensity", "show_built_in_stars")
before["rig"] = {n: rig.get_editor_property(n) for n in RIG_PROPS}
rig.modify()
rig.set_editor_property("use_manual_editor_lighting", True)
rig.set_editor_property("editor_preview_time_hours", 0.0)
rig.set_editor_property("initial_phase_cycles", 0.0)
rig.set_editor_property("maximum_sun_intensity", 0.0)
rig.set_editor_property("maximum_moon_intensity", 0.0)
rig.set_editor_property("day_sky_light_intensity", 0.0)
rig.set_editor_property("night_sky_light_intensity", 0.0)
rig.set_editor_property("show_built_in_stars", False)
rig.apply_editor_preview_lighting()

moons = [a for a in actors if a.get_actor_label() == "Infinity Stage - Moon"]
require(len(moons) == 1, "Moon actor not unique")
moon_comp = moons[0].get_component_by_class(unreal.DirectionalLightComponent)
before["moon_forward_shading_priority"] = int(moon_comp.get_editor_property("forward_shading_priority"))
moons[0].modify()
moon_comp.set_editor_property("forward_shading_priority", 1)

# ---- 2. Post-process: unbound, exposure pinned to a night window ----
ppvs = [a for a in actors if a.get_class().get_name() == "PostProcessVolume"]
require(len(ppvs) == 1, f"Expected one PostProcessVolume, found {len(ppvs)}")
ppv = ppvs[0]
s = ppv.get_editor_property("settings")
before["ppv"] = {"unbound": bool(ppv.get_editor_property("unbound")),
                 "override_min": bool(s.get_editor_property("override_auto_exposure_min_brightness")),
                 "override_max": bool(s.get_editor_property("override_auto_exposure_max_brightness")),
                 "min": float(s.get_editor_property("auto_exposure_min_brightness")),
                 "max": float(s.get_editor_property("auto_exposure_max_brightness"))}
ppv.modify()
ppv.set_editor_property("unbound", True)
s.set_editor_property("override_auto_exposure_min_brightness", True)
s.set_editor_property("override_auto_exposure_max_brightness", True)
s.set_editor_property("auto_exposure_min_brightness", -5.0)
s.set_editor_property("auto_exposure_max_brightness", -1.0)
s.set_editor_property("override_auto_exposure_bias", True)
s.set_editor_property("auto_exposure_bias", 0.0)
ppv.set_editor_property("settings", s)

# ---- 3. Show: freeze temporality; author the light template and replicate ----
show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
require(show is not None, "Show did not load")
show.modify()
settings = list(show.get_editor_property("passage_settings"))
require(len(settings) == 6, "Expected 6 passages")
before["passages"] = []
for i, ps in enumerate(settings):
    cc = ps.get_editor_property("celestial_cycle")
    before["passages"].append({"animate": bool(cc.get_editor_property("animate")),
                               "entry_phase_offset_cycles": float(cc.get_editor_property("entry_phase_offset_cycles"))})
    cc.set_editor_property("animate", False)
    cc.set_editor_property("entry_phase_offset_cycles", 0.0)
    ps.set_editor_property("celestial_cycle", cc)
    settings[i] = ps
show.set_editor_property("passage_settings", settings)

cues = list(show.get_editor_property("cues"))
wing_rows = []
before["removed_light_attachments"] = []
for i, cue in enumerate(cues):
    label = str(cue.get_editor_property("label"))
    if str(i) not in plan:
        continue
    require(plan[str(i)]["label"] == label, f"Row {i} label {label} != plan {plan[str(i)]['label']}")
    pair = cue.get_editor_property("wing_pair")
    kept = []
    for att in pair.get_editor_property("attachments"):
        if att.get_editor_property("kind") == unreal.InfinityAttachmentKind.LIGHT:
            before["removed_light_attachments"].append({"cue": label, "label": str(att.get_editor_property("label"))})
        else:
            kept.append(att)
    pair.set_editor_property("attachments", kept)
    cue.set_editor_property("wing_pair", pair)
    cues[i] = cue
    wing_rows.append((i, label, cue.get_editor_property("cue_guid")))
require(len(wing_rows) == len(plan), f"Wing rows {len(wing_rows)} != plan {len(plan)}")

# template on the first row: 10 typed slots (GUIDs are minted by replication below)
t_index, t_label, t_guid = wing_rows[0]
t_cue = cues[t_index]
t_pair = t_cue.get_editor_property("wing_pair")
slots = list(t_pair.get_editor_property("attachments"))
for slot in plan[str(t_index)]["lights"]:
    att = unreal.InfinityCueAttachment()
    att.set_editor_property("kind", unreal.InfinityAttachmentKind.LIGHT)
    att.set_editor_property("anchor", unreal.InfinityAttachmentAnchor.STATION)
    att.set_editor_property("label", unreal.Text(slot["label"]))
    L = unreal.InfinityStageLightSettings()
    L.set_editor_property("type", unreal.InfinityStageLightType.RECT if slot["type"] == "Rect" else unreal.InfinityStageLightType.SPOT)
    att.set_editor_property("lighting", L)
    slots.append(att)
t_pair.set_editor_property("attachments", slots)
t_cue.set_editor_property("wing_pair", t_pair)
cues[t_index] = t_cue
show.set_editor_property("cues", cues)

others = [g for (_, _, g) in wing_rows[1:]]
replicated = show.replicate_light_attachments(t_guid, others)
require(replicated == len(others), f"Replicated {replicated} of {len(others)} rows")
back = show.replicate_light_attachments(others[0], [t_guid])
require(back == 1, "Template row did not receive minted GUIDs")

# ---- 4. Per-row variation, in place ----
cues = list(show.get_editor_property("cues"))
guids = set()
enabled_total = 0
for i, cue in enumerate(cues):
    label = str(cue.get_editor_property("label"))
    if str(i) not in plan:
        continue
    pair = cue.get_editor_property("wing_pair")
    atts = list(pair.get_editor_property("attachments"))
    lights = [k for k, a in enumerate(atts) if a.get_editor_property("kind") == unreal.InfinityAttachmentKind.LIGHT]
    require(len(lights) == SLOT_COUNT, f"{label}: {len(lights)} light slots")
    for slot in plan[str(i)]["lights"]:
        att = atts[lights[slot["slot"]]]
        gid = att.get_editor_property("attachment_guid")
        g = unreal.GuidLibrary.conv_guid_to_string(gid)
        require(len(g) >= 32 and set(g) != {"0"} and g not in guids, f"{label}: bad GUID {g}")
        guids.add(g)
        att.set_editor_property("label", unreal.Text(slot["label"]))
        att.set_editor_property("enabled", bool(slot["enabled"]))
        att.set_editor_property("anchor", unreal.InfinityAttachmentAnchor.STATION)
        t = unreal.Transform()
        t.translation = unreal.Vector(*slot["loc"])
        t.rotation = unreal.Rotator(roll=slot["rot"][2], pitch=slot["rot"][0], yaw=slot["rot"][1]).quaternion()
        att.set_editor_property("relative_transform", t)
        L = att.get_editor_property("lighting")
        L.set_editor_property("type", unreal.InfinityStageLightType.RECT if slot["type"] == "Rect" else unreal.InfinityStageLightType.SPOT)
        L.set_editor_property("intensity_units", unreal.InfinityStageLightIntensityUnits.CANDELAS)
        L.set_editor_property("intensity", float(slot["intensity_cd"]))
        c = slot["color"]
        L.set_editor_property("color", unreal.LinearColor(c[0], c[1], c[2], 1.0))
        L.set_editor_property("use_temperature", slot["temperature_k"] is not None)
        if slot["temperature_k"] is not None:
            L.set_editor_property("temperature_kelvin", float(slot["temperature_k"]))
        L.set_editor_property("attenuation_radius_cm", float(slot["radius"]))
        if slot["cone"][0] is not None:
            L.set_editor_property("inner_cone_angle_degrees", float(slot["cone"][0]))
            L.set_editor_property("outer_cone_angle_degrees", float(slot["cone"][1]))
        if slot["rect"][0] is not None:
            L.set_editor_property("rect_source_width_cm", float(slot["rect"][0]))
            L.set_editor_property("rect_source_height_cm", float(slot["rect"][1]))
        L.set_editor_property("source_radius_cm", float(slot["source_radius"]))
        L.set_editor_property("cast_shadows", bool(slot["cast_shadows"]))
        L.set_editor_property("cast_volumetric_shadow", False)
        L.set_editor_property("max_draw_distance_cm", 0.0)
        L.set_editor_property("max_distance_fade_range_cm", 0.0)
        L.set_editor_property("light_function_material", flicker[slot["flicker"]])
        att.set_editor_property("lighting", L)
        atts[lights[slot["slot"]]] = att
        enabled_total += int(bool(slot["enabled"]))
    pair.set_editor_property("attachments", atts)
    cue.set_editor_property("wing_pair", pair)
    cues[i] = cue
show.set_editor_property("cues", cues)

# ---- 5. Materialize all six Passages ----
materialized = {}
for a in actors:
    if a.get_class().get_name() != "InfinityStagePassageActor":
        continue
    try:
        if a.get_editor_property("show_asset") != show:
            continue
    except Exception:  # noqa: BLE001
        continue
    require(bool(a.materialize_passage()), f"Materialization failed: {a.get_actor_label()}")
    materialized[a.get_actor_label()] = int(a.get_editor_property("materialized_wing_pair_count"))
require(len(materialized) == 6, f"Materialized {len(materialized)} Passages")
spawned_lights = sum(1 for a in sub.get_all_level_actors() if isinstance(a, unreal.Light) and " Wing " in a.get_actor_label())

d1 = dirty()
require(set(d1["content"]) <= {SHOW_PATH} and set(d1["maps"]) <= {EXPECTED_WORLD}, f"Unexpected dirty: {d1}")
with open(os.path.join(OUT, "apply_night_and_lights_stage1_result.json"), "w", encoding="utf-8") as fh:
    json.dump({"status": "ok", "saved": False, "backup": backup, "before": before, "rows": len(wing_rows),
               "slots_per_row": SLOT_COUNT, "unique_guids": len(guids), "enabled_lights": enabled_total,
               "spawned_light_actors": spawned_lights, "materialized": materialized, "dirty": d1}, fh, indent=1, default=str)

p1 = [a for a in actors if a.get_class().get_name() == "InfinityStageCameraRig" and a.get_actor_label().startswith("Passage 01")]
if p1:
    cam = p1[0].get_editor_property("camera")
    ed.set_level_viewport_camera_info(cam.get_world_location(), cam.get_world_rotation())
    unreal.AutomationLibrary.take_high_res_screenshot(1920, 1080, "NightLights_Stage1_P1Camera")
unreal.log(f"NIGHT_LIGHTS_STAGE1_SUCCESS|rows={len(wing_rows)}|guids={len(guids)}|enabled={enabled_total}"
           f"|spawned={spawned_lights}|materialized={materialized}|daylight={rig.get_editor_property('current_daylight_amount')}|saved=0")
