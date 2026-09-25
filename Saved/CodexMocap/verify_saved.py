"""Reload only this batch's output packages, then verify persisted body data."""
import json
import pathlib
import re
import unreal
from batch_runner import summarize_body, utc


def encode(v):
    if v is None or isinstance(v,(bool,int,float,str)):
        return v
    if isinstance(v,unreal.Object):
        return v.get_path_name()
    if hasattr(v,'export_text'):
        return v.export_text()
    try:
        return [encode(x) for x in v]
    except TypeError:
        return str(v)


def verify_motion(animation, expected_images):
    tracks=[str(n) for n in unreal.AnimationLibrary.get_animation_track_names(animation)]
    num_frames=unreal.AnimationLibrary.get_num_frames(animation)
    assert num_frames+1==expected_images, 'Exported animation sample count differs from the video'
    samples=sorted(set([0,num_frames//4,num_frames//2,3*num_frames//4,num_frames]))
    variations={}
    for name in ['root','pelvis','spine_01','upperarm_l','upperarm_r','thigh_l','thigh_r']:
        if name in tracks:
            poses=[unreal.AnimationLibrary.get_bone_pose_for_frame(animation,name,frame,False).export_text() for frame in samples]
            variations[name]=len(set(poses))
    assert sum(n>1 for n in variations.values())>=2, 'Exported body animation appears static'
    return {'bone_tracks':len(tracks),'sampled_keys':num_frames+1,'sample_frames':samples,'distinct_poses_by_bone':variations}


def verify_pipeline_log(job):
    log_path=pathlib.Path('E:/PussStage/Saved/Logs/PussStage_2.log')
    text=log_path.read_text(encoding='utf-8',errors='replace')
    start='MOCAP_TAKE_START|'+job['stem']+'|'
    finish='MOCAP_TAKE_COMPLETION_EVENT|'+job['stem']
    assert start in text and finish in text, 'Missing pipeline boundary markers'
    segment=text.rsplit(start,1)[1].split(finish,1)[0]
    stages=[int(x) for x in re.findall(r'Finished Pipeline \(Frame range \d+, Stage (\d+)\)',segment)]
    assert {1,2,3,4,5}.issubset(stages), 'Incomplete processing stages: '+str(stages)
    errors=[line for line in segment.splitlines() if re.search(r'Log(?:MetaHuman(?:Pipeline|Performance|BodyTracker|BodyOptimizer)|BodyTracker|Segmentation): Error:',line)]
    assert not errors,'Pipeline errors: '+'\n'.join(errors)
    return {'log':str(log_path),'completed_stages':stages,'pipeline_errors':errors}


def verify(job, manifest):
    p=unreal.load_asset(job['performance'])
    animation=unreal.load_asset(job['animation'])
    assert p and animation and not p.is_processing()
    packages=[p.get_outermost(),animation.get_outermost()]
    assert all(package.get_path_name().startswith(manifest['root']+'/') for package in packages)
    dirty={package.get_path_name() for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
    assert not any(package.get_path_name() in dirty for package in packages)
    reloaded,error=unreal.EditorLoadingAndSavingUtils.reload_packages(packages,unreal.ReloadPackagesInteractionMode.ASSUME_POSITIVE)
    assert reloaded and not str(error), 'Reload failed: '+str(error)
    p=unreal.load_asset(job['performance'])
    animation=unreal.load_asset(job['animation'])
    assert p.get_editor_property('footage_capture_data').get_path_name()==job['capture']
    assert p.get_editor_property('start_frame_to_process')==0
    assert p.get_editor_property('end_frame_to_process')==job['image_count']
    mismatches={k:[v,encode(p.get_editor_property(k))] for k,v in manifest['settings'].items()
                if v!=encode(p.get_editor_property(k))}
    assert not mismatches,str(mismatches)
    assert p.contains_animation_data_type(unreal.FrameAnimationDataType.BODY)
    coverage=summarize_body(p,job['image_count'])
    assert coverage==job['coverage'], 'Body data coverage changed after package reload'
    duration=float(animation.get_editor_property('sequence_length'))
    assert abs(duration-job['image_count']/30.0)<=1.01/30.0, str(duration)
    skeleton=animation.get_editor_property('skeleton')
    assert skeleton
    motion=verify_motion(animation,job['image_count'])
    pipeline=verify_pipeline_log(job)
    report={'verified_utc':utc(),'performance':p.get_path_name(),'animation':animation.get_path_name(),
            'skeleton':skeleton.get_path_name(),'duration_seconds':duration,'saved_settings_match':True,
            'packages_reloaded':True,'coverage':coverage,'exported_motion':motion,'pipeline':pipeline}
    folder=pathlib.Path('E:/PussStage/Saved/CodexMocap/Verification')
    folder.mkdir(exist_ok=True)
    (folder/(job['stem']+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    unreal.log('MOCAP_SAVED_READBACK_SUCCESS|'+job['stem']+'|body_frames='+str(coverage['body_frames'])+
               '|total_frames='+str(job['image_count'])+'|seconds='+str(duration))
    return report
