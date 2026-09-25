"""Create a separate one-character drape review stage, with actual body collision."""
import json
import pathlib
import unreal

root = '/Game/Metahuman/ShoreCast_20260910'
folder = pathlib.Path('E:/PussStage/Saved/CodexMocap')
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
map_path = root + '/Review/L_ShoreDrape_Pilot'
if editor.get_editor_world().get_path_name().split('.')[0] != map_path:
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
    assert not unreal.EditorAssetLibrary.does_asset_exist(map_path)
    unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
    assert levels.new_level(map_path)
existing = {a.get_actor_label(): a for a in actors.get_all_level_actors()}
floor = existing.get('Shore Drape Review Floor') or actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, -1))
floor.set_actor_label('Shore Drape Review Floor')
floor.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Plane'))
floor.set_actor_scale3d(unreal.Vector(12, 12, 1))
for name, intensity, pitch, yaw in [('Key', 2.0, -35, 145), ('Fill', 0.4, -20, -145), ('Rim', 1.0, -35, 0)]:
    light = existing.get('Shore Drape ' + name) or actors.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 400), unreal.Rotator(pitch=pitch, yaw=yaw, roll=0))
    light.set_actor_label('Shore Drape ' + name)
    light.light_component.set_editor_property('intensity', intensity)
    light.light_component.set_editor_property('light_source_angle', 5.0)
bp = unreal.load_asset(root + '/SceneCharacters/BP_Shore01_M56_Draped')
actor = existing.get('Shore01_M56 Drape Pilot') or actors.spawn_actor_from_class(bp.generated_class(), unreal.Vector(), unreal.Rotator(pitch=0, yaw=90, roll=0))
actor.set_actor_label('Shore01_M56 Drape Pilot')
body = next(c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == 'Body')
cloth = actor.get_component_by_class(unreal.ChaosClothComponent)
actor.call_method('ConfigureShoreDrape')
assert cloth.get_attach_parent() == body and str(cloth.get_attach_socket_name()) == 'head'
animation = unreal.load_asset(root + '/Animations/AS_Shore01_M56_shoreguy1_Full')
body.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
body.play_animation(animation, True)
body.set_play_rate(0.0)
body.set_position(10.0, False)
for component in actor.get_components_by_class(unreal.SkeletalMeshComponent):
    component.set_update_animation_in_editor(True)
actor.call_method('ConfigureShoreDrape')
cloth.set_simulate_in_editor(True)
camera = existing.get('Shore Drape Review Camera') or actors.spawn_actor_from_class(unreal.CineCameraActor, unreal.Vector(500, 0, 110), unreal.Rotator(pitch=-1.7, yaw=180, roll=0))
camera.set_actor_label('Shore Drape Review Camera')
cam = camera.get_cine_camera_component()
cam.set_editor_property('current_focal_length', 50.0)
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
pp.auto_exposure_bias = -0.5
cam.set_editor_property('post_process_settings', pp)
assert levels.save_current_level()
unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera.get_actor_location(), camera.get_actor_rotation())
levels.editor_set_game_view(True)
unreal.AutomationLibrary.take_high_res_screenshot(1440, 1080, str(folder / 'ShoreDrape_Pilot_Initial.png'), camera=camera, delay=8.0)
report = {'map': map_path, 'actor': actor.get_path_name(), 'body': body.get_path_name(), 'cloth': cloth.get_path_name(),
          'camera': camera.get_path_name(), 'animation_seconds': 10, 'cloth_simulation_in_editor': True,
          'cloth_relative_location': cloth.get_editor_property('relative_location').export_text()}
(folder / 'shore_drape_pilot_review.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
unreal.log('SHORE_DRAPE_PILOT_REVIEW_SAVED|' + json.dumps(report))
