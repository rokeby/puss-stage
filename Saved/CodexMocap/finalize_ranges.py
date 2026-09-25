import json, pathlib
import unreal
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
manifest=json.loads((folder/'batch_manifest.json').read_text(encoding='utf-8'))
def encode(v):
    if v is None or isinstance(v,(bool,int,float,str)): return v
    if isinstance(v,unreal.Object): return v.get_path_name()
    if hasattr(v,'export_text'): return v.export_text()
    try: return [encode(x) for x in v]
    except TypeError: return str(v)
for job in manifest['jobs']:
    original=unreal.load_asset(job['capture'])
    name='CD_'+job['stem']+'_BodyFullRange'
    path=manifest['root']+'/CaptureData/'+name
    duplicate=unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else unreal.AssetToolsHelpers.get_asset_tools().duplicate_asset(name,manifest['root']+'/CaptureData',original)
    assert duplicate
    duplicate.set_editor_property('audio_tracks',[])
    assert unreal.EditorAssetLibrary.save_loaded_asset(duplicate,only_if_is_dirty=False)
    p=unreal.load_asset(job['performance'])
    p.set_editor_property('footage_capture_data',duplicate)
    p.set_processing_range(0,2147483647)
    job['original_capture']=job['capture']
    job['capture']=duplicate.get_path_name()
    job['start']=p.get_editor_property('start_frame_to_process')
    job['end_exclusive']=p.get_editor_property('end_frame_to_process')
    assert job['start']==0 and job['end_exclusive']==job['image_count'], str(job)
    differences={key:[val,encode(p.get_editor_property(key))] for key,val in manifest['settings'].items() if val!=encode(p.get_editor_property(key))}
    assert not differences,str(differences)
    assert unreal.EditorAssetLibrary.save_loaded_asset(p,only_if_is_dirty=False)
manifest['full_range_input_note']='Body-only copies reference the same video image sequences but omit shorter ingested audio tracks, preventing audio from truncating the solve. Original captures and audio are unchanged.'
(folder/'batch_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
unreal.log('MOCAP_FULL_RANGES_READY|takes='+str(len(manifest['jobs']))+'|frames='+str(sum(j['image_count'] for j in manifest['jobs'])))
