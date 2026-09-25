import unreal
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
fog = [a for a in sub.get_all_level_actors() if a.get_class().get_name() == "ExponentialHeightFog" and a.get_actor_label().startswith("Infinity Stage")][0]
c = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
names = sorted({p for p in dir(c) if "volumetric" in p.lower() or "fog" in p.lower()})
unreal.log("PUSS_FOGPROPS|" + ", ".join(names))
