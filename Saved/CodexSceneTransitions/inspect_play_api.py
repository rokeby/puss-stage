import json
import pathlib
import unreal
out={}
for cls in [unreal.LevelEditorSubsystem,unreal.EditorLevelLibrary,unreal.AutomationLibrary,unreal.LevelSequencePlayer]:
    methods=[m for m in dir(cls) if any(w in m.lower() for w in ['play','screenshot','camera','simulate'])]
    out[cls.__name__]={m:str(getattr(cls,m).__doc__) for m in methods}
pathlib.Path('E:/PussStage/Saved/CodexSceneTransitions/play_api.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
unreal.log('SCENE_TRANSITION_PLAY_API_INSPECTED')
