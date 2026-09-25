"""STAGE 1 (no save): restore P01 Wing 001's light attachments to the plugin-written relative transforms captured
in p01_tuned.json (show_row), then replicate those relative transforms + settings to every other pair with small
jitter. Slot 10 (Top Down) stays disabled. Rematerializes all six Passages."""
import json, os, random
import unreal
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting")
def require(c, m):
    if not c: raise RuntimeError(m)
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem); require(ed.get_game_world() is None, "PIE active - stop PIE first")
tuned = json.load(open(os.path.join(OUT, "p01_tuned.json"), encoding="utf-8"))
show_row, actors = tuned["show_row"], tuned["actors"]
plan = json.load(open(os.path.join(OUT, "lighting_plan.json"), encoding="utf-8"))
template = {}
for name, r in show_row.items():
    if name not in actors: continue
    a = actors[name]
    template[name] = {"loc": r["rel"]["loc"], "rot": r["rel"]["rot"], "intensity": a["intensity"], "cone": [a.get("inner_cone_angle"), a.get("outer_cone_angle")],
                      "radius": a.get("attenuation_radius"), "cast_shadows": a.get("cast_shadows"), "source_radius": a.get("source_radius") or 0.0}
require(len(template) == 9, f"expected 9 template lights, found {sorted(template)}")
show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH); require(show, "Show did not load")
show.modify(); cues = list(show.get_editor_property("cues")); rows = 0; enabled = 0
for i, cue in enumerate(cues):
    prow = plan.get(str(i))
    if not prow: continue
    rng = random.Random(f"tmpl2:{i}"); first = (prow["passage"] == 1 and prow["ordinal"] == 1)
    pair = cue.get_editor_property("wing_pair"); atts = list(pair.get_editor_property("attachments"))
    lights = [k for k, a in enumerate(atts) if a.get_editor_property("kind") == unreal.InfinityAttachmentKind.LIGHT]
    require(len(lights) == 10, f"row {i}: {len(lights)} light slots")
    for slot in prow["lights"]:
        att = atts[lights[slot["slot"]]]; name = slot["label"][len(prow["label"]) + 1:]
        if name not in template:
            slot["enabled"] = False; att.set_editor_property("enabled", False); atts[lights[slot["slot"]]] = att; continue
        t = template[name]; loc = list(t["loc"]); rot = list(t["rot"]); inten = t["intensity"]
        if not first:
            loc = [loc[0] + rng.uniform(-25, 25), loc[1] + rng.uniform(-15, 15), loc[2] + rng.uniform(-20, 20)]
            rot = [rot[0] + rng.uniform(-3, 3), rot[1] + rng.uniform(-3, 3), rot[2] + rng.uniform(-2, 2)]
            inten *= rng.uniform(0.8, 1.2)
        slot.update({"enabled": True, "loc": [round(v, 2) for v in loc], "rot": [round(v, 3) for v in rot], "intensity_cd": round(inten, 4),
                     "cone": t["cone"], "radius": t["radius"], "cast_shadows": bool(t["cast_shadows"]), "source_radius": float(t["source_radius"])})
        tr = unreal.Transform(); tr.translation = unreal.Vector(*slot["loc"])
        tr.rotation = unreal.Rotator(roll=slot["rot"][2], pitch=slot["rot"][0], yaw=slot["rot"][1]).quaternion()
        att.set_editor_property("relative_transform", tr); att.set_editor_property("enabled", True)
        L = att.get_editor_property("lighting")
        L.set_editor_property("intensity", float(slot["intensity_cd"])); L.set_editor_property("attenuation_radius_cm", float(slot["radius"]))
        if slot["cone"][0] is not None:
            L.set_editor_property("inner_cone_angle_degrees", float(slot["cone"][0])); L.set_editor_property("outer_cone_angle_degrees", float(slot["cone"][1]))
        L.set_editor_property("cast_shadows", bool(slot["cast_shadows"])); L.set_editor_property("source_radius_cm", float(slot["source_radius"]))
        att.set_editor_property("lighting", L); atts[lights[slot["slot"]]] = att; enabled += 1
    pair.set_editor_property("attachments", atts); cue.set_editor_property("wing_pair", pair); cues[i] = cue; rows += 1
show.set_editor_property("cues", cues)
json.dump(plan, open(os.path.join(OUT, "lighting_plan.json"), "w", encoding="utf-8"), indent=1)
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem); mat = {}
for a in sub.get_all_level_actors():
    if a.get_class().get_name() == "InfinityStagePassageActor" and a.get_editor_property("show_asset") == show:
        require(bool(a.materialize_passage()), f"materialize failed {a.get_actor_label()}"); mat[a.get_actor_label()[:10]] = int(a.get_editor_property("materialized_wing_pair_count"))
# read back row 1 actor rotations for the record
back = {}
for a in sub.get_all_level_actors():
    if isinstance(a, unreal.Light) and a.get_actor_label().startswith("P01 Wing 001 "):
        r = a.get_actor_rotation(); back[a.get_actor_label()[13:]] = [round(r.pitch,2), round(r.yaw,2), round(r.roll,2)]
json.dump({"row1_actor_rot_after": back, "tuned_actor_rot_before": {k: v["world"]["rot"] for k, v in actors.items()}}, open(os.path.join(OUT, "repair_row1_result.json"), "w"), indent=1)
match = sum(1 for k in back if k in actors and all(abs(back[k][j] - actors[k]["world"]["rot"][j]) < 0.5 for j in range(3)))
unreal.log(f"ROW1_REPAIRED_AND_REPLICATED|rows={rows}|enabled={enabled}|row1_rot_matches_tuned={match}/9|materialized={mat}|saved=0")
