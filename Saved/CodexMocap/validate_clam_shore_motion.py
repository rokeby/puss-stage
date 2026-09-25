import builtins
import json
import pathlib
import time
import traceback
import unreal
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
manifest=json.loads((folder/'shore_clam_integration.json').read_text(encoding='utf-8'))
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert world.get_path_name()==manifest['world']
assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
assert not hasattr(builtins,'PUSS_CLAM_SHORE_QC_HANDLE')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
seq=unreal.load_asset(manifest['sequence'])
targets=[];binding_report=[]
for row in manifest['characters']:
    actor=next(a for a in actors if a.get_path_name()==row['actor'])
    body=next(c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()=='Body')
    cloth=actor.get_component_by_class(unreal.ChaosClothComponent)
    bb=next(b for b in seq.get_bindings() if unreal.GuidLibrary.conv_guid_to_string(b.get_id())==row['body_binding'])
    objects=seq.locate_bound_objects(bb,world)
    assert len(objects)==1 and objects[0].get_path_name()==body.get_path_name(),row['id']+' body binding'
    sections=bb.get_tracks()[0].get_sections();assert len(sections)==1
    params=sections[0].get_editor_property('params')
    assert params.animation.get_path_name()==row['animation']
    assert abs(params.play_rate.to_fixed_play_rate()-row['play_rate'])<1e-6
    actor.call_method('ConfigureShoreDrape');cloth.set_simulate_in_editor(True);cloth.resume_simulation()
    targets.append((row,actor,body,cloth))
    binding_report.append({'id':row['id'],'body':body.get_path_name(),'animation':params.animation.get_path_name(),'cloth':cloth.get_asset().get_path_name(),'socket':str(cloth.get_attach_socket_name())})
assert len({r['body'] for r in binding_report})==6
unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
unreal.LevelSequenceEditorBlueprintLibrary.pause();unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
for _,_,_,cloth in targets:cloth.force_next_update_teleport_and_reset()
run=str(int(time.time()))
state={'status':'warming','run_id':run,'started':time.time(),'bindings':binding_report,'samples':[],'screenshots':[],'errors':[],'next_capture_frame':0,'last_frame':-1}
builtins.PUSS_CLAM_SHORE_QC_STATE=state
def persist():
    (folder/'shore_clam_motion_qc.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
def finish(status):
    unreal.LevelSequenceEditorBlueprintLibrary.pause();state['status']=status;state['finished']=time.time();persist()
    unreal.unregister_slate_post_tick_callback(builtins.PUSS_CLAM_SHORE_QC_HANDLE);del builtins.PUSS_CLAM_SHORE_QC_HANDLE
    unreal.log('CLAM_SHORE_MOTION_QC_'+status.upper()+'|samples='+str(len(state['samples']))+'|six_unique_bound_bodies')
def tick(delta):
    if state.get('inside_callback'):return
    state['inside_callback']=True
    try:
        if time.time()-state['started']>180:state['errors'].append('Playback timeout');finish('failed');return
        if state['status']=='warming':
            if time.time()-state['started']<5:return
            state['status']='playing';unreal.LevelSequenceEditorBlueprintLibrary.play();persist();return
        frame=unreal.LevelSequenceEditorBlueprintLibrary.get_current_time()
        if frame!=state['last_frame']:
            samples=[]
            for row,actor,body,cloth in targets:
                assert cloth.get_attach_parent()==body and str(cloth.get_attach_socket_name())=='head',row['id']+' attachment'
                samples.append({'id':row['id'],'head':list(body.get_socket_transform('head').translation.to_tuple()),'simulating_in_editor':cloth.get_editor_property('simulate_in_editor'),'simulation_enabled':cloth.is_simulation_enabled()})
            state['samples'].append({'frame':frame,'characters':samples});state['last_frame']=frame
        task=getattr(builtins,'PUSS_CLAM_SHORE_QC_SCREENSHOT_TASK',None)
        if frame>=state['next_capture_frame'] and (task is None or task.is_task_done()):
            cuts=next(t for t in seq.get_tracks() if isinstance(t,unreal.MovieSceneCameraCutTrack)).get_sections()
            cut=next(s for s in cuts if s.get_start_frame()<=frame<s.get_end_frame())
            guid=cut.get_camera_binding_id().get_editor_property('guid')
            guid_text=unreal.GuidLibrary.conv_guid_to_string(guid)
            b=next((b for b in seq.get_bindings() if unreal.GuidLibrary.conv_guid_to_string(b.get_id())==guid_text),None)
            if b is None:
                state['errors'].append('Existing camera cut binding does not resolve: '+guid_text)
                camera=next(a for a in actors if a.get_actor_label()==('ClamCam2' if 215<=frame<408 else 'ClamCam1'))
            else:camera=seq.locate_bound_objects(b,world)[0]
            name='Clam_Shore_'+run+'_Frame'+str(frame).zfill(4)+'.png'
            builtins.PUSS_CLAM_SHORE_QC_SCREENSHOT_TASK=unreal.AutomationLibrary.take_high_res_screenshot(2560,1440,str(folder/name),camera=camera,delay=0.0)
            state['screenshots'].append({'frame':frame,'camera':camera.get_actor_label(),'file':str(folder/name)})
            state['next_capture_frame']=frame+90;persist()
        if frame>=795:finish('complete')
    except Exception:state['errors'].append(traceback.format_exc());finish('failed')
    finally:state['inside_callback']=False
builtins.PUSS_CLAM_SHORE_QC_HANDLE=unreal.register_slate_post_tick_callback(tick)
persist()
unreal.log('CLAM_SHORE_MOTION_QC_STARTED|six_unique_bindings_verified')
