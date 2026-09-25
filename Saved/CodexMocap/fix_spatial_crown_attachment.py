import json
import pathlib
import unreal
root='/Game/Metahuman/ShoreCast_20260910'
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
unreal.LevelSequenceEditorBlueprintLibrary.pause()
cloth=unreal.load_asset(root+'/Cloth/CA_ShoreHeadDrape')
df=cloth.get_editor_property('dataflow_instance').get_editor_property('dataflow_asset')
lib=unreal.DataflowEditorBlueprintLibrary
def node(typ,name,x,y):
    if unreal.find_object(df,name): return name
    result=lib.add_dataflow_node(df,typ,name,unreal.Vector2D(x,y))
    assert str(result)!='None',(typ,name)
    return str(result)
def prop(n,p,v):
    assert lib.set_dataflow_node_property(df,n,p,v),(n,p,v)
def link(a,p,b,q):
    assert lib.connect_dataflow_nodes(df,a,p,b,q),(a,p,b,q)
distance=node('FDataflowDistanceFromSphereFloatSamplerNode','ShoreCrownDistance',200,1150)
falloff=node('FDataflowSmoothStepFloatSamplerNode','ShoreCrownFalloff',500,1150)
weights=node('FDataflowSamplerToAttributeNode','ShoreSpatialCrownWeights',850,1150)
prop(distance,'DistanceFromSphereSampler','(Sphere=(Center=(X=0,Y=0,Z=0),W=0))')
prop(falloff,'SmoothStepSampler','(MinValue=3,MaxValue=14,ValueA=0,ValueB=1)')
prop(weights,'AttributeName','ShoreCrownMaxDistance')
prop(weights,'VertexGroup','(Name="SimVertices3D")')
prop('ShoreCrownPins','Indices','()')
prop('SimulationMaxDistanceConfig','MaxDistance','(bIsAnimatable=True,Low=0,High=140,WeightMap="ShoreCrownMaxDistance")')
link(distance,'Sampler',falloff,'Sampler')
link(falloff,'Sampler',weights,'Sampler')
link('TransferSkinWeights','Collection',weights,'Collection')
link(weights,'Collection','SimulationMaxDistanceConfig','Collection')
link(weights,'AttributeName','SimulationMaxDistanceConfig','MaxDistance.WeightMap')
unreal.DataflowBlueprintLibrary.evaluate_terminal_node_by_name(df,'ClothAssetTerminal',cloth)
assert unreal.EditorAssetLibrary.save_loaded_asset(cloth,only_if_is_dirty=False)
sub=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
dl=unreal.SubobjectDataBlueprintFunctionLibrary
cast=json.loads((folder/'shore_draped_cast_components.json').read_text(encoding='utf-8'))
for p in cast:
    bp=unreal.load_asset(p['blueprint'])
    for h in sub.k2_gather_subobject_data_for_blueprint(bp):
        d=dl.get_data(h)
        if str(dl.get_variable_name(d))=='ShoreHeadCloth':
            c=dl.get_object_for_blueprint(d,bp)
            c.set_editor_property('relative_location',unreal.Vector(15,0,0))
            break
    assert unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
actor=next(a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if a.get_actor_label()=='Shore01_M56 Drape Pilot')
c=actor.get_component_by_class(unreal.ChaosClothComponent)
c.set_editor_property('relative_location',unreal.Vector(15,0,0))
c.recreate_cloth_simulation_proxy()
actor.call_method('ConfigureShoreDrape')
c.force_next_update_teleport_and_reset()
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
report={'asset':cloth.get_path_name(),'method':'Spatial distance sampler on actual SimVertices3D positions, independent of imported vertex numbering','center_local_cm':[0,0,0],'fixed_radius_local_cm':3,'smooth_falloff_end_local_cm':14,'maximum_distance_cm':140,'head_anchor_local_x_cm':15,'old_explicit_selection_empty':True,'render_validation':'pending'}
(folder/'shore_spatial_crown_attachment.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(300)
unreal.LevelSequenceEditorBlueprintLibrary.play()
unreal.log('SHORE_SPATIAL_CROWN_ATTACHMENT_SAVED|' + json.dumps(report))
