"""Undo the bank test from bank_test.json."""
import json, os, unreal
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting")
rec = json.load(open(os.path.join(OUT, "bank_test.json"), encoding="utf-8"))["before"]
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
p1 = [a for a in sub.get_all_level_actors() if a.get_class().get_name() == "InfinityStagePassageActor" and a.get_actor_label().startswith("Passage 01")][0]
route = p1.get_editor_property("route"); p1.modify(); route.modify()
# The bank was applied with up vectors, so that is what must be cleared.
for i in range(route.get_number_of_spline_points()):
    route.set_up_vector_at_spline_point(i, unreal.Vector(0.0, 0.0, 1.0), unreal.SplineCoordinateSpace.LOCAL, True)
route.update_spline()
p1.set_editor_property("auto_fit_straight_route", rec["auto_fit"])
assert p1.materialize_passage(), "materialize failed"
L = route.get_spline_length()
rolls = [round(route.get_roll_at_distance_along_spline(L*f, unreal.SplineCoordinateSpace.WORLD), 2) for f in (0.0,0.25,0.5,0.75,1.0)]
unreal.log(f"BANK_REVERTED|auto_fit={rec['auto_fit']}|roll_along_route={rolls}")
