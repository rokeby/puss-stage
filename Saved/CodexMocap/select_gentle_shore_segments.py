import json
import math
import pathlib
import unreal
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
cast=json.loads((folder/'shore_cast_fitted_animations.json').read_text(encoding='utf-8'))['characters']
results=[]
opts=unreal.AnimPoseEvaluationOptions()
bones=['head','pelvis','hand_l','hand_r','foot_l','foot_r']
for person in cast:
    anim=unreal.load_asset(person['animation'])
    opts.optional_skeletal_mesh=unreal.load_asset(person['body_mesh'])
    samples=[]
    for step in range(8,int(person['seconds']*2)-8):
        sec=step*0.5
        pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(anim,sec,opts)
        locations={}
        for bone in bones:
            t=unreal.AnimPoseExtensions.get_bone_pose(pose,bone,unreal.AnimPoseSpaces.WORLD)
            p=t.translation
            locations[bone]=[p.x,p.y,p.z]
        samples.append({'time':sec,'bones':locations})
    candidates=[]
    # 18 seconds of source at 0.60 speed covers the 26.57-second clam sequence.
    n=37
    for i in range(0,len(samples)-n):
        s=samples[i:i+n]
        energy=0.0
        for prev,cur in zip(s,s[1:]):
            for bone,w in [('head',1),('pelvis',1.5),('hand_l',0.4),('hand_r',0.4),('foot_l',2),('foot_r',2)]:
                energy+=w*sum((a-b)**2 for a,b in zip(prev['bones'][bone],cur['bones'][bone]))
        head_z=[x['bones']['head'][2] for x in s]
        hand_z=[x['bones'][b][2] for x in s for b in ['hand_l','hand_r']]
        score=energy/(n-1)+max(0,max(hand_z)-105)**2+max(0,max(head_z)-min(head_z)-14)**2+4*max(0,120-min(head_z))**2
        candidates.append({'start_seconds':s[0]['time'],'source_duration_seconds':18,'play_rate':0.60,'score':score,'head_height_range_cm':[min(head_z),max(head_z)],'max_hand_height_cm':max(hand_z)})
    best=min(candidates,key=lambda x:x['score'])
    results.append({'id':person['id'],'animation':person['animation'],'selected':best,'source_samples':samples,'top_candidates':sorted(candidates,key=lambda x:x['score'])[:4]})
(folder/'shore_gentle_motion_selection.json').write_text(json.dumps({'method':'0.5-second pose samples; minimize movement energy, raised hands and large vertical head excursions','characters':results},indent=2),encoding='utf-8')
unreal.log('SHORE_GENTLE_SEGMENTS_SELECTED|' + json.dumps([{'id':r['id'],**r['selected']} for r in results]))
