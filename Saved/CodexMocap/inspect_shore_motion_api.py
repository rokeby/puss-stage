import json
import pathlib
import unreal
out={}
for name in ['AnimPoseExtensions','AnimPoseEvaluationOptions','AnimationLibrary']:
    cls=getattr(unreal,name,None)
    out[name]={n:getattr(getattr(cls,n),'__doc__',None) for n in dir(cls) if any(k in n for k in ['pose','bone_names','frame']) and not n.startswith('_')}
pathlib.Path('E:/PussStage/Saved/CodexMocap/shore_motion_selection_api.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
unreal.log('SHORE_MOTION_SELECTION_API_INSPECTED')
