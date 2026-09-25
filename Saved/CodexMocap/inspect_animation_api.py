import pathlib
import unreal
animation=unreal.load_asset('/Game/Metahuman/FullTakes_20260910/RawAnimations/AS_shoreguy1_Body_Full')
lines=[]
for cls in [type(animation),unreal.AnimationLibrary]:
    lines.append(str(cls))
    for name in dir(cls):
        if any(part in name for part in ['bone','pose','track','frame','model','key','length']):
            lines.append(name+': '+str(getattr(cls,name).__doc__))
try:
    model=animation.get_editor_property('data_model')
    lines.append('MODEL: '+str(model)+'\n'+str(type(model).__doc__))
    for name in dir(model):
        if any(part in name for part in ['bone','pose','track','frame','key']):
            lines.append(name+': '+str(getattr(model,name).__doc__))
except Exception as exc:
    lines.append(str(exc))
pathlib.Path('E:/PussStage/Saved/CodexMocap/animation_api.txt').write_text('\n'.join(lines),encoding='utf-8')
unreal.log('MOCAP_ANIMATION_API_SUCCESS')
