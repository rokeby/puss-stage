"""Read-only: P01's and P02's StructurePortal instances raw (mesh, bounds, instance transform). Mutates nothing."""
import unreal


def main():
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    rows = []
    for a in sub.get_all_level_actors():
        if isinstance(a, unreal.InfinityStageStructureActor) and a.get_actor_label()[-2:] in ("01", "02"):
            for comp in a.get_components_by_class(unreal.InstancedStaticMeshComponent):
                if comp.get_name().startswith("StructurePortal_"):
                    mesh = comp.get_editor_property("static_mesh")
                    bb = mesh.get_bounding_box()
                    rows.append(f"{a.get_actor_label()} {comp.get_name()} mesh={mesh.get_name()} bb=({bb.min.to_tuple()},{bb.max.to_tuple()}) n={comp.get_instance_count()}")
                    for i in range(min(comp.get_instance_count(), 8)):
                        t = comp.get_instance_transform(i, True)
                        rows.append(f"   i{i} loc={tuple(round(v, 1) for v in t.translation.to_tuple())} rot={tuple(round(v, 2) for v in (t.rotation.rotator().roll, t.rotation.rotator().pitch, t.rotation.rotator().yaw))} scale={tuple(round(v, 3) for v in t.scale3d.to_tuple())}")
    unreal.log("PORTAL_PIECES|" + " || ".join(rows))


main()
