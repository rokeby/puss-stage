import json, pathlib
import unreal
animation=unreal.load_asset('/Game/Metahuman/FullTakes_20260910/RawAnimations/AS_shoreguy1_Body_Full')
tracks=[str(n) for n in unreal.AnimationLibrary.get_animation_track_names(animation)]
num_frames=unreal.AnimationLibrary.get_num_frames(animation)
samples=sorted(set([0,num_frames//4,num_frames//2,3*num_frames//4,num_frames]))
motions={}
for name in ['root','pelvis','spine_01','upperarm_l','upperarm_r','thigh_l','thigh_r']:
    if name not in tracks: continue
    poses=[unreal.AnimationLibrary.get_bone_pose_for_frame(animation,name,frame,False).export_text() for frame in samples]
    motions[name]={'distinct_poses':len(set(poses)),'first':poses[0],'last':poses[-1]}
result={'tracks':len(tracks),'track_names':tracks[:25],'num_frames':num_frames,'sample_frames':samples,'motions':motions}
pathlib.Path('E:/PussStage/Saved/CodexMocap/export_motion_probe.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
unreal.log('MOCAP_EXPORT_MOTION_PROBE|'+json.dumps(result))
