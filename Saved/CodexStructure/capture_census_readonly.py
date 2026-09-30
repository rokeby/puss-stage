"""Read-only census (30 Sep) of every component that re-renders the scene on its own: SceneCaptureComponent2D/Cube,
PlanarReflectionComponent and ReflectionCaptureComponent, on EVERY actor including TRANSIENT ones (found through
GameplayStatics.get_all_actors_of_class, which sees what EditorActorSubsystem.get_all_level_actors() cannot).
Reports the owner, whether the editor's actor list sees it, and capture_every_frame / capture_on_movement where the
component has them. Answers whether the stutter's "zero SceneCapture actors" exclusion holds. Mutates nothing."""
import unreal


def main():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    listed = set(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    kinds = [k for k in ("SceneCaptureComponent2D", "SceneCaptureComponentCube", "PlanarReflectionComponent", "ReflectionCaptureComponent")
             if hasattr(unreal, k)]
    rows, total = [], 0
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
        for k in kinds:
            for c in a.get_components_by_class(getattr(unreal, k)):
                total += 1
                info = f"{a.get_actor_label()} [{a.get_class().get_name()}] {k} listed={a in listed}"
                for prop in ("capture_every_frame", "capture_on_movement"):
                    try:
                        info += f" {prop}={c.get_editor_property(prop)}"
                    except Exception:  # noqa: BLE001
                        pass
                rows.append(info)
    unreal.log(f"CAPTURE_CENSUS|components={total}|" + " || ".join(rows[:40]))


main()
