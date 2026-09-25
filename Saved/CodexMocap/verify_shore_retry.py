import json
import os
import pathlib
import unreal
project = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
assert project == pathlib.Path('E:/PussStage').resolve()
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world()
world_path = editor.get_editor_world().get_path_name().split('.')[0]
assert world_path in ('/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice', '/Engine/Maps/Entry')
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
char = unreal.load_asset('/Game/Metahuman/ShoreCast_20260910/Characters/MHC_Shore01_M56')
sub = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
assert char and char.get_editor_property('has_high_resolution_textures')
added = not sub.is_object_added_for_editing(char)
if added:
    assert sub.try_add_object_to_edit(char)
try:
    assert sub.can_build_meta_human(char, log_error=True)
finally:
    if added:
        sub.remove_object_to_edit(char)
result = {'pid': os.getpid(), 'project': str(project), 'pilot_build_ready': True, 'pilot_texture_sources_saved': True,
          'world': world_path,
          'scoped_output_assets': list(unreal.EditorAssetLibrary.list_assets('/Game/Metahuman/ShoreCast_20260910/Assembled'))}
(project / 'Saved/CodexMocap/shore_retry_verified.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
unreal.log('SHORE_RETRY_PREFLIGHT_SUCCESS|' + json.dumps(result))
