"""Is P01's ground actually there? Read the structure actor, don't judge a frame."""
import unreal
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
ps = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStagePassageActor)
p1 = next((p for p in ps if "01" in p.get_actor_label()), ps[0])
route = next(iter(p1.get_components_by_class(unreal.SplineComponent)), None)
d = route.get_spline_length() * 0.30
here = route.get_location_at_distance_along_spline(d, unreal.SplineCoordinateSpace.WORLD)
unreal.log("PROBE_AT|x=%.0f y=%.0f z=%.0f" % (here.x, here.y, here.z))

structs = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
           if "Structure" in a.get_class().get_name()]
unreal.log("STRUCTURE_ACTORS|%d" % len(structs))
for s in structs:
    label = s.get_actor_label()
    total = 0
    near = 0
    for comp in s.get_components_by_class(unreal.InstancedStaticMeshComponent):
        n = comp.get_instance_count()
        total += n
        tags = ",".join([str(t) for t in comp.component_tags])
        mesh = comp.get_editor_property("static_mesh")
        mname = mesh.get_name() if mesh else "None"
        # Count instances within 3000 cm of the probe point, on any axis.
        hits = 0
        for i in range(min(n, 4000)):
            xf = comp.get_instance_transform(i, True)
            if xf is None:
                continue
            t = xf.translation
            if abs(t.x - here.x) < 3000 and abs(t.y - here.y) < 3000:
                hits += 1
        near += hits
        if hits:
            unreal.log("  NEAR|%s|tags=%s|mesh=%s|instances=%d|near_probe=%d" % (label, tags, mname, n, hits))
    unreal.log("STRUCTURE|%s|total_instances=%d|near_probe=%d" % (label, total, near))
