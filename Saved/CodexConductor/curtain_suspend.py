"""Suspend the placed curtain's live sim. Transient per-instance state, no save.

Note: on ChaosClothComponent, suspend_simulation and is_simulation_suspended are
bool PROPERTIES, not methods -- calling them raises "'bool' object is not
callable". Use set_editor_property / plain attribute access.
"""
import unreal
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
b_c = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
b_m = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
done = 0
for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    if "Curtain" in a.get_actor_label():
        for comp in a.get_components_by_class(unreal.ActorComponent):
            if "Cloth" not in comp.get_class().get_name():
                continue
            for setter, val in (("suspend_simulation", True), ("simulate_in_editor", False)):
                try:
                    comp.set_editor_property(setter, val)
                except Exception as e:
                    unreal.log_error("SET_FAILED|%s|%s" % (setter, e))
            try:
                comp.set_simulate_in_editor(False)
            except Exception:
                pass
            done += 1
            unreal.log("SUSPENDED|%s|suspend=%s|sim_in_editor=%s" % (
                a.get_actor_label(),
                comp.get_editor_property("suspend_simulation"),
                comp.get_editor_property("simulate_in_editor")))
a_c = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
a_m = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
unreal.log("SUSPEND_DONE|%d|dirty %d+%d -> %d+%d" % (done, b_c, b_m, a_c, a_m))
