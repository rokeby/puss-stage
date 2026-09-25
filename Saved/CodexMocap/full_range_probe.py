import json, pathlib
import unreal
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
manifest=json.loads((folder/'batch_manifest.json').read_text(encoding='utf-8'))
job=manifest['jobs'][0]
original=unreal.load_asset(job['capture'])
audio=[{'asset':a.get_path_name(),'duration':a.get_editor_property('duration')} for a in original.get_editor_property('audio_tracks')]
duplicate=unreal.AssetToolsHelpers.get_asset_tools().duplicate_asset('CD_shoreguy1_BodyFullRange',manifest['root']+'/CaptureData',original)
assert duplicate
duplicate.set_editor_property('audio_tracks',[])
assert unreal.EditorAssetLibrary.save_loaded_asset(duplicate,only_if_is_dirty=False)
p=unreal.load_asset(job['performance'])
p.set_editor_property('footage_capture_data',duplicate)
p.set_processing_range(0,2147483647)
result={'before':[job['start'],job['end_exclusive']], 'after':[p.get_editor_property('start_frame_to_process'),p.get_editor_property('end_frame_to_process')], 'images':job['image_count'],'audio':audio,'duplicate':duplicate.get_path_name()}
assert unreal.EditorAssetLibrary.save_loaded_asset(p,only_if_is_dirty=False)
(folder/'full_range_probe.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
unreal.log('MOCAP_FULL_RANGE_PROBE_SUCCESS|'+json.dumps(result))
