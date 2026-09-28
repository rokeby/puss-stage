import unreal
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
ticking = 0
for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    for comp in a.get_components_by_class(unreal.ActorComponent):
        if "Cloth" not in comp.get_class().get_name():
            continue
        susp = comp.get_editor_property("suspend_simulation")
        try:
            sie = comp.get_editor_property("simulate_in_editor")
        except Exception:
            sie = "?"
        try:
            tick_on = comp.is_component_tick_enabled()
        except Exception:
            tick_on = "?"
        live = (sie is True) and (susp is False)
        if live:
            ticking += 1
        unreal.log("CLOTH|%s|susp=%s|sim_in_editor=%s|tick=%s|LIVE=%s" % (
            a.get_actor_label(), susp, sie, tick_on, live))
unreal.log("QUIET_VERDICT|live_simulating=%d" % ticking)
