"""Read-only: local-space X (thickness) range of every live wing mesh."""
import importlib.util, os, collections
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
wm.editor_ready()
rows = {}
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if actor.get_class().get_name() != "InfinityStagePassageActor":
        continue
    for comp in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
        m = comp.get_editor_property("static_mesh")
        if m is None:
            continue
        b = m.get_bounding_box()
        rows[wm.pkg(m)] = [round(b.min.x, 2), round(b.max.x, 2), round(b.min.y, 1), round(b.max.y, 1),
                           round(b.min.z, 1), round(b.max.z, 1)]
wm.write_json("mesh_bounds.json", rows)
unreal.log(f"PUSS_WING_MESH_BOUNDS_SUCCESS|meshes={len(rows)}")
