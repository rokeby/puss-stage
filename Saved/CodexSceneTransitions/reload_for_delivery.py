import json
import pathlib
import unreal
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert editor.get_game_world() is None
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
target='/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice'
assert levels.load_level(target)
root=next(a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if isinstance(a,unreal.InfinityStageShowRoot))
assert root.transport.auto_play_scene_after_passage
show=root.show_asset
assert len([c for c in show.cues if c.type!=unreal.InfinityCueType.WING_PAIR])==13
assert all(c.scene.use_sequence_length for c in show.cues if c.type!=unreal.InfinityCueType.WING_PAIR)
unreal.log('SCENE_TRANSITION_SAVED_LEVEL_RELOAD_SUCCESS|auto_scene=1|sequence_length_cues=13|pie=0')
