"""READ-ONLY (5 Oct, Gary: 'there are waves in P01'): every actor or component whose label, mesh or tags mention wave,
with world location, hidden flag, owner, folder; plus P01's bounds. Changes nothing."""
import json
import os

import unreal

acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
p01 = [a for a in acts if a.get_class().get_name() == "InfinityStagePassageActor" and str(a.get_actor_label()).startswith("Passage 01")][0]
o, e = p01.get_actor_bounds(False)
rows = []
for a in acts:
    lab = str(a.get_actor_label())
    tags = [str(t) for t in a.tags]
    hit = "wave" in lab.lower() or any("wave" in t.lower() for t in tags)
    meshes = []
    for c in a.get_components_by_class(unreal.StaticMeshComponent):
        m = c.get_editor_property("static_mesh")
        if m and "wave" in m.get_name().lower():
            hit = True
            meshes.append(m.get_path_name())
    if hit:
        loc = a.get_actor_location()
        rows.append({"label": lab, "class": a.get_class().get_name(), "loc": [round(loc.x), round(loc.y), round(loc.z)],
                     "hidden": bool(a.get_editor_property("hidden")), "folder": str(a.get_folder_path()), "tags": tags,
                     "meshes": sorted(set(meshes))[:3],
                     "in_p01_box": (o.x - e.x <= loc.x <= o.x + e.x and o.y - e.y <= loc.y <= o.y + e.y)})
p = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor", "probe_waves.json")
json.dump({"p01_box": [o.x - e.x, o.x + e.x, o.y - e.y, o.y + e.y], "rows": rows}, open(p, "w", encoding="utf-8"), indent=1)
unreal.log("PROBE_WAVES_OK|n=%d|in_p01=%d|out=%s" % (len(rows), sum(r["in_p01_box"] for r in rows), p))
