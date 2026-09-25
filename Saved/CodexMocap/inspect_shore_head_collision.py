import json
import pathlib
import re
import unreal
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
cast=json.loads((folder/'shore_draped_cast_components.json').read_text(encoding='utf-8'))
out=[]
for p in cast:
    phys=unreal.load_asset(p['physics_asset'])
    task=unreal.AssetExportTask()
    task.object=phys
    task.filename=str(folder/(p['id']+'_physics.t3d'))
    task.automated=True
    task.prompt=False
    task.replace_identical=True
    task.exporter=unreal.ObjectExporterT3D()
    assert unreal.Exporter.run_asset_export_task(task)
    content=pathlib.Path(task.filename).read_text(encoding='utf-8-sig')
    names=re.findall(r'Begin Object Class=/Script/Engine.SkeletalBodySetup Name="([^"]+)"',content)
    bodies=[unreal.find_object(phys,n) for n in names]
    rows=[]
    for body in bodies:
        bone=str(body.get_editor_property('bone_name'))
        if any(t in bone for t in ['head','neck','spine']):
            rows.append({'bone':bone,'geometry':body.get_editor_property('agg_geom').export_text()})
    out.append({'id':p['id'],'bodies':rows})
(folder/'shore_head_collision_inspection.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
unreal.log('SHORE_HEAD_COLLISION_INSPECTED|' + json.dumps(out))
