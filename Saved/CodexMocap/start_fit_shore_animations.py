"""Schedule the six body exports after MCP returns, with persistent status."""
import builtins
import importlib
import pathlib
import sys
import time
import traceback
import unreal

project = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
assert project == pathlib.Path('E:/PussStage').resolve()
folder = project / 'Saved/CodexMocap'
assert (folder / 'shore_cast_assets.json').is_file(), 'Assemble and verify all six characters first'
assert not getattr(builtins, 'PUSS_SHORE_FIT_IN_PROGRESS', False), 'Export already scheduled/running'
if str(folder) not in sys.path:
    sys.path.insert(0, str(folder))
import restart_common as common
builtins.PUSS_SHORE_FIT_IN_PROGRESS = True
due = time.monotonic() + 3.0
state_path = folder / 'shore_cast_fit_status.json'
common.write(state_path, {'state': 'scheduled', 'updated_utc': common.utc()})


def deferred_fit(delta_seconds):
    if time.monotonic() < due:
        return
    unreal.unregister_slate_post_tick_callback(builtins.PUSS_SHORE_FIT_CALLBACK)
    try:
        common.write(state_path, {'state': 'running', 'updated_utc': common.utc()})
        import fit_shore_animations
        importlib.reload(fit_shore_animations).run()
        common.write(state_path, {'state': 'complete', 'updated_utc': common.utc()})
    except Exception as exc:
        common.write(state_path, {'state': 'attention_required', 'error': str(exc),
                                   'traceback': traceback.format_exc(), 'updated_utc': common.utc()})
        unreal.log_error('SHORE_CAST_FITTING_FAILED|' + str(exc))
    finally:
        builtins.PUSS_SHORE_FIT_IN_PROGRESS = False


builtins.PUSS_SHORE_FIT_CALLBACK = unreal.register_slate_post_tick_callback(deferred_fit)
unreal.log('SHORE_CAST_FITTING_SCHEDULED')
