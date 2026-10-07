import unreal, re
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
pat = re.compile(r"wing|leaf|leaves|border|ceiling|foliage|canopy|valance", re.I)
rows = []
for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.StaticMeshActor):
    lvl = a.get_outermost().get_name().split('/')[-1]
    sm = a.static_mesh_component.static_mesh
    mn = sm.get_name() if sm else ""
    lab = str(a.get_actor_label())
    if lvl != "Japanese_Alley" and not lab.startswith("S2"):
        continue
    if not (pat.search(lab) or pat.search(mn)):
        continue
    loc, rot, sc = a.get_actor_location(), a.get_actor_rotation(), a.get_actor_scale3d()
    p = a.get_attach_parent_actor()
    rows.append("%s|%s|lvl=%s|loc=(%.0f,%.0f,%.0f)|rpy=(%.1f,%.1f,%.1f)|scl=(%.2f,%.2f,%.2f)|parent=%s" % (
        lab, mn, lvl, loc.x, loc.y, loc.z, rot.roll, rot.pitch, rot.yaw, sc.x, sc.y, sc.z, p.get_actor_label() if p else None))
unreal.log("PROBE_S2W|n=%d|%s" % (len(rows), " || ".join(rows[:80])))
