"""Finish and save the already-created review map after fixing the camera binding API."""
import json
import pathlib
import unreal

project = pathlib.Path('E:/PussStage')
folder = project / 'Saved/CodexMocap'
root = '/Game/Metahuman/ShoreCast_20260910'
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert world.get_path_name().split('.')[0] == root + '/Review/L_ShoreCast_Review'
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
sequence = unreal.load_asset(root + '/Review/LS_ShoreCast_AllSix')
cast = json.loads((folder / 'shore_cast_assets.json').read_text(encoding='utf-8'))
fitted = json.loads((folder / 'shore_cast_fitted_animations.json').read_text(encoding='utf-8'))
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
camera = next(a for a in actors if a.get_actor_label() == 'Shore Review Lineup Camera')
bindings = list(sequence.get_bindings())
camera_binding = next(b for b in bindings if camera in sequence.locate_bound_objects(b, world))
cuts = [t for t in sequence.get_tracks() if isinstance(t, unreal.MovieSceneCameraCutTrack)]
assert len(cuts) == 1 and len(cuts[0].get_sections()) == 1
cuts[0].get_sections()[0].set_camera_binding_id(sequence.get_binding_id(camera_binding))
evidence = []
for record, motion in zip(cast['characters'], fitted['characters']):
    assert record['id'] == motion['id']
    actor = next(a for a in actors if a.get_actor_label().startswith(record['id'] + ' '))
    body = next(c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent)
                if c.get_skeletal_mesh_asset() and c.get_skeletal_mesh_asset().get_path_name() == record['body_mesh'])
    bound = next(b for b in bindings if body in sequence.locate_bound_objects(b, world))
    tracks = [t for t in bound.get_tracks() if isinstance(t, unreal.MovieSceneSkeletalAnimationTrack)]
    assert len(tracks) == 1 and len(tracks[0].get_sections()) == 1
    section = tracks[0].get_sections()[0]
    assert section.get_editor_property('params').animation.get_path_name() == motion['animation']
    evidence.append({'id': record['id'], 'actor': actor.get_path_name(), 'body': body.get_path_name(),
                     'animation': motion['animation'], 'body_binding': unreal.GuidLibrary.conv_guid_to_string(bound.get_id()),
                     'source_samples': motion['image_count'], 'source_fps': 30, 'review_fps': 25})
assert unreal.EditorAssetLibrary.save_loaded_asset(sequence, only_if_is_dirty=False)
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(sequence)
unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(250)
unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera.get_actor_location(), camera.get_actor_rotation())
report = {'map': world.get_path_name().split('.')[0], 'sequence': sequence.get_path_name(), 'camera': camera.get_path_name(),
          'display_rate': 25, 'tick_resolution': 24000, 'source_animation_speed': 1.0,
          'characters': evidence, 'saved': True, 'rendered_validation': 'pending'}
(folder / 'shore_review_manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
(folder / 'shore_review_build_status.json').write_text(json.dumps({'state': 'complete'}), encoding='utf-8')
unreal.AutomationLibrary.take_high_res_screenshot(1920, 1080, str(folder / 'ShoreCast_Review_Frame0250.png'), camera=camera, delay=2.0)
unreal.log('SHORE_REVIEW_MAP_AND_SEQUENCE_SAVED|characters=6|camera_binding_verified=1')
