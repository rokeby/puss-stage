"""Build a separate saved review map after the six assembled bodies are verified.

This is a staged helper, not a startup script. Nothing executes on import.
"""
import json
import math
import pathlib
import unreal


def run():
    project = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
    assert project == pathlib.Path('E:/PussStage').resolve()
    folder = project / 'Saved/CodexMocap'
    brief = json.loads((folder / 'shore_cast_brief.json').read_text(encoding='utf-8'))
    assembled = json.loads((folder / 'shore_cast_assets.json').read_text(encoding='utf-8'))
    fitted = json.loads((folder / 'shore_cast_fitted_animations.json').read_text(encoding='utf-8'))
    root = brief['output_root']
    records = {r['id']: r for r in assembled['characters']}
    animations = {r['id']: r for r in fitted['characters']}
    assert len(records) == len(animations) == 6
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert not editor.get_game_world(), 'PIE is active'
    dirty = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    dirty += list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    assert not dirty, 'Save scoped character assets before switching maps: ' + str(dirty)
    map_path = root + '/Review/L_ShoreCast_Review'
    seq_path = root + '/Review/LS_ShoreCast_AllSix'
    assert not unreal.EditorAssetLibrary.does_asset_exist(map_path), 'Review map already exists'
    assert not unreal.EditorAssetLibrary.does_asset_exist(seq_path), 'Review sequence already exists'
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    assert levels.new_level(map_path)
    world = editor.get_editor_world()
    assert world.get_path_name().split('.')[0] == map_path

    floor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, -1))
    floor.set_actor_label('Shore Review Floor')
    floor.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Plane'))
    floor.set_actor_scale3d(unreal.Vector(40, 40, 1))
    for name, intensity, rotation in [
            ('Key', 3.5, (-35, 145, 0)),
            ('Fill', 1.0, (-20, -145, 0)),
            ('Rim', 2.0, (-35, 0, 0))]:
        light = actors.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 300),
                                              unreal.Rotator(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]))
        light.set_actor_label('Shore Review ' + name)
        light.light_component.set_editor_property('intensity', intensity)
        light.light_component.set_editor_property('light_source_angle', 5.0)

    camera = actors.spawn_actor_from_class(unreal.CineCameraActor, unreal.Vector(2100, 0, 145),
                                           unreal.Rotator(pitch=-1.5, yaw=180, roll=0))
    camera.set_actor_label('Shore Review Lineup Camera')
    cam = camera.get_cine_camera_component()
    cam.set_editor_property('current_focal_length', 35.0)
    cam.set_editor_property('current_aperture', 8.0)
    filmback = cam.get_editor_property('filmback')
    filmback.sensor_width = 36.0
    filmback.sensor_height = 20.25
    cam.set_editor_property('filmback', filmback)
    focus = cam.get_editor_property('focus_settings')
    focus.focus_method = unreal.CameraFocusMethod.DISABLE
    cam.set_editor_property('focus_settings', focus)
    pp = cam.get_editor_property('post_process_settings')
    pp.override_auto_exposure_method = True
    pp.auto_exposure_method = unreal.AutoExposureMethod.AEM_MANUAL
    pp.override_auto_exposure_apply_physical_camera_exposure = True
    pp.auto_exposure_apply_physical_camera_exposure = False
    pp.override_auto_exposure_bias = True
    pp.auto_exposure_bias = 0.0
    cam.set_editor_property('post_process_settings', pp)
    sequence = asset_tools.create_asset('LS_ShoreCast_AllSix', root + '/Review', unreal.LevelSequence,
                                        unreal.LevelSequenceFactoryNew())
    sequence.set_display_rate(unreal.FrameRate(25, 1))
    sequence.set_tick_resolution(unreal.FrameRate(24000, 1))
    sequence.set_playback_start(0)
    sequence.set_playback_end(max(math.ceil((r['image_count'] - 1) * 25 / 30) for r in animations.values()))
    evidence = []
    for index, person in enumerate(brief['characters']):
        record, motion = records[person['id']], animations[person['id']]
        blueprint = unreal.load_asset(record['blueprint'])
        actor = actors.spawn_actor_from_class(blueprint.generated_class(),
                                               unreal.Vector(0, (index - 2.5) * 280.0, 0))
        actor.set_actor_label(person['id'] + ' — ' + person['take'])
        components = actor.get_components_by_class(unreal.SkeletalMeshComponent)
        body = next(c for c in components if c.get_skeletal_mesh_asset()
                    and c.get_skeletal_mesh_asset().get_path_name() == record['body_mesh'])
        animation = unreal.load_asset(motion['animation'])
        assert animation.get_editor_property('skeleton') == body.get_skeletal_mesh_asset().get_editor_property('skeleton')
        actor_binding = sequence.add_possessable(actor)
        actor_binding.set_display_name(person['id'])
        body_binding = sequence.add_possessable(body)
        body_binding.set_parent(actor_binding)
        body_binding.set_display_name('Body — ' + person['take'])
        track = body_binding.add_track(unreal.MovieSceneSkeletalAnimationTrack)
        section = track.add_section()
        # Range is end-exclusive; do not add a trailing frame that could loop the clip.
        review_end = math.ceil((motion['image_count'] - 1) * 25 / 30)
        section.set_range(0, review_end)
        section.set_completion_mode(unreal.MovieSceneCompletionMode.KEEP_STATE)
        params = section.get_editor_property('params')
        params.animation = animation
        params.force_custom_mode = True
        section.set_editor_property('params', params)
        evidence.append({'id': person['id'], 'actor': actor.get_path_name(), 'body': body.get_path_name(),
                         'animation': animation.get_path_name(), 'body_binding': str(body_binding.binding_id),
                         'start_frame': 0, 'end_exclusive': review_end,
                         'source_samples': motion['image_count'], 'source_fps': 30, 'review_fps': 25})
    camera_binding = sequence.add_possessable(camera)
    cut = sequence.add_track(unreal.MovieSceneCameraCutTrack).add_section()
    cut.set_range(0, sequence.get_playback_end())
    binding_id = sequence.get_binding_id(camera_binding)
    cut.set_camera_binding_id(binding_id)
    assert unreal.EditorAssetLibrary.save_loaded_asset(sequence, only_if_is_dirty=False)
    assert levels.save_current_level()
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(sequence)
    unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
    unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
    unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera.get_actor_location(), camera.get_actor_rotation())
    result = {'map': map_path, 'sequence': sequence.get_path_name(), 'camera': camera.get_path_name(),
              'display_rate': 25, 'tick_resolution': 24000, 'source_animation_speed': 1.0,
              'characters': evidence, 'saved': True, 'rendered_validation': 'pending'}
    (folder / 'shore_review_manifest.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    unreal.log('SHORE_REVIEW_MAP_AND_SEQUENCE_SAVED|characters=6')
