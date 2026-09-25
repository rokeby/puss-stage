"""Create the first scoped character and inspect actual parametric constraints."""
import json
import pathlib
import sys
import unreal

folder = pathlib.Path('E:/PussStage/Saved/CodexMocap')
if str(folder) not in sys.path:
    sys.path.insert(0, str(folder))
import shore_character_authoring as author
brief = json.loads((folder / 'shore_cast_brief.json').read_text(encoding='utf-8'))
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
person = brief['characters'][0]
preset = '/MetaHumanCharacter/Optional/Presets/Walter'
character = author.make_from_preset(person, preset)
before = author.constraints_report(character)
after = author.set_global_shape(character, person)
author.set_pale_skin(character, 0.07, 0.22)
record = author.save_character(character, person, preset, 'lean_base_before_belly_sculpt')
record['before_constraints'] = before
(folder / 'shore_pilot_setup.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).open_editor_for_assets([character])
unreal.log('SHORE_PILOT_LEAN_BASE_CREATED|' + character.get_path_name())
