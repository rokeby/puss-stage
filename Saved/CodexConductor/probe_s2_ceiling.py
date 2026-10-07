import unreal
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
out = []
for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.StaticMeshActor):
    sm = a.static_mesh_component.static_mesh
    if not sm or sm.get_name() != "SM_S2_ceiling_wing":
        continue
    b = sm.get_bounding_box()
    mats = [str(m.get_name()) if m else None for m in a.static_mesh_component.get_materials()]
    out.append("%s|mesh_local_min=(%.0f,%.0f,%.0f)|max=(%.0f,%.0f,%.0f)|nmat=%d|%s" % (a.get_actor_label(), b.min.x, b.min.y, b.min.z, b.max.x, b.max.y, b.max.z, len(mats), mats[:3]))
    if len([o for o in out if "ceiling" in o]) > 1: break
cams = []
for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.CineCameraActor):
    if a.get_outermost().get_name().endswith("Japanese_Alley"):
        l, r = a.get_actor_location(), a.get_actor_rotation()
        cams.append("%s@(%.0f,%.0f,%.0f) yaw %.1f" % (a.get_actor_label(), l.x, l.y, l.z, r.yaw))
unreal.log("PROBE_S2C|" + " || ".join(out) + " || CAMS: " + "; ".join(cams[:6]))
