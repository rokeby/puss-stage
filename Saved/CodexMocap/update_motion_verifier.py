import importlib, json, pathlib
import unreal
import verify_saved
importlib.reload(verify_saved)
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap/Verification')
for path in folder.glob('*.json'):
    report=json.loads(path.read_text(encoding='utf-8'))
    animation=unreal.load_asset(report['animation'])
    report['exported_motion']=verify_saved.verify_motion(animation,report['coverage']['total_frames'])
    report['pipeline']=verify_saved.verify_pipeline_log({'stem':path.stem})
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    unreal.log('MOCAP_EXPORT_MOTION_VERIFIED|'+path.stem+'|tracks='+str(report['exported_motion']['bone_tracks']))
unreal.log('MOCAP_MOTION_VERIFIER_READY')
