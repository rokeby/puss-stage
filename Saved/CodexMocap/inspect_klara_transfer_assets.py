import json
import pathlib
import unreal

folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
registry=unreal.AssetRegistryHelpers.get_asset_registry()
root='/Game/Metahuman/FullTakes_20260910/RawAnimations'
takes=['shoreguy1','shoreguy12','shoreguy3','shoreguy4','shoreguy5','shoreguy6','child1','child2']
out=[]
for take in takes:
    anim=unreal.load_asset(root+'/AS_'+take+'_Body_Full')
    mesh=unreal.load_asset(root+'/SK_'+take+'_Body_Full')
    assert anim and mesh,take
    skeleton=anim.get_editor_property('skeleton')
    assert skeleton,take+' skeleton'
    row={
        'take':take,
        'animation':anim.get_path_name(),
        'animation_package':anim.get_outermost().get_path_name(),
        'source_mesh':mesh.get_path_name(),
        'source_mesh_package':mesh.get_outermost().get_path_name(),
        'skeleton':skeleton.get_path_name(),
        'skeleton_package':skeleton.get_outermost().get_path_name(),
        'sampled_keys':anim.get_number_of_sampled_keys(),
        'play_length_seconds':anim.get_play_length(),
        'target_frame_rate':str(anim.get_editor_property('target_frame_rate')),
        'animation_dependencies':[],
        'mesh_dependencies':[]
    }
    for field,asset in [('animation_dependencies',anim),('mesh_dependencies',mesh)]:
        package=asset.get_outermost().get_path_name()
        try:
            dependencies=registry.get_dependencies(package,unreal.AssetRegistryDependencyOptions(True,True,True,False))
        except Exception:
            dependencies=registry.get_dependencies(package)
        row[field]=sorted(str(p) for p in dependencies)
    out.append(row)
(folder/'klara_transfer_asset_inspection.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
unreal.log('KLARA_TRANSFER_ASSET_INSPECTION_SUCCESS|takes=8|'+json.dumps(out))
