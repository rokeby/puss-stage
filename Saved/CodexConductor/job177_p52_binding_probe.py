import json, unreal as u
OUT='E:/PussStage/Saved/CodexConductor/job177_p52_binding_probe.json'
master=u.load_asset('/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master'); world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
target=[a for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors() if str(a.get_actor_label())=='P75 P06 Chandelier Body'][0]
path=target.get_path_name().split('.',1)[0]; rows=[]
for b in master.get_bindings():
    old=[]; new=[]
    try: old=[o.get_path_name().split('.',1)[0] for o in master.locate_bound_objects(b,world)]
    except Exception as e: old=['ERROR:'+str(e)]
    try: new=[o.get_path_name().split('.',1)[0] for o in master.locate_bound_objects(b.get_id(),world)]
    except Exception as e: new=['ERROR:'+str(e)]
    if path in old or path in new or str(b.get_display_name())=='P75 P06 Chandelier Body': rows.append({'name':str(b.get_display_name()),'guid':u.GuidLibrary.conv_guid_to_string(b.get_id()),'old_match':path in old,'guid_match':path in new,'tracks':[t.get_class().get_name() for t in b.get_tracks()]})
with open(OUT,'x',encoding='utf-8') as f: json.dump({'target':path,'rows':rows,'old_count':sum(r['old_match'] for r in rows),'guid_count':sum(r['guid_match'] for r in rows),'exact_name_count':sum(r['name']=='P75 P06 Chandelier Body' for r in rows)},f,indent=2)
u.log('JOB177_P52_BINDING_PROBE_OK|old=%d|guid=%d|exact=%d'%(sum(r['old_match'] for r in rows),sum(r['guid_match'] for r in rows),sum(r['name']=='P75 P06 Chandelier Body' for r in rows)))
