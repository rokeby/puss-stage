"""READ-ONLY: every materialized wing panel's world bottom vs its passage floor. No edits, no saves."""
import json, os, unreal
BASE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexFlatV3")
def census():
    n = lambda ps: sorted(str(p.get_name()).split(".", 1)[0] for p in ps)
    return {"content": n(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": n(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}
start = census()
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world() is not None:
    raise RuntimeError("PIE_OR_SIE_ACTIVE")
out = {"census_start": start, "passages": {}}
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if actor.get_class().get_name() != "InfinityStagePassageActor":
        continue
    floor_z = float(actor.get_actor_location().z)
    rows = []
    for ref in actor.get_editor_property("materialized_panels"):
        side = str(ref.get_editor_property("side")).upper()
        if "TOP" in side:
            continue
        comp = ref.get_editor_property("component")
        mesh = comp.get_editor_property("static_mesh")
        t = comp.get_instance_transform(int(ref.get_editor_property("instance_index")), True)
        box = mesh.get_bounding_box()
        zs = [t.transform_location(unreal.Vector(x, y, z)).z for x in (box.min.x, box.max.x)
              for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z)]
        rows.append({"cue_guid": ref.get_editor_property("cue_guid").to_string(), "side": side[-6:],
                     "mesh": mesh.get_name(), "bottom_above_floor_cm": round(min(zs) - floor_z, 1)})
    floating = [r for r in rows if r["bottom_above_floor_cm"] > 2.0]
    out["passages"][actor.get_actor_label()] = {"floor_z": floor_z, "panels": len(rows),
                                                "floating": len(floating), "rows": floating}
end = census()
if end != start:
    raise RuntimeError("PROBE_CHANGED_CENSUS|" + json.dumps([start, end]))
p = os.path.join(BASE, "probe_ground_contact_out.json"); open(p, "w").write(json.dumps(out, indent=1))
unreal.log("FLATV3_PROBE_GROUND_OK path=%s summary=%s census=%s" % (
    p, json.dumps({k: [v["panels"], v["floating"]] for k, v in out["passages"].items()}), json.dumps(end)))
