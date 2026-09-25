import json
import pathlib
import unreal
root='/Game/Metahuman/ShoreCast_20260910'
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
unreal.LevelSequenceEditorBlueprintLibrary.pause()
path=root+'/Cloth/CA_ShoreHeadDrape_Bowed'
cloth=unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else unreal.EditorAssetLibrary.duplicate_asset(root+'/Cloth/CA_ShoreHeadDrape',path)
assert cloth
df=cloth.get_editor_property('dataflow_instance').get_editor_property('dataflow_asset')
assert df.get_path_name().startswith(path+'.')
lib=unreal.DataflowEditorBlueprintLibrary
node='ShoreSkullTop'
if not unreal.find_object(df,node):
    assert str(lib.add_dataflow_node(df,'FChaosClothAssetTransformPositionsNode',node,unreal.Vector2D(1120,1150)))==node
for key,value in {'bTransform3DSimPositions':'True','bTransformRenderPositions':'True','Sim3DTranslation':'(X=0,Y=0,Z=10)','RenderTranslation':'(X=0,Y=0,Z=10)'}.items():
    assert lib.set_dataflow_node_property(df,node,key,value),(key,value)
assert lib.connect_dataflow_nodes(df,'ShoreSpatialCrownWeights','Collection',node,'Collection')
assert lib.connect_dataflow_nodes(df,node,'Collection','SimulationMaxDistanceConfig','Collection')
unreal.DataflowBlueprintLibrary.evaluate_terminal_node_by_name(df,'ClothAssetTerminal',cloth)
assert unreal.EditorAssetLibrary.save_loaded_asset(cloth,only_if_is_dirty=False)
bp=unreal.load_asset(root+'/SceneCharacters/BP_Shore02_F52_Draped')
sub=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
dl=unreal.SubobjectDataBlueprintFunctionLibrary
def configure(c):
    c.set_asset(cloth)
    c.set_editor_property('absolute_rotation',True)
    c.set_editor_property('relative_rotation',unreal.Rotator(pitch=0,yaw=0,roll=0))
    c.set_editor_property('relative_location',unreal.Vector(6.179051,0.949429,0))
for h in sub.k2_gather_subobject_data_for_blueprint(bp):
    d=dl.get_data(h)
    if str(dl.get_variable_name(d))=='ShoreHeadCloth':
        configure(dl.get_object_for_blueprint(d,bp));break
else:raise RuntimeError('Missing cloth template')
assert unreal.BlueprintEditorLibrary.compile_blueprint(bp)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
actor=next(a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if a.get_actor_label()=='Shore02_F52 Draped Review')
c=actor.get_component_by_class(unreal.ChaosClothComponent)
configure(c)
actor.call_method('ConfigureShoreDrape')
c.set_simulate_in_editor(True)
c.force_next_update_teleport_and_reset()
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
report={'character':'Shore02_F52','cloth':cloth.get_path_name(),'attachment':'head socket, head-capsule center; gravity-aligned cloth orientation','skull_center_in_head_cm':[6.179051,0.949429,0],'rest_crown_above_skull_center_cm':16.41315,'rotation_absolute':True,'small_spatial_crown_pins_retained':True,'coverage_validation':'pending'}
(folder/'shore_bowed_drape.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.log('SHORE_BOWED_DRAPE_SKULL_ATTACHMENT_SAVED|'+json.dumps(report))
