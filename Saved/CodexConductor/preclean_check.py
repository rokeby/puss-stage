"""Before clearing my own map flag: prove nothing of mine is left in the level."""
import unreal
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
strays = [a.get_actor_label() for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
          if a.get_actor_label().startswith("ZZ_")]
caps = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.SceneCapture2D)
# Spawnables from the Chaos opening sequence must be gone now Sequencer is closed.
chaos = [a.get_actor_label() for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
         if "Chaos Curtain" in a.get_actor_label() or "Curtain Floor" in a.get_actor_label()]
seq = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
unreal.log("PRECLEAN|strays=%s|scene_captures=%d|chaos_spawnables=%s|sequencer_open=%s" % (
    strays, len(caps), chaos, seq.get_name() if seq else "none"))
c = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
m = unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
unreal.log("PRECLEAN_DIRTY|content=%d|maps=%s" % (c, [p.get_name() for p in m]))
