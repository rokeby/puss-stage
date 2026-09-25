import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
p1 = [a for a in sub.get_all_level_actors() if a.get_class().get_name()=="InfinityStagePassageActor" and a.get_actor_label().startswith("Passage 01")][0]
route = p1.get_editor_property("route"); L = route.get_spline_length()
t = route.get_transform_at_distance_along_spline(L*0.12, unreal.SplineCoordinateSpace.WORLD, True)
loc = t.translation + unreal.Vector(0,0,260)
rot = unreal.Rotator(pitch=14.0, yaw=t.rotation.rotator().yaw, roll=0.0)
ed.set_level_viewport_camera_info(loc, rot)
unreal.log(f"GRIDIRON_VIEW|loc={loc}|looking_up_at_grid")
