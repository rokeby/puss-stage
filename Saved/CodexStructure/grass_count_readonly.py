"""Read-only (30 Sep, the conductor's test): with both landscapes hidden, how much landscape grass exists? Per landscape:
GrassInstancedStaticMeshComponent count, how many hold instances, the total instance count, and how many are visible.
Hidden landscapes that still hold ~2,950 populated grass components means the hide does not stop grass generation,
so only the delete fixes it. Mutates nothing."""
import unreal


def main():
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    rows = []
    for a in sub.get_all_level_actors():
        if isinstance(a, unreal.LandscapeProxy):
            comps = list(a.get_components_by_class(unreal.GrassInstancedStaticMeshComponent)) if hasattr(unreal, "GrassInstancedStaticMeshComponent") \
                else [c for c in a.get_components_by_class(unreal.InstancedStaticMeshComponent) if "Grass" in c.get_class().get_name()]
            inst = [c.get_instance_count() for c in comps]
            rows.append(f"{a.get_actor_label()}: hidden={a.get_editor_property('hidden')} grass_components={len(comps)} populated={sum(1 for i in inst if i)} "
                        f"instances={sum(inst)} visible_components={sum(1 for c in comps if c.is_visible())}")
    unreal.log("GRASS_COUNT|" + " || ".join(rows))


main()
