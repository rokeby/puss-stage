import json
import pathlib
import re
import unreal

folder=pathlib.Path('E:/PussStage/Saved/CodexSceneTransitions')
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world=editor.get_editor_world()
assert editor.get_game_world() is None
show=unreal.load_asset('/Game/InfinityStage/Dev/DA_InfinityStage_V1Show')
roots=[a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if isinstance(a,unreal.InfinityStageShowRoot)]
assert len(roots)==1
root=roots[0];master=root.master_sequence
result={'world':world.get_path_name(),'auto_scene':root.transport.auto_play_scene_after_passage,'scenes':[],'errors':[]}
assert result['auto_scene']
sections=[s for t in master.get_tracks() if t.get_class().get_name()=='MovieSceneInfinitySceneTrack' for s in t.get_sections()]
for cue in show.cues:
    if cue.type!=unreal.InfinityCueType.SCENE:continue
    assert cue.scene.use_sequence_length
    path=re.search(r'Sequence="([^"]+)"',cue.scene.export_text()).group(1)
    seq=unreal.load_asset(path)
    section=next(s for s in sections if s.get_sequence()==seq)
    expected=(seq.get_playback_end()-seq.get_playback_start())/seq.get_display_rate().numerator
    actual=(section.get_end_frame()-section.get_start_frame())/master.get_display_rate().numerator
    assert abs(expected-actual)<0.041,(path,expected,actual)
    cuts=sorted([s for t in seq.get_tracks() if isinstance(t,unreal.MovieSceneCameraCutTrack) for s in t.get_sections()],key=lambda s:s.get_start_frame())
    assert cuts and cuts[0].get_start_frame()<=seq.get_playback_start() and cuts[-1].get_end_frame()>=seq.get_playback_end(),path
    assert all(a.get_end_frame()>=b.get_start_frame() for a,b in zip(cuts,cuts[1:])),path
    cameras=[]
    for cut in cuts:
        guid=unreal.GuidLibrary.conv_guid_to_string(cut.get_camera_binding_id().get_editor_property('guid'))
        binding=next(b for b in seq.get_bindings() if unreal.GuidLibrary.conv_guid_to_string(b.get_id())==guid)
        objects=seq.locate_bound_objects(binding,world)
        assert objects,(path,binding.get_name())
        cameras.append({'name':binding.get_name(),'objects':[o.get_path_name() for o in objects]})
    result['scenes'].append({'label':str(cue.label),'sequence':path,'duration_seconds':actual,'master_start':section.get_start_frame(),'master_end':section.get_end_frame(),'cameras':cameras})
check=unreal.InfinityStageSequenceBuilderLibrary.check_scene_handoffs(show,world)
assert check is not None
assert len(check[0])==0,str(check)
result['handoff_check']=str(check)
result['camera_sample_api']=unreal.InfinityStageCameraRig.get_camera_view_at_master_frame.__doc__
result['dirty']=[p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
assert not result['dirty'],result['dirty']
result['status']='passed'
(folder/'authoring_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
unreal.log('SCENE_TRANSITION_AUTHORING_VERIFY_SUCCESS|scenes='+str(len(result['scenes']))+'|handoffs='+str(check)+'|dirty=0')
