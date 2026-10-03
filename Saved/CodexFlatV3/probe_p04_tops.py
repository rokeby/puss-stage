"""READ-ONLY: world bounds of P04's top-border panels, plus the walking camera, to size a lift."""
import json, os, unreal
BASE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexFlatV3")
def census():
    n = lambda ps: sorted(str(p.get_name()).split(".", 1)[0] for p in ps)
    return {"content": n(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": n(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}
start = census(); out = {"census": start, "tops": [], "cameras": []}
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    cls = actor.get_class().get_name()
    if cls == "InfinityStagePassageActor" and "Passage 04" in actor.get_actor_label():
        for ref in actor.get_editor_property("materialized_panels"):
            if "TOP" not in str(ref.get_editor_property("side")).upper():
                continue
            comp = ref.get_editor_property("component"); mesh = comp.get_editor_property("static_mesh")
            t = comp.get_instance_transform(int(ref.get_editor_property("instance_index")), True)
            b = mesh.get_bounding_box()
            pts = [t.transform_location(unreal.Vector(x, y, z)) for x in (b.min.x, b.max.x) for y in (b.min.y, b.max.y) for z in (b.min.z, b.max.z)]
            out["tops"].append({"cue_guid": ref.get_editor_property("cue_guid").to_string(), "mesh": mesh.get_name(),
                                "z_min": round(min(p.z for p in pts), 1), "z_max": round(max(p.z for p in pts), 1),
                                "y_span": [round(min(p.y for p in pts), 1), round(max(p.y for p in pts), 1)],
                                "x_center": round(sum(p.x for p in pts) / 8, 1)})
    if "Camera" in cls and ("Pilot" in actor.get_actor_label() or "Walk" in actor.get_actor_label() or "Master" in actor.get_actor_label()):
        cam = actor.get_component_by_class(unreal.CameraComponent)
        out["cameras"].append({"label": actor.get_actor_label(), "class": cls, "z": round(actor.get_actor_location().z, 1),
                               "fov": cam.get_editor_property("field_of_view") if cam else None})
end = census()
if end != start:
    raise RuntimeError("PROBE_CHANGED_CENSUS")
p = os.path.join(BASE, "probe_p04_tops_out.json"); open(p, "w").write(json.dumps(out, indent=1))
unreal.log("FLATV3_PROBE_P04_TOPS_OK n=%d path=%s" % (len(out["tops"]), p))
