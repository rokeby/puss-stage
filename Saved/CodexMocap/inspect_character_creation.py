"""Read-only capability check; leave the running mocap queue untouched."""
import builtins
import datetime
import json
import os
import pathlib
import unreal

project = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
assert project == pathlib.Path('E:/PussStage').resolve(), str(project)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
batch = getattr(builtins, 'PUSS_MOCAP_BATCH', None)
classes = ['MetaHumanCharacter', 'MetaHumanCharacterFactoryNew', 'MetaHumanCharacterEditorSubsystem',
           'MetaHumanCharacterSkinSettings', 'PluginBlueprintLibrary', 'PluginManager']
registry = unreal.AssetRegistryHelpers.get_asset_registry()
assets = []
for folder in ['/Game/MetaHumans', '/Game/Metahuman']:
    for asset in registry.get_assets_by_path(folder, recursive=True):
        if '/FullTakes_20260910/' not in str(asset.package_name):
            assets.append({'package': str(asset.package_name), 'class': str(asset.asset_class_path)})
result = {
    'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'pid': os.getpid(), 'project': str(project), 'engine': unreal.SystemLibrary.get_engine_version(),
    'world': editor.get_editor_world().get_path_name(), 'pie': editor.get_game_world() is not None,
    'classes_available': {name: hasattr(unreal, name) for name in classes},
    'mocap_running': bool(batch and batch.running),
    'mocap_current': batch.job['stem'] if batch and batch.job else None,
    'dirty_content': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
    'dirty_maps': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
    'existing_assets': assets,
}
api = []
for name in classes:
    cls = getattr(unreal, name, None)
    if cls:
        api += [name, str(cls.__doc__), '\n'.join(n for n in dir(cls) if not n.startswith('_'))]
plugin_api = getattr(unreal, 'PluginBlueprintLibrary', None)
if plugin_api and hasattr(plugin_api, 'get_enabled_plugin_names'):
    result['enabled_metahuman_plugins'] = [str(n) for n in plugin_api.get_enabled_plugin_names() if 'metahuman' in str(n).lower()]
folder = project / 'Saved' / 'CodexMocap'
(folder / 'character_creation_preflight.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
(folder / 'character_creation_api.txt').write_text('\n\n'.join(api), encoding='utf-8')
unreal.log('MOCAP_CHARACTER_CREATION_INSPECT_SUCCESS|' + json.dumps({k: v for k, v in result.items() if k != 'existing_assets'}))
