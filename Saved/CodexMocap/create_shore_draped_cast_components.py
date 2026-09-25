import json
import pathlib
import unreal
root='/Game/Metahuman/ShoreCast_20260910'
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
cast=json.loads((folder/'shore_cast_assets.json').read_text(encoding='utf-8'))['characters']
cloth_asset=unreal.load_asset(root+'/Cloth/CA_ShoreHeadDrape')
mat=unreal.load_asset(root+'/Cloth/M_ShoreLinen')
assert cloth_asset and mat
sub=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
lib=unreal.SubobjectDataBlueprintFunctionLibrary
report=[]
unreal.LevelSequenceEditorBlueprintLibrary.pause()
for person in cast:
    destination=root+'/SceneCharacters/BP_'+person['id']+'_Draped'
    if unreal.EditorAssetLibrary.does_asset_exist(destination):
        bp=unreal.load_asset(destination)
        handles=sub.k2_gather_subobject_data_for_blueprint(bp)
        assert any(str(lib.get_variable_name(lib.get_data(h)))=='ShoreHeadCloth' for h in handles)
    else:
        bp=unreal.EditorAssetLibrary.duplicate_asset(person['blueprint'],destination)
        assert bp
        handles=sub.k2_gather_subobject_data_for_blueprint(bp)
        body_handle=next(h for h in handles if str(lib.get_variable_name(lib.get_data(h)))=='Body')
        body=lib.get_object_for_blueprint(lib.get_data(body_handle),bp)
        assert body.get_skeletal_mesh_asset().get_path_name()==person['body_mesh']
        handle,reason=sub.add_new_subobject(unreal.AddNewSubobjectParams(parent_handle=body_handle,new_class=unreal.ChaosClothComponent,blueprint_context=bp))
        assert not str(reason),str(reason)
        assert sub.rename_subobject(handle,'ShoreHeadCloth')
        c=lib.get_object_for_blueprint(lib.get_data(handle),bp)
        c.set_asset(cloth_asset)
        c.set_material(0,mat)
        c.set_editor_property('use_attached_parent_as_pose_component',False)
        c.set_editor_property('relative_location',unreal.Vector(21,0,0))
        c.set_editor_property('relative_rotation',unreal.Rotator(pitch=-90,yaw=0,roll=0))
        c.set_editor_property('relative_scale3d',unreal.Vector(1.641315,1.641315,1.641315))
        c.set_simulate_in_editor(True)
        assert unreal.BlueprintEditorLibrary.compile_blueprint(bp)
        assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
    bodymesh=unreal.load_asset(person['body_mesh'])
    report.append({'id':person['id'],'blueprint':bp.get_path_name(),'physics_asset':bodymesh.get_editor_property('physics_asset').get_path_name(),'graph_status':'pending' if person['id']!='Shore01_M56' else 'configured'})
(folder/'shore_draped_cast_components.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.log('ALL_SIX_DRAPED_CHARACTER_COMPONENTS_SAVED|'+str(len(report)))
