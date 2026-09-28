import unreal
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    if "Curtain" in a.get_actor_label():
        unreal.log("ACTOR|%s|%s" % (a.get_actor_label(), a.get_class().get_name()))
        for comp in a.get_components_by_class(unreal.ActorComponent):
            if "Cloth" in comp.get_class().get_name():
                ca = comp.get_editor_property("cloth_asset")
                unreal.log("  ASSET|%s" % (ca.get_name() if ca else "None"))
                for prop in ("suspend_simulation_at_start","simulate_in_editor"):
                    try:
                        unreal.log("  %s=%s" % (prop, comp.get_editor_property(prop)))
                    except Exception:
                        pass
                try:
                    unreal.log("  is_suspended=%s" % comp.is_simulation_suspended())
                except Exception as e:
                    unreal.log("  is_suspended=<%s>" % e)
