import json
import pathlib
import shutil
import time
import unreal

folder=pathlib.Path('E:/PussStage/Saved/CodexSceneTransitions')
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world=editor.get_editor_world()
assert world.get_path_name().startswith('/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.')
assert editor.get_game_world() is None
def dirty():
    return [p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
assert not dirty(),dirty()
show=unreal.load_asset('/Game/InfinityStage/Dev/DA_InfinityStage_V1Show')
root=next(a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if isinstance(a,unreal.InfinityStageShowRoot))
master=root.master_sequence
scene3=unreal.load_asset('/Game/InfinityStage/Dev/Sequences/LS_DevScene_03')
backup=pathlib.Path((folder/'backup_path.txt').read_text().strip())/'BeforeAuthoring'
originals=[show.get_path_name(),master.get_path_name(),scene3.get_path_name(),world.get_path_name()]
for objpath in originals:
    package=objpath.split('.')[0]
    relative='Content/'+package.removeprefix('/Game/')+('.umap' if package.endswith('L_InfinityStage_V1VerticalSlice') else '.uasset')
    dest=backup/relative;dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(pathlib.Path('E:/PussStage')/relative,dest)
changes=[]
cues=list(show.cues)
for i,cue in enumerate(cues):
    if cue.type!=unreal.InfinityCueType.SCENE:continue
    scene=cue.scene
    changes.append({'label':str(cue.label),'previous_use_sequence_length':scene.use_sequence_length,'old_duration_ticks':scene.duration_frames.value})
    scene.set_editor_property('use_sequence_length',True)
    cue.set_editor_property('scene',scene);cues[i]=cue
assert len(changes)==6
show.set_editor_property('cues',cues)
root.transport.set_editor_property('auto_play_scene_after_passage',True)
# Extend the preceding shot across each gap without shifting the incoming shot,
# its keyed animation, or the artist's containing Scene playback range.
cuts=sorted([s for t in scene3.get_tracks() if isinstance(t,unreal.MovieSceneCameraCutTrack) for s in t.get_sections()],key=lambda s:s.get_start_frame())
assert len(cuts)==3
cut_changes=[]
for i,cut in enumerate(cuts):
    target=cuts[i+1].get_start_frame() if i+1<len(cuts) else scene3.get_playback_end()
    previous=cut.get_end_frame()
    if previous<target:
        cut.set_end_frame(target)
        cut_changes.append({'start':cut.get_start_frame(),'old_end':previous,'new_end':target})
report=unreal.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show,master)
assert (bool(report[0]) if isinstance(report,tuple) else bool(report)),report
allowed={p.split('.')[0] for p in originals}
assert set(dirty()).issubset(allowed),dirty()
for asset in (show,scene3,master):
    assert unreal.EditorAssetLibrary.save_loaded_asset(asset,False),asset.get_path_name()
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
assert not dirty(),dirty()
result={'status':'saved','utc':time.time(),'changes':changes,'cut_changes':cut_changes,'master_report':str(report),'auto_play_scene_after_passage':root.transport.auto_play_scene_after_passage,'scene3_playback':[scene3.get_playback_start(),scene3.get_playback_end()],'backup':str(backup),'dirty':dirty()}
(folder/'authoring_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
unreal.log('SCENE_TRANSITION_AUTHORING_SAVED|scenes=6|cut_gaps='+str(len(cut_changes))+'|auto_scene=1|dirty=0')
