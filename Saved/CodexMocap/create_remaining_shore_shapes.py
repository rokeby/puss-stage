"""Create and save the six approved draft appearances, one per editor tick."""
import builtins
import importlib
import json
import pathlib
import sys
import time
import traceback
import unreal

folder = pathlib.Path('E:/PussStage/Saved/CodexMocap')
if str(folder) not in sys.path:
    sys.path.insert(0, str(folder))
import shore_character_authoring as author
importlib.reload(author)
brief = json.loads((folder / 'shore_cast_brief.json').read_text(encoding='utf-8'))
assert brief['approved'] and len(brief['characters']) == 6
assert not getattr(builtins, 'PUSS_SHORE_SHAPES_RUNNING', False)
author.subsystem()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
unrelated = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
             if not p.get_path_name().startswith(author.ROOT + '/Characters/')]
assert not unrelated, unrelated
presets = ['Walter', 'Lani', 'Aoi', 'Grace', 'Lorenzo', 'Celeste']
extras = [26.0, 21.0, 26.0, 22.0, 25.0, 19.0]
tones = [(0.015, 0.15), (0.025, 0.21), (0.02, 0.12), (0.01, 0.18), (0.03, 0.25), (0.025, 0.28)]
state = {'state': 'scheduled', 'completed': [], 'index': 0, 'busy': False}
builtins.PUSS_SHORE_SHAPES_RUNNING = True


def write():
    (folder / 'shore_shape_status.json').write_text(json.dumps(state, indent=2), encoding='utf-8')


def tick(delta):
    if state['busy'] or time.monotonic() < start_after:
        return
    state['busy'] = True
    try:
        index = state['index']
        person = brief['characters'][index]
        state.update(state='running', current=person['id'])
        write()
        path = author.ROOT + '/Characters/MHC_' + person['id']
        preset = '/MetaHumanCharacter/Optional/Presets/' + presets[index]
        if index == 0:
            character = unreal.load_asset(path)
            assert character
            unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(character)
            author.open_character(character)
        else:
            character = author.make_from_preset(person, preset)
            author.set_global_shape(character, person, fat_fraction=0.13 + 0.01 * (index % 2), muscle_fraction=0.12)
            author.set_rounded_abdomen(character, extras[index])
        author.set_pale_skin(character, *tones[index])
        record = author.save_character(character, person, preset, 'gaunt_pot_bellied_draft')
        author.open_character(character).remove_object_to_edit(character)
        assert unreal.EditorAssetLibrary.does_asset_exist(path)
        state['completed'].append({'id': person['id'], 'character': path, 'source_preset': preset, 'saved': True})
        state['index'] += 1
        if state['index'] == 6:
            state['state'] = 'all_six_draft_appearances_saved'
            unreal.unregister_slate_post_tick_callback(handle)
            builtins.PUSS_SHORE_SHAPES_RUNNING = False
            unreal.log('SHORE_ALL_SIX_DRAFT_APPEARANCES_SAVED')
    except Exception as exc:
        state.update(state='attention_required', error=str(exc), traceback=traceback.format_exc())
        unreal.unregister_slate_post_tick_callback(handle)
        builtins.PUSS_SHORE_SHAPES_RUNNING = False
        unreal.log_error('SHORE_SHAPES_FAILED|' + str(exc))
    finally:
        state['busy'] = False
        write()


start_after = time.monotonic() + 3
handle = unreal.register_slate_post_tick_callback(tick)
write()
unreal.log('SHORE_SIX_SHAPES_SCHEDULED')
