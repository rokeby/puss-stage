"""Read-only inspection of the installed Sequencer and preview APIs."""
import pathlib
import unreal

project = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
assert project == pathlib.Path('E:/PussStage').resolve()
names = {
    'LevelSequence': ['add_possessable', 'add_spawnable_from_instance', 'set_display_rate', 'set_playback_start', 'set_playback_end', 'add_track'],
    'MovieSceneBindingProxy': ['set_parent', 'add_track', 'set_display_name', 'get_tracks'],
    'MovieSceneSkeletalAnimationSection': ['set_range', 'set_completion_mode', 'get_editor_property'],
    'MovieSceneSkeletalAnimationParams': [],
    'LevelSequenceEditorBlueprintLibrary': ['open_level_sequence', 'set_current_time', 'set_current_time_seconds', 'refresh_current_level_sequence'],
    'LevelEditorSubsystem': ['new_level', 'load_level', 'save_current_level', 'set_current_level_by_name'],
    'EditorActorSubsystem': ['spawn_actor_from_class', 'destroy_actor', 'get_all_level_actors', 'set_selected_level_actors'],
    'EditorLevelLibrary': ['set_level_viewport_camera_info', 'get_level_viewport_camera_info', 'editor_set_game_view'],
    'AutomationLibrary': ['take_high_res_screenshot', 'finish_loading_before_screenshot'],
    'SkeletalMeshComponent': ['set_animation_mode', 'set_animation', 'set_position', 'play_animation', 'get_bone_location', 'get_bone_transform'],
    'CineCameraComponent': ['set_current_focal_length', 'set_current_aperture'],
    'MovieSceneCameraCutSection': ['set_camera_binding_id'],
    'MovieSceneObjectBindingID': [],
}
lines = []
for name, methods in names.items():
    cls = getattr(unreal, name, None)
    if not cls:
        lines.append(name + ': UNAVAILABLE')
        continue
    lines += [name, str(cls.__doc__)]
    for method in methods:
        lines += [method, str(getattr(cls, method, None).__doc__)]
(project / 'Saved/CodexMocap/preview_api.txt').write_text('\n\n'.join(lines), encoding='utf-8')
unreal.log('SHORE_PREVIEW_API_INSPECT_SUCCESS')
