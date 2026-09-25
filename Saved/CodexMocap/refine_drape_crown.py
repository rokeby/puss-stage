import json
import pathlib
import unreal
root='/Game/Metahuman/ShoreCast_20260910'
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
unreal.LevelSequenceEditorBlueprintLibrary.pause()
cloth=unreal.load_asset(root+'/Cloth/CA_ShoreHeadDrape')
df=cloth.get_editor_property('dataflow_instance').get_editor_property('dataflow_asset')
mesh=unreal.load_asset('/Game/Scenes/SM_OrtalanSheet')
dynamic,outcome=unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(mesh,unreal.DynamicMesh(),unreal.GeometryScriptCopyMeshFromAssetOptions(),unreal.GeometryScriptMeshReadLOD())
assert outcome==unreal.GeometryScriptOutcomePins.SUCCESS
pin_positions=[]
for idx in range(unreal.GeometryScript_MeshQueries.get_num_vertex_i_ds(dynamic)):
    pos,valid=unreal.GeometryScript_MeshQueries.get_vertex_position(dynamic,idx)
    if valid and pos.x*pos.x+pos.y*pos.y<=7.1*7.1:
        pin_positions.append({'index':idx,'position':[pos.x,pos.y,pos.z]})
pins=[p['index'] for p in pin_positions]
assert len(pins)==9
assert unreal.DataflowEditorBlueprintLibrary.set_dataflow_node_property(df,'ShoreCrownPins','Indices','('+','.join(map(str,pins))+')')
unreal.DataflowBlueprintLibrary.evaluate_terminal_node_by_name(df,'ClothAssetTerminal',cloth)
assert unreal.EditorAssetLibrary.save_loaded_asset(cloth,only_if_is_dirty=False)
sub=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
lib=unreal.SubobjectDataBlueprintFunctionLibrary
cast=json.loads((folder/'shore_draped_cast_components.json').read_text(encoding='utf-8'))
for p in cast:
    bp=unreal.load_asset(p['blueprint'])
    for h in sub.k2_gather_subobject_data_for_blueprint(bp):
        d=lib.get_data(h)
        c=lib.get_object_for_blueprint(d,bp)
        if isinstance(c,unreal.GroomComponent):
            c.set_editor_property('visible',False)
            c.set_editor_property('hidden_in_game',True)
    assert unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if a.get_actor_label()=='Shore01_M56 Drape Pilot':
        for c in a.get_components_by_class(unreal.GroomComponent):
            c.set_visibility(False)
            c.set_hidden_in_game(True)
        c=a.get_component_by_class(unreal.ChaosClothComponent)
        c.recreate_cloth_simulation_proxy()
        a.call_method('ConfigureShoreDrape')
        c.force_next_update_teleport_and_reset()
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
r=json.loads((folder/'shore_pinned_drape.json').read_text(encoding='utf-8'))
r.update({'crown_pin_indices':pins,'crown_pins':pin_positions,'crown_patch_local_cm':[10,10],'grooms_hidden_in_draped_copies':True,'verification':'Saved crown selection; motion coverage review in progress'})
(folder/'shore_pinned_drape.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(300)
unreal.LevelSequenceEditorBlueprintLibrary.play()
unreal.log('SHORE_CROWN_PATCH_REFINED_SAVED|nine_pins|six_draped_copies')
