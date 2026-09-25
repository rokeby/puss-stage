"""Read saved assembly assets, reload body packages, and verify disk assets."""
import datetime
import json
import pathlib
import unreal

project = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
assert project == pathlib.Path('E:/PussStage').resolve()
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
folder = project / 'Saved/CodexMocap'
root = '/Game/Metahuman/ShoreCast_20260910/Assembled'
cast = json.loads((folder / 'shore_cast_assets.json').read_text(encoding='utf-8'))
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
results = []
for person in cast['characters']:
    bp_data = unreal.EditorAssetLibrary.find_asset_data(person['blueprint'])
    body = unreal.load_asset(person['body_mesh'])
    assert str(bp_data.asset_class_path.asset_name) == 'Blueprint' and body
    # Reload the body independently: reloading the Blueprint also reloads the
    # facial ARKit mapping while its generated Control Rig is still bound.
    packages = [body.get_outermost()]
    body = None
    success, error = unreal.EditorLoadingAndSavingUtils.reload_packages(packages, unreal.ReloadPackagesInteractionMode.ASSUME_POSITIVE)
    assert success and not str(error), str(error)
    body = unreal.load_asset(person['body_mesh'])
    assert body.get_editor_property('skeleton').get_path_name() == person['skeleton']
    scoped = root + '/' + person['id']
    assets = unreal.EditorAssetLibrary.list_assets(scoped, recursive=True, include_folder=False)
    assert len(assets) == person['asset_count']
    total = 0
    for asset in assets:
        package = asset.split('.')[0]
        assert package.startswith(root + '/')
        disk = project / 'Content' / (package[len('/Game/'):] + '.uasset')
        assert disk.is_file() and disk.stat().st_size > 0, str(disk)
        total += disk.stat().st_size
    physics = body.get_editor_property('physics_asset')
    results.append({'id': person['id'], 'assets_on_disk': len(assets), 'bytes': total,
                    'body_reloaded': True, 'blueprint_registry_class_valid': True, 'skeleton': person['skeleton'],
                    'physics_asset': physics.get_path_name() if physics else None})
dirty = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
report = {'characters': results, 'remaining_dirty_packages': dirty,
          'verified_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
(folder / 'shore_assembly_saved_audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
unreal.log('SHORE_ASSEMBLY_SAVED_READBACK_SUCCESS|' + json.dumps(report))
body = None
unreal.SystemLibrary.collect_garbage()
