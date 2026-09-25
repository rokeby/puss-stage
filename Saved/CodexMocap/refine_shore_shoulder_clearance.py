import builtins
import json
import pathlib
import re
import unreal
assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
root='/Game/Metahuman/ShoreCast_20260910'
unreal.LevelSequenceEditorBlueprintLibrary.pause()
cast=json.loads((folder/'shore_cast_brief.json').read_text(encoding='utf-8'))['characters']
rows=[]
for p in cast:
    cid=p['id']
    source=unreal.load_asset(root+'/Assembled/'+cid+'/MHC_'+cid+'/Body/PHYS_MHC_'+cid)
    phys=unreal.load_asset(root+'/Cloth/PHYS_'+cid+'_Drape')
    content=(folder/(cid+'_physics.t3d')).read_text(encoding='utf-8-sig')
    names=re.findall(r'Begin Object Class=/Script/Engine.SkeletalBodySetup Name="([^"]+)"',content)
    edits=[]
    for name in names:
        src=unreal.find_object(source,name)
        bone=str(src.get_editor_property('bone_name'))
        if bone not in ['clavicle_l','clavicle_r','upperarm_l','upperarm_r']:continue
        dst=unreal.find_object(phys,name)
        geom=dst.get_editor_property('agg_geom')
        capsules=list(geom.get_editor_property('sphyl_elems'))
        originals=list(src.get_editor_property('agg_geom').get_editor_property('sphyl_elems'))
        for i,c in enumerate(capsules):
            radius=float(originals[i].get_editor_property('radius'))
            c.set_editor_property('radius',radius+2.5)
            edits.append({'bone':bone,'radius_before':radius,'radius_after':radius+2.5})
        geom.set_editor_property('sphyl_elems',capsules);dst.set_editor_property('agg_geom',geom)
    assert len(edits)==4
    assert unreal.EditorAssetLibrary.save_loaded_asset(phys,only_if_is_dirty=False)
    rows.append({'id':cid,'physics_asset':phys.get_path_name(),'edits':edits})
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if a.get_actor_label().endswith(' Clam') and a.get_actor_label().startswith('Shore'):
        a.call_method('ConfigureShoreDrape')
        c=a.get_component_by_class(unreal.ChaosClothComponent)
        c.set_simulate_in_editor(True);c.force_next_update_teleport_and_reset()
(folder/'shore_shoulder_clearance.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
camera=next(a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if a.get_actor_label()=='Shore Cast Review Camera')
builtins.PUSS_SHORE_CLOSEUP_TASK=unreal.AutomationLibrary.take_high_res_screenshot(1920,1080,'E:/PussStage/Saved/CodexMocap/Shore_Cloth_Corrected_Closeup.png',camera=camera,delay=5.0)
unreal.log('SHORE_SHOULDER_CLEARANCE_SAVED|four_capsules_per_person|plus_2_5_cm|originals_unchanged')
