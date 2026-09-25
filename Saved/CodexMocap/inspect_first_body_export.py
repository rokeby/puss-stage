import json
import pathlib
import unreal
folder = pathlib.Path('E:/PussStage/Saved/CodexMocap')
paths = ['/Game/Metahuman/FullTakes_20260910/RawAnimations/AS_shoreguy1_Body_Full',
         '/Game/Metahuman/ShoreCast_20260910/Animations/AS_Shore01_M56_shoreguy1']
result = []
for path in paths:
    animation = unreal.load_asset(path)
    assert animation
    names = [str(n) for n in unreal.AnimationLibrary.get_animation_track_names(animation)]
    record = {'path': path, 'skeleton': animation.get_editor_property('skeleton').get_path_name(),
              'num_frames': unreal.AnimationLibrary.get_num_frames(animation), 'tracks': names, 'poses': {}}
    for bone in ['root', 'pelvis', 'spine_01', 'spine_03', 'head', 'upperarm_l', 'thigh_l']:
        if bone in names:
            record['poses'][bone] = [unreal.AnimationLibrary.get_bone_pose_for_frame(animation, bone, f, False).export_text()
                                     for f in [0, 100, 500, 1000, 2000]]
    result.append(record)
retargeter = unreal.load_asset('/MetaHumanBodyTracker/RTG_MH_IKRig')
result.append({'retargeter_class': retargeter.get_class().get_path_name(),
               'retargeter_doc': unreal.IKRetargeter.__doc__})
(folder / 'first_body_export_inspection.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
unreal.log('FIRST_BODY_EXPORT_INSPECTED|' + json.dumps([{k: v for k,v in r.items() if k not in ['tracks', 'retargeter_doc']} for r in result]))
