import json
import pathlib
import unreal
seq=unreal.load_asset('/Game/Metahuman/ShoreCast_20260910/Review/LS_ShoreDrape_Pilot')
section=next(s for b in seq.get_bindings() for t in b.get_tracks() if isinstance(t,unreal.MovieSceneSkeletalAnimationTrack) for s in t.get_sections())
params=section.get_editor_property('params')
rate=params.get_editor_property('play_rate')
out={'params':params.export_text(),'rate':str(rate),'rate_api':{n:getattr(getattr(rate,n),'__doc__',None) for n in dir(rate) if not n.startswith('_')},'extensions':[n for n in dir(unreal) if 'TimeWarp' in n]}
pathlib.Path('E:/PussStage/Saved/CodexMocap/shore_playrate_api.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
unreal.log('SHORE_PLAYRATE_API_INSPECTED')
