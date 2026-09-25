import json
import pathlib
import unreal
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
manifest=json.loads((folder/'shore_clam_integration.json').read_text(encoding='utf-8'))
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert not levels.is_in_play_in_editor()
assert world.get_path_name()==manifest['world']
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
for row in manifest['characters']:
    actor=next(a for a in actors if a.get_path_name()==row['actor'])
    actor.call_method('ConfigureShoreDrape')
    cloth=actor.get_component_by_class(unreal.ChaosClothComponent)
    cloth.set_simulate_in_editor(True);cloth.resume_simulation()
unreal.get_editor_subsystem(unreal.LayersSubsystem).set_layer_visibility('Shore_Retained_Mannys',False)
seq=unreal.load_asset(manifest['sequence'])
unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(300)
unreal.LevelSequenceEditorBlueprintLibrary.set_lock_camera_cut_to_viewport(False)
camera=next(a for a in actors if a.get_actor_label()=='Shore Cast Review Camera')
levels.pilot_level_actor(camera)
unreal.LevelSequenceEditorBlueprintLibrary.pause()
unreal.log('CLAM_SHORE_EDITOR_PREVIEW_ENABLED|six_cloths|review_camera|frame_300')
