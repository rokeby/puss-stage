import unreal
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
out = []
for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
    lab = str(a.get_actor_label())
    if lab.endswith("Hangar Root") and lab.startswith("S"):
        l, r = a.get_actor_location(), a.get_actor_rotation()
        out.append("%s loc=(%.1f,%.1f,%.1f) rpy=(%.1f,%.1f,%.1f)" % (lab, l.x, l.y, l.z, r.roll, r.pitch, r.yaw))
unreal.log("PROBE_ROOTS|" + " || ".join(sorted(out)))
