"""Read-only: each Passage route's tangent yaw at 0, 1, 2.5, 5 and 10 m from its start (how much a
drape yawed to the tangent would rotate if the tangent were sampled off the start). Mutates nothing."""
import unreal


def main():
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    rows = []
    for a in sorted((a for a in sub.get_all_level_actors() if isinstance(a, unreal.InfinityStageStructureActor)), key=lambda a: a.get_actor_label()):
        route = a.get_editor_property("passage").get_editor_property("route")
        yaws = [route.get_transform_at_distance_along_spline(d, unreal.SplineCoordinateSpace.WORLD, False).rotation.rotator().yaw for d in (0.0, 100.0, 250.0, 500.0, 1000.0)]
        rows.append(f"P{a.get_actor_label()[-2:]}:" + ",".join(f"{y:.3f}" for y in yaws))
    unreal.log("ROUTE_YAW|" + " ".join(rows))


main()
