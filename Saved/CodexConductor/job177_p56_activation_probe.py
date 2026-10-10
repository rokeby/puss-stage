import json, os, unreal as u
OUT='E:/PussStage/Saved/CodexConductor/job177_p56_activation_probe.json'
show=u.load_asset('/Game/InfinityStage/Dev/DA_InfinityStage_V1Show')
master=u.load_asset('/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master')
rows=[]
for p in show.get_editor_property('passage_settings'):
    label=str(p.get_editor_property('label'))
    if '6' in label or '06' in label:
        guid=p.get_editor_property('passage_guid')
        result=u.InfinityStageCameraPilotLibrary.get_passage_frame_range(show,guid)
        rows.append({'label':label,'guid':u.GuidLibrary.conv_guid_to_string(guid),'range':str(result)})
enum={n:str(getattr(u.ParticleKey,n)) for n in ('ACTIVATE','DEACTIVATE','TRIGGER') if hasattr(u.ParticleKey,n)}
bindings=[{'name':str(b.get_display_name()),'guid':u.GuidLibrary.conv_guid_to_string(b.get_id()),'tracks':[t.get_class().get_name() for t in b.get_tracks()]} for b in master.get_bindings() if str(b.get_display_name()).startswith('P56 ')]
with open(OUT,'x',encoding='utf-8') as f: json.dump({'passages':rows,'particle_key':enum,'bindings':bindings},f,indent=2)
u.log('JOB177_P56_ACTIVATION_PROBE_OK|passages=%d|bindings=%d|enum=%s'%(len(rows),len(bindings),','.join(enum)))
