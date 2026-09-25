import json
import pathlib
import re
import unreal
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
root='/Game/Metahuman/ShoreCast_20260910'
cast=json.loads((folder/'shore_draped_cast_components.json').read_text(encoding='utf-8'))
unreal.LevelSequenceEditorBlueprintLibrary.pause()
out=[]
for person in cast:
    dest=root+'/Cloth/PHYS_'+person['id']+'_Drape'
    source_path=root+'/Assembled/'+person['id']+'/MHC_'+person['id']+'/Body/PHYS_MHC_'+person['id']
    phys=unreal.load_asset(dest) if unreal.EditorAssetLibrary.does_asset_exist(dest) else unreal.EditorAssetLibrary.duplicate_asset(source_path,dest)
    assert phys
    content=(folder/(person['id']+'_physics.t3d')).read_text(encoding='utf-8-sig')
    names=re.findall(r'Begin Object Class=/Script/Engine.SkeletalBodySetup Name="([^"]+)"',content)
    head=next(unreal.find_object(phys,n) for n in names if str(unreal.find_object(phys,n).get_editor_property('bone_name'))=='head')
    geom=head.get_editor_property('agg_geom')
    capsules=list(geom.get_editor_property('sphyl_elems'))
    assert len(capsules)==1
    source_head=unreal.find_object(unreal.load_asset(source_path),head.get_name())
    old=float(source_head.get_editor_property('agg_geom').get_editor_property('sphyl_elems')[0].get_editor_property('radius'))
    capsules[0].set_editor_property('radius',old+3.0)
    geom.set_editor_property('sphyl_elems',capsules)
    head.set_editor_property('agg_geom',geom)
    assert unreal.EditorAssetLibrary.save_loaded_asset(phys,only_if_is_dirty=False)
    assert abs(head.get_editor_property('agg_geom').get_editor_property('sphyl_elems')[0].get_editor_property('radius')-(old+3))<0.001
    out.append({'id':person['id'],'physics_asset':phys.get_path_name(),'head_radius_before_cm':old,'head_radius_after_cm':old+3})
(folder/'shore_drape_collision_assets.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
actor=next(a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if a.get_actor_label()=='Shore01_M56 Drape Pilot')
body=next(c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()=='Body')
cloth=actor.get_component_by_class(unreal.ChaosClothComponent)
cloth.reset_collision_sources()
cloth.add_collision_source(body,unreal.load_asset(out[0]['physics_asset']),False)
cloth.force_next_update_teleport_and_reset()
unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(300)
unreal.LevelSequenceEditorBlueprintLibrary.play()
unreal.log('SHORE_CLOTH_COLLISION_COPIES_SAVED|' + str(len(out)))
