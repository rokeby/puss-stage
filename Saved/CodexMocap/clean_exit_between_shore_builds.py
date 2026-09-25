"""Request a normal editor exit only at a clean, saved assembly boundary."""
import builtins
import json
import pathlib
import time
import unreal

project = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
assert project == pathlib.Path('E:/PussStage').resolve()
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world()
assert editor.get_editor_world().get_path_name().split('.')[0] == '/Engine/Maps/Entry'
assert not getattr(builtins, 'PUSS_SHORE_ASSEMBLY_RUNNING', False)
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
folder = project / 'Saved/CodexMocap'
cast = json.loads((folder / 'shore_cast_assets.json').read_text(encoding='utf-8'))
assert len(cast['characters']) == 4
for person in cast['characters']:
    inventory = json.loads((folder / ('assembly_assets_' + person['id'] + '.json')).read_text(encoding='utf-8'))
    assert len(inventory['assets']) == person['asset_count']
    for record in inventory['assets']:
        package = record['path'].split('.')[0]
        assert package.startswith('/Game/Metahuman/ShoreCast_20260910/Assembled/')
        disk = project / 'Content' / (package[len('/Game/'):] + '.uasset')
        assert disk.is_file() and disk.stat().st_size > 0, str(disk)
deadline = time.monotonic() + 3
def quit_when_ready(delta):
    if time.monotonic() < deadline:
        return
    unreal.unregister_slate_post_tick_callback(handle)
    unreal.log('SHORE_CLEAN_EDITOR_EXIT|saved_characters=4|dirty_packages=0')
    unreal.SystemLibrary.quit_editor()
handle = unreal.register_slate_post_tick_callback(quit_when_ready)
unreal.log('SHORE_CLEAN_EDITOR_EXIT_SCHEDULED|saved_characters=4')
