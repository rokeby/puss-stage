"""READ-ONLY: actors near S3 whose label/tags/mesh mention door, with location, parent, hidden flag."""
import json
import unreal
rows = []
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    lab = str(a.get_actor_label())
    tags = [str(t) for t in a.tags]
    meshes = [c.get_editor_property("static_mesh").get_name() for c in a.get_components_by_class(unreal.StaticMeshComponent)
              if c.get_editor_property("static_mesh")]
    blob = (lab + " " + " ".join(tags) + " " + " ".join(meshes)).lower()
    if "door" in blob and ("s3" in blob or "scene 3" in blob or "scene3" in blob or abs(a.get_actor_location().y - 160000) < 6000):
        par = a.get_attach_parent_actor()
        l = a.get_actor_location()
        rows.append({"label": lab, "class": a.get_class().get_name(), "loc": [round(l.x), round(l.y), round(l.z)],
                     "parent": par.get_actor_label() if par else None, "hidden": bool(a.get_editor_property("hidden")),
                     "tags": tags[:4], "meshes": meshes[:3]})
for r in rows:
    unreal.log("PROBE_S3_DOOR|" + json.dumps(r))
unreal.log("PROBE_S3_DOORS_OK|n=%d" % len(rows))
