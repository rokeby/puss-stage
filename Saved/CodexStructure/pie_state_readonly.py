"""Read-only, one line: is PIE running, is Sequencer open, what is dirty. Mutates nothing."""
import unreal

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
seq = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
unreal.log(f"EDITOR_STATE|pie={ed.get_game_world() is not None}|sequencer={seq.get_name() if seq else None}"
           f"|dirty={len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())}+{len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}")
