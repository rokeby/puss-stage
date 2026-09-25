import json
import pathlib
import unreal
show=unreal.load_asset('/Game/InfinityStage/Dev/DA_InfinityStage_V1Show')
out={'show':show.get_path_name(),'cues':[]}
for idx,cue in enumerate(show.get_editor_property('cues')):
    content=cue.export_text()
    if 'Type=Scene,' in content:
        out['cues'].append({'index':idx,'label':str(cue.get_editor_property('label')),'scene':cue.get_editor_property('scene').export_text()})
pathlib.Path('E:/PussStage/Saved/CodexMocap/clam_show_cue.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
unreal.log('CLAM_SHOW_CUE_READ_SUCCESS|' + json.dumps(out))
