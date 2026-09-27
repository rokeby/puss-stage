import unreal
print_ = unreal.log
print_("HAS_POST_TICK|%s" % hasattr(unreal, "register_slate_post_tick_callback"))
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    if a.get_actor_label() == "CurtainChaos Preview":
        for comp in a.get_components_by_class(unreal.ActorComponent):
            cn = comp.get_class().get_name()
            if "Cloth" in cn:
                members = [m for m in dir(comp) if any(k in m.lower() for k in ("simul","suspend","reset","teleport","tick"))]
                print_("CLOTH_COMP|%s" % cn)
                print_("CLOTH_MEMBERS|%s" % members)
