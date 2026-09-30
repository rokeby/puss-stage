"""Read-only: every camera and light within 90 m of Scene 3's dock, in the dock frame (x
ahead of the Entry Handoff Camera, y left/right, z up), against the planned box interior
(x 5-65 m, |y| < 10 m, z 0-30 m). A Scene 3 camera outside the box looking in would lose its
view to a wall. Mutates nothing."""
import unreal


def main():
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    cam = next(a for a in actors if a.get_actor_label().startswith("Scene 3 ") and "Entry Handoff Camera" in a.get_actor_label())
    dock = unreal.Transform(location=unreal.Vector(cam.get_actor_location().x, cam.get_actor_location().y, 0.0),
                            rotation=unreal.Rotator(0.0, 0.0, cam.get_actor_rotation().yaw))
    for a in actors:
        if not isinstance(a, (unreal.CameraActor, unreal.Light)):
            continue
        p = unreal.MathLibrary.inverse_transform_location(dock, a.get_actor_location())
        if -1000.0 < p.x < 9000.0 and abs(p.y) < 6000.0:
            r = a.get_actor_rotation()
            inside = 500.0 <= p.x <= 6500.0 and abs(p.y) < 1000.0 and 0.0 <= p.z <= 3000.0
            unreal.log(f"S3_NEAR|{a.get_class().get_name()}|{a.get_actor_label()}|dock=({p.x:.0f},{p.y:.0f},{p.z:.0f})|yaw={r.yaw:.1f}|pitch={r.pitch:.1f}|inside_box={inside}")
    unreal.log("S3_NEAR_OK")


main()
