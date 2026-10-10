"""Read-only Job 183 S1 binding-name probe after shrink validation mismatch."""
import json
import unreal
seq = unreal.load_asset('/Game/InfinityStage/Dev/Sequences/LS_DevScene_01')
rows=[]
for binding in seq.get_bindings():
    name=str(binding.get_display_name())
    if 'HANGAR' not in name.upper():
        continue
    tracks=[]
    for track in binding.get_tracks():
        sections=[]
        for section in track.get_sections():
            try: sections.append([int(section.get_start_frame()),int(section.get_end_frame())])
            except Exception: sections.append(None)
        tracks.append({'class':track.get_class().get_name(),'sections':sections})
    rows.append({'name':name,'tracks':tracks})
path='E:/PussStage/Saved/CodexConductor/job183_s1_hangar_binding_probe.json'
with open(path,'w',encoding='utf-8') as h: json.dump({'rows':rows},h,indent=2,sort_keys=True)
unreal.log('JOB183_S1_HANGAR_BINDING_PROBE_OK|rows=%d|path=%s'%(len(rows),path))
