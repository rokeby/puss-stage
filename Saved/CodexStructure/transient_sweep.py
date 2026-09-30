"""Find (and with SWEEP_DESTROY destroy) actors whose label starts with ZZ_, INCLUDING transient ones, which
EditorActorSubsystem.get_all_level_actors() does not list (Look & camera, 30 Sep): GameplayStatics sees them.
Reports each actor's class and whether a scene capture captures every frame. Saves nothing."""
import unreal


def main():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    listed = {a.get_actor_label() for a in sub.get_all_level_actors()}
    found = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor) if a.get_actor_label().startswith("ZZ_")]
    rows = []
    for a in found:
        cap = a.get_component_by_class(unreal.SceneCaptureComponent2D)
        rows.append(f"{a.get_actor_label()} [{a.get_class().get_name()}] listed_by_editor={a.get_actor_label() in listed} "
                    f"every_frame={cap.get_editor_property('capture_every_frame') if cap else None}")
    destroy = bool(globals().get("SWEEP_DESTROY"))
    if destroy:
        for a in found:
            sub.destroy_actor(a)
    left = [a.get_actor_label() for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor) if a.get_actor_label().startswith("ZZ_")]
    d = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
    unreal.log(f"TRANSIENT_SWEEP|found={len(found)}|destroyed={destroy}|left={left}|dirty={d[0]}+{d[1]}|" + " || ".join(rows))


main()
