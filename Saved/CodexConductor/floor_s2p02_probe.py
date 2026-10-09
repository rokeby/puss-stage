import unreal
out = []
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    l = str(a.get_actor_label())
    if not (("Passage 02" in l and "Floor" in l) or (l.startswith("S2") and ("Floor" in l or "Apron" in l)) or "DarkWet" in l): continue
    mats = []
    for c in a.get_components_by_class(unreal.StaticMeshComponent):
        mats.append([m.get_name() if m else None for m in c.get_materials()])
    out.append((l, a.get_class().get_name(), a.get_level().get_outer().get_name(), [round(v) for v in (a.get_actor_location().x, a.get_actor_location().y, a.get_actor_location().z)], mats))
unreal.log("FLOORPROBE_OK|%s" % out)
