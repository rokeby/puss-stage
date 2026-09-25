import json
import pathlib
import unreal
folder = pathlib.Path('E:/PussStage/Saved/CodexMocap')
actor = next(a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if a.get_actor_label() == 'Shore01_M56 Drape Pilot')
c = actor.get_component_by_class(unreal.ChaosClothComponent)
i = c.get_cloth_outfit_interactor()
props = {}
if i:
    for n in i.get_all_property_names():
        props[str(n)] = {'weighted': str(i.get_weighted_float_property_value(n)), 'string': i.get_string_property_value(n)}
report = {'properties':props, 'level_api':{n:getattr(getattr(unreal.LevelEditorSubsystem,n), '__doc__',None) for n in dir(unreal.LevelEditorSubsystem) if any(k in n for k in ['play','simulate','realtime'])}, 'render_api':{n:getattr(getattr(unreal.AutomationLibrary,n),'__doc__',None) for n in dir(unreal.AutomationLibrary) if any(k in n for k in ['tick','play','simulate'])}}
(folder/'cloth_simulation_runtime.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.log('CLOTH_SIMULATION_PROPERTIES_SUCCESS|' + json.dumps(props))
