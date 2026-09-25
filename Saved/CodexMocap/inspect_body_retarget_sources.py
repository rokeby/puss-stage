import json
import pathlib
import unreal
results = {}
for path in ['/Game/Metahuman/FullTakes_20260910/RawAnimations/SK_shoreguy1_Body_Full',
             '/MetaHumanBodyTracker/SKM_Body', '/MetaHumanBodyTracker/RTG_MH_IKRig',
             '/MetaHumanCharacter/Animation/Retargeting/RTG_MH_IKRig']:
    obj = unreal.load_asset(path)
    entry = {'class': obj.get_class().get_path_name() if obj else None}
    if isinstance(obj, unreal.SkeletalMesh):
        entry['skeleton'] = obj.get_editor_property('skeleton').get_path_name()
    if isinstance(obj, unreal.IKRetargeter):
        controller = unreal.IKRetargeterController.get_controller(obj)
        for side in [unreal.RetargetSourceOrTarget.SOURCE, unreal.RetargetSourceOrTarget.TARGET]:
            rig = controller.get_ik_rig(side)
            preview = controller.get_preview_mesh(side)
            entry[str(side)] = {'rig': rig.get_path_name() if rig else None, 'preview': preview.get_path_name() if preview else None}
    results[path] = entry
p = unreal.load_asset('/Game/Metahuman/FullTakes_20260910/Performances/MHP_shoreguy1_Full')
settings = unreal.MetaHumanPerformanceExportUtils.get_export_animation_sequence_settings(p)
for property_name in ['source_skeletal_mesh', 'SourceSkeletalMesh']:
    try:
        results[property_name] = str(settings.get_editor_property(property_name))
    except Exception as exc:
        results[property_name] = str(exc)
results['batch_api'] = unreal.IKRetargetBatchOperation.__doc__
results['batch_methods'] = {n: getattr(unreal.IKRetargetBatchOperation, n).__doc__ for n in dir(unreal.IKRetargetBatchOperation) if 'retarget' in n.lower()}
results['set_object_property_api'] = getattr(getattr(unreal.SystemLibrary, 'set_object_property_by_name', None), '__doc__', None)
pathlib.Path('E:/PussStage/Saved/CodexMocap/body_retarget_sources.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
unreal.log('BODY_RETARGET_SOURCES_INSPECTED|' + json.dumps(results))
