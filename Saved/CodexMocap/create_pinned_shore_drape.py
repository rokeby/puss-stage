import json
import pathlib
import unreal
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
root='/Game/Metahuman/ShoreCast_20260910'
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert world.get_path_name().startswith(root+'/Review/L_ShoreDrape_Pilot.')
assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
unreal.LevelSequenceEditorBlueprintLibrary.pause()
mesh=unreal.load_asset('/Game/Scenes/SM_OrtalanSheet')
dynamic=unreal.DynamicMesh()
dynamic,outcome=unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(mesh,dynamic,unreal.GeometryScriptCopyMeshFromAssetOptions(),unreal.GeometryScriptMeshReadLOD())
assert outcome==unreal.GeometryScriptOutcomePins.SUCCESS
vertices=[]
for idx in range(unreal.GeometryScript_MeshQueries.get_num_vertex_i_ds(dynamic)):
    p,valid=unreal.GeometryScript_MeshQueries.get_vertex_position(dynamic,idx)
    if valid: vertices.append({'index':idx,'position':[p.x,p.y,p.z]})
pins=[v for v in vertices if v['position'][0]**2+v['position'][1]**2 <= 4.0**2]
assert 1 <= len(pins) <= 81, len(pins)
path=root+'/Cloth/CA_ShoreHeadDrape'
cloth=unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else unreal.EditorAssetLibrary.duplicate_asset('/Game/Scenes/CA__OrtolanSheets',path)
assert cloth
df=cloth.get_editor_property('dataflow_instance').get_editor_property('dataflow_asset')
assert df.get_path_name().startswith(path+'.'), df.get_path_name()
lib=unreal.DataflowEditorBlueprintLibrary
pin_name='ShoreCrownPins' if unreal.find_object(df,'ShoreCrownPins') else lib.add_dataflow_node(df,'FChaosClothAssetSelectionNode_v2','ShoreCrownPins',unreal.Vector2D(800,850))
assert str(pin_name)!='None'
def setprop(node,name,value):
    assert lib.set_dataflow_node_property(df,node,name,value), (node,name,value)
setprop(pin_name,'OutputName','(StringValue="ShoreCrownPins")')
setprop(pin_name,'Group','(Name="SimVertices3D")')
setprop(pin_name,'Indices','('+','.join(str(v['index']) for v in pins)+')')
assert lib.connect_dataflow_nodes(df,'WeightMap_MaxDistance','Collection',pin_name,'Collection')
assert lib.connect_dataflow_nodes(df,pin_name,'Collection','SimulationMaxDistanceConfig','Collection')
assert lib.connect_dataflow_nodes(df,pin_name,'OutputName.StringValue','SimulationMaxDistanceConfig','InKinematic.StringValue')
unreal.DataflowBlueprintLibrary.evaluate_terminal_node_by_name(df,'ClothAssetTerminal',cloth)
material_path=root+'/Cloth/M_ShoreLinen'
mat=unreal.AssetToolsHelpers.get_asset_tools().create_asset('M_ShoreLinen',root+'/Cloth',unreal.Material,unreal.MaterialFactoryNew())
assert mat
mat.set_editor_property('two_sided',True)
base=unreal.MaterialEditingLibrary.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector,-350,-100)
base.set_editor_property('constant',unreal.LinearColor(0.58,0.55,0.48,1.0))
rough=unreal.MaterialEditingLibrary.create_material_expression(mat,unreal.MaterialExpressionConstant,-350,80)
rough.set_editor_property('r',0.94)
unreal.MaterialEditingLibrary.connect_material_property(base,'',unreal.MaterialProperty.MP_BASE_COLOR)
unreal.MaterialEditingLibrary.connect_material_property(rough,'',unreal.MaterialProperty.MP_ROUGHNESS)
unreal.MaterialEditingLibrary.recompile_material(mat)
assert unreal.EditorAssetLibrary.save_loaded_asset(mat,only_if_is_dirty=False)
materials=list(cloth.get_editor_property('materials'))
assert len(materials)==1
materials[0].set_editor_property('material_interface',mat)
cloth.set_editor_property('materials',materials)
assert unreal.EditorAssetLibrary.save_loaded_asset(cloth,only_if_is_dirty=False)
bp=unreal.load_asset(root+'/SceneCharacters/BP_Shore01_M56_Draped')
sub=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
dl=unreal.SubobjectDataBlueprintFunctionLibrary
for h in sub.k2_gather_subobject_data_for_blueprint(bp):
    data=dl.get_data(h)
    if str(dl.get_variable_name(data))=='ShoreHeadCloth':
        c=dl.get_object_for_blueprint(data,bp)
        c.set_asset(cloth)
        c.set_material(0,mat)
        c.set_editor_property('relative_location',unreal.Vector(21,0,0))
        break
else: raise RuntimeError('No cloth template')
assert unreal.BlueprintEditorLibrary.compile_blueprint(bp)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
actor=next(a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if a.get_actor_label()=='Shore01_M56 Drape Pilot')
c=actor.get_component_by_class(unreal.ChaosClothComponent)
c.set_asset(cloth)
c.set_material(0,mat)
c.set_editor_property('relative_location',unreal.Vector(21,0,0))
actor.call_method('ConfigureShoreDrape')
c.force_next_update_teleport_and_reset()
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
report={'asset':cloth.get_path_name(),'dataflow':df.get_path_name(),'material':mat.get_path_name(),'source_vertices':len(vertices),'crown_pins':pins,'pin_radius_local_cm':4,'component_scale':1.641315,'head_anchor_local_x_cm':21,'verification':'Explicit kinematic selection added; runtime coverage validation pending'}
(folder/'shore_pinned_drape.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(300)
unreal.LevelSequenceEditorBlueprintLibrary.play()
unreal.log('SHORE_CROWN_PINNED_DRAPE_SAVED|' + json.dumps(report))
