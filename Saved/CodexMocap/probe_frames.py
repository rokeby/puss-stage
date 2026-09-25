import json, pathlib, os
import unreal
out = pathlib.Path('E:/PussStage/Saved/CodexMocap')
p = unreal.load_asset('/Game/Metahuman/Shore1')
data = p.get_animation_data()
fields = ['animation_data','body_animation_data','raw_body_animation_smplx_data','raw_body_animation_smplx_pose']
summary = {}
for name in fields:
    indices = [i for i, frame in enumerate(data) if len(frame.get_editor_property(name))]
    summary[name] = {'count':len(indices), 'first':indices[:2], 'last':indices[-2:]}
enum = unreal.FrameAnimationDataType
types = {}
for name in dir(enum):
    if name.isupper():
        try: types[name] = p.contains_animation_data_type(getattr(enum,name))
        except Exception as exc: types[name] = str(exc)
capture_info=[]
for stem in ['shoreguy1','shoreguy12','shoreguy3','shoreguy4','shoreguy5','shoreguy6','child1','child2']:
    path=f'/Game/CaptureManager/Imports/Mono_Video_Ingest/{stem}_1/CD_{stem}_1'
    if not unreal.EditorAssetLibrary.does_asset_exist(path):
        capture_info.append({'stem':stem,'missing':True}); continue
    capture=unreal.load_asset(path)
    media=capture.get_editor_property('image_sequences')[0]
    source=pathlib.Path(media.get_sequence_path())
    files=sorted(x.name for x in source.iterdir() if x.suffix.lower() in ['.jpg','.jpeg','.png','.exr','.bmp','.tif','.tiff'])
    capture_info.append({'stem':stem,'capture':capture.get_path_name(),'directory':str(source),'image_count':len(files),'first':files[:2],'last':files[-2:]})
result={'frame_data':summary,'data_types':types,'can_export':p.can_export_animation(),'captures':capture_info}
(out/'frame_probe.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
unreal.log('MOCAP_FRAME_PROBE_SUCCESS|' + json.dumps(summary))
