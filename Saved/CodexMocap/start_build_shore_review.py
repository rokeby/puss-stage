import importlib
import pathlib
import sys
import time
import traceback
import unreal

folder = pathlib.Path('E:/PussStage/Saved/CodexMocap')
if str(folder) not in sys.path:
    sys.path.insert(0, str(folder))
import restart_common as common
due = time.monotonic() + 3
def build(delta):
    if time.monotonic() < due:
        return
    unreal.unregister_slate_post_tick_callback(handle)
    try:
        import build_shore_review
        importlib.reload(build_shore_review).run()
        common.write(folder / 'shore_review_build_status.json', {'state': 'complete'})
    except Exception as exc:
        common.write(folder / 'shore_review_build_status.json', {'state': 'attention_required', 'error': str(exc), 'traceback': traceback.format_exc()})
        unreal.log_error('SHORE_REVIEW_BUILD_FAILED|' + str(exc))
handle = unreal.register_slate_post_tick_callback(build)
common.write(folder / 'shore_review_build_status.json', {'state': 'scheduled'})
unreal.log('SHORE_REVIEW_BUILD_SCHEDULED')
