"""READ-ONLY (5 Oct): what are the dark cubes on P05's horizon? Groups every StaticMesh/ISM component in the P05 area
(the Passage 05 actor's children and any actor whose origin is inside its box) by mesh asset, with counts, owner
labels and sample world locations. Changes nothing."""
import collections
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = sub.get_all_level_actors()
p05 = [a for a in actors if a.get_class().get_name() == "InfinityStagePassageActor"
       and str(a.get_actor_label()).startswith("Passage 05")][0]
o, e = p05.get_actor_bounds(False)
box = (o.x - e.x, o.x + e.x, o.y - e.y, o.y + e.y)
rows = collections.defaultdict(lambda: {"n": 0, "owners": collections.Counter(), "samples": [], "class": ""})
for a in actors:
    loc = a.get_actor_location()
    if not (box[0] - 500 <= loc.x <= box[1] + 500 and box[2] - 500 <= loc.y <= box[3] + 500):
        continue
    for c in a.get_components_by_class(unreal.StaticMeshComponent):
        m = c.get_editor_property("static_mesh")
        key = m.get_path_name() if m else "None"
        r = rows[key]
        n = c.get_instance_count() if isinstance(c, unreal.InstancedStaticMeshComponent) else 1
        r["n"] += n
        r["class"] = c.get_class().get_name()
        r["owners"][str(a.get_actor_label())] += n
        if len(r["samples"]) < 3:
            w = c.get_world_location()
            r["samples"].append([round(w.x), round(w.y), round(w.z), str(c.get_name())])
out = {k: {"n": v["n"], "class": v["class"], "owners": dict(v["owners"].most_common(4)), "samples": v["samples"]}
       for k, v in sorted(rows.items(), key=lambda kv: -kv[1]["n"])}
p = os.path.join(HERE, "probe_p05_meshes.json")
json.dump({"box": box, "meshes": out}, open(p, "w", encoding="utf-8"), indent=1)
unreal.log("PROBE_P05_MESHES|meshes=%d|out=%s" % (len(out), p))
