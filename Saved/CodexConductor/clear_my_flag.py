"""Save the level to absorb the conductor's own net-nil capture flag.

Verified immediately before: no ZZ_ strays, no SceneCapture2D, no Chaos
spawnables, Sequencer closed, content dirty 0. Nothing of substance changed --
this clears an artefact of my own capture tool so another stream's guard can
pass without accepting someone else's dirt.
"""
import unreal
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
if "L_InfinityStage_V1VerticalSlice" not in world.get_name():
    unreal.log_error("WRONG_WORLD|%s" % world.get_name())
    raise SystemExit
c = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
if c != 0:
    unreal.log_error("REFUSING|content dirty=%d -- not mine to save" % c)
    raise SystemExit

# The guard must live in the SAME script as the save. On 2026-09-28 this check
# lived in a separate script; between the check and the save another stream
# spawned 12 bench actors, and the save baked them into the level.
strays = [a.get_actor_label() for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
          if a.get_actor_label().startswith(("ZZ_", "TEMP_"))]
if strays:
    unreal.log_error("REFUSING|%d temporary actors present: %s" % (len(strays), strays))
    raise SystemExit
seq = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
if seq:
    unreal.log_error("REFUSING|a level sequence is open: %s" % seq.get_name())
    raise SystemExit
unreal.log("PRESAVE_GUARD_OK|content=0|strays=0|sequencer=closed")
ok = unreal.EditorLoadingAndSavingUtils.save_map(world, world.get_outermost().get_name())
a_c = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
a_m = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
unreal.log("FLAG_CLEARED|saved=%s|dirty now %d+%d" % (ok, a_c, a_m))
