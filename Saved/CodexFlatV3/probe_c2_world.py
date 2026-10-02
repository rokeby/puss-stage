"""Read-only: world bounds of placed P05 panels for chosen cues, independent of verify's pair-frame logic."""
import json, os, unreal
BASE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexFlatV3")
guids = json.load(open(os.path.join(BASE, "probe_c2_guids.json")))
def census():
    n = lambda ps: sorted(str(p.get_name()).split(".", 1)[0] for p in ps)
    return {"content": n(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": n(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}
start = census()
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world() is not None:
    raise RuntimeError("PIE_OR_SIE_ACTIVE")
actors = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
          if a.get_class().get_name() == "InfinityStagePassageActor" and a.get_actor_label().startswith("Passage 05")]
if len(actors) != 1:
    raise RuntimeError("P05_ACTOR_COUNT|%d" % len(actors))
refs = actors[0].get_editor_property("materialized_panels")
v = lambda x: [round(x.x, 2), round(x.y, 2), round(x.z, 2)]
out = {}
for idx, guid in guids.items():
    sides = {}
    for ref in refs:
        if ref.get_editor_property("cue_guid").to_string() != guid:
            continue
        side = str(ref.get_editor_property("side")).upper()
        comp = ref.get_editor_property("component")
        mesh = comp.get_editor_property("static_mesh")
        t = comp.get_instance_transform(int(ref.get_editor_property("instance_index")), True)
        box = mesh.get_bounding_box()
        pts = [t.transform_location(unreal.Vector(x, y, z)) for x in (box.min.x, box.max.x)
               for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z)]
        lo = [min(getattr(p, a) for p in pts) for a in "xyz"]; hi = [max(getattr(p, a) for p in pts) for a in "xyz"]
        sides[side] = {"mesh": mesh.get_name(), "world_min": [round(q, 1) for q in lo], "world_max": [round(q, 1) for q in hi],
                       "centre": [round((a + b) / 2, 1) for a, b in zip(lo, hi)],
                       "inward": v(ref.get_editor_property("inward_world_direction")),
                       "instance_loc": v(t.translation), "base_loc": v(ref.get_editor_property("base_world_transform").translation)}
    keys = list(sides)
    L = next((sides[k] for k in keys if "LEFT" in k), None); R = next((sides[k] for k in keys if "RIGHT" in k), None)
    res = {"sides": sides}
    if L and R:
        d = [r - l for r, l in zip(R["centre"], L["centre"])]
        res["right_minus_left_dot_left_inward"] = round(sum(a * b for a, b in zip(d, L["inward"])), 1)
        res["left_minus_right_dot_right_inward"] = round(sum(-a * b for a, b in zip(d, R["inward"])), 1)
    out[idx] = res
end = census()
if end != start or end != {"content": [], "maps": []}:
    raise RuntimeError("CENSUS|start=%s|end=%s" % (start, end))
p = os.path.join(BASE, "probe_c2_world_out.json"); open(p, "w").write(json.dumps(out, indent=1))
unreal.log("FLATV3_PROBE_C2_OK path=%s census=%s" % (p, json.dumps(end)))
