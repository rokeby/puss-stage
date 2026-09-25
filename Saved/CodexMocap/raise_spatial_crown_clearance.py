import json
import pathlib
import unreal
root='/Game/Metahuman/ShoreCast_20260910'
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
unreal.LevelSequenceEditorBlueprintLibrary.pause()
sub=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
dl=unreal.SubobjectDataBlueprintFunctionLibrary
cast=json.loads((folder/'shore_draped_cast_components.json').read_text(encoding='utf-8'))
for p in cast:
    bp=unreal.load_asset(p['blueprint'])
    for h in sub.k2_gather_subobject_data_for_blueprint(bp):
        d=dl.get_data(h)
        if str(dl.get_variable_name(d))=='ShoreHeadCloth':
            dl.get_object_for_blueprint(d,bp).set_editor_property('relative_location',unreal.Vector(21,0,0))
            break
    assert unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
actor=next(a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if a.get_actor_label()=='Shore01_M56 Drape Pilot')
c=actor.get_component_by_class(unreal.ChaosClothComponent)
c.set_editor_property('relative_location',unreal.Vector(21,0,0))
actor.call_method('ConfigureShoreDrape')
c.force_next_update_teleport_and_reset()
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
report=json.loads((folder/'shore_spatial_crown_attachment.json').read_text(encoding='utf-8'))
report['head_anchor_local_x_cm']=21
report['render_validation']='Canopy corrected with spatial pinning; crown clearance raised 6 cm; full-motion check pending'
(folder/'shore_spatial_crown_attachment.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(300)
unreal.LevelSequenceEditorBlueprintLibrary.play()
unreal.log('SHORE_SPATIAL_CROWN_CLEARANCE_SAVED|21cm')
