import datetime, json, pathlib
import unreal

RUN_DIR = pathlib.Path('E:/PussStage/Saved/CodexMocap')
ROOT = '/Game/Metahuman/FullTakes_20260910'
TEMPLATE = '/Game/Metahuman/Shore1'
STEMS = ['shoreguy1','shoreguy12','shoreguy3','shoreguy4','shoreguy5','shoreguy6','child1','child2']
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert editor.get_game_world() is None
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
template = unreal.load_asset(TEMPLATE)
assert template and not template.is_processing()
assert template.get_editor_property('body_tracking') and not template.get_editor_property('face_tracking')
assert template.contains_animation_data_type(unreal.FrameAnimationDataType.BODY)
FIELDS = ['body_tracking','face_tracking','auto_body_height','body_height','body_detection_confidence',
          'body_tracking_confidence','enable_foot_locking','head_movement_mode','head_stabilization',
          'solve_type','skip_filtering','skip_per_vertex_solve','skip_preview','skip_tongue_solve',
          'easy_to_edit_control_curves','user_excluded_frames','visualization_object','show_skeleton',
          'skeleton_offset','skeleton_color','show_frames_as_they_are_processed','timecode_alignment',
          'skip_diagnostics','mono_smoothing_params','monocular_animation_pipeline_models',
          'head_allowed_rotation_left_right','head_allowed_rotation_up_down','head_rotation_handler',
          'auto_choose_head_movement_reference_frame','neutral_pose_calibration_enabled',
          'neutral_pose_calibration_alpha','neutral_pose_calibration_curves']
def encode(v):
    if v is None or isinstance(v,(bool,int,float,str)): return v
    if isinstance(v,unreal.Object): return v.get_path_name()
    if hasattr(v,'export_text'): return v.export_text()
    try: return [encode(x) for x in v]
    except TypeError: return str(v)
settings = {name:template.get_editor_property(name) for name in FIELDS}
manifest = {'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'root':ROOT,
            'template':template.get_path_name(), 'settings':{k:encode(v) for k,v in settings.items()}, 'jobs':[]}
probe=json.loads((RUN_DIR/'frame_probe.json').read_text(encoding='utf-8'))
captures={c['stem']:c for c in probe['captures']}
tools=unreal.AssetToolsHelpers.get_asset_tools()
for stem in STEMS:
    source=captures[stem]
    assert not source.get('missing')
    capture=unreal.load_asset(source['capture'])
    assert capture
    name=f'MHP_{stem}_Full'
    path=f'{ROOT}/Performances/{name}'
    assert not unreal.EditorAssetLibrary.does_asset_exist(path), 'Output already exists: '+path
    p=tools.create_asset(name,f'{ROOT}/Performances',unreal.MetaHumanPerformance,unreal.MetaHumanPerformanceFactoryNew())
    assert p
    p.set_editor_property('input_type',unreal.DataInputType.MONO_FOOTAGE)
    p.set_editor_property('footage_capture_data',capture)
    for key,val in settings.items():
        p.set_editor_property(key,val)
    # Request the complete available video range; engine clamps to its source limits.
    p.set_processing_range(0,2147483647)
    actual_start=p.get_editor_property('start_frame_to_process')
    actual_end=p.get_editor_property('end_frame_to_process')
    differences={key:[encode(val),encode(p.get_editor_property(key))] for key,val in settings.items()
                 if encode(val)!=encode(p.get_editor_property(key))}
    assert not differences, str(differences)
    assert p.can_process(), 'Cannot process '+path
    assert actual_end > actual_start
    assert unreal.EditorAssetLibrary.save_loaded_asset(p,only_if_is_dirty=False)
    manifest['jobs'].append({'stem':stem,'capture':capture.get_path_name(),'performance':p.get_path_name(),
                             'image_count':source['image_count'],'media_directory':source['directory'],
                             'start':actual_start,'end_exclusive':actual_end,'state':'queued'})
    (RUN_DIR/'batch_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(RUN_DIR/'verification_api.txt').write_text(str(unreal.EditorLoadingAndSavingUtils.reload_packages.__doc__)+'\n'+str(unreal.AnimSequence.__doc__),encoding='utf-8')
unreal.log('MOCAP_BATCH_PREPARE_SUCCESS|' + json.dumps({'jobs':len(manifest['jobs']),'ranges':[(j['stem'],j['start'],j['end_exclusive'],j['image_count']) for j in manifest['jobs']]}))
