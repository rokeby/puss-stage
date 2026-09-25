"""Request a joints-only production rig for the first character."""
import builtins
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
shape = json.loads((folder / 'shore_shape_status.json').read_text(encoding='utf-8'))
assert shape['state'] == 'all_six_draft_appearances_saved'
assert not getattr(builtins, 'PUSS_SHORE_RIG_RUNNING', False)
builtins.PUSS_SHORE_RIG_RUNNING = True
state = {'state': 'scheduled', 'character': author.ROOT + '/Characters/MHC_Shore01_M56'}


def write():
    (folder / 'shore_pilot_rig_status.json').write_text(json.dumps(state, indent=2), encoding='utf-8')


def tick(delta):
    if time.monotonic() < start_after:
        return
    unreal.unregister_slate_post_tick_callback(handle)
    try:
        character = unreal.load_asset(state['character'])
        sub = author.open_character(character)
        state['state'] = 'requesting_joints_only_rig'
        write()
        params = unreal.MetaHumanCharacterAutoRiggingRequestParams()
        params.blocking = True
        params.report_progress = False
        params.rig_type = unreal.MetaHumanRigType.JOINTS_ONLY
        sub.request_auto_rigging(character, params)
        assert unreal.EditorAssetLibrary.save_loaded_asset(character, only_if_is_dirty=False)
        state['state'] = 'rig_request_returned'
        state['can_build'] = sub.can_build_meta_human(character, log_error=True)
        state['high_resolution_textures'] = bool(character.get_editor_property('has_high_resolution_textures'))
        sub.remove_object_to_edit(character)
        unreal.log('SHORE_PILOT_RIG_REQUEST_RETURNED|' + json.dumps(state))
    except Exception as exc:
        state.update(state='attention_required', error=str(exc), traceback=traceback.format_exc())
        unreal.log_error('SHORE_PILOT_RIG_FAILED|' + str(exc))
    finally:
        builtins.PUSS_SHORE_RIG_RUNNING = False
        write()


start_after = time.monotonic() + 3
handle = unreal.register_slate_post_tick_callback(tick)
write()
unreal.log('SHORE_PILOT_RIG_REQUEST_SCHEDULED')
