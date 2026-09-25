import json
import pathlib
import unreal
folder = pathlib.Path('E:/PussStage/Saved/CodexMocap')
cloth = unreal.load_asset('/Game/Scenes/CA__OrtolanSheets')
df = cloth.get_editor_property('dataflow_instance').get_editor_property('dataflow_asset')
actor = next(a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if a.get_actor_label() == 'Shore01_M56 Drape Pilot')
component = actor.get_component_by_class(unreal.ChaosClothComponent)
out = {'cloth_api': dir(cloth), 'dataflow_api': dir(df), 'dataflow_functions': {}, 'component_state': {}, 'classes': [n for n in dir(unreal) if any(k in n for k in ['Dataflow','ClothAsset','ObjectExporter','RenderTarget'])]}
for name in ['blend_weight','enable_simulation','suspend_simulation','simulate_in_editor','component_tick','visibility_based_anim_tick_option','use_attached_parent_as_pose_component','forced_lod_model']:
    try: out['component_state'][name] = str(component.get_editor_property(name))
    except Exception as e: out['component_state'][name] = str(e)
out['component_state']['enabled'] = component.is_simulation_enabled()
out['component_state']['suspended'] = component.is_simulation_suspended()
for name in ['DataflowBlueprintLibrary','DataflowEditorBlueprintLibrary','Dataflow','RenderingLibrary','Exporter','AutomationEditorTask']:
    cls = getattr(unreal, name, None)
    out['dataflow_functions'][name] = {n: getattr(getattr(cls,n,None),'__doc__',None) for n in dir(cls) if any(k in n for k in ['export','node','graph','task','capture','evaluate'])}
task = unreal.AssetExportTask()
task.object = df
task.filename = str(folder / 'ortolan_dataflow.t3d')
task.automated = True
task.prompt = False
task.replace_identical = True
task.exporter = unreal.ObjectExporterT3D()
out['export'] = unreal.Exporter.run_asset_export_task(task)
out['export_errors'] = [str(x) for x in task.errors]
(folder/'cloth_pinning_probe.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
unreal.log('CLOTH_PINNING_PROBE_SUCCESS|' + json.dumps(out['component_state']))
