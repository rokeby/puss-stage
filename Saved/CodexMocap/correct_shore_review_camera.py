import json
import pathlib
import unreal
folder = pathlib.Path('E:/PussStage/Saved/CodexMocap')
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert world.get_path_name().startswith('/Game/Metahuman/ShoreCast_20260910/Review/L_ShoreCast_Review.')
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
camera = next(a for a in actors if a.get_actor_label() == 'Shore Review Lineup Camera')
before = camera.get_actor_rotation().export_text()
camera.set_actor_location(unreal.Vector(2100, 0, 145), False, False)
camera.set_actor_rotation(unreal.Rotator(pitch=-1.5, yaw=180, roll=0), False)
cam = camera.get_cine_camera_component()
filmback = cam.get_editor_property('filmback')
filmback.sensor_width = 36.0
filmback.sensor_height = 20.25
cam.set_editor_property('filmback', filmback)
cam.set_editor_property('current_focal_length', 35.0)
for name, pitch, yaw in [('Key', -35, 145), ('Fill', -20, -145), ('Rim', -35, 0)]:
    light = next(a for a in actors if a.get_actor_label() == 'Shore Review ' + name)
    light.set_actor_rotation(unreal.Rotator(pitch=pitch, yaw=yaw, roll=0), False)
unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera.get_actor_location(), camera.get_actor_rotation())
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
poses = []
cast = json.loads((folder / 'shore_cast_assets.json').read_text(encoding='utf-8'))
for record in cast['characters']:
    actor = next(a for a in actors if a.get_actor_label().startswith(record['id'] + ' '))
    body = next(c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent)
                if c.get_skeletal_mesh_asset() and c.get_skeletal_mesh_asset().get_path_name() == record['body_mesh'])
    poses.append({'id': record['id'], 'actor_transform': actor.get_actor_transform().export_text(),
                  'bones': {bone: body.get_socket_transform(bone).export_text() for bone in ['pelvis', 'head', 'foot_l', 'foot_r']}})
(folder / 'shore_review_pose_frame0250.json').write_text(json.dumps(poses, indent=2), encoding='utf-8')
unreal.AutomationLibrary.take_high_res_screenshot(1920, 1080, str(folder / 'ShoreCast_Review_Upright_Frame0250.png'), camera=camera, delay=3.0)
unreal.log('SHORE_REVIEW_CAMERA_CORRECTED|' + before + ' -> ' + camera.get_actor_rotation().export_text())
