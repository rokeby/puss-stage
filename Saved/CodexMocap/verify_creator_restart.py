"""Read-only verification in the freshly launched Editor."""
import json
import os
import pathlib
import sys
import unreal

project = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
assert project == pathlib.Path('E:/PussStage').resolve()
folder = str(project / 'Saved' / 'CodexMocap')
if folder not in sys.path:
    sys.path.insert(0, folder)
import restart_common as common
plan = common.read(common.PLAN)
assert os.getpid() != plan['old_editor_pid'], 'Old Editor is still serving MCP'
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world().get_path_name().split('.', 1)[0]
assert world == plan['world'], 'The restarted Editor opened a different map'
assert editor.get_game_world() is None
plugins = [str(p) for p in unreal.PluginBlueprintLibrary.get_enabled_plugin_names()]
assert 'MetaHumanCharacter' in plugins, 'Creator plugin is not enabled'
classes = ['MetaHumanCharacter', 'MetaHumanCharacterFactoryNew', 'MetaHumanCharacterEditorSubsystem', 'MetaHumanCharacterSkinSettings']
assert all(hasattr(unreal, name) for name in classes), 'Creator Python classes are missing'
subsystem = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
assert subsystem is not None
assert unreal.EditorAssetLibrary.does_asset_exist('/MetaHumanCharacter/Body/IdentityTemplate/SKM_Body_DNA')
status = common.read(common.FOLDER / 'batch_status.json')
assert not common.batch_issues(status, common.read(common.FOLDER / 'batch_final_audit.json'))
for job in status['jobs']:
    assert unreal.EditorAssetLibrary.does_asset_exist(job['performance'])
    assert unreal.EditorAssetLibrary.does_asset_exist(job['animation'])
result = {'verified_utc': common.utc(), 'token': plan['token'], 'pid': os.getpid(), 'project': str(project),
          'world': world, 'creator_enabled': True, 'creator_classes': classes,
          'creator_subsystem': subsystem.get_path_name(), 'all_eight_saved_outputs_present': True,
          'dirty_content': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
          'dirty_maps': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
common.write(common.VERIFIED, result)
unreal.log('MOCAP_CREATOR_RESTART_VERIFIED|' + json.dumps(result))
