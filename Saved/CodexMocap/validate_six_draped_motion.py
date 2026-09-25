import builtins
import json
import pathlib
import time
import traceback
import unreal
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
manifest=json.loads((folder/'shore_draped_review_manifest.json').read_text(encoding='utf-8'))
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert world.get_path_name().split('.')[0]==manifest['map']
assert not hasattr(builtins,'PUSS_SHORE_CLOTH_QC_HANDLE'),'QC callback already active'
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
camera=next(a for a in actors if a.get_path_name()==manifest['camera'])
targets=[]
for row in manifest['characters']:
    actor=next(a for a in actors if a.get_path_name()==row['actor'])
    body=next(c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()=='Body')
    cloth=actor.get_component_by_class(unreal.ChaosClothComponent)
    cloth.set_simulate_in_editor(True)
    cloth.resume_simulation()
    actor.call_method('ConfigureShoreDrape')
    targets.append((row,actor,body,cloth))
unreal.LevelSequenceEditorBlueprintLibrary.pause()
unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(0)
for _,_,_,cloth in targets: cloth.force_next_update_teleport_and_reset()
run_id=str(int(time.time()))
state={'status':'warming','run_id':run_id,'started':time.time(),'phase_started':time.time(),'samples':[],'screenshots':[],'next_capture_frame':0,'last_frame':-1,'errors':[]}
builtins.PUSS_SHORE_CLOTH_QC_STATE=state
def persist():
    (folder/'shore_draped_motion_qc.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
def finish(status):
    unreal.LevelSequenceEditorBlueprintLibrary.pause()
    state['status']=status;state['finished']=time.time()
    persist()
    unreal.unregister_slate_post_tick_callback(builtins.PUSS_SHORE_CLOTH_QC_HANDLE)
    del builtins.PUSS_SHORE_CLOTH_QC_HANDLE
    unreal.log('SHORE_DRAPED_MOTION_QC_'+status.upper()+'|samples='+str(len(state['samples']))+'|screenshots='+str(len(state['screenshots'])))
def tick(delta):
    try:
        if time.time()-state['started']>160:
            state['errors'].append('Review playback exceeded 160 seconds');finish('failed');return
        if state['status']=='warming':
            if time.time()-state['phase_started']<3:return
            state['status']='playing';unreal.LevelSequenceEditorBlueprintLibrary.play();persist();return
        frame=unreal.LevelSequenceEditorBlueprintLibrary.get_current_time()
        if frame!=state['last_frame']:
            poses=[]
            for row,actor,body,cloth in targets:
                assert cloth.get_attach_parent()==body and str(cloth.get_attach_socket_name())=='head',row['id']+' detached'
                head=body.get_socket_transform('head')
                anchor=cloth.get_socket_transform('None')
                poses.append({'id':row['id'],'head':list(head.translation.to_tuple()),'anchor':list(anchor.translation.to_tuple()),'simulation_enabled':cloth.is_simulation_enabled()})
            state['samples'].append({'frame':frame,'characters':poses})
            state['last_frame']=frame
        task=getattr(builtins,'PUSS_SHORE_QC_SCREENSHOT_TASK',None)
        available=task is None or task.is_task_done()
        if frame>=state['next_capture_frame'] and available:
            name='ShoreDrape_AllSix_'+run_id+'_Frame'+str(frame).zfill(4)+'.png'
            builtins.PUSS_SHORE_QC_SCREENSHOT_TASK=unreal.AutomationLibrary.take_high_res_screenshot(2560,1440,str(folder/name),camera=camera,delay=0.0)
            state['screenshots'].append({'frame_requested':frame,'file':str(folder/name)})
            state['next_capture_frame']=frame+90
            persist()
        if frame>=795:
            finish('complete')
    except Exception:
        state['errors'].append(traceback.format_exc());finish('failed')
builtins.PUSS_SHORE_CLOTH_QC_HANDLE=unreal.register_slate_post_tick_callback(tick)
persist()
unreal.log('SHORE_DRAPED_MOTION_QC_STARTED|full_797_frame_scene')
