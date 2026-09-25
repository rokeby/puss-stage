import json
import pathlib
import unreal

folder = pathlib.Path('E:/PussStage/Saved/CodexMocap')
template = unreal.load_asset('/Game/Metahuman/Shore1')
assert template is not None
fields = ['input_type', 'body_tracking', 'face_tracking', 'auto_body_height', 'body_height', 'body_detection_confidence',
          'body_tracking_confidence', 'enable_foot_locking', 'head_movement_mode', 'head_stabilization',
          'solve_type', 'skip_filtering', 'skip_per_vertex_solve', 'skip_preview', 'skip_tongue_solve',
          'easy_to_edit_control_curves', 'user_excluded_frames', 'start_frame_to_process', 'end_frame_to_process',
          'camera', 'visualization_object', 'show_frames_as_they_are_processed']
def simple(v):
    if v is None or isinstance(v, (bool, int, float, str)): return v
    if isinstance(v, unreal.Object): return v.get_path_name()
    if hasattr(v, 'export_text'): return v.export_text()
    try: return [simple(x) for x in v]
    except TypeError: return str(v)
result = {'template': template.get_path_name(), 'settings': {k:simple(template.get_editor_property(k)) for k in fields},
          'is_processing': template.is_processing(), 'can_process': template.can_process(),
          'contains_animation_data': template.contains_animation_data(),
          'processed_frames': template.get_number_of_processed_frames(), 'captures': []}
data = template.get_animation_data()
result['animation_array_count'] = len(data)
result['frame_data_doc'] = str(unreal.FrameAnimationData.__doc__) if hasattr(unreal, 'FrameAnimationData') else str(type(data[0]).__doc__)
if len(data):
    result['first_frame'] = simple(data[0])
    result['middle_frame'] = simple(data[min(500, len(data)-1)])
for stem in ['shoreguy1','shoreguy12','shoreguy3','shoreguy4','shoreguy5','shoreguy6','child1','child2']:
    path = f'/Game/CaptureManager/Imports/Mono_Video_Ingest/{stem}_1/CD_{stem}_1'
    if not unreal.EditorAssetLibrary.does_asset_exist(path):
        result['captures'].append({'stem': stem, 'missing': path})
        continue
    capture = unreal.load_asset(path)
    images = capture.get_editor_property('image_sequences')
    item = {'stem': stem, 'path': capture.get_path_name(), 'metadata': simple(capture.get_editor_property('metadata')), 'images': []}
    for media in images:
        image = {'asset':media.get_path_name(), 'class':media.get_class().get_path_name()}
        for attr in ['sequence_path', 'frame_rate_override', 'is_path_relative_to_project_root']:
            try: image[attr] = simple(media.get_editor_property(attr))
            except Exception as exc: image[attr] = str(exc)
        if hasattr(media, 'get_sequence_path'): image['absolute_sequence_path'] = media.get_sequence_path()
        item['images'].append(image)
    result['captures'].append(item)
api=[]
for cls in [unreal.MetaHumanPerformance, unreal.FootageCaptureData, unreal.ImgMediaSource, unreal.MetaHumanPerformanceExportUtils]:
    api.append(str(cls))
    for name in dir(cls):
        if any(s in name for s in ['frame','range','processing','animation','sequence','export','delegate']):
            api.append(name + ': ' + str(getattr(cls, name).__doc__))
api.append('ExportSkeleton: ' + str(unreal.PerformanceExportSkeleton.__doc__) + '\n' + str(dir(unreal.PerformanceExportSkeleton)))
api.append('Delegate: ' + str(type(template.get_editor_property('on_processing_finished_dynamic')).__doc__))
(folder/'details_api.txt').write_text('\n'.join(api), encoding='utf-8')
(folder/'batch_details.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
unreal.log('MOCAP_DETAILS_SUCCESS|template=' + template.get_path_name() + '|captures=' + str(len(result['captures'])))
