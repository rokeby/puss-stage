import pathlib
import unreal
assert pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve() == pathlib.Path('E:/PussStage').resolve()
character = unreal.load_asset('/Game/Metahuman/ShoreCast_20260910/Characters/MHC_Shore01_M56')
sub = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
if sub.is_object_added_for_editing(character):
    sub.remove_object_to_edit(character)
assert unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).open_editor_for_assets([character])
unreal.log('SHORE_PILOT_EDITOR_OPEN_REQUESTED')
