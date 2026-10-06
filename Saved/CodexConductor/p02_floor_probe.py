import json, unreal
out = {}
acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
for lab in ["Passage 02 - Floor Near", "Passage 02 - Floor Left", "Passage 02 - Floor Right", "Passage 02 - Floor Far", "Passage 03 - Floor"]:
    a = [x for x in acts if str(x.get_actor_label()) == lab]
    if a:
        c = a[0].get_component_by_class(unreal.StaticMeshComponent)
        o, e = a[0].get_actor_bounds(False)
        out[lab] = {"mats": [m.get_path_name() if m else None for m in c.get_materials()], "hidden": bool(a[0].get_editor_property("hidden")),
                    "top_z": o.z + e.z, "x": [o.x - e.x, o.x + e.x], "y": [o.y - e.y, o.y + e.y]}
for x in acts:
    if isinstance(x, unreal.InfinityStageStructureActor) and str(x.get_actor_label()).endswith(("02", "03")):
        g = x.get_editor_property("ground")
        out[str(x.get_actor_label())] = {"ground_enabled": bool(g.get_editor_property("enabled"))}
mi = unreal.load_asset("/Game/EnvironmentPacks/4K_WoodFlooring_Vol_02/Materials/M_Walnut_Hrrngbn_02_Mat_Inst_Dup")
MEL = unreal.MaterialEditingLibrary
out["walnut_scalars"] = {str(n): float(MEL.get_material_instance_scalar_parameter_value(mi, n)) for n in MEL.get_scalar_parameter_names(mi)}
unreal.log("P02_FLOOR_PROBE|%s" % json.dumps(out))
