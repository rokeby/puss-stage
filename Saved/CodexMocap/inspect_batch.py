import json
import os
import pathlib
import unreal

out = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / 'CodexMocap'
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert editor.get_game_world() is None, 'PIE/SIE active'
assert pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve() == pathlib.Path('E:/PussStage').resolve()

def value(item):
    if item is None or isinstance(item, (str, int, float, bool)):
        return item
    if isinstance(item, unreal.Object):
        return item.get_path_name()
    try:
        return [value(v) for v in item]
    except TypeError:
        return str(item)

def props(obj, names):
    result = {}
    for name in names:
        try:
            result[name] = value(obj.get_editor_property(name))
        except Exception as exc:
            result[name] = {'unavailable': str(exc)}
    return result

def assets_of(cls):
    path = cls.static_class().get_path_name()
    package, name = path.rsplit('.', 1)
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    return [a.get_asset() for a in registry.get_assets_by_class(unreal.TopLevelAssetPath(package, name), True)]

performances = assets_of(unreal.MetaHumanPerformance)
captures = assets_of(unreal.FootageCaptureData)
names = ['input_type', 'footage_capture_data', 'body_tracking', 'facial_tracking', 'head_movement_mode',
         'visualization_object', 'start_frame_to_process', 'end_frame_to_process', 'processing_ranges',
         'body_tracker_mode', 'body_tracking_parameters', 'user_excluded_frames', 'solve_type']
result = {
    'pid': os.getpid(), 'engine': unreal.SystemLibrary.get_engine_version(),
    'project': unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()),
    'world': editor.get_editor_world().get_path_name(),
    'dirty_content': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
    'dirty_maps': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
    'performances': [{'path': p.get_path_name(), 'properties': props(p, names)} for p in performances],
    'captures': [{'path': c.get_path_name(), 'properties': props(c, ['image_sequences', 'audio', 'metadata', 'views'])} for c in captures],
}
try:
    result['edited_assets'] = [a.get_path_name() for a in unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).get_all_edited_assets()]
except Exception as exc:
    result['edited_assets_error'] = str(exc)
api = []
for cls in [unreal.MetaHumanPerformance, unreal.FootageCaptureData, unreal.MetaHumanPerformanceExportAnimationSettings, unreal.MetaHumanPerformanceExportUtils]:
    api.append(str(cls) + '\n' + str(cls.__doc__))
    api.append('\n'.join(name for name in dir(cls) if not name.startswith('_')))
for name in ['start_pipeline', 'is_processing', 'set_processing_range', 'get_processing_range', 'get_processing_state', 'get_start_frame', 'get_end_frame', 'get_animation_data', 'get_number_of_frames', 'set_blocking_processing']:
    api.append(name + ': ' + str(getattr(unreal.MetaHumanPerformance, name, None).__doc__))
(out / 'batch_api.txt').write_text('\n\n'.join(api), encoding='utf-8')
(out / 'batch_inspection.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
unreal.log('MOCAP_BATCH_INSPECT_SUCCESS|' + json.dumps({'pid': result['pid'], 'performances': len(performances), 'captures': len(captures)}))
