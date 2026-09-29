"""READ-ONLY: report the Show Root's transport flags and their real Python names.

Gary asked for bPerformanceMode off and bAutoPlaySceneAfterPassage on, so the
show can be walked by hand tomorrow. Inspect before writing: UE 5.8 renames
bool properties and guessing the name is how earlier passes failed.
"""
import unreal

els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
if "L_InfinityStage_V1VerticalSlice" not in world.get_name():
    unreal.log_error("WRONG_WORLD|%s" % world.get_name())
    raise SystemExit

roots = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot)
unreal.log("PROBE|show_roots=%d" % len(roots))
if not roots:
    unreal.log_error("NO_SHOW_ROOT")
    raise SystemExit

root = roots[0]
unreal.log("PROBE|root_label=%s" % root.get_actor_label())

transport = None
for name in ("transport", "Transport"):
    try:
        transport = root.get_editor_property(name)
        if transport:
            unreal.log("PROBE|transport_via=%s class=%s" % (name, transport.get_class().get_name()))
            break
    except Exception as exc:
        unreal.log("PROBE|no_property_%s|%s" % (name, exc))

if transport is None:
    for comp in root.get_components_by_class(unreal.ActorComponent):
        unreal.log("PROBE|component=%s class=%s" % (comp.get_name(), comp.get_class().get_name()))
    unreal.log_error("TRANSPORT_NOT_FOUND")
    raise SystemExit

# Report every bool-ish property name the class actually exposes.
for cand in ("performance_mode", "b_performance_mode", "bPerformanceMode",
             "auto_play_scene_after_passage", "b_auto_play_scene_after_passage",
             "bAutoPlaySceneAfterPassage"):
    try:
        val = transport.get_editor_property(cand)
        unreal.log("PROBE|FOUND|%s=%s" % (cand, val))
    except Exception:
        pass

unreal.log("PROBE|dirty_content=%d dirty_maps=%d" % (
    len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())))
unreal.log("PUSS_CONDUCTOR_TRANSPORT_PROBE_OK")
