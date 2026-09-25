import builtins
import json
import pathlib
import time
import traceback
import unreal
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not levels.is_in_play_in_editor()
assert not hasattr(builtins,'PUSS_CLAM_SHORE_QC_HANDLE')
assert not hasattr(builtins,'PUSS_CLAM_SHORE_RUNTIME_HANDLE')
dirty=list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
assert not dirty,[p.get_path_name() for p in dirty]
unreal.LevelSequenceEditorBlueprintLibrary.pause()
unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
manifest=json.loads((folder/'shore_clam_integration.json').read_text(encoding='utf-8'))
seq=unreal.load_asset(manifest['sequence'])
state={'status':'starting_simulation','started':time.time(),'errors':[],'samples':[],'last_frame':-1}
builtins.PUSS_CLAM_SHORE_RUNTIME_STATE=state
targets=[]
def persist():
    (folder/'shore_clam_runtime_qc.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
def finish(status):
    state['status']=status;state['finished']=time.time();persist()
    player=getattr(builtins,'PUSS_CLAM_RUNTIME_PLAYER',None)
    if player:player.stop()
    levels.editor_request_end_play()
    unreal.unregister_slate_post_tick_callback(builtins.PUSS_CLAM_SHORE_RUNTIME_HANDLE)
    del builtins.PUSS_CLAM_SHORE_RUNTIME_HANDLE
    unreal.log('CLAM_SHORE_RUNTIME_'+status.upper()+'|samples='+str(len(state['samples'])))
def tick(delta):
    if state.get('inside_callback'):return
    state['inside_callback']=True
    try:
        if time.time()-state['started']>150:state['errors'].append('Runtime validation timeout');finish('failed');return
        if state['status']=='starting_simulation':
            world=editor.get_game_world()
            if not world:return
            all_actors=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor)
            by_label={a.get_actor_label():a for a in all_actors}
            if not all(row['id']+' Clam' in by_label for row in manifest['characters']):return
            for row in manifest['characters']:
                actor=by_label[row['id']+' Clam']
                body=next(c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()=='Body')
                cloth=actor.get_component_by_class(unreal.ChaosClothComponent)
                assert cloth.get_attach_parent()==body and str(cloth.get_attach_socket_name())=='head',row['id']+' BeginPlay attachment'
                assert cloth.is_simulation_enabled(),row['id']+' runtime simulation disabled'
                targets.append((row,actor,body,cloth))
            player,sequence_actor=unreal.LevelSequencePlayer.create_level_sequence_player(world,seq,unreal.MovieSceneSequencePlaybackSettings())
            assert player
            builtins.PUSS_CLAM_RUNTIME_PLAYER=player
            builtins.PUSS_CLAM_RUNTIME_SEQUENCE_ACTOR=sequence_actor
            editor_world=editor.get_editor_world()
            for b in seq.get_bindings():
                if unreal.GuidLibrary.conv_guid_to_string(b.get_parent().get_id())!='00000000000000000000000000000000':continue
                existing=seq.locate_bound_objects(b,editor_world)
                if len(existing)==1 and isinstance(existing[0],unreal.Actor) and existing[0].get_actor_label() in by_label:
                    sequence_actor.set_binding(seq.get_binding_id(b),[by_label[existing[0].get_actor_label()]],False)
            state['world']=world.get_path_name();state['status']='warming';state['warm_started']=time.time();persist();return
        if state['status']=='warming':
            if time.time()-state['warm_started']<5:return
            builtins.PUSS_CLAM_RUNTIME_PLAYER.play();state['status']='playing';persist();return
        frame=builtins.PUSS_CLAM_RUNTIME_PLAYER.get_current_time().time.frame_number.value
        if frame!=state['last_frame']:
            poses=[]
            for row,actor,body,cloth in targets:
                assert cloth.get_attach_parent()==body and str(cloth.get_attach_socket_name())=='head'
                poses.append({'id':row['id'],'head':list(body.get_socket_transform('head').translation.to_tuple()),'cloth_simulation':cloth.is_simulation_enabled()})
            state['samples'].append({'frame':frame,'characters':poses});state['last_frame']=frame
        if frame>=795:
            assert len(state['samples'])>30
            for index,row in enumerate(manifest['characters']):
                positions=[s['characters'][index]['head'] for s in state['samples']]
                assert max(max(p[k] for p in positions)-min(p[k] for p in positions) for k in range(3))>1.0,row['id']+' not moving'
            finish('passed')
    except Exception:state['errors'].append(traceback.format_exc());finish('failed')
    finally:state['inside_callback']=False
builtins.PUSS_CLAM_SHORE_RUNTIME_HANDLE=unreal.register_slate_post_tick_callback(tick)
persist()
levels.editor_play_simulate()
unreal.log('CLAM_SHORE_RUNTIME_VALIDATION_START_REQUESTED')
