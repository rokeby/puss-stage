"""READ-ONLY: current mesh, class and component info of the six S3 Wave Row actors."""
import json, os, unreal
BASE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexFlatV3")
def census():
    n = lambda ps: sorted(str(p.get_name()).split(".", 1)[0] for p in ps)
    return {"content": n(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": n(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}
start = census(); rows = []
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if not a.get_actor_label().startswith("S3 Wave Row"):
        continue
    comps = a.get_components_by_class(unreal.StaticMeshComponent)
    rows.append({"label": a.get_actor_label(), "class": a.get_class().get_name(), "path": a.get_path_name(),
                 "level": a.get_outermost().get_name(),
                 "components": [{"name": c.get_name(), "mesh": c.get_editor_property("static_mesh").get_path_name() if c.get_editor_property("static_mesh") else None,
                                 "mobility": str(c.get_editor_property("mobility"))} for c in comps]})
end = census()
if end != start:
    raise RuntimeError("PROBE_CHANGED_CENSUS|" + json.dumps([start, end]))
p = os.path.join(BASE, "probe_w2_actors_out.json"); open(p, "w").write(json.dumps({"census": end, "actors": rows}, indent=1))
unreal.log("FLATV3_PROBE_W2_ACTORS_OK n=%d census=%s" % (len(rows), json.dumps(end)))
