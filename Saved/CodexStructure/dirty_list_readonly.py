"""Read-only, one line: which packages are dirty right now. Mutates nothing."""
import unreal

c = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
m = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
seq = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
zz = [a.get_actor_label() for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if a.get_actor_label().startswith("ZZ_")]
unreal.log(f"DIRTY_LIST|content={c}|maps={m}|pie={ed.get_game_world() is not None}|sequencer={seq.get_name() if seq else None}|zz={zz}")
