import json
import pathlib
import unreal
root='/Game/Metahuman/ShoreCast_20260910'
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assert not levels.is_in_play_in_editor()
unreal.LevelSequenceEditorBlueprintLibrary.pause()
for owned in [root+'/Review/LS_ShoreDrape_Pilot',root+'/Cloth/M_ShoreLinen']:
    assert unreal.EditorAssetLibrary.save_asset(owned,only_if_is_dirty=True)
assert levels.save_current_level()
dirty=list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
assert not dirty,[p.get_path_name() for p in dirty]
map_path=root+'/Review/L_ShoreDrape_AllSix'
seq_path=root+'/Review/LS_ShoreDrape_Gentle'
assert not unreal.EditorAssetLibrary.does_asset_exist(map_path)
assert not unreal.EditorAssetLibrary.does_asset_exist(seq_path)
assert levels.new_level(map_path)
cast=json.loads((folder/'shore_draped_cast_components.json').read_text(encoding='utf-8'))
selection={p['id']:p for p in json.loads((folder/'shore_gentle_motion_selection.json').read_text(encoding='utf-8'))['characters']}
floor=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(0,0,-1))
floor.set_actor_label('Draped Shore Review Floor')
floor.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Plane'))
floor.set_actor_scale3d(unreal.Vector(30,30,1))
for idx,(name,intensity,pitch,yaw) in enumerate([('Key',2.0,-35,145),('Fill',0.5,-20,-145),('Rim',1.0,-35,0)]):
    light=actors.spawn_actor_from_class(unreal.DirectionalLight,unreal.Vector(0,0,300),unreal.Rotator(pitch=pitch,yaw=yaw,roll=0))
    light.set_actor_label('Draped Shore '+name)
    light.light_component.set_editor_property('intensity',intensity)
    light.light_component.set_editor_property('forward_shading_priority',3-idx)
camera=actors.spawn_actor_from_class(unreal.CineCameraActor,unreal.Vector(1700,0,140),unreal.Rotator(pitch=-1.5,yaw=180,roll=0))
camera.set_actor_label('Draped Shore Group Camera')
cam=camera.get_cine_camera_component()
cam.set_editor_property('current_focal_length',35.0)
cam.set_editor_property('current_aperture',8.0)
film=cam.get_editor_property('filmback');film.sensor_width=36;film.sensor_height=20.25;cam.set_editor_property('filmback',film)
focus=cam.get_editor_property('focus_settings');focus.focus_method=unreal.CameraFocusMethod.DISABLE;cam.set_editor_property('focus_settings',focus)
pp=cam.get_editor_property('post_process_settings');pp.override_auto_exposure_method=True;pp.auto_exposure_method=unreal.AutoExposureMethod.AEM_MANUAL;pp.override_auto_exposure_apply_physical_camera_exposure=True;pp.auto_exposure_apply_physical_camera_exposure=False;pp.override_auto_exposure_bias=True;pp.auto_exposure_bias=-0.5;cam.set_editor_property('post_process_settings',pp)
seq=unreal.AssetToolsHelpers.get_asset_tools().create_asset('LS_ShoreDrape_Gentle',root+'/Review',unreal.LevelSequence,unreal.LevelSequenceFactoryNew())
seq.set_display_rate(unreal.FrameRate(30,1));seq.set_tick_resolution(unreal.FrameRate(24000,1));seq.set_playback_start(0);seq.set_playback_end(797)
rows=[]
for i,p in enumerate(cast):
    actor=actors.spawn_actor_from_class(unreal.load_asset(p['blueprint']).generated_class(),unreal.Vector(0,(i-2.5)*235,0),unreal.Rotator(pitch=0,yaw=-90,roll=0))
    actor.set_actor_label(p['id']+' Draped Review')
    body=next(c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()=='Body')
    cloth=actor.get_component_by_class(unreal.ChaosClothComponent)
    assert cloth.get_attach_parent()==body and str(cloth.get_attach_socket_name())=='head'
    ab=seq.add_possessable(actor);ab.set_display_name(p['id'])
    bb=seq.add_possessable(body);bb.set_parent(ab)
    section=bb.add_track(unreal.MovieSceneSkeletalAnimationTrack).add_section();section.set_range(0,797)
    section.set_completion_mode(unreal.MovieSceneCompletionMode.KEEP_STATE)
    params=section.get_editor_property('params')
    motion=selection[p['id']]
    params.animation=unreal.load_asset(motion['animation']);params.force_custom_mode=True
    params.start_frame_offset=unreal.FrameNumber(round(motion['selected']['start_seconds']*24000))
    rate=params.play_rate;rate.set_fixed_play_rate(motion['selected']['play_rate']);params.play_rate=rate
    section.set_editor_property('params',params)
    rows.append({'id':p['id'],'actor':actor.get_path_name(),'body':body.get_path_name(),'blueprint':p['blueprint'],'animation':motion['animation'],'start_seconds':motion['selected']['start_seconds'],'play_rate':motion['selected']['play_rate'],'cloth_socket':str(cloth.get_attach_socket_name()),'cloth_asset':cloth.get_asset().get_path_name()})
cb=seq.add_possessable(camera);cut=seq.add_track(unreal.MovieSceneCameraCutTrack).add_section();cut.set_range(0,797);cut.set_camera_binding_id(seq.get_binding_id(cb))
assert unreal.EditorAssetLibrary.save_loaded_asset(seq,only_if_is_dirty=False)
assert levels.save_current_level()
(folder/'shore_draped_review_manifest.json').write_text(json.dumps({'map':map_path,'sequence':seq.get_path_name(),'camera':camera.get_path_name(),'characters':rows,'source_preserved':True,'frame_rate':30,'duration_frames':797},indent=2),encoding='utf-8')
unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
unreal.LevelSequenceEditorBlueprintLibrary.play()
unreal.log('ALL_SIX_GENTLE_DRAPED_REVIEW_SAVED|characters=6|frames=797')
