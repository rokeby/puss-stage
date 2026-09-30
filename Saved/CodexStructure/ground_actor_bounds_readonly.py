"""Read-only: world bounds and transform of the ground actors the hangar survey found. Mutates nothing."""
import unreal

LABELS = ("Passage 01 - Opening Floor", "Passage 01 - Opening Floor2", "Passage 05 - Floor (oak)")


def main():
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    rows = []
    for a in sub.get_all_level_actors():
        if a.get_actor_label() in LABELS:
            o, e = a.get_actor_bounds(False)
            rows.append(f"{a.get_actor_label()}: origin={tuple(round(v) for v in o.to_tuple())} extent={tuple(round(v) for v in e.to_tuple())} "
                        f"scale={a.get_actor_scale3d().to_tuple()} yaw={a.get_actor_rotation().yaw:.2f} attached={a.get_attach_parent_actor() is not None}")
    unreal.log("GROUND_BOUNDS|" + " || ".join(rows))


main()
