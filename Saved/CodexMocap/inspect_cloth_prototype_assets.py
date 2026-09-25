"""Read the original drape's Dataflow and the authoring APIs; do not mutate assets."""
import json
import pathlib
import unreal

project = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
assert project == pathlib.Path('E:/PussStage').resolve()
cloth = unreal.load_asset('/Game/Scenes/CA__OrtolanSheets')
assert cloth
data = {'cloth': cloth.get_path_name(), 'properties': {}, 'api': {}}
def encode(value):
    if isinstance(value, unreal.Object):
        return value.get_path_name()
    if hasattr(value, 'export_text'):
        return value.export_text()
    return str(value)
for name in ['dataflow_instance', 'skeleton', 'physics_asset', 'materials']:
    try:
        data['properties'][name] = encode(cloth.get_editor_property(name))
    except Exception as exc:
        data['properties'][name] = str(exc)
instance = cloth.get_editor_property('dataflow_instance')
flow = instance.get_editor_property('dataflow_asset')
data['dataflow'] = flow.get_path_name() if flow else None
if flow:
    try:
        data['nodes'] = [{'name': node.get_name(), 'class': node.get_class().get_path_name()}
                         for node in flow.get_editor_property('nodes')]
    except Exception as exc:
        data['nodes_error'] = str(exc)
for class_name, names in {
    'SubobjectDataBlueprintFunctionLibrary': ['get_data', 'get_object', 'get_object_for_blueprint', 'get_variable_name', 'is_inherited_component'],
    'SubobjectDataSubsystem': ['k2_gather_subobject_data_for_blueprint', 'add_new_subobject', 'rename_subobject'],
    'BlueprintEditorLibrary': ['compile_blueprint'],
    'Actor': ['get_component_by_class', 'get_components_by_tag'],
    'SkeletalMeshComponent': ['get_physics_asset', 'get_bone_location', 'get_socket_transform'],
    'ChaosClothComponent': ['add_collision_source', 'set_asset', 'set_simulate_in_editor'],
    'DataflowBlueprintLibrary': ['get_dataflow_variables', 'get_dataflow_variable'],
}.items():
    cls = getattr(unreal, class_name, None)
    data['api'][class_name] = {name: getattr(getattr(cls, name, None), '__doc__', None) for name in names}
(project / 'Saved/CodexMocap/cloth_prototype_asset_inspection.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
unreal.log('SHORE_CLOTH_ASSETS_INSPECTED|' + json.dumps({k:v for k,v in data.items() if k != 'api'}))
