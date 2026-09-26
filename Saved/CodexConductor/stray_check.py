import unreal
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
caps = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.SceneCapture2D)
unreal.log("STRAY_SCENECAPTURE|%d" % len(caps))
for c in caps:
    unreal.log("STRAY|%s|%s" % (c.get_actor_label(), c.get_actor_location()))
