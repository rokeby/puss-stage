import unreal
a = [x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if x.get_actor_label() == "FX SMOKE P04 B18 L"][0]
cls = a.get_class()
props = [p for p in dir(a) if any(k in p.lower() for k in ("apparatus", "show", "visible", "hide", "mesh", "machine", "body"))]
unreal.log("SMOKE_CLASS|%s|%s|%s" % (cls.get_path_name(), props, [c.get_name() + ":" + c.get_class().get_name() for c in a.get_components_by_class(unreal.ActorComponent)]))
