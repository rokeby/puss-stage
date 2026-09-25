"""STAGE 1 (no save): read P01 Wing 001's Light attachments straight from the Show (as written back by the
editor when you move the actors) and replicate their relative transforms + light settings to every other
wing pair with small jitter. Enabled state follows row 1 (disabled slots stay disabled everywhere).
Rematerializes all six Passages and records the template."""
import json, os, random
import unreal
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting")
def require(c, m):
    if not c: raise RuntimeError(m)
def rot(r): return [round(r.pitch,3), round(r.yaw,3), round(r.roll,3)]
def vec(v): return [round(v.x,2), round(v.y,2), round(v.z,2)]
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem); require(ed.get_game_world() is None, "PIE active - stop PIE first")
plan = json.load(open(os.path.join(OUT, "lighting_plan.json"), encoding="utf-8"))
show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH); require(show, "Show did not load")
cues = list(show.get_editor_property("cues"))
src_index = next(i for i, c in enumerate(cues) if str(c.get_editor_property("label")) == "P01 Wing 001")
src = cues[src_index].get_editor_property("wing_pair").get_editor_property("attachments")
template = {}
FIELDS = ["type", "intensity_units", "intensity", "color", "use_temperature", "temperature_kelvin", "attenuation_radius_cm", "inner_cone_angle_degrees",
          "outer_cone_angle_degrees", "rect_source_width_cm", "rect_source_height_cm", "source_radius_cm", "cast_shadows", "light_function_material",
          "max_draw_distance_cm", "max_distance_fade_range_cm"]
for att in src:
    if att.get_editor_property("kind") != unreal.InfinityAttachmentKind.LIGHT: continue
    name = str(att.get_editor_property("label"))[len("P01 Wing 001 "):]
    t = att.get_editor_property("relative_transform"); L = att.get_editor_property("lighting")
    template[name] = {"loc": vec(t.translation), "rot": rot(t.rotation.rotator()), "enabled": bool(att.get_editor_property("enabled")),
                      "lighting": {f: L.get_editor_property(f) for f in FIELDS}}
require(len(template) == 10, f"expected 10 light slots on row 1, found {len(template)}")
show.modify(); rows = 0; enabled = 0
for i, cue in enumerate(cues):
    prow = plan.get(str(i))
    if not prow or i == src_index: continue
    rng = random.Random(f"tmpl3:{i}")
    pair = cue.get_editor_property("wing_pair"); atts = list(pair.get_editor_property("attachments"))
    lights = [k for k, a in enumerate(atts) if a.get_editor_property("kind") == unreal.InfinityAttachmentKind.LIGHT]
    require(len(lights) == 10, f"row {i}: {len(lights)} light slots")
    for slot in prow["lights"]:
        att = atts[lights[slot["slot"]]]; name = slot["label"][len(prow["label"]) + 1:]
        t = template.get(name); require(t is not None, f"row {i}: slot {name} missing on row 1")
        loc = [t["loc"][0] + rng.uniform(-25, 25), t["loc"][1] + rng.uniform(-15, 15), t["loc"][2] + rng.uniform(-20, 20)]
        r = [t["rot"][0] + rng.uniform(-3, 3), t["rot"][1] + rng.uniform(-3, 3), t["rot"][2] + rng.uniform(-2, 2)]
        inten = float(t["lighting"]["intensity"]) * rng.uniform(0.8, 1.2)
        tr = unreal.Transform(); tr.translation = unreal.Vector(*loc); tr.rotation = unreal.Rotator(roll=r[2], pitch=r[0], yaw=r[1]).quaternion()
        att.set_editor_property("relative_transform", tr); att.set_editor_property("enabled", t["enabled"])
        L = att.get_editor_property("lighting")
        for f, v in t["lighting"].items():
            L.set_editor_property(f, v)
        L.set_editor_property("intensity", inten)
        att.set_editor_property("lighting", L); atts[lights[slot["slot"]]] = att
        slot.update({"enabled": t["enabled"], "loc": [round(v, 2) for v in loc], "rot": [round(v, 3) for v in r], "intensity_cd": round(inten, 4)})
        enabled += int(t["enabled"])
    pair.set_editor_property("attachments", atts); cue.set_editor_property("wing_pair", pair); cues[i] = cue; rows += 1
show.set_editor_property("cues", cues)
json.dump(plan, open(os.path.join(OUT, "lighting_plan.json"), "w", encoding="utf-8"), indent=1)
json.dump({k: {"loc": v["loc"], "rot": v["rot"], "enabled": v["enabled"], "intensity": v["lighting"]["intensity"]} for k, v in template.items()},
          open(os.path.join(OUT, "row1_template_used.json"), "w"), indent=1, default=str)
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem); mat = {}
for a in sub.get_all_level_actors():
    if a.get_class().get_name() == "InfinityStagePassageActor" and a.get_editor_property("show_asset") == show:
        require(bool(a.materialize_passage()), f"materialize failed {a.get_actor_label()}"); mat[a.get_actor_label()[:10]] = int(a.get_editor_property("materialized_wing_pair_count"))
unreal.log(f"ROW1_SHOW_TEMPLATE_REPLICATED|source_slots=10|enabled_on_row1={sum(1 for t in template.values() if t['enabled'])}|rows={rows}|enabled_total={enabled}|materialized={mat}|saved=0")
