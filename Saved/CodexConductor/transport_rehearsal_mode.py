"""Set the Show Root transport to REHEARSAL: performance_mode OFF.

Gary, 2026-09-28: "Ok save that note and flip". He wants to walk the show by
hand tomorrow. The keys were always bound (Right/Left/Space, ShowGameMode.cpp
44-46); what refused was the live-performance interlock.

performance_mode True makes IsUnsafeExternalMove refuse ANY move out of a
segment declared DeclaredUnpausable -> result=4 UnsafeExternalClock. Measured
5 x Succeeded / 6 x result=4 in a PIE log.

auto_play_scene_after_passage is ALREADY True on this instance (the C++ default
is false), so it is NOT touched here.

*** THIS REMOVES A LIVE-PERFORMANCE SAFEGUARD. Set performance_mode back to
*** True before anything runs in front of an audience.
"""
import unreal

els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
if "L_InfinityStage_V1VerticalSlice" not in world.get_name():
    unreal.log_error("WRONG_WORLD|%s" % world.get_name())
    raise SystemExit

# The guard lives in the SAME script as the save (28 Sep: a separate check let
# another stream's bench actors get baked into the level between check and save).
strays = [a.get_actor_label() for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
          if a.get_actor_label().startswith(("ZZ_", "TEMP_"))]
if strays:
    unreal.log_error("REFUSING|%d temporary actors present: %s" % (len(strays), strays))
    raise SystemExit

c = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
m = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
if c != 0 or m != 0:
    unreal.log_error("REFUSING|dirty before: content=%d maps=%d -- not mine to save" % (c, m))
    raise SystemExit

roots = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot)
if len(roots) != 1:
    unreal.log_error("REFUSING|expected 1 show root, found %d" % len(roots))
    raise SystemExit
root = roots[0]
transport = root.get_editor_property("transport")

before_pm = transport.get_editor_property("performance_mode")
before_ap = transport.get_editor_property("auto_play_scene_after_passage")
unreal.log("FLIP|before|performance_mode=%s auto_play_scene_after_passage=%s" % (before_pm, before_ap))

if before_pm is False:
    unreal.log("FLIP|already off, nothing to do")
else:
    root.modify()
    transport.modify()
    transport.set_editor_property("performance_mode", False)

after_pm = transport.get_editor_property("performance_mode")
after_ap = transport.get_editor_property("auto_play_scene_after_passage")
unreal.log("FLIP|after|performance_mode=%s auto_play_scene_after_passage=%s" % (after_pm, after_ap))

if after_pm is not False:
    unreal.log_error("FLIP_FAILED|performance_mode still %s" % after_pm)
    raise SystemExit
if after_ap is not True:
    unreal.log_error("FLIP_FAILED|auto_play changed unexpectedly to %s" % after_ap)
    raise SystemExit

dirty_maps = unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
unreal.log("FLIP|dirty maps now: %s" % [p.get_name() for p in dirty_maps])
dirty_content = unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
if dirty_content:
    unreal.log_error("REFUSING_SAVE|content went dirty: %s" % [p.get_name() for p in dirty_content])
    raise SystemExit

saved = unreal.EditorLoadingAndSavingUtils.save_map(world, world.get_path_name().split('.')[0])
unreal.log("FLIP|save_map=%s" % saved)

unreal.log("FLIP|verify|performance_mode=%s" % transport.get_editor_property("performance_mode"))
unreal.log("FLIP|post dirty content=%d maps=%d" % (
    len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())))
unreal.log("PUSS_CONDUCTOR_REHEARSAL_MODE_SET")
