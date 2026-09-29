"""Read-only: ISM/Nanite usage flags on every base material the wings render with."""
import importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
wm.editor_ready()
before = wm.dirty()
bases = {}
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if actor.get_class().get_name() != "InfinityStagePassageActor":
        continue
    p = actor.get_actor_label()[:10].replace("Passage ", "P")
    for comp in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
        nanite = bool(comp.get_editor_property("static_mesh").get_editor_property("nanite_settings").get_editor_property("enabled"))
        for m in comp.get_materials():
            base = m.get_base_material() if m else None
            key = wm.pkg(base)
            rec = bases.setdefault(key, {"ism": bool(base.get_editor_property("used_with_instanced_static_meshes")),
                                         "nanite_flag": bool(base.get_editor_property("used_with_nanite")),
                                         "auto": bool(base.get_editor_property("automatically_set_usage_in_editor")),
                                         "passages": {}, "nanite_meshes": 0})
            rec["passages"][p] = rec["passages"].get(p, 0) + 1
            rec["nanite_meshes"] += int(nanite)
wm.require(wm.dirty() == before, "dirty changed")
wm.write_json("usage_flags.json", bases)
unreal.log(f"PUSS_WING_USAGE_FLAGS_SUCCESS|bases={len(bases)}")
