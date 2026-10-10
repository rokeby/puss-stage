"""Guarded Job 177 P56 activation repair: 44 component bindings, P06-only keys."""
import datetime, hashlib, json, os, shutil, unreal as u

RUN='J177-P56-ACTIVATE-20261010'
MASTER_PATH='/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master'
SHOW_PATH='/Game/InfinityStage/Dev/DA_InfinityStage_V1Show'
WORLD_PATH='/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice'
BP_PATH='/Game/Scenes/Effects/BP_Effect_ChandelierCandle'
PREFIX='P56_P75_P06_Chandelier_Body_Candle_'
TRACK_NAME='P56 P06 Flame Activation [OWNED]'
RECORD='E:/PussStage/Saved/CodexConductor/job177_p56_activation_record.json'

def req(x,m):
    if not x: raise RuntimeError(m)
def aid(x): return x.get_path_name().split('.',1)[0] if x else None
def census():
    lib=u.EditorLoadingAndSavingUtils
    return {'content':sorted(aid(x) for x in lib.get_dirty_content_packages()),'maps':sorted(aid(x) for x in lib.get_dirty_map_packages())}
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    return h.hexdigest()
def package_file(pkg):
    base=os.path.join(u.Paths.convert_relative_path_to_full(u.Paths.project_content_dir()),*pkg[6:].split('/'))
    for ext in ('.uasset','.umap'):
        if os.path.isfile(base+ext): return base+ext
    raise RuntimeError('PACKAGE_FILE|'+pkg)
def backup():
    root=os.path.join(u.Paths.convert_relative_path_to_full(u.Paths.project_dir()),'Backups','PreJob177P56Activation-'+RUN)
    os.makedirs(root,exist_ok=False); rows=[]
    for pkg in (MASTER_PATH,BP_PATH):
        src=package_file(pkg); dst=os.path.join(root,*pkg[6:].split('/'))+os.path.splitext(src)[1]
        os.makedirs(os.path.dirname(dst),exist_ok=True); shutil.copy2(src,dst)
        req(sha(src)==sha(dst),'BACKUP_HASH|'+pkg); rows.append({'package':pkg,'source':src,'backup':dst,'sha256':sha(dst),'bytes':os.path.getsize(dst)})
    return {'root':root,'packages':rows}
def subobject(bp,name):
    ss=u.get_engine_subsystem(u.SubobjectDataSubsystem); lib=u.SubobjectDataBlueprintFunctionLibrary
    for h in ss.k2_gather_subobject_data_for_blueprint(bp):
        d=lib.get_data(h)
        if str(lib.get_variable_name(d))==name: return lib.get_object_for_blueprint(d,bp) or lib.get_associated_object(d)
def passages(show):
    return [p for p in show.get_editor_property('passage_settings') if str(p.get_editor_property('label'))=='Passage 6']
def readback(master):
    rows=[]
    for b in master.get_bindings():
        name=str(b.get_display_name())
        if not name.startswith('P56 P06 Flame '): continue
        tracks=[t for t in b.get_tracks() if str(t.get_display_name())==TRACK_NAME]
        req(len(tracks)==1,'TRACK_COUNT|'+name)
        sections=tracks[0].get_sections(); req(len(sections)==1,'SECTION_COUNT|'+name)
        keys=list(sections[0].get_all_channels()[0].get_keys()); req(len(keys)==2,'KEY_COUNT|'+name)
        rows.append({'name':name,'guid':u.GuidLibrary.conv_guid_to_string(b.get_id()),'key_count':len(keys)})
    req(len(rows)==44,'READBACK_BINDINGS|%d'%len(rows))
    return sorted(rows,key=lambda x:x['name'])

editor=u.get_editor_subsystem(u.UnrealEditorSubsystem)
req(editor.get_game_world() is None,'PIE_ACTIVE')
req(aid(editor.get_editor_world())==WORLD_PATH,'WRONG_WORLD')
req(census()=={'content':[],'maps':[]},'DIRTY_PRE|'+json.dumps(census()))
req(u.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is None,'SEQUENCER_OPEN')
req(not os.path.exists(RECORD),'RECORD_EXISTS')
master=u.load_asset(MASTER_PATH); show=u.load_asset(SHOW_PATH); bp=u.load_asset(BP_PATH)
req(master and show and bp,'ASSET_LOAD')
req(not [b for b in master.get_bindings() if str(b.get_display_name()).startswith('P56 P06 Flame ')],'OWNED_BINDINGS_EXIST')
actors=sorted([a for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors() if str(a.get_actor_label()).startswith(PREFIX)],key=lambda a:str(a.get_actor_label()))
req(len(actors)==44,'ACTOR_COUNT|%d'%len(actors))
p=passages(show); req(len(p)==1,'PASSAGE_COUNT|%d'%len(p))
span=u.InfinityStageCameraPilotLibrary.get_passage_frame_range(show,p[0].get_editor_property('passage_guid'))
start,end=int(span[0]),int(span[1]); req(start<end,'PASSAGE_RANGE')
b=backup(); record={'schema':'job177_p56_activation_v1','status':'prepared','run':RUN,'backup':b,'span':[start,end],'actor_labels':[str(a.get_actor_label()) for a in actors]}
with open(RECORD,'x',encoding='utf-8') as f: json.dump(record,f,indent=2)
component_template=subobject(bp,'ChandelierFlameFX'); req(isinstance(component_template,u.NiagaraComponent),'BP_COMPONENT')
record['auto_activate_before']=bool(component_template.get_editor_property('auto_activate'))
component_template.set_editor_property('auto_activate',False)
req(u.BlueprintEditorLibrary.compile_blueprint(bp),'BP_COMPILE')
req(u.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False),'BP_SAVE')
for index,actor in enumerate(actors,1):
    comps=[c for c in actor.get_components_by_class(u.NiagaraComponent) if str(c.get_name())=='ChandelierFlameFX']
    req(len(comps)==1,'COMPONENT_COUNT|%s|%d'%(actor.get_actor_label(),len(comps)))
    ab=master.add_possessable(actor); ab.set_display_name('P56 P06 Candle %02d [OWNED]'%index)
    cb=master.add_possessable(comps[0]); cb.set_parent(ab); cb.set_display_name('P56 P06 Flame %02d [OWNED]'%index)
    track=cb.add_track(u.MovieSceneParticleTrack); track.set_display_name(TRACK_NAME)
    section=track.add_section(); section.set_range(start,end)
    ch=section.get_all_channels()[0]
    ch.add_key(u.FrameNumber(start),u.ParticleKey.ACTIVATE,0.0,u.MovieSceneTimeUnit.TICK_RESOLUTION)
    ch.add_key(u.FrameNumber(end-1),u.ParticleKey.DEACTIVATE,0.0,u.MovieSceneTimeUnit.TICK_RESOLUTION)
req(census()=={'content':[MASTER_PATH],'maps':[]},'DIRTY_SCOPE|'+json.dumps(census()))
req(u.EditorAssetLibrary.save_loaded_asset(master,only_if_is_dirty=False),'MASTER_SAVE')
rows=readback(master); req(census()=={'content':[],'maps':[]},'DIRTY_POST|'+json.dumps(census()))
record.update({'status':'applied','auto_activate_after':False,'bindings':rows,'dirty_after':census()})
with open(RECORD,'w',encoding='utf-8') as f: json.dump(record,f,indent=2)
u.log('JOB177_P56_ACTIVATION_APPLY_OK|run=%s|bindings=44|tracks=44|keys=88|span=%d:%d|auto_activate=0|saved=%s,%s|dirty=0'%(RUN,start,end,BP_PATH,MASTER_PATH))
