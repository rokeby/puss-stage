"""READ-ONLY (30 Sep): what is dirty right now, and is anything mid-operation? Before a restart for the stutter test.
Dirty packages by name, Sequencer, PIE, ZZ_/TEMP_ and capture components (GameplayStatics census). Mutates nothing."""
import unreal


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    content = [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    maps = [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    seq = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
    all_actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
    temps = [a.get_actor_label() for a in all_actors if a.get_actor_label().startswith(("ZZ_", "TEMP_"))]
    caps = [a.get_actor_label() for a in all_actors if a.get_components_by_class(unreal.SceneCaptureComponent2D)]
    unreal.log(f"EDITOR_STATE|world={world.get_path_name().split('.')[0]}|pie={ed.get_game_world() is not None}|dirty_content={content}|dirty_maps={maps}"
               f"|sequencer={seq.get_path_name() if seq else None}|temps={temps}|capture_actors={caps}")


main()
