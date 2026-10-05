"""READ-ONLY: where is SM_lily_01_1 (floor DRY says it stands on the old slab top)."""
import unreal
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if str(a.get_actor_label()).startswith("SM_lily"):
        o, e = a.get_actor_bounds(False)
        par = a.get_attach_parent_actor()
        unreal.log("PROBE_LILY|%s|loc=%s|zmin=%.1f|zmax=%.1f|folder=%s|parent=%s|hidden=%s" % (
            a.get_actor_label(), a.get_actor_location(), o.z - e.z, o.z + e.z, a.get_folder_path(),
            par.get_actor_label() if par else None, a.get_editor_property("hidden")))
