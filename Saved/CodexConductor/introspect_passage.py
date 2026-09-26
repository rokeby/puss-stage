import unreal
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
ps = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStagePassageActor)
p1 = next((p for p in ps if "01" in p.get_actor_label()), ps[0])
props = [m for m in dir(p1) if not m.startswith('_')]
unreal.log("PASSAGE_PROPS|%s" % [m for m in props if any(k in m.lower() for k in ('wing','passage','compil','panel','station','show'))])
