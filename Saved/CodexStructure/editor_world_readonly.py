"""Read-only: which world the editor holds, PIE state, actor count, dirty set."""
import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w = ed.get_editor_world()
g = ed.get_game_world()
n = len(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
c = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
m = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
unreal.log(f"EDITOR_WORLD|editor={w.get_path_name() if w else None}|game={g.get_path_name() if g else None}|actors={n}|dirty={c}+{m}")
