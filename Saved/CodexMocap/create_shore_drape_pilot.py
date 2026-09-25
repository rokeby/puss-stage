"""Create a scoped Blueprint copy with a head-attached drape; leave the source intact."""
import json
import pathlib
import unreal

root = '/Game/Metahuman/ShoreCast_20260910'
folder = pathlib.Path('E:/PussStage/Saved/CodexMocap')
assert pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve() == pathlib.Path('E:/PussStage').resolve()
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
cast = json.loads((folder / 'shore_cast_assets.json').read_text(encoding='utf-8'))
person = cast['characters'][0]
destination = root + '/SceneCharacters/BP_Shore01_M56_Draped'
assert not unreal.EditorAssetLibrary.does_asset_exist(destination), 'Inspect the existing pilot before changing it'
bp = unreal.EditorAssetLibrary.duplicate_asset(person['blueprint'], destination)
assert bp
sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
lib = unreal.SubobjectDataBlueprintFunctionLibrary
handles = sub.k2_gather_subobject_data_for_blueprint(bp)
body_handle = next(h for h in handles if str(lib.get_variable_name(lib.get_data(h))) == 'Body')
body = lib.get_object_for_blueprint(lib.get_data(body_handle), bp)
assert isinstance(body, unreal.SkeletalMeshComponent)
assert body.get_skeletal_mesh_asset().get_path_name() == person['body_mesh']
params = unreal.AddNewSubobjectParams(parent_handle=body_handle, new_class=unreal.ChaosClothComponent, blueprint_context=bp)
handle, reason = sub.add_new_subobject(params)
assert not str(reason), str(reason)
assert sub.rename_subobject(handle, 'ShoreHeadCloth')
cloth = lib.get_object_for_blueprint(lib.get_data(handle), bp)
assert isinstance(cloth, unreal.ChaosClothComponent)
cloth.set_asset(unreal.load_asset('/Game/Scenes/CA__OrtolanSheets'))
cloth.set_editor_property('use_attached_parent_as_pose_component', False)
assert cloth.attach_to_component(body, 'head', unreal.AttachmentRule.KEEP_RELATIVE,
                                 unreal.AttachmentRule.KEEP_RELATIVE, unreal.AttachmentRule.KEEP_RELATIVE, False)
cloth.set_editor_property('relative_location', unreal.Vector(16, 0, 0))
cloth.set_editor_property('relative_rotation', unreal.Rotator(pitch=-90, yaw=0, roll=0))
cloth.set_editor_property('relative_scale3d', unreal.Vector(1.641315, 1.641315, 1.641315))
cloth.set_simulate_in_editor(True)
assert unreal.BlueprintEditorLibrary.compile_blueprint(bp)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp, only_if_is_dirty=False)
report = {'blueprint': bp.get_path_name(), 'body_component': body.get_name(), 'cloth_component': cloth.get_name(),
          'cloth_parent': cloth.get_attach_parent().get_name(), 'socket': str(cloth.get_attach_socket_name()),
          'physics_asset': body.get_skeletal_mesh_asset().get_editor_property('physics_asset').get_path_name(),
          'collision_graph': 'pending', 'rendered_fit': 'pending'}
(folder / 'shore_drape_pilot.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
unreal.log('SHORE_DRAPE_PILOT_COMPONENT_SAVED|' + json.dumps(report))
