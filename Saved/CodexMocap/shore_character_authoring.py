"""Narrow helpers for the approved six-character cast. No work runs on import."""
import json
import pathlib
import unreal

PROJECT = pathlib.Path('E:/PussStage')
FOLDER = PROJECT / 'Saved/CodexMocap'
ROOT = '/Game/Metahuman/ShoreCast_20260910'


def subsystem():
    actual = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
    assert actual == PROJECT.resolve()
    assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    return unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)


def open_character(character):
    sub = subsystem()
    if not sub.is_object_added_for_editing(character):
        assert sub.try_add_object_to_edit(character), character.get_path_name()
    return sub


def constraints_report(character):
    return [{'name': str(c.name), 'active': bool(c.is_active), 'target': float(c.target_measurement),
             'min': float(c.min_measurement), 'max': float(c.max_measurement)}
            for c in open_character(character).get_body_constraints(character, False)]


def make_from_preset(person, preset_path):
    path = ROOT + '/Characters/MHC_' + person['id']
    assert not unreal.EditorAssetLibrary.does_asset_exist(path), 'Existing character: ' + path
    preset = unreal.load_asset(preset_path)
    assert isinstance(preset, unreal.MetaHumanCharacter), preset_path
    character = unreal.EditorAssetLibrary.duplicate_asset(preset_path, path)
    assert isinstance(character, unreal.MetaHumanCharacter)
    open_character(character)
    return character


def set_constraints(character, values, reset_active=False):
    sub = open_character(character)
    constraints = list(sub.get_body_constraints(character, False))
    names = {str(c.name) for c in constraints}
    assert set(values) <= names, sorted(set(values) - names)
    for c in constraints:
        name = str(c.name)
        if reset_active:
            c.is_active = False
        if name in values:
            target = float(values[name])
            assert c.min_measurement <= target <= c.max_measurement, (name, target, c.min_measurement, c.max_measurement)
            c.is_active = True
            c.target_measurement = target
    sub.set_body_constraints(character, constraints)
    sub.commit_body_state(character)
    return constraints_report(character)


def set_global_shape(character, person, fat_fraction=0.13, muscle_fraction=0.12):
    available = {r['name']: r for r in constraints_report(character)}
    def normalized(name, value):
        c = available[name]
        return c['min'] + value * (c['max'] - c['min'])
    # Masculine/Feminine direction is defined by Epic's installed generator example.
    values = {'Height': person['height_cm'],
              'Masculine/Feminine': normalized('Masculine/Feminine', 0.10 if person['gender'] == 'male' else 0.90),
              'Fat': normalized('Fat', fat_fraction),
              'Muscularity': normalized('Muscularity', muscle_fraction)}
    return set_constraints(character, values, reset_active=True)


def set_pale_skin(character, u, v, roughness=1.06):
    # Creator exposes a roughness multiplier (0.85-1.15), not a 0-1 value.
    assert 0 <= u <= 1 and 0 <= v <= 1 and 0.85 <= roughness <= 1.15
    settings = character.get_editor_property('skin_settings')
    skin = settings.skin
    skin.u, skin.v, skin.roughness = u, v, roughness
    settings.skin = skin
    character.set_editor_property('preview_material_type', unreal.MetaHumanCharacterSkinPreviewMaterial.EDITABLE)
    open_character(character).commit_skin_settings(character, settings)


def set_rounded_abdomen(character, extra_cm=24.0):
    """Keep the lean limb measurements while increasing abdominal girth."""
    sub = open_character(character)
    constraints = list(sub.get_body_constraints(character, False))
    base = {str(c.name): float(c.target_measurement) for c in constraints}
    pinned = ('Chest', 'Underbust', 'Bicep', 'Forearm', 'Thigh', 'Calf', 'Neck')
    targets = {name: base[name] for name in pinned}
    targets['Waist'] = base['Waist'] + extra_cm
    targets['High Hip'] = base['High Hip'] + extra_cm * 0.65
    targets['Hip'] = base['Hip'] + extra_cm * 0.20
    for c in constraints:
        name = str(c.name)
        if name == 'Fat':
            c.is_active = False
        if name in targets:
            c.is_active = True
            c.target_measurement = min(float(c.max_measurement), max(float(c.min_measurement), targets[name]))
    sub.set_body_constraints(character, constraints)
    sub.commit_body_state(character)
    return constraints_report(character)


def save_character(character, person, source_preset, phase):
    assert character.get_path_name().startswith(ROOT + '/Characters/')
    assert unreal.EditorAssetLibrary.save_loaded_asset(character, only_if_is_dirty=False)
    sub = open_character(character)
    landmarks = sub.get_face_landmarks(character)
    record = {'id': person['id'], 'take': person['take'], 'character': character.get_path_name(),
              'source_preset': source_preset, 'phase': phase, 'constraints': constraints_report(character),
              'face_landmarks': [[v.x, v.y, v.z] for v in landmarks],
              'skin_settings': str(character.get_editor_property('skin_settings')),
              'saved': True, 'visual_review': 'pending'}
    destination = FOLDER / ('appearance_' + person['id'] + '.json')
    destination.write_text(json.dumps(record, indent=2), encoding='utf-8')
    unreal.log('SHORE_CHARACTER_APPEARANCE_SAVED|' + person['id'] + '|' + phase)
    return record
