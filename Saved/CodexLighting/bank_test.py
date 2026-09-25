"""Bank Passage 1's route so the machine rolls as you travel. No save; revert recorded."""
import json, os, unreal
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ROLL_DEGREES = float(os.environ.get("PUSS_BANK_DEG", "20"))
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world(); assert world, "no world"
assert world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
assert ed.get_game_world() is None, "PIE active"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
p1 = [a for a in sub.get_all_level_actors() if a.get_class().get_name() == "InfinityStagePassageActor" and a.get_actor_label().startswith("Passage 01")][0]
route = p1.get_editor_property("route")
n = route.get_number_of_spline_points()
def rot(r): return [round(r.pitch, 3), round(r.yaw, 3), round(r.roll, 3)]
# Idempotent: normalise to a level, auto-fitted route first, so re-running never
# records an already-banked state as the baseline.
p1.modify(); route.modify()
for i in range(n):
    b = route.get_rotation_at_spline_point(i, unreal.SplineCoordinateSpace.LOCAL)
    route.set_up_vector_at_spline_point(i, unreal.Vector(0.0, 0.0, 1.0),
                                        unreal.SplineCoordinateSpace.LOCAL, True)
p1.set_editor_property("auto_fit_straight_route", True)
before = {"auto_fit": bool(p1.get_editor_property("auto_fit_straight_route")),
          "rotations": [rot(route.get_rotation_at_spline_point(i, unreal.SplineCoordinateSpace.LOCAL)) for i in range(n)]}
p1.modify(); route.modify()
# Auto-fit rewrites the route as a straight line on materialize, which would
# discard any authored bank.
p1.set_editor_property("auto_fit_straight_route", False)
# Roll ramps from level at the entry to ROLL_DEGREES at the far end; the spline
# interpolates between, so the whole machine banks progressively as you travel.
# Banking a spline is done with the up vector, not by writing a rotation: the
# frame's up is what GetTransformAtDistanceAlongSpline resolves roll from.
import math
for i in range(n):
    t = i / max(1, n - 1)
    a = math.radians(ROLL_DEGREES * t)
    route.set_up_vector_at_spline_point(
        i, unreal.Vector(0.0, -math.sin(a), math.cos(a)),
        unreal.SplineCoordinateSpace.LOCAL, True)
route.update_spline()
length = route.get_spline_length()
after = {"rotations": [rot(route.get_rotation_at_spline_point(i, unreal.SplineCoordinateSpace.LOCAL)) for i in range(n)],
         "roll_along_route": [round(route.get_roll_at_distance_along_spline(length * f, unreal.SplineCoordinateSpace.WORLD), 2)
                              for f in (0.0, 0.25, 0.5, 0.75, 1.0)]}
assert p1.materialize_passage(), "materialize failed"
after["materialized_pairs"] = int(p1.get_editor_property("materialized_wing_pair_count"))
# Frame the show camera part-way along so the bank is visible
rigs = [a for a in sub.get_all_level_actors() if a.get_class().get_name() == "InfinityStageCameraRig" and a.get_actor_label().startswith("Passage 01")]
if rigs:
    c = rigs[0].get_editor_property("camera")
    ed.set_level_viewport_camera_info(c.get_world_location(), c.get_world_rotation())
d = {"content": [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
     "maps": [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
json.dump({"before": before, "after": after, "roll_degrees": ROLL_DEGREES, "dirty": d},
          open(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting", "bank_test.json"), "w"), indent=1)
unreal.log(f"BANK_TEST|roll={ROLL_DEGREES}|points={n}|before={before['rotations']}|roll_along_route={after['roll_along_route']}|pairs={after['materialized_pairs']}|saved=0")
