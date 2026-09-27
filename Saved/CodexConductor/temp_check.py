import unreal
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
n=0
for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    if a.get_actor_label().startswith("ZZ_"):
        unreal.log("STRANDED|%s" % a.get_actor_label()); n+=1
unreal.log("STRANDED_TOTAL|%d" % n)
c=len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
m=len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
unreal.log("DIRTY|%d+%d" % (c,m))
