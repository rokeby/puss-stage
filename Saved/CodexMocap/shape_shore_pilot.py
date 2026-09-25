import json
import pathlib
import sys
import unreal
folder = pathlib.Path('E:/PussStage/Saved/CodexMocap')
if str(folder) not in sys.path:
    sys.path.insert(0, str(folder))
import shore_character_authoring as author
person = json.loads((folder / 'shore_cast_brief.json').read_text(encoding='utf-8'))['characters'][0]
character = unreal.load_asset(author.ROOT + '/Characters/MHC_' + person['id'])
unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(character)
sub = author.open_character(character)
constraints = list(sub.get_body_constraints(character, False))
targets = {'Waist': 92.0, 'High Hip': 89.0, 'Hip': 84.0, 'Chest': 80.0,
           'Underbust': 74.0, 'Bicep': 24.0, 'Forearm': 22.0,
           'Thigh': 40.0, 'Calf': 31.5}
for constraint in constraints:
    name = str(constraint.name)
    if name == 'Fat':
        constraint.is_active = False
    if name in targets:
        assert constraint.min_measurement <= targets[name] <= constraint.max_measurement
        constraint.is_active = True
        constraint.target_measurement = targets[name]
sub.set_body_constraints(character, constraints)
sub.commit_body_state(character)
author.set_pale_skin(character, 0.015, 0.15)
author.save_character(character, person, '/MetaHumanCharacter/Optional/Presets/Walter', 'gaunt_with_rounded_abdomen')
sub.remove_object_to_edit(character)
assert unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).open_editor_for_assets([character])
unreal.log('SHORE_PILOT_BELLY_SHAPE_SAVED')
