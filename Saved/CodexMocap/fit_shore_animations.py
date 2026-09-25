"""Fit saved shore performances to the six assembled bodies; never re-solve footage."""
import json
import pathlib
import sys
import unreal

project = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
assert project == pathlib.Path('E:/PussStage').resolve()
folder = project / 'Saved' / 'CodexMocap'
if str(folder) not in sys.path:
    sys.path.insert(0, str(folder))
import restart_common as common
from verify_saved import verify_motion


def fit_one(character, source, root):
    p = unreal.load_asset(source['performance'])
    body = unreal.load_asset(character['body_mesh'])
    assert p and body and isinstance(body, unreal.SkeletalMesh)
    assert not p.is_processing()
    assert p.contains_animation_data_type(unreal.FrameAnimationDataType.BODY)
    name = 'AS_' + character['id'] + '_' + source['stem'] + '_Full'
    path = root + '/Animations/' + name
    assert not unreal.EditorAssetLibrary.does_asset_exist(path), 'Existing animation must be reviewed before replacement: ' + path
    # PerformanceExport's required transient SourceSkeletalMesh is protected in
    # this UE build. Retarget the already verified full source animation through
    # the public batch API, which accepts both meshes explicitly.
    raw_animation = unreal.load_asset(source['animation'])
    raw_folder = source['animation'].split('/AS_')[0]
    source_mesh = unreal.load_asset(raw_folder + '/SK_' + source['stem'] + '_Body_Full')
    assert isinstance(source_mesh, unreal.SkeletalMesh)
    assert raw_animation.get_editor_property('skeleton') == source_mesh.get_editor_property('skeleton')
    retargeter = unreal.load_asset('/MetaHumanCharacter/Animation/Retargeting/RTG_MH_IKRig')
    assert retargeter
    inputs = unreal.IKRetargetBatchOperationInputs()
    inputs.set_editor_properties({
        'assets_to_retarget': [unreal.EditorAssetLibrary.find_asset_data(source['animation'])],
        'source_mesh': source_mesh, 'target_mesh': body, 'ik_retarget_asset': retargeter,
        'search': raw_animation.get_name(), 'replace': name, 'target_path': root + '/Animations',
        'use_source_path': False, 'include_referenced_assets': False, 'overwrite_existing_files': False,
    })
    exported = unreal.IKRetargetBatchOperation.run_batch_retarget(inputs)
    assert len(exported) == 1, exported
    animation = exported[0].get_asset()
    assert animation and animation.get_path_name().split('.')[0] == path, str(animation)
    assert unreal.EditorAssetLibrary.save_loaded_asset(animation, only_if_is_dirty=False)
    reloaded, error = unreal.EditorLoadingAndSavingUtils.reload_packages(
        [animation.get_outermost()], unreal.ReloadPackagesInteractionMode.ASSUME_POSITIVE)
    assert reloaded and not str(error), str(error)
    animation = unreal.load_asset(path)
    assert animation.get_editor_property('skeleton') == body.get_editor_property('skeleton')
    motion = verify_motion(animation, source['image_count'])
    length = float(animation.get_editor_property('sequence_length'))
    assert abs(length - (source['image_count'] - 1) / 30.0) < 1.0 / 30.0
    result = {'id': character['id'], 'take': source['stem'], 'body_mesh': body.get_path_name(),
              'blueprint': character['blueprint'], 'animation': animation.get_path_name(),
              'source_performance': p.get_path_name(), 'source_animation': source['animation'],
              'source_mesh': source_mesh.get_path_name(), 'retargeter': retargeter.get_path_name(),
              'seconds': length, 'image_count': source['image_count'],
              'motion': motion, 'saved_and_reloaded': True, 'verified_utc': common.utc()}
    unreal.log('SHORE_CAST_ANIMATION_FITTED|' + json.dumps(result))
    return result


def run():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert editor.get_game_world() is None
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
    assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
    brief = common.read(folder / 'shore_cast_brief.json')
    cast = common.read(folder / 'shore_cast_assets.json')
    source_batch = common.read(folder / 'batch_status.json')
    assert not common.batch_issues(source_batch, common.read(folder / 'batch_final_audit.json'))
    assert len(cast['characters']) == 6
    approved = {c['id']: c for c in brief['characters']}
    sources = {j['stem']: j for j in source_batch['jobs']}
    output_path = folder / 'shore_cast_fitted_animations.json'
    output = common.read(output_path) if output_path.exists() else {'characters': []}
    done = {c['id']: c for c in output['characters']}
    for character in cast['characters']:
        desired = approved[character['id']]
        assert character['take'] == desired['take']
        if character['id'] in done:
            previous = done[character['id']]
            assert previous['body_mesh'] == character['body_mesh']
            assert unreal.EditorAssetLibrary.does_asset_exist(previous['animation'])
            continue
        result = fit_one(character, sources[desired['take']], brief['output_root'])
        output['characters'].append(result)
        common.write(output_path, output)
    assert len(output['characters']) == 6
    unreal.log('SHORE_CAST_ALL_SIX_ANIMATIONS_FITTED')


if __name__ == '__main__':
    run()
