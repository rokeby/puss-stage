"""Inspect Creator assets/API after restart; do not create or mutate assets."""
import json
import os
import pathlib
import sys
import unreal

project = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
assert project == pathlib.Path('E:/PussStage').resolve()
folder = project / 'Saved' / 'CodexMocap'
if str(folder) not in sys.path:
    sys.path.insert(0, str(folder))
import restart_common as common
assert hasattr(unreal, 'MetaHumanCharacterEditorSubsystem')
subsystem = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
registry = unreal.AssetRegistryHelpers.get_asset_registry()
character_class = unreal.TopLevelAssetPath('/Script/MetaHumanCharacter', 'MetaHumanCharacter')
presets = [{'package': str(a.package_name), 'asset_name': str(a.asset_name)}
           for a in registry.get_assets_by_class(character_class, True)]
wardrobe = []
for a in registry.get_assets_by_path('/MetaHumanCharacter/Optional', recursive=True):
    package = str(a.package_name)
    if '/Bindings/' in package or '/Clothing/WI_' in package:
        wardrobe.append({'package': package, 'class': str(a.asset_class_path)})
settings = unreal.get_default_object(unreal.MetaHumanCharacterEditorSettings)
result = {'pid': os.getpid(), 'checked_utc': common.utc(), 'presets': presets, 'wardrobe': wardrobe,
          'texture_synthesis_model_dir': str(settings.get_editor_property('texture_synthesis_model_dir')),
          'preset_directories': [str(p) for p in settings.get_editor_property('presets_directories')],
          'creator_subsystem': subsystem.get_path_name(),
          'dirty_content': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
          'dirty_maps': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
common.write(folder / 'shore_cast_api_inventory.json', result)
api = []
for name in ['MetaHumanCharacter', 'MetaHumanCharacterEditorSubsystem', 'MetaHumanCharacterBodyConstraint',
             'MetaHumanCharacterSkinProperties', 'MetaHumanCharacterSkinSettings', 'MetaHumanCharacterHeadModelSettings',
             'MetaHumanCharacterAssemblySettings', 'MetaHumanCharacterEditorBuildParameters',
             'MetaHumanCharacterTextureRequestParams', 'MetaHumanCharacterAutoRiggingRequestParams',
             'MetaHumanCharacterViewportSettings', 'MetaHumanCharacterExportBlueprintLibrary',
             'MetaHumanPerformanceExportAnimationSettings', 'LevelSequenceEditorBlueprintLibrary',
             'AutomationLibrary', 'MovieSceneSkeletalAnimationParams']:
    cls = getattr(unreal, name, None)
    if cls:
        api += [name, str(cls.__doc__), '\n'.join(n for n in dir(cls) if not n.startswith('_'))]
        if name in ('MetaHumanCharacterEditorSubsystem', 'MetaHumanCharacterExportBlueprintLibrary', 'AutomationLibrary'):
            for method_name in dir(cls):
                if method_name.startswith('_'):
                    continue
                if any(s in method_name for s in ['body', 'face', 'skin', 'rig', 'build', 'preview', 'preset', 'screenshot', 'texture', 'mesh', 'export']):
                    api.append(method_name + '\n' + str(getattr(cls, method_name).__doc__))
(folder / 'shore_cast_api.txt').write_text('\n\n'.join(api), encoding='utf-8')
unreal.log('SHORE_CAST_API_INSPECT_SUCCESS|presets=' + str(len(presets)) + '|wardrobe=' + str(len(wardrobe)))

# The user also authorized placing the cast by the clam with the existing head
# drapes. Collect that live setup after restart without making scene changes.
import inspect_clam_setup
inspect_clam_setup.run()
