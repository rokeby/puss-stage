import unreal
L = unreal.LevelSequenceEditorBlueprintLibrary
cur = L.get_current_level_sequence()
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
spawned = [a.get_actor_label() for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
           if "Chaos Curtain" in a.get_actor_label() or "Curtain Floor" in a.get_actor_label()]
strays = [a.get_actor_label() for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
          if a.get_actor_label().startswith("ZZ_")]
c = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
m = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
unreal.log("SEQ_STATE|open=%s|opening_spawnables=%s|strays=%s|dirty=%d+%d" % (
    cur.get_name() if cur else "NONE", spawned, strays, c, m))
