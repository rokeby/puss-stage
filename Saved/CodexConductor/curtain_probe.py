"""Which curtains are actually in the level, and which pipeline made each."""
import unreal
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    label = a.get_actor_label()
    cls = a.get_class().get_name()
    if "urtain" in label or "Cloth" in label or "GeometryCache" in cls or "ChaosCloth" in cls:
        loc = a.get_actor_location()
        unreal.log("CURTAIN|%s|class=%s|x=%.0f y=%.0f z=%.0f" % (label, cls, loc.x, loc.y, loc.z))
        for comp in a.get_components_by_class(unreal.ActorComponent):
            cn = comp.get_class().get_name()
            if "GeometryCache" in cn:
                gc = comp.get_editor_property("geometry_cache")
                unreal.log("   ASSET|GeometryCache|%s" % (gc.get_name() if gc else "None"))
            if "ChaosCloth" in cn:
                try:
                    ca = comp.get_editor_property("cloth_asset")
                    unreal.log("   ASSET|ChaosCloth|%s" % (ca.get_name() if ca else "None"))
                except Exception as e:
                    unreal.log("   ASSET|ChaosCloth|<%s>" % e)
