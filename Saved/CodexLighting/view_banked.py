"""Put the viewport on the banked stretch of Passage 1, looking down the route."""
import unreal
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_editor_world().get_path_name().split(".",1)[0] == EXPECTED_WORLD, "wrong project"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
p1 = [a for a in sub.get_all_level_actors() if a.get_class().get_name() == "InfinityStagePassageActor" and a.get_actor_label().startswith("Passage 01")][0]
route = p1.get_editor_property("route"); L = route.get_spline_length()
d = L * 0.7
t = route.get_transform_at_distance_along_spline(d, unreal.SplineCoordinateSpace.WORLD, True)
loc = t.translation + t.rotation.rotate_vector(unreal.Vector(0.0, 0.0, 150.0))
ed.set_level_viewport_camera_info(loc, t.rotation.rotator())
unreal.log(f"BANKED_VIEW|dist={d:.0f}|roll={route.get_roll_at_distance_along_spline(d, unreal.SplineCoordinateSpace.WORLD):.2f}|loc={loc}")
