import json
import pathlib
import unreal
paths=['/Game/Scenes/LS_Clams','/Game/Scenes/LS_OrtalanSheetSway','/Game/InfinityStage/Dev/Sequences/LS_DevScene_03']
out=[]
for path in paths:
    seq=unreal.load_asset(path)
    row={'path':path,'rate':str(seq.get_display_rate()),'start':seq.get_playback_start(),'end':seq.get_playback_end(),'tracks':[],'bindings':[]}
    for t in seq.get_tracks():
        tr={'type':t.get_class().get_name(),'sections':[]}
        for s in t.get_sections():
            sr={'type':s.get_class().get_name(),'range':[s.get_start_frame() if s.has_start_frame() else None,s.get_end_frame() if s.has_end_frame() else None]}
            if isinstance(s,unreal.MovieSceneSubSection):sr['sequence']=str(s.get_sequence())
            tr['sections'].append(sr)
        row['tracks'].append(tr)
    for b in seq.get_bindings():row['bindings'].append({'name':str(b.get_display_name()),'tracks':[t.get_class().get_name() for t in b.get_tracks()]})
    out.append(row)
pathlib.Path('E:/PussStage/Saved/CodexMocap/clam_sequence_routing.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
unreal.log('CLAM_SEQUENCE_ROUTING_READ_SUCCESS|'+json.dumps(out))
