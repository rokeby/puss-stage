import builtins
import json
import pathlib
import unreal
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
manifest=json.loads((folder/'shore_clam_integration.json').read_text(encoding='utf-8'))
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not levels.is_in_play_in_editor()
assert not hasattr(builtins,'PUSS_CLAM_SHORE_QC_HANDLE')
assert not hasattr(builtins,'PUSS_CLAM_SHORE_RUNTIME_HANDLE')
assert builtins.PUSS_SHORE_CLOSEUP_TASK.is_task_done()
unreal.LevelSequenceEditorBlueprintLibrary.pause();unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
camera=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='Shore Cast Review Camera')
if hasattr(builtins,'PUSS_SHORE_REVIEW_CAMERA_RESTORE'):
    transform,lens=builtins.PUSS_SHORE_REVIEW_CAMERA_RESTORE
    camera.set_actor_transform(transform,False,True)
    camera.get_cine_camera_component().set_editor_property('current_focal_length',lens)
    del builtins.PUSS_SHORE_REVIEW_CAMERA_RESTORE
assert levels.save_current_level()
dirty=list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
assert not dirty,[p.get_path_name() for p in dirty]
assert levels.load_level(manifest['world'].split('.')[0])
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
all_actors=actors.get_all_level_actors()
seq=unreal.load_asset(manifest['sequence'])
rows=[]
for row in manifest['characters']:
    a=next(a for a in all_actors if a.get_path_name()==row['actor'])
    body=next(c for c in a.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()=='Body')
    cloth=a.get_component_by_class(unreal.ChaosClothComponent)
    assert cloth.get_attach_parent()==body and str(cloth.get_attach_socket_name())=='head',row['id']+' saved attachment'
    assert cloth.get_asset().get_path_name()==row['cloth']
    b=next(b for b in seq.get_bindings() if unreal.GuidLibrary.conv_guid_to_string(b.get_id())==row['body_binding'])
    bound=seq.locate_bound_objects(b,world)
    assert len(bound)==1 and bound[0].get_path_name()==body.get_path_name()
    tracks=b.get_tracks();assert len(tracks)==1
    params=tracks[0].get_sections()[0].get_editor_property('params')
    assert params.animation.get_path_name()==row['animation']
    assert abs(params.play_rate.to_fixed_play_rate()-row['play_rate'])<1e-5
    a.call_method('ConfigureShoreDrape');cloth.set_simulate_in_editor(True);cloth.resume_simulation()
    rows.append({'id':row['id'],'actor':a.get_path_name(),'cloth_asset':cloth.get_asset().get_path_name(),'socket':str(cloth.get_attach_socket_name()),'animation':params.animation.get_path_name(),'play_rate':params.play_rate.to_fixed_play_rate(),'serialized_start_pose':body.get_editor_property('animation_data').export_text()})
for row in manifest['retained_originals']:
    a=next(a for a in all_actors if a.get_path_name()==row['actor'])
    assert a.get_editor_property('hidden')
    assert 'Shore_Retained_Mannys' in [str(n) for n in a.get_editor_property('layers')]
unreal.get_editor_subsystem(unreal.LayersSubsystem).set_layer_visibility('Shore_Retained_Mannys',False)
camera=next(a for a in all_actors if a.get_actor_label()=='Shore Cast Review Camera')
unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(300)
unreal.LevelSequenceEditorBlueprintLibrary.set_lock_camera_cut_to_viewport(False)
levels.pilot_level_actor(camera)
out={'status':'passed','world':world.get_path_name(),'verified_after_map_reload':True,'characters':rows,'retained_originals_hidden_in_game':4,'originals_editor_layer':'Shore_Retained_Mannys','editor_layer_visibility_refreshed':True,'editor_preview_note':'Editor cloth simulation and layer visibility are session state; run enable_clam_shore_preview.py after reopening for the same editing view. Game hiding and BeginPlay attachment are serialized.','camera':camera.get_path_name()}
(folder/'shore_clam_saved_delivery_audit.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
unreal.log('SHORE_CLAM_SAVED_DELIVERY_RELOAD_VERIFIED|six_characters|six_correct_body_bindings|six_head_drapes|four_originals_hidden')
