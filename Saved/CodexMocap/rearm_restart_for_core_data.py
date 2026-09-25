"""Replace only our waiting helper to insert the newly discovered data-install step."""
import builtins
import datetime
import os
import pathlib
import shutil
import subprocess
import sys
import unreal

folder = 'E:/PussStage/Saved/CodexMocap'
if folder not in sys.path:
    sys.path.insert(0, folder)
import restart_common as common
plan = common.read(common.PLAN)
status = common.read(common.STATUS)
assert plan['old_editor_pid'] == os.getpid()
assert status['state'] == 'waiting_for_verified_batch'
assert builtins.PUSS_MOCAP_BATCH.running
previous = builtins.PUSS_CREATOR_RESTART_HELPER
assert previous.pid == status['helper_pid'] and previous.poll() is None
backup = common.PROJECT.parent / 'Backups' / ('PreShoreCharacterPreparation-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
backup.mkdir(exist_ok=False)
shutil.copy2(common.PLAN, backup / common.PLAN.name)
shutil.copy2(common.PROJECT, backup / common.PROJECT.name)
# Terminate only the idle helper created for this task; the Editor and mocap are untouched.
previous.terminate()
previous.wait(timeout=10)
plan['require_core_data_installation'] = True
plan['character_brief'] = 'Six pale gaunt pot-bellied adults: three men and three women; five in their 50s and one woman around 25. Pair one with each shore take.'
common.write(common.PLAN, plan)
with (common.FOLDER / 'creator_restart_helper.log').open('a', encoding='utf-8') as log:
    helper = subprocess.Popen([str(common.PYTHON), str(common.FOLDER / 'restart_after_mocap.py')],
        cwd=str(common.PROJECT.parent), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
        close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
builtins.PUSS_CREATOR_RESTART_HELPER = helper
unreal.log('MOCAP_CREATOR_RESTART_WITH_CORE_DATA_ARMED|helper_pid=' + str(helper.pid) + '|backup=' + str(backup))
